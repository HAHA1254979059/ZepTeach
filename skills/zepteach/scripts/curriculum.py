#!/usr/bin/env python3
"""Curriculum navigation: what to teach next, and whether the plan is on time.

Two things the teaching layer should never guess at:

  - which lesson comes next, given what is proven, what is held back, and
    what the prerequisite graph actually says
  - whether the course is ahead or behind, measured against the deadline in
    minutes of work remaining, not in optimism

Output stays small on purpose: a lesson card is what a session needs, not the
whole curriculum.

Exit codes: 0 ok, 2 validation, 3 gate, 5 not found.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import learner as ln  # noqa: E402
import constants as K  # noqa: E402
import zt_state as zs  # noqa: E402


# --------------------------------------------------------------------------
# walking the curriculum
# --------------------------------------------------------------------------

def iter_lessons(curriculum: dict):
    for mod in curriculum.get("modules", []):
        for les in mod.get("lessons", []):
            yield mod, les


def find_lesson(curriculum: dict, lesson_id: str):
    for mod, les in iter_lessons(curriculum):
        if les.get("lesson_id") == lesson_id:
            return mod, les
    return None, None


def lesson_concepts(les: dict) -> list:
    return les.get("concepts", []) or []


def lesson_state(les: dict, by_id: dict) -> str:
    """done when every concept in it is at least consolidating; started when
    some are; otherwise untouched."""
    states = [(by_id.get(c.get("concept_id")) or {}).get("state", "unseen")
              for c in lesson_concepts(les)]
    if states and all(s in ln.PROVEN for s in states):
        return "done"
    if any(s not in ("unseen",) for s in states):
        return "started"
    return "untouched"


def blockers_for(les: dict, by_id: dict, taught_here: set) -> list:
    """Prerequisites that are shaky and not waved through. Unproven ground is
    handled by probing at lesson start; a held prerequisite is different, it
    means something already broke."""
    out = []
    for c in lesson_concepts(les):
        for p in c.get("prereq", []) or []:
            row = by_id.get(p) or {}
            down = row.get("downstream") or {}
            if row.get("state") == "shaky" and not down.get("bypassed"):
                out.append({"concept_id": p, "for": c.get("concept_id"),
                            "reason": "shaky"})
    return out


def next_lesson(curriculum: dict, rows: list):
    """First lesson in curriculum order that is not done. Reports its
    blockers rather than silently skipping it, because skipping is a decision
    the learner should make."""
    by_id = dict((r.get("concept_id"), r) for r in rows)
    taught = set()
    for _, les in iter_lessons(curriculum):
        for c in lesson_concepts(les):
            taught.add(c.get("concept_id"))
    for mod, les in iter_lessons(curriculum):
        if lesson_state(les, by_id) == "done":
            continue
        return {
            "module_id": mod.get("module_id"),
            "lesson_id": les.get("lesson_id"),
            "title": les.get("title"),
            "estimated_minutes": les.get("estimated_minutes"),
            "state": lesson_state(les, by_id),
            "blockers": blockers_for(les, by_id, taught),
        }
    return None


def lesson_card(curriculum: dict, lesson_id: str, rows: list,
                course: dict) -> dict:
    """Exactly what a session needs to teach one lesson, and nothing else."""
    mod, les = find_lesson(curriculum, lesson_id)
    if les is None:
        raise FileNotFoundError("no such lesson: " + lesson_id)
    by_id = dict((r.get("concept_id"), r) for r in rows)
    concepts = []
    for c in lesson_concepts(les):
        row = by_id.get(c.get("concept_id")) or {}
        concepts.append({
            "concept_id": c.get("concept_id"),
            "title": c.get("title"),
            "depth_target": c.get("depth_target"),
            "state": row.get("state", "unseen"),
            "depth_reached": row.get("depth_reached"),
            "prereq": c.get("prereq", []),
            "exercise_types": c.get("exercise_types", []),
            "modeling_prompt": c.get("modeling_prompt"),
            "common_misconceptions": c.get("common_misconceptions", []),
        })
    card = {
        "course_id": course.get("course_id"),
        "adapter_ref": course.get("adapter_ref"),
        "domain": course.get("domain"),
        "module": mod.get("title"),
        "lesson_id": lesson_id,
        "title": les.get("title"),
        "estimated_minutes": les.get("estimated_minutes"),
        "concepts": concepts,
        "source_anchored": bool(course.get("source_anchored")),
    }
    span = les.get("source_span")
    if span:
        card["source_span"] = span
    return card


# --------------------------------------------------------------------------
# pace against the deadline
# --------------------------------------------------------------------------

def remaining_minutes(curriculum: dict, rows: list) -> int:
    by_id = dict((r.get("concept_id"), r) for r in rows)
    total = 0
    for _, les in iter_lessons(curriculum):
        if lesson_state(les, by_id) == "done":
            continue
        total += int(les.get("estimated_minutes") or 0)
    return total


def drift(course: dict, curriculum: dict, rows: list, today: date = None):
    """Negative drift means behind. Reported in minutes per week, because that
    is the unit the learner actually spends."""
    today = today or datetime.now(timezone.utc).date()
    left = remaining_minutes(curriculum, rows)
    budget = int(course.get("weekly_minutes") or 0)
    out = {"remaining_minutes": left, "weekly_budget_minutes": budget}

    deadline = course.get("deadline")
    if not deadline:
        out["deadline"] = None
        if budget:
            out["weeks_at_current_budget"] = round(left / budget, 1)
        out["verdict"] = "no deadline set; pace is whatever you choose"
        return out

    dl = date.fromisoformat(deadline)
    days_left = (dl - today).days
    out["deadline"] = deadline
    out["days_left"] = days_left
    if days_left <= 0:
        out["verdict"] = ("deadline passed with " + str(left) +
                          " minutes of work left")
        out["required_weekly_minutes"] = None
        out["drift_minutes_per_week"] = None
        return out
    weeks = max(days_left / 7.0, 0.1)
    required = left / weeks
    out["required_weekly_minutes"] = int(round(required))
    out["drift_minutes_per_week"] = int(round(budget - required))
    if budget and required > budget * K.DRIFT_BEHIND_RATIO:
        out["verdict"] = ("behind: needs " + str(int(round(required))) +
                          " min/week, budget is " + str(budget))
    elif budget and required < budget * K.DRIFT_AHEAD_RATIO:
        out["verdict"] = "ahead of the deadline pace"
    else:
        out["verdict"] = "on pace"
    return out


# --------------------------------------------------------------------------
# registry helper
# --------------------------------------------------------------------------

def register_concepts(root: Path, course: dict, curriculum: dict) -> dict:
    """Add this curriculum's concepts to the global registry so other courses
    can reuse them. Never renames or merges anything that already exists."""
    p = root / "concepts.json"
    reg = zs.read_json(p) if p.exists() else {"schema_version": 1,
                                              "concepts": []}
    by_id = dict((c.get("concept_id"), c) for c in reg.get("concepts", []))
    course_id = course.get("course_id")
    added, linked = [], []
    for _, les in iter_lessons(curriculum):
        for c in lesson_concepts(les):
            cid = c.get("concept_id")
            if cid in by_id:
                entry = by_id[cid]
                if course_id not in (entry.get("courses") or []):
                    entry.setdefault("courses", []).append(course_id)
                    linked.append(cid)
                continue
            entry = {"concept_id": cid,
                     "canonical_title": c.get("title") or cid,
                     "domain": course.get("domain") or "unspecified",
                     "courses": [course_id],
                     "note_path": "notes/concepts/" + cid + ".md"}
            reg.setdefault("concepts", []).append(entry)
            by_id[cid] = entry
            added.append(cid)
    reg["updated"] = datetime.now(timezone.utc).replace(
        microsecond=0).isoformat()
    return {"registry": reg, "added": added, "linked": linked}


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------

def _root(args) -> Path:
    return Path(args.root) if args.root else zs.default_root()


def _load(root: Path, slug: str):
    cdir = root / "courses" / slug
    cpath = cdir / "course.json"
    if not cpath.exists():
        raise FileNotFoundError("no such course: " + slug)
    curpath = cdir / "curriculum.json"
    curriculum = zs.read_json(curpath) if curpath.exists() else {"modules": []}
    return cdir, zs.read_json(cpath), curriculum, ln.load_mastery(root)


def cmd_next(args) -> int:
    root = _root(args)
    _, course, curriculum, rows = _load(root, args.course)
    nxt = next_lesson(curriculum, rows)
    if nxt is None:
        print("every lesson in this course is done")
        return zs.EXIT_OK
    print(json.dumps(nxt, ensure_ascii=False, indent=2))
    return zs.EXIT_GATE if nxt["blockers"] else zs.EXIT_OK


def cmd_lesson(args) -> int:
    root = _root(args)
    _, course, curriculum, rows = _load(root, args.course)
    print(json.dumps(lesson_card(curriculum, args.lesson, rows, course),
                     ensure_ascii=False, indent=2))
    return zs.EXIT_OK


def cmd_drift(args) -> int:
    root = _root(args)
    _, course, curriculum, rows = _load(root, args.course)
    today = date.fromisoformat(args.today) if args.today else None
    d = drift(course, curriculum, rows, today)
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(d["verdict"])
        print("remaining: " + str(d["remaining_minutes"]) + " min" +
              ("  deadline: " + str(d["deadline"]) if d.get("deadline") else ""))
    return zs.EXIT_OK


def cmd_register(args) -> int:
    root = _root(args)
    _, course, curriculum, _rows = _load(root, args.course)
    res = register_concepts(root, course, curriculum)
    errs = zs.validate_doc(res["registry"], "concept_registry")
    findings = list(zs.rule_concept_registry(res["registry"], "concepts.json"))
    if errs:
        for e in errs:
            print("[SCHEMA] " + e, file=sys.stderr)
        return zs.EXIT_VALIDATION
    if any(f.severity == "error" for f in findings):
        for f in findings:
            print(str(f), file=sys.stderr)
        return zs.EXIT_VALIDATION
    zs.atomic_write_json(root / "concepts.json", res["registry"])
    print("registered " + str(len(res["added"])) + " new, linked " +
          str(len(res["linked"])) + " existing to this course")
    for cid in res["linked"]:
        print("  reused: " + cid + " (already known from another course)")
    for f in findings:
        print(str(f))
    return zs.EXIT_OK


def cmd_validate(args) -> int:
    root = _root(args)
    _, course, curriculum, _rows = _load(root, args.course)
    known = zs.registry_ids(root)
    findings = [zs.Finding("SCHEMA", "curriculum", e)
                for e in zs.validate_doc(curriculum, "curriculum")]
    findings.extend(zs.rule_curriculum(curriculum, "curriculum", known))
    findings.extend(zs.rule_course(course, "course"))
    if not findings:
        print("curriculum is sound")
        return zs.EXIT_OK
    errs = [f for f in findings if f.severity == "error"]
    for f in findings:
        print(str(f), file=sys.stderr if f.severity == "error" else sys.stdout)
    return zs.EXIT_VALIDATION if errs else zs.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="curriculum.py",
        description="What to teach next, and whether the plan is on time.")
    p.add_argument("--root")
    sub = p.add_subparsers(dest="cmd", required=True)

    for name, fn in (("next", cmd_next), ("register-concepts", cmd_register),
                     ("validate", cmd_validate)):
        sp = sub.add_parser(name)
        sp.add_argument("--course", required=True)
        sp.set_defaults(func=fn)

    sp = sub.add_parser("lesson")
    sp.add_argument("--course", required=True)
    sp.add_argument("--lesson", required=True)
    sp.set_defaults(func=cmd_lesson)

    sp = sub.add_parser("drift")
    sp.add_argument("--course", required=True)
    sp.add_argument("--today", help="YYYY-MM-DD, for testing")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_drift)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print("error: " + str(exc), file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    except ValueError as exc:
        print("error: " + str(exc), file=sys.stderr)
        return zs.EXIT_VALIDATION


if __name__ == "__main__":
    sys.exit(main())
