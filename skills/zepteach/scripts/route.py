#!/usr/bin/env python3
"""Selective loading: what to read for the thing you are about to do.

A teaching system that loads its whole doctrine on every turn is expensive and
worse at its job, because the guidance that matters gets buried in guidance
that does not. So SKILL.md stays thin and carries a routing table, and this
script resolves an intent into the smallest set of reference files and
commands that intent actually needs.

The route is also conditional: a course with no registered textbook does not
load the source-anchoring doctrine, and only the adapter for the domain in
hand is read, never all of them.

Reference files named here are the contract for stage S2 onward. Missing ones
are reported as missing rather than silently skipped.

Exit codes: 0 ok, 5 unknown intent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import zt_state as zs  # noqa: E402

REF_DIR = Path(__file__).resolve().parents[1] / "references"


# Each route: what to read, what to run, and what NOT to pull in yet.
ROUTES = {
    "setup1": {
        "what": "first-time setup: who is learning, in what language, "
                "notes where",
        "read": ["setup-stage1.md", "persona-zep.md"],
        "run": ["intake.py known", "zt_state.py init",
                "intake.py write --data <json>", "zt_state.py validate"],
        "defer": "environment probing belongs to setup2, after the study "
                 "goal exists",
    },
    "course-new": {
        "what": "design a course from a goal",
        "read": ["curriculum-design.md", "adapter-contract.md"],
        "run": ["curriculum.py register-concepts --course <slug>",
                "curriculum.py validate --course <slug>"],
        "agent": "zt-curriculum-architect",
        "defer": "teaching doctrine is not needed to plan a course",
    },
    "setup2": {
        "what": "second-stage setup: what this course needs to practise on, and how close we can get to it",
        "read": ["setup-stage2.md", "practice-reach.md"],
        "run": ["practice_reach.py check --course <slug>",
                "zt_state.py gate course-env --course <slug>"],
        "conditional": {"tools": ["resources-and-tools.md"]},
        "defer": "no teaching material yet; this is about what practice will land on",
    },
    "lesson": {
        "what": "teach",
        "read": ["persona-zep.md", "teaching-contract.md", "delivery.md",
                 "mode-router.md", "session-protocol.md"],
        "run": ["session.py open --course <slug> --energy <level>",
                "learner.py probe --course <slug> --lesson <id>",
                "curriculum.py lesson --course <slug> --lesson <id>"],
        "conditional": {"source_anchored": ["source-anchoring.md"],
                        "adapter": True},
        "then": {"review": "session protocol step 3 clears due reviews; "
                           "resolve that route when you get there",
                 "exercise": "step 7",
                 "notes": "step 9",
                 "close": "step 10"},
        "defer": "exercise-engine.md and assessment-rubrics.md load when you "
                 "reach exercises, not before",
    },
    "exercise": {
        "what": "set and run exercises",
        "read": ["exercise-engine.md"],
        "run": ["exercise.py issue --course <slug> --lesson <id>"],
        "conditional": {"adapter": True, "tools": ["resources-and-tools.md"]},
        "defer": "the rubric itself goes to the grader, not into this context",
    },
    "grade": {
        "what": "judge an answer",
        "read": ["assessment-rubrics.md"],
        "run": ["grade.py package --item <i> --rubric <r> --answer <a>",
                "grade.py check --verdict <v> --rubric <r> --answer <a>",
                "learner.py record --course <slug> --file <attempt.json>"],
        "agent": "zt-grader",
        "isolate": "the grader gets the item, the rubric and the answer. It "
                   "does not get the teaching transcript, and it is not Zep",
        "defer": "teaching doctrine must not reach the grader",
    },
    "review": {
        "what": "run due reviews and retests",
        "read": ["mastery-policy.md", "persona-zep.md"],
        "run": ["review.py rebuild --course <slug>",
                "review.py due --course <slug>",
                "review.py plan --concept <id>"],
        "defer": "no new material; this is about what is already owed",
    },
    "sidequest": {
        "what": "fill a background gap without derailing the main line",
        "read": ["sidequest-protocol.md"],
        "run": ["learner.py probe --course <slug> --lesson <id>"],
        "agent": "zt-sidequest-tutor",
        "isolate": "the subagent gets the gap, the register and a depth "
                   "ceiling. The main line gets back a short digest, one "
                   "note and a mastery entry, not the transcript",
    },
    "notes": {
        "what": "write or repair the canonical notes",
        "read": ["note-doctrine.md"],
        "run": ["notes.py check", "notes.py write --concept <id>"],
        "defer": "session chatter belongs in the journal, not here",
    },
    "checkpoint": {
        "what": "compress the session and carry on",
        "read": ["context-budget.md"],
        "run": ["session.py checkpoint --session <id> --digest <path>"],
        "defer": "nothing else; this step exists to shed context, not add it",
    },
    "close": {
        "what": "end the session honestly",
        "read": ["load-and-energy.md", "note-doctrine.md"],
        "run": ["session.py close --session <id> --reason <reason>",
                "review.py rebuild --course <slug>"],
    },
    "assess": {
        "what": "stage assessment and an objective progress report",
        "read": ["assessment-rubrics.md", "mastery-policy.md"],
        "run": ["progress_report.py --course <slug>"],
        "agent": "zt-grader",
    },
    "lookup": {
        "what": "go and find something Zep does not know",
        "read": ["tool-integration.md"],
        "run": [],
        "defer": "admitting ignorance and checking is always cheaper than a "
                 "confident guess; this route exists so that admitting it "
                 "leads somewhere",
    },
    "status": {
        "what": "where things stand",
        "read": [],
        "run": ["learner.py show", "curriculum.py drift --course <slug>",
                "review.py due --course <slug>"],
        "defer": "this is a scripts-only intent; no doctrine needs loading",
    },
}


def _course(root: Path, slug: str):
    p = root / "courses" / slug / "course.json"
    return zs.read_json(p) if p.exists() else None


def resolve(intent: str, root: Path = None, slug: str = None) -> dict:
    spec = ROUTES.get(intent)
    if spec is None:
        raise KeyError(intent)

    read = list(spec.get("read", []))
    reasons = {}
    cond = spec.get("conditional") or {}
    course = _course(root, slug) if (root and slug) else None

    if course is not None:
        if cond.get("adapter"):
            # The adapter lives with the learner's data, not in the plugin.
            # It is generated when the course is set up, from the goal and
            # from what is actually within reach, so the plugin ships no list
            # of disciplines at all - for the same reason it ships no list of
            # installed software. A path here, never an enum.
            ref = course.get("adapter_ref")
            if ref:
                read.append(ref)
                reasons[ref] = ("the adapter generated for this course, in "
                                "the data root")
            else:
                reasons["_adapter"] = (
                    "this course has no adapter yet; generate one before "
                    "teaching (see adapter-contract.md)")
        if "source_anchored" in cond and course.get("source_anchored"):
            for f in cond["source_anchored"]:
                read.append(f)
                reasons[f] = "this course teaches from registered material"
        if "tools" in cond:
            # Loaded only when this course actually has tools registered.
            # A course whose practice is reading and writing never sees this
            # doctrine at all.
            res = root / "courses" / slug / "resources.json"
            has_tools = False
            if res.exists():
                has_tools = bool(zs.read_json(res).get("tools"))
            if has_tools:
                for f in cond["tools"]:
                    read.append(f)
                    reasons[f] = "this course has tools registered for it"
    elif cond:
        reasons["_note"] = ("pass --course to resolve the conditional parts "
                            "of this route")

    out = {
        "intent": intent,
        "what": spec.get("what"),
        "read": read,
        "read_reasons": reasons,
        "run": spec.get("run", []),
        "missing": [f for f in read
                    if f.endswith(".md") and not f.startswith("adapters/")
                    and not (REF_DIR / f).exists()],
    }
    for key in ("agent", "isolate", "defer"):
        if spec.get(key):
            out[key] = spec[key]
    if spec.get("then"):
        out["then"] = spec["then"]
    return out


def render(res: dict) -> str:
    lines = ["INTENT  " + res["intent"] + " - " + str(res["what"])]
    if res["read"]:
        lines.append("READ (" + str(len(res["read"])) + ")")
        for f in res["read"]:
            why = res["read_reasons"].get(f)
            lines.append("  " + f + ("   <- " + why if why else ""))
    else:
        lines.append("READ  nothing; scripts are enough for this")
    if res["missing"]:
        lines.append("  NOT WRITTEN YET: " + ", ".join(res["missing"]))
    if res["run"]:
        lines.append("RUN")
        for c in res["run"]:
            lines.append("  " + c)
    if res.get("agent"):
        lines.append("SUBAGENT  " + res["agent"])
    if res.get("isolate"):
        lines.append("ISOLATION  " + res["isolate"])
    if res.get("then"):
        lines.append("LATER, SEPARATELY (do not load these now)")
        for intent, when in res["then"].items():
            lines.append("  " + intent + "  <- " + when)
    if res.get("defer"):
        lines.append("DO NOT LOAD  " + res["defer"])
    return "\n".join(lines)


def cmd_route(args) -> int:
    root = Path(args.root) if args.root else zs.default_root()
    try:
        res = resolve(args.intent, root, args.course)
    except KeyError:
        print("unknown intent: " + args.intent, file=sys.stderr)
        print("available: " + ", ".join(sorted(ROUTES)), file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    print(json.dumps(res, ensure_ascii=False, indent=2) if args.json
          else render(res))
    return zs.EXIT_OK


def cmd_list(args) -> int:
    if args.json:
        print(json.dumps(
            dict((k, {"what": v.get("what"),
                      "read": v.get("read", [])}) for k, v in ROUTES.items()),
            ensure_ascii=False, indent=2))
        return zs.EXIT_OK
    width = max(len(k) for k in ROUTES)
    for k in sorted(ROUTES):
        spec = ROUTES[k]
        n = len(spec.get("read", []))
        print(k.ljust(width) + "  " + str(spec.get("what")) +
              "  (" + str(n) + " file" + ("s" if n != 1 else "") + ")")
    return zs.EXIT_OK


def cmd_audit(args) -> int:
    """Which reference files every route depends on, and which are missing.
    This is the running to-do list for the doctrine stages."""
    needed = {}
    for k, spec in ROUTES.items():
        for f in spec.get("read", []):
            needed.setdefault(f, []).append(k)
        cond = spec.get("conditional") or {}
        for key, val in cond.items():
            if isinstance(val, list):
                for f in val:
                    needed.setdefault(f, []).append(k + " (" + key + ")")
    rows = []
    for f in sorted(needed):
        rows.append({"file": f, "used_by": needed[f],
                     "exists": (REF_DIR / f).exists()})
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return zs.EXIT_OK
    missing = [r for r in rows if not r["exists"]]
    for r in rows:
        mark = "ok " if r["exists"] else "-- "
        print(mark + r["file"] + "   used by: " + ", ".join(r["used_by"]))
    print("")
    print(str(len(rows) - len(missing)) + " written, " + str(len(missing)) +
          " still owed")
    return zs.EXIT_OK


def cmd_sizes(args) -> int:
    """How much doctrine each intent loads.

    The ceilings are recorded but not enforced while the doctrine is being
    written, so this keeps the numbers visible. Compressing happens once
    everything exists, when it is editing rather than deciding what to leave
    out.
    """
    import constants as K
    rows = []
    for intent in sorted(ROUTES):
        files = ROUTES[intent].get("read", [])
        total = 0
        present = []
        for f in files:
            path = REF_DIR / f
            if path.exists():
                n = len(path.read_text(encoding="utf-8").splitlines())
                total += n
                present.append((f, n))
        rows.append((intent, total, present, len(files) - len(present)))

    if args.json:
        print(json.dumps([{"intent": i, "lines": t, "unwritten": m}
                          for i, t, _, m in rows],
                        ensure_ascii=False, indent=2))
        return zs.EXIT_OK

    ceiling = K.LESSON_DOCTRINE_MAX_LINES
    for intent, total, present, missing in rows:
        mark = "  " if total <= ceiling else "! "
        line = mark + intent.ljust(12) + str(total).rjust(5) + " lines"
        if missing:
            line += "   (+" + str(missing) + " not written yet)"
        print(line)
        if args.detail:
            for f, n in present:
                print("        " + f.ljust(28) + str(n).rjust(5))
    print("")
    print("ceiling " + str(ceiling) + " per intent, " +
          ("enforced" if K.enforced("lesson_doctrine_max_lines")
           else "recorded but NOT enforced while the doctrine is written"))
    return zs.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="route.py",
        description="Resolve an intent into the smallest set of files to read.")
    p.add_argument("--root")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("for")
    sp.add_argument("intent")
    sp.add_argument("--course")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_route)

    sp = sub.add_parser("list")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("sizes", help="how much each intent loads")
    sp.add_argument("--detail", action="store_true")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_sizes)

    sp = sub.add_parser("audit")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_audit)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
