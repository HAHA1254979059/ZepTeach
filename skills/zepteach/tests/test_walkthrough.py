"""Regression tests from the paper walkthrough of the S2 doctrine.

Walking the session protocol step by step against the actual scripts found
eleven places where the doctrine told the teacher to do something the code
refused, or described a mechanism nobody was instructed to drive. Each one is
pinned here so it cannot come back.

The category that mattered most was not "wrong value" but "instruction that
cannot be carried out" - a doctrine file can read perfectly and still be
impossible to follow.
"""

import json
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
REF_DIR = SKILL_DIR / "references"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import learner as ln  # noqa: E402
import route as rt  # noqa: E402
import zt_state as zs  # noqa: E402
import conftest as fx  # noqa: E402


def ref(name):
    return (REF_DIR / name).read_text(encoding="utf-8")


class TestProductiveFailureIsActuallyRunnable:
    """Finding 1: the mode asked for an attempt before teaching, and `record`
    refuses attempts on untaught concepts. The whole mode was dead."""

    def _teach(self, root, concepts="linalg.eigenvalue"):
        last = zs.EXIT_OK
        for cid in concepts.split(","):
            last = ln.main([
                "--root", str(root), "teach", "--course", "linear-algebra",
                "--data", json.dumps(fx.exposition(
                    cid, lesson_id="l1",
                    delivered_at="2026-09-01T09:00:00+00:00"))])
            if last != zs.EXIT_OK:
                return last
        return last

    def test_the_failed_first_attempt_can_be_recorded(self, root):
        self._teach(root)
        pf = fx.attempt(attempt_id="pf1", exercise_id="pf-e1", tier="anchored",
                        verdict="fail",
                        failure_points=["never formed the characteristic polynomial"])
        pf.pop("evidence_quotes")
        assert ln.main(["--root", str(root), "record", "--course",
                        "linear-algebra", "--data", json.dumps(pf)]) == \
            zs.EXIT_OK

    def test_a_failure_does_not_demote_a_concept_that_was_only_introduced(
            self, root):
        self._teach(root)
        pf = fx.attempt(attempt_id="pf1", exercise_id="pf-e1", tier="anchored",
                        verdict="fail", failure_points=["no idea"])
        pf.pop("evidence_quotes")
        ln.main(["--root", str(root), "record", "--course", "linear-algebra",
                 "--data", json.dumps(pf)])
        assert ln.load_mastery(root)[0]["state"] == "introduced"

    def test_the_doctrine_puts_the_explanation_after_the_failed_attempt(self):
        """The order this mode needs, now that recording teaching means
        recording what was said.

        The first attempt goes in as a probe, which is the one kind allowed
        on a concept nothing has explained yet. The explanation comes after
        and points at where the attempt broke. Finding 1 was that the mode
        was unrunnable; the fix then was to teach first, which worked and
        also made the explanation optional, because `teach` took no content.
        """
        s = ref("mode-router.md")
        assert "`kind: probe`" in s
        assert "after_failed_attempt" in s
        assert "Step 6 is the one that goes missing" in s

    def test_the_precondition_is_reachable_through_a_probe(self):
        """Finding 4: requiring prerequisites at consolidating made the mode
        unreachable, because a probe never moves state."""
        s = ref("mode-router.md")
        assert "the probe came back clean" in s
        assert "A failed probe kills this mode" in s


class TestExplainBackIsRecordable:
    """Findings 2 and 3: the doctrine said to record `form: explain_back`,
    but attempts had no `form` field and demanded an exercise tier."""

    def _eb(self, **over):
        doc = {
            "schema_version": 1, "attempt_id": "eb1", "course_id": "linalg",
            "exercise_id": "explain-back:linalg.eigenvalue",
            "concept_ids": ["linalg.eigenvalue"], "kind": "inclass",
            "form": "explain_back", "verdict": "pass", "graded_by": "manual",
            "submitted_at": "2026-09-01T10:30:00+00:00",
            "evidence_quotes": ["said eigenvalues make A - lambda I singular"],
            "latency_rating": "effortful", "latency_source": "inferred",
            "depth_demonstrated": 2,
        }
        doc.update(over)
        return doc

    def test_it_validates_with_no_tier(self):
        assert zs.validate_doc(self._eb(), "attempt") == []
        assert zs.rule_attempt(self._eb(), "x") == []

    def test_an_ordinary_exercise_attempt_still_needs_a_tier(self):
        a = fx.attempt()
        a.pop("tier")
        codes = [f.code for f in zs.rule_attempt(a, "x")
                 if f.severity == "error"]
        assert "ATT006" in codes

    def test_a_probe_needs_no_tier_either(self):
        a = fx.attempt(kind="probe")
        a.pop("tier")
        assert [f for f in zs.rule_attempt(a, "x")
                if f.severity == "error"] == []

    def test_giving_a_probe_a_tier_is_flagged(self):
        a = fx.attempt(kind="probe", tier="anchored")
        assert any(f.code == "ATT006" for f in zs.rule_attempt(a, "x"))

    def test_it_reaches_practiced_through_the_normal_path(self, root):
        ln.main(["--root", str(root), "teach", "--course",
                        "linear-algebra", "--data",
                        json.dumps(fx.exposition(
                            "linalg.eigenvalue", lesson_id="l1",
                            delivered_at="2026-09-01T09:00:00+00:00"))])
        assert ln.main(["--root", str(root), "record", "--course",
                        "linear-algebra",
                        "--data", json.dumps(self._eb())]) == zs.EXIT_OK
        assert ln.load_mastery(root)[0]["state"] == "practiced"

    def test_the_stable_id_makes_reuse_as_a_retest_detectable(self, root):
        ln.main(["--root", str(root), "teach", "--course",
                        "linear-algebra", "--data",
                        json.dumps(fx.exposition(
                            "linalg.eigenvalue", lesson_id="l1",
                            delivered_at="2026-09-01T09:00:00+00:00"))])
        ln.main(["--root", str(root), "record", "--course", "linear-algebra",
                 "--data", json.dumps(self._eb())])
        ln.main(["--root", str(root), "record", "--course", "linear-algebra",
                 "--data", json.dumps(self._eb(
                     attempt_id="eb2", kind="delayed_retest",
                     submitted_at="2026-09-20T10:00:00+00:00"))])
        assert "ATT004" in [f.code for f in zs.validate_root(root)]


class TestTheSchedulingInputsAreAskedFor:
    """Findings 5 and 6: recall effort is the main input to the interval and
    depth is what the ceiling checks, and no doctrine file mentioned either."""

    def test_missing_recall_effort_is_surfaced(self):
        a = fx.attempt()
        a.pop("latency_rating")
        a.pop("latency_source")
        assert "ATT008" in [f.code for f in zs.rule_attempt(a, "x")]

    def test_missing_depth_on_a_pass_is_surfaced(self):
        assert "ATT007" in [f.code for f in zs.rule_attempt(fx.attempt(), "x")]

    def test_neither_blocks_the_write(self, root):
        ln.main(["--root", str(root), "teach", "--course",
                        "linear-algebra", "--data",
                        json.dumps(fx.exposition(
                            "linalg.eigenvalue", lesson_id="l1",
                            delivered_at="2026-09-01T09:00:00+00:00"))])
        a = fx.attempt()
        a.pop("latency_rating")
        a.pop("latency_source")
        assert ln.main(["--root", str(root), "record", "--course",
                        "linear-algebra",
                        "--data", json.dumps(a)]) == zs.EXIT_OK

    def test_a_probe_is_exempt_from_both(self):
        a = fx.attempt(kind="probe")
        a.pop("tier")
        a.pop("latency_rating")
        a.pop("latency_source")
        codes = [f.code for f in zs.rule_attempt(a, "x")]
        assert "ATT007" not in codes and "ATT008" not in codes

    def test_the_doctrine_now_asks_for_the_rating(self):
        s = ref("teaching-contract.md")
        assert "Rate how hard the recall was" in s
        for level in ("instant", "fluent", "effortful",
                      "recovered_with_hint"):
            assert level in s
        assert "learner_corrected" in s

    def test_the_doctrine_now_asks_for_the_depth(self):
        assert "depth_demonstrated" in ref("teaching-contract.md")


class TestInterleavingIsCheckable:
    """Finding 11: the drill was mandatory but nothing marked an item as
    interleaved, so nobody could tell whether it happened."""

    def test_a_single_concept_interleaved_item_is_refused(self):
        a = fx.attempt(interleaved=True)
        assert "ATT009" in [f.code for f in zs.rule_attempt(a, "x")
                            if f.severity == "error"]

    def test_a_multi_concept_one_is_accepted(self):
        a = fx.attempt(interleaved=True,
                       concept_ids=["linalg.eigenvalue", "linalg.eigenvector"])
        assert "ATT009" not in [f.code for f in zs.rule_attempt(a, "x")]

    def test_the_same_rule_applies_to_the_exercise(self):
        ex = fx.attempt  # placeholder to keep the import used
        item = {"schema_version": 1, "exercise_id": "i1",
                "course_id": "linalg", "concept_ids": ["linalg.eigenvalue"],
                "tier": "variant", "prompt": "solve", "interleaved": True,
                "response": {"mode": "free_text"},
                "grader": {"type": "numeric"}}
        assert "EXE005" in [f.code for f in zs.rule_exercise(item, "x")]

    def test_the_session_can_record_whether_the_drill_happened(self):
        props = zs.load_schema("session")["properties"]["outcome"]["properties"]
        assert "interleaved_drill_done" in props
        assert "modes_used" in props


class TestTheRoutesCoverTheProtocol:
    """Findings 7 and 8: the lesson route did not carry what protocol step 3
    needs, and the lookup doctrine was referenced by nothing at all."""

    def test_the_lesson_route_chains_to_what_it_will_need(self):
        res = rt.resolve("lesson")
        assert "review" in res["then"]
        assert "exercise" in res["then"]
        assert "notes" in res["then"]
        assert "close" in res["then"]

    def test_chained_routes_are_not_loaded_up_front(self):
        res = rt.resolve("lesson")
        assert "mastery-policy.md" not in res["read"]
        assert "exercise-engine.md" not in res["read"]

    def test_the_chain_is_visible_in_the_rendered_route(self):
        text = rt.render(rt.resolve("lesson"))
        assert "LATER, SEPARATELY" in text
        assert "do not load these now" in text

    def test_there_is_a_route_for_going_and_checking(self):
        res = rt.resolve("lookup")
        assert "tool-integration.md" in res["read"]

    def test_the_persona_points_at_it(self):
        assert "for lookup" in ref("persona-zep.md")

    def test_the_protocol_defers_the_review_route(self):
        assert "route.py for review" in ref("session-protocol.md")


class TestTheProtocolDrivesTheMechanisms:
    """Findings 9, 10 and 12: nothing said to scope the teaching event, to
    call `turn` at all, or what to do when the backlog forbids new material."""

    def test_teaching_cannot_be_claimed_for_a_whole_lesson_at_once(self, root):
        """What used to be a scoping convention is now the only option.

        `teach` once took a lesson and marked every concept in it, which made
        "I taught six things" a single call with no content in it. Finding 9
        was that nothing told the protocol to scope that call. Scoping it was
        never the real answer: the call was free either way, so whichever
        number it wrote down was equally unsupported. It now takes one
        explanation for one concept, and the second concept in the lesson
        stays unseen until something is recorded as having been said about
        it.
        """
        cur = fx.curriculum()
        cur["modules"][0]["lessons"][0]["concepts"] = [
            {"concept_id": "linalg.eigenvalue", "title": "E",
             "depth_target": 3},
            {"concept_id": "linalg.eigenvector", "title": "V",
             "depth_target": 3},
        ]
        zs.atomic_write_json(
            root / "courses" / "linear-algebra" / "curriculum.json", cur)
        ln.main(["--root", str(root), "teach", "--course", "linear-algebra",
                 "--data", json.dumps(fx.exposition(
                     "linalg.eigenvalue", lesson_id="l1",
                     delivered_at="2026-09-01T09:00:00+00:00"))])
        introduced = [r["concept_id"] for r in ln.load_mastery(root)
                      if r["state"] == "introduced"]
        assert introduced == ["linalg.eigenvalue"]

    def test_the_turn_cadence_is_stated_in_both_places(self):
        for f in ("session-protocol.md", "context-budget.md"):
            s = ref(f)
            assert "after every exchange" in s, f

    def test_a_severe_backlog_skips_teaching_rather_than_shrinking_it(self):
        s = ref("session-protocol.md")
        assert "skip this step" in s
        assert "do not teach a little bit anyway" in s
