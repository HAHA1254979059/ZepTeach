"""The opening interview.

The failure this file guards against is an interview that keeps growing.
Every question looks reasonable on its own, and a long questionnaire before
any teaching happens is its own kind of failure. So the tests check not only
that the right things are asked, but that specific things are not.
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import conftest as fx  # noqa: E402
import intake  # noqa: E402
import zt_state as zs  # noqa: E402


def run(argv):
    try:
        return intake.main(argv)
    except SystemExit as exc:
        return exc.code


def full_answers(**over):
    doc = {
        "teaching_language": "zh-CN",
        "display_name": "Z",
        "address": {"name": "Zep", "closeness": 4, "banter": 2},
        "notes": {"markdown_dir": "E:/notes",
                  "document_dir": "E:/docs",
                  "journal_dir": "E:/notes/journal"},
        "purpose": {"statement": "preparing to do research in this area",
                    "motivation": "research"},
        "depth_expectation": 4,
        "background": [{"domain": "mathematics", "level": "working"}],
        "pacing": {"weekly_minutes": 300, "preferred_session_minutes": 45},
        "source_languages": ["zh", "en"],
    }
    doc.update(over)
    return doc


class TestWhatIsAsked:
    def test_the_teaching_language_is_asked_and_never_defaulted(self):
        """The one setting where choosing on someone's behalf decides how
        every explanation they ever read will sound."""
        q = [q for q in intake.QUESTIONS if q["id"] == "teaching_language"][0]
        assert q["required"]
        config, _ = intake.build(full_answers(teaching_language=None))
        assert "teaching_language" not in config

    def test_writing_without_a_language_is_refused(self, tmp_path):
        answers = full_answers()
        del answers["teaching_language"]
        code = run(["--root", str(tmp_path), "write",
                    "--data", json.dumps(answers)])
        assert code == zs.EXIT_VALIDATION
        assert not (tmp_path / "config.json").exists()

    def test_why_they_are_learning_is_asked_because_it_cannot_be_measured(
            self):
        q = [q for q in intake.QUESTIONS if q["id"] == "purpose"][0]
        assert q["required"]
        assert "cannot be measured later" in q["why"]

    def test_the_interview_stays_short(self):
        """Not an arbitrary cap. Every question here delays the first lesson,
        and the evidence says most of what a tutor wants to know is better
        established by watching the learner work."""
        assert len(intake.QUESTIONS) <= 10
        required = [q for q in intake.QUESTIONS if q["required"]]
        assert len(required) <= 6


class TestWhatIsDeliberatelyNotAsked:
    def test_nothing_asks_the_learner_to_rate_their_own_level(self):
        """Self-rated level correlates at about zero with measured level and
        runs consistently high. An answer would look like information and be
        used as if it were, which is worse than having none."""
        for q in intake.QUESTIONS:
            text = (q["ask"] + " " + q["why"]).lower()
            for phrase in ("how well do you know", "rate yourself",
                           "out of five", "on a scale of"):
                assert phrase not in text

    def test_the_background_question_says_not_to_ask_how_well(self):
        q = [q for q in intake.QUESTIONS if q["id"] == "background"][0]
        assert "Do not ask how well" in q["never"]

    def test_equipment_is_left_to_the_second_stage(self):
        """It depends on what they decide to study, and that has not
        happened yet."""
        ids = {q["id"] for q in intake.QUESTIONS}
        assert "equipment" not in ids
        deferred = {d["id"] for d in intake.DEFERRED}
        assert "equipment_and_material" in deferred

    def test_every_deferred_question_says_where_it_went(self):
        for d in intake.DEFERRED:
            assert d["instead"].strip()


class TestNothingIsAskedTwice:
    def test_a_fresh_root_knows_nothing(self, tmp_path):
        assert intake.known(tmp_path)["answered"] == {}
        assert len(intake.remaining(tmp_path)) == len(intake.QUESTIONS)

    def test_what_was_answered_before_is_not_asked_again(self, tmp_path):
        run(["--root", str(tmp_path), "write",
             "--data", json.dumps(full_answers())])
        left = {q["id"] for q in intake.remaining(tmp_path)}
        assert "teaching_language" not in left
        assert "purpose" not in left
        assert "pacing" not in left

    def test_an_existing_root_reports_stage_one_as_done(self, root):
        assert intake.known(root)["stage1_done"] is True


class TestWhatGetsStored:
    def test_a_stated_level_is_recorded_as_self_declared(self, tmp_path):
        """Whatever the learner sounded like when they said it. Upgrading to
        probe_verified later requires evidence, and the distinction has to
        start somewhere."""
        _, profile = intake.build(full_answers())
        assert profile["background"][0]["basis"] == "self_declared"

    def test_a_self_declared_level_is_flagged_if_the_basis_is_missing(self):
        prof = fx.profile(background=[{"domain": "maths", "level": "expert"}])
        codes = [f.code for f in zs.rule_profile(prof, "p")]
        assert "PRF001" in codes

    def test_claiming_a_probe_verified_level_requires_saying_what_proved_it(
            self):
        prof = fx.profile(background=[
            {"domain": "maths", "level": "expert", "basis": "probe_verified"}])
        codes = [f.code for f in zs.rule_profile(prof, "p")]
        assert "PRF002" in codes

    def test_a_depth_expectation_without_a_reason_is_flagged(self):
        prof = fx.profile(depth_expectation=5)
        codes = [f.code for f in zs.rule_profile(prof, "p")]
        assert "PRF003" in codes

    def test_both_documents_validate(self, tmp_path):
        config, profile = intake.build(full_answers())
        assert zs.validate_doc(config, "config") == []
        assert zs.validate_doc(profile, "profile") == []

    def test_a_missing_answer_stays_missing_rather_than_being_invented(self):
        answers = full_answers()
        del answers["purpose"]
        _, profile = intake.build(answers)
        assert "purpose" not in profile


class TestCli:
    def test_known_on_an_empty_root_says_so(self, tmp_path, capsys):
        assert run(["--root", str(tmp_path), "known"]) == zs.EXIT_OK
        assert "this is a first setup" in capsys.readouterr().out

    def test_questions_prints_the_prohibition_alongside_the_question(
            self, tmp_path, capsys):
        run(["--root", str(tmp_path), "questions"])
        out = capsys.readouterr().out
        assert "DO NOT:" in out
        assert "NOT ASKED HERE" in out

    def test_after_writing_nothing_required_is_still_outstanding(
            self, tmp_path):
        """Optional questions may remain - an unanswered optional question is
        a preference nobody has expressed, not a gap."""
        assert run(["--root", str(tmp_path), "write",
                    "--data", json.dumps(full_answers())]) == zs.EXIT_OK
        left = intake.remaining(tmp_path)
        assert [q["id"] for q in left if q["required"]] == []
        assert [q["id"] for q in left] == ["notation_input",
                                           "constraints"]

    def test_the_written_root_passes_a_full_check(self, tmp_path):
        zs.main(["--root", str(tmp_path), "init"])
        run(["--root", str(tmp_path), "write",
             "--data", json.dumps(full_answers())])
        errors = [f for f in zs.validate_root(tmp_path)
                  if f.severity == "error"]
        assert errors == []

    def test_it_points_at_the_next_step_without_doing_it(self, tmp_path,
                                                         capsys):
        run(["--root", str(tmp_path), "write",
             "--data", json.dumps(full_answers())])
        out = capsys.readouterr().out
        assert "able to DO" in out
        assert "milestones" in out
