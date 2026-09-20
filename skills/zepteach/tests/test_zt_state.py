"""Tests for the ZepTeach state engine.

The point of these tests is not coverage for its own sake. Each block below
pins down one invariant that the system must keep even when a persuasive
model is driving the session: evidence must exist before a pass is recorded,
mastery must be earned across days rather than within a lesson, depth must
stay inside its declared target, and an exercise without a grading spec must
never reach the learner.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import zt_state as zs  # noqa: E402


# --------------------------------------------------------------------------
# fixtures: the smallest documents that are legitimately valid
# --------------------------------------------------------------------------

def valid_config():
    return {
        "schema_version": 1,
        "learner_id": "learner",
        "teaching_language": "zh-CN",
        "setup": {"stage1_completed_at": "2026-09-01T00:00:00+00:00"},
        "notes": {"markdown_dir": "E:/notes", "document_dir": "E:/docs",
                  "journal_dir": "E:/notes/journal"},
        "persona": {"name": "Zep", "closeness": 4, "banter": 2},
        "agent_models": {
            "sidequest_tutor": "sonnet",
            "grader": "opus",
            "curriculum_architect": "opus",
        },
        "defaults": {"turn_budget": 40, "checkpoint_at": 0.6,
                     "session_minutes": 45},
    }


def valid_profile():
    return {
        "schema_version": 1,
        "learner_id": "learner",
        "registers": [{"domain": "*", "register": "technical_with_gloss"}],
        "pacing": {"weekly_minutes": 180},
    }


def valid_course(**over):
    doc = {
        "schema_version": 1,
        "course_id": "c1",
        "slug": "linear-algebra",
        "title": "Linear algebra for AI",
        "goal": "Model a real problem with eigen-decomposition unaided.",
        "domain": "mathematics",
        "adapter_ref": "adapters/mathematics.json",
        "status": "planning",
        "depth_policy": {"default_depth_target": 3},
        "environment": {
            "required_targets": [
                {"target_id": "problem-set", "kind": "problem set",
                 "named_in_goal": False, "criticality": "required"}
            ]
        },
    }
    doc.update(over)
    return doc


def valid_curriculum(**over):
    doc = {
        "schema_version": 1,
        "course_id": "c1",
        "modules": [{
            "module_id": "m1",
            "title": "Eigen-structure",
            "lessons": [{
                "lesson_id": "l1",
                "title": "Eigenvalues and eigenvectors",
                "concepts": [
                    {"concept_id": "linalg.eigenvalue", "title": "Eigenvalue",
                     "depth_target": 3},
                    {"concept_id": "linalg.eigenvector", "title": "Eigenvector",
                     "depth_target": 3, "prereq": ["linalg.eigenvalue"]},
                ],
            }],
        }],
    }
    doc.update(over)
    return doc


def valid_attempt(**over):
    doc = {
        "schema_version": 1,
        "attempt_id": "a1",
        "course_id": "c1",
        "exercise_id": "e1",
        "concept_ids": ["linalg.eigenvalue"],
        "kind": "inclass",
        "tier": "anchored",
        "verdict": "pass",
        "graded_by": "script:numeric",
        "submitted_at": "2026-09-10T10:00:00+00:00",
        "evidence_quotes": ["solved det(A - lambda I) = 0 correctly"],
        "latency_rating": "fluent",
        "latency_source": "inferred",
        "depth_demonstrated": 2,
    }
    doc.update(over)
    return doc


def valid_exercise(**over):
    doc = {
        "schema_version": 1,
        "exercise_id": "e1",
        "course_id": "c1",
        "concept_ids": ["linalg.eigenvalue"],
        "tier": "anchored",
        "prompt": "Find the eigenvalues of the given matrix.",
        "anchor_kind": "textbook",
        "source_ref": "Strang 6.1, problem 14, p.288",
        "grader": {"type": "numeric", "tolerance": 1e-6},
    }
    doc.update(over)
    return doc


def mastery_mastered(**over):
    doc = {
        "schema_version": 1,
        "concept_id": "linalg.eigenvalue",
        "courses": ["c1"],
        "state": "mastered",
        "depth_targets": [{"course_id": "c1", "depth_target": 3}],
        "depth_reached": 3,
        "first_taught": "2026-01-01T09:00:00+00:00",
        "evidence": [
            {"attempt_id": "a1", "kind": "inclass", "verdict": "pass",
             "date": "2026-01-01T10:00:00+00:00"},
            {"attempt_id": "a2", "kind": "delayed_retest", "verdict": "pass",
             "date": "2026-01-08T10:00:00+00:00"},
            {"attempt_id": "a3", "kind": "transfer_test", "verdict": "pass",
             "date": "2026-01-20T10:00:00+00:00"},
        ],
    }
    doc.update(over)
    return doc


def valid_registry(**over):
    doc = {
        "schema_version": 1,
        "concepts": [
            {"concept_id": "linalg.eigenvalue", "canonical_title": "Eigenvalue",
             "domain": "mathematics/linear-algebra", "courses": ["c1"],
             "note_path": "notes/concepts/linalg.eigenvalue.md"},
            {"concept_id": "linalg.eigenvector", "canonical_title": "Eigenvector",
             "domain": "mathematics/linear-algebra", "courses": ["c1"]},
        ],
    }
    doc.update(over)
    return doc


def errors(findings):
    return [f.code for f in findings if f.severity == "error"]


# --------------------------------------------------------------------------
# the validator itself
# --------------------------------------------------------------------------

class TestValidator:
    def test_accepts_the_valid_fixtures(self):
        for doc, name in ((valid_config(), "config"),
                          (valid_profile(), "profile"),
                          (valid_course(), "course"),
                          (valid_curriculum(), "curriculum"),
                          (valid_attempt(), "attempt"),
                          (valid_exercise(), "exercise"),
                          (mastery_mastered(), "mastery")):
            assert zs.validate_doc(doc, name) == [], name

    def test_missing_required_field_is_caught(self):
        doc = valid_course()
        del doc["goal"]
        assert any("goal" in e for e in zs.validate_doc(doc, "course"))

    def test_unknown_field_is_caught(self):
        doc = valid_course()
        doc["vibe"] = "good"
        assert any("vibe" in e for e in zs.validate_doc(doc, "course"))

    def test_enum_is_enforced(self):
        doc = valid_attempt(verdict="excellent")
        assert any("not one of" in e for e in zs.validate_doc(doc, "attempt"))

    def test_bool_is_not_an_integer(self):
        doc = valid_curriculum()
        doc["modules"][0]["lessons"][0]["concepts"][0]["depth_target"] = True
        assert zs.validate_doc(doc, "curriculum")

    def test_numeric_bounds(self):
        doc = valid_curriculum()
        doc["modules"][0]["lessons"][0]["concepts"][0]["depth_target"] = 9
        assert any("above maximum" in e for e in zs.validate_doc(doc, "curriculum"))

    def test_pattern_on_slug(self):
        assert any("pattern" in e
                   for e in zs.validate_doc(valid_course(slug="Linear Algebra"),
                                            "course"))

    def test_date_time_format(self):
        doc = valid_attempt(submitted_at="last tuesday")
        assert any("ISO date-time" in e for e in zs.validate_doc(doc, "attempt"))

    def test_local_ref_resolves(self):
        # curriculum uses $ref into $defs for concept and source_span
        doc = valid_curriculum()
        doc["modules"][0]["lessons"][0]["concepts"][0]["bogus"] = 1
        assert any("bogus" in e for e in zs.validate_doc(doc, "curriculum"))

    def test_every_shipped_schema_loads(self):
        names = zs.schema_names()
        assert len(names) >= 14
        for n in names:
            assert isinstance(zs.load_schema(n), dict)


# --------------------------------------------------------------------------
# no-leniency rule: a pass must be able to point at what earned it
# --------------------------------------------------------------------------

class TestAttemptRules:
    def test_pass_without_quoted_evidence_is_rejected(self):
        doc = valid_attempt()
        doc.pop("evidence_quotes")
        assert "ATT001" in errors(zs.semantic_check(doc, "attempt", "x"))

    def test_pass_with_evidence_is_accepted(self):
        assert errors(zs.semantic_check(valid_attempt(), "attempt", "x")) == []

    def test_fail_without_evidence_quotes_is_fine(self):
        doc = valid_attempt(verdict="fail",
                            failure_points=["never formed the characteristic polynomial"])
        doc.pop("evidence_quotes")
        assert errors(zs.semantic_check(doc, "attempt", "x")) == []

    def test_fail_without_failure_points_warns_but_does_not_block(self):
        doc = valid_attempt(verdict="fail")
        doc.pop("evidence_quotes")
        found = zs.semantic_check(doc, "attempt", "x")
        assert errors(found) == []
        assert any(f.code == "ATT003" for f in found)

    def test_transfer_test_must_be_new_ground(self):
        doc = valid_attempt(kind="transfer_test", tier="variant",
                            concept_ids=["linalg.eigenvalue"])
        assert "ATT002" in errors(zs.semantic_check(doc, "attempt", "x"))

    def test_transfer_test_accepts_modeling_tier(self):
        doc = valid_attempt(kind="transfer_test", tier="modeling")
        assert "ATT002" not in errors(zs.semantic_check(doc, "attempt", "x"))

    def test_transfer_test_accepts_cross_concept_item(self):
        doc = valid_attempt(kind="transfer_test", tier="variant",
                            concept_ids=["linalg.eigenvalue", "linalg.diagonalisation"])
        assert "ATT002" not in errors(zs.semantic_check(doc, "attempt", "x"))


# --------------------------------------------------------------------------
# exercises cannot be issued without a way to judge them
# --------------------------------------------------------------------------

class TestExerciseRules:
    def test_missing_grader_fails_schema(self):
        doc = valid_exercise()
        doc.pop("grader")
        assert any("grader" in e for e in zs.validate_doc(doc, "exercise"))

    def test_modeling_tier_must_be_rubric_graded(self):
        doc = valid_exercise(tier="modeling",
                             grader={"type": "numeric"}, rubric_id="r1")
        assert "EXE001" in errors(zs.semantic_check(doc, "exercise", "x"))

    def test_rubric_grading_needs_a_rubric_id(self):
        doc = valid_exercise(tier="modeling", grader={"type": "rubric"})
        assert "EXE002" in errors(zs.semantic_check(doc, "exercise", "x"))

    def test_anchored_tier_must_cite_its_source(self):
        doc = valid_exercise()
        doc.pop("source_ref")
        assert "EXE003" in errors(zs.semantic_check(doc, "exercise", "x"))

    def test_anchored_tier_must_declare_what_anchors_it(self):
        doc = valid_exercise()
        doc.pop("anchor_kind")
        assert "EXE004" in errors(zs.semantic_check(doc, "exercise", "x"))

    def test_a_course_with_no_textbook_can_still_anchor(self):
        # the anchor does not have to be a book: a paper, official docs, a
        # public course assignment or a published benchmark all count
        for kind, ref in (("paper", "Vaswani 2017, eq.(1), sec.3.2.1"),
                          ("official_doc", "PyTorch docs, torch.autograd.grad"),
                          ("course_assignment", "CS231n assignment 2, Q4"),
                          ("benchmark", "GLUE MNLI-m dev accuracy")):
            doc = valid_exercise(anchor_kind=kind, source_ref=ref)
            assert errors(zs.semantic_check(doc, "exercise", "x")) == [], kind

    def test_well_formed_modeling_item_passes(self):
        doc = valid_exercise(tier="modeling", grader={"type": "rubric"},
                             rubric_id="modeling-v1")
        doc.pop("source_ref")
        doc.pop("anchor_kind")
        assert errors(zs.semantic_check(doc, "exercise", "x")) == []


# --------------------------------------------------------------------------
# mastery: earned across days, never inside one lesson
# --------------------------------------------------------------------------

class TestMasteryRules:
    def test_a_well_earned_mastered_record_passes(self):
        assert errors(zs.rule_mastery(mastery_mastered(), "x")) == []

    def test_mastered_without_transfer_evidence_is_rejected(self):
        doc = mastery_mastered()
        doc["evidence"] = [e for e in doc["evidence"]
                           if e["kind"] != "transfer_test"]
        assert "MAS001" in errors(zs.rule_mastery(doc, "x"))

    def test_mastered_without_delayed_retest_is_rejected(self):
        doc = mastery_mastered()
        doc["evidence"] = [e for e in doc["evidence"]
                           if e["kind"] != "delayed_retest"]
        assert "MAS001" in errors(zs.rule_mastery(doc, "x"))

    def test_in_class_success_alone_cannot_claim_mastered(self):
        doc = mastery_mastered()
        doc["evidence"] = [{"attempt_id": "a1", "kind": "inclass",
                            "verdict": "pass",
                            "date": "2026-01-01T10:00:00+00:00"}]
        assert "MAS001" in errors(zs.rule_mastery(doc, "x"))

    def test_consolidating_needs_a_delayed_retest(self):
        doc = mastery_mastered(state="consolidating")
        doc["evidence"] = [{"attempt_id": "a1", "kind": "inclass",
                            "verdict": "pass",
                            "date": "2026-01-01T10:00:00+00:00"}]
        assert "MAS001" in errors(zs.rule_mastery(doc, "x"))

    def test_same_day_retest_does_not_count_as_delayed(self):
        doc = mastery_mastered()
        for e in doc["evidence"]:
            if e["kind"] == "delayed_retest":
                e["date"] = "2026-01-01T18:00:00+00:00"
        assert "MAS004" in errors(zs.rule_mastery(doc, "x"))

    def test_gap_thresholds_come_from_config(self):
        doc = mastery_mastered()
        # transfer pass is 19 days out; demanding 30 must reject it
        strict = {"delayed_retest_min_days": 3, "transfer_test_min_days": 30}
        assert "MAS004" in errors(zs.rule_mastery(doc, "x", strict))

    def test_failed_evidence_does_not_count_as_passed(self):
        doc = mastery_mastered()
        for e in doc["evidence"]:
            if e["kind"] == "transfer_test":
                e["verdict"] = "fail"
        assert "MAS001" in errors(zs.rule_mastery(doc, "x"))

    def test_shaky_holds_downstream_by_default_but_only_warns(self):
        # holding dependents back is the default, not a hard stop: the learner
        # is allowed to carry on, so an unrecorded decision is a warning
        doc = mastery_mastered(state="shaky")
        found = zs.rule_mastery(doc, "x")
        assert "MAS002" not in errors(found)
        assert any(f.code == "MAS002" and f.severity == "warning"
                   for f in found)

    def test_recording_the_hold_clears_the_warning(self):
        doc = mastery_mastered(state="shaky", downstream={"hold": True})
        assert not any(f.code == "MAS002" for f in zs.rule_mastery(doc, "x"))

    def test_carrying_on_anyway_is_allowed_but_must_say_why(self):
        doc = mastery_mastered(state="shaky",
                               downstream={"bypassed": True})
        assert "MAS005" in errors(zs.rule_mastery(doc, "x"))

    def test_a_reasoned_bypass_is_accepted(self):
        doc = mastery_mastered(
            state="shaky",
            downstream={"bypassed": True, "bypass_count": 1,
                        "bypass_reason": "bad day, not a real gap; retest Friday"})
        assert errors(zs.rule_mastery(doc, "x")) == []

    def test_depth_may_not_exceed_its_target(self):
        doc = mastery_mastered(
            depth_targets=[{"course_id": "c1", "depth_target": 2}],
            depth_reached=4)
        assert "MAS003" in errors(zs.rule_mastery(doc, "x"))

    def test_depth_below_target_is_not_an_error_here(self):
        doc = mastery_mastered(
            depth_targets=[{"course_id": "c1", "depth_target": 4}],
            depth_reached=2)
        assert "MAS003" not in errors(zs.rule_mastery(doc, "x"))

    def test_the_ceiling_is_the_deepest_course_that_wants_it(self):
        # linear algebra wants can-derive, the transformer course only
        # can-use; reaching 3 is fine because one course asked for it
        doc = mastery_mastered(
            courses=["c1", "c2"],
            depth_targets=[{"course_id": "c1", "depth_target": 3},
                           {"course_id": "c2", "depth_target": 1}],
            depth_reached=3)
        assert "MAS003" not in errors(zs.rule_mastery(doc, "x"))
        doc["depth_reached"] = 4
        assert "MAS003" in errors(zs.rule_mastery(doc, "x"))

    def test_a_course_states_its_depth_once(self):
        doc = mastery_mastered(
            depth_targets=[{"course_id": "c1", "depth_target": 3},
                           {"course_id": "c1", "depth_target": 5}])
        assert "MAS006" in errors(zs.rule_mastery(doc, "x"))

    def test_evidence_from_any_course_counts(self):
        # the concept is one thing, so a transfer test passed in the
        # transformer course consolidates it for linear algebra too
        doc = mastery_mastered(courses=["c1", "c2"],
                               depth_targets=[{"course_id": "c1", "depth_target": 3},
                                              {"course_id": "c2", "depth_target": 2}])
        doc["evidence"][2]["course_id"] = "c2"
        assert errors(zs.rule_mastery(doc, "x")) == []

    def test_recall_effort_rating_should_say_where_it_came_from(self):
        att = valid_attempt(latency_rating="effortful")
        att.pop("latency_source")
        found = zs.semantic_check(att, "attempt", "x")
        assert any(f.code == "ATT005" for f in found)
        att = valid_attempt(latency_rating="effortful",
                            latency_source="inferred")
        assert not any(f.code == "ATT005"
                       for f in zs.semantic_check(att, "attempt", "x"))


class TestMasteryTransitions:
    def test_the_normal_ladder(self):
        ladder = ["unseen", "introduced", "practiced", "consolidating",
                  "mastered"]
        for a, b in zip(ladder, ladder[1:]):
            assert zs.can_transition(a, b)

    def test_no_skipping_rungs(self):
        assert not zs.can_transition("introduced", "mastered")
        assert not zs.can_transition("unseen", "practiced")
        assert not zs.can_transition("practiced", "mastered")

    def test_anything_taught_can_go_shaky(self):
        for s in ["introduced", "practiced", "consolidating", "mastered"]:
            assert zs.can_transition(s, "shaky")

    def test_recovery_never_jumps_straight_back_to_mastered(self):
        assert not zs.can_transition("shaky", "mastered")
        assert zs.can_transition("shaky", "consolidating")

    def test_staying_put_is_allowed(self):
        assert zs.can_transition("practiced", "practiced")


# --------------------------------------------------------------------------
# curriculum integrity
# --------------------------------------------------------------------------

class TestCurriculumRules:
    def test_clean_curriculum_passes(self):
        assert errors(zs.rule_curriculum(valid_curriculum(), "x")) == []

    def test_duplicate_concept_ids_are_caught(self):
        doc = valid_curriculum()
        doc["modules"][0]["lessons"][0]["concepts"][1]["concept_id"] = "linalg.eigenvalue"
        assert "CUR001" in errors(zs.rule_curriculum(doc, "x"))

    def test_self_prerequisite_is_caught(self):
        doc = valid_curriculum()
        doc["modules"][0]["lessons"][0]["concepts"][0]["prereq"] = ["linalg.eigenvalue"]
        assert "CUR002" in errors(zs.rule_curriculum(doc, "x"))

    def test_dangling_prerequisite_is_caught(self):
        doc = valid_curriculum()
        doc["modules"][0]["lessons"][0]["concepts"][0]["prereq"] = ["calculus"]
        assert "CUR003" in errors(zs.rule_curriculum(doc, "x"))

    def test_cycle_is_caught(self):
        doc = valid_curriculum()
        cs = doc["modules"][0]["lessons"][0]["concepts"]
        cs[0]["prereq"] = ["linalg.eigenvector"]
        cs[1]["prereq"] = ["linalg.eigenvalue"]
        assert "CUR004" in errors(zs.rule_curriculum(doc, "x"))

    def test_external_background_is_not_a_dangling_reference(self):
        doc = valid_curriculum()
        doc["modules"][0]["lessons"][0]["concepts"][0]["external_prereq"] = \
            ["matrix multiplication"]
        assert errors(zs.rule_curriculum(doc, "x")) == []


# --------------------------------------------------------------------------
# course and config rules
# --------------------------------------------------------------------------

class TestCourseAndConfigRules:
    def test_active_course_without_environment_setup_is_blocked(self):
        doc = valid_course(status="active")
        assert "CRS001" in errors(zs.rule_course(doc, "x"))

    def test_planning_course_may_legitimately_lack_it(self):
        assert errors(zs.rule_course(valid_course(), "x")) == []

    def test_active_course_with_completed_setup_passes(self):
        doc = valid_course(status="active")
        doc["environment"]["completed_at"] = "2026-09-05T00:00:00+00:00"
        assert errors(zs.rule_course(doc, "x")) == []

    def test_notes_need_a_markdown_copy(self):
        cfg = valid_config()
        cfg["notes"] = {"document_dir": "E:/docs"}
        assert "CFG001" in errors(zs.rule_config(cfg, "x"))

    def test_a_document_folder_with_no_format_is_flagged(self):
        """A warning rather than a refusal: it costs the learner a document
        they expected, not correctness."""
        cfg = valid_config()
        cfg["notes"] = {"markdown_dir": "E:/n", "document_dir": "E:/d",
                        "document_format": "none"}
        codes = [f.code for f in zs.rule_config(cfg, "x")]
        assert "CFG002" in codes

    def test_a_raw_api_key_in_config_is_refused(self):
        cfg = valid_config()
        cfg["ocr"] = {"provider": "deepseek-ocr",
                      "endpoint": "sk_livekey0123456789abcdefghijklmnop"}
        assert "CFG003" in errors(zs.rule_config(cfg, "x"))

    def test_an_env_var_name_is_fine(self):
        cfg = valid_config()
        cfg["ocr"] = {"provider": "deepseek-ocr",
                      "api_key_env": "DEEPSEEK_OCR_API_KEY"}
        assert errors(zs.rule_config(cfg, "x")) == []

    def test_teaching_language_is_required_and_never_defaulted(self):
        cfg = valid_config()
        del cfg["teaching_language"]
        assert any("teaching_language" in e
                   for e in zs.validate_doc(cfg, "config"))


# --------------------------------------------------------------------------
# path safety
# --------------------------------------------------------------------------

class TestPathSafety:
    def test_absolute_path_is_refused(self, tmp_path):
        with pytest.raises(ValueError):
            zs.resolve_in_root(tmp_path, str(tmp_path / "x.json"))

    def test_parent_escape_is_refused(self, tmp_path):
        with pytest.raises(ValueError):
            zs.resolve_in_root(tmp_path, "../outside.json")

    def test_nested_escape_is_refused(self, tmp_path):
        with pytest.raises(ValueError):
            zs.resolve_in_root(tmp_path, "courses/../../outside.json")

    def test_normal_relative_path_is_fine(self, tmp_path):
        got = zs.resolve_in_root(tmp_path, "courses/x/course.json")
        assert got == (tmp_path / "courses/x/course.json").resolve()


# --------------------------------------------------------------------------
# command line behaviour and exit codes
# --------------------------------------------------------------------------

def run(argv):
    return zs.main(argv)


class TestCli:
    def test_init_creates_the_layout(self, tmp_path):
        assert run(["--root", str(tmp_path), "init"]) == zs.EXIT_OK
        for d in zs.LAYOUT_DIRS:
            assert (tmp_path / d).is_dir()
        assert (tmp_path / ".zepteach-root").exists()

    def test_init_seeds_an_empty_concept_registry(self, tmp_path):
        # present but empty, so that teaching an unregistered concept is
        # caught from the very first course rather than silently allowed
        run(["--root", str(tmp_path), "init"])
        reg = zs.read_json(tmp_path / "concepts.json")
        assert reg["concepts"] == []
        assert zs.validate_doc(reg, "concept_registry") == []

    def test_init_reports_that_stage_one_has_not_run(self, tmp_path, capsys):
        run(["--root", str(tmp_path), "init"])
        out = capsys.readouterr().out
        assert "stage 1 has NOT run" in out

    def test_check_accepts_a_good_document(self, tmp_path):
        code = run(["check", "--schema", "course",
                    "--data", json.dumps(valid_course())])
        assert code == zs.EXIT_OK

    def test_check_rejects_a_bad_document_with_exit_two(self, tmp_path):
        bad = valid_attempt()
        bad.pop("evidence_quotes")
        assert run(["check", "--schema", "attempt",
                    "--data", json.dumps(bad)]) == zs.EXIT_VALIDATION

    def test_write_refuses_to_persist_an_invalid_document(self, tmp_path):
        run(["--root", str(tmp_path), "init"])
        bad = valid_course()
        bad["status"] = "active"  # no environment.completed_at
        code = run(["--root", str(tmp_path), "write",
                    "--path", "courses/linear-algebra/course.json",
                    "--schema", "course", "--data", json.dumps(bad)])
        assert code == zs.EXIT_VALIDATION
        assert not (tmp_path / "courses/linear-algebra/course.json").exists()

    def test_write_then_read_round_trip(self, tmp_path):
        run(["--root", str(tmp_path), "init"])
        assert run(["--root", str(tmp_path), "write",
                    "--path", "courses/linear-algebra/course.json",
                    "--schema", "course",
                    "--data", json.dumps(valid_course())]) == zs.EXIT_OK
        assert run(["--root", str(tmp_path), "read",
                    "--path", "courses/linear-algebra/course.json"]) == zs.EXIT_OK

    def test_append_refuses_an_unearned_pass(self, tmp_path):
        run(["--root", str(tmp_path), "init"])
        bad = valid_attempt()
        bad.pop("evidence_quotes")
        code = run(["--root", str(tmp_path), "append",
                    "--path", "courses/linear-algebra/attempts.jsonl",
                    "--schema", "attempt", "--data", json.dumps(bad)])
        assert code == zs.EXIT_VALIDATION
        assert not (tmp_path / "courses/linear-algebra/attempts.jsonl").exists()

    def test_append_accepts_an_evidenced_pass(self, tmp_path):
        run(["--root", str(tmp_path), "init"])
        assert run(["--root", str(tmp_path), "append",
                    "--path", "courses/linear-algebra/attempts.jsonl",
                    "--schema", "attempt",
                    "--data", json.dumps(valid_attempt())]) == zs.EXIT_OK
        rows = zs.read_jsonl(tmp_path / "courses/linear-algebra/attempts.jsonl")
        assert len(rows) == 1

    def test_read_missing_file_exits_five(self, tmp_path):
        run(["--root", str(tmp_path), "init"])
        assert run(["--root", str(tmp_path), "read",
                    "--path", "courses/nope/course.json"]) == zs.EXIT_NOT_FOUND

    def test_unknown_schema_exits_five(self):
        assert run(["schema", "nonsense"]) == zs.EXIT_NOT_FOUND

    def test_write_outside_the_root_is_refused(self, tmp_path):
        run(["--root", str(tmp_path), "init"])
        code = run(["--root", str(tmp_path), "write",
                    "--path", "../escaped.json", "--schema", "course",
                    "--data", json.dumps(valid_course())])
        assert code == zs.EXIT_VALIDATION
        assert not (tmp_path.parent / "escaped.json").exists()


# --------------------------------------------------------------------------
# the environment gate: setup stage 2 must have run before teaching
# --------------------------------------------------------------------------

class TestEnvironmentGate:
    def _course_dir(self, tmp_path, course):
        run(["--root", str(tmp_path), "init"])
        d = tmp_path / "courses" / "linear-algebra"
        d.mkdir(parents=True, exist_ok=True)
        zs.atomic_write_json(d / "course.json", course)
        return d

    def test_gate_blocks_when_stage_two_never_ran(self, tmp_path):
        self._course_dir(tmp_path, valid_course())
        assert run(["--root", str(tmp_path), "gate", "course-env",
                    "--course", "linear-algebra"]) == zs.EXIT_GATE

    def test_gate_blocks_when_a_required_target_is_out_of_reach(self,
                                                               tmp_path):
        course = valid_course()
        course["environment"]["completed_at"] = "2026-09-05T00:00:00+00:00"
        course["environment"]["resolution"] = [
            {"target_id": "problem-set", "reach": "out_of_reach",
             "where": "none"}
        ]
        self._course_dir(tmp_path, course)
        assert run(["--root", str(tmp_path), "gate", "course-env",
                    "--course", "linear-algebra"]) == zs.EXIT_GATE

    def test_gate_passes_when_everything_required_is_within_reach(self,
                                                                  tmp_path):
        course = valid_course()
        course["environment"]["completed_at"] = "2026-09-05T00:00:00+00:00"
        course["environment"]["resolution"] = [
            {"target_id": "problem-set", "reach": "direct", "where": "local"}
        ]
        self._course_dir(tmp_path, course)
        assert run(["--root", str(tmp_path), "gate", "course-env",
                    "--course", "linear-algebra"]) == zs.EXIT_OK

    def test_a_preferred_target_out_of_reach_does_not_block(self, tmp_path):
        course = valid_course()
        course["environment"]["required_targets"].append(
            {"target_id": "solver", "kind": "solver",
             "named_in_goal": False, "criticality": "preferred"})
        course["environment"]["completed_at"] = "2026-09-05T00:00:00+00:00"
        course["environment"]["resolution"] = [
            {"target_id": "problem-set", "reach": "direct", "where": "local"},
            {"target_id": "solver", "reach": "out_of_reach", "where": "none"},
        ]
        self._course_dir(tmp_path, course)
        assert run(["--root", str(tmp_path), "gate", "course-env",
                    "--course", "linear-algebra"]) == zs.EXIT_OK

    # ---- the ruling that decides whether a shortfall is fatal ------------
    # Same shortfall, two goals. What changes the answer is not how good the
    # substitute is, it is whether the goal asks for understanding or for
    # competence with the thing itself.

    def test_a_stand_in_is_allowed_when_the_goal_does_not_name_the_target(
            self, tmp_path):
        course = valid_course(
            goal="Explain how stream of consciousness organises time.")
        course["domain"] = "literature"
        course["environment"]["required_targets"] = [
            {"target_id": "primary-text", "kind": "primary text",
             "named_in_goal": False, "criticality": "required"}]
        course["environment"]["completed_at"] = "2026-09-05T00:00:00+00:00"
        course["environment"]["resolution"] = [
            {"target_id": "primary-text", "reach": "stand_in",
             "depth_ceiling": 4, "where": "constructed",
             "what_is_lost": "the passage was written for the lesson, so its "
                             "difficulties are the ones we chose to put in"}]
        self._course_dir(tmp_path, course)
        assert run(["--root", str(tmp_path), "gate", "course-env",
                    "--course", "linear-algebra"]) == zs.EXIT_OK

    def test_a_stand_in_is_refused_when_the_goal_names_the_target(self,
                                                                  tmp_path):
        course = valid_course(
            goal="Read Ulysses chapter 3 closely and trace its allusions.")
        course["domain"] = "literature"
        course["environment"]["required_targets"] = [
            {"target_id": "primary-text", "kind": "primary text",
             "named_in_goal": True, "criticality": "required"}]
        course["environment"]["completed_at"] = "2026-09-05T00:00:00+00:00"
        course["environment"]["resolution"] = [
            {"target_id": "primary-text", "reach": "stand_in",
             "depth_ceiling": 4, "where": "constructed",
             "what_is_lost": "an imitation is not the text"}]
        self._course_dir(tmp_path, course)
        assert run(["--root", str(tmp_path), "gate", "course-env",
                    "--course", "linear-algebra"]) == zs.EXIT_GATE

    def test_the_same_ruling_holds_outside_the_humanities(self, tmp_path):
        """The rule is about the goal's verb, not about the subject. A course
        that only needs to explain a mechanism survives losing the tool; one
        that promises competence with the tool does not."""
        codes = []
        for named in (False, True):
            course = valid_course(
                goal=("Explain how a thermostat shapes ensemble sampling."
                      if not named else
                      "Run a production simulation and diagnose "
                      "non-convergence."))
            course["domain"] = "chemistry"
            course["environment"]["required_targets"] = [
                {"target_id": "engine", "kind": "solver",
                 "named_in_goal": named, "criticality": "required"}]
            course["environment"]["completed_at"] =                 "2026-09-05T00:00:00+00:00"
            course["environment"]["resolution"] = [
                {"target_id": "engine", "reach": "stand_in",
                 "depth_ceiling": 4, "where": "constructed",
                 "what_is_lost": "the stand-in integrates one mechanism and "
                                 "ignores the rest"}]
            d = tmp_path / str(named)
            d.mkdir()
            self._course_dir(d, course)
            codes.append(run(["--root", str(d), "gate", "course-env",
                              "--course", "linear-algebra"]))
        assert codes == [zs.EXIT_OK, zs.EXIT_GATE]

    def test_gate_on_a_missing_course_exits_five(self, tmp_path):
        run(["--root", str(tmp_path), "init"])
        assert run(["--root", str(tmp_path), "gate", "course-env",
                    "--course", "ghost"]) == zs.EXIT_NOT_FOUND


# --------------------------------------------------------------------------
# whole-root validation, including checks that span files
# --------------------------------------------------------------------------

def build_root(tmp_path, *, source_anchored=False, attempts=None,
               mastery=None, curriculum=None, registry=None):
    run(["--root", str(tmp_path), "init"])
    zs.atomic_write_json(tmp_path / "config.json", valid_config())
    zs.atomic_write_json(tmp_path / "concepts.json",
                         registry if registry is not None else valid_registry())
    zs.atomic_write_json(tmp_path / "learner" / "profile.json", valid_profile())
    d = tmp_path / "courses" / "linear-algebra"
    d.mkdir(parents=True, exist_ok=True)
    course = valid_course(source_anchored=source_anchored)
    zs.atomic_write_json(d / "course.json", course)
    zs.atomic_write_json(d / "curriculum.json", curriculum or valid_curriculum())
    for row in attempts or []:
        zs.append_jsonl(d / "attempts.jsonl", row)
    for row in mastery or []:
        zs.append_jsonl(tmp_path / "learner" / "mastery.jsonl", row)
    return d


class TestGlobalConcepts:
    """Concepts are shared across courses. That is what stops the system
    re-teaching eigenvalues in the transformer course, and it is also what
    makes naming discipline non-optional."""

    def test_a_concept_id_must_be_namespaced(self):
        doc = valid_curriculum()
        doc["modules"][0]["lessons"][0]["concepts"][0]["concept_id"] = "eigenvalue"
        assert any("pattern" in e for e in zs.validate_doc(doc, "curriculum"))

    def test_registry_accepts_the_fixture(self):
        assert zs.validate_doc(valid_registry(), "concept_registry") == []

    def test_duplicate_registry_ids_are_caught(self):
        reg = valid_registry()
        reg["concepts"][1]["concept_id"] = "linalg.eigenvalue"
        assert "CON001" in errors(zs.rule_concept_registry(reg, "x"))

    def test_same_name_in_two_namespaces_is_surfaced(self):
        reg = valid_registry()
        reg["concepts"].append(
            {"concept_id": "qm.eigenvalue", "canonical_title": "Eigenvalue",
             "domain": "chemistry/quantum"})
        found = zs.rule_concept_registry(reg, "x")
        assert any(f.code == "CON003" for f in found)
        assert errors(found) == []  # a judgement call, not a blocker

    def test_declaring_them_distinct_settles_it(self):
        reg = valid_registry()
        reg["concepts"][0]["distinct_from"] = ["qm.eigenvalue"]
        reg["concepts"].append(
            {"concept_id": "qm.eigenvalue", "canonical_title": "Eigenvalue",
             "domain": "chemistry/quantum",
             "distinct_from": ["linalg.eigenvalue"]})
        assert not any(f.code == "CON003"
                       for f in zs.rule_concept_registry(reg, "x"))

    def test_aliases_are_compared_too(self):
        reg = valid_registry()
        reg["concepts"].append(
            {"concept_id": "qm.energy-level", "canonical_title": "Energy level",
             "domain": "chemistry/quantum", "aliases": ["Eigen Value"]})
        assert any(f.code == "CON003"
                   for f in zs.rule_concept_registry(reg, "x"))

    def test_teaching_an_unregistered_concept_is_caught(self, tmp_path):
        reg = valid_registry()
        reg["concepts"] = [reg["concepts"][0]]
        build_root(tmp_path, registry=reg)
        assert "CON002" in errors(zs.validate_root(tmp_path))

    def test_mastery_for_an_unregistered_concept_is_caught(self, tmp_path):
        row = mastery_mastered(concept_id="ghost.concept")
        build_root(tmp_path, mastery=[row])
        assert "CON004" in errors(zs.validate_root(tmp_path))

    def test_an_unregistered_concept_is_refused_at_write_time(self, tmp_path):
        # caught when it happens, not discovered later by a health check
        run(["--root", str(tmp_path), "init"])
        row = mastery_mastered(concept_id="ghost.concept")
        code = run(["--root", str(tmp_path), "append",
                    "--path", "learner/mastery.jsonl",
                    "--schema", "mastery", "--data", json.dumps(row)])
        assert code == zs.EXIT_VALIDATION
        assert not (tmp_path / "learner" / "mastery.jsonl").exists()

    def test_no_registry_at_all_means_no_membership_enforcement(self, tmp_path):
        # an empty registry still enforces; a missing one cannot
        (tmp_path / "learner").mkdir(parents=True)
        row = mastery_mastered()
        assert "CON004" not in errors(zs.rule_mastery(row, "x"))
        assert "CON004" in errors(zs.rule_mastery(row, "x", None, set()))

    def test_a_prerequisite_from_another_course_resolves(self):
        doc = valid_curriculum()
        doc["modules"][0]["lessons"][0]["concepts"][0]["prereq"] = \
            ["calculus.chain-rule"]
        assert "CUR003" in errors(zs.rule_curriculum(doc, "x"))
        assert "CUR003" not in errors(
            zs.rule_curriculum(doc, "x", {"calculus.chain-rule"}))

    def test_depth_claimed_must_match_what_the_course_declared(self, tmp_path):
        row = mastery_mastered(
            depth_targets=[{"course_id": "c1", "depth_target": 5}])
        build_root(tmp_path, mastery=[row])
        assert "CON006" in errors(zs.validate_root(tmp_path))

    def test_claiming_a_course_that_never_asked_for_it(self, tmp_path):
        row = mastery_mastered(
            courses=["c1", "c9"],
            depth_targets=[{"course_id": "c1", "depth_target": 3},
                           {"course_id": "c9", "depth_target": 2}])
        build_root(tmp_path, mastery=[row])
        assert "CON006" in errors(zs.validate_root(tmp_path))


class TestValidateRoot:
    def test_a_clean_root_reports_nothing(self, tmp_path):
        build_root(tmp_path, attempts=[valid_attempt()],
                   mastery=[mastery_mastered()])
        assert zs.validate_root(tmp_path) == []

    def test_missing_root_is_reported(self, tmp_path):
        found = zs.validate_root(tmp_path / "nope")
        assert "ROOT001" in errors(found)

    def test_a_bad_mastery_row_surfaces_with_its_line_number(self, tmp_path):
        bad = mastery_mastered()
        bad["evidence"] = [e for e in bad["evidence"]
                           if e["kind"] != "transfer_test"]
        build_root(tmp_path, mastery=[mastery_mastered(), bad])
        found = zs.validate_root(tmp_path)
        assert any(f.code == "MAS001" and f.where.endswith(":2") for f in found)

    def test_retesting_with_the_very_same_item_is_caught(self, tmp_path):
        retest = valid_attempt(attempt_id="a2", kind="delayed_retest",
                               exercise_id="e1",
                               submitted_at="2026-09-20T10:00:00+00:00")
        build_root(tmp_path, attempts=[valid_attempt(), retest])
        assert "ATT004" in errors(zs.validate_root(tmp_path))

    def test_retesting_with_a_different_item_is_fine(self, tmp_path):
        retest = valid_attempt(attempt_id="a2", kind="delayed_retest",
                               exercise_id="e2",
                               submitted_at="2026-09-20T10:00:00+00:00")
        build_root(tmp_path, attempts=[valid_attempt(), retest])
        assert "ATT004" not in errors(zs.validate_root(tmp_path))

    def test_source_anchored_course_needs_a_span_on_every_lesson(self, tmp_path):
        build_root(tmp_path, source_anchored=True)
        assert "CUR005" in errors(zs.validate_root(tmp_path))

    def test_source_anchored_course_with_spans_is_clean(self, tmp_path):
        cur = valid_curriculum()
        cur["modules"][0]["lessons"][0]["source_span"] = {
            "source_id": "strang", "section": "6.1",
            "page_start": 283, "page_end": 296,
        }
        build_root(tmp_path, source_anchored=True, curriculum=cur)
        assert "CUR005" not in errors(zs.validate_root(tmp_path))

    def test_config_gap_thresholds_are_applied_to_mastery_rows(self, tmp_path):
        build_root(tmp_path, mastery=[mastery_mastered()])
        cfg = valid_config()
        cfg["defaults"]["transfer_test_min_days"] = 60
        zs.atomic_write_json(tmp_path / "config.json", cfg)
        assert "MAS004" in errors(zs.validate_root(tmp_path))

    def test_validate_command_exits_two_on_a_dirty_root(self, tmp_path):
        bad = mastery_mastered()
        bad["evidence"] = [e for e in bad["evidence"]
                           if e["kind"] != "transfer_test"]
        build_root(tmp_path, mastery=[bad])
        assert run(["--root", str(tmp_path), "validate"]) == zs.EXIT_VALIDATION

    def test_a_warning_alone_does_not_fail_validation(self, tmp_path):
        shaky = mastery_mastered(state="shaky")
        build_root(tmp_path, mastery=[shaky])
        found = zs.validate_root(tmp_path)
        assert errors(found) == []
        assert any(f.code == "MAS002" for f in found)
        assert run(["--root", str(tmp_path), "validate"]) == zs.EXIT_OK

    def test_validate_command_exits_zero_on_a_clean_root(self, tmp_path):
        build_root(tmp_path)
        assert run(["--root", str(tmp_path), "validate"]) == zs.EXIT_OK
