#!/usr/bin/env python3
"""Adaptive review scheduling.

The delayed retest exists to strengthen a memory, not to audit it. So the
interval is not a fixed ladder: it is computed from how this learner actually
recalled this concept, and the configured minimum gaps act only as a floor
that stops a same-afternoon redo counting as consolidation.

Two signals drive it:
  verdict  - pass / partial / fail
  latency  - instant / fluent / effortful / recovered_with_hint

Same correct answer, very different schedule. A fact recalled with visible
effort comes back within days; one recalled instantly drifts out.

Exit codes follow zt_state: 0 ok, 2 validation, 3 gate, 5 not found.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import zt_state as zs  # noqa: E402


# Every number below comes from constants.py, where each one declares
# whether it is backed by a study, copied from an established tool, an
# engineering decision, or a placeholder waiting to be calibrated from this
# learner's own logs. Run: python constants.py table
from constants import (  # noqa: E402
    GRADE_TABLE, DEFAULT_LATENCY, PASSING_GRADE,
    DEFAULT_EASE, MIN_EASE, MAX_EASE,
    FIRST_INTERVAL, SECOND_INTERVAL, GRADE_FACTOR, LATE_CREDIT,
    MAX_INTERVAL_DAYS, TARGET_RETENTION, RETIRE_AFTER_INSTANT,
    DEFAULT_REVIEW_CAP, BAND_MODERATE, BAND_SEVERE,
    DELAYED_RETEST_MIN_DAYS, TRANSFER_TEST_MIN_DAYS,
    REVIEW_SHARE_MANAGEABLE, REVIEW_SHARE_MODERATE,
    LAPSE_EASE_PENALTY,
)


def grade_of(verdict: str, latency: str = None) -> int:
    if verdict == "fail":
        return 0
    return GRADE_TABLE.get((verdict, latency or DEFAULT_LATENCY), 0)


# --------------------------------------------------------------------------
# what kind of test is owed next
# --------------------------------------------------------------------------

NEXT_KIND = {
    "unseen": "delayed_retest",
    "introduced": "delayed_retest",
    "practiced": "delayed_retest",
    "consolidating": "transfer_test",
    "mastered": "refresh",
    "shaky": "repair",
}

# floors measured from when the concept was first taught
FLOOR_KEY = {
    "delayed_retest": ("delayed_retest_min_days", DELAYED_RETEST_MIN_DAYS),
    "transfer_test": ("transfer_test_min_days", TRANSFER_TEST_MIN_DAYS),
}


def next_kind(state: str) -> str:
    return NEXT_KIND.get(state, "delayed_retest")


def floor_days(kind: str, min_days: dict) -> int:
    key, default = FLOOR_KEY.get(kind, (None, 0))
    if key is None:
        return 0
    return int((min_days or {}).get(key, default))


# --------------------------------------------------------------------------
# SM-2 style interval update
# --------------------------------------------------------------------------

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def update_scheduling(sched: dict, grade: int, algorithm: str = "sm2",
                      days_late: float = 0.0) -> dict:
    """Return a new scheduling block. Pure function: easy to test, easy to
    audit, and it never looks at anything except the numbers handed to it.

    days_late is how far past the due date the review actually happened. A
    late recall that still succeeded says the interval was too short, so some
    of that lateness is credited back into the base before it grows."""
    if algorithm == "fsrs":
        raise NotImplementedError(
            "fsrs is reserved but not implemented; use sm2 or fixed")

    out = dict(sched or {})
    out["algorithm"] = algorithm
    ease = float(out.get("ease", DEFAULT_EASE))
    reps = int(out.get("reps", 0))
    interval = float(out.get("interval_days", 0))
    lapses = int(out.get("lapses", 0))
    if grade >= PASSING_GRADE and days_late > 0:
        interval += max(0.0, days_late) * LATE_CREDIT.get(grade, 0.0)

    if algorithm == "fixed":
        out["interval_days"] = 1 if grade < PASSING_GRADE else max(1.0, interval or 1.0)
        out["reps"] = 0 if grade < PASSING_GRADE else reps + 1
        out["lapses"] = lapses + (1 if grade < PASSING_GRADE else 0)
        out["ease"] = ease
        return out

    if grade < PASSING_GRADE:
        # a lapse: back to the start of the ladder, and the concept is now
        # marked as harder for this learner than it looked
        out["reps"] = 0
        out["lapses"] = lapses + 1
        out["interval_days"] = 1.0
        out["ease"] = _clamp(ease - LAPSE_EASE_PENALTY,
                             MIN_EASE, MAX_EASE)
    else:
        if reps == 0:
            interval = FIRST_INTERVAL[grade]
        elif reps == 1:
            interval = SECOND_INTERVAL[grade]
        else:
            interval = round(min(interval * ease * GRADE_FACTOR[grade],
                                 MAX_INTERVAL_DAYS), 1)
        out["reps"] = reps + 1
        out["interval_days"] = interval
        delta = 0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02)
        out["ease"] = _clamp(ease + delta, MIN_EASE, MAX_EASE)
        out["lapses"] = lapses

    # difficulty is just the ease read the other way round, kept so that a
    # progress report can say which concepts fight back without exposing
    # the algorithm internals
    out["difficulty"] = round(
        _clamp((MAX_EASE - out["ease"]) / (MAX_EASE - MIN_EASE), 0.0, 1.0), 3)
    return out


def compute_next_due(state: str, sched: dict, first_taught, now,
                     min_days: dict) -> datetime:
    """Interval from the recall history, then pushed out to the floor if the
    next thing owed is a delayed retest or a transfer test."""
    interval = float((sched or {}).get("interval_days", 1) or 1)
    due = now + timedelta(days=interval)
    kind = next_kind(state)
    floor = floor_days(kind, min_days)
    if floor and first_taught:
        due = max(due, first_taught + timedelta(days=floor))
    return due


# --------------------------------------------------------------------------
# state transitions driven by evidence
# --------------------------------------------------------------------------

def _gap_ok(kind: str, first_taught, when, min_days: dict) -> bool:
    floor = floor_days(kind, min_days)
    if not floor:
        return True
    if not first_taught or not when:
        return False
    return (when - first_taught).days >= floor


def next_state(current: str, kind: str, verdict: str, first_taught, when,
               min_days: dict, latency: str = None):
    """Return (new_state, reason). Promotion is never granted for effort or
    enthusiasm; it is granted for a specific kind of evidence arriving after
    a specific gap, recalled cleanly.

    Hints are part of teaching, so one during a lesson does not block reaching
    practiced. On a retest a hint means the thing did not come back on its
    own, which is exactly what a retest is asking, so it does not promote."""
    current = current or "unseen"

    if kind == "probe":
        return current, "a prerequisite probe does not move the state"

    if verdict == "fail":
        if current in ("practiced", "consolidating", "mastered"):
            return "shaky", "a due retest was failed"
        return current, "failed, but the state was already below practiced"

    if verdict == "partial":
        if current in ("consolidating", "mastered") and \
                kind in ("delayed_retest", "transfer_test", "assessment"):
            return "shaky", "only partly recalled on a due retest"
        return current, "partial answers do not promote"

    # verdict == pass
    if kind in ("inclass", "assessment"):
        if current in ("unseen", "introduced", "shaky"):
            return "practiced", "solved it in the session"
        return current, "in-session success cannot advance past practiced"

    clean_recall = grade_of(verdict, latency) >= PASSING_GRADE

    if kind == "delayed_retest":
        if current in ("practiced", "shaky"):
            if not _gap_ok(kind, first_taught, when, min_days):
                return current, ("recalled too soon after first being "
                                 "taught to count as consolidation")
            if not clean_recall:
                return current, ("it came back only with a hint, which is "
                                 "the opposite of what a retest checks")
            return "consolidating", "recalled after a real gap"
        return current, "a delayed retest does not apply from this state"

    if kind == "transfer_test":
        if current == "consolidating":
            if not _gap_ok(kind, first_taught, when, min_days):
                return current, "transfer test came too soon to count"
            if not clean_recall:
                return current, "needed a hint, so it has not transferred"
            return "mastered", "used it in new ground"
        return current, "a transfer test only advances from consolidating"

    return current, "no rule matched"


# --------------------------------------------------------------------------
# applying one piece of evidence to a mastery record
# --------------------------------------------------------------------------

def apply_evidence(mastery: dict, evidence: dict, min_days: dict,
                   now=None) -> dict:
    """Return an updated mastery record. Does not write anything."""
    m = json.loads(json.dumps(mastery))
    when = zs._parse_dt(evidence.get("date")) or now or _utcnow()
    now = now or when
    first = zs._parse_dt(m.get("first_taught")) or when

    m.setdefault("evidence", []).append(evidence)
    if not m.get("first_taught"):
        m["first_taught"] = _iso(first)

    old = m.get("state", "unseen")
    new, reason = next_state(old, evidence.get("kind"),
                             evidence.get("verdict"), first, when, min_days,
                             evidence.get("latency_rating"))
    if new != old and not zs.can_transition(old, new):
        new, reason = old, ("refused an illegal transition " + old +
                            " -> " + new)
    m["state"] = new
    m["_transition_reason"] = reason

    grade = grade_of(evidence.get("verdict"),
                     evidence.get("latency_rating"))
    prev = m.get("scheduling") or {}
    prev_due = zs._parse_dt(prev.get("next_due"))
    days_late = max((when - prev_due).total_seconds() / 86400.0, 0.0) \
        if prev_due else 0.0
    m["scheduling"] = update_scheduling(
        prev, grade, prev.get("algorithm", "sm2"), days_late)
    m["scheduling"]["last_review"] = _iso(when)
    m["scheduling"]["next_due"] = _iso(
        compute_next_due(new, m["scheduling"], first, when, min_days))

    # Retirement: something recalled instantly several times running is being
    # used, not maintained. It leaves the queue, and any answer that is not
    # another instant pass puts it straight back.
    if should_retire(m):
        m["scheduling"]["retired"] = True
        m["scheduling"]["retired_at"] = _iso(when)
    elif prev.get("retired"):
        m["scheduling"].pop("retired", None)
        m["scheduling"].pop("retired_at", None)

    down = m.setdefault("downstream", {})
    if new == "shaky":
        down["hold"] = True
    elif old == "shaky" and new != "shaky":
        down["hold"] = False

    m["updated"] = _iso(now)
    return m


def _utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


# --------------------------------------------------------------------------
# the queue
# --------------------------------------------------------------------------

def _downstream_map(curriculum: dict) -> dict:
    """concept -> concepts that list it as a prerequisite."""
    out = {}
    for mod in (curriculum or {}).get("modules", []):
        for les in mod.get("lessons", []):
            for c in les.get("concepts", []):
                for p in c.get("prereq", []) or []:
                    out.setdefault(p, []).append(c.get("concept_id"))
    return out


def retrievability(elapsed_days: float, interval_days: float) -> float:
    """Roughly, the chance the thing is still there. At exactly the scheduled
    interval this is the target retention; past it, it decays.

    This is the ordering key for a backlog, and it is deliberately NOT the
    same as "most overdue first". Simulation work in the spaced-repetition
    community found due-date-ascending to be one of the worst orders to clear
    a backlog with: something already forgotten has to be relearned either
    way, and a few more days costs it little, while something still barely
    held is saved cheaply right now. So the queue takes the ones most likely
    to survive first."""
    interval_days = max(float(interval_days or 1.0), 0.1)
    elapsed_days = max(float(elapsed_days or 0.0), 0.0)
    return float(_clamp(TARGET_RETENTION ** (elapsed_days / interval_days),
                        0.0, 1.0))


def priority_of(item_kind: str, retriev: float, blocks: int) -> int:
    """Blocking comes first, because a shaky concept holding up a lesson is a
    progress problem, not just a memory one. Everything else is ordered by
    how likely it still is to be remembered, highest first."""
    base = {"repair": 60, "transfer_test": 30, "delayed_retest": 28,
            "refresh": 12}.get(item_kind, 20)
    return int(_clamp(base + min(blocks, 5) * 5 + retriev * 10, 0, 100))


def trailing_instant_passes(evidence: list) -> int:
    """How many recalls in a row came back instantly. The streak breaks on
    anything less, which is what makes retirement safe to reverse."""
    n = 0
    for e in reversed(evidence or []):
        if e.get("kind") == "probe":
            continue
        if e.get("verdict") == "pass" and e.get("latency_rating") == "instant":
            n += 1
        else:
            break
    return n


def should_retire(mastery: dict, threshold: int = RETIRE_AFTER_INSTANT) -> bool:
    """A mastered concept that keeps coming back instantly is one the learner
    is using, not one they are maintaining. It leaves the queue and comes
    back only if it shows up wrong somewhere else."""
    return (mastery.get("state") == "mastered" and
            trailing_instant_passes(mastery.get("evidence")) >= threshold)


def build_queue(course_id: str, mastery_rows: list, curriculum: dict,
                min_days: dict, now=None) -> dict:
    now = now or _utcnow()
    downstream = _downstream_map(curriculum)
    items = []
    for m in mastery_rows:
        if course_id not in (m.get("courses") or []):
            continue
        state = m.get("state", "unseen")
        if state == "unseen":
            continue
        sched = m.get("scheduling") or {}
        if sched.get("retired"):
            continue
        kind = next_kind(state)
        due = zs._parse_dt(sched.get("next_due"))
        if due is None:
            first = zs._parse_dt(m.get("first_taught")) or now
            due = compute_next_due(state, sched, first, now, min_days)
        last = zs._parse_dt(sched.get("last_review")) or \
            zs._parse_dt(m.get("first_taught")) or due
        elapsed = max((now - last).total_seconds() / 86400.0, 0.0)
        retriev = retrievability(elapsed, sched.get("interval_days") or 1.0)
        blocks = downstream.get(m.get("concept_id"), [])
        item = {
            "concept_id": m.get("concept_id"),
            "due": _iso(due),
            "kind": kind,
            "priority": priority_of(kind, retriev, len(blocks)),
        }
        if blocks:
            item["blocks"] = blocks
        lapses = sched.get("lapses")
        if isinstance(lapses, int) and lapses:
            item["reason"] = ("slipped " + str(lapses) +
                              " time(s) before; coming back sooner")
        items.append(item)
    items.sort(key=lambda i: (-i["priority"], i["due"]))
    return {"schema_version": 1, "course_id": course_id,
            "updated": _iso(now), "items": items}


# --------------------------------------------------------------------------
# backlog
# --------------------------------------------------------------------------

def backlog_status(queue: dict, cap: int = DEFAULT_REVIEW_CAP,
                   now=None) -> dict:
    """Three bands, and what each one does to the session.

    The point of banding rather than just draining the queue is that the
    documented failure mode of spaced repetition is not forgetting, it is
    abandonment: a wall of overdue items becomes a reason to stop. Measured
    against that, lateness itself is cheap - one long-running analysis of
    real review logs put the extra forgetting from reviewing late at around
    one percentage point. So the debt is worked off at a steady rate rather
    than cleared in one heroic sitting, and it is never silently rescheduled
    away, because that hides the signal and loses real progress.
    """
    now = now or _utcnow()
    due = due_items(queue, now)
    cap = max(1, int(cap))
    sessions = len(due) / float(cap)
    if sessions <= BAND_MODERATE:
        band, new_ok, share = "manageable", True, REVIEW_SHARE_MANAGEABLE
        advice = "normal mix; reviews first, then new material"
    elif sessions <= BAND_SEVERE:
        band, new_ok, share = "moderate", True, REVIEW_SHARE_MODERATE
        advice = ("lean on review this session, but still teach one new "
                  "thing so the course keeps moving")
    else:
        band, new_ok, share = "severe", False, 1.0
        advice = ("pause new material until the backlog is back under " +
                  str(int(BAND_SEVERE * cap)) + " items; say so plainly and "
                  "do not reschedule the debt away")
    return {"due_now": len(due), "per_session_cap": cap,
            "sessions_of_debt": round(sessions, 1), "band": band,
            "new_material_allowed": new_ok, "review_share": share,
            "take_this_session": min(len(due), cap),
            "advice": advice}


def due_items(queue: dict, now=None, limit=None) -> list:
    now = now or _utcnow()
    out = [i for i in queue.get("items", [])
           if (zs._parse_dt(i.get("due")) or now) <= now]
    return out[:limit] if limit else out


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------

def _root(args) -> Path:
    return Path(args.root) if args.root else zs.default_root()


def _min_days(root: Path) -> dict:
    p = root / "config.json"
    if not p.exists():
        return {}
    try:
        return dict(zs.read_json(p).get("defaults") or {})
    except json.JSONDecodeError:
        return {}


def _now(args):
    return zs._parse_dt(args.now) if getattr(args, "now", None) else _utcnow()


def _course_dir(root: Path, slug: str) -> Path:
    return root / "courses" / slug


def cmd_rebuild(args) -> int:
    root = _root(args)
    cdir = _course_dir(root, args.course)
    cpath = cdir / "course.json"
    if not cpath.exists():
        print("no such course: " + args.course, file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    course_id = zs.read_json(cpath).get("course_id")
    curpath = cdir / "curriculum.json"
    curriculum = zs.read_json(curpath) if curpath.exists() else {}
    rows = zs.read_jsonl(root / "learner" / "mastery.jsonl")
    queue = build_queue(course_id, rows, curriculum, _min_days(root),
                        _now(args))
    errs = zs.validate_doc(queue, "review_queue")
    if errs:
        for e in errs:
            print("[SCHEMA] " + e, file=sys.stderr)
        return zs.EXIT_VALIDATION
    zs.atomic_write_json(cdir / "review_queue.json", queue)
    print("queue rebuilt: " + str(len(queue["items"])) + " tracked, " +
          str(len(due_items(queue, _now(args)))) + " due now")
    return zs.EXIT_OK


def cmd_due(args) -> int:
    root = _root(args)
    qpath = _course_dir(root, args.course) / "review_queue.json"
    if not qpath.exists():
        print("no queue yet; run rebuild", file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    now = _now(args)
    items = due_items(zs.read_json(qpath), now, args.limit)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return zs.EXIT_OK
    if not items:
        print("nothing due")
        return zs.EXIT_OK
    # deliberately terse: this goes into a live session, not a report
    for i in items:
        due = zs._parse_dt(i["due"])
        late = (now - due).days if due else 0
        tag = ("  overdue " + str(late) + "d") if late > 0 else ""
        print("- " + i["concept_id"] + "  [" + i["kind"] + "]" + tag)
    return zs.EXIT_OK


def cmd_plan(args) -> int:
    root = _root(args)
    rows = zs.read_jsonl(root / "learner" / "mastery.jsonl")
    row = next((r for r in rows if r.get("concept_id") == args.concept), None)
    if row is None:
        print("no mastery record for " + args.concept, file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    md = _min_days(root)
    state = row.get("state", "unseen")
    sched = row.get("scheduling") or {}
    first = zs._parse_dt(row.get("first_taught"))
    due = zs._parse_dt(sched.get("next_due")) or compute_next_due(
        state, sched, first, _now(args), md)
    print(json.dumps({
        "concept_id": args.concept,
        "state": state,
        "next_kind": next_kind(state),
        "next_due": _iso(due),
        "interval_days": sched.get("interval_days"),
        "ease": sched.get("ease"),
        "difficulty": sched.get("difficulty"),
        "lapses": sched.get("lapses", 0),
        "floor_days": floor_days(next_kind(state), md),
    }, ensure_ascii=False, indent=2))
    return zs.EXIT_OK


def cmd_simulate(args) -> int:
    """Show what a given outcome would do to the schedule, without writing.
    Used to review the algorithm rather than trust it."""
    sched = {"ease": args.ease, "reps": args.reps,
             "interval_days": args.interval, "lapses": 0}
    g = grade_of(args.verdict, args.latency)
    out = update_scheduling(sched, g)
    print(json.dumps({"grade": g, "scheduling": out},
                     ensure_ascii=False, indent=2))
    return zs.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="review.py",
        description="Adaptive review scheduling and the due queue.")
    p.add_argument("--root")
    p.add_argument("--now", help="ISO timestamp, for testing")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("rebuild")
    sp.add_argument("--course", required=True)
    sp.set_defaults(func=cmd_rebuild)

    sp = sub.add_parser("due")
    sp.add_argument("--course", required=True)
    sp.add_argument("--limit", type=int)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_due)

    sp = sub.add_parser("plan")
    sp.add_argument("--concept", required=True)
    sp.set_defaults(func=cmd_plan)

    sp = sub.add_parser("simulate")
    sp.add_argument("--verdict", required=True,
                    choices=["pass", "partial", "fail"])
    sp.add_argument("--latency",
                    choices=["instant", "fluent", "effortful",
                             "recovered_with_hint"])
    sp.add_argument("--ease", type=float, default=DEFAULT_EASE)
    sp.add_argument("--reps", type=int, default=2)
    sp.add_argument("--interval", type=float, default=6.0)
    sp.set_defaults(func=cmd_simulate)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError, NotImplementedError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return zs.EXIT_VALIDATION


if __name__ == "__main__":
    sys.exit(main())
