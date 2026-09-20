"""Tests for adaptive review scheduling.

The thing being pinned down here is that the schedule follows the evidence.
Same verdict, different recall effort, different next date. And no amount of
in-session success shortcuts the gap that consolidation actually needs.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import review as rv  # noqa: E402
import zt_state as zs  # noqa: E402
import conftest as fx  # noqa: E402

MIN_DAYS = {"delayed_retest_min_days": 3, "transfer_test_min_days": 7}


def dt(s):
    return zs._parse_dt(s)


class TestGrading:
    def test_effort_separates_two_correct_answers(self):
        assert rv.grade_of("pass", "instant") > rv.grade_of("pass", "effortful")
        assert rv.grade_of("pass", "effortful") > \
            rv.grade_of("pass", "recovered_with_hint")

    def test_a_failed_recall_scores_zero_however_quick(self):
        for lat in ("instant", "fluent", "effortful", "recovered_with_hint"):
            assert rv.grade_of("fail", lat) == 0

    def test_partial_never_counts_as_a_successful_recall(self):
        for lat in ("instant", "fluent", "effortful", "recovered_with_hint"):
            assert rv.grade_of("partial", lat) < rv.PASSING_GRADE

    def test_an_unrated_recall_is_assumed_to_have_taken_work(self):
        assert rv.grade_of("pass") == rv.grade_of("pass", "effortful")

    def test_recovered_with_hint_is_not_a_clean_pass(self):
        assert rv.grade_of("pass", "recovered_with_hint") < rv.PASSING_GRADE


class TestIntervalUpdate:
    def test_a_confident_recall_pushes_the_interval_out(self):
        s = rv.update_scheduling({"ease": 2.5, "reps": 2, "interval_days": 6},
                                 rv.grade_of("pass", "instant"))
        assert s["interval_days"] > 6
        assert s["ease"] > 2.5

    def test_an_effortful_recall_grows_it_far_less(self):
        easy = rv.update_scheduling({"ease": 2.5, "reps": 2, "interval_days": 6},
                                    rv.grade_of("pass", "instant"))
        hard = rv.update_scheduling({"ease": 2.5, "reps": 2, "interval_days": 6},
                                    rv.grade_of("pass", "effortful"))
        assert hard["interval_days"] < easy["interval_days"]
        assert hard["ease"] < easy["ease"]

    def test_effort_separates_the_very_first_interval_too(self):
        # the opening interval is where the effort signal matters most, so it
        # is graded rather than fixed
        seen = set()
        for lat in ("effortful", "fluent", "instant"):
            s = rv.update_scheduling({"reps": 0}, rv.grade_of("pass", lat))
            seen.add(s["interval_days"])
        assert len(seen) == 3

    def test_a_lapse_resets_the_ladder_and_counts(self):
        s = rv.update_scheduling({"ease": 2.5, "reps": 5, "interval_days": 40,
                                  "lapses": 1}, 0)
        assert s["interval_days"] == 1.0
        assert s["reps"] == 0
        assert s["lapses"] == 2
        assert s["ease"] < 2.5

    def test_ease_is_clamped_at_both_ends(self):
        s = {"ease": rv.MIN_EASE, "reps": 3, "interval_days": 10}
        for _ in range(10):
            s = rv.update_scheduling(s, 0)
        assert s["ease"] == rv.MIN_EASE
        s = {"ease": rv.MAX_EASE, "reps": 3, "interval_days": 10}
        for _ in range(10):
            s = rv.update_scheduling(s, 5)
        assert s["ease"] == rv.MAX_EASE

    def test_difficulty_tracks_a_concept_that_keeps_fighting_back(self):
        easy = rv.update_scheduling({"ease": 2.5, "reps": 2, "interval_days": 6}, 5)
        s = {"ease": 2.5, "reps": 2, "interval_days": 6}
        for _ in range(3):
            s = rv.update_scheduling(s, 0)
        assert s["difficulty"] > easy["difficulty"]

    def test_the_opening_ladder_is_short_and_then_hands_over_to_ease(self):
        s = rv.update_scheduling({"reps": 0}, 4)
        assert s["interval_days"] == 2.0
        s = rv.update_scheduling(s, 4)
        assert s["interval_days"] == 6.0
        s = rv.update_scheduling(s, 4)
        assert s["interval_days"] > 6.0

    def test_the_interval_never_runs_away_in_one_step(self):
        s = rv.update_scheduling({"ease": 2.5, "reps": 3,
                                  "interval_days": 20}, 5)
        assert s["interval_days"] < 20 * 3

    def test_nothing_drops_off_the_radar_for_a_year(self):
        s = {"ease": rv.MAX_EASE, "reps": 9, "interval_days": 170}
        for _ in range(5):
            s = rv.update_scheduling(s, 5)
            assert s["interval_days"] <= rv.MAX_INTERVAL_DAYS

    def test_fsrs_is_declared_but_not_pretended(self):
        with pytest.raises(NotImplementedError):
            rv.update_scheduling({}, 4, algorithm="fsrs")


class TestLateCredit:
    """Recalling something that was already overdue says the interval was too
    short, so part of the lateness is credited back before it grows."""

    def test_a_late_instant_recall_grows_more_than_an_on_time_one(self):
        base = {"ease": 2.5, "reps": 3, "interval_days": 20}
        on_time = rv.update_scheduling(dict(base), 5, days_late=0)
        late = rv.update_scheduling(dict(base), 5, days_late=20)
        assert late["interval_days"] > on_time["interval_days"]

    def test_a_late_effortful_recall_gets_no_credit(self):
        base = {"ease": 2.5, "reps": 3, "interval_days": 20}
        assert rv.update_scheduling(dict(base), 3, days_late=20)[
            "interval_days"] == rv.update_scheduling(dict(base), 3)[
            "interval_days"]

    def test_a_fluent_recall_gets_half_the_credit(self):
        base = {"ease": 2.5, "reps": 3, "interval_days": 20}
        none = rv.update_scheduling(dict(base), 4)["interval_days"]
        half = rv.update_scheduling(dict(base), 4, days_late=20)["interval_days"]
        full = rv.update_scheduling({"ease": 2.5, "reps": 3,
                                     "interval_days": 40}, 4)["interval_days"]
        assert none < half < full

    def test_a_failed_late_review_gets_no_credit_at_all(self):
        s = rv.update_scheduling({"ease": 2.5, "reps": 3,
                                  "interval_days": 20}, 0, days_late=60)
        assert s["interval_days"] == 1.0

    def test_lateness_is_measured_from_the_due_date(self):
        m = fx.mastery(state="practiced")
        m["scheduling"] = {"ease": 2.5, "reps": 3, "interval_days": 20,
                           "next_due": "2026-09-10T10:00:00+00:00"}
        ev = {"attempt_id": "x", "kind": "delayed_retest", "verdict": "pass",
              "latency_rating": "instant", "date": "2026-09-30T10:00:00+00:00"}
        out = rv.apply_evidence(m, ev, MIN_DAYS)
        assert out["scheduling"]["interval_days"] > 20 * 2.6


class TestBacklogOrdering:
    """Clearing a backlog oldest-first is a documented mistake: something
    already forgotten has to be relearned either way, while something still
    barely held is saved cheaply right now."""

    def test_retrievability_falls_as_a_review_gets_later(self):
        assert rv.retrievability(0, 10) == 1.0
        assert rv.retrievability(10, 10) == pytest.approx(0.9)
        assert rv.retrievability(40, 10) < rv.retrievability(20, 10)

    def test_a_short_interval_decays_faster_in_relative_terms(self):
        # five days late on a two-day interval is far worse than five days
        # late on a six-month one
        assert rv.retrievability(7, 2) < rv.retrievability(185, 180)

    def test_the_still_remembered_item_is_taken_first(self):
        now = dt("2026-09-20T10:00:00+00:00")
        fresh = fx.mastery("linalg.fresh", state="practiced")
        fresh["scheduling"] = {"next_due": "2026-09-19T10:00:00+00:00",
                               "last_review": "2026-09-09T10:00:00+00:00",
                               "interval_days": 10}
        stale = fx.mastery("linalg.stale", state="practiced")
        stale["scheduling"] = {"next_due": "2026-06-01T10:00:00+00:00",
                               "last_review": "2026-05-30T10:00:00+00:00",
                               "interval_days": 2}
        q = rv.build_queue("linalg", [fresh, stale], {"modules": []},
                           MIN_DAYS, now)
        assert q["items"][0]["concept_id"] == "linalg.fresh"

    def test_something_blocking_a_lesson_still_jumps_the_queue(self):
        now = dt("2026-09-20T10:00:00+00:00")
        fresh = fx.mastery(fx.EIGENVECTOR, state="practiced")
        fresh["scheduling"] = {"next_due": "2026-09-19T10:00:00+00:00",
                               "last_review": "2026-09-19T10:00:00+00:00",
                               "interval_days": 10}
        blocking = fx.mastery(fx.EIGENVALUE, state="shaky",
                              downstream={"hold": True})
        blocking["scheduling"] = {"next_due": "2026-06-01T10:00:00+00:00",
                                  "last_review": "2026-05-30T10:00:00+00:00",
                                  "interval_days": 2}
        q = rv.build_queue("linalg", [fresh, blocking], fx.curriculum(),
                           MIN_DAYS, now)
        assert q["items"][0]["concept_id"] == fx.EIGENVALUE
        assert q["items"][0]["kind"] == "repair"


class TestBacklogBands:
    def _queue(self, n, now):
        rows = []
        for i in range(n):
            m = fx.mastery("linalg.c" + str(i), state="practiced")
            m["scheduling"] = {"next_due": "2026-01-01T00:00:00+00:00",
                               "last_review": "2025-12-25T00:00:00+00:00",
                               "interval_days": 7}
            rows.append(m)
        return rv.build_queue("linalg", rows, {"modules": []}, MIN_DAYS, now)

    def test_a_small_debt_changes_nothing(self):
        now = dt("2026-09-20T10:00:00+00:00")
        s = rv.backlog_status(self._queue(5, now), cap=8, now=now)
        assert s["band"] == "manageable"
        assert s["new_material_allowed"] is True

    def test_a_moderate_debt_still_teaches_something_new(self):
        now = dt("2026-09-20T10:00:00+00:00")
        s = rv.backlog_status(self._queue(16, now), cap=8, now=now)
        assert s["band"] == "moderate"
        assert s["new_material_allowed"] is True
        assert s["review_share"] > 0.5

    def test_a_severe_debt_pauses_new_material(self):
        now = dt("2026-09-20T10:00:00+00:00")
        s = rv.backlog_status(self._queue(40, now), cap=8, now=now)
        assert s["band"] == "severe"
        assert s["new_material_allowed"] is False
        assert "do not reschedule" in s["advice"]

    def test_only_a_session_worth_is_taken_at_a_time(self):
        now = dt("2026-09-20T10:00:00+00:00")
        s = rv.backlog_status(self._queue(40, now), cap=8, now=now)
        assert s["take_this_session"] == 8
        assert s["due_now"] == 40

    def test_the_debt_is_never_silently_rescheduled(self):
        now = dt("2026-09-20T10:00:00+00:00")
        q = self._queue(40, now)
        before = [i["due"] for i in q["items"]]
        rv.backlog_status(q, cap=8, now=now)
        assert [i["due"] for i in q["items"]] == before


class TestRetirement:
    def _ev(self, day, latency="instant", verdict="pass"):
        return {"attempt_id": "a" + str(day), "kind": "delayed_retest",
                "verdict": verdict,
                "date": "2026-1" + str(day) + "-01T10:00:00+00:00",
                "latency_rating": latency}

    def test_three_instant_recalls_retire_a_mastered_concept(self):
        m = fx.mastery(state="mastered")
        m["evidence"] = [self._ev(d) for d in (1, 2, 3)]
        assert rv.should_retire(m)

    def test_two_is_not_enough(self):
        m = fx.mastery(state="mastered")
        m["evidence"] = [self._ev(d) for d in (1, 2)]
        assert not rv.should_retire(m)

    def test_anything_less_than_instant_breaks_the_streak(self):
        m = fx.mastery(state="mastered")
        m["evidence"] = [self._ev(1), self._ev(2, "fluent"), self._ev(3)]
        assert not rv.should_retire(m)

    def test_a_concept_short_of_mastered_never_retires(self):
        m = fx.mastery(state="consolidating")
        m["evidence"] = [self._ev(d) for d in (1, 2, 3, 4)]
        assert not rv.should_retire(m)

    def test_probes_do_not_break_the_streak(self):
        m = fx.mastery(state="mastered")
        m["evidence"] = [self._ev(d) for d in (1, 2, 3)]
        m["evidence"].append({"attempt_id": "p", "kind": "probe",
                              "verdict": "pass",
                              "date": "2026-12-02T10:00:00+00:00"})
        assert rv.should_retire(m)

    def test_retiring_takes_it_out_of_the_queue(self):
        now = dt("2027-01-20T10:00:00+00:00")
        m = fx.mastery(state="mastered")
        m["scheduling"] = {"next_due": "2026-12-01T10:00:00+00:00",
                           "retired": True}
        q = rv.build_queue("linalg", [m], {"modules": []}, MIN_DAYS, now)
        assert q["items"] == []

    def test_a_third_instant_recall_sets_the_flag(self):
        m = fx.mastery(state="mastered")
        m["evidence"] = [self._ev(1), self._ev(2)]
        out = rv.apply_evidence(m, self._ev(3), MIN_DAYS)
        assert out["scheduling"]["retired"] is True
        assert out["scheduling"]["retired_at"]

    def test_one_slower_answer_brings_it_straight_back(self):
        m = fx.mastery(state="mastered")
        m["evidence"] = [self._ev(1), self._ev(2)]
        m = rv.apply_evidence(m, self._ev(3), MIN_DAYS)
        assert m["scheduling"]["retired"] is True
        m = rv.apply_evidence(m, self._ev(4, "effortful"), MIN_DAYS)
        assert "retired" not in m["scheduling"]

    def test_a_retired_concept_that_fails_elsewhere_comes_back_shaky(self):
        m = fx.mastery(state="mastered")
        m["evidence"] = [self._ev(1), self._ev(2)]
        m = rv.apply_evidence(m, self._ev(3), MIN_DAYS)
        m = rv.apply_evidence(m, self._ev(4, "effortful", "fail"), MIN_DAYS)
        assert m["state"] == "shaky"
        assert "retired" not in m["scheduling"]

    def test_the_retired_record_still_validates(self):
        m = fx.mastery(state="mastered")
        m["evidence"] = [self._ev(1), self._ev(2)]
        m = rv.apply_evidence(m, self._ev(3), MIN_DAYS)
        m.pop("_transition_reason", None)
        assert zs.validate_doc(m, "mastery") == []


class TestFloors:
    def test_the_floor_pushes_an_early_due_date_out(self):
        first = dt("2026-09-01T09:00:00+00:00")
        due = rv.compute_next_due("practiced", {"interval_days": 1},
                                  first, first, MIN_DAYS)
        assert due >= first + timedelta(days=3)

    def test_a_long_interval_is_not_dragged_back_by_the_floor(self):
        first = dt("2026-09-01T09:00:00+00:00")
        due = rv.compute_next_due("practiced", {"interval_days": 30},
                                  first, first, MIN_DAYS)
        assert due == first + timedelta(days=30)

    def test_transfer_tests_sit_behind_a_longer_floor(self):
        first = dt("2026-09-01T09:00:00+00:00")
        due = rv.compute_next_due("consolidating", {"interval_days": 1},
                                  first, first, MIN_DAYS)
        assert due >= first + timedelta(days=7)

    def test_refresh_and_repair_have_no_extra_floor(self):
        assert rv.floor_days("refresh", MIN_DAYS) == 0
        assert rv.floor_days("repair", MIN_DAYS) == 0

    def test_what_is_owed_next_depends_on_where_you_are(self):
        assert rv.next_kind("practiced") == "delayed_retest"
        assert rv.next_kind("consolidating") == "transfer_test"
        assert rv.next_kind("mastered") == "refresh"
        assert rv.next_kind("shaky") == "repair"


class TestStateTransitions:
    def test_in_session_success_reaches_practiced_and_stops(self):
        first = dt("2026-09-01T09:00:00+00:00")
        s, _ = rv.next_state("introduced", "inclass", "pass", first, first,
                             MIN_DAYS)
        assert s == "practiced"
        s, _ = rv.next_state("practiced", "inclass", "pass", first, first,
                             MIN_DAYS)
        assert s == "practiced"

    def test_a_retest_on_the_same_day_does_not_promote(self):
        first = dt("2026-09-01T09:00:00+00:00")
        s, why = rv.next_state("practiced", "delayed_retest", "pass",
                               first, first + timedelta(hours=8), MIN_DAYS)
        assert s == "practiced"
        assert "too soon" in why

    def test_a_retest_after_the_gap_promotes(self):
        first = dt("2026-09-01T09:00:00+00:00")
        s, _ = rv.next_state("practiced", "delayed_retest", "pass",
                             first, first + timedelta(days=4), MIN_DAYS)
        assert s == "consolidating"

    def test_transfer_test_is_the_last_rung(self):
        first = dt("2026-09-01T09:00:00+00:00")
        s, _ = rv.next_state("consolidating", "transfer_test", "pass",
                             first, first + timedelta(days=12), MIN_DAYS)
        assert s == "mastered"

    def test_a_transfer_test_cannot_skip_consolidating(self):
        first = dt("2026-09-01T09:00:00+00:00")
        s, _ = rv.next_state("practiced", "transfer_test", "pass",
                             first, first + timedelta(days=12), MIN_DAYS)
        assert s == "practiced"

    def test_failing_a_due_retest_drops_to_shaky(self):
        first = dt("2026-09-01T09:00:00+00:00")
        for state in ("practiced", "consolidating", "mastered"):
            s, _ = rv.next_state(state, "delayed_retest", "fail", first,
                                 first + timedelta(days=9), MIN_DAYS)
            assert s == "shaky", state

    def test_a_partly_right_answer_on_a_due_retest_also_drops(self):
        first = dt("2026-09-01T09:00:00+00:00")
        s, _ = rv.next_state("mastered", "delayed_retest", "partial", first,
                             first + timedelta(days=30), MIN_DAYS)
        assert s == "shaky"

    def test_a_partly_right_answer_in_session_changes_nothing(self):
        first = dt("2026-09-01T09:00:00+00:00")
        s, _ = rv.next_state("practiced", "inclass", "partial", first, first,
                             MIN_DAYS)
        assert s == "practiced"

    def test_recovery_climbs_back_one_rung_at_a_time(self):
        first = dt("2026-09-01T09:00:00+00:00")
        s, _ = rv.next_state("shaky", "inclass", "pass", first,
                             first + timedelta(days=20), MIN_DAYS)
        assert s == "practiced"
        s, _ = rv.next_state("shaky", "transfer_test", "pass", first,
                             first + timedelta(days=20), MIN_DAYS)
        assert s == "shaky"

    def test_a_prerequisite_probe_never_moves_the_state(self):
        first = dt("2026-09-01T09:00:00+00:00")
        for state in ("unseen", "practiced", "mastered"):
            s, _ = rv.next_state(state, "probe", "pass", first, first, MIN_DAYS)
            assert s == state


class TestApplyEvidence:
    def _ev(self, kind, verdict, day, latency="fluent"):
        return {"attempt_id": "a" + str(day), "kind": kind, "verdict": verdict,
                "date": "2026-09-" + str(day).zfill(2) + "T10:00:00+00:00",
                "latency_rating": latency, "latency_source": "inferred"}

    def test_a_full_ladder_takes_real_time(self):
        m = fx.mastery(state="introduced")
        m = rv.apply_evidence(m, self._ev("inclass", "pass", 1), MIN_DAYS)
        assert m["state"] == "practiced"
        m = rv.apply_evidence(m, self._ev("delayed_retest", "pass", 6),
                              MIN_DAYS)
        assert m["state"] == "consolidating"
        m = rv.apply_evidence(m, self._ev("transfer_test", "pass", 20),
                              MIN_DAYS)
        assert m["state"] == "mastered"
        assert zs.validate_doc(_clean(m), "mastery") == []
        assert zs.rule_mastery(_clean(m), "x", MIN_DAYS) == []

    def test_cramming_the_whole_ladder_into_one_day_fails(self):
        m = fx.mastery(state="introduced")
        m = rv.apply_evidence(m, self._ev("inclass", "pass", 1), MIN_DAYS)
        m = rv.apply_evidence(m, self._ev("delayed_retest", "pass", 1),
                              MIN_DAYS)
        assert m["state"] == "practiced"

    def test_a_failure_sets_the_hold_on_dependents(self):
        m = fx.mastery(state="mastered")
        m = rv.apply_evidence(m, self._ev("delayed_retest", "fail", 20),
                              MIN_DAYS)
        assert m["state"] == "shaky"
        assert m["downstream"]["hold"] is True

    def test_recovering_lifts_the_hold(self):
        m = fx.mastery(state="mastered")
        m = rv.apply_evidence(m, self._ev("delayed_retest", "fail", 20),
                              MIN_DAYS)
        m = rv.apply_evidence(m, self._ev("inclass", "pass", 22), MIN_DAYS)
        assert m["state"] == "practiced"
        assert m["downstream"]["hold"] is False

    def test_effort_changes_when_it_comes_back(self):
        base = fx.mastery(state="practiced")
        easy = rv.apply_evidence(base, self._ev("delayed_retest", "pass", 20,
                                                "instant"), MIN_DAYS)
        hard = rv.apply_evidence(base, self._ev("delayed_retest", "pass", 20,
                                                "effortful"), MIN_DAYS)
        assert dt(hard["scheduling"]["next_due"]) < \
            dt(easy["scheduling"]["next_due"])

    def test_a_hint_on_a_retest_does_not_promote(self):
        # hints are part of teaching; on a retest they are the answer to the
        # question the retest is asking
        base = fx.mastery(state="practiced")
        m = rv.apply_evidence(base, self._ev("delayed_retest", "pass", 20,
                                             "recovered_with_hint"), MIN_DAYS)
        assert m["state"] == "practiced"
        assert "hint" in m["_transition_reason"]

    def test_a_hint_during_a_lesson_still_reaches_practiced(self):
        base = fx.mastery(state="introduced")
        m = rv.apply_evidence(base, self._ev("inclass", "pass", 1,
                                             "recovered_with_hint"), MIN_DAYS)
        assert m["state"] == "practiced"

    def test_a_hinted_retest_still_shortens_the_interval(self):
        base = fx.mastery(state="practiced")
        base["scheduling"] = {"ease": 2.5, "reps": 3, "interval_days": 20}
        m = rv.apply_evidence(base, self._ev("delayed_retest", "pass", 20,
                                             "recovered_with_hint"), MIN_DAYS)
        assert m["scheduling"]["interval_days"] == 1.0
        assert m["scheduling"]["lapses"] == 1

    def test_an_illegal_transition_is_refused_rather_than_written(self):
        m = fx.mastery(state="introduced")
        m = rv.apply_evidence(m, self._ev("transfer_test", "pass", 30),
                              MIN_DAYS)
        assert m["state"] == "introduced"

    def test_first_taught_is_filled_in_if_absent(self):
        m = fx.mastery(state="unseen")
        m.pop("first_taught")
        m = rv.apply_evidence(m, self._ev("inclass", "pass", 1), MIN_DAYS)
        assert m["first_taught"]


def _clean(m):
    out = dict(m)
    out.pop("_transition_reason", None)
    return out


class TestQueue:
    def _rows(self):
        now = "2026-09-20T10:00:00+00:00"
        overdue = fx.mastery(fx.EIGENVALUE, state="practiced")
        overdue["scheduling"] = {"next_due": "2026-09-10T10:00:00+00:00",
                                 "interval_days": 6, "lapses": 2}
        future = fx.mastery(fx.EIGENVECTOR, state="consolidating")
        future["scheduling"] = {"next_due": "2026-10-30T10:00:00+00:00",
                                "interval_days": 40}
        unseen = fx.mastery("transformer.attention", state="unseen",
                            courses=("hist",))
        return [overdue, future, unseen], dt(now)

    def test_unseen_concepts_are_not_review_items(self):
        rows, now = self._rows()
        q = rv.build_queue("linalg", rows, fx.curriculum(), MIN_DAYS, now)
        assert all(i["concept_id"] != "transformer.attention"
                   for i in q["items"])

    def test_only_this_course_appears(self):
        rows, now = self._rows()
        q = rv.build_queue("hist", rows, fx.hist_curriculum(), MIN_DAYS, now)
        assert q["items"] == []

    def test_a_shared_concept_appears_in_both_courses(self):
        rows, now = self._rows()
        rows[0]["courses"] = ["linalg", "hist"]
        rows[0]["depth_targets"] = [{"course_id": "linalg", "depth_target": 3},
                                    {"course_id": "hist", "depth_target": 1}]
        for cid, cur in (("linalg", fx.curriculum()),
                         ("hist", fx.hist_curriculum())):
            q = rv.build_queue(cid, rows, cur, MIN_DAYS, now)
            assert any(i["concept_id"] == fx.EIGENVALUE for i in q["items"])

    def test_overdue_outranks_not_yet_due(self):
        rows, now = self._rows()
        q = rv.build_queue("linalg", rows, fx.curriculum(), MIN_DAYS, now)
        assert q["items"][0]["concept_id"] == fx.EIGENVALUE

    def test_blocking_other_concepts_raises_priority(self):
        rows, now = self._rows()
        blocking = rv.build_queue("linalg", rows, fx.curriculum(), MIN_DAYS,
                                  now)["items"][0]["priority"]
        alone = rv.build_queue("linalg", rows, {"modules": []}, MIN_DAYS,
                               now)["items"][0]["priority"]
        assert blocking > alone

    def test_a_repeatedly_slipped_concept_says_so(self):
        rows, now = self._rows()
        q = rv.build_queue("linalg", rows, fx.curriculum(), MIN_DAYS, now)
        item = next(i for i in q["items"] if i["concept_id"] == fx.EIGENVALUE)
        assert "slipped" in item.get("reason", "")

    def test_the_queue_validates_against_its_schema(self):
        rows, now = self._rows()
        q = rv.build_queue("linalg", rows, fx.curriculum(), MIN_DAYS, now)
        assert zs.validate_doc(q, "review_queue") == []

    def test_due_filter_respects_the_clock(self):
        rows, now = self._rows()
        q = rv.build_queue("linalg", rows, fx.curriculum(), MIN_DAYS, now)
        assert len(rv.due_items(q, now)) == 1
        assert len(rv.due_items(q, dt("2026-11-30T10:00:00+00:00"))) == 2


class TestCli:
    def run(self, root, argv):
        return rv.main(["--root", str(root)] + argv)

    def test_rebuild_then_due(self, root, capsys):
        m = fx.mastery(fx.EIGENVALUE, state="practiced")
        m["scheduling"] = {"next_due": "2026-09-10T10:00:00+00:00",
                           "interval_days": 6}
        fx.write_mastery(root, [m])
        assert rv.main(["--root", str(root), "--now",
                        "2026-09-20T10:00:00+00:00", "rebuild",
                        "--course", "linear-algebra"]) == zs.EXIT_OK
        capsys.readouterr()
        assert rv.main(["--root", str(root), "--now",
                        "2026-09-20T10:00:00+00:00", "due",
                        "--course", "linear-algebra"]) == zs.EXIT_OK
        out = capsys.readouterr().out
        assert fx.EIGENVALUE in out
        assert "overdue" in out

    def test_due_output_is_terse_enough_for_a_live_session(self, root, capsys):
        rows = []
        for i in range(5):
            m = fx.mastery("linalg.c" + str(i), state="practiced")
            m["scheduling"] = {"next_due": "2026-09-10T10:00:00+00:00"}
            rows.append(m)
        fx.write_mastery(root, rows)
        rv.main(["--root", str(root), "--now", "2026-09-20T10:00:00+00:00",
                 "rebuild", "--course", "linear-algebra"])
        capsys.readouterr()
        rv.main(["--root", str(root), "--now", "2026-09-20T10:00:00+00:00",
                 "due", "--course", "linear-algebra", "--limit", "3"])
        lines = [l for l in capsys.readouterr().out.strip().splitlines() if l]
        assert len(lines) == 3

    def test_rebuild_on_a_missing_course_exits_five(self, root):
        assert self.run(root, ["rebuild", "--course", "ghost"]) == \
            zs.EXIT_NOT_FOUND

    def test_plan_reports_what_is_owed_and_when(self, root, capsys):
        m = fx.mastery(fx.EIGENVALUE, state="consolidating")
        m["scheduling"] = {"next_due": "2026-09-25T10:00:00+00:00",
                           "interval_days": 9, "ease": 2.5}
        fx.write_mastery(root, [m])
        assert self.run(root, ["plan", "--concept", fx.EIGENVALUE]) == \
            zs.EXIT_OK
        got = json.loads(capsys.readouterr().out)
        assert got["next_kind"] == "transfer_test"
        assert got["floor_days"] == 7

    def test_simulate_shows_the_algorithm_without_writing(self, capsys):
        assert rv.main(["simulate", "--verdict", "pass", "--latency",
                        "instant"]) == zs.EXIT_OK
        got = json.loads(capsys.readouterr().out)
        assert got["grade"] == 5
        assert got["scheduling"]["interval_days"] > 6
