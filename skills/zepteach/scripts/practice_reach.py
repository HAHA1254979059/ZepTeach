#!/usr/bin/env python3
"""Can this course's practice actually act on what it needs to?

This is the second stage of setting up a course, and it runs after the goal
exists, because what a course needs depends on what it is trying to achieve.

It is deliberately not a survey of the machine. An earlier version of this
file was organised around installed software and machines, which silently
assumed the subject was computational. A literature course needs a text, a
history course needs documents, and a mathematics course needs the learner to
have paper. Those are the same kind of question and get the same treatment
here.

Three things happen:

  1. Every target the course adapter declares is checked. Some checks run a
     program, some can only be answered by asking the learner.
  2. Whatever is not within reach drops to the highest rung of the
     substitution ladder that still works, and the ladder records what the
     learner no longer has to decide.
  3. The result is written down, so that no lesson ever has to decide this
     while it is running.

The one judgement that decides whether a shortfall is fatal is not about how
good a substitute is. It is whether the goal names the thing that is missing.
A goal asking for understanding of what something does survives a substitute.
A goal asking for competence with the thing itself does not, however good the
substitute is. See adapter-contract.md.

Nothing here installs anything, ever. Shortfalls become written
recommendations that the learner acts on or declines.

Exit codes: 0 ok, 2 invalid data, 3 a required target is missing and no
substitute is permitted, 5 course or adapter not found.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import constants as K  # noqa: E402
import zt_state as zs  # noqa: E402


# The substitution ladder, closest first. Each rung says what the learner
# still has to decide, which is the thing that has to survive when the real
# target cannot be reached. The depth ceilings are engineering judgements
# recorded in constants.py, not findings.
LADDER = [
    {
        "level": "direct",
        "means": "the target is at hand and the system works on it",
        "still_decided_by_learner": "everything the real task involves",
    },
    {
        "level": "learner_run",
        "means": "the learner does it outside this system and brings the "
                 "result back",
        "still_decided_by_learner": "everything, plus arranging it; what is "
                                    "lost is that the system cannot see the "
                                    "attempts that failed along the way",
    },
    {
        "level": "stand_in",
        "means": "a smaller substitute is built for the occasion, declaring "
                 "what it represents and where it stops being faithful",
        "still_decided_by_learner": "the reasoning and the choices, but "
                                    "inside a situation someone arranged; "
                                    "the difficulties are the ones that were "
                                    "put there",
    },
    {
        "level": "setup_only",
        "means": "the learner specifies the whole thing and defends each "
                 "choice, without carrying it out",
        "still_decided_by_learner": "every choice, but nothing tests whether "
                                    "the choices were right",
    },
]

LEVEL_INDEX = dict((r["level"], i) for i, r in enumerate(LADDER))


def rung(level: str) -> dict:
    return LADDER[LEVEL_INDEX[level]]


# ---------------------------------------------------------------------------
# checking one target
# ---------------------------------------------------------------------------

def check_program(spec: dict, runner=None) -> dict:
    """Run a program and see whether it behaves like the thing it is named
    after.

    Being present is not evidence. Program names collide across unrelated
    software, and a name matching a well-known scientific tool on one machine
    belongs to something entirely different on another. So the check runs the
    program and looks for a string that the real one prints.

    It runs inside a temporary directory that is removed afterwards. Many
    programs write a log or output file into wherever they were started, and
    one such file has already been found sitting in this repository.
    """
    cmd = list(spec.get("command") or [])
    if not cmd:
        return {"ran": False, "verified": False,
                "note": "no command given, so nothing could be checked"}

    exe = shutil.which(cmd[0])
    if exe is None:
        return {"ran": False, "verified": False,
                "note": "not found: " + cmd[0]}

    timeout = spec.get("timeout_seconds") or K.PROBE_TIMEOUT_SECONDS
    run = runner or _run_in_scratch
    try:
        out = run(cmd, timeout)
    except Exception as exc:                      # noqa: BLE001
        return {"ran": False, "verified": False, "path": exe,
                "note": "could not be run: " + str(exc)}

    want = spec.get("expect_in_output")
    if not want:
        return {"ran": True, "verified": False, "path": exe,
                "note": "ran, but the adapter gave nothing to look for in "
                        "its output, so this is a name match only"}

    if want.lower() in (out or "").lower():
        return {"ran": True, "verified": True, "path": exe,
                "note": "ran and identified itself"}

    return {"ran": True, "verified": False, "impostor": True, "path": exe,
            "note": "something with this name exists at " + exe + " but it "
                    "did not identify itself as expected, so it is a "
                    "different program that happens to share the name"}


def _run_in_scratch(cmd, timeout):
    with tempfile.TemporaryDirectory(prefix="zepteach-check-") as scratch:
        proc = subprocess.run(cmd, cwd=scratch, capture_output=True,
                              text=True, timeout=timeout)
        return (proc.stdout or "") + (proc.stderr or "")


def resolve_target(target: dict, answers: dict, runner=None) -> dict:
    """Decide how close this course can get to one target.

    answers holds what the learner has already said, keyed by target_id, for
    the targets that can only be settled by asking. A value of True means they
    have it, False means they do not, and a missing key means nobody asked
    yet, which is reported rather than assumed either way.
    """
    tid = target.get("target_id")
    out = {"target_id": tid, "kind": target.get("kind")}
    how = target.get("how_to_check") or {}

    if tid in answers:
        reachable = bool(answers[tid])
        out["where"] = "learner" if reachable else "none"
        out["asked"] = True
    elif how.get("command"):
        res = check_program(how, runner=runner)
        reachable = bool(res.get("verified"))
        out["verified"] = bool(res.get("verified"))
        out["verify_note"] = res.get("note")
        if res.get("impostor"):
            out["impostor"] = True
        out["where"] = "local" if reachable else "none"
    elif how.get("ask_the_learner"):
        out["unanswered"] = how["ask_the_learner"]
        out["where"] = "none"
        reachable = False
    else:
        # No way to check and nothing to ask. The honest reading is that the
        # adapter considers this always available - paper, for instance.
        reachable = True
        out["where"] = "learner"
        out["note"] = "nothing to check; the adapter treats this as always " \
                      "at hand"

    if reachable:
        out["reach"] = "direct"
        out["depth_ceiling"] = 5
        return out

    sub = target.get("substitute")
    if not sub:
        out["reach"] = "out_of_reach"
        out["depth_ceiling"] = 0
        return out

    out["reach"] = sub.get("level", "stand_in")
    out["depth_ceiling"] = sub.get(
            "depth_ceiling", K.DEFAULT_SUBSTITUTE_DEPTH_CEILING)
    out["what_is_lost"] = sub.get("what_is_lost") or \
        rung(out["reach"])["still_decided_by_learner"]
    out["where"] = "constructed" if out["reach"] == "stand_in" else "learner"
    return out


# ---------------------------------------------------------------------------
# turning target reach into what practice can do
# ---------------------------------------------------------------------------

def support_for(adapter: dict, resolved: list) -> list:
    """Which of the seven actions this course can practise, and how deep.

    An activity is held back by whichever of its targets is furthest out of
    reach, and several activities can share one action, so the action keeps
    the best reach any of its activities achieves. The exercise engine reads
    this and never re-decides it during a lesson.
    """
    by_id = dict((r["target_id"], r) for r in resolved)
    best = {}

    for act in adapter.get("activities", []):
        action = act.get("action")
        needs = act.get("acts_on") or []
        rows = [by_id[t] for t in needs if t in by_id]

        if rows:
            worst = max(rows, key=lambda r: LEVEL_INDEX.get(
                r.get("reach"), len(LADDER)))
            reach = worst.get("reach", "out_of_reach")
            ceiling = min(r.get("depth_ceiling", 5) for r in rows)
        else:
            reach = "direct"
            ceiling = 5

        # an activity cannot certify deeper than it reaches on its own terms
        span = act.get("depth_range") or [1, 5]
        ceiling = min(ceiling, span[1])

        prev = best.get(action)
        better = prev is None or (
            LEVEL_INDEX.get(reach, len(LADDER)) <
            LEVEL_INDEX.get(prev["reach"], len(LADDER)))
        if better or (prev and reach == prev["reach"]
                      and ceiling > prev["depth_ceiling"]):
            best[action] = {
                "action": action,
                "reach": reach,
                "depth_ceiling": ceiling,
                "via": needs,
                "activity": act.get("label"),
            }

    rows = []
    for action, row in best.items():
        entry = {"action": action, "reach": row["reach"],
                 "depth_ceiling": row["depth_ceiling"], "via": row["via"]}
        if row["reach"] != "direct":
            entry["fallback"] = (
                str(row["activity"]) + " becomes: " +
                rung(row["reach"])["means"] + ". What the learner still "
                "decides: " + rung(row["reach"])["still_decided_by_learner"])
        rows.append(entry)
    return sorted(rows, key=lambda r: r["action"])


def fatal_shortfalls(adapter: dict, resolved: list) -> list:
    """Targets whose absence the goal does not permit substituting.

    The test is the goal's wording, not the quality of the substitute. This
    is the one place where being unable to get something stops a course
    rather than reshaping it.
    """
    by_id = dict((r["target_id"], r) for r in resolved)
    out = []
    for t in adapter.get("targets", []):
        if not t.get("named_in_goal"):
            continue
        row = by_id.get(t.get("target_id"), {})
        if row.get("reach") != "direct":
            out.append({
                "target_id": t.get("target_id"),
                "why": t.get("why"),
                "reach": row.get("reach", "out_of_reach"),
            })
    return out


def recommendations(adapter: dict, resolved: list) -> list:
    """What to obtain. Written for the learner to act on or decline; nothing
    here is ever carried out automatically."""
    by_id = dict((r["target_id"], r) for r in resolved)
    out = []
    for t in adapter.get("targets", []):
        row = by_id.get(t.get("target_id"), {})
        if row.get("reach") == "direct":
            continue
        detail = str(t.get("why") or "")
        if row.get("impostor"):
            detail += (" Note: something of this name is already on the "
                       "machine but is a different program.")
        if row.get("unanswered"):
            detail += " Nobody has been asked yet: " + row["unanswered"]
        out.append({
            "target_id": t.get("target_id"),
            "action": "obtain or arrange access to: " +
                      str(t.get("kind")),
            "detail": detail.strip(),
        })
    return out


def check(adapter: dict, answers: dict = None, runner=None) -> dict:
    answers = answers or {}
    resolved = [resolve_target(t, answers, runner)
                for t in adapter.get("targets", [])]
    doc = {
        "schema_version": 1,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "targets": [_as_target_row(r) for r in resolved],
        "practice_support": support_for(adapter, resolved),
    }
    recs = recommendations(adapter, resolved)
    if recs:
        doc["recommendations"] = recs
    return doc


def _as_target_row(r: dict) -> dict:
    keep = ("target_id", "kind", "reach", "depth_ceiling", "where",
            "verified", "verify_note", "impostor", "what_is_lost")
    row = dict((k, r[k]) for k in keep if k in r and r[k] is not None)
    if row.get("depth_ceiling") == 0:
        del row["depth_ceiling"]
    return row


# ---------------------------------------------------------------------------
# depth: what the course wants against what practice can certify
# ---------------------------------------------------------------------------

def depth_shortfalls(support: list, curriculum: dict) -> list:
    """Concepts whose depth target is deeper than their own practice can
    certify.

    Compared against the actions the concept declares, not against the best
    action in the course. Taking the maximum across everything hides the case
    this check exists for: a concept practised only by applying a method,
    where applying reaches depth 2, is not rescued by some other concept
    being practised by constructing something at depth 5.

    A concept that declares no actions is compared against the best
    available, and the result says so, because nothing better can be done
    with no information.

    Catching this now is the point. The alternative is discovering it during
    a lesson, at which moment the cheapest move is to quietly set an easier
    exercise, and the course goes on claiming a depth it never reached.
    """
    by_action = dict((r["action"], r["depth_ceiling"]) for r in support)
    best = max(list(by_action.values()) or [0])

    out = []
    for module in curriculum.get("modules", []):
        for lesson in module.get("lessons", []):
            for c in lesson.get("concepts", []):
                want = c.get("depth_target")
                if not want:
                    continue
                actions = c.get("exercise_types") or []
                if actions:
                    ceiling = max(
                        [by_action.get(a, 0) for a in actions] or [0])
                    via = "its own practice"
                else:
                    ceiling = best
                    via = ("the best action in the course; this concept "
                           "declares no actions of its own")
                if want > ceiling:
                    out.append({"concept_id": c.get("concept_id"),
                                "depth_target": want,
                                "reachable_depth": ceiling,
                                "measured_against": via,
                                "lesson_id": lesson.get("lesson_id")})
    return out


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def render(doc: dict, fatal: list = None, depth: list = None) -> str:
    lines = ["WHAT PRACTICE CAN ACT ON"]
    for t in doc["targets"]:
        mark = "ok  " if t["reach"] == "direct" else "--  "
        line = mark + str(t["target_id"]) + " (" + str(t.get("kind")) + ")"
        line += "   " + t["reach"]
        if t.get("depth_ceiling"):
            line += ", certifies to depth " + str(t["depth_ceiling"])
        lines.append(line)
        if t.get("impostor"):
            lines.append("      a different program shares this name here")
        if t.get("what_is_lost"):
            lines.append("      lost: " + t["what_is_lost"])

    lines.append("")
    lines.append("WHAT THIS COURSE CAN PRACTISE")
    for r in doc["practice_support"]:
        line = "  " + r["action"].ljust(13) + r["reach"]
        line += "   to depth " + str(r["depth_ceiling"])
        lines.append(line)
        if r.get("fallback"):
            lines.append("      " + r["fallback"])

    if fatal:
        lines.append("")
        lines.append("BLOCKED - the goal names these, so nothing stands in "
                     "for them")
        for f in fatal:
            lines.append("  " + str(f["target_id"]) + ": " + str(f["why"]))
        lines.append("  Either obtain them, or rewrite the goal to ask for "
                     "understanding rather than competence with the thing "
                     "itself.")

    if depth:
        lines.append("")
        lines.append("DEPTH THAT CANNOT BE REACHED")
        for d in depth:
            lines.append("  " + str(d["concept_id"]) + " wants depth " +
                         str(d["depth_target"]) + "; practice reaches " +
                         str(d["reachable_depth"]))
        lines.append("  Either obtain what is missing, or lower the target "
                     "and record it. Do not quietly set easier exercises.")

    if doc.get("recommendations"):
        lines.append("")
        lines.append("WORTH OBTAINING (nothing is installed automatically)")
        for r in doc["recommendations"]:
            lines.append("  " + str(r["target_id"]) + ": " + str(r["action"]))
            if r.get("detail"):
                lines.append("      " + r["detail"])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def _load(root: Path, slug: str):
    cpath = root / "courses" / slug / "course.json"
    if not cpath.exists():
        print("no such course: " + slug, file=sys.stderr)
        return None, None
    course = zs.read_json(cpath)
    ref = course.get("adapter_ref")
    if not ref:
        print("course " + slug + " has no adapter yet; generate one first "
              "(see adapter-contract.md)", file=sys.stderr)
        return course, None
    apath = root / ref
    if not apath.exists():
        print("adapter not found at " + str(apath), file=sys.stderr)
        return course, None
    return course, zs.read_json(apath)


def cmd_check(args) -> int:
    root = Path(args.root) if args.root else zs.default_root()
    course, adapter = _load(root, args.course)
    if adapter is None:
        return zs.EXIT_NOT_FOUND

    errs = zs.validate_doc(adapter, "adapter")
    if errs:
        for e in errs:
            print("[adapter] " + e, file=sys.stderr)
        return zs.EXIT_VALIDATION

    answers = json.loads(args.answers) if args.answers else {}
    doc = check(adapter, answers)

    errs = zs.validate_doc(doc, "capabilities")
    if errs:
        for e in errs:
            print("[result] " + e, file=sys.stderr)
        return zs.EXIT_VALIDATION

    fatal = fatal_shortfalls(adapter, doc["targets"])
    cur_path = root / "courses" / args.course / "curriculum.json"
    depth = []
    if cur_path.exists():
        depth = depth_shortfalls(doc["practice_support"],
                                 zs.read_json(cur_path))

    if args.json:
        print(json.dumps({"capabilities": doc, "blocked": fatal,
                          "depth_shortfalls": depth},
                         ensure_ascii=False, indent=2))
    else:
        print(render(doc, fatal, depth))

    if args.write:
        zs.atomic_write_json(root / "capabilities.json", doc)
        print("\nwritten: capabilities.json")

    return zs.EXIT_GATE if (fatal or depth) else zs.EXIT_OK


def cmd_ladder(args) -> int:
    """Print the ladder itself. Used when explaining a shortfall to the
    learner, so that the explanation is the same every time."""
    if args.json:
        print(json.dumps(LADDER, ensure_ascii=False, indent=2))
        return zs.EXIT_OK
    for i, r in enumerate(LADDER, 1):
        print(str(i) + ". " + r["level"])
        print("   " + r["means"])
        print("   still decided by the learner: " +
              r["still_decided_by_learner"])
    return zs.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="practice_reach.py",
        description="Whether this course's practice can act on what it needs.")
    p.add_argument("--root")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("check")
    sp.add_argument("--course", required=True)
    sp.add_argument("--answers", help="JSON object of target_id to true or "
                                      "false, for what only the learner can "
                                      "answer")
    sp.add_argument("--write", action="store_true")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("ladder")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_ladder)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
