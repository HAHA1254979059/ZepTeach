"""Tests for session sizing, the turn budget, and selective loading.

The brief is the piece that keeps a session cheap: it is a small bounded block
built for the next few turns, not the learner model plus the curriculum plus
every doctrine file. The route table is the same idea applied to reading.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import review as rv  # noqa: E402
import route as rt  # noqa: E402
import session as se  # noqa: E402
import zt_state as zs  # noqa: E402
import conftest as fx  # noqa: E402


def open_session(root, energy="normal", capsys=None):
    code = se.main(["--root", str(root), "open", "--course",
                    "linear-algebra", "--energy", energy])
    assert code == zs.EXIT_OK
    sid = sorted((root / "courses" / "linear-algebra" / "sessions")
                 .glob("*"))[-1].name
    if capsys:
        capsys.readouterr()
    return sid


class TestSizing:
    def test_low_energy_shrinks_the_budget(self):
        cfg = fx.config()
        assert se.budget_for(cfg, "low")["turn_budget"] < \
            se.budget_for(cfg, "normal")["turn_budget"]
        assert se.budget_for(cfg, "high")["turn_budget"] > \
            se.budget_for(cfg, "normal")["turn_budget"]

    def test_a_budget_never_shrinks_below_something_usable(self):
        cfg = fx.config()
        cfg["defaults"]["turn_budget"] = 6
        assert se.budget_for(cfg, "low")["turn_budget"] >= 6

    def test_low_energy_means_fewer_new_concepts(self):
        p = fx.profile()
        assert se.new_concept_cap(p, "low") == 1
        assert se.new_concept_cap(p, "normal") == 3
        assert se.new_concept_cap(p, "high") == 4

    def test_checkpoints_are_owed_once_per_interval(self):
        assert se.checkpoints_owed(23, 24) == 0
        assert se.checkpoints_owed(24, 24) == 1
        assert se.checkpoints_owed(49, 24) == 2


class TestBrief:
    def test_the_brief_carries_the_register_for_this_domain(self, root):
        b = se.build_brief(root, "linear-algebra", "normal")
        assert b["register"]["register"] == "technical_with_gloss"

    def test_open_session_does_not_assign_a_three_tier_quota(self, root):
        sid = open_session(root)
        doc = zs.read_json(root / "courses" / "linear-algebra" /
                           "sessions" / sid / "session.json")
        assert "exercise_tiers" not in doc["plan"]

    def test_a_course_in_an_expert_field_gets_the_terse_register(self, root):
        c = fx.course(domain="semiconductor-physics")
        zs.atomic_write_json(
            root / "courses" / "linear-algebra" / "course.json", c)
        b = se.build_brief(root, "linear-algebra", "normal")
        assert b["register"]["register"] == "terse_technical"
        assert b["register"]["max_analogies_per_concept"] == 0

    def test_low_energy_silences_the_banter(self, root):
        b = se.build_brief(root, "linear-algebra", "low")
        assert b["persona"]["banter"] == 0
        assert "suppressed" in b["persona"]["banter_note"]

    def test_normal_energy_leaves_the_persona_alone(self, root):
        b = se.build_brief(root, "linear-algebra", "normal")
        assert b["persona"]["banter"] == 2

    def test_due_reviews_come_first_and_are_capped_by_energy(self, root):
        rows = []
        for i in range(9):
            m = fx.mastery("linalg.c" + str(i), state="practiced")
            m["scheduling"] = {"next_due": "2026-01-01T00:00:00+00:00"}
            rows.append(m)
        fx.write_mastery(root, rows)
        rv.main(["--root", str(root), "rebuild", "--course",
                 "linear-algebra"])
        low = se.build_brief(root, "linear-algebra", "low")
        high = se.build_brief(root, "linear-algebra", "high")
        assert len(low["due_reviews"]) == 3
        assert len(high["due_reviews"]) == 8
        assert low["due_total"] == 9

    def test_the_rendered_brief_stays_short(self, root):
        rows = []
        for i in range(30):
            m = fx.mastery("linalg.c" + str(i), state="practiced")
            m["scheduling"] = {"next_due": "2026-01-01T00:00:00+00:00"}
            rows.append(m)
        fx.write_mastery(root, rows)
        rv.main(["--root", str(root), "rebuild", "--course",
                 "linear-algebra"])
        text = se.render_brief(se.build_brief(root, "linear-algebra",
                                              "normal"))
        # 30 concepts overdue, but the brief shows the top few and says so
        assert len(text.splitlines()) < 20
        assert "30 total" in text

    def test_the_brief_does_not_carry_evidence_logs(self, root):
        m = fx.mastery(fx.EIGENVALUE, state="practiced")
        m["evidence"] = [{"attempt_id": "a1", "kind": "inclass",
                          "verdict": "pass",
                          "date": "2026-09-01T10:00:00+00:00"}]
        fx.write_mastery(root, [m])
        rv.main(["--root", str(root), "rebuild", "--course",
                 "linear-algebra"])
        assert "evidence" not in json.dumps(
            se.build_brief(root, "linear-algebra", "normal"))

    def test_the_brief_names_the_teaching_language(self, root):
        b = se.build_brief(root, "linear-algebra", "normal")
        assert b["course"]["teaching_language"] == "zh-CN"

    def _pile_up(self, root, n):
        rows = []
        for i in range(n):
            m = fx.mastery("linalg.c" + str(i), state="practiced")
            m["scheduling"] = {"next_due": "2026-01-01T00:00:00+00:00",
                               "last_review": "2025-12-25T00:00:00+00:00",
                               "interval_days": 7}
            rows.append(m)
        fx.write_mastery(root, rows)
        rv.main(["--root", str(root), "rebuild", "--course",
                 "linear-algebra"])

    def test_a_severe_backlog_pauses_new_material(self, root):
        self._pile_up(root, 60)
        b = se.build_brief(root, "linear-algebra", "normal")
        assert b["backlog"]["band"] == "severe"
        assert b["new_concept_cap"] == 0
        text = se.render_brief(b)
        assert "on hold while the backlog clears" in text
        assert "do not reschedule" in text

    def test_a_moderate_backlog_still_teaches_one_new_thing(self, root):
        self._pile_up(root, 10)
        b = se.build_brief(root, "linear-algebra", "normal")
        assert b["backlog"]["band"] == "moderate"
        assert b["new_concept_cap"] > 0

    def test_a_small_backlog_leaves_the_session_alone(self, root):
        self._pile_up(root, 3)
        b = se.build_brief(root, "linear-algebra", "normal")
        assert b["backlog"]["band"] == "manageable"
        assert se.render_brief(b).count("BACKLOG") == 0

    def test_only_a_session_worth_of_debt_is_shown(self, root):
        self._pile_up(root, 60)
        b = se.build_brief(root, "linear-algebra", "normal")
        assert len(b["due_reviews"]) == b["backlog"]["take_this_session"]
        assert b["due_total"] == 60

    def test_a_course_may_override_the_teaching_language(self, root):
        c = fx.course(teaching_language="en")
        zs.atomic_write_json(
            root / "courses" / "linear-algebra" / "course.json", c)
        b = se.build_brief(root, "linear-algebra", "normal")
        assert b["course"]["teaching_language"] == "en"


class TestOpenAndBudget:
    def test_open_is_gated_on_the_environment_setup(self, root, capsys):
        c = fx.course()
        c["environment"].pop("completed_at")
        zs.atomic_write_json(
            root / "courses" / "linear-algebra" / "course.json", c)
        assert se.main(["--root", str(root), "open", "--course",
                        "linear-algebra"]) == zs.EXIT_GATE

    def test_open_writes_a_session_that_validates(self, root, capsys):
        sid = open_session(root, capsys=capsys)
        doc = zs.read_json(root / "courses" / "linear-algebra" / "sessions" /
                           sid / "session.json")
        assert zs.validate_doc(doc, "session") == []

    def test_turns_are_counted(self, root, capsys):
        sid = open_session(root, capsys=capsys)
        for _ in range(3):
            assert se.main(["--root", str(root), "turn",
                            "--session", sid]) == zs.EXIT_OK
        doc = zs.read_json(root / "courses" / "linear-algebra" / "sessions" /
                           sid / "session.json")
        assert doc["turns_used"] == 3

    def test_a_checkpoint_is_demanded_before_the_budget_runs_out(
            self, root, capsys):
        sid = open_session(root, capsys=capsys)
        code = se.main(["--root", str(root), "turn", "--session", sid,
                        "--count", "24"])
        assert code == zs.EXIT_BUDGET
        assert "CHECKPOINT DUE" in capsys.readouterr().err

    def test_writing_the_digest_clears_the_demand(self, root, capsys):
        sid = open_session(root, capsys=capsys)
        se.main(["--root", str(root), "turn", "--session", sid,
                 "--count", "24"])
        assert se.main(["--root", str(root), "checkpoint", "--session", sid,
                        "--digest", "sessions/d.md"]) == zs.EXIT_OK
        assert se.main(["--root", str(root), "turn",
                        "--session", sid]) == zs.EXIT_OK

    def test_the_hard_stop_is_not_negotiable(self, root, capsys):
        sid = open_session(root, capsys=capsys)
        se.main(["--root", str(root), "turn", "--session", sid,
                 "--count", "24"])
        se.main(["--root", str(root), "checkpoint", "--session", sid,
                 "--digest", "d.md"])
        capsys.readouterr()
        code = se.main(["--root", str(root), "turn", "--session", sid,
                        "--count", "20"])
        assert code == zs.EXIT_BUDGET
        assert "BUDGET REACHED" in capsys.readouterr().err

    def test_a_low_energy_session_hits_its_limits_sooner(self, root, capsys):
        low = open_session(root, "low", capsys=capsys)
        assert se.main(["--root", str(root), "turn", "--session", low,
                        "--count", "15"]) == zs.EXIT_BUDGET

    def test_a_closed_session_refuses_more_turns(self, root, capsys):
        sid = open_session(root, capsys=capsys)
        se.main(["--root", str(root), "close", "--session", sid])
        capsys.readouterr()
        assert se.main(["--root", str(root), "turn",
                        "--session", sid]) == zs.EXIT_GATE

    def test_an_unknown_session_exits_five(self, root):
        assert se.main(["--root", str(root), "turn",
                        "--session", "nope"]) == zs.EXIT_NOT_FOUND


class TestClose:
    def test_closing_writes_an_energy_row(self, root, capsys):
        sid = open_session(root, "low", capsys=capsys)
        assert se.main(["--root", str(root), "close", "--session", sid,
                        "--reason", "learner_stopped"]) == zs.EXIT_OK
        rows = zs.read_jsonl(root / "learner" / "energy_log.jsonl")
        assert rows[0]["declared_energy"] == "low"
        assert rows[0]["ended_reason"] == "learner_stopped"
        assert zs.validate_doc(rows[0], "energy") == []

    def test_a_session_that_got_worse_as_it_went_is_flagged(self, root, capsys):
        sid = open_session(root, capsys=capsys)
        cdir = root / "courses" / "linear-algebra"
        verdicts = ["pass", "pass", "pass", "fail", "fail", "partial"]
        for i, v in enumerate(verdicts):
            a = fx.attempt(attempt_id="a" + str(i), exercise_id="e" + str(i),
                           verdict=v, session_id=sid)
            if v != "pass":
                a.pop("evidence_quotes")
                a["failure_points"] = ["lost the sign"]
            zs.append_jsonl(cdir / "attempts.jsonl", a)
        capsys.readouterr()
        se.main(["--root", str(root), "close", "--session", sid])
        assert "error rate climbed" in capsys.readouterr().out
        rows = zs.read_jsonl(root / "learner" / "energy_log.jsonl")
        assert rows[0]["fatigue_detected"] is True

    def test_a_steady_session_is_not_flagged(self, root, capsys):
        sid = open_session(root, capsys=capsys)
        cdir = root / "courses" / "linear-algebra"
        for i in range(6):
            zs.append_jsonl(cdir / "attempts.jsonl",
                            fx.attempt(attempt_id="a" + str(i),
                                       exercise_id="e" + str(i),
                                       session_id=sid))
        se.main(["--root", str(root), "close", "--session", sid])
        rows = zs.read_jsonl(root / "learner" / "energy_log.jsonl")
        assert rows[0]["fatigue_detected"] is False

    def test_too_few_answers_to_judge_is_not_a_verdict(self, root, capsys):
        sid = open_session(root, capsys=capsys)
        se.main(["--root", str(root), "close", "--session", sid])
        rows = zs.read_jsonl(root / "learner" / "energy_log.jsonl")
        assert rows[0]["fatigue_detected"] is False
        assert "error_rate_first_half" not in rows[0]


class TestRouting:
    def test_every_intent_resolves(self):
        for intent in rt.ROUTES:
            res = rt.resolve(intent)
            assert "read" in res and "run" in res

    def test_status_needs_no_doctrine_at_all(self):
        assert rt.resolve("status")["read"] == []

    def test_a_lesson_loads_teaching_files_not_exercise_files(self):
        res = rt.resolve("lesson")
        assert "teaching-contract.md" in res["read"]
        assert "exercise-engine.md" not in res["read"]
        assert "exercise" in res["defer"]

    def test_only_the_adapter_for_this_course_is_loaded(self, root):
        res = rt.resolve("lesson", root, "linear-algebra")
        assert "adapters/mathematics.json" in res["read"]
        assert "adapters/history.json" not in res["read"]
        res = rt.resolve("lesson", root, "historiography")
        assert "adapters/history.json" in res["read"]
        assert "adapters/mathematics.json" not in res["read"]

    def test_source_anchoring_loads_only_for_an_anchored_course(self, root):
        assert "source-anchoring.md" not in rt.resolve(
            "lesson", root, "linear-algebra")["read"]
        zs.atomic_write_json(
            root / "courses" / "linear-algebra" / "course.json",
            fx.course(source_anchored=True))
        assert "source-anchoring.md" in rt.resolve(
            "lesson", root, "linear-algebra")["read"]

    def test_the_tools_doctrine_loads_only_when_tools_are_registered(
            self, root):
        """A course whose practice is reading and writing never loads the
        doctrine about running things. Context has a price, and doctrine for
        a situation that does not apply is worse than absent: it is
        misleading."""
        assert "resources-and-tools.md" not in rt.resolve(
            "exercise", root, "linear-algebra")["read"]

        zs.atomic_write_json(
            root / "courses" / "linear-algebra" / "resources.json",
            {"schema_version": 1, "course_id": "linalg",
             "updated": "2026-09-20T00:00:00+00:00",
             "tools": [{"tool_id": "t", "what_it_does": "checks a proof",
                        "runs_where": "this machine"}]})
        res = rt.resolve("exercise", root, "linear-algebra")
        assert "resources-and-tools.md" in res["read"]
        assert res["read_reasons"]["resources-and-tools.md"]

        # teaching itself never loads it: nothing runs during an explanation
        assert "resources-and-tools.md" not in rt.resolve(
            "lesson", root, "linear-algebra")["read"]

    def test_a_resources_file_with_no_tools_does_not_load_it(self, root):
        """Material without tools is the common case and needs nothing."""
        zs.atomic_write_json(
            root / "courses" / "linear-algebra" / "resources.json",
            {"schema_version": 1, "course_id": "linalg",
             "updated": "2026-09-20T00:00:00+00:00",
             "materials": [{"material_id": "m", "title": "a book",
                            "kind": "textbook", "where": "the shelf"}]})
        assert "resources-and-tools.md" not in rt.resolve(
            "lesson", root, "linear-algebra")["read"]

    def test_each_conditional_addition_says_why(self, root):
        res = rt.resolve("lesson", root, "linear-algebra")
        assert res["read_reasons"]["adapters/mathematics.json"]

    def test_grading_is_marked_as_an_isolated_job(self):
        res = rt.resolve("grade")
        assert res["agent"] == "zt-grader"
        assert "not Zep" in res["isolate"]
        assert "teaching-contract.md" not in res["read"]

    def test_a_sidequest_is_marked_as_an_isolated_job(self):
        res = rt.resolve("sidequest")
        assert res["agent"] == "zt-sidequest-tutor"
        assert "digest" in res["isolate"]

    def test_unwritten_reference_files_are_reported_not_hidden(self):
        """A route that names a file nobody has written yet must say so.
        Silently skipping it would mean a lesson quietly running without the
        doctrine it was supposed to follow.

        Written against a route invented here rather than a real one, so that
        writing the last outstanding doctrine file does not break the test
        for the mechanism."""
        rt.ROUTES["_test_only"] = {
            "what": "a route naming a file that does not exist",
            "read": ["nobody-has-written-this.md"],
        }
        try:
            res = rt.resolve("_test_only")
            assert res["missing"] == ["nobody-has-written-this.md"]
        finally:
            del rt.ROUTES["_test_only"]

    def test_written_files_are_not_reported_as_missing(self):
        res = rt.resolve("lesson")
        assert "teaching-contract.md" in res["read"]
        assert "teaching-contract.md" not in res["missing"]
        assert set(res["missing"]) <= set(res["read"])

    def test_an_unknown_intent_raises(self):
        with pytest.raises(KeyError):
            rt.resolve("vibes")

    def test_the_cli_reports_an_unknown_intent(self, capsys):
        assert rt.main(["for", "vibes"]) == zs.EXIT_NOT_FOUND
        assert "available" in capsys.readouterr().err

    def test_the_audit_lists_what_the_doctrine_stages_still_owe(self, capsys):
        assert rt.main(["audit"]) == zs.EXIT_OK
        out = capsys.readouterr().out
        assert "still owed" in out
        assert "teaching-contract.md" in out

    def test_no_route_loads_everything(self):
        every_file = set()
        for intent in rt.ROUTES:
            every_file |= set(rt.resolve(intent)["read"])
        for intent in rt.ROUTES:
            assert set(rt.resolve(intent)["read"]) != every_file
