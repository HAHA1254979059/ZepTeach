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


def lesson_progress(root: Path, slug: str, curriculum: dict, lesson_id: str,
                    rows: list) -> dict:
    """What is still open in this lesson.

    The reason this exists: nothing decided when a lesson was over. The
    pointer was advisory, `curriculum.py next` printed a suggestion, and the
    judgement of whether to move on belonged to whoever was teaching - who,
    in the one real run, spent four hours on one lesson of a course with
    five weeks to cover seventy-eight concepts. Going deeper always feels
    like the responsible choice in the moment; that is exactly why it needs
    something outside the moment.
    """
    import teaching as tp
    les = None
    for mod in curriculum.get("modules") or []:
        for candidate in mod.get("lessons") or []:
            if candidate.get("lesson_id") == lesson_id:
                les = candidate
    if les is None:
        raise FileNotFoundError("no such lesson: " + lesson_id)

    cdir = root / "courses" / slug
    explained = set(e.get("concept_id")
                    for e in zs.read_jsonl(cdir / "expositions.jsonl"))
    deferred = dict((d["concept_id"], d)
                    for d in zs.read_jsonl(cdir / "deferrals.jsonl"))
    attempts = zs.read_jsonl(cdir / "attempts.jsonl")
    said_back = set()
    for a in attempts:
        if a.get("form") == "explain_back":
            said_back.update(a.get("concept_ids") or [])

    wanted = [c.get("concept_id") for c in les.get("concepts") or []]
    return {
        "lesson_id": lesson_id,
        "estimated_minutes": les.get("estimated_minutes"),
        "concepts": wanted,
        "not_explained": [c for c in wanted
                          if c not in explained and c not in deferred],
        "owes_explain_back": [c for c in wanted
                              if c in explained and c not in said_back
                              and c not in deferred],
        "deferred": sorted(deferred),
    }


def cmd_advance(args) -> int:
    """Move to the next lesson, or say what is stopping that.

    The refusal is the point. Either the lesson was finished or somebody
    decided out loud to leave part of it - both are fine, and drifting is
    not, because drifting is what produces a course that is one third
    covered and entirely out of time.
    """
    root = _root(args)
    _cdir, course, curriculum, rows = _load(root, args.course)
    st = lesson_progress(root, args.course, curriculum, args.lesson,
                         rows)

    blocked = []
    if st["not_explained"]:
        blocked.append("never explained: " + ", ".join(st["not_explained"]))
    if st["owes_explain_back"]:
        blocked.append("explained but never said back: " +
                       ", ".join(st["owes_explain_back"]))

    if blocked and not args.leaving_it:
        print("GATE FAILED: lesson " + args.lesson + " is not finished.",
              file=sys.stderr)
        for b in blocked:
            print("  " + b, file=sys.stderr)
        print("  Finish it, or decide with the learner to leave part of it "
              "and record that: curriculum.py defer --course " + args.course +
              " --lesson " + args.lesson + " --concepts <a,b> --because "
              "<their words>. Moving on without either is how a plan stops "
              "describing the course.", file=sys.stderr)
        return zs.EXIT_GATE

    nxt = next_lesson(curriculum, ln.load_mastery(root))
    print("lesson " + args.lesson + " closed" +
          (" (leaving " + ", ".join(st["not_explained"] +
                                    st["owes_explain_back"]) + ")"
           if blocked else ""))
    if nxt is None:
        print("every lesson in this course is done")
    else:
        print("next: " + str(nxt.get("lesson_id")))
    return zs.EXIT_OK


def cmd_defer(args) -> int:
    """Record that part of a lesson is being left, and why.

    Written down rather than dropped, so that a progress report can tell the
    difference between a course that covered less and a course that decided
    to cover less.
    """
    root = _root(args)
    cdir, _course, _curriculum, _rows = _load(root, args.course)
    when = zs.now_iso()
    for cid in args.concepts.split(","):
        zs.append_jsonl(cdir / "deferrals.jsonl", {
            "schema_version": 1,
            "concept_id": cid.strip(),
            "lesson_id": args.lesson,
            "deferred_at": when,
            "because": args.because,
        })
        print("deferred " + cid.strip())
    print("because: " + args.because)
    return zs.EXIT_OK


def pace_check(st: dict, minutes_spent: int) -> dict:
    """Whether this lesson is running long, and by how much.

    Reports; refuses nothing. A lesson can be worth twice its estimate. What
    is not worth anything is nobody noticing.
    """
    est = st.get("estimated_minutes")
    if not est or not minutes_spent:
        return {"known": False}
    ratio = minutes_spent / float(est)
    return {
        "known": True,
        "estimated_minutes": est,
        "spent_minutes": minutes_spent,
        "ratio": round(ratio, 2),
        "over": ratio >= K.LESSON_OVERRUN_RATIO,
        "say": ("这节课已经花了 " + str(minutes_spent) + " 分钟，计划是 " +
                str(est) + " 分钟。是继续深挖还是先往前走，你决定。"
                if ratio >= K.LESSON_OVERRUN_RATIO else ""),
    }


def plan_diff(old_cur: dict, new_cur: dict, rows: list) -> dict:
    """What this replan actually does to the course.

    Written out rather than applied quietly, because the expensive case is
    invisible: dropping concepts that were already taught. Those have review
    debt against them, they are prerequisites for things still in the plan,
    and a schedule that no longer mentions them keeps scheduling them. A plan
    can absolutely be cut - most plans should be - but cutting it is a
    decision somebody makes, not a side effect of writing a new file.
    """
    def ids(cur):
        out = []
        for mod in cur.get("modules") or []:
            for les in mod.get("lessons") or []:
                for c in les.get("concepts") or []:
                    out.append(c.get("concept_id"))
        return out

    before, after = set(ids(old_cur)), set(ids(new_cur))
    by_id = dict((r.get("concept_id"), r) for r in rows)
    dropped = sorted(before - after)
    return {
        "added": sorted(after - before),
        "dropped": dropped,
        "dropped_but_already_taught": sorted(
            c for c in dropped
            if (by_id.get(c) or {}).get("state", "unseen") != "unseen"),
        "kept": len(before & after),
    }


def cmd_replan(args) -> int:
    """Change the course, on the record.

    Every plan change is recorded with the learner's own reason. Without
    that, a progress report months later compares work done under one plan
    with a plan that has since been rewritten, and reports whichever story
    the current file happens to tell.
    """
    root = _root(args)
    cdir, course, old_cur, rows = _load(root, args.course)
    new_cur = json.loads(Path(args.file).read_text(encoding="utf-8")
                         if args.file else args.data)

    errors = zs.validate_doc(new_cur, "curriculum")
    if errors:
        for e in errors:
            print("invalid curriculum: " + str(e), file=sys.stderr)
        return zs.EXIT_VALIDATION

    diff = plan_diff(old_cur, new_cur, rows)
    if diff["dropped_but_already_taught"] and not args.drop_taught:
        print("GATE FAILED: this plan drops concepts that were already "
              "taught: " + ", ".join(diff["dropped_but_already_taught"]) +
              ". They still carry review debt and may be prerequisites for "
              "what is left. Say so to the learner and pass --drop-taught "
              "if that is what they want.", file=sys.stderr)
        return zs.EXIT_GATE

    when = zs.now_iso()
    new_cur["version"] = int(old_cur.get("version") or 1) + 1
    new_cur["updated"] = when
    zs.atomic_write_json(cdir / "curriculum.json", new_cur)
    zs.append_jsonl(cdir / "plan_changes.jsonl", {
        "schema_version": 1,
        "changed_at": when,
        "version": new_cur["version"],
        "because": args.because,
        "diff": diff,
    })

    print("plan updated to version " + str(new_cur["version"]))
    print("  because: " + args.because)
    print("  added " + str(len(diff["added"])) + ", dropped " +
          str(len(diff["dropped"])) + ", kept " + str(diff["kept"]))
    if diff["dropped_but_already_taught"]:
        print("  dropped after being taught: " +
              ", ".join(diff["dropped_but_already_taught"]))
        print("  their reviews still come due. Retire them deliberately or "
              "leave them in the queue, but do not let the queue decide")
    return zs.EXIT_OK


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

    sp = sub.add_parser("advance", help="close this lesson and move on")
    sp.add_argument("--course", required=True)
    sp.add_argument("--lesson", required=True)
    sp.add_argument("--leaving-it", action="store_true",
                    help="they agreed to leave part of it unfinished")
    sp.set_defaults(func=cmd_advance)

    sp = sub.add_parser("defer", help="leave part of a lesson, on the record")
    sp.add_argument("--course", required=True)
    sp.add_argument("--lesson", required=True)
    sp.add_argument("--concepts", required=True)
    sp.add_argument("--because", required=True)
    sp.set_defaults(func=cmd_defer)

    sp = sub.add_parser("replan", help="change the course, on the record")
    sp.add_argument("--course", required=True)
    sp.add_argument("--because", required=True,
                    help="the learner's reason, in their words")
    sp.add_argument("--file")
    sp.add_argument("--data")
    sp.add_argument("--drop-taught", action="store_true",
                    help="they agreed to drop concepts already taught")
    sp.set_defaults(func=cmd_replan)

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
