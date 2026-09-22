"""Setting exercises, and catching the ones that only look like exercises.

Every case here is a thing that produces output reading perfectly well while
having lost the point. That is why these are refusals in code rather than
advice in prose: none of them is visible by looking at the result.
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import conftest as fx  # noqa: E402
import constants as K  # noqa: E402
import exercise as ex  # noqa: E402
import zt_state as zs  # noqa: E402
from sandbox import Refused  # noqa: E402


def refusal(fn):
    with pytest.raises(Refused) as exc:
        fn()
    return exc.value


def item(**over):
    doc = {
        "schema_version": 1,
        "exercise_id": "e1",
        "course_id": "linalg",
        "concept_ids": [fx.EIGENVALUE],
        "tier": "variant",
        "prompt": "a question",
        "grader": {"type": "numeric", "tolerance": 0.01},
        "response": {"mode": "free_text"},
    }
    doc.update(over)
    return doc


class TestNothingIsIssuedWithoutAWayToMarkIt:
    def test_an_item_with_no_grader_is_refused(self):
        """Reached by callers that build items in memory. The stored shape
        also requires a grader, so this guards the path that never went
        through the shape check."""
        bad = item()
        bad["grader"] = {}
        r = refusal(lambda: ex.check_issuable(bad))
        assert r.code == "EXE011"
        assert "after the answer arrives" in r.suggestion

    def test_a_rubric_item_must_name_its_rubric(self):
        r = refusal(lambda: ex.check_issuable(
            item(grader={"type": "rubric"})))
        assert r.code == "EXE012"

    def test_a_checker_item_must_name_its_checker(self):
        r = refusal(lambda: ex.check_issuable(
            item(grader={"type": "checker"})))
        assert r.code == "EXE013"

    def test_an_ordinary_item_passes(self):
        assert ex.check_issuable(item())["ok"]


class TestAnExecutionSlipDoesNotStartAFullRetestLoop:
    def test_same_session_same_concept_is_refused(self):
        previous = {"session_id": "session-one",
                    "concept_ids": [fx.EIGENVALUE],
                    "execution_only": True, "verdict": "partial"}
        r = refusal(lambda: ex.check_retry_after_slip(
            item(session_id="session-one"), [previous]))
        assert r.code == "EXE030"
        assert "move to the next concept" in r.suggestion

    def test_an_explicit_learner_request_can_repeat(self):
        previous = {"session_id": "session-one",
                    "concept_ids": [fx.EIGENVALUE],
                    "execution_only": True}
        doc = item(session_id="session-one", learner_requested_repeat=True,
                   repeat_reason="I want another full example")
        ex.check_retry_after_slip(doc, [previous])

    def test_new_session_or_new_concept_can_continue(self):
        previous = {"session_id": "session-one",
                    "concept_ids": [fx.EIGENVALUE],
                    "execution_only": True}
        ex.check_retry_after_slip(item(session_id="session-two"), [previous])
        ex.check_retry_after_slip(item(session_id="session-one",
                                       concept_ids=[fx.SHARED]), [previous])

    def test_only_slipped_part_is_blocked(self):
        previous = {"session_id": "session-one",
                    "concept_ids": [fx.EIGENVALUE, fx.SHARED],
                    "concept_results": [
                        {"concept_id": fx.EIGENVALUE, "verdict": "pass"},
                        {"concept_id": fx.SHARED, "verdict": "partial",
                         "execution_only": True}]}
        ex.check_retry_after_slip(item(session_id="session-one",
                                       concept_ids=[fx.EIGENVALUE]), [previous])
        assert refusal(lambda: ex.check_retry_after_slip(
            item(session_id="session-one", concept_ids=[fx.SHARED]),
            [previous])).code == "EXE030"

    def test_issue_command_does_not_keep_the_refused_repeat(self, root):
        course_dir = root / "courses" / "linear-algebra"
        zs.append_jsonl(course_dir / "attempts.jsonl", {
            "session_id": "session-one", "concept_ids": [fx.EIGENVALUE],
            "execution_only": True, "verdict": "partial"})
        candidate = root / "candidate.json"
        candidate.write_text(json.dumps(item(session_id="session-one")),
                             encoding="utf-8")
        code = ex.main(["issue", "--root", str(root), "--course",
                        "linear-algebra", "--file", str(candidate)])
        assert code == zs.EXIT_GATE
        assert zs.read_jsonl(course_dir / "exercises.jsonl") == []


class TestDifficultyComesFromOutside:
    def test_an_anchored_item_must_name_its_source(self):
        """An anchored item whose source cannot be named is an item this
        system invented and then called hard."""
        r = refusal(lambda: ex.check_issuable(item(tier="anchored")))
        assert r.code == "EXE014"
        assert "invented and then called hard" in r.suggestion

    def test_a_properly_sourced_anchored_item_passes(self):
        assert ex.check_issuable(item(
            tier="anchored", anchor_kind="textbook",
            source_ref="chapter 4, problem 11"))["ok"]

    def test_an_open_ended_item_needs_a_rubric(self):
        r = refusal(lambda: ex.check_issuable(
            item(tier="modeling", grader={"type": "rubric"})))
        assert r.code == "EXE012"


class TestMixedPracticeIsActuallyMixed:
    """Each of these produces a set that passes for mixed. The evidence says
    the benefit comes from having to choose the method; every failure here
    removes the choosing while keeping the appearance."""

    def test_one_concept_is_not_mixed(self):
        r = refusal(lambda: ex.check_issuable(item(interleaved=True)))
        assert r.code == "EXE015"
        assert "which method applies" in r.suggestion

    def test_a_prompt_that_names_the_method_is_not_mixed(self):
        r = refusal(lambda: ex.check_issuable(item(
            interleaved=True, concept_ids=[fx.EIGENVALUE, fx.SHARED],
            reveals_method=True)))
        assert r.code == "EXE016"
        assert "Choosing is the thing being practised" in r.suggestion

    def test_drawing_from_one_lesson_is_not_mixed(self):
        """Within one lesson the learner knows which method is in play
        whatever the item says."""
        r = refusal(lambda: ex.check_issuable(item(
            interleaved=True, concept_ids=[fx.EIGENVALUE, fx.SHARED],
            mixed_from=["l1", "l1"])))
        assert r.code == "EXE017"

    def test_a_genuine_mixed_item_passes(self):
        assert ex.check_issuable(item(
            interleaved=True, concept_ids=[fx.EIGENVALUE, fx.SHARED],
            mixed_from=["l1", "l2"]))["ok"]


class TestComposingASet:
    def pool(self, n_per=3):
        out = []
        for c in (fx.EIGENVALUE, fx.SHARED, fx.EIGENVECTOR):
            for i in range(n_per):
                out.append(item(exercise_id=c + ":" + str(i),
                                concept_ids=[c]))
        return out

    def test_a_set_alternates_rather_than_running(self):
        """Grouping by concept and concatenating gives a set that is mixed on
        paper and blocked in practice: the learner works out the method once
        per group and coasts through the rest."""
        drill = ex.compose_drill(self.pool())
        concepts = [i["concept_ids"][0] for i in drill["items"]]
        assert all(a != b for a, b in zip(concepts, concepts[1:]))

    def test_too_few_concepts_is_refused_with_a_reason(self):
        pool = [item(exercise_id="a", concept_ids=[fx.EIGENVALUE]),
                item(exercise_id="b", concept_ids=[fx.SHARED])]
        drill = ex.compose_drill(pool)
        assert drill["items"] == []
        assert "at least 3" in drill["refused"]
        assert "barely mixing" in drill["hint"]

    def test_items_that_name_their_method_are_left_out(self):
        pool = self.pool()
        pool[0]["reveals_method"] = True
        drill = ex.compose_drill(pool)
        ids = [i["exercise_id"] for i in drill["items"]]
        assert pool[0]["exercise_id"] not in ids

    def test_the_set_warns_that_it_will_feel_worse(self):
        """Performance during mixed practice genuinely drops. Unwarned, that
        reads as going backwards and invites abandoning the method that
        works."""
        drill = ex.compose_drill(self.pool())
        assert "feel worse" in drill["note"]
        assert "delayed test" in drill["note"]

    def test_an_assembled_set_can_be_checked_as_a_whole(self):
        """Item-by-item checks pass on a set that is blocked overall, which
        is the likeliest failure once composition is automatic."""
        blocked = [item(exercise_id="a", concept_ids=[fx.EIGENVALUE]),
                   item(exercise_id="b", concept_ids=[fx.EIGENVALUE]),
                   item(exercise_id="c", concept_ids=[fx.SHARED])]
        out = ex.is_really_mixed(blocked)
        assert out["mixed"] is False
        assert any("consecutive" in p for p in out["problems"])

    def test_a_properly_composed_set_passes_the_whole_check(self):
        drill = ex.compose_drill(self.pool())
        assert ex.is_really_mixed(drill["items"])["mixed"]


class TestTransferSaysWhichWayItMoved:
    def test_a_transfer_item_with_no_dimension_is_refused(self):
        bad = item(transfer_dimensions=[])
        bad["transfer_dimensions"] = []
        r = refusal(lambda: ex.check_transfer(bad))
        assert r.code == "EXE020"
        assert "cannot be checked" in r.suggestion

    def test_knowledge_domain_alone_is_the_weak_case(self):
        """It is exactly what the criterion this replaced already did: an
        open-ended item, or one spanning two concepts. The setting, the form
        and the stakes all stay put."""
        out = ex.transfer_strength(item(
            transfer_dimensions=["knowledge_domain"]))
        assert out["weak"] is True
        assert "the criterion this replaced" in out["why"]

    def test_two_dimensions_are_not_weak(self):
        out = ex.transfer_strength(item(transfer_dimensions=[
            "knowledge_domain", "functional_context"]))
        assert out["weak"] is False

    def test_moving_into_a_real_situation_is_called_out(self):
        out = ex.transfer_strength(item(
            transfer_dimensions=["functional_context"]))
        assert "do not arrive tidied" in out["note"]

    def test_the_six_dimensions_are_the_published_ones(self):
        dims = zs.shared_defs()["transfer_dimension"]["enum"]
        assert dims == ["knowledge_domain", "physical_context",
                        "temporal_context", "functional_context",
                        "social_context", "modality"]

    def test_a_transfer_item_validates_with_its_dimensions(self):
        doc = item(transfer_dimensions=["modality", "social_context"])
        assert zs.validate_doc(doc, "exercise") == []


class TestEveryLessonOwesAnExplainBack:
    def test_the_item_is_generated_for_a_concept(self):
        it = ex.explain_back_item(fx.EIGENVALUE, "linalg")
        assert it["form"] == "explain_back"
        assert zs.validate_doc(it, "exercise") == []

    def test_it_has_no_tier_and_that_is_allowed(self):
        """An explain-back is not taken from a source, not a variant of one,
        and not an open-ended task, so no tier describes it. The attempt
        schema was corrected for this during an earlier walkthrough; the
        exercise schema still demanded a tier, which made the one item every
        lesson owes impossible to record."""
        it = ex.explain_back_item(fx.EIGENVALUE, "linalg")
        assert "tier" not in it
        assert zs.validate_doc(it, "exercise") == []
        assert [f.code for f in zs.rule_exercise(it, "x")] == []
        assert ex.check_issuable(it)["ok"]

    def test_anything_else_without_a_tier_is_still_flagged(self):
        bad = item()
        del bad["tier"]
        assert "EXE006" in [f.code for f in zs.rule_exercise(bad, "x")]

    def test_it_asks_for_the_boundary_too(self):
        """A concept without its failure mode gets misapplied, so saying it
        back has to include where it stops working."""
        it = ex.explain_back_item(fx.EIGENVALUE)
        assert "stop working" in it["prompt"]

    def test_the_id_is_conventional_so_reuse_is_detectable(self):
        """Reusing the same explain-back later as a delayed retest would pass
        unnoticed with a random id."""
        assert ex.explain_back_item("x.y")["exercise_id"] == \
            "explain-back:x.y"

    def test_concepts_taught_but_not_said_back_are_named(self):
        owed = ex.owed_explain_backs(
            [fx.EIGENVALUE, fx.SHARED],
            [{"form": "explain_back",
              "exercise_id": "explain-back:" + fx.EIGENVALUE}])
        assert owed == [fx.SHARED]

    def test_nothing_is_owed_once_all_are_done(self):
        assert ex.owed_explain_backs(
            [fx.EIGENVALUE],
            [{"form": "explain_back",
              "exercise_id": "explain-back:" + fx.EIGENVALUE}]) == []


class TestTheNumbersAreDeclared:
    def test_the_mixing_minimum_cites_the_experiments(self):
        spec = K.TUNABLE["mixed_set_min_concepts"]
        assert "abcbcacab" in spec["source"]

    def test_the_set_length_admits_nothing_established_it(self):
        spec = K.TUNABLE["mixed_set_size"]
        assert spec["kind"] == "calibrated"
        assert "Nothing establishes" in spec["why"]


class TestCli:
    def run(self, argv):
        try:
            return ex.main(argv)
        except SystemExit as exc:
            return exc.code

    def test_a_schema_violation_exits_two_not_three(self, capsys):
        """Two different failures with two different codes. An empty grader
        is caught by the shape check before any judgement is applied."""
        bad = item()
        bad["grader"] = {}
        assert self.run(["check", "--data", json.dumps(bad)]) ==             zs.EXIT_VALIDATION

    def test_a_refusal_exits_three_and_explains(self, capsys):
        """Well-formed and still not issuable: rubric marking with no rubric
        named. This is the path the shape check cannot see."""
        code = self.run(["check", "--data", json.dumps(
            item(grader={"type": "rubric"}))])
        err = capsys.readouterr().err
        assert code == zs.EXIT_GATE
        assert "EXE012" in err
        assert "instead:" in err

    def test_tiers_says_where_difficulty_comes_from(self, capsys):
        assert self.run(["tiers"]) == zs.EXIT_OK
        out = capsys.readouterr().out
        assert "outside this system entirely" in out

    def test_transfer_reports_the_weak_case(self, capsys):
        self.run(["transfer", "--data", json.dumps(
            item(transfer_dimensions=["knowledge_domain"]))])
        assert "WEAK" in capsys.readouterr().out
