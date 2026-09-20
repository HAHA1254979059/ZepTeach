#!/usr/bin/env python3
"""The learner model: profile, per-domain register, and mastery records.

Two jobs that the teaching layer must not do for itself:

  - decide how to talk about a domain (the register), because the same person
    is terse-technical in one field and needs intuition first in another
  - decide whether the ground under a lesson is solid, by probing the
    prerequisites instead of assuming them

Output is deliberately small. Nothing here prints the whole learner model; it
prints the part that the thing about to happen actually needs.

Exit codes: 0 ok, 2 validation, 3 gate (prerequisites unproven or on hold),
5 not found.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import review as rv  # noqa: E402
import zt_state as zs  # noqa: E402
from constants import BYPASS_WARNING_COUNT  # noqa: E402

MASTERY_REL = "learner/mastery.jsonl"

# states we treat as proven ground for something built on top
PROVEN = ("consolidating", "mastered")


# --------------------------------------------------------------------------
# storage
# --------------------------------------------------------------------------

def load_mastery(root: Path) -> list:
    return zs.read_jsonl(root / "learner" / "mastery.jsonl")


def _strip(row: dict) -> dict:
    out = dict(row)
    out.pop("_transition_reason", None)
    return out


def save_mastery(root: Path, rows: list) -> list:
    """Validate everything, then rewrite atomically. Returns findings; writes
    nothing if any of them is an error."""
    known = zs.registry_ids(root)
    min_days = _min_days(root)
    findings = []
    cleaned = []
    for i, row in enumerate(rows, 1):
        row = _strip(row)
        cleaned.append(row)
        where = MASTERY_REL + ":" + str(i)
        for e in zs.validate_doc(row, "mastery"):
            findings.append(zs.Finding("SCHEMA", where, e))
        findings.extend(zs.rule_mastery(row, where, min_days, known))
    if any(f.severity == "error" for f in findings):
        return findings
    path = root / "learner" / "mastery.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in cleaned:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return findings


def _min_days(root: Path) -> dict:
    p = root / "config.json"
    if not p.exists():
        return {}
    try:
        return dict(zs.read_json(p).get("defaults") or {})
    except json.JSONDecodeError:
        return {}


def get_profile(root: Path) -> dict:
    p = root / "learner" / "profile.json"
    return zs.read_json(p) if p.exists() else {}


# --------------------------------------------------------------------------
# register: how to talk about this domain, to this person
# --------------------------------------------------------------------------

def register_for(profile: dict, domain: str) -> dict:
    """Most specific match wins; the entry named * is the fallback. A single
    global register is the root cause of explanations that are simultaneously
    too hand-wavy in one field and too dense in another."""
    entries = profile.get("registers", []) or []
    best = None
    best_len = -1
    for e in entries:
        d = e.get("domain", "")
        if d == "*":
            if best is None:
                best = e
            continue
        if domain == d or (domain or "").startswith(d + "/"):
            if len(d) > best_len:
                best, best_len = e, len(d)
    if best is None:
        best = {"domain": "*", "register": "technical_with_gloss"}
    out = dict(best)
    out.setdefault("max_analogies_per_concept", 1)
    out.setdefault("require_operational_definition", True)
    out.setdefault("formalism_tolerance", 3)
    return out


def background_for(profile: dict, domain: str):
    for e in profile.get("background", []) or []:
        d = e.get("domain", "")
        if domain == d or (domain or "").startswith(d + "/"):
            return e
    return None


# --------------------------------------------------------------------------
# prerequisites
# --------------------------------------------------------------------------

def _lesson(curriculum: dict, lesson_id: str):
    for mod in curriculum.get("modules", []):
        for les in mod.get("lessons", []):
            if les.get("lesson_id") == lesson_id:
                return les
    return None


def _by_concept(rows: list) -> dict:
    return dict((r.get("concept_id"), r) for r in rows)


def probe_plan(curriculum: dict, lesson_id: str, rows: list) -> dict:
    """What has to be checked or repaired before this lesson can run.

    unproven  - a prerequisite nobody has evidence for; ask 2-4 quick questions
    held      - a prerequisite that went shaky; dependents are held by default
    external  - background this course never taught; a sidequest candidate
    """
    les = _lesson(curriculum, lesson_id)
    if les is None:
        raise FileNotFoundError("no such lesson: " + lesson_id)
    by_id = _by_concept(rows)
    taught_here = set()
    for mod in curriculum.get("modules", []):
        for l2 in mod.get("lessons", []):
            for c in l2.get("concepts", []):
                taught_here.add(c.get("concept_id"))

    unproven, held, external = [], [], []
    for c in les.get("concepts", []):
        for p in c.get("prereq", []) or []:
            row = by_id.get(p)
            if row is None:
                unproven.append({"concept_id": p, "state": "unseen",
                                 "for": c.get("concept_id")})
                continue
            down = row.get("downstream") or {}
            if row.get("state") == "shaky" and not down.get("bypassed"):
                held.append({"concept_id": p, "state": "shaky",
                             "for": c.get("concept_id")})
            elif row.get("state") not in PROVEN:
                unproven.append({"concept_id": p, "state": row.get("state"),
                                 "for": c.get("concept_id")})
        for x in c.get("external_prereq", []) or []:
            external.append({"topic": x, "for": c.get("concept_id")})

    return {"lesson_id": lesson_id, "unproven": unproven, "held": held,
            "external": external,
            "blocking": bool(held),
            "taught_in_this_course": sorted(taught_here)}


# --------------------------------------------------------------------------
# recording an attempt
# --------------------------------------------------------------------------

def ensure_row(rows: list, concept_id: str, course_id: str,
               depth_target: int) -> dict:
    by_id = _by_concept(rows)
    row = by_id.get(concept_id)
    if row is None:
        row = {"schema_version": 1, "concept_id": concept_id,
               "courses": [course_id], "state": "unseen",
               "depth_targets": [{"course_id": course_id,
                                  "depth_target": depth_target}],
               "evidence": []}
        rows.append(row)
        return row
    if course_id not in row.get("courses", []):
        row.setdefault("courses", []).append(course_id)
    targets = row.setdefault("depth_targets", [])
    if not any(t.get("course_id") == course_id for t in targets):
        targets.append({"course_id": course_id,
                        "depth_target": depth_target})
    return row


def depth_target_in(curriculum: dict, concept_id: str, default=3) -> int:
    for mod in curriculum.get("modules", []):
        for les in mod.get("lessons", []):
            for c in les.get("concepts", []):
                if c.get("concept_id") == concept_id:
                    return c.get("depth_target", default)
    return default


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------

def _root(args) -> Path:
    return Path(args.root) if args.root else zs.default_root()


def _course(root: Path, slug: str):
    cdir = root / "courses" / slug
    cpath = cdir / "course.json"
    if not cpath.exists():
        raise FileNotFoundError("no such course: " + slug)
    curpath = cdir / "curriculum.json"
    return (cdir, zs.read_json(cpath),
            zs.read_json(curpath) if curpath.exists() else {"modules": []})


def cmd_show(args) -> int:
    root = _root(args)
    prof = get_profile(root)
    rows = load_mastery(root)
    counts = {}
    for r in rows:
        counts[r.get("state")] = counts.get(r.get("state"), 0) + 1
    out = {
        "learner": prof.get("display_name") or prof.get("learner_id"),
        "weekly_minutes": (prof.get("pacing") or {}).get("weekly_minutes"),
        "concepts_tracked": len(rows),
        "by_state": counts,
        "shaky": [r.get("concept_id") for r in rows
                  if r.get("state") == "shaky"],
    }
    if getattr(args, "brief", False):
        print(brief_line(root, rows))
        return zs.EXIT_OK
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return zs.EXIT_OK


def brief_line(root, rows=None) -> str:
    """One or two lines for the start of a session.

    Printed before anyone has said what they want to do, so it has to be
    short enough to be worth reading every time and specific enough to change
    what happens next. Counts of concepts are neither. What is overdue and
    what has gone shaky both change the opening move.

    Silent when there is nothing to say. A greeting that appears every
    session whether or not it carries information stops being read, and takes
    the sessions that do carry something with it.
    """
    import datetime
    rows = load_mastery(root) if rows is None else rows
    if not rows:
        return ""

    now = datetime.datetime.now(datetime.timezone.utc)
    due, shaky = 0, []
    for r in rows:
        if r.get("state") == "shaky":
            shaky.append(r.get("concept_id"))
        nxt = (r.get("scheduling") or {}).get("next_due")
        if nxt:
            try:
                when = datetime.datetime.fromisoformat(str(nxt))
            except ValueError:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=datetime.timezone.utc)
            if when <= now:
                due += 1

    bits = []
    if due:
        bits.append(str(due) + " due for review")
    if shaky:
        bits.append(str(len(shaky)) + " shaky (" + ", ".join(shaky[:3]) +
                    ("..." if len(shaky) > 3 else "") + ")")
    if not bits:
        return ""
    return "ZepTeach: " + "; ".join(bits)


def cmd_register(args) -> int:
    prof = get_profile(_root(args))
    reg = register_for(prof, args.domain)
    bg = background_for(prof, args.domain)
    if bg:
        reg["background_level"] = bg.get("level")
        reg["background_basis"] = bg.get("basis")
    print(json.dumps(reg, ensure_ascii=False, indent=2))
    return zs.EXIT_OK


def cmd_get(args) -> int:
    rows = load_mastery(_root(args))
    row = next((r for r in rows if r.get("concept_id") == args.concept), None)
    if row is None:
        print("no record for " + args.concept, file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    if args.full:
        print(json.dumps(row, ensure_ascii=False, indent=2))
        return zs.EXIT_OK
    sched = row.get("scheduling") or {}
    print(json.dumps({
        "concept_id": row.get("concept_id"),
        "state": row.get("state"),
        "courses": row.get("courses"),
        "depth_targets": row.get("depth_targets"),
        "depth_reached": row.get("depth_reached"),
        "next_kind": rv.next_kind(row.get("state", "unseen")),
        "next_due": sched.get("next_due"),
        "lapses": sched.get("lapses", 0),
        "evidence_count": len(row.get("evidence", [])),
    }, ensure_ascii=False, indent=2))
    return zs.EXIT_OK


def cmd_probe(args) -> int:
    root = _root(args)
    _, course, curriculum = _course(root, args.course)
    plan = probe_plan(curriculum, args.lesson, load_mastery(root))

    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        if plan["held"]:
            print("HELD - repair these before building on them:")
            for h in plan["held"]:
                print("  " + h["concept_id"] + " (needed by " + h["for"] + ")")
            print("  to carry on anyway: learner.py bypass --concept <id> "
                  "--reason <why>")
        if plan["unproven"]:
            print("UNPROVEN - probe with 2-4 quick questions before teaching:")
            for u in plan["unproven"]:
                print("  " + u["concept_id"] + " [" + str(u["state"]) +
                      "] (needed by " + u["for"] + ")")
        if plan["external"]:
            print("ASSUMED BACKGROUND - sidequest candidates:")
            for e in plan["external"]:
                print("  " + e["topic"] + " (for " + e["for"] + ")")
        if not (plan["held"] or plan["unproven"] or plan["external"]):
            print("ground is solid; nothing to probe")

    if plan["blocking"]:
        return zs.EXIT_GATE
    return zs.EXIT_OK


def cmd_teach(args) -> int:
    """Mark concepts as taught. This is a real event, not something inferred
    from the first exercise: every gap the review schedule measures is
    measured from here, so a lesson on Monday practised on Friday must not
    silently baseline itself to Friday."""
    root = _root(args)
    _cdir, course, curriculum = _course(root, args.course)
    les = _lesson(curriculum, args.lesson)
    if les is None:
        print("no such lesson: " + args.lesson, file=sys.stderr)
        return zs.EXIT_NOT_FOUND

    wanted = set(args.concepts.split(",")) if args.concepts else None
    when = args.at or rv._iso(rv._utcnow())
    rows = load_mastery(root)
    course_id = course.get("course_id")
    touched = []
    for c in les.get("concepts", []) or []:
        cid = c.get("concept_id")
        if wanted and cid not in wanted:
            continue
        row = ensure_row(rows, cid, course_id, c.get("depth_target", 3))
        state = row.get("state", "unseen")
        if state == "unseen":
            row["state"] = "introduced"
            row["first_taught"] = when
            touched.append((cid, "introduced"))
        else:
            row.setdefault("first_taught", when)
            touched.append((cid, "already " + state))
        row["updated"] = when

    findings = save_mastery(root, rows)
    if any(f.severity == "error" for f in findings):
        for f in findings:
            print(str(f), file=sys.stderr)
        return zs.EXIT_VALIDATION
    for cid, what in touched:
        print(cid + ": " + what)
    return zs.EXIT_OK


def cmd_record(args) -> int:
    root = _root(args)
    cdir, course, curriculum = _course(root, args.course)
    att = (json.loads(args.data) if args.data
           else json.loads(Path(args.file).read_text(encoding="utf-8")))

    known = zs.registry_ids(root)
    findings = [zs.Finding("SCHEMA", "attempt", e)
                for e in zs.validate_doc(att, "attempt")]
    findings.extend(zs.rule_attempt(att, "attempt"))
    if any(f.severity == "error" for f in findings):
        print("refusing to record: the attempt does not hold up",
              file=sys.stderr)
        for f in findings:
            print(str(f), file=sys.stderr)
        return zs.EXIT_VALIDATION

    rows = load_mastery(root)
    min_days = _min_days(root)
    course_id = course.get("course_id")

    by_id = _by_concept(rows)
    untaught = [c for c in att.get("concept_ids", [])
                if (by_id.get(c) or {}).get("state", "unseen") == "unseen"
                and att.get("kind") != "probe"]
    if untaught:
        print("GATE FAILED: no record of teaching " + ", ".join(untaught) +
              ". Run learner.py teach --course " + args.course +
              " --lesson <id> first, so the review schedule is measured from "
              "when it was actually taught.", file=sys.stderr)
        return zs.EXIT_GATE

    changed = []
    for cid in att.get("concept_ids", []):
        row = ensure_row(rows, cid, course_id,
                         depth_target_in(curriculum, cid))
        ev = {"attempt_id": att.get("attempt_id"), "course_id": course_id,
              "kind": att.get("kind"), "verdict": att.get("verdict"),
              "date": att.get("submitted_at")}
        if att.get("tier"):
            ev["tier"] = att["tier"]
        if att.get("latency_rating"):
            ev["latency_rating"] = att["latency_rating"]
            ev["latency_source"] = att.get("latency_source", "inferred")
        if att.get("graded_by"):
            ev["graded_by"] = att["graded_by"]
        before = row.get("state")
        updated = rv.apply_evidence(row, ev, min_days)

        # depth only counts when the answer was actually right
        shown = att.get("depth_demonstrated")
        if isinstance(shown, int) and att.get("verdict") == "pass":
            updated["depth_reached"] = max(
                int(updated.get("depth_reached") or 0), shown)

        rows[rows.index(row)] = updated
        changed.append({"concept_id": cid, "from": before,
                        "to": updated.get("state"),
                        "why": updated.get("_transition_reason"),
                        "depth_reached": updated.get("depth_reached"),
                        "next_due": (updated.get("scheduling") or {})
                        .get("next_due")})

    findings = save_mastery(root, rows)
    if any(f.severity == "error" for f in findings):
        print("refusing to record: the resulting learner model is invalid",
              file=sys.stderr)
        for f in findings:
            print(str(f), file=sys.stderr)
        return zs.EXIT_VALIDATION

    zs.append_jsonl(cdir / "attempts.jsonl", att)
    for c in changed:
        arrow = c["from"] + " -> " + c["to"] if c["from"] != c["to"] \
            else "stays " + str(c["to"])
        print(c["concept_id"] + ": " + arrow + " (" + str(c["why"]) + ")")
        line = "  next due " + str(c["next_due"])
        if c.get("depth_reached"):
            line += "   depth reached " + str(c["depth_reached"])
        print(line)
    for f in findings:
        print(str(f))
    return zs.EXIT_OK


def cmd_bypass(args) -> int:
    root = _root(args)
    rows = load_mastery(root)
    row = next((r for r in rows if r.get("concept_id") == args.concept), None)
    if row is None:
        print("no record for " + args.concept, file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    down = row.setdefault("downstream", {})
    down["bypassed"] = True
    down["bypassed_at"] = rv._iso(rv._utcnow())
    down["bypass_reason"] = args.reason
    down["bypass_count"] = int(down.get("bypass_count", 0)) + 1
    findings = save_mastery(root, rows)
    if any(f.severity == "error" for f in findings):
        for f in findings:
            print(str(f), file=sys.stderr)
        return zs.EXIT_VALIDATION
    print("carrying on past " + args.concept + " (bypass #" +
          str(down["bypass_count"]) + "): " + args.reason)
    if down["bypass_count"] >= BYPASS_WARNING_COUNT:
        print("that is the " + str(down["bypass_count"]) + "rd time this one "
              "has been waved through; it is worth fixing rather than "
              "stepping over again")
    return zs.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="learner.py",
        description="Learner profile, register selection and mastery records.")
    p.add_argument("--root")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("show")
    sp.add_argument("--brief", action="store_true",
                    help="one line for the start of a session, silent when "
                         "there is nothing worth saying")
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("register")
    sp.add_argument("--domain", required=True)
    sp.set_defaults(func=cmd_register)

    sp = sub.add_parser("get")
    sp.add_argument("--concept", required=True)
    sp.add_argument("--full", action="store_true")
    sp.set_defaults(func=cmd_get)

    sp = sub.add_parser("probe")
    sp.add_argument("--course", required=True)
    sp.add_argument("--lesson", required=True)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_probe)

    sp = sub.add_parser("teach")
    sp.add_argument("--course", required=True)
    sp.add_argument("--lesson", required=True)
    sp.add_argument("--concepts", help="comma separated subset of the lesson")
    sp.add_argument("--at", help="ISO timestamp, for testing")
    sp.set_defaults(func=cmd_teach)

    sp = sub.add_parser("record")
    sp.add_argument("--course", required=True)
    sp.add_argument("--file")
    sp.add_argument("--data")
    sp.set_defaults(func=cmd_record)

    sp = sub.add_parser("bypass")
    sp.add_argument("--concept", required=True)
    sp.add_argument("--reason", required=True)
    sp.set_defaults(func=cmd_bypass)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    except json.JSONDecodeError as exc:
        print("error: " + str(exc), file=sys.stderr)
        return zs.EXIT_VALIDATION


if __name__ == "__main__":
    sys.exit(main())
