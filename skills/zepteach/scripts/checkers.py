#!/usr/bin/env python3
"""Marking the answers a machine can mark.

Four ways an answer gets judged. Three of them are here; the fourth, rubric
marking, needs a reader and lives in grade.py.

  exact     the answer is a specific thing
  numeric   the answer is a number within a tolerance
  checker   run a program the course adapter registered and read its result

The design rule shared by all three: **a check that cannot run produces "not
checked", never "passed".** The tempting failure is to treat a missing
checker or a crashed program as an inconvenience and let the answer through.
That converts an infrastructure problem into a false record of what the
learner can do, and the record outlives the infrastructure problem.

Nothing here knows what it is checking. A checker's command comes from the
adapter; this file runs it inside the boundary and reads its verdict.

Exit codes: 0 ok, 2 invalid data, 3 refused, 5 not found.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import constants as K  # noqa: E402
import sandbox as sb  # noqa: E402
import zt_state as zs  # noqa: E402

VERDICTS = ("pass", "fail", "not_checked")


def _result(verdict, why, **extra):
    out = {"verdict": verdict, "why": why}
    out.update(extra)
    return out


# ---------------------------------------------------------------------------
# exact
# ---------------------------------------------------------------------------

def _fold(s: str) -> str:
    """Normalise away differences that are not the learner's answer.

    Width and accent normalisation matters more than it looks: an answer
    typed with full-width characters, or with a different unicode
    composition, is the same answer, and failing it teaches nothing except
    that the system is unreliable.
    """
    s = unicodedata.normalize("NFKC", str(s))
    s = re.sub(r"\s+", " ", s).strip()
    return s.casefold()


def check_exact(answer: str, spec: dict) -> dict:
    expected = spec.get("expected")
    if expected is None:
        return _result("not_checked",
                       "the item says the answer is exact but does not say "
                       "what it is")

    accepted = [expected] + list(spec.get("also_accept") or [])
    if _fold(answer) in [_fold(a) for a in accepted]:
        return _result("pass", "matches the expected answer")

    return _result("fail", "does not match the expected answer",
                   expected=expected, got=str(answer)[:200])


# ---------------------------------------------------------------------------
# numeric
# ---------------------------------------------------------------------------

NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def extract_number(answer: str):
    """The number the learner is asserting.

    The last number in the answer, not the first. Working shown before the
    result is the normal shape of a worked answer, and taking the first
    number marks the first intermediate step instead of the conclusion.
    """
    found = NUMBER.findall(str(answer).replace(",", ""))
    if not found:
        return None
    try:
        return float(found[-1])
    except ValueError:
        return None


def check_numeric(answer: str, spec: dict) -> dict:
    expected = spec.get("expected")
    if expected is None:
        return _result("not_checked",
                       "the item is marked numeric but carries no expected "
                       "value")

    got = extract_number(answer)
    if got is None:
        return _result("fail", "no number in the answer",
                       got=str(answer)[:200])

    expected = float(expected)
    tol = spec.get("tolerance")
    relative = spec.get("relative", False)

    if tol is None:
        return _result("not_checked",
                       "no tolerance given, and comparing floating point "
                       "numbers for equality is not a check. State one, "
                       "including zero if the answer really is exact")

    limit = abs(float(tol) * expected) if relative else abs(float(tol))
    if abs(got - expected) <= limit:
        return _result("pass", "within tolerance", got=got,
                       expected=expected)

    # A sign error, or a factor, is worth naming rather than reporting a bare
    # mismatch: it points at the step that went wrong.
    note = None
    if expected and abs(got + expected) <= limit:
        note = "the magnitude is right and the sign is wrong"
    elif expected and got and abs(abs(got / expected) - 1) > 0.01:
        ratio = got / expected
        for factor, name in ((2, "twice"), (0.5, "half"), (10, "ten times"),
                             (0.1, "a tenth of")):
            if abs(ratio - factor) < 0.01:
                note = "the answer is " + name + " the expected value, " \
                       "which usually means one step, not the whole method"
                break

    return _result("fail", note or "outside tolerance", got=got,
                   expected=expected, tolerance=limit)


# ---------------------------------------------------------------------------
# checker
# ---------------------------------------------------------------------------

def check_with_program(answer_path: Path, checker: dict,
                       where: dict = None, runner=None) -> dict:
    """Run an adapter-registered program and read its verdict.

    The program goes through the same boundary checks as anything else: the
    paths it touches must be permitted, environment changes are refused, and
    it carries a time limit. A marking program is still a program running on
    someone's machine.
    """
    cmd = list(checker.get("command") or [])
    if not cmd:
        return _result("not_checked",
                       "the adapter registered this checker with no command")

    where = dict(where or {})

    # `or` would treat a declared 0 as "not set" and quietly substitute the
    # default, which is how an invalid limit turns into a working one. A
    # stated value is used as stated, even when it is wrong, so that the
    # boundary check refuses it rather than the default rescuing it.
    timeout = checker.get("timeout_seconds")
    if timeout is None:
        timeout = where.get("timeout_seconds")
    if timeout is None:
        timeout = K.PROBE_TIMEOUT_SECONDS

    try:
        sb.check_command(cmd, where.get("allowed_paths"), timeout)
    except sb.Refused as r:
        return _result("not_checked",
                       "the checker was refused: " + r.message,
                       refused=r.code)

    run = runner or _run
    try:
        code, out = run(cmd + [str(answer_path)], timeout)
    except Exception as exc:                          # noqa: BLE001
        return _result("not_checked",
                       "the checker could not be run: " + str(exc))

    pass_when = checker.get("pass_when", "exit code 0")
    if code == 0:
        return _result("pass", "the checker accepted it", output=out[-400:])
    return _result("fail", "the checker rejected it (" + pass_when +
                   " was not met)", exit_code=code, output=out[-400:])


def _run(cmd, timeout):
    with tempfile.TemporaryDirectory(prefix="zepteach-check-") as scratch:
        proc = subprocess.run(cmd, cwd=scratch, capture_output=True,
                              text=True, timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------

def mark(item: dict, answer: str, adapter: dict = None,
         answer_path: Path = None, runner=None) -> dict:
    """Route an item to whatever marks it.

    A rubric item is not marked here. It is handed to a separate process with
    no teaching context, which is the whole reason open-ended marking is
    trustworthy at all. Returning "not_checked" for it is correct rather than
    a gap.
    """
    grader = item.get("grader") or {}
    gtype = grader.get("type")
    spec = grader.get("spec") or {}
    if grader.get("tolerance") is not None:
        spec = dict(spec, tolerance=grader["tolerance"])

    if gtype == "exact":
        return check_exact(answer, spec)

    if gtype == "numeric":
        return check_numeric(answer, spec)

    if gtype == "checker":
        cid = grader.get("checker_id")
        registered = {c.get("checker_id"): c
                      for c in (adapter or {}).get("checkers", [])}
        if cid not in registered:
            return _result(
                "not_checked",
                "the item asks for checker " + str(cid) + " and the course "
                "adapter does not register it")
        if answer_path is None:
            return _result("not_checked",
                           "a program checker needs the answer as a file")
        return check_with_program(answer_path, registered[cid],
                                  runner=runner)

    if gtype == "rubric":
        return _result(
            "not_checked",
            "open-ended, so it goes to the separate marking process rather "
            "than being decided here")

    return _result("not_checked", "no way of marking this is recorded")


def to_attempt(item: dict, result: dict, **over) -> dict:
    """Turn a mechanical result into the start of an attempt record.

    Deliberately incomplete. How effortful the recall was and what depth the
    answer demonstrated are not things a program can see, and filling them in
    with plausible defaults would put invented data where the schedule reads
    from. They are left out so that recording fails until a person supplies
    them.
    """
    doc = {
        "schema_version": 1,
        "exercise_id": item.get("exercise_id"),
        "course_id": item.get("course_id"),
        "concept_ids": item.get("concept_ids", []),
        "graded_by": "script:" + str((item.get("grader") or {}).get("type")),
        "verdict": result["verdict"] if result["verdict"] != "not_checked"
        else "fail",
    }
    if item.get("tier"):
        doc["tier"] = item["tier"]
    if item.get("form"):
        doc["form"] = item["form"]
    doc.update(over)
    return doc


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="checkers.py",
        description="Marking the answers a machine can mark.")
    p.add_argument("--item", required=True)
    p.add_argument("--answer", required=True,
                   help="path to the answer, or the answer itself")
    p.add_argument("--adapter")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    item = json.loads(Path(args.item).read_text(encoding="utf-8"))
    adapter = json.loads(Path(args.adapter).read_text(encoding="utf-8")) \
        if args.adapter else None

    apath = Path(args.answer)
    if apath.exists():
        answer = apath.read_text(encoding="utf-8")
    else:
        answer, apath = args.answer, None

    result = mark(item, answer, adapter, apath)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["verdict"].upper() + "  " + result["why"])
        for key in ("expected", "got", "tolerance"):
            if key in result:
                print("  " + key + ": " + str(result[key]))

    if result["verdict"] == "not_checked":
        return zs.EXIT_GATE
    return zs.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
