#!/usr/bin/env python3
"""The opening interview: what has to be settled before any teaching starts.

Two things shape this script, and they pull in opposite directions.

The first is that some settings cannot be guessed and must not be defaulted.
Which language to teach in is the clearest: picking one on the learner's
behalf is a decision about their whole experience, made silently.

The second is that most of what a tutor wants to know is better measured than
asked. Self-rated knowledge gain correlates at about zero with gain measured
by testing, and self-reported level runs consistently high. What learners do
report accurately is WHICH courses, books and projects they went through. So
this asks what they have encountered, never how well they know it, and leaves
level to be established by asking them questions about the material.

The result is a short interview. Anything that the first ten minutes of the
first lesson would establish more reliably is not asked here.

What is deliberately NOT asked at this stage: what equipment or material they
have. That depends on what they decide to study, which has not happened yet.
It belongs to the second stage, in practice_reach.py.

Exit codes: 0 ok, 2 the answers do not form a valid profile or config.
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


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# what gets asked
# ---------------------------------------------------------------------------
#
# Each entry says what to ask, why it cannot be settled any other way, and
# where the answer is stored. "never" records a question that would be natural
# to ask here and should not be, with the reason - that field exists because
# the interview grows by accretion otherwise, and a long interview before any
# teaching is its own failure.

QUESTIONS = [
    {
        "id": "teaching_language",
        "ask": "Which language should the teaching be in?",
        "why": "It cannot be inferred and must never be chosen for them. A "
               "default here silently decides how every explanation reads.",
        "stores": "config.teaching_language",
        "group": "start",
        "blocks": "anything at all: it decides the first sentence",
        "required": True,
    },
    {
        "id": "notes",
        "ask": "Your notes are going in the notes folder under your data "
               "root - one plain-text copy I read back later, one document "
               "copy for you. Say the word if you want them somewhere you "
               "already open instead.",
        "why": "Notes are the durable half of this, and the two readers "
               "genuinely want different things. Writing them somewhere the "
               "learner does not already open wastes them - which is why "
               "this is said out loud rather than defaulted in silence. It "
               "is not a blocking question: a default that is stated can be "
               "corrected in one sentence, and a course does not have to "
               "wait for it.",
        "stores": "config.notes",
        "group": "notes",
        "blocks": "nothing, but say where they are going the first time "
                  "notes are written",
        "required": False,
    },
    {
        "id": "purpose",
        "ask": "What are you studying this for?",
        "why": "This is the only question here whose answer cannot be "
               "measured later. Everything else about the learner can be "
               "established by watching them work; why they are here cannot. "
               "It also settles how deep is deep enough, which otherwise "
               "gets renegotiated in every lesson.",
        "stores": "profile.purpose",
        "group": "course",
        "blocks": "creating a course",
        "required": True,
    },
    {
        "id": "depth_expectation",
        "ask": "By default, how far do you want to take a topic? Being able "
               "to use it, compute with it, derive it, judge work that uses "
               "it, or build something new with it?",
        "why": "A depth target is a budget for how many connections to "
               "build. Without one stated, lessons drift deeper than "
               "intended because going deeper always feels productive.",
        "stores": "profile.depth_expectation",
        "group": "course",
        "blocks": "creating a course",
        "required": True,
    },
    {
        "id": "background",
        "ask": "Which courses, books or projects have you already been "
               "through in this area?",
        "why": "Learners remember what they studied accurately. This gives "
               "the starting point for probing.",
        "stores": "profile.background",
        "group": "course",
        "blocks": "creating a course",
        "required": False,
        "never": "Do not ask how well they know it, or to rate themselves "
                 "out of five. Self-rated level correlates at about zero "
                 "with measured level and runs consistently high, so the "
                 "answer would be worse than no answer: it would look like "
                 "information and be used as if it were.",
    },
    {
        "id": "pacing",
        "ask": "Roughly how many minutes a week, and how long is a "
               "comfortable single sitting?",
        "why": "Progress is measured against this. Without it there is no "
               "way to say whether a course is on schedule, and no honest "
               "way to plan one.",
        "stores": "profile.pacing",
        "group": "course",
        "blocks": "creating a course",
        "required": True,
        "note": "A starting figure is enough. The session log replaces it "
                "with what they actually complete.",
    },
    {
        "id": "source_languages",
        "ask": "Which languages can you read source material in?",
        "why": "Different from the teaching language, and it decides which "
               "material can be used at all.",
        "stores": "profile.source_languages",
        "group": "never",
        "blocks": "nothing",
        "required": False,
    },
    {
        "id": "notation_input",
        "ask": "When an answer needs something awkward to type - a formula, "
               "a structure, a diagram, a table - how do you want to give "
               "it? Typing it out, writing it in a markup language, "
               "photographing it off paper, or picking between candidates "
               "I offer. More than one is fine.",
        "why": "Because the alternative is finding out in the middle of a "
               "lesson. This learner told us mid-lesson that typing "
               "formulas was painful and that the item could have been "
               "multiple choice, which was true and arrived too late. It is "
               "asked as a channel rather than as a free-text preference so "
               "that an item can actually be refused for ignoring it: "
               "`formulas must be LaTeX` written as prose reads clearly and "
               "gates nothing.",
        "say": "This changes how they answer, never what counts as "
               "answering. A question that is easier to submit is not an "
               "easier question.",
        "stores": "profile.notation_input",
        "group": "item",
        "blocks": "issuing an item whose answer needs notation",
        "required": False,
    },
    {
        "id": "constraints",
        "ask": "Anything else that should always hold? No video, a "
               "particular convention, anything like that.",
        "why": "Standing preferences are cheap to record once and annoying "
               "to restate every session. Note that anything here is prose "
               "and cannot be enforced - if a preference needs to be "
               "honoured rather than remembered, it needs a field of its "
               "own, the way the notation channel does.",
        "stores": "profile.constraints",
        "group": "never",
        "blocks": "nothing",
        "required": False,
    },
]

# Questions that belong to a later stage, kept here so that the reason is
# written down where someone would look for it.
DEFERRED = [
    {
        "id": "current_level",
        "instead": "Establish it by asking them about the material in the "
                   "first lesson. A stated level is a hypothesis about where "
                   "to start, never a reason to skip the check.",
    },
    {
        "id": "equipment_and_material",
        "instead": "This depends on what they decide to study, which has not "
                   "been settled yet. It belongs to the second stage, after "
                   "the course goal exists: practice_reach.py.",
    },
    {
        "id": "study_goal",
        "instead": "A goal belongs to a course, not to a person. It is "
                   "written when the course is created, as a capability "
                   "rather than a list of topics, with near-term milestones.",
    },
]


# ---------------------------------------------------------------------------
# what is already known
# ---------------------------------------------------------------------------

def known(root: Path) -> dict:
    """What can be read rather than asked.

    Asking someone something they already told you is the fastest way to make
    a system feel like it has no memory, which is one of the complaints this
    project exists to answer. So the interview starts by reading.
    """
    out = {"answered": {}, "root": str(root), "root_exists": root.exists()}

    cfg_path = root / "config.json"
    if cfg_path.exists():
        cfg = zs.read_json(cfg_path)
        if cfg.get("teaching_language"):
            out["answered"]["teaching_language"] = cfg["teaching_language"]
        if cfg.get("persona", {}).get("name"):
            out["answered"]["address"] = cfg["persona"]
        if cfg.get("notes", {}).get("markdown_dir"):
            out["answered"]["notes"] = cfg["notes"]
        out["stage1_done"] = bool(cfg.get("setup", {})
                                  .get("stage1_completed_at"))

    prof_path = root / "learner" / "profile.json"
    if prof_path.exists():
        prof = zs.read_json(prof_path)
        for key, field in (("purpose", "purpose"),
                           ("depth_expectation", "depth_expectation"),
                           ("background", "background"),
                           ("pacing", "pacing"),
                           ("source_languages", "source_languages"),
                           ("notation_input", "notation_input"),
                           ("constraints", "constraints")):
            if prof.get(field):
                out["answered"][key] = prof[field]

    return out


# When each group has to be answered by. Asking everything at once was the
# first thing the first real learner complained about, and the complaint was
# precise: too much in one message, and it should be split into groups asked
# when each group matters.
#
# It is worse than tiring. Two of the questions asked up front were ones the
# learner had no way to answer yet - what to include in a course about a
# field they had not started - and being asked them produced an answer that
# looked like a decision and was a guess.
GROUPS = {
    "start": "before the first word: it decides what language everything is "
             "in",
    "course": "before designing a course, because they set what it is for "
              "and how far it goes",
    "notes": "before the first notes are written, which is the end of a "
             "session rather than the start",
    "item": "before setting an item whose answer needs notation",
    "never": "not proactively. Recorded if the learner brings it up",
}


def remaining(root: Path) -> list:
    """The questions still worth asking, in order."""
    have = known(root)["answered"]
    return [q for q in QUESTIONS if q["id"] not in have]


def blocking(root: Path, action: str) -> list:
    """Only the questions standing between here and `action`.

    This is the whole of the fix for a nine-question opening interview. The
    interview was not too long because the questions were bad; it was too
    long because it was all asked at the same moment, most of it about
    decisions that had not come up yet.
    """
    if action not in GROUPS:
        raise KeyError("no such group: " + action + " (have: " +
                       ", ".join(GROUPS) + ")")
    return [q for q in remaining(root) if q.get("group") == action]


def still_needed(root: Path) -> dict:
    """Every group, and what is still outstanding in it."""
    have = known(root)["answered"]
    out = {}
    for name in GROUPS:
        out[name] = [q["id"] for q in QUESTIONS
                     if q.get("group") == name and q["id"] not in have]
    return out


# ---------------------------------------------------------------------------
# turning answers into stored state
# ---------------------------------------------------------------------------

def build(answers: dict, learner_id: str = "learner") -> tuple:
    """Produce the two documents the interview writes.

    Nothing is invented here. A missing answer produces a missing field and
    then a validation error, rather than a plausible value that nobody chose.
    The one exception is the set of pacing and session numbers, which have
    recorded starting values that the learner's own logs later replace; those
    are marked in constants.py as starting values rather than findings.
    """
    persona = dict(answers.get("address") or {})
    persona.setdefault("name", "Zep")

    config = {
        "schema_version": 1,
        "learner_id": learner_id,
        "updated": _now(),
        "setup": {"stage1_completed_at": _now(), "stage1_version": 1},
        "persona": persona,
        "agent_models": answers.get("agent_models") or {
            "sidequest_tutor": "sonnet",
            "grader": "opus",
            "curriculum_architect": "opus",
        },
        "defaults": {
            "turn_budget": K.TURN_BUDGET,
            "checkpoint_at": K.CHECKPOINT_AT,
            "hard_stop_at": K.HARD_STOP_AT,
            "session_minutes": (answers.get("pacing") or {}).get(
                "preferred_session_minutes", K.SESSION_MINUTES),
            "delayed_retest_min_days": K.DELAYED_RETEST_MIN_DAYS,
            "transfer_test_min_days": K.TRANSFER_TEST_MIN_DAYS,
            "review_cap_per_session": K.DEFAULT_REVIEW_CAP,
            "retire_after_instant": K.RETIRE_AFTER_INSTANT,
        },
    }
    if answers.get("teaching_language"):
        config["teaching_language"] = answers["teaching_language"]
    # Notes default to a folder inside the data root, and the learner is
    # told where rather than asked where. The question used to be required
    # before anything could start, which put a decision about the end of a
    # session in front of the first word of the first lesson. Proposing a
    # place and offering to move it costs one sentence and no waiting; the
    # doctrine that notes must not land somewhere nobody opens is satisfied
    # by saying where they landed, not by demanding a path up front.
    config["notes"] = answers.get("notes") or {"markdown_dir": "notes"}

    profile = {
        "schema_version": 1,
        "learner_id": learner_id,
        "created": _now(),
        "updated": _now(),
        "registers": answers.get("registers") or [
            {"domain": "*", "register": "technical_with_gloss",
             "max_analogies_per_concept": 1,
             "require_operational_definition": True},
        ],
        "pacing": answers.get("pacing") or {},
    }
    if answers.get("display_name"):
        profile["display_name"] = answers["display_name"]
    if answers.get("purpose"):
        profile["purpose"] = dict(answers["purpose"], updated=_now())
    if answers.get("depth_expectation"):
        profile["depth_expectation"] = answers["depth_expectation"]
    if answers.get("background"):
        profile["background"] = [_as_background(b)
                                 for b in answers["background"]]
    for key in ("source_languages", "notation_input", "constraints"):
        if answers.get(key):
            profile[key] = answers[key]

    return config, profile


def _as_background(row):
    """A background entry always records how the level was established.

    Anything the learner said about themselves is self_declared, whatever
    they sounded like when they said it. Upgrading that to probe_verified
    later requires evidence, and this is where the distinction starts.
    """
    row = dict(row)
    row.setdefault("basis", "self_declared")
    row.setdefault("updated", _now())
    return row


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def render_known(state: dict) -> str:
    lines = ["ALREADY KNOWN - do not ask these again"]
    if not state["answered"]:
        lines.append("  nothing; this is a first setup")
    for key, val in sorted(state["answered"].items()):
        shown = json.dumps(val, ensure_ascii=False)
        if len(shown) > 70:            # layout, not a tunable
            shown = shown[:67] + "..."
        lines.append("  " + key.ljust(20) + shown)
    if state.get("stage1_done"):
        lines.append("")
        lines.append("Stage 1 has already run. Ask only about what changed.")
    return "\n".join(lines)


def render_questions(qs: list) -> str:
    lines = []
    for i, q in enumerate(qs, 1):
        mark = "" if q["required"] else "   (optional)"
        lines.append(str(i) + ". " + q["ask"] + mark)
        lines.append("   why: " + q["why"])
        if q.get("note"):
            lines.append("   say: " + q["note"])
        if q.get("never"):
            lines.append("   DO NOT: " + q["never"])
        lines.append("")
    lines.append("NOT ASKED HERE")
    for d in DEFERRED:
        lines.append("  " + d["id"] + " - " + d["instead"])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def cmd_known(args) -> int:
    root = Path(args.root) if args.root else zs.default_root()
    state = known(root)
    print(json.dumps(state, ensure_ascii=False, indent=2) if args.json
          else render_known(state))
    return zs.EXIT_OK


def cmd_questions(args) -> int:
    root = Path(args.root) if args.root else zs.default_root()
    qs = QUESTIONS if args.all else remaining(root)
    if args.json:
        print(json.dumps(qs, ensure_ascii=False, indent=2))
        return zs.EXIT_OK
    if not qs:
        print("nothing left to ask; stage 1 is complete")
        return zs.EXIT_OK
    print(render_questions(qs))
    return zs.EXIT_OK


def cmd_next(args) -> int:
    """Only the questions standing between here and the next thing.

    The opening interview used to put all nine in one message. The first
    real learner said so immediately: too much at once, split it into groups
    and ask each group when it matters. Two of the nine were also questions
    they had no way to answer yet, and asking anyway produced a guess that
    then looked like a decision.

    Asked this way, the interview before the first lesson is one question.
    """
    root = Path(args.root) if args.root else zs.default_root()
    try:
        qs = blocking(root, args.group)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return zs.EXIT_NOT_FOUND

    if args.json:
        print(json.dumps({"group": args.group, "when": GROUPS[args.group],
                          "questions": qs}, ensure_ascii=False, indent=2))
        return zs.EXIT_OK

    if not qs:
        print("nothing blocking " + args.group)
        return zs.EXIT_OK

    print("ASK NOW (" + args.group + " - " + GROUPS[args.group] + ")")
    print(render_questions(qs))
    print()
    print("Propose an answer to each of these before asking it, whenever "
          "anything already said supports one, and ask them to correct it "
          "rather than supply it. A learner who has just described what they "
          "do for a living has already answered why they are studying; "
          "asking it back reads as not having listened. An open question is "
          "for what genuinely cannot be inferred.")
    left = {k: v for k, v in still_needed(root).items()
            if v and k not in (args.group, "never")}
    if left:
        print()
        print("NOT NOW: " + "; ".join(
            k + " (" + ", ".join(v) + ")" for k, v in left.items()))
    return zs.EXIT_OK


def cmd_write(args) -> int:
    root = Path(args.root) if args.root else zs.default_root()
    answers = json.loads(Path(args.file).read_text(encoding="utf-8")
                         if args.file else args.data)
    config, profile = build(answers, args.learner_id)

    problems = []
    for doc, name, rel in ((config, "config", "config.json"),
                           (profile, "profile", "learner/profile.json")):
        for e in zs.validate_doc(doc, name):
            problems.append("[" + rel + "] " + e)
        for f in zs.semantic_check(doc, name, rel):
            if f.severity == "error":
                problems.append("[" + rel + "] " + f.code + " " + f.message)
            else:
                print("warning: " + f.code + " " + f.message, file=sys.stderr)

    if problems:
        for p in problems:
            print(p, file=sys.stderr)
        print("", file=sys.stderr)
        print("Nothing was written. Missing answers stay missing rather than "
              "being filled in with a guess.", file=sys.stderr)
        return zs.EXIT_VALIDATION

    (root / "learner").mkdir(parents=True, exist_ok=True)
    zs.atomic_write_json(root / "config.json", config)
    zs.atomic_write_json(root / "learner" / "profile.json", profile)
    print("written: config.json, learner/profile.json")
    print("teaching language: " + config["teaching_language"])
    print("")
    print("Next: create a course. Its goal is written as something the "
          "learner will be able to DO, with near-term milestones, and only "
          "then does it make sense to ask what practice will act on.")
    return zs.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="intake.py",
        description="The opening interview, before any course exists.")
    p.add_argument("--root")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("known", help="what can be read instead of asked")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_known)

    sp = sub.add_parser("questions", help="what still needs asking")
    sp.add_argument("--all", action="store_true")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_questions)

    sp = sub.add_parser("next", help="only what blocks the next thing")
    sp.add_argument("--group", required=True,
                    choices=sorted(GROUPS),
                    help="start, course, notes, item")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_next)

    sp = sub.add_parser("groups", help="the groups and when each is due")
    sp.set_defaults(func=lambda a: ([print(k.ljust(8) + v)
                                     for k, v in GROUPS.items()],
                                    zs.EXIT_OK)[1])

    sp = sub.add_parser("write", help="store the answers")
    sp.add_argument("--data", help="JSON object of answers")
    sp.add_argument("--file", help="path to the same, as a file")
    sp.add_argument("--learner-id", default="learner")
    sp.set_defaults(func=cmd_write)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
