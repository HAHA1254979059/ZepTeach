#!/usr/bin/env python3
"""Setting exercises, and refusing the ones that only look like exercises.

Three things here are refusals rather than advice, because each of them is
easy to get wrong in a way that still produces something that reads fine.

  An item with no stated way of marking it cannot be issued. Otherwise the
  marking gets decided after the answer arrives, which is when it is most
  susceptible to how the answer happened to look.

  A mixed set that draws from one lesson, or whose wording says which method
  to use, is not a mixed set. Choosing the method is the thing being
  practised; a set that hands over the choice has removed its own point while
  keeping its appearance. This is the failure mode that makes interleaving
  worth enforcing in code rather than describing in prose.

  A transfer test has to say which way it moved away from where the material
  was learned. "Test it in a new context" is not a specification, cannot be
  checked afterwards, and in practice collapses to changing the surface of
  the question while the structure stays put.

Exit codes: 0 ok, 2 invalid data, 3 refused, 5 not found.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import constants as K  # noqa: E402
import zt_state as zs  # noqa: E402
from sandbox import Refused  # noqa: E402


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# the three tiers
# ---------------------------------------------------------------------------
#
# Difficulty has to come from somewhere outside this system, or it becomes
# this system's opinion of what is hard, which drifts towards what the
# learner can already do.

TIERS = {
    "anchored": {
        "means": "a real problem somebody else set, taken from a source",
        "difficulty_from": "outside this system entirely",
        "needs": ("anchor_kind", "source_ref"),
    },
    "variant": {
        "means": "the anchored item with conditions or parameters changed",
        "difficulty_from": "the anchored item it was derived from",
        "needs": (),
    },
    "modeling": {
        "means": "a real situation the learner has to set up themselves",
        "difficulty_from": "the situation being real rather than tidied",
        "needs": ("rubric_id",),
    },
}


def check_depth(item: dict, depth_targets: dict = None) -> None:
    """Refuse an item that probes deeper than the concept is meant to go.

    Going deeper always feels like thoroughness in the moment, which is why
    this is a refusal rather than a reminder. Unchecked, a course quietly
    becomes twice as long as the learner agreed to, and the extra depth
    arrives at the cost of the concepts that were supposed to come next.

    depth_targets maps concept_id to the target for this course. With none
    supplied nothing is checked, which is the honest behaviour: a caller that
    cannot say how deep a concept is meant to go has not established that the
    item is too deep either.
    """
    depth = item.get("depth")
    if not depth or not depth_targets:
        return
    over = [(cid, depth_targets[cid]) for cid in item.get("concept_ids", [])
            if cid in depth_targets and depth > depth_targets[cid]]
    if over:
        detail = ", ".join(c + " is meant to reach " + str(t)
                           for c, t in over)
        raise Refused(
            "EXE018",
            "this item probes to depth " + str(depth) + " and " + detail,
            "set an item at the target depth. If going deeper is genuinely "
            "worth it, that is a side branch or an explicit raise, and both "
            "are recorded. Depth that creeps upward unrecorded is how a "
            "course doubles in length without anyone deciding to")


def check_issuable(item: dict, depth_targets: dict = None,
                   notation_input=None) -> dict:
    """Everything that must be true before an item may be put in front of
    someone. Raises rather than returning a verdict, so a caller that forgets
    to look at the result still does not issue anything."""
    tier = item.get("tier")
    if tier is None and item.get("form") == "explain_back":
        tier = None                      # the one item with no tier
    elif tier not in TIERS:
        raise Refused("EXE010", "unknown tier: " + str(tier),
                      "one of " + ", ".join(TIERS) + ", or no tier at all "
                      "for an explain-back")

    grader = item.get("grader") or {}
    if not grader.get("type"):
        raise Refused(
            "EXE011",
            "this item says nothing about how it will be marked",
            "decide that now. Deciding after the answer arrives is when it "
            "is most easily talked into being generous")

    if grader.get("type") == "rubric" and not item.get("rubric_id"):
        raise Refused("EXE012", "marking is by rubric but no rubric is named",
                      "name one, or choose a different way of marking")

    if grader.get("type") == "checker" and not grader.get("checker_id"):
        raise Refused(
            "EXE013", "marking is by a checker but none is named",
            "name a checker the course adapter registered")

    for field in (TIERS[tier]["needs"] if tier else ()):
        if not item.get(field):
            raise Refused(
                "EXE014",
                "a " + tier + " item needs " + field + ": " +
                TIERS[tier]["means"],
                "an anchored item whose source cannot be named is an item "
                "this system invented and then called hard")

    check_depth(item, depth_targets)

    if item.get("learner_requested_repeat") and not (
            item.get("repeat_reason") or "").strip():
        raise Refused("EXE031", "a repeated full item has no learner reason",
                      "record what the learner asked for; a tutor's wish "
                      "to retest is not the learner's request")

    if item.get("interleaved"):
        check_mixed(item)

    if item.get("transfer_dimensions"):
        check_transfer(item)

    check_response(item, notation_input)

    return {"ok": True, "exercise_id": item.get("exercise_id"),
            "tier": tier or "none (explain-back)",
            "response_mode": (item.get("response") or {}).get("mode")}


# ---------------------------------------------------------------------------
# how the answer gets supplied
# ---------------------------------------------------------------------------

def check_response(item: dict, notation_input=None) -> None:
    """Refuse an item that has not decided how it will be answered.

    The reason this is a gate and not advice: when it was neither, the shape
    of the answer got decided in the moment. In the first real use that
    produced a good interactive form, and then, about twenty minutes later,
    a silent return to walls of prose, because nothing on disk remembered
    the decision and nothing could refuse an item that ignored it. The
    learner had to notice and complain. That is the same failure as a
    doctrine file claiming an enforcement the code never had.
    """
    resp = item.get("response") or {}
    mode = resp.get("mode")
    if not mode:
        raise Refused(
            "EXE020",
            "this item does not say how it is to be answered",
            "choose a response mode now. Deciding in the moment is how a "
            "whole session drifts back to typing paragraphs without anyone "
            "choosing that")

    if mode == "choice":
        options = resp.get("options") or []
        if len(options) < 2:
            raise Refused(
                "EXE021", "a choice item with fewer than two options",
                "write the wrong answers as things someone could actually "
                "believe. Options nobody would pick make a free pass that "
                "looks like an assessment")
        texts = [str(o.get("text", "")).strip().lower() for o in options]
        if len(set(texts)) != len(texts):
            raise Refused(
                "EXE022", "two options in this choice item say the same thing",
                "duplicate options shrink the real choice without shrinking "
                "the apparent one")

    if mode == "fill_blanks" and not (resp.get("fields") or []):
        raise Refused(
            "EXE023", "fill_blanks, but no slots are named",
            "name the slots. Unnamed slots mean the answer comes back as a "
            "paragraph and cannot be stored as data or compared with the "
            "next attempt")

    for field in resp.get("fields") or []:
        grid = field.get("grid")
        if grid is not None and (not isinstance(grid, dict) or
                any(not isinstance(grid.get(key), int) or grid[key] < 1
                    for key in ("rows", "columns"))):
            raise Refused("EXE025", "an answer grid needs positive rows and columns",
                          "name the shape before issuing the item so the "
                          "learner does not have to invent a text layout")

    if notation_input is None:
        return

    wants_notation = bool(resp.get("expects_notation")) or any(
        f.get("expects_notation") or f.get("grid")
        for f in resp.get("fields") or [])
    if not wants_notation:
        return

    channels = set(notation_input or [])
    if mode in ("free_text", "fill_blanks", "numeric") and not (
            channels & {"types_plain", "types_markup"}):
        raise Refused(
            "EXE024",
            "answering this means writing notation, and this learner did not "
            "say they would type it",
            "they said they can supply notation by: " +
            (", ".join(sorted(channels)) or "no channel at all") + ". Offer "
            "candidates to choose between, or accept a photograph of work "
            "done on paper. Making someone type what is painful to type "
            "measures their patience, not their understanding")


# ---------------------------------------------------------------------------
# mixed practice
# ---------------------------------------------------------------------------

def check_mixed(item: dict) -> None:
    """A mixed item that fails these is single-topic practice wearing a
    label, which is worse than honest single-topic practice: it looks like
    the harder thing was done."""
    concepts = item.get("concept_ids") or []
    if len(concepts) < 2:
        raise Refused(
            "EXE015",
            "marked as mixed but involves one concept",
            "with one concept the question itself says which method applies, "
            "so nothing about choosing gets practised")

    if item.get("reveals_method"):
        raise Refused(
            "EXE016",
            "marked as mixed, but the wording says which method to use",
            "rewrite the prompt so it describes the situation without "
            "naming the technique. Choosing is the thing being practised")

    drawn = item.get("mixed_from") or []
    if drawn and len(set(drawn)) < 2:
        raise Refused(
            "EXE017",
            "marked as mixed but drawn from a single lesson",
            "draw across lessons. Within one lesson the learner already "
            "knows which method is in play, whatever the item says")


def compose_drill(pool: list, taught_recently: list = None,
                  size: int = None) -> dict:
    """Assemble a mixed set out of available items.

    The ordering is the part that matters and the part that is easy to get
    wrong. Grouping by concept and then concatenating produces a set that is
    mixed on paper and blocked in practice, because the learner discovers the
    method once per group and coasts. So consecutive items must differ in
    concept, and the arrangement alternates rather than runs.
    """
    size = size or K.MIXED_SET_SIZE
    usable = [i for i in pool if not i.get("reveals_method")]

    by_concept = {}
    for item in usable:
        for cid in item.get("concept_ids") or []:
            by_concept.setdefault(cid, []).append(item)

    if len(by_concept) < K.MIXED_SET_MIN_CONCEPTS:
        return {
            "items": [],
            "refused": "only " + str(len(by_concept)) + " concept(s) have "
                       "usable items; a mixed set needs at least " +
                       str(K.MIXED_SET_MIN_CONCEPTS),
            "hint": "teach or practise more before mixing; mixing two "
                    "things is barely mixing",
        }

    # round-robin across concepts, which is what stops a run forming
    order, seen = [], set()
    concepts = sorted(by_concept, key=lambda c: -len(by_concept[c]))
    while len(order) < size:
        added = False
        for cid in concepts:
            for item in by_concept[cid]:
                eid = item.get("exercise_id")
                if eid in seen:
                    continue
                if order and cid in (order[-1].get("concept_ids") or []):
                    continue
                order.append(item)
                seen.add(eid)
                added = True
                break
            if len(order) >= size:
                break
        if not added:
            break

    return {
        "items": order,
        "concepts_covered": sorted({c for i in order
                                    for c in (i.get("concept_ids") or [])}),
        "note": "expect this to feel worse than practising one thing at a "
                "time, and to score better on a delayed test. Say so before "
                "starting, so the drop is not read as going backwards",
    }


def is_really_mixed(items: list) -> dict:
    """Check an assembled set rather than an individual item.

    A set can pass item-by-item and still be blocked overall, which is the
    likeliest way this goes wrong once composition is automatic.
    """
    problems = []
    concepts = [tuple(sorted(i.get("concept_ids") or [])) for i in items]

    distinct = {c for group in concepts for c in group}
    if len(distinct) < K.MIXED_SET_MIN_CONCEPTS:
        problems.append("the whole set covers " + str(len(distinct)) +
                        " concept(s)")

    runs = [1]
    for a, b in zip(concepts, concepts[1:]):
        runs.append(runs[-1] + 1 if a == b else 1)
    if max(runs, default=0) > 1:
        problems.append("consecutive items share the same concept, so the "
                        "learner stops choosing after the first one")

    if any(i.get("reveals_method") for i in items):
        problems.append("an item names the method it wants")

    return {"mixed": not problems, "problems": problems}


def check_retry_after_slip(item: dict, attempts: list) -> None:
    """A small execution error must not start another full same-session test.

    A learner may explicitly ask to practise it again. Otherwise the useful
    next move is one targeted correction if it matters, or moving on. Only
    the most recent attempt on the affected concept is relevant.
    """
    session = item.get("session_id")
    concepts = set(item.get("concept_ids") or [])
    if not session or not concepts:
        return
    for attempt in reversed(attempts):
        if attempt.get("session_id") != session:
            continue
        shared = concepts & set(attempt.get("concept_ids") or [])
        if not shared:
            continue
        parts = attempt.get("concept_results") or []
        slipped = ({r.get("concept_id") for r in parts
                    if r.get("execution_only")} if parts else
                   set(attempt.get("concept_ids") or [])
                   if attempt.get("execution_only") else set())
        if concepts <= slipped:
            if item.get("learner_requested_repeat") and \
                    (item.get("repeat_reason") or "").strip():
                return
            raise Refused(
                "EXE030",
                "the last answer already showed the idea; only its "
                "execution slipped, and this is another full item on the "
                "same concept in the same session",
                "name the local step and offer one correction only if it "
                "matters for the goal, or move to the next concept. A full "
                "repeat needs the learner's explicit request and reason")
        return


# ---------------------------------------------------------------------------
# transfer
# ---------------------------------------------------------------------------

def check_transfer(item: dict) -> None:
    dims = item.get("transfer_dimensions") or []
    if not dims:
        raise Refused(
            "EXE020",
            "used as a transfer test but does not say what it moved",
            "name at least one of Barnett and Ceci's six context "
            "dimensions. 'A new context' cannot be checked and in practice "
            "means the surface changed while the structure did not")


def transfer_strength(item: dict) -> dict:
    """How far this item actually moves, and whether that is enough.

    Named separately from the refusal because this is a judgement, not a
    rule: an item can satisfy the letter and still be weak, and saying so is
    more useful than refusing it.
    """
    dims = list(item.get("transfer_dimensions") or [])
    out = {"dimensions": dims, "count": len(dims)}

    if dims == ["knowledge_domain"]:
        out["weak"] = True
        out["why"] = ("moving only along knowledge domain is the criterion "
                      "this replaced: an open-ended item, or one spanning "
                      "two concepts, already does that. On its own it leaves "
                      "the setting, the form and the stakes unchanged")
    elif not dims:
        out["weak"] = True
        out["why"] = "nothing named"
    else:
        out["weak"] = False

    if "functional_context" in dims:
        out["note"] = ("moving into a real situation is the dimension the "
                       "open-ended tier exists for, and the one that most "
                       "often fails: real situations do not arrive tidied")
    return out


# ---------------------------------------------------------------------------
# the lesson is not finished until they have said it back
# ---------------------------------------------------------------------------

def explain_back_item(concept_id: str, course_id: str = "") -> dict:
    """The one item every lesson owes.

    Conventional id on purpose: reusing the same explain-back later as if it
    were a delayed retest is caught by the duplicate check rather than
    passing unnoticed.
    """
    return {
        "schema_version": 1,
        "exercise_id": "explain-back:" + concept_id,
        "course_id": course_id,
        "concept_ids": [concept_id],
        "form": "explain_back",
        "prompt": "Say it back without looking: what is it, why is it "
                  "needed, and where does it stop working?",
        "grader": {"type": "rubric"},
        "rubric_id": "explain-back",
        # Said back unaided is the whole point, so there is nothing to choose
        # between and nothing to fill in. This is the one item whose response
        # mode is not a decision.
        "response": {"mode": "free_text",
                     "why": "saying it back in their own words is the "
                            "evidence; supplying the words would remove it"},
        "created": _now(),
    }


def owed_explain_backs(taught: list, attempts: list) -> list:
    """Concepts taught in this session that nobody has said back yet."""
    done = {a.get("exercise_id") for a in attempts
            if a.get("form") == "explain_back"}
    return [c for c in taught if "explain-back:" + c not in done]


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def render_drill(drill: dict) -> str:
    if drill.get("refused"):
        return "NOT MIXED: " + drill["refused"] + "\n  " + drill["hint"]
    lines = ["MIXED SET (" + str(len(drill["items"])) + " items across " +
             str(len(drill["concepts_covered"])) + " concepts)"]
    for i, item in enumerate(drill["items"], 1):
        lines.append("  " + str(i) + ". " + str(item.get("exercise_id")) +
                     "  [" + str(item.get("tier")) + "]")
    lines.append("")
    lines.append("SAY FIRST: " + drill["note"])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def _report(fn, args) -> int:
    try:
        out = fn()
    except Refused as r:
        if args.json:
            print(json.dumps(r.as_dict(), ensure_ascii=False, indent=2))
        else:
            print("REFUSED [" + r.code + "]  " + r.message, file=sys.stderr)
            if r.suggestion:
                print("instead: " + r.suggestion, file=sys.stderr)
        return zs.EXIT_GATE
    print(json.dumps(out, ensure_ascii=False, indent=2) if args.json
          else "ok")
    return zs.EXIT_OK


def cmd_check(args) -> int:
    item = json.loads(Path(args.file).read_text(encoding="utf-8")
                      if args.file else args.data)
    errs = zs.validate_doc(item, "exercise")
    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        return zs.EXIT_VALIDATION
    return _report(lambda: check_issuable(item), args)


def cmd_drill(args) -> int:
    pool = json.loads(Path(args.pool).read_text(encoding="utf-8"))
    drill = compose_drill(pool, size=args.size)
    if args.json:
        print(json.dumps(drill, ensure_ascii=False, indent=2))
    else:
        print(render_drill(drill))
    return zs.EXIT_GATE if drill.get("refused") else zs.EXIT_OK


def cmd_transfer(args) -> int:
    item = json.loads(args.data)
    out = transfer_strength(item)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return zs.EXIT_OK
    print("moves along: " + (", ".join(out["dimensions"]) or "nothing"))
    if out["weak"]:
        print("WEAK: " + out["why"])
    if out.get("note"):
        print("note: " + out["note"])
    return zs.EXIT_OK


def cmd_tiers(args) -> int:
    for name, spec in TIERS.items():
        print(name)
        print("  " + spec["means"])
        print("  difficulty comes from: " + spec["difficulty_from"])
        if spec["needs"]:
            print("  must carry: " + ", ".join(spec["needs"]))
    return zs.EXIT_OK


def cmd_issue(args) -> int:
    """Check an item and keep it.

    Items used to exist only in the conversation. That is why nothing could
    later ask what a learner had actually been shown: an explanation could
    not be checked against the questions it was supposedly separate from, a
    verdict pointed at an exercise_id nobody could look up, and a retest
    could not reuse an item because the item was gone.
    """
    root = zs.default_root() if not args.root else Path(args.root)
    item = json.loads(Path(args.file).read_text(encoding="utf-8"))

    errors = zs.validate_doc(item, "exercise")
    if errors:
        for e in errors:
            print("invalid item: " + str(e), file=sys.stderr)
        return zs.EXIT_VALIDATION

    cdir = root / "courses" / args.course
    if not cdir.exists():
        print("no such course: " + args.course, file=sys.stderr)
        return zs.EXIT_NOT_FOUND

    profile_path = root / "learner" / "profile.json"
    notation = None
    if profile_path.exists():
        notation = zs.read_json(profile_path).get("notation_input")

    try:
        result = check_issuable(item, notation_input=notation)
        check_retry_after_slip(item, zs.read_jsonl(cdir / "attempts.jsonl"))
    except Refused as r:
        print("REFUSED [" + r.code + "]  " + r.message, file=sys.stderr)
        if r.suggestion:
            print("instead: " + r.suggestion, file=sys.stderr)
        return zs.EXIT_GATE

    item.setdefault("created", _now())
    zs.append_jsonl(cdir / "exercises.jsonl", item)
    print("issued " + str(item.get("exercise_id")) + "  answered by " +
          str(result["response_mode"]))
    return zs.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="exercise.py",
        description="Setting exercises, and refusing ones that only look "
                    "like exercises.")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("check", help="may this item be issued")
    sp.add_argument("--data")
    sp.add_argument("--file")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("issue", help="check an item and write it down")
    sp.add_argument("--course", required=True)
    sp.add_argument("--file", required=True)
    sp.add_argument("--root")
    sp.set_defaults(func=cmd_issue)

    sp = sub.add_parser("drill", help="assemble a mixed set")
    sp.add_argument("--pool", required=True)
    sp.add_argument("--size", type=int)
    sp.set_defaults(func=cmd_drill)

    sp = sub.add_parser("transfer", help="how far does this item move")
    sp.add_argument("--data", required=True)
    sp.set_defaults(func=cmd_transfer)

    sp = sub.add_parser("tiers")
    sp.set_defaults(func=cmd_tiers)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
