#!/usr/bin/env python3
"""Bringing a data root written by an older version up to the current one.

The learner's records outlive the plugin. Somebody studies for three weeks,
the plugin gains a rule, and the question is what happens to the three weeks.
Two answers are unacceptable: refusing to run, and pretending the old records
already satisfy the new rule.

So the rules here are:

  Nothing is invented. Where the old records cannot answer a question the new
  version asks, that is written down as not knowable, naming exactly which
  concepts and why, and it stays visible in the progress report rather than
  dissolving into the data.

  Steps are identified by name, not by a version number. A migration added
  later, in the middle of the list, still runs on a root that has already had
  the later ones: the ledger records which steps ran, and anything not in it
  is applied. Numbering them instead is how a root silently skips a step
  forever, because it looks up to date.

  Every step can be run twice with the same result. An interrupted upgrade is
  finished by running it again, not by working out where it stopped.

  Nothing is changed before a copy is taken.

`check` reads and reports; it changes nothing and is safe to run any time.
`apply` does the work.

Exit codes: 0 up to date / applied, 2 invalid data, 3 work is outstanding.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import zt_state as zs  # noqa: E402

LEDGER = "migrations.jsonl"
GRANDFATHERED = "learner/taught_before_expositions.json"


def ledger(root: Path) -> list:
    return zs.read_jsonl(root / LEDGER)


def applied(root: Path) -> set:
    return set(r.get("step") for r in ledger(root))


def _mastery(root: Path) -> list:
    return zs.read_jsonl(root / "learner" / "mastery.jsonl")


def _expositions(root: Path) -> list:
    out = []
    courses = root / "courses"
    if courses.exists():
        for cdir in sorted(courses.iterdir()):
            if cdir.is_dir():
                out.extend(zs.read_jsonl(cdir / "expositions.jsonl"))
    return out


# ---------------------------------------------------------------------------
# step: concepts taught before explanations were recorded
# ---------------------------------------------------------------------------

TEACHING_EVIDENCE = "teaching-evidence"


def teaching_evidence_needed(root: Path) -> dict:
    """Concepts the records say were taught, with nothing on file about what
    was said.

    Before expositions existed, marking something taught was a command that
    took no content, so these are not records of a rule being broken. They
    are records made under a rule that did not exist yet, and the honest
    description of them is that nobody can now say what was said.
    """
    have = set(e.get("concept_id") for e in _expositions(root))
    rows = [r for r in _mastery(root)
            if r.get("state", "unseen") != "unseen"
            and r.get("concept_id") not in have]
    return {
        "step": TEACHING_EVIDENCE,
        "concepts": sorted(r.get("concept_id") for r in rows),
        "what_changes": "Recording an attempt now needs an explanation on "
                        "file from before the answer. These concepts were "
                        "taught under a version that did not record one, so "
                        "they are exempted by name and by date - not "
                        "back-filled with an explanation nobody wrote.",
        "cost": "Their explanations are lost. If one of them turns out to be "
                "shaky, re-teaching it is the repair, and that re-teaching "
                "will be recorded properly.",
    }


def apply_teaching_evidence(root: Path, when: str) -> dict:
    found = teaching_evidence_needed(root)
    rows = {}
    by_id = dict((r.get("concept_id"), r) for r in _mastery(root))
    for cid in found["concepts"]:
        m = by_id.get(cid) or {}
        rows[cid] = {"state": m.get("state"),
                     "first_taught": m.get("first_taught")}

    path = root / GRANDFATHERED
    existing = zs.read_json(path) if path.exists() else {}
    merged = dict(existing.get("concepts") or {})
    merged.update(rows)

    doc = {
        "schema_version": 1,
        "recorded_at": existing.get("recorded_at") or when,
        "why": "These concepts were taught by a version of this plugin that "
               "did not record what was said. They are exempt from the "
               "explanation gate because the gate did not exist when they "
               "were taught, not because anything is known about how they "
               "were taught. Nothing here should ever be added to by hand: "
               "anything taught from now on has its explanation on file.",
        "concepts": merged,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    zs.atomic_write_json(path, doc)
    return {"exempted": sorted(merged)}


# ---------------------------------------------------------------------------
# step: how this learner supplies notation
# ---------------------------------------------------------------------------

NOTATION = "notation-channel"


def notation_needed(root: Path) -> dict:
    """Whether the profile can answer a question items now ask of it.

    Nothing can be migrated here, because the answer is the learner's and
    nobody else has it. What the upgrade can do is make sure the question
    gets asked before it matters, rather than in the middle of a lesson,
    which is when it got asked last time.
    """
    p = root / "learner" / "profile.json"
    profile = zs.read_json(p) if p.exists() else {}
    if profile.get("notation_input"):
        return {"step": NOTATION, "concepts": [], "ask": None}
    return {
        "step": NOTATION,
        "concepts": [],
        "ask": "When an answer needs something awkward to type - a formula, "
               "a structure, a diagram - how do you want to give it? Typing "
               "it out, writing it as markup, photographing it off paper, or "
               "picking between candidates I offer. More than one is fine.",
        "what_changes": "Items now declare how they are answered, and an "
                        "item that needs typed notation from somebody who "
                        "would rather photograph it is refused.",
        "cost": "None to the existing records. This is a question the "
                "profile cannot answer yet.",
    }


def apply_notation(root: Path, when: str) -> dict:
    """Deliberately writes nothing.

    Recorded as applied so the upgrade is complete, while the question stays
    outstanding in `check` until the learner answers it. Guessing an answer
    here would be worse than leaving it open: it would look like the learner
    had said something.
    """
    return {"asked": bool(notation_needed(root)["ask"])}


STEPS = [
    {"id": TEACHING_EVIDENCE,
     "title": "explanations are recorded, and old concepts have none",
     "needed": teaching_evidence_needed,
     "apply": apply_teaching_evidence},
    {"id": NOTATION,
     "title": "the learner has not said how they supply notation",
     "needed": notation_needed,
     "apply": apply_notation},
]


# ---------------------------------------------------------------------------
# what the rest of the system asks
# ---------------------------------------------------------------------------

def grandfathered(root: Path) -> set:
    """Concepts exempt from the explanation gate because they predate it."""
    p = root / GRANDFATHERED
    if not p.exists():
        return set()
    try:
        return set((zs.read_json(p).get("concepts") or {}))
    except json.JSONDecodeError:
        return set()


def outstanding(root: Path) -> list:
    """Steps this root has not had, in order. Empty means up to date."""
    done = applied(root)
    out = []
    for step in STEPS:
        if step["id"] in done:
            continue
        found = step["needed"](root)
        out.append(dict(found, id=step["id"], title=step["title"]))
    return out


def needs_upgrade(root: Path) -> bool:
    return bool(outstanding(root))


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def _root(args) -> Path:
    return Path(args.root) if args.root else zs.default_root()


def backup(root: Path, when: str) -> Path:
    """A copy before anything is touched.

    Whole-root and plain, rather than clever. The records are text and there
    are not many of them, so the cheap option is also the one that cannot go
    wrong in a way that matters.
    """
    dest = root / ".backups" / when.replace(":", "").replace("-", "")[:15]
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root, dest,
                    ignore=shutil.ignore_patterns(".backups"))
    return dest


def cmd_check(args) -> int:
    root = _root(args)
    if not (root / "config.json").exists() and not (root / "learner").exists():
        print("no data root at " + str(root) + ": nothing to upgrade")
        return zs.EXIT_OK

    work = outstanding(root)
    if args.json:
        print(json.dumps({"root": str(root), "outstanding": work},
                         ensure_ascii=False, indent=2))
        return zs.EXIT_GATE if work else zs.EXIT_OK

    if not work:
        print("up to date: " + str(root))
        return zs.EXIT_OK

    print("this data root was written by an earlier version.")
    print("run: migrate.py apply --root " + str(root))
    print()
    for w in work:
        print("- " + w["id"] + ": " + w["title"])
        if w.get("concepts"):
            print("    affects " + str(len(w["concepts"])) + " concepts: " +
                  ", ".join(w["concepts"][:6]) +
                  (", ..." if len(w["concepts"]) > 6 else ""))
        if w.get("what_changes"):
            print("    " + w["what_changes"])
        if w.get("cost"):
            print("    cost: " + w["cost"])
        if w.get("ask"):
            print("    ASK THE LEARNER: " + w["ask"])
    return zs.EXIT_GATE


def cmd_apply(args) -> int:
    root = _root(args)
    work = outstanding(root)
    if not work:
        print("up to date: " + str(root))
        return zs.EXIT_OK

    when = zs.now_iso()
    where = backup(root, when)
    print("copied the root to " + str(where) + " before touching anything")

    asks = []
    for step in STEPS:
        if step["id"] in applied(root):
            continue
        result = step["apply"](root, when)
        zs.append_jsonl(root / LEDGER, {
            "schema_version": 1,
            "step": step["id"],
            "applied_at": when,
            "backup": str(where),
            "result": result,
        })
        print("applied " + step["id"] + ": " +
              json.dumps(result, ensure_ascii=False))
        found = step["needed"](root)
        if found.get("ask"):
            asks.append(found["ask"])

    exempt = grandfathered(root)
    if exempt:
        print()
        print(str(len(exempt)) + " concepts are exempt from the explanation "
              "gate because they were taught before explanations were "
              "recorded. They are listed in " + GRANDFATHERED + " and appear "
              "in the progress report, so this does not quietly become "
              "permanent.")
    for ask in asks:
        print()
        print("STILL TO ASK: " + ask)
    return zs.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="migrate.py",
        description="Bring a data root up to the current version.")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("check", help="what this root needs; changes nothing")
    sp.add_argument("--root")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("apply", help="back up, then do it")
    sp.add_argument("--root")
    sp.set_defaults(func=cmd_apply)

    sp = sub.add_parser("steps", help="every step and what it is for")
    sp.add_argument("--root")
    sp.set_defaults(func=lambda a: (
        [print(s["id"] + "\n  " + s["title"]) for s in STEPS],
        zs.EXIT_OK)[1])
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
