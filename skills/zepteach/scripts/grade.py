#!/usr/bin/env python3
"""Marking: what the marker is given, and what a verdict has to contain.

The design problem here is not accuracy. It is that the thing doing the
marking also did the teaching, knows the learner, and wants them to do well.
Every one of those makes a pass more likely, and none of them is visible in
the output.

Two mechanisms answer that, and both are structural rather than instructions
to try harder.

  The marker is given the item, the criteria and the answer, and nothing
  else. No transcript, no learner name, no history, no indication of how the
  lesson went. It cannot be lenient towards someone it does not know about.

  A pass must quote the sentence in the answer that earned it, for every
  criterion that had to be met. A verdict that cannot quote is not a pass.
  This is checkable afterwards, which is what makes it hold: the quotes have
  to actually appear in the submitted answer, and that is verified here
  rather than trusted.

Exit codes: 0 ok, 2 invalid data, 3 refused, 5 not found.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import zt_state as zs  # noqa: E402
from sandbox import Refused  # noqa: E402


# ---------------------------------------------------------------------------
# what the marker is allowed to see
# ---------------------------------------------------------------------------

ALLOWED = ("exercise_id", "prompt", "assets", "answer_key", "tier",
           "expected_minutes", "transfer_dimensions")

WITHHELD = {
    "transcript": "seeing how the lesson went is exactly what produces a "
                  "lenient reading of a borderline answer",
    "learner_id": "a marker that knows whose work this is has someone to be "
                  "kind to",
    "display_name": "a name is enough to know whose work it is, which is enough to want them to do well",
    "history": "knowing they have failed twice already argues for a pass, "
               "and knowing they usually do well argues for one too",
    "mastery": "the current state is the thing this verdict is supposed to "
               "change, so feeding it in makes the verdict circular",
    "persona": "the marker is not Zep and must not sound like Zep; the "
               "learner should be able to tell the two apart",
    "energy": "how tired they are is a reason to stop early, never a reason "
              "to lower the bar",
}


def package(item: dict, rubric: dict, answer: str) -> dict:
    """Build exactly what the marking subagent receives.

    Built by whitelist rather than by removing fields. A blacklist leaks
    whatever nobody thought of, and what leaks here is the teaching context,
    which is the one thing that must not.
    """
    return {
        "item": dict((k, item[k]) for k in ALLOWED if k in item),
        "rubric": rubric,
        "answer": answer,
        "instructions": [
            "You did not see this being taught and do not know who wrote it.",
            "Mark against the criteria only.",
            "For every criterion you mark as met, quote the words in the "
            "answer that meet it. A criterion you cannot quote for is not "
            "met.",
            "If the answer is too incomplete to judge, say that. Do not "
            "reconstruct what they probably meant.",
        ],
    }


def leaks(payload: dict) -> list:
    """Anything in the package that should not be there."""
    text = json.dumps(payload, ensure_ascii=False).lower()
    return sorted(k for k in WITHHELD if '"' + k + '"' in text)


# ---------------------------------------------------------------------------
# what a verdict has to contain
# ---------------------------------------------------------------------------

def _normalise(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def check_verdict(verdict: dict, rubric: dict, answer: str) -> dict:
    """Refuse a verdict that does not support itself.

    The quotes are checked against the answer rather than taken on trust. A
    marker under pressure to pass something can produce a quote that is a
    paraphrase, or a sentence it wishes were there; both read convincingly
    and neither is in the text.
    """
    met = verdict.get("criteria_met") or {}
    haystack = _normalise(answer)

    by_id = dict((c["criterion_id"], c) for c in rubric.get("criteria", []))
    unknown = sorted(set(met) - set(by_id))
    if unknown:
        raise Refused(
            "GRD001",
            "the verdict mentions criteria this rubric does not have: " +
            ", ".join(unknown),
            "mark against the rubric that was supplied, not a remembered one")

    missing_quotes, absent_quotes = [], []
    for cid, entry in met.items():
        if not entry.get("met"):
            continue
        quotes = entry.get("quotes") or []
        if not quotes:
            missing_quotes.append(cid)
            continue
        for q in quotes:
            if _normalise(q) not in haystack:
                absent_quotes.append(cid + ": " + str(q)[:60])

    if missing_quotes:
        raise Refused(
            "GRD002",
            "these criteria are marked met with nothing quoted: " +
            ", ".join(missing_quotes),
            "quote the words that met them. A criterion nothing can be "
            "quoted for was not met, however the answer reads overall")

    if absent_quotes:
        raise Refused(
            "GRD003",
            "these quotes do not appear in the answer: " +
            "; ".join(absent_quotes),
            "quote the answer exactly. A paraphrase is the marker's sentence, "
            "not the learner's, and marking it as evidence credits the "
            "learner with something they did not write")

    required = [c["criterion_id"] for c in rubric.get("criteria", [])
                if c.get("required_for_pass")]
    unmet_required = [c for c in required
                      if not met.get(c, {}).get("met")]

    stated = verdict.get("verdict")
    if stated == "pass" and unmet_required:
        raise Refused(
            "GRD004",
            "marked as a pass while these must-have criteria are unmet: " +
            ", ".join(unmet_required),
            "these are what the item exists to test. Missing one is a fail "
            "whatever else the answer did well")

    return {"ok": True, "verdict": stated,
            "required_unmet": unmet_required,
            "criteria_met": sorted(c for c, e in met.items()
                                   if e.get("met"))}


def score(verdict: dict, rubric: dict) -> dict:
    """Weighted fraction met, and the two conditions a pass needs.

    Both conditions, never either. Without the required-criteria condition, a
    confident answer that misses the point of the item can collect enough
    partial credit to pass.
    """
    crits = rubric.get("criteria", [])
    met = verdict.get("criteria_met") or {}
    total = sum(float(c.get("weight", 1)) for c in crits) or 1.0
    earned = sum(float(c.get("weight", 1)) for c in crits
                 if met.get(c["criterion_id"], {}).get("met"))
    threshold = rubric.get("pass_threshold")
    if threshold is None:
        threshold = 1.0

    required = [c["criterion_id"] for c in crits if c.get("required_for_pass")]
    all_required = all(met.get(c, {}).get("met") for c in required)
    fraction = earned / total

    return {
        "fraction": round(fraction, 3),
        "threshold": threshold,
        "required_all_met": all_required,
        "passes": bool(fraction >= threshold and all_required),
        "why_not": ([] if all_required else
                    ["a must-have criterion is unmet: " + c
                     for c in required if not met.get(c, {}).get("met")]) +
                   ([] if fraction >= threshold else
                    ["met " + str(round(fraction * 100)) + "% of the "
                     "weighted criteria, needs " +
                     str(round(threshold * 100)) + "%"]),
    }


def depth_shown(verdict: dict, rubric: dict) -> int:
    """The deepest criterion actually met, which is what the answer proved.

    Recorded instead of the depth the item was aiming at. An item written for
    depth 4 that the learner passed on its shallower criteria proved depth 3,
    and writing down the intention rather than the demonstration is how a
    concept drifts past its target with nobody noticing.
    """
    met = verdict.get("criteria_met") or {}
    depths = [int(c.get("depth", 0)) for c in rubric.get("criteria", [])
              if met.get(c["criterion_id"], {}).get("met") and c.get("depth")]
    return max(depths) if depths else 0


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def render(result: dict, scored: dict) -> str:
    lines = ["VERDICT  " + ("pass" if scored["passes"] else "fail")]
    lines.append("  met " + str(round(scored["fraction"] * 100)) + "% of "
                 "weighted criteria, needs " +
                 str(round(scored["threshold"] * 100)) + "%")
    for why in scored["why_not"]:
        lines.append("  " + why)
    if result.get("criteria_met"):
        lines.append("  met: " + ", ".join(result["criteria_met"]))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_package(args) -> int:
    item = _load(args.item)
    rubric = _load(args.rubric)
    answer = Path(args.answer).read_text(encoding="utf-8")
    payload = package(item, rubric, answer)
    found = leaks(payload)
    if found:
        print("REFUSED [GRD010] teaching context in the marking package: " +
              ", ".join(found), file=sys.stderr)
        return zs.EXIT_GATE
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return zs.EXIT_OK


def cmd_check(args) -> int:
    verdict = _load(args.verdict)
    rubric = _load(args.rubric)
    answer = Path(args.answer).read_text(encoding="utf-8")
    try:
        result = check_verdict(verdict, rubric, answer)
    except Refused as r:
        print("REFUSED [" + r.code + "]  " + r.message, file=sys.stderr)
        if r.suggestion:
            print("instead: " + r.suggestion, file=sys.stderr)
        return zs.EXIT_GATE
    scored = score(verdict, rubric)
    if args.json:
        print(json.dumps({"checked": result, "score": scored,
                          "depth_demonstrated": depth_shown(verdict, rubric)},
                         ensure_ascii=False, indent=2))
    else:
        print(render(result, scored))
    return zs.EXIT_OK


def cmd_withheld(args) -> int:
    """What the marker never sees, and why. Printed rather than buried so the
    reason survives someone later wondering whether to pass one in."""
    for key, why in WITHHELD.items():
        print(key)
        print("  " + why)
    return zs.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="grade.py",
        description="What the marker sees, and what a verdict must contain.")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("package", help="build the marker's input")
    sp.add_argument("--item", required=True)
    sp.add_argument("--rubric", required=True)
    sp.add_argument("--answer", required=True)
    sp.set_defaults(func=cmd_package)

    sp = sub.add_parser("check", help="does this verdict support itself")
    sp.add_argument("--verdict", required=True)
    sp.add_argument("--rubric", required=True)
    sp.add_argument("--answer", required=True)
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("withheld")
    sp.set_defaults(func=cmd_withheld)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
