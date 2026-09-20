#!/usr/bin/env python3
"""One learning session: its size, its budget, and its brief.

Three jobs:

  - size the session to the energy actually declared, so a tired evening
    produces one concept and a review rather than a plan nobody can finish
  - print a BRIEF, not a dump. The brief is the whole point: it is the small
    bounded block a session opens with, instead of loading the learner model,
    the curriculum and every reference file into context
  - hold a turn budget, and refuse to keep going past it without a digest,
    so a long session stops quietly costing more and remembering less

Exit codes: 0 ok, 2 validation, 3 gate (environment setup missing),
4 budget reached, 5 not found.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import curriculum as cur
import learner as ln
import review as rv
import zt_state as zs

# See constants.py for where each of these came from and how much to trust it.
from constants import (  # noqa: E402
    ENERGY, TURN_BUDGET, CHECKPOINT_AT, HARD_STOP_AT, SESSION_MINUTES,
    MAX_NEW_CONCEPTS, FATIGUE_ERROR_RISE, FATIGUE_MIN_ATTEMPTS,
    REACH_RECHECK_DAYS,
)


def _utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt):
    return dt.replace(microsecond=0).isoformat()


def _root(args) -> Path:
    return Path(args.root) if args.root else zs.default_root()


def _config(root: Path) -> dict:
    p = root / "config.json"
    return zs.read_json(p) if p.exists() else {}


def _course(root: Path, slug: str):
    cdir = root / "courses" / slug
    cpath = cdir / "course.json"
    if not cpath.exists():
        raise FileNotFoundError("no such course: " + slug)
    curpath = cdir / "curriculum.json"
    return (cdir, zs.read_json(cpath),
            zs.read_json(curpath) if curpath.exists() else {"modules": []})


def new_concept_cap(profile: dict, energy: str) -> int:
    pacing = profile.get("pacing") or {}
    if energy == "low":
        return int(pacing.get("max_new_concepts_low_energy", 1))
    cap = int(pacing.get("max_new_concepts_per_session", MAX_NEW_CONCEPTS))
    return cap + 1 if energy == "high" else cap


def budget_for(config: dict, energy: str) -> dict:
    d = config.get("defaults") or {}
    scale = ENERGY.get(energy, ENERGY["normal"])
    budget = max(6, int(round(
        int(d.get("turn_budget", TURN_BUDGET)) * scale["budget"])))
    checkpoint_at = float(d.get("checkpoint_at", CHECKPOINT_AT))
    hard_stop_at = float(d.get("hard_stop_at", HARD_STOP_AT))
    return {
        "turn_budget": budget,
        "checkpoint_at": checkpoint_at,
        "hard_stop_at": hard_stop_at,
        "checkpoint_every": max(3, math.ceil(budget * checkpoint_at)),
        "hard_stop_turn": max(4, math.ceil(budget * hard_stop_at)),
    }


def checkpoints_owed(turns_used: int, every: int) -> int:
    return turns_used // every if every else 0


# --------------------------------------------------------------------------
# the brief
# --------------------------------------------------------------------------

def elapsed(root: Path, cdir: Path, rows: list, now) -> dict:
    """How long it has actually been, in days.

    Deliberately measured against the clock rather than against how many
    exchanges have happened. A conversation can run for forty turns inside
    one afternoon, or pick up after three weeks in one line; those two
    situations need completely different openings, and only the calendar can
    tell them apart. Everything that decays - what is due, what has gone
    shaky, whether the plan is behind - decays in days.

    The teaching timestamp is what makes this possible: every concept records
    when its lesson began, and every interval is measured from there.
    """
    sessions = cdir / "sessions"
    last_session = None
    if sessions.exists():
        stamps = []
        for d in sessions.iterdir():
            f = d / "session.json"
            if f.exists():
                doc = zs.read_json(f)
                stamps.append(doc.get("closed_at") or doc.get("opened_at"))
        stamps = [t for t in stamps if t]
        if stamps:
            last_session = max(stamps)

    taught = [r.get("last_review") or r.get("first_taught") for r in rows
              if r.get("first_taught")]
    last_taught = max(taught) if taught else None

    def days_since(stamp):
        if not stamp:
            return None
        try:
            then = datetime.fromisoformat(str(stamp))
        except ValueError:
            return None
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        return round((now - then).total_seconds() / 86400.0, 1)

    since_session = days_since(last_session)
    out = {"last_session_at": last_session,
           "days_since_last_session": since_session,
           "last_taught_at": last_taught,
           "days_since_anything_taught": days_since(last_taught)}

    # Say it in words, because the opening line should not read out a number.
    if since_session is None:
        out["say"] = "first session on this course"
    elif since_session < 1:
        out["say"] = "earlier today"
    elif since_session < 2:
        out["say"] = "yesterday"
    elif since_session < 14:            # layout, not a tunable
        out["say"] = str(int(since_session)) + " days ago"
    else:
        out["say"] = str(int(since_session // 7)) + " weeks ago"
        out["long_gap"] = True
    return out


def reach_staleness(root: Path, now) -> dict:
    """How old the check of what practice can act on is.

    A note at the start of a session, never a refusal. What is installed and
    what the learner can get hold of both change, but slowly, and blocking a
    lesson because a check is eight days old would be absurd. What the age is
    good for is knowing to re-check when an exercise fails in a way that
    looks like the environment rather than the learner.
    """
    p = root / "capabilities.json"
    if not p.exists():
        return {"checked": False,
                "say": "nothing has established what this course can "
                       "practise on yet"}
    stamp = zs.read_json(p).get("checked_at")
    when = zs._parse_dt(stamp) if stamp else None
    if not when:
        return {"checked": False, "say": ""}
    days = (now - when).total_seconds() / 86400.0
    out = {"checked": True, "days_old": round(days, 1),
           "stale": days > REACH_RECHECK_DAYS}
    out["say"] = ("what this course can practise on was last checked " +
                  str(int(days)) + " days ago") if out["stale"] else ""
    return out


def build_brief(root: Path, slug: str, energy: str, minutes=None,
                now=None) -> dict:
    now = now or _utcnow()
    config = _config(root)
    profile = ln.get_profile(root)
    cdir, course, curriculum = _course(root, slug)
    rows = ln.load_mastery(root)

    qpath = cdir / "review_queue.json"
    queue = zs.read_json(qpath) if qpath.exists() else {"items": []}
    defaults = config.get("defaults") or {}
    cap = int(defaults.get("review_cap_per_session",
                           ENERGY.get(energy, ENERGY["normal"])["reviews"]))
    if "review_cap_per_session" in defaults:
        cap = max(1, int(round(
            cap * ENERGY.get(energy, ENERGY["normal"])["budget"])))
    backlog = rv.backlog_status(queue, cap, now)
    due = rv.due_items(queue, now, backlog["take_this_session"])

    nxt = cur.next_lesson(curriculum, rows)
    d = cur.drift(course, curriculum, rows, now.date())
    register = ln.register_for(profile, course.get("domain", ""))
    bg = ln.background_for(profile, course.get("domain", ""))

    persona = dict(config.get("persona") or {})
    if ENERGY.get(energy, {}).get("banter") == 0:
        persona["banter"] = 0
        persona["banter_note"] = "suppressed: energy is low"

    b = budget_for(config, energy)
    planned_minutes = int(minutes or round(
        (profile.get("pacing") or {}).get("preferred_session_minutes",
                                          (config.get("defaults") or {})
                                          .get("session_minutes",
                                               SESSION_MINUTES)) *
        ENERGY.get(energy, ENERGY["normal"])["minutes"]))

    return {
        "course": {"slug": slug, "course_id": course.get("course_id"),
                   "title": course.get("title"),
                   "adapter_ref": course.get("adapter_ref"),
                   "domain": course.get("domain"),
                   "teaching_language": course.get("teaching_language") or
                   config.get("teaching_language"),
                   "source_anchored": bool(course.get("source_anchored"))},
        "persona": persona,
        "register": register,
        "background": bg,
        "energy": energy,
        "planned_minutes": planned_minutes,
        "new_concept_cap": (new_concept_cap(profile, energy)
                            if backlog["new_material_allowed"] else 0),
        "budget": b,
        "due_reviews": due,
        "due_total": backlog["due_now"],
        "backlog": backlog,
        "next_lesson": nxt,
        "drift": d,
        "elapsed": elapsed(root, cdir, rows, now),
        "reach": reach_staleness(root, now),
    }


def render_brief(brief: dict) -> str:
    """Compact on purpose. Everything here is something the next few turns
    will actually use; anything else is fetched when it is needed."""
    c = brief["course"]
    lines = []
    lines.append("COURSE  " + str(c["title"]) + "  [" +
                 str(c["adapter_ref"] or "no adapter yet") +
                 "]  language: " + str(c["teaching_language"]))

    # First line after the course, because it changes how to open. Measured
    # in days, never in how many exchanges happened last time.
    e = brief.get("elapsed") or {}
    gap = "LAST STUDIED  " + str(e.get("say"))
    if e.get("days_since_anything_taught") is not None:
        gap += "   (anything taught: " +             str(e["days_since_anything_taught"]) + "d ago)"
    lines.append(gap)
    reach = brief.get("reach") or {}
    if reach.get("say"):
        lines.append("REACH  " + reach["say"] +
                     "; re-check if an exercise fails in a way that looks "
                     "like the setup rather than the learner")
    if e.get("long_gap"):
        lines.append("  a long gap. Expect things to have faded; start by "
                     "finding out what survived, not by apologising for the "
                     "gap or by re-teaching from the top")
    r = brief["register"]
    reg_line = ("REGISTER  " + str(r.get("register")) + "  analogies<=" +
                str(r.get("max_analogies_per_concept")) + "  formalism " +
                str(r.get("formalism_tolerance")) + "/5")
    if brief.get("background"):
        reg_line += "  background: " + str(brief["background"].get("level"))
    lines.append(reg_line)
    p = brief["persona"]
    lines.append("ZEP  closeness " + str(p.get("closeness")) + "/5  banter " +
                 str(p.get("banter")) +
                 ("  (" + p["banter_note"] + ")" if p.get("banter_note") else ""))
    b = brief["budget"]
    lines.append("BUDGET  " + str(b["turn_budget"]) + " turns  checkpoint every "
                 + str(b["checkpoint_every"]) + "  hard stop " +
                 str(b["hard_stop_turn"]) + "  |  " +
                 str(brief["planned_minutes"]) + " min  new concepts <= " +
                 str(brief["new_concept_cap"]))

    lines.append("")
    if brief["due_reviews"]:
        extra = brief["due_total"] - len(brief["due_reviews"])
        head = "DUE FIRST (" + str(brief["due_total"]) + " total"
        head += (", showing " + str(len(brief["due_reviews"])) + ")"
                 if extra > 0 else ")")
        lines.append(head)
        for i in brief["due_reviews"]:
            line = "  " + i["concept_id"] + "  [" + i["kind"] + "]"
            if i.get("reason"):
                line += "  " + i["reason"]
            lines.append(line)
    else:
        lines.append("DUE FIRST  nothing")

    bl = brief.get("backlog") or {}
    if bl.get("band") in ("moderate", "severe"):
        lines.append("  BACKLOG  " + bl["band"] + ", " +
                     str(bl["sessions_of_debt"]) + " sessions of debt - " +
                     bl["advice"])

    lines.append("")
    n = brief["next_lesson"]
    if brief["new_concept_cap"] == 0 and n is not None:
        lines.append("NEXT  on hold while the backlog clears (" +
                     str(n["lesson_id"]) + " " + str(n["title"]) + ")")
        lines.append("PACE  " + str(brief["drift"]["verdict"]))
        return "\n".join(lines)
    if n is None:
        lines.append("NEXT  course complete")
    else:
        lines.append("NEXT  " + str(n["lesson_id"]) + "  " + str(n["title"]) +
                     "  (~" + str(n["estimated_minutes"]) + " min, " +
                     str(n["state"]) + ")")
        for blk in n["blockers"]:
            lines.append("  BLOCKED by " + blk["concept_id"] + " (" +
                         blk["reason"] + ", needed by " + blk["for"] + ")")

    d = brief["drift"]
    lines.append("PACE  " + str(d["verdict"]))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# session files
# --------------------------------------------------------------------------

def _sess_dir(cdir: Path, session_id: str) -> Path:
    return cdir / "sessions" / session_id


def _find_session(root: Path, session_id: str):
    for cdir in sorted((root / "courses").glob("*")):
        p = _sess_dir(cdir, session_id) / "session.json"
        if p.exists():
            return cdir, p
    raise FileNotFoundError("no such session: " + session_id)


def cmd_open(args) -> int:
    root = _root(args)
    cdir, course, _curriculum = _course(root, args.course)

    env = course.get("environment") or {}
    if not env.get("completed_at"):
        print("GATE FAILED: environment setup (stage 2) has not run for this "
              "course, so it cannot be taught yet", file=sys.stderr)
        return zs.EXIT_GATE

    now = _utcnow()
    brief = build_brief(root, args.course, args.energy, args.minutes, now)
    session_id = now.strftime("%Y%m%dT%H%M%S")
    b = brief["budget"]
    doc = {
        "schema_version": 1,
        "session_id": session_id,
        "course_id": course.get("course_id"),
        "started": _iso(now),
        "energy": args.energy,
        "planned_minutes": brief["planned_minutes"],
        "turn_budget": b["turn_budget"],
        "checkpoint_at": b["checkpoint_at"],
        "hard_stop_at": b["hard_stop_at"],
        "turns_used": 0,
        "checkpoints": [],
        "plan": {
            "review_items": [i["concept_id"] for i in brief["due_reviews"]],
            "new_concepts": [c["concept_id"] for c in
                             ((brief["next_lesson"] or {}).get("concepts")
                              or [])],
            "lesson_id": (brief["next_lesson"] or {}).get("lesson_id"),
            "exercise_tiers": ["anchored", "variant", "modeling"],
        },
    }
    dm = brief["drift"].get("drift_minutes_per_week")
    if dm is not None:
        doc["plan"]["progress_drift_minutes"] = dm

    errs = zs.validate_doc(doc, "session")
    if errs:
        for e in errs:
            print("[SCHEMA] " + e, file=sys.stderr)
        return zs.EXIT_VALIDATION

    sd = _sess_dir(cdir, session_id)
    zs.atomic_write_json(sd / "session.json", doc)
    zs.atomic_write_json(sd / "brief.json", brief)

    print("session " + session_id)
    print(render_brief(brief))
    return zs.EXIT_OK


def cmd_brief(args) -> int:
    root = _root(args)
    _cdir, p = _find_session(root, args.session)
    bp = p.parent / "brief.json"
    if not bp.exists():
        print("no brief stored for " + args.session, file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    brief = zs.read_json(bp)
    print(json.dumps(brief, ensure_ascii=False, indent=2) if args.json
          else render_brief(brief))
    return zs.EXIT_OK


def cmd_turn(args) -> int:
    root = _root(args)
    _cdir, p = _find_session(root, args.session)
    doc = zs.read_json(p)
    if doc.get("ended"):
        print("that session is already closed", file=sys.stderr)
        return zs.EXIT_GATE

    doc["turns_used"] = int(doc.get("turns_used", 0)) + int(args.count)
    zs.atomic_write_json(p, doc)

    budget = int(doc["turn_budget"])
    every = max(3, math.ceil(budget * float(doc["checkpoint_at"])))
    hard = max(4, math.ceil(
        budget * float(doc.get("hard_stop_at", HARD_STOP_AT))))
    used = doc["turns_used"]
    done = len(doc.get("checkpoints", []))

    print("turn " + str(used) + "/" + str(budget))
    if used >= hard:
        print("BUDGET REACHED. Close the session: write the digest, save what "
              "was learned, and stop. Carrying on costs more and remembers "
              "less.", file=sys.stderr)
        return zs.EXIT_BUDGET
    owed = checkpoints_owed(used, every)
    if done < owed:
        print("CHECKPOINT DUE. Write a digest of what has been established so "
              "far, save the notes, then run: session.py checkpoint --session "
              + args.session + " --digest <path>. After that the raw detail "
              "can be dropped from context.", file=sys.stderr)
        return zs.EXIT_BUDGET
    if used >= every and done >= owed:
        remaining = hard - used
        if remaining <= 3:
            print("note: " + str(remaining) + " turns before the hard stop")
    return zs.EXIT_OK


def cmd_checkpoint(args) -> int:
    root = _root(args)
    _cdir, p = _find_session(root, args.session)
    doc = zs.read_json(p)
    doc.setdefault("checkpoints", []).append({
        "at_turn": int(doc.get("turns_used", 0)),
        "digest_path": args.digest,
        "written_at": _iso(_utcnow()),
    })
    errs = zs.validate_doc(doc, "session")
    if errs:
        for e in errs:
            print("[SCHEMA] " + e, file=sys.stderr)
        return zs.EXIT_VALIDATION
    zs.atomic_write_json(p, doc)
    print("checkpoint recorded at turn " + str(doc.get("turns_used")) +
          "; raw detail up to here may now be dropped from context")
    return zs.EXIT_OK


def _fatigue(attempts: list) -> dict:
    """Error rate in the second half against the first. Not a diagnosis, just
    a signal that the session has stopped being productive."""
    graded = [a for a in attempts if a.get("verdict")]
    out = {"attempts_total": len(graded),
           "attempts_failed": sum(1 for a in graded
                                  if a.get("verdict") == "fail")}
    if len(graded) < FATIGUE_MIN_ATTEMPTS:
        out["fatigue_detected"] = False
        return out
    half = len(graded) // 2
    first, second = graded[:half], graded[half:]

    def rate(xs):
        bad = sum(1 for a in xs if a.get("verdict") in ("fail", "partial"))
        return round(bad / len(xs), 3) if xs else 0.0

    out["error_rate_first_half"] = rate(first)
    out["error_rate_second_half"] = rate(second)
    out["fatigue_detected"] = (out["error_rate_second_half"] >=
                               out["error_rate_first_half"] +
                               FATIGUE_ERROR_RISE)
    return out


def owed_at_close(attempts: list) -> list:
    """Concepts this session worked on and never had said back.

    Every concept taught owes one explain-back. The doctrine has said so
    since the mode router was written and nothing checked it, which made the
    one item every lesson owes the easiest thing in the system to skip, and
    skipping it left no trace at all.

    Reported rather than refused. A session can end for reasons that have
    nothing to do with the lesson, and refusing to close would strand records
    that are already good.
    """
    import exercise as ex
    touched = []
    for a in attempts:
        if a.get("form") == "explain_back":
            continue
        for c in a.get("concept_ids", []):
            if c not in touched:
                touched.append(c)
    return ex.owed_explain_backs(touched, attempts)


def cmd_close(args) -> int:
    root = _root(args)
    cdir, p = _find_session(root, args.session)
    doc = zs.read_json(p)
    now = _utcnow()
    doc["ended"] = _iso(now)
    started = zs._parse_dt(doc.get("started")) or now
    doc["actual_minutes"] = max(0, int((now - started).total_seconds() // 60))

    attempts = [a for a in zs.read_jsonl(cdir / "attempts.jsonl")
                if a.get("session_id") == args.session]
    fat = _fatigue(attempts)

    owed = owed_at_close(attempts)

    outcome = doc.setdefault("outcome", {})
    outcome["attempts"] = [a.get("attempt_id") for a in attempts]
    outcome["ended_reason"] = args.reason
    if args.digest:
        outcome["digest_path"] = args.digest
    concepts = []
    for a in attempts:
        for c in a.get("concept_ids", []):
            if c not in concepts:
                concepts.append(c)
    outcome["concepts_taught"] = concepts

    errs = zs.validate_doc(doc, "session")
    if errs:
        for e in errs:
            print("[SCHEMA] " + e, file=sys.stderr)
        return zs.EXIT_VALIDATION
    zs.atomic_write_json(p, doc)

    energy_row = {
        "schema_version": 1,
        "ts": _iso(now),
        "session_id": args.session,
        "course_id": doc.get("course_id"),
        "declared_energy": doc.get("energy"),
        "minutes_planned": doc.get("planned_minutes", 0),
        "minutes_actual": doc.get("actual_minutes", 0),
        "concepts_planned": len((doc.get("plan") or {}).get("new_concepts", [])),
        "concepts_done": len(concepts),
        "attempts_total": fat["attempts_total"],
        "attempts_failed": fat["attempts_failed"],
        "fatigue_detected": fat["fatigue_detected"],
        "ended_reason": args.reason,
    }
    for k in ("error_rate_first_half", "error_rate_second_half"):
        if k in fat:
            energy_row[k] = fat[k]
    errs = zs.validate_doc(energy_row, "energy")
    if errs:
        for e in errs:
            print("[SCHEMA] " + e, file=sys.stderr)
        return zs.EXIT_VALIDATION
    zs.append_jsonl(root / "learner" / "energy_log.jsonl", energy_row)

    print("closed " + args.session + " after " +
          str(doc["actual_minutes"]) + " min, " +
          str(doc.get("turns_used", 0)) + " turns, " +
          str(len(concepts)) + " concept(s) touched")
    if owed:
        print("")
        print("NOT SAID BACK: " + ", ".join(owed))
        print("  Every concept worked on owes one explain-back, and these "
              "did not get one. Saying it back unaided is the strongest "
              "single thing available here, and it is also the easiest step "
              "to skip because nothing fails when it is missed.")
        print("  Carry them into the next session rather than counting them "
              "as done.")
    if fat["fatigue_detected"]:
        print("the error rate climbed through this session; plan the next one "
              "smaller rather than treating this as a gap in understanding")
    return zs.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="session.py",
        description="Session sizing, the opening brief, and the turn budget.")
    p.add_argument("--root")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("open")
    sp.add_argument("--course", required=True)
    sp.add_argument("--energy", default="normal",
                    choices=["low", "normal", "high"])
    sp.add_argument("--minutes", type=int)
    sp.set_defaults(func=cmd_open)

    sp = sub.add_parser("brief")
    sp.add_argument("--session", required=True)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_brief)

    sp = sub.add_parser("turn")
    sp.add_argument("--session", required=True)
    sp.add_argument("--count", type=int, default=1)
    sp.set_defaults(func=cmd_turn)

    sp = sub.add_parser("checkpoint")
    sp.add_argument("--session", required=True)
    sp.add_argument("--digest", required=True)
    sp.set_defaults(func=cmd_checkpoint)

    sp = sub.add_parser("close")
    sp.add_argument("--session", required=True)
    sp.add_argument("--reason", default="completed",
                    choices=["completed", "budget_reached", "fatigue",
                             "learner_stopped", "blocked", "crashed"])
    sp.add_argument("--digest")
    sp.set_defaults(func=cmd_close)
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
