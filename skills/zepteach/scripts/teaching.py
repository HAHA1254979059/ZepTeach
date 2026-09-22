#!/usr/bin/env python3
"""What an explanation has to contain before it counts as having happened.

This file is the mirror image of grade.py, and it exists because that mirror
was missing.

grade.py refuses a pass that cannot quote the learner's answer. The whole
plugin is built out of checks with that shape, and every one of them points
the same way: at what the learner produced. Nothing pointed at what the
teacher produced. Marking a concept as taught was one command with three
string arguments and no content, so "I taught this" was an assertion, and an
assertion costs nothing.

The first real use showed what that asymmetry does. Over three lessons the
teacher issued twenty-five assessment items and wrote almost nothing else;
the few sentences it did write were mostly "the form is above, fill it in".
The learner eventually wrote: you never taught this, I only knew how to
calculate it, and you read my arithmetic slips as not having learned it. Every
gate was green the entire time, because the only half that was measured was
the half that was still happening.

So the rule here is the same rule, turned around. An explanation must quote
itself. What was said has to exist on disk, outside the question it was
supposedly delivered in, before any non-probe attempt on that concept can be
recorded.

An untaught concept may still be probed. Letting someone try something
untaught, watching it fail, and explaining into the gap that opens is a
deliberate and usually better order for a conceptual target. What it must
never turn into is a reason the explanation never arrives, which is exactly
what happened.

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
# reading an exposition
# ---------------------------------------------------------------------------

RUNG_NAMES = {
    1: "phenomenon - what is observed, what breaks without this",
    2: "intuitive picture - the shape of it before any symbols",
    3: "minimal model - the smallest case that still has the essential "
       "feature",
    4: "formal statement - the real definition or derivation",
    5: "boundary - where it fails, what it is confused with",
}

# Where each register is expected to start on the ladder. Below this is not
# an error - skipping upward is usually right and a learner who asks for the
# intuition should get it - but starting BELOW the register's rung means the
# register is wrong rather than the explanation, and that is worth saying out
# loud rather than quietly re-teaching at a level nobody chose.
REGISTER_START = {
    "terse_technical": 3,
    "technical_with_gloss": 2,
    "analogy_first": 1,
}


def _normalise(s: str) -> str:
    """Same normalisation grade.py uses on quotes, for the same reason: the
    comparison has to survive reformatting without becoming so loose that
    anything matches."""
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def delivered_text(expo: dict) -> str:
    """Everything the learner was actually shown, as one string."""
    return "\n".join(r.get("said", "") for r in expo.get("rungs", []) or [])


def check_exposition(expo: dict, item_prompts=None,
                     require_operational_definition: bool = True) -> dict:
    """Refuse an explanation that does not support itself.

    item_prompts is what the learner was asked on this concept. It is the
    load-bearing argument. The failure this catches is not laziness, it is
    something that reads perfectly well: a definition gets folded into the
    stem of a question - "the prior is your belief before the evidence; so
    which quantity is the prior here?" - and that feels like teaching while
    being entirely assessment. The learner has to work the definition out of
    the question they are being marked on. So an explanation whose every rung
    already appears inside the questions is not an explanation.
    """
    concept = expo.get("concept_id") or "?"

    rungs = expo.get("rungs") or []
    if not rungs:
        raise Refused(
            "EXP001", "nothing was recorded as said for " + concept,
            "put what the learner was shown in rungs[].said, in the words "
            "they saw it in")

    if not (expo.get("boundary") or "").strip():
        raise Refused(
            "EXP002", "no boundary recorded for " + concept,
            "say where this fails and what it is confused with. A concept "
            "handed over without that gets misapplied, and the transfer test "
            "finds out later at much higher cost")

    for a in expo.get("analogies") or []:
        if not (a.get("mapping") or "").strip() or \
           not (a.get("stops_where") or "").strip():
            raise Refused(
                "EXP003",
                "an analogy for " + concept + " is not cashed out and "
                "bounded",
                "say what stands for what, and where it stops being true. An "
                "uncashed analogy produces the feeling of understanding "
                "without the thing, which is the illusion this system exists "
                "to resist")

    if require_operational_definition:
        for t in expo.get("terms") or []:
            if not (t.get("operational_definition") or "").strip():
                raise Refused(
                    "EXP004",
                    "the term " + str(t.get("term")) + " was introduced with "
                    "no definition the learner can act on",
                    "answer how they would compute or check it, in one line. "
                    "A dictionary gloss is not that")

    prompts = [_normalise(p) for p in (item_prompts or []) if p]
    if prompts:
        outside = []
        for r in rungs:
            said = _normalise(r.get("said", ""))
            if not said:
                continue
            if not any(said in p for p in prompts):
                outside.append(r.get("rung"))
        if not outside:
            raise Refused(
                "EXP005",
                "everything recorded as explaining " + concept + " also "
                "appears inside the questions asked about it",
                "say it somewhere the learner is not simultaneously being "
                "marked. A definition folded into the stem of a question "
                "reads like teaching and is assessment")

    reached = sorted(set(int(r.get("rung", 0)) for r in rungs))
    if expo.get("register") == "analogy_first" and not (
            1 in reached or 2 in reached):
        raise Refused(
            "EXP006",
            "this explanation is marked intuition-first but contains no "
            "phenomenon or intuitive picture",
            "show what the idea is for or what it looks like before the "
            "formal statement. A named register must change the teaching")
    start = REGISTER_START.get(expo.get("register"))
    below = [r for r in reached if start and r < start]

    return {
        "ok": True,
        "concept_id": concept,
        "rungs_covered": reached,
        "terms_defined": [t.get("term") for t in expo.get("terms") or []],
        "started_below_register": below,
        "note": ("" if not below else
                 "this explanation started at rung " + str(min(below)) +
                 " for a " + str(expo.get("register")) + " register, which "
                 "expects rung " + str(start) + ". That is allowed, but it "
                 "usually means the register is wrong rather than the "
                 "explanation. Say so and change the register rather than "
                 "quietly teaching lower than anybody chose"),
    }


# ---------------------------------------------------------------------------
# the gate the rest of the system asks
# ---------------------------------------------------------------------------

def expositions_for(rows, concept_id: str):
    """Every recorded explanation of one concept, oldest first."""
    out = [r for r in rows if r.get("concept_id") == concept_id]
    return sorted(out, key=lambda r: r.get("delivered_at") or "")


def taught_before(rows, concept_id: str, when: str):
    """The explanation this attempt could have been answered from, if any.

    Ordering matters and is not a formality. An explanation recorded after
    the answer was given did not help the person who gave it, and counting it
    would let the whole check be satisfied in arrears - explain everything at
    the end of the session, and every attempt in it retroactively becomes
    taught.
    """
    for r in reversed(expositions_for(rows, concept_id)):
        if not when or (r.get("delivered_at") or "") <= when:
            return r
    return None


def untaught_in(rows, concept_ids, when: str, kind: str, exempt=None):
    """Which of these concepts has no explanation on file from before `when`.

    A probe is exempt: being asked something untaught is the point of a
    probe, and refusing it would remove the one move that opens a gap worth
    explaining into.

    `exempt` holds concepts taught before this rule existed, from
    migrate.py. They are exempt by name and by date, listed in a file and
    reported on, rather than being given a fabricated explanation to satisfy
    the check. A rule that arrives after the records cannot be applied to
    them honestly, and the honest thing is to say which ones and why.
    """
    if kind == "probe":
        return []
    exempt = set(exempt or ())
    return [c for c in concept_ids
            if c not in exempt and taught_before(rows, c, when) is None]


def never_explained(rows, mastery_rows):
    """Concepts the records say were taught, with nothing recorded as said.

    For roots written before expositions existed, and as an audit afterwards.
    The state machine's `introduced` used to be set by a command that took no
    content, so a root can hold any number of concepts that are marked taught
    and have no explanation behind them.
    """
    have = set(r.get("concept_id") for r in rows)
    out = []
    for m in mastery_rows:
        if m.get("state", "unseen") == "unseen":
            continue
        if m.get("concept_id") not in have:
            out.append({"concept_id": m.get("concept_id"),
                        "state": m.get("state"),
                        "first_taught": m.get("first_taught")})
    return sorted(out, key=lambda r: r["concept_id"])


def thin(rows, item_prompts_by_concept=None):
    """Explanations that would be refused if they were submitted today.

    The point of running this over a whole course is that a rule added later
    is worth nothing against records written earlier, and the honest way to
    find that out is to re-run the check rather than assume.
    """
    out = []
    by_concept = item_prompts_by_concept or {}
    for r in rows:
        try:
            check_exposition(r, by_concept.get(r.get("concept_id")))
        except Refused as ref:
            out.append({"exposition_id": r.get("exposition_id"),
                        "concept_id": r.get("concept_id"),
                        "code": ref.code, "why": ref.message})
    return out


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_ladder(args) -> int:
    """The ladder and where each register joins it. Printed rather than left
    in a doctrine file, so it is available at the moment of writing one."""
    for n in sorted(RUNG_NAMES):
        print(str(n) + "  " + RUNG_NAMES[n])
    print()
    print("where to start, by register:")
    for reg, rung in REGISTER_START.items():
        print("  " + reg.ljust(22) + "rung " + str(rung))
    print()
    print("Rung 5 is required in every register and is its own field.")
    print("Skipping upward is fine. Starting below the register's rung is")
    print("allowed but means the register is probably wrong.")
    return zs.EXIT_OK


def cmd_check(args) -> int:
    expo = _load(args.exposition)
    errors = zs.validate_doc(expo, "exposition")
    if errors:
        for e in errors:
            print("invalid exposition: " + str(e), file=sys.stderr)
        return zs.EXIT_VALIDATION

    prompts = []
    for p in args.item or []:
        doc = _load(p)
        if doc.get("prompt"):
            prompts.append(doc["prompt"])

    try:
        result = check_exposition(
            expo, prompts,
            require_operational_definition=not args.no_definitions_required)
    except Refused as r:
        print("REFUSED [" + r.code + "]  " + r.message, file=sys.stderr)
        if r.suggestion:
            print("instead: " + r.suggestion, file=sys.stderr)
        return zs.EXIT_GATE

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("exposition ok: " + result["concept_id"] +
              "  rungs " + ", ".join(str(r) for r in result["rungs_covered"]))
        if result["terms_defined"]:
            print("  defined: " + ", ".join(result["terms_defined"]))
        if result["note"]:
            print("  note: " + result["note"])
    return zs.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="teaching.py",
        description="What an explanation must contain to count as delivered.")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("ladder", help="the explanation ladder")
    sp.set_defaults(func=cmd_ladder)

    sp = sub.add_parser("check", help="does this explanation support itself")
    sp.add_argument("--exposition", required=True)
    sp.add_argument("--item", action="append",
                    help="an item asked on this concept; repeatable. Supply "
                         "them: the check that an explanation exists outside "
                         "the questions cannot run without them")
    sp.add_argument("--no-definitions-required", action="store_true",
                    help="for a register that does not gloss terms")
    sp.set_defaults(func=cmd_check)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print("not found: " + str(exc), file=sys.stderr)
        return zs.EXIT_NOT_FOUND


if __name__ == "__main__":
    sys.exit(main())
