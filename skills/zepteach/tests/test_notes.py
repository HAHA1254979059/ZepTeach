"""Notes.

The failure guarded against is a note turning into a record of
conversations. It happens gradually, every individual line looks reasonable,
and the result is unreadable three months later, which is exactly when it was
supposed to be useful.
"""

import json
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import conftest as fx  # noqa: E402
import notes as nt  # noqa: E402
import zt_state as zs  # noqa: E402
from sandbox import Refused  # noqa: E402


def refusal(fn):
    with pytest.raises(Refused) as exc:
        fn()
    return exc.value


HEADINGS = {
    "definition": "定义",
    "why-needed": "为什么需要",
    "mechanism": "机理",
    "boundary": "边界与常见误区",
    "relations": "与相邻概念的关系",
    "examples": "例题指针",
}


def sections(**over):
    doc = {
        "definition": "一个条件，必须满足才能得出结论，但满足了不一定够。",
        "why-needed": "不分开说，论证会在两个方向上都被当成成立。",
        "mechanism": "方向性来自蕴含关系本身，反过来要单独证。",
        "boundary": "最常见的错是把两者当成一回事，尤其在论证是口头的时候。",
        "relations": "- [[reason.counterexample]] 是推翻充分性最省力的工具。",
        "examples": "- ex:necessary-01",
    }
    doc.update(over)
    return doc


def note(**over):
    doc = {
        "schema_version": 1,
        "concept_id": fx.SHARED,
        "title": "必要条件与充分条件",
        "course_id": "linalg",
        "depth_target": 3,
        "sections": nt.SECTION_IDS,
        "updated": "2026-09-20T00:00:00+00:00",
        "rewrite_count": 1,
    }
    doc.update(over)
    return doc


def config(tmp_path, **over):
    doc = dict(fx.config())
    doc["notes"] = {
        "markdown_dir": str(tmp_path / "notes"),
        "document_dir": str(tmp_path / "docs"),
        "journal_dir": str(tmp_path / "journal"),
    }
    doc.update(over)
    return doc


class TestTheSixSections:
    def test_all_six_are_required(self):
        for spec in nt.SECTIONS:
            bad = sections()
            bad[spec["id"]] = ""
            r = refusal(lambda: nt.check_body(bad))
            assert r.code == "NOT001"
            assert spec["id"] in r.message

    def test_the_refusal_says_what_the_gap_costs(self):
        bad = sections(boundary="")
        r = refusal(lambda: nt.check_body(bad))
        assert "confident misuse" in r.suggestion

    def test_an_empty_section_means_it_is_not_canonical_yet(self):
        """There is a right answer for a concept not yet understood well
        enough, and it is the journal, not a note with a gap in it."""
        r = refusal(lambda: nt.check_body(sections(mechanism="")))
        assert "belongs in the journal" in r.suggestion

    def test_a_complete_note_passes(self):
        nt.check_body(sections())

    def test_the_ids_are_language_independent(self):
        """Headings are written in the teaching language; the ids are not.
        Putting the Chinese headings in the frontmatter would hard-code one
        language into the note format."""
        assert nt.SECTION_IDS == ["definition", "why-needed", "mechanism",
                                  "boundary", "relations", "examples"]
        for sid in nt.SECTION_IDS:
            assert sid.isascii()


class TestNotesAreNotALog:
    @pytest.mark.parametrize("text", [
        "用户问了特征值能不能是复数",
        "今天问到这个条件的方向",
        "我们讲过这一步",
        "Asked whether this can be negative",
        "we discussed the boundary case",
        "2026-09-20 复习了一遍",
    ])
    def test_a_line_recording_the_exchange_is_refused(self, text):
        r = refusal(lambda: nt.check_body(sections(definition=text)))
        assert r.code == "NOT002"

    def test_the_refusal_names_the_alternative(self):
        r = refusal(lambda: nt.check_body(
            sections(definition="用户问了这个能不能反过来")))
        assert "put it in the journal" in r.suggestion

    def test_the_same_content_as_a_statement_is_fine(self):
        """The test is the shape, not the subject. The knowledge behind the
        question belongs in the note; the fact that it was asked does not."""
        nt.check_body(sections(
            definition="反过来不成立：满足结论不代表这个条件成立。"))


class TestLinksCarryTheirRelationship:
    def test_a_bare_link_is_refused(self):
        r = refusal(lambda: nt.check_body(
            sections(relations="- [[reason.counterexample]]")))
        assert r.code == "NOT003"
        assert "near each other" in r.suggestion

    def test_a_link_with_a_stated_relationship_passes(self):
        nt.check_body(sections(
            relations="- [[x.y]] 提供了推翻充分性的最短路径。"))

    def test_links_are_collected_into_the_frontmatter(self, tmp_path):
        out = nt.write(tmp_path, config(tmp_path), note(),
                       sections(relations="- [[a.b]] 是它的反面。\n"
                                          "- [[c.d]] 在证明里一起用。"),
                       HEADINGS)
        front, _ = nt.parse_markdown(
            Path(out["markdown"]).read_text(encoding="utf-8"))
        assert front["links"] == ["a.b", "c.d"]


class TestBothCopies:
    def test_markdown_and_document_are_written_together(self, tmp_path):
        out = nt.write(tmp_path, config(tmp_path), note(), sections(),
                       HEADINGS)
        assert Path(out["markdown"]).exists()
        assert Path(out["document"]).exists()

    def test_only_markdown_when_no_document_folder(self, tmp_path):
        cfg = config(tmp_path)
        del cfg["notes"]["document_dir"]
        out = nt.write(tmp_path, cfg, note(), sections(), HEADINGS)
        assert "document" not in out

    def test_the_document_opens_as_a_real_docx(self, tmp_path):
        """Written with the standard library only, so the plugin still runs
        on a machine with nothing installed."""
        out = nt.write(tmp_path, config(tmp_path), note(), sections(),
                       HEADINGS)
        with zipfile.ZipFile(out["document"]) as z:
            names = set(z.namelist())
            assert "[Content_Types].xml" in names
            assert "word/document.xml" in names
            assert "_rels/.rels" in names
            body = z.read("word/document.xml").decode("utf-8")
        assert "必要条件与充分条件" in body
        assert "边界与常见误区" in body

    def test_the_document_escapes_characters_that_would_break_it(self,
                                                                 tmp_path):
        out = nt.write(tmp_path, config(tmp_path), note(),
                       sections(definition="当 a < b 且 x > y 时成立 & 反之"),
                       HEADINGS)
        with zipfile.ZipFile(out["document"]) as z:
            body = z.read("word/document.xml").decode("utf-8")
        assert "&lt;" in body and "&amp;" in body
        assert "a < b" not in body

    def test_the_two_copies_come_from_one_call(self, tmp_path):
        """Neither is an export of the other, so they cannot describe
        different things."""
        src = (SCRIPTS / "notes.py").read_text(encoding="utf-8")
        assert "build_docx(doc_path, note, sections, headings)" in src


class TestMarkdownIsReadableBack:
    def test_a_written_note_parses_back(self, tmp_path):
        out = nt.write(tmp_path, config(tmp_path), note(), sections(),
                       HEADINGS)
        front, secs = nt.parse_markdown(
            Path(out["markdown"]).read_text(encoding="utf-8"))
        assert front["concept_id"] == fx.SHARED
        assert front["sections"] == nt.SECTION_IDS
        assert "必须满足" in secs["definition"]
        assert set(secs) == set(nt.SECTION_IDS)

    def test_headings_are_in_the_teaching_language(self, tmp_path):
        out = nt.write(tmp_path, config(tmp_path), note(), sections(),
                       HEADINGS)
        text = Path(out["markdown"]).read_text(encoding="utf-8")
        assert "## 边界与常见误区" in text
        assert "## boundary" not in text

    def test_the_frontmatter_validates(self, tmp_path):
        out = nt.write(tmp_path, config(tmp_path), note(), sections(),
                       HEADINGS)
        front, _ = nt.parse_markdown(
            Path(out["markdown"]).read_text(encoding="utf-8"))
        assert zs.validate_doc(front, "note") == []


class TestTheJournal:
    def test_an_entry_is_dated_and_appended(self, tmp_path):
        cfg = config(tmp_path)
        p = nt.append_journal(tmp_path, cfg, "试了一下反例，没构造出来")
        p2 = nt.append_journal(tmp_path, cfg, "第二次想到了")
        assert p == p2
        text = p.read_text(encoding="utf-8")
        assert text.count("- ") == 2
        assert "没构造出来" in text

    def test_the_journal_takes_what_the_note_refuses(self, tmp_path):
        """The two layers are complements. Anything rejected from a note has
        somewhere to go, which is what stops it being forced into one."""
        cfg = config(tmp_path)
        refusal(lambda: nt.check_body(sections(definition="用户问了这个")))
        p = nt.append_journal(tmp_path, cfg, "问了这个能不能反过来")
        assert p.exists()

    def test_no_folder_configured_is_refused_clearly(self, tmp_path):
        cfg = config(tmp_path)
        cfg["notes"] = {}
        r = refusal(lambda: nt.append_journal(tmp_path, cfg, "x"))
        assert r.code == "NOT010"


class TestCli:
    def run(self, argv):
        try:
            return nt.main(argv)
        except SystemExit as exc:
            return exc.code

    def test_sections_explains_each_one(self, capsys):
        assert self.run(["sections"]) == zs.EXIT_OK
        out = capsys.readouterr().out
        assert "decays first" in out
        assert "teaching language" in out

    def test_check_refuses_a_log_entry(self, capsys):
        code = self.run(["check", "--data", json.dumps(
            {"sections": sections(definition="用户问了这个")})])
        assert code == zs.EXIT_GATE
        assert "NOT002" in capsys.readouterr().err

    def test_write_reports_both_paths(self, tmp_path, capsys):
        zs.main(["--root", str(tmp_path), "init"])
        zs.atomic_write_json(tmp_path / "config.json", config(tmp_path))
        capsys.readouterr()
        code = self.run(["--root", str(tmp_path), "write", "--data",
                         json.dumps({"note": note(), "sections": sections(),
                                     "headings": HEADINGS})])
        out = capsys.readouterr().out
        assert code == zs.EXIT_OK
        assert out.count("written:") == 2
