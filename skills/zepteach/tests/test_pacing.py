"""Four defects from the first internal test, each one a thing nobody owned.

Asking everything before starting. Reading a slip as a gap. Nothing deciding
when a lesson was over. Counting time the learner was absent as time they
studied.

They look unrelated. They share a shape: a judgement the system left to
whoever happened to be teaching, at the moment when the wrong answer felt
most reasonable. Going deeper feels responsible. Asking one more question
feels thorough. A wrong number is a wrong answer. An hour on the clock is an
hour. Each is right often enough to be believed and wrong often enough to
matter, which is why none of them belongs to a judgement call made in the
middle of a lesson.
"""

import json

import pytest

import conftest as fx
import constants as K
import curriculum as cur
import grade
import intake
import learner as ln
import review as rv
import session as se
import zt_state as zs


class TestTheOpeningInterviewAsksOneQuestion:
    """It asked nine, in one message. The learner's first complaint was
    exactly that: too much at once, split it into groups and ask each group
    when it matters."""

    def test_only_the_language_blocks_starting(self, tmp_path):
        ids = [q["id"] for q in intake.blocking(tmp_path, "start")]
        assert ids == ["teaching_language"]

    def test_the_course_questions_wait_for_a_course(self, tmp_path):
        later = [q["id"] for q in intake.blocking(tmp_path, "course")]
        assert set(later) == {"purpose", "depth_expectation", "background",
                              "pacing"}
        assert "purpose" not in [q["id"]
                                 for q in intake.blocking(tmp_path, "start")]

    def test_nothing_is_in_a_group_by_accident(self):
        for q in intake.QUESTIONS:
            assert q.get("group") in intake.GROUPS, q["id"]
            assert q.get("blocks"), q["id"]

    def test_the_tone_question_is_gone(self):
        """They said not to ask it: if the tone is wrong they will say so.
        Asking someone to pick a number between formal and friendly, before
        any teaching has happened, asks them to predict their own preference
        about something they have not experienced yet."""
        assert "address" not in [q["id"] for q in intake.QUESTIONS]

    def test_notes_are_placed_and_announced_rather_than_asked_about(self):
        cfg, _ = intake.build({"teaching_language": "zh-CN"})
        assert cfg["notes"]["markdown_dir"]
        q = [q for q in intake.QUESTIONS if q["id"] == "notes"][0]
        assert q["required"] is False
        assert "Say the word" in q["ask"]

    def test_the_two_optional_ones_are_never_asked_proactively(self, tmp_path):
        assert intake.still_needed(tmp_path)["never"] == \
            ["source_languages", "constraints"]


class TestASlipIsNotAGap:
    """A learner was retested three times on one concept, each retest set off
    by a different arithmetic error, until they wrote: those were calculation
    mistakes, I am clear on the concepts."""

    def rubric(self):
        return {"criteria": [
            {"criterion_id": "method", "kind": "concept",
             "requires": "uses the projection formula",
             "evidence_looks_like": "a.b over |b|"},
            {"criterion_id": "arithmetic", "kind": "execution",
             "requires": "computes it correctly",
             "evidence_looks_like": "6/5"},
        ]}

    def verdict(self, method=True, arithmetic=False):
        return {"criteria_met": {
            "method": {"met": method, "quotes": ["a.b over |b|"]},
            "arithmetic": {"met": arithmetic, "quotes": []}}}

    def test_the_idea_held_and_the_execution_did_not(self):
        got = grade.failure_kind(self.verdict(), self.rubric())
        assert got["execution_only"] is True
        assert got["unmet_execution"] == ["arithmetic"]
        assert "one local correction" in got["what_to_do"]

    def test_a_real_gap_is_not_dressed_up_as_a_slip(self):
        got = grade.failure_kind(self.verdict(method=False), self.rubric())
        assert got["execution_only"] is False
        assert "came apart" in got["what_to_do"]

    def test_unmarked_criteria_behave_exactly_as_before(self):
        """Every existing rubric is unmarked. The distinction has to be
        opt-in, or adding it silently reclassifies old records."""
        plain = {"criteria": [{"criterion_id": "c", "requires": "r",
                               "evidence_looks_like": "e"}]}
        got = grade.failure_kind({"criteria_met": {"c": {"met": False}}},
                                 plain)
        assert got["execution_only"] is False

    def test_a_slip_does_not_move_a_concept_backwards(self):
        from datetime import datetime, timezone
        taught = datetime(2026, 9, 1, tzinfo=timezone.utc)
        now = datetime(2026, 9, 20, tzinfo=timezone.utc)
        slipped, why = rv.next_state("practiced", "delayed_retest", "fail",
                                     taught, now, {}, "fluent",
                                     execution_only=True)
        assert slipped == "practiced"
        assert "otherwise move on" in why
        gap, _ = rv.next_state("practiced", "delayed_retest", "fail",
                               taught, now, {}, "fluent")
        assert gap == "shaky"

    def test_a_failed_inclass_item_does_not_erase_delayed_evidence(self):
        from datetime import datetime, timezone
        taught = datetime(2026, 9, 1, tzinfo=timezone.utc)
        now = datetime(2026, 9, 20, tzinfo=timezone.utc)
        state, _ = rv.next_state("consolidating", "inclass", "fail",
                                 taught, now, {})
        assert state == "consolidating"
        base = fx.mastery(state="consolidating", scheduling={
            "algorithm": "sm2", "interval_days": 12.0, "reps": 3,
            "ease": 2.5, "next_due": "2026-10-01T10:00:00+00:00"})
        before = dict(base["scheduling"])
        after = rv.apply_evidence(base, {
            "attempt_id": "inclass-miss", "course_id": "linalg",
            "kind": "inclass", "verdict": "fail",
            "date": "2026-09-20T10:00:00+00:00"}, {})
        assert after["state"] == "consolidating"
        assert after["scheduling"] == before

    def test_a_slip_does_not_shorten_the_next_interval_either(self):
        """The scheduling half of the same mistake: a retest they did not
        need, and sooner than the one they did."""
        base = fx.mastery(state="practiced", scheduling={
            "algorithm": "sm2", "interval_days": 12.0, "reps": 3,
            "ease": 2.5, "next_due": "2026-10-01T10:00:00+00:00"})
        before = dict(base["scheduling"])
        after = rv.apply_evidence(base, {
            "attempt_id": "slip", "course_id": "linalg",
            "kind": "delayed_retest", "verdict": "fail",
            "date": "2026-09-20T10:00:00+00:00",
            "latency_rating": "fluent", "execution_only": True}, {})
        assert after["state"] == "practiced"
        assert after["scheduling"] == before
        assert after["evidence"][-1]["execution_only"] is True

    def test_it_does_not_promote_either(self):
        from datetime import datetime, timezone
        taught = datetime(2026, 9, 1, tzinfo=timezone.utc)
        now = datetime(2026, 9, 20, tzinfo=timezone.utc)
        state, _ = rv.next_state("practiced", "delayed_retest", "partial",
                                 taught, now, {}, "fluent",
                                 execution_only=True)
        assert state == "practiced", "a slip is not a clean answer"

    def test_the_flag_reaches_the_record(self, root):
        fx.teach(root)
        ln.main(["--root", str(root), "record", "--course", "linear-algebra",
                 "--data", json.dumps(_slip())])
        row = ln.load_mastery(root)[0]
        assert row["evidence"][-1].get("execution_only") is True


def _slip():
    a = fx.attempt(verdict="fail", execution_only=True,
                   failure_points=["wrote 6/5 where the working says 5/6"],
                   submitted_at="2026-09-20T10:00:00+00:00")
    a.pop("evidence_quotes", None)
    return a


class TestALessonEndsOnPurpose:
    """One lesson ran four hours, on a course with five weeks to cover
    seventy-eight concepts. Nothing was wrong with the teaching in it.
    Nothing decided it was over, and going deeper always feels like the
    responsible choice from inside the lesson."""

    def test_advancing_is_refused_while_the_lesson_is_unfinished(
            self, root, capsys):
        code = cur.main(["--root", str(root), "advance",
                         "--course", "linear-algebra", "--lesson", "l1"])
        assert code == zs.EXIT_GATE
        err = capsys.readouterr().err
        assert "never explained" in err
        assert "curriculum.py defer" in err

    def test_leaving_part_of_it_is_allowed_once_it_is_recorded(self, root,
                                                              capsys):
        _cdir, _course, curriculum, rows = cur._load(root, "linear-algebra")
        wanted = cur.lesson_progress(root, "linear-algebra", curriculum,
                                     "l1", rows)["concepts"]
        assert cur.main(["--root", str(root), "defer",
                         "--course", "linear-algebra", "--lesson", "l1",
                         "--concepts", ",".join(wanted),
                         "--because", "he needs the later material first"]) \
            == zs.EXIT_OK
        capsys.readouterr()
        assert cur.main(["--root", str(root), "advance",
                         "--course", "linear-algebra", "--lesson", "l1"]) \
            == zs.EXIT_OK

    def test_a_deferral_records_the_reason_in_their_words(self, root):
        cur.main(["--root", str(root), "defer", "--course", "linear-algebra",
                  "--lesson", "l1", "--concepts", fx.EIGENVALUE,
                  "--because", "I only need this for the exam"])
        rows = zs.read_jsonl(root / "courses" / "linear-algebra" /
                             "deferrals.jsonl")
        assert rows[0]["because"] == "I only need this for the exam"

    def test_explained_but_never_said_back_still_counts_as_unfinished(
            self, root):
        for cid in (fx.EIGENVALUE, fx.EIGENVECTOR, fx.SHARED):
            fx.teach(root, cid)
        _cdir, _course, curriculum, rows = cur._load(root, "linear-algebra")
        st = cur.lesson_progress(root, "linear-algebra", curriculum, "l1",
                                 rows)
        assert st["not_explained"] == []
        assert st["owes_explain_back"], (
            "an explanation nobody has said back is not a finished concept")

    def test_running_long_is_reported_not_refused(self):
        st = {"estimated_minutes": 60}
        assert cur.pace_check(st, 240)["over"] is True
        assert cur.pace_check(st, 70)["over"] is False
        assert cur.pace_check({}, 240)["known"] is False

    def test_the_overrun_ratio_says_where_it_came_from(self):
        entry = K.TUNABLE["lesson_overrun_ratio"]
        assert entry["kind"] == "engineering"
        assert "four hours" in entry["why"]


class TestTimeAwayIsNotStudyTime:
    """The learner said it twice in one session, unprompted: I left for a
    long time, the elapsed time means nothing. Both times the system had
    already counted it."""

    def test_elapsed_and_studied_are_two_different_numbers(self):
        props = zs.load_schema("session")["properties"]
        assert "elapsed_minutes" in props
        assert "away" in props

    def test_a_long_silence_is_asked_about_rather_than_assumed(self, root,
                                                              capsys):
        sid = _open(root, capsys)
        path = _session_path(root, sid)
        doc = zs.read_json(path)
        doc["last_turn_at"] = "2026-01-01T00:00:00+00:00"
        zs.atomic_write_json(path, doc)
        se.main(["--root", str(root), "turn", "--session", sid])
        out = capsys.readouterr().out
        assert "GAP:" in out
        assert "Do not guess" in out

    def test_recording_it_takes_it_out_of_the_study_time(self, root, capsys):
        sid = _open(root, capsys)
        se.main(["--root", str(root), "turn", "--session", sid,
                 "--away", "90"])
        se.main(["--root", str(root), "close", "--session", sid,
                 "--reason", "completed"])
        doc = zs.read_json(_session_path(root, sid))
        assert doc["actual_minutes"] == 0
        assert doc["elapsed_minutes"] >= 0
        assert doc["away"][0]["minutes"] == 90

    def test_the_gap_threshold_says_where_it_came_from(self):
        entry = K.TUNABLE["idle_gap_minutes"]
        assert entry["kind"] == "engineering"
        assert "no study supports" in entry["source"]

    def test_review_intervals_still_run_on_the_calendar(self):
        """The one thing elapsed time is right for. Somebody who was away
        for a week has forgotten a week's worth, whether or not they were
        studying."""
        import inspect
        src = inspect.getsource(rv.compute_next_due)
        assert "away" not in src and "actual_minutes" not in src


def _open(root, capsys):
    se.main(["--root", str(root), "open", "--course", "linear-algebra",
             "--energy", "normal"])
    out = capsys.readouterr().out
    for line in out.splitlines():
        if line.startswith("session "):
            return line.split()[1]
    raise AssertionError("no session id in:\n" + out)


def _session_path(root, sid):
    return (root / "courses" / "linear-algebra" / "sessions" / sid /
            "session.json")
