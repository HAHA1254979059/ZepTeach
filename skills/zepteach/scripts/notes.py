#!/usr/bin/env python3
"""Notes, written twice for two different readers.

The markdown copy is what this plugin reads back. Plain text, linkable,
diffable, and the thing a later lesson searches to find out what was already
established. The document copy is what the learner reads.

Both are produced from the same note in one operation, so they cannot drift
apart. Neither is an export of the other.

The failure this file exists to prevent is a note turning into a record of
conversations. "Asked whether this can be negative" is meaningless three
months later: it records that an exchange happened, not what is now known.
So the canonical layer holds knowledge statements and the journal holds
everything else, and the split is enforced rather than encouraged.

The document is written without any third-party library. A .docx is a zip of
XML parts, and writing the few that matter keeps this plugin runnable on any
machine with Python and nothing else installed.

Exit codes: 0 ok, 2 invalid data, 3 refused, 5 not found.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))

import zt_state as zs  # noqa: E402
from sandbox import Refused  # noqa: E402


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# the six sections
# ---------------------------------------------------------------------------
#
# The ids are fixed and English; the headings the learner sees are written in
# the course's teaching language. Those are different things, and conflating
# them would hard-code one language into the note format, which is the same
# mistake as hard-coding a subject.

SECTIONS = [
    {"id": "definition",
     "asks": "What is it, operationally? How would you compute or check it?",
     "missing_costs": "without this the note cannot be acted on, only "
                      "recognised"},
    {"id": "why-needed",
     "asks": "What breaks without it? What problem was it invented for?",
     "missing_costs": "a definition with no motivation is memorised and not "
                      "understood"},
    {"id": "mechanism",
     "asks": "Why does it work? The actual mechanism, not a restatement of "
             "the definition.",
     "missing_costs": "this is the section most often filled with a "
                      "paraphrase of section one"},
    {"id": "boundary",
     "asks": "Where does it fail? What is it confused with?",
     "missing_costs": "the section that decays first when not enforced, and "
                      "the one whose absence produces confident misuse"},
    {"id": "relations",
     "asks": "Which neighbouring concepts, and what is the relationship to "
             "each?",
     "missing_costs": "an isolated note is an isolated memory, and isolated "
                      "memories are the ones that go"},
    {"id": "examples",
     "asks": "Which worked items show this? Pointers, not copies.",
     "missing_costs": "nothing links the statement to anything concrete"},
]

SECTION_IDS = [s["id"] for s in SECTIONS]


# Phrasings that mean the note is recording a conversation rather than
# knowledge. Checked in whatever language, because the shape is the same.
LEDGER_MARKERS = [
    (r"用户问|学习者问|他问|今天问", "records that a question was asked"),
    (r"我(们)?(讲|说|解释)过", "records that something was said"),
    (r"\b(asked|we discussed|we went over|today we|I explained)\b",
     "records the exchange rather than the knowledge"),
    (r"^\s*\d{4}-\d{2}-\d{2}", "a dated entry belongs in the journal"),
]


def check_body(sections: dict) -> None:
    """Refuse a note that is missing a section or is writing a log."""
    missing = [s["id"] for s in SECTIONS if not (sections.get(s["id"]) or
                                                 "").strip()]
    if missing:
        detail = "; ".join(
            s["id"] + " (" + s["missing_costs"] + ")"
            for s in SECTIONS if s["id"] in missing)
        raise Refused(
            "NOT001",
            "these sections are empty: " + ", ".join(missing),
            detail + ". If one of them genuinely has nothing to say yet, the "
            "concept is not understood well enough to write a canonical note "
            "about, and what there is belongs in the journal")

    for sid, text in sections.items():
        for pattern, why in LEDGER_MARKERS:
            if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                raise Refused(
                    "NOT002",
                    "section " + sid + " " + why,
                    "rewrite it as a statement about the subject. If it "
                    "cannot be written that way, it was never canonical: put "
                    "it in the journal")

    rel = sections.get("relations", "")
    links = re.findall(r"\[\[([^\]]+)\]\]", rel)
    for link in links:
        line = next((ln for ln in rel.splitlines() if "[[" + link + "]]" in ln),
                    "")
        stripped = re.sub(r"\[\[[^\]]+\]\]", "", line)
        if len(re.sub(r"[\s\-\*•,.;:]", "", stripped)) < 4:
            raise Refused(
                "NOT003",
                "the link to " + link + " has no relationship written next "
                "to it",
                "say what the relationship is. A bare link records that two "
                "things are near each other, which is not what makes either "
                "of them easier to recall")


# ---------------------------------------------------------------------------
# markdown, the copy this plugin reads
# ---------------------------------------------------------------------------

def render_markdown(note: dict, sections: dict, headings: dict) -> str:
    """Frontmatter plus the six sections.

    headings maps section id to the heading text in the teaching language.
    The ids stay in the frontmatter so that a later lesson can find a section
    without knowing which language the note was written in.
    """
    front = dict(note)
    front["sections"] = SECTION_IDS
    lines = ["---"]
    for key in sorted(front):
        val = front[key]
        lines.append(key + ": " + json.dumps(val, ensure_ascii=False))
    lines.append("---")
    lines.append("")
    lines.append("# " + str(note.get("title")))
    for spec in SECTIONS:
        sid = spec["id"]
        lines.append("")
        lines.append("## " + headings.get(sid, sid))
        lines.append("")
        lines.append(sections.get(sid, "").strip())
    lines.append("")
    return "\n".join(lines)


def parse_markdown(text: str) -> tuple:
    """Read one back. Used when a later lesson needs what was established."""
    if not text.startswith("---"):
        return {}, {}
    _, front_block, body = text.split("---", 2)
    front = {}
    for line in front_block.strip().splitlines():
        if ": " not in line:
            continue
        key, val = line.split(": ", 1)
        try:
            front[key] = json.loads(val)
        except ValueError:
            front[key] = val
    sections, current = {}, None
    ids = iter(SECTION_IDS)
    for line in body.splitlines():
        if line.startswith("## "):
            current = next(ids, None)
            if current:
                sections[current] = ""
        elif current:
            sections[current] += line + "\n"
    return front, dict((k, v.strip()) for k, v in sections.items())


# ---------------------------------------------------------------------------
# the document, the copy the learner reads
# ---------------------------------------------------------------------------

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
    'content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-'
    'package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.'
    'openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '</Types>')

_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
    'relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
    'officeDocument/2006/relationships/officeDocument" Target="word/'
    'document.xml"/>'
    '</Relationships>')

_DOC_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
    'relationships"/>')

_W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def _para(text: str, style: str = None) -> str:
    bits = ['<w:p>']
    if style:
        bits.append('<w:pPr><w:pStyle w:val="' + style + '"/></w:pPr>')
    for chunk in str(text).split("\n"):
        bits.append('<w:r><w:t xml:space="preserve">' + escape(chunk) +
                    '</w:t></w:r>')
        bits.append('<w:r><w:br/></w:r>')
    if len(bits) > (2 if style else 1):
        bits.pop()
    bits.append('</w:p>')
    return "".join(bits)


def _heading(text: str, level: int) -> str:
    """Bold and sized rather than a named style.

    A named heading style only renders if the document carries a styles part
    defining it. Direct formatting works in any reader, which is what matters
    for a file the learner opens in whatever they happen to have.
    """
    size = {1: "36", 2: "28"}.get(level, "24")
    return ('<w:p><w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>'
            '<w:r><w:rPr><w:b/><w:sz w:val="' + size + '"/></w:rPr>'
            '<w:t xml:space="preserve">' + escape(str(text)) +
            '</w:t></w:r></w:p>')


def build_docx(path: Path, note: dict, sections: dict,
               headings: dict) -> Path:
    """Write the readable copy.

    Built from the same note as the markdown, in the same call, so the two
    cannot describe different things.
    """
    body = [_heading(note.get("title", ""), 1)]
    for spec in SECTIONS:
        sid = spec["id"]
        body.append(_heading(headings.get(sid, sid), 2))
        body.append(_para(sections.get(sid, "").strip()))

    updated = note.get("updated", "")
    if updated:
        body.append(_para("最后更新 " + str(updated)[:10]))

    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="' + _W + '"><w:body>' +
                "".join(body) +
                '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" '
                'w:left="1134"/></w:sectPr></w:body></w:document>')

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/_rels/document.xml.rels", _DOC_RELS)
        z.writestr("word/document.xml", document)
    return path


# ---------------------------------------------------------------------------
# the journal
# ---------------------------------------------------------------------------

def journal_line(entry: str, when=None) -> str:
    """One line in the running record.

    Everything that is not a change in what the learner knows goes here:
    questions asked, things tried, what went wrong today. It is dated,
    append-only, and never read back by a lesson.
    """
    return "- " + (when or _now())[:16].replace("T", " ") + "  " + \
        entry.strip() + "\n"


def append_journal(root: Path, cfg: dict, entry: str, when=None) -> Path:
    notes = cfg.get("notes") or {}
    jdir = notes.get("journal_dir") or notes.get("markdown_dir")
    if not jdir:
        raise Refused("NOT010", "no folder is configured for notes",
                      "run the first setup; the markdown folder is required")
    day = (when or _now())[:10]
    path = Path(jdir) / (day + ".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("# " + day + "\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(journal_line(entry, when))
    return path


# ---------------------------------------------------------------------------
# writing both copies
# ---------------------------------------------------------------------------

def write(root: Path, cfg: dict, note: dict, sections: dict,
          headings: dict) -> dict:
    """Validate, then write markdown and, if configured, the document."""
    check_body(sections)

    note = dict(note)
    note["sections"] = SECTION_IDS
    note["updated"] = _now()

    # Counted here rather than supplied by the caller. A number the writer
    # passes in is a number the writer can forget, and this one is read as a
    # health signal: a note rewritten four times as understanding deepened is
    # working, and one that says 0 after four rewrites is lying quietly.
    existing = Path((cfg.get("notes") or {}).get("markdown_dir", "")) /         (str(note["concept_id"]) + ".md")
    if existing.exists():
        prior, _ = parse_markdown(existing.read_text(encoding="utf-8"))
        note["rewrite_count"] = int(prior.get("rewrite_count", 0)) + 1
    else:
        note["rewrite_count"] = 0
    note["links"] = sorted(set(
        re.findall(r"\[\[([^\]]+)\]\]",
                   "\n".join(sections.values()))))

    errs = zs.validate_doc(note, "note")
    if errs:
        raise Refused("NOT004", "; ".join(errs),
                      "the frontmatter does not match the stored shape")

    cfgn = cfg.get("notes") or {}
    md_dir = cfgn.get("markdown_dir")
    if not md_dir:
        raise Refused("NOT010", "no folder is configured for notes",
                      "run the first setup; the markdown folder is required")

    name = str(note["concept_id"]) + ".md"
    md_path = Path(md_dir) / name
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(note, sections, headings),
                       encoding="utf-8")

    out = {"markdown": str(md_path), "rewrite_count": note.get(
        "rewrite_count", 0)}

    doc_dir = cfgn.get("document_dir")
    if doc_dir and cfgn.get("document_format", "docx") != "none":
        doc_path = Path(doc_dir) / (str(note["concept_id"]) + ".docx")
        build_docx(doc_path, note, sections, headings)
        out["document"] = str(doc_path)
    return out


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def _payload(args):
    raw = Path(args.file).read_text(encoding="utf-8") if args.file \
        else args.data
    return json.loads(raw)


def cmd_sections(args) -> int:
    """What each section is for, and what its absence costs."""
    if args.json:
        print(json.dumps(SECTIONS, ensure_ascii=False, indent=2))
        return zs.EXIT_OK
    for i, s in enumerate(SECTIONS, 1):
        print(str(i) + ". " + s["id"])
        print("   " + s["asks"])
        print("   missing: " + s["missing_costs"])
    print("")
    print("Headings go in the course's teaching language. These ids do not; "
          "they are how a later lesson finds a section without knowing which "
          "language the note was written in.")
    return zs.EXIT_OK


def cmd_check(args) -> int:
    payload = _payload(args)
    try:
        check_body(payload.get("sections") or {})
    except Refused as r:
        print("REFUSED [" + r.code + "]  " + r.message, file=sys.stderr)
        if r.suggestion:
            print("instead: " + r.suggestion, file=sys.stderr)
        return zs.EXIT_GATE
    print("ok")
    return zs.EXIT_OK


def cmd_write(args) -> int:
    root = Path(args.root) if args.root else zs.default_root()
    cfg_path = root / "config.json"
    if not cfg_path.exists():
        print("no config; run the first setup", file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    payload = _payload(args)
    try:
        out = write(root, zs.read_json(cfg_path), payload["note"],
                    payload["sections"], payload.get("headings") or {})
    except Refused as r:
        print("REFUSED [" + r.code + "]  " + r.message, file=sys.stderr)
        if r.suggestion:
            print("instead: " + r.suggestion, file=sys.stderr)
        return zs.EXIT_GATE
    print("written: " + out["markdown"])
    if out.get("document"):
        print("written: " + out["document"])
    return zs.EXIT_OK


def cmd_journal(args) -> int:
    root = Path(args.root) if args.root else zs.default_root()
    cfg_path = root / "config.json"
    if not cfg_path.exists():
        print("no config; run the first setup", file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    try:
        path = append_journal(root, zs.read_json(cfg_path), args.entry)
    except Refused as r:
        print("REFUSED [" + r.code + "]  " + r.message, file=sys.stderr)
        return zs.EXIT_GATE
    print("appended: " + str(path))
    return zs.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="notes.py",
        description="Notes, written twice for two different readers.")
    p.add_argument("--root")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("sections", help="what each section is for")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_sections)

    sp = sub.add_parser("check", help="would this be accepted")
    sp.add_argument("--data")
    sp.add_argument("--file")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("write", help="write both copies")
    sp.add_argument("--data")
    sp.add_argument("--file")
    sp.set_defaults(func=cmd_write)

    sp = sub.add_parser("journal", help="append to the running record")
    sp.add_argument("--entry", required=True)
    sp.set_defaults(func=cmd_journal)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
