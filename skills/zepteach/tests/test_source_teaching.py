"""An anchored course must connect a delivered explanation to its source."""

import conftest as fx
import learner as ln
import sources as sr
import zt_state as zs


def anchored_root(root, status="indexed"):
    course_path = root / "courses" / "linear-algebra" / "course.json"
    course = zs.read_json(course_path)
    course["source_anchored"] = True
    zs.atomic_write_json(course_path, course)
    curriculum_path = root / "courses" / "linear-algebra" / "curriculum.json"
    curriculum = zs.read_json(curriculum_path)
    curriculum["modules"][0]["lessons"][0]["source_span"] = {
        "source_id": "primary", "section": "unit-one", "page_start": 4}
    zs.atomic_write_json(curriculum_path, curriculum)
    index_path = root / "courses" / "linear-algebra" / "sources" / "index.json"
    zs.atomic_write_json(index_path, {
        "schema_version": 1, "course_id": "linalg", "sources": [
            {"source_id": "primary", "kind": "pdf_text",
             "title": "A course text", "edition": "first",
             "path": "a-course-text.pdf", "index_status": status}]})


def test_source_anchored_teaching_refuses_a_source_free_explanation(root):
    anchored_root(root)
    assert fx.teach(root) == zs.EXIT_GATE
    assert ln.load_mastery(root) == []


def test_source_anchored_teaching_accepts_the_mapped_citable_source(root):
    anchored_root(root)
    assert fx.teach(root, sources=["primary"]) == zs.EXIT_OK
    assert ln.load_mastery(root)[0]["state"] == "introduced"


def test_unindexed_source_cannot_be_used_as_an_authority(root):
    anchored_root(root, status="pending")
    assert fx.teach(root, sources=["primary"]) == zs.EXIT_GATE
    assert ln.load_mastery(root) == []


def test_source_plan_reports_an_unanchored_course_without_a_source(root):
    cdir = root / "courses" / "linear-algebra"
    plan = sr.teaching_plan(zs.read_json(cdir / "course.json"),
                            zs.read_json(cdir / "curriculum.json"),
                            {"sources": []})
    assert plan["registered_sources"] == 0
    assert "select a teaching source" in plan["next_actions"][0]


def test_source_plan_reports_a_readable_but_unmapped_source(root):
    anchored_root(root)
    cdir = root / "courses" / "linear-algebra"
    plan = sr.teaching_plan(zs.read_json(cdir / "course.json"),
                            zs.read_json(cdir / "curriculum.json"),
                            sr.load(root, "linear-algebra"))
    assert plan["readable_sources"] == ["primary"]
    assert "l2" in plan["lessons_without_mapped_spans"]


def test_a_video_span_keeps_its_timecode_in_the_citation():
    index = {"sources": [{"source_id": "course", "title": "Recorded course",
                          "kind": "video_transcript", "path": "lesson.txt",
                          "index_status": "indexed"}]}
    result = sr.span_for(index, {"source_id": "course",
                                 "heading": "A worked explanation",
                                 "timecode_start": "00:12:30",
                                 "timecode_end": "00:18:10"})
    assert "00:12:30-00:18:10" in result["cite_as"]


def test_partial_video_index_cannot_cite_an_unverified_timecode():
    index = {"sources": [{"source_id": "course", "title": "Recorded course",
                          "kind": "video_transcript", "path": "lesson.txt",
                          "index_status": "partial", "toc": []}]}
    try:
        sr.span_for(index, {"source_id": "course",
                            "timecode_start": "00:12:30"})
    except Exception as error:
        assert getattr(error, "code", None) == "SRC012"
    else:
        raise AssertionError("an unreadable timecoded span was cited")
