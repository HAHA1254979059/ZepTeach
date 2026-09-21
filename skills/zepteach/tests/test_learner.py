"""Tests for the learner model.

Two things matter here. The register has to come out different for different
fields, because that is the whole reason it is stored per domain. And the
prerequisite probe has to distinguish "nobody checked" from "this broke",
because those call for different responses.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import learner as ln  # noqa: E402
import zt_state as zs  # noqa: E402
import conftest as fx  # noqa: E402


class TestRegister:
    def test_the_same_person_gets_different_registers_per_field(self):
        p = fx.profile()
        assert ln.register_for(p, "semiconductor-physics")["register"] == \
            "terse_technical"
        assert ln.register_for(p, "humanities")["register"] == "analogy_first"

    def test_an_unlisted_field_falls_back(self):
        assert ln.register_for(fx.profile(), "geology")["register"] == \
            "technical_with_gloss"

    def test_the_most_specific_match_wins(self):
        p = fx.profile()
        p["registers"].append({"domain": "semiconductor-physics/organic",
                               "register": "analogy_first"})
        assert ln.register_for(p, "semiconductor-physics/organic")[
            "register"] == "analogy_first"
        assert ln.register_for(p, "semiconductor-physics")["register"] == \
            "terse_technical"

    def test_a_subdomain_inherits_its_parent(self):
        assert ln.register_for(fx.profile(),
                               "semiconductor-physics/transport")[
            "register"] == "terse_technical"

    def test_expert_fields_carry_no_analogy_budget(self):
        assert ln.register_for(fx.profile(), "semiconductor-physics")[
            "max_analogies_per_concept"] == 0

    def test_defaults_are_filled_in_so_callers_need_no_fallbacks(self):
        r = ln.register_for({"registers": [{"domain": "*",
                                            "register": "terse_technical"}]},
                            "anything")
        assert r["max_analogies_per_concept"] == 1
        assert r["require_operational_definition"] is True
        assert r["formalism_tolerance"] == 3

    def test_an_empty_profile_still_yields_a_usable_register(self):
        assert ln.register_for({}, "x")["register"] == "technical_with_gloss"

    def test_background_is_looked_up_the_same_way(self):
        assert ln.background_for(fx.profile(),
                                 "semiconductor-physics")["level"] == "expert"
        assert ln.background_for(fx.profile(), "geology") is None


class TestProbePlan:
    def test_an_unrecorded_prerequisite_is_unproven(self):
        plan = ln.probe_plan(fx.curriculum(), "l2", [])
        assert [u["concept_id"] for u in plan["unproven"]] == [fx.EIGENVALUE]
        assert plan["blocking"] is False

    def test_a_merely_practiced_prerequisite_still_needs_probing(self):
        rows = [fx.mastery(fx.EIGENVALUE, state="practiced")]
        plan = ln.probe_plan(fx.curriculum(), "l2", rows)
        assert plan["unproven"]

    def test_a_consolidated_prerequisite_is_proven_ground(self):
        rows = [fx.mastery(fx.EIGENVALUE, state="consolidating")]
        plan = ln.probe_plan(fx.curriculum(), "l2", rows)
        assert plan["unproven"] == []
        assert plan["blocking"] is False

    def test_a_broken_prerequisite_blocks_rather_than_prompting_a_probe(self):
        rows = [fx.mastery(fx.EIGENVALUE, state="shaky",
                           downstream={"hold": True})]
        plan = ln.probe_plan(fx.curriculum(), "l2", rows)
        assert [h["concept_id"] for h in plan["held"]] == [fx.EIGENVALUE]
        assert plan["blocking"] is True

    def test_waving_it_through_clears_the_block(self):
        rows = [fx.mastery(fx.EIGENVALUE, state="shaky",
                           downstream={"hold": True, "bypassed": True,
                                       "bypass_reason": "bad day"})]
        plan = ln.probe_plan(fx.curriculum(), "l2", rows)
        assert plan["blocking"] is False

    def test_assumed_background_is_reported_as_a_sidequest_candidate(self):
        c = fx.curriculum()
        c["modules"][0]["lessons"][1]["concepts"][0]["external_prereq"] = \
            ["determinants"]
        plan = ln.probe_plan(c, "l2", [])
        assert plan["external"][0]["topic"] == "determinants"

    def test_an_unknown_lesson_is_an_error_not_an_empty_plan(self):
        with pytest.raises(FileNotFoundError):
            ln.probe_plan(fx.curriculum(), "nope", [])


class TestEnsureRow:
    def test_a_new_concept_starts_unseen_with_this_course_target(self):
        rows = []
        row = ln.ensure_row(rows, fx.EIGENVALUE, "linalg", 3)
        assert row["state"] == "unseen"
        assert row["depth_targets"] == [{"course_id": "linalg",
                                        "depth_target": 3}]

    def test_a_second_course_is_added_without_disturbing_the_first(self):
        rows = [fx.mastery(fx.SHARED, state="mastered",
                           courses=("linalg",))]
        row = ln.ensure_row(rows, fx.SHARED, "hist", 1)
        assert row["courses"] == ["linalg", "hist"]
        assert {"course_id": "hist", "depth_target": 1} in row["depth_targets"]
        assert row["state"] == "mastered"
        assert len(rows) == 1

    def test_re_adding_the_same_course_changes_nothing(self):
        rows = [fx.mastery(fx.EIGENVALUE, courses=("linalg",))]
        ln.ensure_row(rows, fx.EIGENVALUE, "linalg", 3)
        ln.ensure_row(rows, fx.EIGENVALUE, "linalg", 3)
        assert len(rows[0]["depth_targets"]) == 1

    def test_the_depth_target_comes_from_the_curriculum(self):
        assert ln.depth_target_in(fx.curriculum(), fx.EIGENVALUE) == 3
        assert ln.depth_target_in(fx.hist_curriculum(), fx.SHARED) == 1


class TestCli:
    def run(self, root, argv):
        return ln.main(["--root", str(root)] + argv)

    def test_show_is_a_summary_not_a_dump(self, root, capsys):
        fx.write_mastery(root, [fx.mastery(fx.EIGENVALUE, state="shaky",
                                           downstream={"hold": True})])
        assert self.run(root, ["show"]) == zs.EXIT_OK
        got = json.loads(capsys.readouterr().out)
        assert got["concepts_tracked"] == 1
        assert got["shaky"] == [fx.EIGENVALUE]
        assert "evidence" not in json.dumps(got)

    def test_register_command_answers_for_one_field(self, root, capsys):
        assert self.run(root, ["register", "--domain",
                               "semiconductor-physics"]) == zs.EXIT_OK
        got = json.loads(capsys.readouterr().out)
        assert got["register"] == "terse_technical"
        assert got["background_level"] == "expert"

    def test_probe_exits_three_when_the_ground_is_broken(self, root, capsys):
        fx.write_mastery(root, [fx.mastery(fx.EIGENVALUE, state="shaky",
                                           downstream={"hold": True})])
        code = self.run(root, ["probe", "--course", "linear-algebra",
                               "--lesson", "l2"])
        assert code == zs.EXIT_GATE
        assert "bypass" in capsys.readouterr().out

    def test_probe_exits_zero_but_still_asks_for_a_probe(self, root, capsys):
        code = self.run(root, ["probe", "--course", "linear-algebra",
                               "--lesson", "l2"])
        assert code == zs.EXIT_OK
        assert "UNPROVEN" in capsys.readouterr().out

    def _teach(self, root, lesson="l1", course="linear-algebra",
               at="2026-09-01T09:00:00+00:00", concept=None):
        """Teaching now costs what marking costs: something on the record.

        It used to be three strings and a call. That made claiming to have
        taught free in a system where claiming a pass costs a quote from the
        answer, and the first real use went exactly where that asymmetry
        pointed.
        """
        doc = fx.exposition(concept or fx.EIGENVALUE, lesson_id=lesson,
                            delivered_at=at)
        return self.run(root, ["teach", "--course", course,
                               "--data", json.dumps(doc)])

    def test_teaching_is_recorded_as_its_own_event(self, root, capsys):
        assert self._teach(root) == zs.EXIT_OK
        row = ln.load_mastery(root)[0]
        assert row["state"] == "introduced"
        assert row["first_taught"] == "2026-09-01T09:00:00+00:00"

    def test_teaching_twice_does_not_reset_the_baseline(self, root):
        self._teach(root)
        self._teach(root, at="2026-09-20T09:00:00+00:00")
        assert ln.load_mastery(root)[0]["first_taught"] ==             "2026-09-01T09:00:00+00:00"

    def test_an_attempt_on_something_never_taught_is_refused(self, root, capsys):
        code = self.run(root, ["record", "--course", "linear-algebra",
                               "--data", json.dumps(fx.attempt())])
        assert code == zs.EXIT_GATE
        assert "teach" in capsys.readouterr().err
        assert ln.load_mastery(root) == []

    def test_recording_an_attempt_moves_the_learner_model(self, root, capsys):
        self._teach(root)
        capsys.readouterr()
        code = self.run(root, ["record", "--course", "linear-algebra",
                               "--data", json.dumps(fx.attempt())])
        assert code == zs.EXIT_OK
        out = capsys.readouterr().out
        assert "introduced -> practiced" in out
        rows = ln.load_mastery(root)
        assert rows[0]["state"] == "practiced"
        assert rows[0]["scheduling"]["next_due"]

    def test_the_attempt_itself_is_kept_for_audit(self, root):
        self._teach(root)
        self.run(root, ["record", "--course", "linear-algebra",
                        "--data", json.dumps(fx.attempt())])
        saved = zs.read_jsonl(root / "courses" / "linear-algebra" /
                              "attempts.jsonl")
        assert saved[0]["attempt_id"] == "a1"

    def test_an_unearned_pass_is_refused_before_anything_moves(self, root):
        self._teach(root)
        bad = fx.attempt()
        bad.pop("evidence_quotes")
        code = self.run(root, ["record", "--course", "linear-algebra",
                               "--data", json.dumps(bad)])
        assert code == zs.EXIT_VALIDATION
        assert ln.load_mastery(root)[0]["state"] == "introduced"
        assert not (root / "courses" / "linear-algebra" /
                    "attempts.jsonl").exists()

    def test_a_retest_recorded_too_soon_does_not_promote(self, root, capsys):
        self._teach(root)
        self.run(root, ["record", "--course", "linear-algebra",
                        "--data", json.dumps(fx.attempt())])
        capsys.readouterr()
        soon = fx.attempt(attempt_id="a2", exercise_id="e2",
                          kind="delayed_retest",
                          submitted_at="2026-09-02T10:00:00+00:00")
        self.run(root, ["record", "--course", "linear-algebra",
                        "--data", json.dumps(soon)])
        assert "too soon" in capsys.readouterr().out
        assert ln.load_mastery(root)[0]["state"] == "practiced"

    def test_a_retest_after_the_gap_does_promote(self, root):
        self._teach(root)
        self.run(root, ["record", "--course", "linear-algebra",
                        "--data", json.dumps(fx.attempt())])
        later = fx.attempt(attempt_id="a2", exercise_id="e2",
                           kind="delayed_retest", tier="variant",
                           submitted_at="2026-09-09T10:00:00+00:00",
                           latency_rating="fluent")
        self.run(root, ["record", "--course", "linear-algebra",
                        "--data", json.dumps(later)])
        assert ln.load_mastery(root)[0]["state"] == "consolidating"

    def test_evidence_from_a_second_course_lands_on_the_same_concept(self, root):
        # explained once, in the course that introduced it. The other course
        # does not have to explain it again: the concept belongs to the
        # learner, not to a course, which is the same reason the evidence
        # from both courses lands on one row.
        self._teach(root, concept=fx.SHARED)
        self.run(root, ["record", "--course", "linear-algebra",
                        "--data", json.dumps(
                            fx.attempt(concept_ids=[fx.SHARED]))])
        via_hist = fx.attempt(attempt_id="a9", exercise_id="e9",
                              course_id="hist", lesson_id="l1",
                              concept_ids=[fx.SHARED],
                              submitted_at="2026-09-11T10:00:00+00:00")
        self.run(root, ["record", "--course", "historiography",
                        "--data", json.dumps(via_hist)])
        rows = ln.load_mastery(root)
        shared = [r for r in rows if r["concept_id"] == fx.SHARED]
        assert len(shared) == 1, "the second course must not clone the row"
        assert sorted(shared[0]["courses"]) == ["hist", "linalg"]

    def test_recording_against_a_concept_nobody_taught_is_refused(self, root):
        self._teach(root)
        bad = fx.attempt(concept_ids=["ghost.thing"])
        assert self.run(root, ["record", "--course", "linear-algebra",
                               "--data", json.dumps(bad)]) == zs.EXIT_GATE
        assert all(r["concept_id"] != "ghost.thing"
                   for r in ln.load_mastery(root))

    def test_bypass_records_the_reason_and_counts_it(self, root, capsys):
        fx.write_mastery(root, [fx.mastery(fx.EIGENVALUE, state="shaky",
                                           downstream={"hold": True})])
        assert self.run(root, ["bypass", "--concept", fx.EIGENVALUE,
                               "--reason", "tired, not a real gap"]) == \
            zs.EXIT_OK
        down = ln.load_mastery(root)[0]["downstream"]
        assert down["bypassed"] is True
        assert down["bypass_count"] == 1
        assert down["bypass_reason"]

    def test_repeated_bypasses_get_called_out(self, root, capsys):
        fx.write_mastery(root, [fx.mastery(fx.EIGENVALUE, state="shaky",
                                           downstream={"hold": True})])
        for _ in range(3):
            self.run(root, ["bypass", "--concept", fx.EIGENVALUE,
                            "--reason", "later"])
        assert "worth fixing" in capsys.readouterr().out

    def test_depth_reached_comes_from_what_an_answer_proved(self, root):
        self._teach(root)
        self.run(root, ["record", "--course", "linear-algebra",
                        "--data", json.dumps(fx.attempt(depth_demonstrated=2))])
        assert ln.load_mastery(root)[0]["depth_reached"] == 2

    def test_depth_only_ratchets_upward(self, root):
        self._teach(root)
        for d in (3, 1):
            self.run(root, ["record", "--course", "linear-algebra",
                            "--data", json.dumps(fx.attempt(
                                attempt_id="a" + str(d),
                                exercise_id="e" + str(d),
                                depth_demonstrated=d))])
        assert ln.load_mastery(root)[0]["depth_reached"] == 3

    def test_a_wrong_answer_proves_no_depth(self, root):
        self._teach(root)
        bad = fx.attempt(verdict="fail", depth_demonstrated=4,
                         failure_points=["never formed the polynomial"])
        bad.pop("evidence_quotes")
        self.run(root, ["record", "--course", "linear-algebra",
                        "--data", json.dumps(bad)])
        assert not ln.load_mastery(root)[0].get("depth_reached")

    def test_going_deeper_than_the_target_is_refused(self, root, capsys):
        self._teach(root)
        deep = fx.attempt(depth_demonstrated=5)
        code = self.run(root, ["record", "--course", "linear-algebra",
                               "--data", json.dumps(deep)])
        assert code == zs.EXIT_VALIDATION
        assert "exceeds the highest declared target" in capsys.readouterr().err

    def test_get_on_an_unknown_concept_exits_five(self, root):
        assert self.run(root, ["get", "--concept", "nope.nope"]) == \
            zs.EXIT_NOT_FOUND
