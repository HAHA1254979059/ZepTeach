#!/usr/bin/env python3
"""What this course has to work with, and how to use it.

Written once the learner has said what they have, and kept with the course.
Two kinds of entry: the material they supplied to study from, and the tools
their environment offers.

Nothing here is assumed. An entry exists because the learner said so or
because a check found it, never because a subject usually involves one. That
is the same rule that keeps a list of disciplines out of the core, applied to
equipment instead.

The part worth the trouble is not the list of tool names. It is how to use
each one: which setting matters, what the output means, what it cannot do.
That knowledge would otherwise be reconstructed in every lesson, badly. Once
recorded, a tool with a real procedure can be wired up as a project-level
skill, an MCP server, a plugin or a command, so it is set up once rather than
re-explained.

Exit codes: 0 ok, 2 invalid data, 3 refused, 5 course not found.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sandbox as sb  # noqa: E402
import zt_state as zs  # noqa: E402


def _now():
    return datetime.now(timezone.utc).isoformat()


def path_for(root: Path, slug: str) -> Path:
    return root / "courses" / slug / "resources.json"


def load(root: Path, slug: str) -> dict:
    p = path_for(root, slug)
    if p.exists():
        return zs.read_json(p)
    course = root / "courses" / slug / "course.json"
    cid = zs.read_json(course).get("course_id") if course.exists() else slug
    return {"schema_version": 1, "course_id": cid, "updated": _now()}


# ---------------------------------------------------------------------------
# adding things
# ---------------------------------------------------------------------------

def add_material(doc: dict, entry: dict) -> dict:
    """Record something to study from.

    The edition field earns its place: a lesson that cites section 6.1 is
    citing nothing if the learner's printing numbers its sections
    differently, and that failure is quiet.
    """
    entry = dict(entry)
    entry.setdefault("added", _now())
    rows = [m for m in doc.get("materials", [])
            if m.get("material_id") != entry.get("material_id")]
    rows.append(entry)
    doc["materials"] = rows
    doc["updated"] = _now()
    return doc


def add_tool(doc: dict, entry: dict) -> dict:
    """Record a tool and, more importantly, how to use it.

    A tool the learner operates themselves is a proper entry. Most useful
    tools are not things this plugin runs, and an entry with no invocation
    block is the common case rather than an incomplete one.
    """
    entry = dict(entry)
    entry.setdefault("added_by", "learner")

    for field in ("what_it_does", "how_to_use", "limits", "reached_how"):
        if entry.get(field):
            sb.check_no_secret(entry[field], "the tool's " + field)

    inv = entry.get("invocation")
    if inv:
        for field in ("credentials_env", "credentials_file"):
            if inv.get(field):
                sb.check_no_secret(inv[field], "invocation." + field)
        allow = inv.get("allowed_paths") or []
        if inv.get("workdir"):
            sb.check_path(inv["workdir"], allow, purpose="work in")
        if not inv.get("timeout_seconds"):
            raise sb.Refused(
                "RES001",
                "the tool " + str(entry.get("tool_id")) + " is set up to be "
                "run by this plugin but has no time limit",
                "give one. Something that hangs otherwise waits for as long "
                "as the learner is willing to sit there")

    rows = [t for t in doc.get("tools", [])
            if t.get("tool_id") != entry.get("tool_id")]
    rows.append(entry)
    doc["tools"] = rows
    doc["updated"] = _now()
    return doc


def add_integration(doc: dict, entry: dict) -> dict:
    """Record wiring set up for a tool.

    Three things are checked, because each corresponds to a way this goes
    wrong later. The tools must exist, or the wiring refers to nothing. The
    learner must have seen it, because it is written into their project and
    not this plugin's data. And it must say what it saves, because an
    integration that saves nothing is clutter somebody still has to maintain.
    """
    entry = dict(entry)
    entry.setdefault("generated_at", _now())

    known = {t.get("tool_id") for t in doc.get("tools", [])}
    unknown = [t for t in entry.get("for_tools", []) if t not in known]
    if unknown:
        raise sb.Refused(
            "RES002",
            "this wiring names tools that are not recorded: " +
            ", ".join(unknown),
            "record the tool first, including how to use it; the wiring is "
            "supposed to capture that, so there is nothing to capture yet")

    if not entry.get("confirmed_by_learner"):
        raise sb.Refused(
            "RES003",
            "this would be written into the learner's project at " +
            str(entry.get("path")) + " without them having seen it",
            "show them what it does and where it goes, then record that they "
            "agreed")

    if not entry.get("why"):
        raise sb.Refused(
            "RES004",
            "this wiring does not say what it saves",
            "if that is hard to answer, do not build it. A tool used twice "
            "needs a sentence in how_to_use, not an integration")

    rows = [i for i in doc.get("integrations", [])
            if i.get("integration_id") != entry.get("integration_id")]
    rows.append(entry)
    doc["integrations"] = rows
    doc["updated"] = _now()
    return doc


def decline(doc: dict, what: str, reason: str = "") -> dict:
    """Remember a suggestion that was turned down.

    Making the same suggestion every week is its own kind of failure. The
    learner had a reason the first time.
    """
    rows = list(doc.get("declined", []))
    rows.append({"what": what, "reason": reason, "when": _now()})
    doc["declined"] = rows
    doc["updated"] = _now()
    return doc


# ---------------------------------------------------------------------------
# deciding whether wiring is worth it
# ---------------------------------------------------------------------------

def worth_wiring(tool: dict, uses: int = 0) -> dict:
    """Whether a tool should be wired up, and as what.

    Deliberately biased against building anything. A project accumulates
    integrations easily and sheds them slowly, and each one is a thing whose
    purpose somebody will later have to reconstruct.
    """
    tid = tool.get("tool_id")
    has_procedure = bool(tool.get("how_to_use")) or bool(tool.get("limits"))
    runnable = bool(tool.get("invocation"))

    if not has_procedure and uses < 3:
        return {"tool_id": tid, "build": None,
                "why": "nothing has been recorded about using it well, and "
                       "it has not come up often. A sentence in how_to_use "
                       "is the right size of answer"}

    if not has_procedure:
        return {"tool_id": tid, "build": "command" if runnable else None,
                "why": "used often, but there is no procedure to capture "
                       "yet. Ask the learner what matters about using it "
                       "before building anything"}

    if runnable:
        return {"tool_id": tid, "build": "check_existing",
                "if_missing": "skill",
                "why": "there is a procedure worth capturing. Check the "
                       "host, installed plugins, MCP servers and skills "
                       "first; create a project skill only if none already "
                       "supports the teaching task"}

    return {"tool_id": tid, "build": "check_existing",
            "if_missing": "skill",
            "why": "the learner runs it themselves, but their procedure "
                   "is worth keeping. Check existing integrations first; "
                   "if none fits, capture the steps in a project skill so "
                   "they survive being forgotten"}


def review(doc: dict) -> list:
    return [worth_wiring(t) for t in doc.get("tools", [])]


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def render(doc: dict) -> str:
    lines = []
    mats = doc.get("materials", [])
    lines.append("MATERIAL (" + str(len(mats)) + ")")
    for m in mats:
        line = "  " + str(m.get("title")) + "  [" + str(m.get("kind")) + "]"
        if m.get("edition"):
            line += "  " + m["edition"]
        lines.append(line)
        lines.append("      at: " + str(m.get("where")))
        if m.get("usable_pages"):
            lines.append("      not fully readable: " + m["usable_pages"])
    if not mats:
        lines.append("  none recorded")

    tools = doc.get("tools", [])
    lines.append("")
    lines.append("TOOLS (" + str(len(tools)) + ")")
    for t in tools:
        lines.append("  " + str(t.get("tool_id")) + " - " +
                     str(t.get("what_it_does")))
        lines.append("      where: " + str(t.get("runs_where")) +
                     ("   (this plugin runs it)" if t.get("invocation")
                      else "   (the learner runs it)"))
        if t.get("how_to_use"):
            lines.append("      using it: " + t["how_to_use"])
        if t.get("limits"):
            lines.append("      cannot: " + t["limits"])
    if not tools:
        lines.append("  none recorded")

    ints = doc.get("integrations", [])
    if ints:
        lines.append("")
        lines.append("WIRED UP (" + str(len(ints)) + ")")
        for i in ints:
            lines.append("  " + str(i.get("kind")) + "  " +
                         str(i.get("path")) + "  for " +
                         ", ".join(i.get("for_tools", [])))
            lines.append("      saves: " + str(i.get("why")))

    dec = doc.get("declined", [])
    if dec:
        lines.append("")
        lines.append("TURNED DOWN - do not suggest again")
        for d in dec:
            lines.append("  " + str(d.get("what")) +
                         ("  (" + d["reason"] + ")" if d.get("reason")
                          else ""))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def _save(root: Path, slug: str, doc: dict) -> int:
    errs = zs.validate_doc(doc, "resources")
    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        return zs.EXIT_VALIDATION
    p = path_for(root, slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    zs.atomic_write_json(p, doc)
    print("written: courses/" + slug + "/resources.json")
    return zs.EXIT_OK


def _root(args) -> Path:
    return Path(args.root) if args.root else zs.default_root()


def cmd_show(args) -> int:
    root = _root(args)
    if not (root / "courses" / args.course).exists():
        print("no such course: " + args.course, file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    doc = load(root, args.course)
    print(json.dumps(doc, ensure_ascii=False, indent=2) if args.json
          else render(doc))
    return zs.EXIT_OK


def _add(args, fn) -> int:
    root = _root(args)
    doc = load(root, args.course)
    try:
        doc = fn(doc, json.loads(args.data))
    except sb.Refused as r:
        print("REFUSED [" + r.code + "]  " + r.message, file=sys.stderr)
        if r.suggestion:
            print("instead: " + r.suggestion, file=sys.stderr)
        return zs.EXIT_GATE
    return _save(root, args.course, doc)


def cmd_add_material(args) -> int:
    return _add(args, add_material)


def cmd_add_tool(args) -> int:
    return _add(args, add_tool)


def cmd_add_integration(args) -> int:
    return _add(args, add_integration)


def cmd_decline(args) -> int:
    root = _root(args)
    doc = decline(load(root, args.course), args.what, args.reason or "")
    return _save(root, args.course, doc)


def cmd_review(args) -> int:
    root = _root(args)
    rows = review(load(root, args.course))
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return zs.EXIT_OK
    if not rows:
        print("no tools recorded for this course")
        return zs.EXIT_OK
    for r in rows:
        verdict = ("check existing capabilities first" if
                   r["build"] == "check_existing" else
                   r["build"] or "nothing")
        print(str(r["tool_id"]) + "  ->  " + verdict)
        print("    " + r["why"])
        if r.get("if_missing"):
            print("    if none fits: " + r["if_missing"])
    print("")
    print("Anything written into the learner's project is shown to them "
          "first.")
    return zs.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="resources.py",
        description="What this course has to work with, and how to use it.")
    p.add_argument("--root")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("show")
    sp.add_argument("--course", required=True)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_show)

    for name, fn in (("add-material", cmd_add_material),
                     ("add-tool", cmd_add_tool),
                     ("add-integration", cmd_add_integration)):
        sp = sub.add_parser(name)
        sp.add_argument("--course", required=True)
        sp.add_argument("--data", required=True)
        sp.set_defaults(func=fn)

    sp = sub.add_parser("decline")
    sp.add_argument("--course", required=True)
    sp.add_argument("--what", required=True)
    sp.add_argument("--reason")
    sp.set_defaults(func=cmd_decline)

    sp = sub.add_parser("review",
                        help="which tools are worth wiring up, and as what")
    sp.add_argument("--course", required=True)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_review)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
