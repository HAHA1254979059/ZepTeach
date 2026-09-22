"""A multi-concept answer must not copy one verdict to every concept."""

import json

import conftest as fx
import grade as gr
import learner as ln
import zt_state as zs
from sandbox import Refused


def _partial_attempt():
    return fx.attempt(
        attempt_id="mixed-1", exercise_id="mixed-item",
        concept_ids=[fx.EIGENVALUE, fx.SHARED],
        kind="delayed_retest", tier="variant", verdict="partial",
        answer="The first rule is stated. The second answer is wrong.",
        evidence_quotes=["The first rule is stated"],
        failure_points=["second part"],
        submitted_at="2026-09-09T10:00:00+00:00",
        concept_results=[
            {"concept_id": fx.EIGENVALUE, "verdict": "pass",
             "evidence_quotes": ["The first rule is stated"],
             "latency_rating": "fluent", "depth_demonstrated": 2},
            {"concept_id": fx.SHARED, "verdict": "fail",
             "failure_points": ["second part"],
             "latency_rating": "effortful"},
        ])


def test_new_multi_concept_attempt_without_separate_results_is_refused(root):
    attempt = _partial_attempt()
    attempt.pop("concept_results")
    code = ln.main(["--root", str(root), "record", "--course",
                    "linear-algebra", "--data", json.dumps(attempt)])
    assert code == zs.EXIT_VALIDATION
    assert ln.load_mastery(root) == []


def test_one_failed_part_does_not_lower_the_independent_pass(root):
    assert fx.teach(root, fx.EIGENVALUE, exposition_id="teach-first") == 0
    assert fx.teach(root, fx.SHARED, exposition_id="teach-second") == 0
    for idx, cid in enumerate((fx.EIGENVALUE, fx.SHARED), 1):
        single = fx.attempt(attempt_id="practice-" + str(idx),
                            exercise_id="practice-item-" + str(idx),
                            concept_ids=[cid])
        assert ln.main(["--root", str(root), "record", "--course",
                        "linear-algebra", "--data", json.dumps(single)]) == 0
    assert ln.main(["--root", str(root), "record", "--course",
                    "linear-algebra", "--data",
                    json.dumps(_partial_attempt())]) == 0
    states = {r["concept_id"]: r["state"] for r in ln.load_mastery(root)}
    assert states[fx.EIGENVALUE] == "consolidating"
    assert states[fx.SHARED] == "shaky"


def test_pass_for_one_concept_requires_a_quote_from_the_answer():
    attempt = _partial_attempt()
    attempt["concept_results"][0]["evidence_quotes"] = ["not in answer"]
    assert any(f.code == "ATT011" for f in zs.rule_attempt(attempt, "x"))


def test_marker_splits_criteria_before_scoring_concepts():
    item = {"concept_ids": ["course.first", "course.second"]}
    rubric = {"pass_threshold": 1.0, "criteria": [
        {"criterion_id": "first", "concept_id": "course.first",
         "required_for_pass": True, "kind": "concept", "depth": 2},
        {"criterion_id": "second", "concept_id": "course.second",
         "required_for_pass": True, "kind": "concept", "depth": 2},
    ]}
    verdict = {"verdict": "partial", "criteria_met": {
        "first": {"met": True, "quotes": ["first rule"]},
        "second": {"met": False}}}
    results = gr.concept_results(verdict, rubric, item)
    assert [(r["concept_id"], r["verdict"]) for r in results] == [
        ("course.first", "pass"), ("course.second", "fail")]


def test_marker_refuses_an_unassigned_criterion():
    item = {"concept_ids": ["course.first", "course.second"]}
    rubric = {"criteria": [{"criterion_id": "shared"}]}
    try:
        gr.concept_results({"criteria_met": {}}, rubric, item)
    except Refused as error:
        assert error.code == "GRD020"
    else:
        raise AssertionError("unassigned multi-concept evidence was accepted")


def test_rubric_cannot_fail_an_unannounced_other_concept():
    item = {"concept_ids": ["course.first"]}
    rubric = {"criteria": [{"criterion_id": "extra",
                            "concept_id": "course.second"}]}
    try:
        gr.check_concept_coverage(rubric, item)
    except Refused as error:
        assert error.code == "GRD019"
    else:
        raise AssertionError("a foreign concept entered the rubric")


def test_unassessed_answer_is_kept_without_lowering_mastery(root):
    assert fx.teach(root) == zs.EXIT_OK
    attempt = fx.attempt(verdict="unassessed", evidence_quotes=[],
                         answer="a different route needs review")
    assert ln.main(["--root", str(root), "record", "--course",
                    "linear-algebra", "--data", json.dumps(attempt)]) == 0
    assert ln.load_mastery(root)[0]["state"] == "introduced"
    kept = zs.read_jsonl(root / "courses" / "linear-algebra" /
                         "attempts.jsonl")
    assert kept[0]["verdict"] == "unassessed"


def test_unassessed_work_does_not_claim_an_untaught_concept_was_taught(root):
    attempt = fx.attempt(verdict="unassessed", evidence_quotes=[],
                         answer="the input could not be read")
    assert ln.main(["--root", str(root), "record", "--course",
                    "linear-algebra", "--data", json.dumps(attempt)]) == 0
    assert ln.load_mastery(root) == []


def test_an_unassessable_criterion_does_not_fail_another_concept():
    item = {"concept_ids": ["course.first", "course.second"]}
    rubric = {"criteria": [
        {"criterion_id": "first", "concept_id": "course.first"},
        {"criterion_id": "second", "concept_id": "course.second"}]}
    verdict = {"verdict": "partial", "criteria_met": {
        "first": {"met": True, "quotes": ["first rule"]},
        "second": {"assessable": False,
                   "reason": "valid alternative needs source review"}}}
    assert gr.check_verdict(verdict, rubric, "first rule; another route")["ok"]
    results = gr.concept_results(verdict, rubric, item)
    assert [r["verdict"] for r in results] == ["pass", "unassessed"]


def test_an_unassessable_criterion_cannot_be_used_for_a_pass():
    rubric = {"criteria": [{"criterion_id": "x"}]}
    verdict = {"verdict": "pass", "criteria_met": {
        "x": {"assessable": False, "reason": "needs source review"}}}
    try:
        gr.check_verdict(verdict, rubric, "alternate answer")
    except Refused as error:
        assert error.code == "GRD022"
    else:
        raise AssertionError("unknown evidence was treated as a pass")
