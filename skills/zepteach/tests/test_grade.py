"""Marking.

The failure this guards against is not inaccuracy. It is that the thing doing
the marking also did the teaching, knows the learner, and wants them to do
well. None of that shows up in the output, so none of it can be caught by
reading the verdict. It has to be prevented structurally.
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import grade as gr  # noqa: E402
import zt_state as zs  # noqa: E402
from sandbox import Refused  # noqa: E402


def refusal(fn):
    with pytest.raises(Refused) as exc:
        fn()
    return exc.value


ANSWER = ("I set up the characteristic polynomial and solved it. "
          "The approximation stops holding once the coupling is strong, "
          "because the expansion is in that parameter.")


def rubric(**over):
    doc = {
        "schema_version": 1,
        "rubric_id": "r1",
        "applies_to": "an open-ended item about where a method breaks down",
        "criteria": [
            {"criterion_id": "sets-up",
             "requires": "states the method used",
             "evidence_looks_like": "names the polynomial or the equation",
             "weight": 1, "depth": 2},
            {"criterion_id": "boundary",
             "requires": "states when the approximation stops holding",
             "evidence_looks_like": "names the condition and why",
             "common_miss": "says it is approximate without saying when",
             "weight": 2, "depth": 4, "required_for_pass": True},
        ],
        "pass_threshold": 0.6,
        "not_evidence": ["restating the question",
                         "using the right words with no reasoning"],
        "refuse_to_guess": True,
    }
    doc.update(over)
    return doc


def verdict(**over):
    doc = {
        "verdict": "pass",
        "criteria_met": {
            "sets-up": {"met": True,
                        "quotes": ["set up the characteristic polynomial"]},
            "boundary": {"met": True,
                         "quotes": ["stops holding once the coupling is "
                                    "strong"]},
        },
    }
    doc.update(over)
    return doc


def item(**over):
    doc = {
        "schema_version": 1,
        "exercise_id": "e1",
        "course_id": "linalg",
        "concept_ids": ["x.y"],
        "tier": "modeling",
        "prompt": "Where does this method stop working, and why?",
        "grader": {"type": "rubric"},
        "rubric_id": "r1",
    }
    doc.update(over)
    return doc


class TestTheMarkerIsGivenAlmostNothing:
    def test_the_package_carries_the_item_criteria_and_answer(self):
        pkg = gr.package(item(), rubric(), ANSWER)
        assert pkg["item"]["prompt"]
        assert pkg["rubric"]["criteria"]
        assert pkg["answer"] == ANSWER

    def test_the_teaching_transcript_never_goes_in(self):
        pkg = gr.package(dict(item(), transcript="we went over this twice"),
                         rubric(), ANSWER)
        assert "transcript" not in json.dumps(pkg)

    def test_who_wrote_it_never_goes_in(self):
        pkg = gr.package(dict(item(), learner_id="zep", display_name="Z"),
                         rubric(), ANSWER)
        assert gr.leaks(pkg) == []

    def test_the_package_is_built_by_whitelist(self):
        """A blacklist leaks whatever nobody thought of, and what leaks here
        is the teaching context."""
        pkg = gr.package(dict(item(), some_field_nobody_anticipated="x"),
                         rubric(), ANSWER)
        assert "some_field_nobody_anticipated" not in json.dumps(pkg)

    def test_every_withheld_field_says_why(self):
        for key, why in gr.WITHHELD.items():
            assert len(why) > 20, key

    def test_the_marker_is_told_it_did_not_see_the_teaching(self):
        pkg = gr.package(item(), rubric(), ANSWER)
        joined = " ".join(pkg["instructions"])
        assert "did not see this being taught" in joined
        assert "do not know who wrote it" in joined

    def test_the_leak_check_catches_a_bad_package(self):
        bad = {"item": {}, "rubric": {}, "answer": "x",
               "transcript": "the whole lesson"}
        assert gr.leaks(bad) == ["transcript"]


class TestAPassHasToQuoteSomething:
    def test_a_criterion_met_with_no_quote_is_refused(self):
        v = verdict()
        v["criteria_met"]["boundary"] = {"met": True}
        r = refusal(lambda: gr.check_verdict(v, rubric(), ANSWER))
        assert r.code == "GRD002"
        assert "was not met" in r.suggestion

    def test_a_quote_that_is_not_in_the_answer_is_refused(self):
        """A marker under pressure to pass can produce a quote that is a
        paraphrase, or a sentence it wishes were there. Both read
        convincingly and neither is in the text, so the quotes are checked
        rather than trusted."""
        v = verdict()
        v["criteria_met"]["boundary"]["quotes"] = [
            "the learner clearly understands the limits"]
        r = refusal(lambda: gr.check_verdict(v, rubric(), ANSWER))
        assert r.code == "GRD003"
        assert "not the learner's" in r.suggestion

    def test_a_paraphrase_is_caught_even_when_it_is_fair(self):
        v = verdict()
        v["criteria_met"]["boundary"]["quotes"] = [
            "the approximation fails at strong coupling"]
        assert refusal(
            lambda: gr.check_verdict(v, rubric(), ANSWER)).code == "GRD003"

    def test_quoting_is_tolerant_of_whitespace_and_case(self):
        v = verdict()
        v["criteria_met"]["sets-up"]["quotes"] = [
            "Set  up   the\ncharacteristic polynomial"]
        assert gr.check_verdict(v, rubric(), ANSWER)["ok"]

    def test_an_unmet_criterion_needs_no_quote(self):
        v = verdict(verdict="fail")
        v["criteria_met"]["boundary"] = {"met": False}
        assert gr.check_verdict(v, rubric(), ANSWER)["ok"]

    def test_marking_against_criteria_that_do_not_exist_is_refused(self):
        v = verdict()
        v["criteria_met"]["invented"] = {"met": True, "quotes": ["I"]}
        assert refusal(
            lambda: gr.check_verdict(v, rubric(), ANSWER)).code == "GRD001"

    def test_a_well_supported_verdict_passes(self):
        assert gr.check_verdict(verdict(), rubric(), ANSWER)["ok"]


class TestTheMustHaveCriteria:
    def test_a_pass_missing_a_must_have_is_refused(self):
        v = verdict()
        v["criteria_met"]["boundary"] = {"met": False}
        r = refusal(lambda: gr.check_verdict(v, rubric(), ANSWER))
        assert r.code == "GRD004"
        assert "what the item exists to test" in r.suggestion

    def test_partial_credit_cannot_substitute_for_one(self):
        """Without this, a confident answer that misses the point of the item
        collects enough partial credit to pass."""
        rb = rubric()
        rb["criteria"][0]["weight"] = 10
        v = verdict(verdict="fail")
        v["criteria_met"]["boundary"] = {"met": False}
        out = gr.score(v, rb)
        assert out["fraction"] > out["threshold"]
        assert out["passes"] is False
        assert any("must-have" in w for w in out["why_not"])

    def test_both_conditions_must_hold(self):
        v = verdict(verdict="fail")
        v["criteria_met"]["sets-up"] = {"met": False}
        out = gr.score(v, rubric())
        assert out["required_all_met"] is True
        assert out["passes"] is True

    def test_a_clean_pass_scores_as_one(self):
        out = gr.score(verdict(), rubric())
        assert out["passes"] is True
        assert out["why_not"] == []


class TestDepthIsWhatWasShownNotWhatWasHopedFor:
    def test_the_deepest_met_criterion_is_the_depth(self):
        assert gr.depth_shown(verdict(), rubric()) == 4

    def test_passing_only_the_shallow_criteria_records_the_shallow_depth(
            self):
        """An item written for depth 4 that was passed on its shallower
        criteria proved depth 3 at most. Recording the intention instead of
        the demonstration is how a concept drifts past its target with nobody
        noticing."""
        v = verdict(verdict="fail")
        v["criteria_met"]["boundary"] = {"met": False}
        assert gr.depth_shown(v, rubric()) == 2

    def test_nothing_met_is_depth_zero(self):
        v = {"verdict": "fail", "criteria_met": {}}
        assert gr.depth_shown(v, rubric()) == 0


class TestTheRubricItself:
    def test_a_rubric_validates(self):
        assert zs.validate_doc(rubric(), "rubric") == []

    def test_a_criterion_must_say_what_passing_looks_like(self):
        rb = rubric()
        del rb["criteria"][0]["evidence_looks_like"]
        errs = zs.validate_doc(rb, "rubric")
        assert any("evidence_looks_like" in e for e in errs)

    def test_it_lists_what_must_not_count_as_evidence(self):
        """Each of these reads as competence, which is why they are named."""
        assert rubric()["not_evidence"]


class TestCli:
    def run(self, argv):
        try:
            return gr.main(argv)
        except SystemExit as exc:
            return exc.code

    def files(self, tmp_path, v=None, rb=None, ans=None):
        (tmp_path / "item.json").write_text(json.dumps(item()),
                                            encoding="utf-8")
        (tmp_path / "rubric.json").write_text(json.dumps(rb or rubric()),
                                              encoding="utf-8")
        (tmp_path / "answer.txt").write_text(ans or ANSWER, encoding="utf-8")
        (tmp_path / "verdict.json").write_text(json.dumps(v or verdict()),
                                               encoding="utf-8")
        return [str(tmp_path / n) for n in
                ("item.json", "rubric.json", "answer.txt", "verdict.json")]

    def test_package_prints_the_markers_input(self, tmp_path, capsys):
        i, rb, a, _ = self.files(tmp_path)
        assert self.run(["package", "--item", i, "--rubric", rb,
                         "--answer", a]) == zs.EXIT_OK
        out = json.loads(capsys.readouterr().out)
        assert set(out) == {"item", "rubric", "answer", "instructions"}

    def test_check_reports_a_pass_with_the_numbers(self, tmp_path, capsys):
        i, rb, a, v = self.files(tmp_path)
        assert self.run(["check", "--verdict", v, "--rubric", rb,
                         "--answer", a]) == zs.EXIT_OK
        out = capsys.readouterr().out
        assert "VERDICT  pass" in out
        assert "%" in out

    def test_an_unsupported_verdict_exits_three(self, tmp_path, capsys):
        v = verdict()
        v["criteria_met"]["boundary"] = {"met": True}
        i, rb, a, vf = self.files(tmp_path, v=v)
        assert self.run(["check", "--verdict", vf, "--rubric", rb,
                         "--answer", a]) == zs.EXIT_GATE
        assert "GRD002" in capsys.readouterr().err

    def test_withheld_explains_each_exclusion(self, capsys):
        assert self.run(["withheld"]) == zs.EXIT_OK
        out = capsys.readouterr().out
        assert "transcript" in out
        assert "lenient reading" in out
