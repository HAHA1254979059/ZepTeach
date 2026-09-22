#!/usr/bin/env python3
"""What actually happened, computed from the records and nothing else.

No impression of how it went goes into this, from the learner or from Zep.
Both are reading how fluent things felt recently, which is the measure this
whole system is built to distrust.

The harder design problem is that a report can be accurate and still
flattering. Counting concepts at each state produces a number that rises
steadily and says almost nothing: it does not say what evidence supported the
promotions, how much was waved through, or how much depth was quietly given
up. So every figure here that could be read as progress is printed next to
the thing that qualifies it, and the qualifications are not optional
sections.

Exit codes: 0 ok, 5 not found.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import constants as K  # noqa: E402
import curriculum as cur  # noqa: E402
import learner as ln  # noqa: E402
import review as rv  # noqa: E402
import zt_state as zs  # noqa: E402


def _parse(stamp):
    if not stamp:
        return None
    try:
        dt = datetime.fromisoformat(str(stamp))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


# ---------------------------------------------------------------------------
# what the states rest on
# ---------------------------------------------------------------------------

def evidence_behind(row: dict) -> dict:
    """What actually supports this concept's state.

    A state is a claim. This is the claim's basis, separated into the kinds
    that count differently: work done during the lesson says little about
    next week, and everything after a delay says a great deal.
    """
    kinds = Counter(e.get("kind") for e in row.get("evidence", [])
                    if e.get("verdict") == "pass")
    delayed = kinds["delayed_retest"] + kinds["transfer_test"] + \
        kinds["assessment"]
    return {
        "in_lesson": kinds["inclass"],
        "delayed": delayed,
        "transfer": kinds["transfer_test"],
        "kinds": dict(kinds),
    }


def unsupported(rows: list) -> list:
    """States that the evidence does not reach.

    Should always be empty: the state machine refuses these on the way in.
    It is recomputed here anyway, because a rule that is only checked at
    write time stops catching anything the moment a file is edited by hand or
    written by an older version.
    """
    needed = {"consolidating": 1, "mastered": 2}
    out = []
    for row in rows:
        want = needed.get(row.get("state"))
        if not want:
            continue
        have = evidence_behind(row)["delayed"]
        if have < want:
            out.append({"concept_id": row.get("concept_id"),
                        "state": row.get("state"),
                        "delayed_evidence": have,
                        "needs": want})
    return out


def weak_transfers(rows: list) -> list:
    """Concepts marked mastered on a transfer test that barely moved.

    Moving only along knowledge domain is what the weaker criterion already
    did. Such a pass is real but thin, and a report that does not say so is
    presenting it as more than it is.
    """
    out = []
    for row in rows:
        if row.get("state") != "mastered":
            continue
        dims = set()
        for e in row.get("evidence", []):
            if e.get("kind") == "transfer_test" and e.get("verdict") == "pass":
                dims.update(e.get("transfer_dimensions") or [])
        if dims and dims <= {"knowledge_domain"}:
            out.append({"concept_id": row.get("concept_id"),
                        "dimensions": sorted(dims)})
        elif not dims:
            out.append({"concept_id": row.get("concept_id"),
                        "dimensions": [],
                        "note": "the transfer test did not record which "
                                "dimension it moved along"})
    return out


# ---------------------------------------------------------------------------
# what was given up
# ---------------------------------------------------------------------------

def bypasses(rows: list) -> list:
    """Prerequisites waved through, with how many times.

    Waving one through is legitimate and the system allows it. What it does
    not allow is forgetting: a course built on three bypassed prerequisites
    is a different course from one built on none, and the difference belongs
    in the report rather than in somebody's memory.
    """
    out = []
    for row in rows:
        down = row.get("downstream") or {}
        if down.get("bypassed"):
            out.append({
                "concept_id": row.get("concept_id"),
                "state": row.get("state"),
                "times": down.get("bypass_count", 1),
                "reason": down.get("bypass_reason", ""),
            })
    return sorted(out, key=lambda r: -r["times"])


def depth_given_up(course: dict) -> list:
    """Depth targets lowered because practice could not reach far enough.

    Kept for the life of the course. The alternative is that the course
    finishes and reports success at a level nobody ever demonstrated.
    """
    env = course.get("environment") or {}
    return list(env.get("depth_concessions") or [])


def never_retested(rows: list, now) -> list:
    """Taught, practised, and then nothing.

    The quiet failure of a spaced system: material that was covered, felt
    fine at the time, and never came back. It does not appear as a failure
    anywhere else, because nothing failed.
    """
    out = []
    for row in rows:
        if row.get("state") not in ("introduced", "practiced"):
            continue
        taught = _parse(row.get("first_taught"))
        if not taught:
            continue
        days = (now - taught).total_seconds() / 86400.0
        if days >= K.NEVER_RETESTED_AFTER_DAYS and \
                not evidence_behind(row)["delayed"]:
            out.append({"concept_id": row.get("concept_id"),
                        "state": row.get("state"),
                        "days_since_taught": round(days)})
    return sorted(out, key=lambda r: -r["days_since_taught"])


def diagnostic_snapshot(attempts: list) -> dict:
    """Describe observed strengths and gaps without turning them into a score.

    Older multi-concept attempts have only a whole-item verdict. They remain
    readable, but that verdict cannot honestly be assigned to either
    concept, so the report counts them separately.
    """
    by_concept = {}
    unattributed = 0
    legacy_affected = set()
    for attempt in attempts:
        ids = attempt.get("concept_ids") or []
        parts = attempt.get("concept_results")
        if not parts:
            if len(ids) != 1:
                if len(ids) > 1:
                    unattributed += 1
                    legacy_affected.update(ids)
                continue
            parts = [dict(attempt, concept_id=ids[0])]
        for part in parts:
            cid = part.get("concept_id")
            if not cid:
                continue
            row = by_concept.setdefault(cid, {"concept_id": cid})
            row["last_observed"] = attempt.get("submitted_at")
            row["last_verdict"] = part.get("verdict")
            if part.get("verdict") == "unassessed":
                row["last_observation"] = "not assessed"
                continue
            row.pop("last_observation", None)
            quotes = part.get("evidence_quotes") or []
            if quotes:
                row["last_demonstrated"] = quotes[0]
            failures = part.get("failure_points") or []
            slips = part.get("slips") or attempt.get("slips") or []
            if part.get("verdict") == "pass":
                row.pop("last_concept_gap", None)
                row.pop("last_execution_issue", None)
            elif part.get("execution_only"):
                row.pop("last_concept_gap", None)
                row["last_execution_issue"] = (failures or slips or
                                               ["execution needs a redo"])[0]
            elif part.get("verdict") in ("partial", "fail"):
                row.pop("last_execution_issue", None)
                row["last_concept_gap"] = (failures or
                                           ["answer did not establish this concept"])[0]
    return {"concepts": sorted(by_concept.values(),
                               key=lambda row: row["concept_id"]),
            "older_multi_concept_items_without_attribution": unattributed,
            "concepts_touched_by_unattributed_items": sorted(legacy_affected)}


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------

def build(root: Path, slug: str, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    cdir = root / "courses" / slug
    course = zs.read_json(cdir / "course.json")
    cid = course.get("course_id")

    rows = [r for r in ln.load_mastery(root) if cid in (r.get("courses") or [])]
    states = Counter(r.get("state", "unseen") for r in rows)

    curriculum = {}
    cpath = cdir / "curriculum.json"
    if cpath.exists():
        curriculum = zs.read_json(cpath)
    planned = len({c.get("concept_id")
                   for m in curriculum.get("modules", [])
                   for l in m.get("lessons", [])
                   for c in l.get("concepts", [])})

    qpath = cdir / "review_queue.json"
    queue = zs.read_json(qpath) if qpath.exists() else {"items": []}
    attempts = zs.read_jsonl(cdir / "attempts.jsonl")

    report = {
        "course": {"slug": slug, "title": course.get("title"),
                   "goal": course.get("goal")},
        "generated_at": now.isoformat(),
        "computed_from": ["mastery records", "recorded attempts",
                          "the review queue", "the course file"],
        "not_computed_from": ["anyone's impression of how sessions went"],
        "concepts": {
            "in_curriculum": planned,
            "touched": len(rows),
            "by_state": dict(states),
        },
        "evidence": {
            "mastered_on_two_delayed": sum(
                1 for r in rows if r.get("state") == "mastered"),
            "resting_on_in_lesson_work_only": sum(
                1 for r in rows
                if evidence_behind(r)["delayed"] == 0 and
                evidence_behind(r)["in_lesson"] > 0),
        },
        "diagnostics": diagnostic_snapshot(attempts),
        "qualifications": {
            "states_the_evidence_does_not_support": unsupported(rows),
            "mastered_on_a_weak_transfer": weak_transfers(rows),
            "prerequisites_waved_through": bypasses(rows),
            "depth_targets_lowered": depth_given_up(course),
            "taught_then_never_retested": never_retested(rows, now),
        },
        "shaky": [r.get("concept_id") for r in rows
                  if r.get("state") == "shaky"],
        "due_now": rv.backlog_status(queue, 8, now)["due_now"],
    }

    if course.get("deadline"):
        report["pace"] = cur.drift(course, curriculum, rows, now.date())
    if course.get("milestones"):
        report["milestones"] = _milestones(course, now)
    return report


def _milestones(course: dict, now) -> list:
    out = []
    for m in course.get("milestones", []):
        date = _parse(str(m.get("date")) + "T00:00:00+00:00")
        out.append({
            "date": m.get("date"),
            "capability": m.get("capability"),
            "met": bool(m.get("met_at")),
            "days_away": round((date - now).total_seconds() / 86400.0)
            if date else None,
        })
    return out


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def render(r: dict) -> str:
    c = r["concepts"]
    lines = ["PROGRESS  " + str(r["course"]["title"])]
    lines.append("  goal: " + str(r["course"]["goal"]))
    lines.append("")
    lines.append("COVERED  " + str(c["touched"]) + " of " +
                 str(c["in_curriculum"]) + " concepts touched")
    for state in ("mastered", "consolidating", "practiced", "introduced",
                  "shaky"):
        if c["by_state"].get(state):
            lines.append("    " + state.ljust(14) +
                         str(c["by_state"][state]))

    e = r["evidence"]
    lines.append("")
    lines.append("WHAT THE STATES REST ON")
    lines.append("    mastered, on two pieces of delayed evidence: " +
                 str(e["mastered_on_two_delayed"]))
    lines.append("    resting on in-lesson work only: " +
                 str(e["resting_on_in_lesson_work_only"]) +
                 "   (says little about next week)")

    diagnostics = r["diagnostics"]
    lines.append("")
    lines.append("WHAT THE ANSWERS SHOW")
    if not diagnostics["concepts"]:
        lines.append("  no attributed attempts yet")
    for row in diagnostics["concepts"]:
        lines.append("  " + row["concept_id"] + "  " +
                     str(row.get("last_verdict")))
        for key, label in (("last_demonstrated", "shown"),
                           ("last_execution_issue", "execution to redo"),
                           ("last_concept_gap", "concept to revisit"),
                           ("last_observation", "observation")):
            if row.get(key):
                lines.append("    " + label + ": " + str(row[key]))
    if diagnostics["older_multi_concept_items_without_attribution"]:
        lines.append("  older multi-concept items without separable evidence: " +
                     str(diagnostics["older_multi_concept_items_without_attribution"]))
        lines.append("  concepts to review, not automatically change: " +
                     ", ".join(diagnostics["concepts_touched_by_unattributed_items"]))

    q = r["qualifications"]
    lines.append("")
    lines.append("QUALIFICATIONS")
    any_q = False
    if q["states_the_evidence_does_not_support"]:
        any_q = True
        lines.append("  ! states not supported by their evidence:")
        for row in q["states_the_evidence_does_not_support"]:
            lines.append("      " + row["concept_id"] + " is " + row["state"] +
                         " on " + str(row["delayed_evidence"]) +
                         " delayed pass(es), needs " + str(row["needs"]))
    if q["mastered_on_a_weak_transfer"]:
        any_q = True
        lines.append("  - mastered on a transfer test that barely moved:")
        for row in q["mastered_on_a_weak_transfer"]:
            lines.append("      " + row["concept_id"] + "  " +
                         (", ".join(row["dimensions"]) or
                          "no dimension recorded"))
    if q["prerequisites_waved_through"]:
        any_q = True
        lines.append("  - prerequisites waved through:")
        for row in q["prerequisites_waved_through"]:
            lines.append("      " + row["concept_id"] + "  x" +
                         str(row["times"]) +
                         ("  " + row["reason"] if row["reason"] else ""))
    if q["depth_targets_lowered"]:
        any_q = True
        lines.append("  - depth targets lowered:")
        for row in q["depth_targets_lowered"]:
            lines.append("      " + str(row.get("concept_id")) + "  " +
                         str(row.get("from_depth")) + " -> " +
                         str(row.get("to_depth")) + "  " +
                         str(row.get("reason", "")))
    if q["taught_then_never_retested"]:
        any_q = True
        lines.append("  - taught and never retested:")
        for row in q["taught_then_never_retested"]:
            lines.append("      " + row["concept_id"] + "  " +
                         str(row["days_since_taught"]) + " days ago")
    if not any_q:
        lines.append("  none")

    if r.get("pace"):
        lines.append("")
        lines.append("PACE  " + str(r["pace"].get("verdict")))
    if r.get("milestones"):
        lines.append("")
        lines.append("MILESTONES")
        for m in r["milestones"]:
            mark = "done" if m["met"] else (
                str(m["days_away"]) + "d away" if m["days_away"] is not None
                else "")
            lines.append("    " + str(m["date"]) + "  " + mark + "  " +
                         str(m["capability"]))

    lines.append("")
    lines.append("Computed from records only. No one's impression of how "
                 "sessions went is an input.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="progress_report.py",
        description="What actually happened, from the records only.")
    p.add_argument("--root")
    p.add_argument("--course", required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    root = Path(args.root) if args.root else zs.default_root()
    if not (root / "courses" / args.course / "course.json").exists():
        print("no such course: " + args.course, file=sys.stderr)
        return zs.EXIT_NOT_FOUND

    report = build(root, args.course)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json
          else render(report))
    return zs.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
