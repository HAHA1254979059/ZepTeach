#!/usr/bin/env python3
"""Registered study material: what is in it, and what may be cited from it.

A course marked as anchored may not teach a lesson before the mapped part of
the material has been read. This file holds the index that makes "the mapped
part" a real address rather than a rough idea, and the check that stops a
lesson citing something nobody could read.

That second one is the part worth being strict about. A citation to a page
that came back unreadable looks exactly like a citation to a page that says
something else, and both read as authoritative. Extraction that fails loudly
is an inconvenience; extraction that fails quietly and then gets cited is how
a learner ends up with a confident reference to nothing.

This file does not extract anything itself. Converting a scan into text is a
separate job with its own tools, recorded per course in resources.json. What
happens here is indexing what came back, recording how much of it is usable,
and refusing the parts that are not.

Exit codes: 0 ok, 2 invalid data, 3 refused, 5 not found.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import zt_state as zs  # noqa: E402
from sandbox import Refused  # noqa: E402


def _now():
    return datetime.now(timezone.utc).isoformat()


def index_path(root: Path, slug: str) -> Path:
    return root / "courses" / slug / "sources" / "index.json"


def load(root: Path, slug: str, course_id: str = "") -> dict:
    p = index_path(root, slug)
    if p.exists():
        return zs.read_json(p)
    return {"schema_version": 1, "course_id": course_id, "sources": []}


def save(root: Path, slug: str, doc: dict) -> Path:
    doc["updated"] = _now()
    errs = zs.validate_doc(doc, "sources_index")
    if errs:
        raise Refused("SRC001", "; ".join(errs),
                      "the index does not match the stored shape")
    p = index_path(root, slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    zs.atomic_write_json(p, doc)
    return p


# ---------------------------------------------------------------------------
# registering
# ---------------------------------------------------------------------------

def register(doc: dict, source: dict) -> dict:
    """Add or replace one piece of material.

    The edition is asked for rather than inferred. A citation to section 6.1
    means nothing if the learner holds a different printing, and that failure
    is silent: both people see a plausible section number and neither finds
    out they were looking at different text.
    """
    source = dict(source)
    source.setdefault("index_status", "pending")

    if source.get("kind") in ("pdf_text", "pdf_scanned") and \
            not source.get("edition"):
        raise Refused(
            "SRC002",
            "no edition recorded for " + str(source.get("title")),
            "ask the learner which printing they have. Section and page "
            "numbers differ between editions, and a citation to the wrong "
            "one fails silently")

    rows = [s for s in doc.get("sources", [])
            if s.get("source_id") != source.get("source_id")]
    rows.append(source)
    doc["sources"] = rows
    return doc


def find(doc: dict, source_id: str) -> dict:
    for s in doc.get("sources", []):
        if s.get("source_id") == source_id:
            return s
    raise Refused("SRC005", "no such source: " + str(source_id),
                  "register it first")


# ---------------------------------------------------------------------------
# what may be cited
# ---------------------------------------------------------------------------

def _pages_in(ref: str) -> list:
    """Page numbers mentioned in a citation.

    Deliberately simple. It catches a single page and a range, which is what
    citations in practice contain. Anything it cannot parse is treated as
    naming no pages, which fails open for the reader and is checked again by
    the status rule below.
    """
    pages = []
    for match in re.finditer(r"(?:p\.?|pp\.?|page[s]?)\s*(\d+)(?:\s*[-–]"
                             r"\s*(\d+))?", str(ref), re.IGNORECASE):
        start = int(match.group(1))
        end = int(match.group(2) or start)
        pages.extend(range(start, end + 1))
    return pages


def check_citable(source: dict, ref: str) -> dict:
    """Refuse a citation into material that cannot support it."""
    status = source.get("index_status")
    if status in ("pending", "failed"):
        raise Refused(
            "SRC010",
            str(source.get("title")) + " has not been indexed (" +
            str(status) + "), so nothing in it has an address yet",
            "index it, or teach this lesson unanchored and mark it so")

    bad = set((source.get("ocr") or {}).get("pages_below_threshold") or [])
    asked = _pages_in(ref)
    overlap = sorted(set(asked) & bad)
    if overlap:
        raise Refused(
            "SRC011",
            "pages " + ", ".join(str(p) for p in overlap) + " of " +
            str(source.get("title")) + " could not be read reliably",
            "a citation to a page nobody could read is indistinguishable "
            "from a citation to a page that says something else. Get a "
            "better copy, have the learner read it and report back, or teach "
            "it unanchored")

    if status == "partial" and not asked:
        return {"citable": True, "caution":
                "this source is only partly indexed and the citation does "
                "not name pages, so nothing checked whether this part is "
                "readable"}

    return {"citable": True}


def unusable(source: dict) -> dict:
    """What is known not to be usable, for reporting before a lesson."""
    ocr = source.get("ocr") or {}
    pages = sorted(ocr.get("pages_below_threshold") or [])
    return {
        "source_id": source.get("source_id"),
        "title": source.get("title"),
        "index_status": source.get("index_status"),
        "unreadable_pages": pages,
        "mean_quality": ocr.get("mean_quality"),
        "say_to_learner": (
            "这本里有 " + str(len(pages)) + " 页没读清楚，讲到那几页时我会说，"
            "不会假装引用。" if pages else ""),
    }


# ---------------------------------------------------------------------------
# finding the span for a lesson
# ---------------------------------------------------------------------------

def span_for(doc: dict, lesson_span: dict) -> dict:
    """Resolve a lesson's mapped span into something readable.

    A lesson in an anchored course carries source_span. This turns it into
    the source plus the check on whether it may be cited, in one step, so a
    lesson cannot get the text and skip the check.
    """
    source = find(doc, lesson_span.get("source_id"))
    ref = lesson_span.get("section") or ""
    if lesson_span.get("page_start"):
        ref += " p." + str(lesson_span["page_start"])
        if lesson_span.get("page_end"):
            ref += "-" + str(lesson_span["page_end"])

    out = dict(check_citable(source, ref))
    out.update({
        "source_id": source.get("source_id"),
        "title": source.get("title"),
        "edition": source.get("edition"),
        "path": source.get("path"),
        "cite_as": (str(source.get("title")) + " " + ref).strip(),
        "page_offset": source.get("page_offset", 0),
    })
    return out


def toc_entries(source: dict) -> list:
    return list(source.get("toc") or [])


def problem_sets(source: dict) -> list:
    """Where anchored-tier items come from in this material.

    An anchored item needs a real problem somebody else set. Recording where
    those live is what makes the hardest tier possible without inventing
    difficulty.
    """
    return list(source.get("problem_sets") or [])


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def render(doc: dict) -> str:
    rows = doc.get("sources", [])
    lines = ["REGISTERED MATERIAL (" + str(len(rows)) + ")"]
    for s in rows:
        line = "  " + str(s.get("source_id")) + "  " + str(s.get("title"))
        if s.get("edition"):
            line += "  [" + s["edition"] + "]"
        line += "   " + str(s.get("index_status"))
        lines.append(line)
        u = unusable(s)
        if u["unreadable_pages"]:
            lines.append("      unreadable: " +
                         ", ".join(str(p) for p in u["unreadable_pages"]))
        if u["mean_quality"] is not None:
            lines.append("      extraction quality: " +
                         str(u["mean_quality"]))
        n = len(problem_sets(s))
        if n:
            lines.append("      problem sets recorded: " + str(n))
    if not rows:
        lines.append("  none; this course is not anchored to any material")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def _root(args) -> Path:
    return Path(args.root) if args.root else zs.default_root()


def _refuse(r: Refused) -> int:
    print("REFUSED [" + r.code + "]  " + r.message, file=sys.stderr)
    if r.suggestion:
        print("instead: " + r.suggestion, file=sys.stderr)
    return zs.EXIT_GATE


def cmd_show(args) -> int:
    root = _root(args)
    if not (root / "courses" / args.course).exists():
        print("no such course: " + args.course, file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    doc = load(root, args.course)
    print(json.dumps(doc, ensure_ascii=False, indent=2) if args.json
          else render(doc))
    return zs.EXIT_OK


def cmd_register(args) -> int:
    root = _root(args)
    cpath = root / "courses" / args.course / "course.json"
    if not cpath.exists():
        print("no such course: " + args.course, file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    doc = load(root, args.course, zs.read_json(cpath).get("course_id", ""))
    try:
        doc = register(doc, json.loads(args.data))
        path = save(root, args.course, doc)
    except Refused as r:
        return _refuse(r)
    print("written: " + str(path))
    return zs.EXIT_OK


def cmd_cite(args) -> int:
    root = _root(args)
    doc = load(root, args.course)
    try:
        source = find(doc, args.source)
        out = check_citable(source, args.ref)
    except Refused as r:
        return _refuse(r)
    if out.get("caution"):
        print("caution: " + out["caution"])
    print("citable: " + str(source.get("title")) + " " + args.ref)
    return zs.EXIT_OK


def cmd_unusable(args) -> int:
    root = _root(args)
    doc = load(root, args.course)
    rows = [unusable(s) for s in doc.get("sources", [])]
    rows = [r for r in rows if r["unreadable_pages"] or
            r["index_status"] in ("pending", "partial", "failed")]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return zs.EXIT_OK
    if not rows:
        print("everything registered is fully readable")
        return zs.EXIT_OK
    for r in rows:
        print(str(r["title"]) + "  " + str(r["index_status"]))
        if r["unreadable_pages"]:
            print("  unreadable pages: " +
                  ", ".join(str(p) for p in r["unreadable_pages"]))
        if r["say_to_learner"]:
            print("  say: " + r["say_to_learner"])
    return zs.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sources.py",
        description="Registered material, and what may be cited from it.")
    p.add_argument("--root")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("show")
    sp.add_argument("--course", required=True)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("register")
    sp.add_argument("--course", required=True)
    sp.add_argument("--data", required=True)
    sp.set_defaults(func=cmd_register)

    sp = sub.add_parser("cite", help="may this be cited")
    sp.add_argument("--course", required=True)
    sp.add_argument("--source", required=True)
    sp.add_argument("--ref", required=True)
    sp.set_defaults(func=cmd_cite)

    sp = sub.add_parser("unusable", help="what cannot be cited, and why")
    sp.add_argument("--course", required=True)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_unusable)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
