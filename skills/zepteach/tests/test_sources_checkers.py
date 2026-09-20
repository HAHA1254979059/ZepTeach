"""Registered material, and the answers a machine can mark.

Two files, one shared concern: both refuse rather than guess. Material that
could not be read is not cited; a check that could not run does not pass.
Each of those, done the other way, produces a confident record of something
that never happened.
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import checkers as ck  # noqa: E402
import conftest as fx  # noqa: E402
import sources as sr  # noqa: E402
import zt_state as zs  # noqa: E402
from sandbox import Refused  # noqa: E402


def refusal(fn):
    with pytest.raises(Refused) as exc:
        fn()
    return exc.value


def source(**over):
    doc = {
        "source_id": "book",
        "kind": "pdf_text",
        "title": "某本教材",
        "edition": "第三版",
        "path": "/home/u/books/x.pdf",
        "index_status": "indexed",
    }
    doc.update(over)
    return doc


# ---------------------------------------------------------------------------
# material
# ---------------------------------------------------------------------------

class TestRegistering:
    def test_a_source_is_stored(self):
        doc = sr.register({"schema_version": 1, "course_id": "linalg",
                           "sources": []}, source())
        assert doc["sources"][0]["source_id"] == "book"

    def test_a_book_without_an_edition_is_refused(self):
        """Section and page numbers differ between printings, and a citation
        to the wrong one fails silently: both people see a plausible number
        and neither finds out they were looking at different text."""
        base = {"schema_version": 1, "course_id": "linalg", "sources": []}
        bad = source()
        del bad["edition"]
        r = refusal(lambda: sr.register(base, bad))
        assert r.code == "SRC002"
        assert "fails silently" in r.suggestion

    def test_registering_twice_replaces(self):
        base = {"schema_version": 1, "course_id": "linalg", "sources": []}
        doc = sr.register(base, source())
        doc = sr.register(doc, source(title="改过的标题"))
        assert len(doc["sources"]) == 1
        assert doc["sources"][0]["title"] == "改过的标题"


class TestWhatMayBeCited:
    def test_an_indexed_source_is_citable(self):
        assert sr.check_citable(source(), "6.1 p.288")["citable"]

    def test_an_unindexed_source_is_refused(self):
        r = refusal(lambda: sr.check_citable(
            source(index_status="pending"), "6.1"))
        assert r.code == "SRC010"

    def test_a_page_that_could_not_be_read_is_refused(self):
        """The reason this is strict: a citation to a page nobody could read
        is indistinguishable from a citation to a page that says something
        else, and both read as authoritative."""
        s = source(ocr={"used": True, "mean_quality": 0.7,
                        "pages_below_threshold": [287, 288]})
        r = refusal(lambda: sr.check_citable(s, "6.1 p.288"))
        assert r.code == "SRC011"
        assert "indistinguishable" in r.suggestion

    def test_a_readable_page_in_a_partly_bad_source_is_fine(self):
        s = source(ocr={"used": True, "pages_below_threshold": [287]})
        assert sr.check_citable(s, "6.1 p.290")["citable"]

    def test_a_page_range_is_checked_across_the_whole_range(self):
        s = source(ocr={"used": True, "pages_below_threshold": [289]})
        refusal(lambda: sr.check_citable(s, "pp. 288-291"))

    def test_a_partial_index_with_no_page_says_nothing_was_checked(self):
        out = sr.check_citable(source(index_status="partial"), "6.1")
        assert "nothing checked" in out["caution"]

    def test_the_refusal_offers_the_real_alternatives(self):
        s = source(ocr={"pages_below_threshold": [1]})
        r = refusal(lambda: sr.check_citable(s, "p.1"))
        for option in ("better copy", "read it and report back",
                       "unanchored"):
            assert option in r.suggestion


class TestResolvingALessonSpan:
    def index(self):
        return {"schema_version": 1, "course_id": "linalg",
                "sources": [source()]}

    def test_a_span_resolves_to_something_citable(self):
        out = sr.span_for(self.index(), {"source_id": "book",
                                         "section": "6.1",
                                         "page_start": 288})
        assert out["citable"]
        assert "6.1 p.288" in out["cite_as"]
        assert out["edition"] == "第三版"

    def test_the_check_cannot_be_skipped_by_asking_for_the_text(self):
        """Resolving a span and checking whether it may be cited are one
        call, so a lesson cannot take the first and miss the second."""
        doc = self.index()
        doc["sources"][0]["ocr"] = {"pages_below_threshold": [288]}
        refusal(lambda: sr.span_for(doc, {"source_id": "book",
                                          "page_start": 288}))

    def test_an_unknown_source_is_named(self):
        r = refusal(lambda: sr.span_for(self.index(),
                                        {"source_id": "ghost"}))
        assert r.code == "SRC005"


class TestReportingBeforeALesson:
    def test_unreadable_pages_come_with_a_line_to_say(self):
        out = sr.unusable(source(ocr={"pages_below_threshold": [1, 2]}))
        assert out["unreadable_pages"] == [1, 2]
        assert "不会假装引用" in out["say_to_learner"]

    def test_a_clean_source_has_nothing_to_say(self):
        assert sr.unusable(source())["say_to_learner"] == ""


# ---------------------------------------------------------------------------
# machine marking
# ---------------------------------------------------------------------------

def item(**over):
    doc = {
        "schema_version": 1,
        "exercise_id": "e1",
        "course_id": "linalg",
        "concept_ids": [fx.EIGENVALUE],
        "tier": "variant",
        "prompt": "q",
        "grader": {"type": "numeric", "spec": {"expected": 3.0},
                   "tolerance": 0.01},
    }
    doc.update(over)
    return doc


class TestExact:
    def test_a_match_passes(self):
        out = ck.check_exact("必要条件", {"expected": "必要条件"})
        assert out["verdict"] == "pass"

    def test_spacing_and_case_do_not_decide_it(self):
        out = ck.check_exact("  Necessary   Condition ",
                             {"expected": "necessary condition"})
        assert out["verdict"] == "pass"

    def test_full_width_characters_are_the_same_answer(self):
        """Failing this teaches nothing except that the system is
        unreliable."""
        out = ck.check_exact("ABC", {"expected": "ABC"})
        assert out["verdict"] == "pass"

    def test_an_alternative_spelling_can_be_accepted(self):
        out = ck.check_exact("eigenvector",
                             {"expected": "特征向量",
                              "also_accept": ["eigenvector"]})
        assert out["verdict"] == "pass"

    def test_no_expected_answer_is_not_checked(self):
        out = ck.check_exact("anything", {})
        assert out["verdict"] == "not_checked"

    def test_a_mismatch_fails_and_says_both(self):
        out = ck.check_exact("充分条件", {"expected": "必要条件"})
        assert out["verdict"] == "fail"
        assert out["expected"] == "必要条件"


class TestNumeric:
    def test_within_tolerance_passes(self):
        assert ck.check_numeric("答案是 3.001",
                                {"expected": 3.0,
                                 "tolerance": 0.01})["verdict"] == "pass"

    def test_the_last_number_is_the_answer(self):
        """Working shown before the result is the normal shape of a worked
        answer. Taking the first number marks the first intermediate step
        instead of the conclusion."""
        assert ck.extract_number("先算 12，再除以 4，得 3") == 3.0

    def test_no_tolerance_is_not_a_check(self):
        """Comparing floating point numbers for equality is not a check."""
        out = ck.check_numeric("3.0", {"expected": 3.0})
        assert out["verdict"] == "not_checked"
        assert "not a check" in out["why"]

    def test_a_sign_error_is_named(self):
        out = ck.check_numeric("-3", {"expected": 3.0, "tolerance": 0.01})
        assert out["verdict"] == "fail"
        assert "sign is wrong" in out["why"]

    def test_a_factor_of_two_is_named(self):
        """It points at one step rather than the whole method, which is
        worth saying instead of reporting a bare mismatch."""
        out = ck.check_numeric("6", {"expected": 3.0, "tolerance": 0.01})
        assert "twice" in out["why"]

    def test_relative_tolerance_scales(self):
        out = ck.check_numeric("1010", {"expected": 1000.0,
                                        "tolerance": 0.02,
                                        "relative": True})
        assert out["verdict"] == "pass"

    def test_an_answer_with_no_number_fails(self):
        out = ck.check_numeric("我不知道", {"expected": 3.0,
                                            "tolerance": 0.01})
        assert out["verdict"] == "fail"


class TestProgramCheckers:
    def adapter(self, **over):
        c = {"checker_id": "proof", "what_it_checks": "gaps in a proof",
             "command": [sys.executable, "-c", "raise SystemExit(0)"],
             "timeout_seconds": 10}
        c.update(over)
        return {"checkers": [c]}

    def test_an_accepting_checker_passes(self, tmp_path):
        ans = tmp_path / "a.txt"
        ans.write_text("x", encoding="utf-8")
        out = ck.mark(item(grader={"type": "checker",
                                   "checker_id": "proof"}),
                      "x", self.adapter(), ans)
        assert out["verdict"] == "pass"

    def test_a_rejecting_checker_fails(self, tmp_path):
        ans = tmp_path / "a.txt"
        ans.write_text("x", encoding="utf-8")
        out = ck.mark(item(grader={"type": "checker",
                                   "checker_id": "proof"}),
                      "x", self.adapter(
                          command=[sys.executable, "-c",
                                   "raise SystemExit(1)"]), ans)
        assert out["verdict"] == "fail"

    def test_a_checker_that_does_not_exist_is_not_checked(self, tmp_path):
        out = ck.mark(item(grader={"type": "checker", "checker_id": "ghost"}),
                      "x", self.adapter(), tmp_path / "a.txt")
        assert out["verdict"] == "not_checked"
        assert "does not register it" in out["why"]

    def test_a_crashed_checker_is_not_checked_rather_than_passed(self):
        """The tempting failure: treat a broken checker as an inconvenience
        and let the answer through. That turns an infrastructure problem into
        a false record of what the learner can do, and the record outlives
        the problem."""
        def boom(cmd, timeout):
            raise OSError("cannot start")
        out = ck.check_with_program(Path("a.txt"),
                                    self.adapter()["checkers"][0],
                                    runner=boom)
        assert out["verdict"] == "not_checked"

    def test_a_checker_that_would_change_the_environment_is_refused(self):
        out = ck.check_with_program(
            Path("a.txt"),
            {"checker_id": "bad", "command": ["pip", "install", "x"],
             "timeout_seconds": 10})
        assert out["verdict"] == "not_checked"
        assert out["refused"] == "SBX010"

    def test_a_declared_zero_timeout_is_refused_not_replaced(self):
        """A stated 0 is an invalid limit and gets refused. Reading it as
        "not set" and substituting the default is how an invalid limit turns
        into a working one."""
        out = ck.check_with_program(
            Path("a.txt"),
            {"checker_id": "bad", "command": ["echo"], "timeout_seconds": 0})
        assert out["verdict"] == "not_checked"
        assert out["refused"] == "SBX012"

    def test_an_absent_timeout_falls_back_to_the_default(self):
        out = ck.check_with_program(
            Path("a.txt"),
            {"checker_id": "ok",
             "command": [sys.executable, "-c", "raise SystemExit(0)"]})
        assert out["verdict"] == "pass"


class TestDispatch:
    def test_an_open_ended_item_is_not_marked_here(self):
        """It goes to the separate process with no teaching context, which is
        the whole reason open-ended marking is trustworthy."""
        out = ck.mark(item(grader={"type": "rubric"}), "x")
        assert out["verdict"] == "not_checked"
        assert "separate marking process" in out["why"]

    def test_an_item_with_no_grader_is_not_checked(self):
        out = ck.mark({"grader": {}}, "x")
        assert out["verdict"] == "not_checked"

    def test_every_verdict_is_one_of_three(self):
        for out in (ck.mark(item(), "3.0"),
                    ck.mark(item(), "nonsense"),
                    ck.mark({"grader": {}}, "x")):
            assert out["verdict"] in ck.VERDICTS


class TestTurningAResultIntoARecord:
    def test_the_record_is_deliberately_incomplete(self):
        """How effortful the recall was, and what depth the answer showed,
        are not things a program can see. Filling them in with defaults would
        put invented data where the schedule reads from."""
        doc = ck.to_attempt(item(), ck.mark(item(), "3.0"))
        assert "latency_rating" not in doc
        assert "depth_demonstrated" not in doc
        assert zs.validate_doc(doc, "attempt") != []

    def test_supplying_the_missing_parts_makes_it_valid(self):
        doc = ck.to_attempt(
            item(), ck.mark(item(), "3.0"),
            attempt_id="a1", kind="inclass",
            submitted_at="2026-09-20T10:00:00+00:00",
            evidence_quotes=["得 3"], latency_rating="fluent",
            latency_source="inferred", depth_demonstrated=2)
        assert zs.validate_doc(doc, "attempt") == []

    def test_an_unchecked_result_is_recorded_as_a_fail_not_a_pass(self):
        doc = ck.to_attempt(item(grader={"type": "rubric"}),
                            ck.mark(item(grader={"type": "rubric"}), "x"))
        assert doc["verdict"] == "fail"
