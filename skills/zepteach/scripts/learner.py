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

import migrate as mg  # noqa: E402
import review as rv  # noqa: E402
import teaching as tp  # noqa: E402
import zt_state as zs  # noqa: E402
from constants import BYPASS_WARNING_COUNT  # noqa: E402
from sandbox import Refused  # noqa: E402

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


def load_expositions(root: Path) -> list:
    """Every explanation on file, from every course.

    Root-wide rather than per-course, for the same reason evidence is: a
    concept belongs to the learner, not to a course. Having had it explained
    in one course and then meeting it in another is the ordinary case, and
    demanding it be explained again there would be asking for a second
    delivery of something already delivered. What differs between courses is
    the register and the depth target, and those are handled where they
    belong.
    """
    out = []
    courses = root / "courses"
    if courses.exists():
        for cdir in sorted(courses.iterdir()):
            if cdir.is_dir():
                out.extend(zs.read_jsonl(cdir / "expositions.jsonl"))
    return out


def _items_on(cdir: Path, concept_id: str) -> list:
    """Every item issued on one concept.

    Read from disk rather than passed in, because the check it feeds - that
    an explanation exists somewhere other than inside the questions - is
    worth nothing if it can be satisfied by not mentioning the questions.
    """
    return [it for it in zs.read_jsonl(cdir / "exercises.jsonl")
            if concept_id in (it.get("concept_ids") or [])]


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
    """Record one concept actually being explained, and mark it taught.

    This used to take three strings and no content: a course, a lesson, and a
    list of concept ids. It flipped the state to `introduced` on the strength
    of being called. That made "I taught this" free to say, in a system where
    "they passed this" costs a quote from their answer, and the first real
    use went where the incentives pointed - the teaching went to nearly zero
    and every gate stayed green.

    So it now takes what was said, the same way marking takes the answer.
    See teaching.py for what the explanation has to contain.

    Every review interval is still measured from here, so a lesson on Monday
    practised on Friday must not baseline itself to Friday.
    """
    root = _root(args)
    cdir, course, curriculum = _course(root, args.course)

    expo = (json.loads(args.data) if args.data
            else json.loads(Path(args.file).read_text(encoding="utf-8")))

    errors = zs.validate_doc(expo, "exposition")
    if errors:
        for e in errors:
            print("invalid exposition: " + str(e), file=sys.stderr)
        return zs.EXIT_VALIDATION

    cid = expo.get("concept_id")
    if cid not in zs.registry_ids(root):
        print("no such concept in the registry: " + str(cid), file=sys.stderr)
        return zs.EXIT_NOT_FOUND

    lesson_id = expo.get("lesson_id") or args.lesson
    les = _lesson(curriculum, lesson_id) if lesson_id else None
    if lesson_id and les is None:
        print("no such lesson: " + str(lesson_id), file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    if les is not None:
        in_lesson = set(c.get("concept_id") for c in les.get("concepts") or [])
        if cid not in in_lesson:
            print("GATE FAILED: " + cid + " is not one of the concepts in "
                  "lesson " + str(lesson_id) + ". Either the wrong lesson is "
                  "named or this explanation belongs to a sidequest.",
                  file=sys.stderr)
            return zs.EXIT_GATE

    prompts = []
    for path in args.item or []:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if doc.get("prompt"):
            prompts.append(doc["prompt"])
    if not prompts:
        prompts = [it.get("prompt") for it in _items_on(cdir, cid)
                   if it.get("prompt")]

    reg = register_for(get_profile(root), course.get("domain"))
    try:
        checked = tp.check_exposition(
            expo, prompts,
            require_operational_definition=bool(
                reg.get("require_operational_definition", True)))
    except Refused as r:
        print("REFUSED [" + r.code + "]  " + r.message, file=sys.stderr)
        if r.suggestion:
            print("instead: " + r.suggestion, file=sys.stderr)
        return zs.EXIT_GATE

    when = expo.get("delivered_at") or args.at or rv._iso(rv._utcnow())
    expo.setdefault("delivered_at", when)
    zs.append_jsonl(cdir / "expositions.jsonl", expo)

    rows = load_mastery(root)
    course_id = course.get("course_id")
    depth = 3
    if les is not None:
        for c in les.get("concepts") or []:
            if c.get("concept_id") == cid:
                depth = c.get("depth_target", 3)
    row = ensure_row(rows, cid, course_id, depth)
    state = row.get("state", "unseen")
    if state == "unseen":
        row["state"] = "introduced"
        row["first_taught"] = when
        what = "introduced"
    else:
        row.setdefault("first_taught", when)
        what = "already " + state + ", explanation recorded"
    row["updated"] = when

    findings = save_mastery(root, rows)
    if any(f.severity == "error" for f in findings):
        for f in findings:
            print(str(f), file=sys.stderr)
        return zs.EXIT_VALIDATION

    print(cid + ": " + what)
    print("  rungs " + ", ".join(str(r) for r in checked["rungs_covered"]))
    if checked["note"]:
        print("  note: " + checked["note"])
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
    # Was this concept ever actually explained, before this answer was given?
    #
    # This used to ask the mastery state instead, which only recorded that a
    # command had been called. The command took no content, so the check
    # amounted to asking the teacher whether it had taught, and the answer was
    # always yes. It now asks the explanations on file, which have to contain
    # what was said and have to say it somewhere other than inside the
    # questions. A probe is still exempt: being asked something untaught is
    # what a probe is for.
    untaught = tp.untaught_in(load_expositions(root),
                              att.get("concept_ids", []),
                              att.get("submitted_at") or "",
                              att.get("kind"),
                              exempt=mg.grandfathered(root))
    if untaught:
        print("GATE FAILED: nothing on file explains " + ", ".join(untaught) +
              " from before this answer was given. Record the explanation "
              "with learner.py teach --course " + args.course +
              " --file <exposition.json> first. If the point was to let them "
              "try it untaught, this attempt is a probe and should say so.",
              file=sys.stderr)
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

    sp = sub.add_parser("teach", help="record one concept being explained")
    sp.add_argument("--course", required=True)
    sp.add_argument("--file", help="an exposition document")
    sp.add_argument("--data", help="the same document inline")
    sp.add_argument("--lesson", help="only when the document omits lesson_id")
    sp.add_argument("--item", action="append",
                    help="an item asked on this concept; repeatable. Usually "
                         "unnecessary - the items issued on it are read from "
                         "the course")
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
