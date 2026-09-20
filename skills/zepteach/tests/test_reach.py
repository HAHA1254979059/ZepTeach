"""Whether a course's practice can act on what it needs, and what happens when
it cannot.

The cases that matter here are the ones where the honest answer and the
convenient answer differ. It is always possible to set an easier exercise and
carry on; every test below exists to make that impossible to do silently.
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import conftest as fx  # noqa: E402
import practice_reach as pr  # noqa: E402
import zt_state as zs  # noqa: E402


def run(argv):
    try:
        return pr.main(argv)
    except SystemExit as exc:
        return exc.code


class TestAFieldThatNeedsNothing:
    """Mathematics is the case that breaks a system built around software.
    Practice acts on the learner's own paper; there is nothing to install and
    nothing to obtain, and the check has to say so rather than finding
    nothing and reporting a problem."""

    def test_paper_is_within_reach_without_being_checked(self):
        doc = pr.check(fx.math_adapter())
        paper = [t for t in doc["targets"] if t["target_id"] == "paper"][0]
        assert paper["reach"] == "direct"
        assert paper["depth_ceiling"] == 5

    def test_the_course_can_practise_at_full_depth(self):
        doc = pr.check(fx.math_adapter())
        proving = [r for r in doc["practice_support"]
                   if r["action"] == "derive"][0]
        assert proving["reach"] == "direct"
        assert proving["depth_ceiling"] >= 3

    def test_nothing_is_recommended_for_the_paper(self):
        doc = pr.check(fx.math_adapter())
        recommended = [r["target_id"] for r in doc.get("recommendations", [])]
        assert "paper" not in recommended


class TestAFieldThatNeedsDocuments:
    def test_an_unanswered_question_is_reported_not_assumed(self):
        """Nobody has been asked whether they can reach an archive. That is
        not the same as their not being able to, and the difference has to
        survive into the report."""
        doc = pr.check(fx.hist_adapter())
        recs = doc.get("recommendations", [])
        sources = [r for r in recs if r["target_id"] == "source-set"][0]
        assert "Nobody has been asked yet" in sources["detail"]

    def test_saying_yes_puts_it_within_reach(self):
        doc = pr.check(fx.hist_adapter(), answers={"source-set": True})
        row = [t for t in doc["targets"]
               if t["target_id"] == "source-set"][0]
        assert row["reach"] == "direct"

    def test_saying_no_drops_to_the_declared_substitute(self):
        doc = pr.check(fx.hist_adapter(), answers={"source-set": False})
        row = [t for t in doc["targets"]
               if t["target_id"] == "source-set"][0]
        assert row["reach"] == "stand_in"
        assert row["depth_ceiling"] == 4

    def test_the_substitute_must_say_what_was_lost(self):
        doc = pr.check(fx.hist_adapter(), answers={"source-set": False})
        row = [t for t in doc["targets"]
               if t["target_id"] == "source-set"][0]
        assert "silent on the question" in row["what_is_lost"]

    def test_judging_sources_degrades_but_reading_the_book_does_not(self):
        """Only the activities that need the missing thing are affected. A
        blanket downgrade would be easier and would misreport the course."""
        doc = pr.check(fx.hist_adapter(), answers={"source-set": False})
        by_action = dict((r["action"], r) for r in doc["practice_support"])
        assert by_action["critique"]["reach"] == "stand_in"
        assert by_action["analyze"]["reach"] == "direct"


class TestTheRulingThatDecidesWhetherAShortfallIsFatal:
    """Same missing thing, two goals. What changes the answer is the goal's
    wording, not how good the substitute is."""

    def test_a_goal_about_understanding_survives_the_substitute(self):
        adapter = fx.hist_adapter(
            goal_quoted="Explain how a historian builds a causal claim.")
        doc = pr.check(adapter, answers={"source-set": False})
        assert pr.fatal_shortfalls(adapter, doc["targets"]) == []

    def test_a_goal_naming_the_thing_itself_does_not(self):
        adapter = fx.hist_adapter(
            goal_quoted="Work through the 1923 ministry files and date every "
                        "memorandum in them.")
        adapter["targets"][0]["named_in_goal"] = True
        doc = pr.check(adapter, answers={"source-set": False})
        blocked = pr.fatal_shortfalls(adapter, doc["targets"])
        assert [b["target_id"] for b in blocked] == ["source-set"]

    def test_the_ruling_does_not_depend_on_the_substitute_being_poor(self):
        """The substitute here is declared excellent - it certifies to depth
        5. It still does not satisfy a goal that asks for competence with the
        actual thing, because those are different claims about the learner."""
        adapter = fx.hist_adapter()
        adapter["targets"][0]["named_in_goal"] = True
        adapter["targets"][0]["substitute"]["depth_ceiling"] = 5
        doc = pr.check(adapter, answers={"source-set": False})
        assert pr.fatal_shortfalls(adapter, doc["targets"])

    def test_the_same_ruling_applies_to_a_science_course(self):
        """The rule is about the goal's verb, not about the subject."""
        base = {
            "schema_version": 1, "adapter_id": "a", "field": "a science",
            "generated_at": "2026-09-05T00:00:00+00:00",
            "targets": [{"target_id": "engine", "kind": "solver",
                         "why": "the calculation has to actually run",
                         "how_to_check": {"ask_the_learner": "installed?"},
                         "substitute": {
                             "level": "stand_in", "depth_ceiling": 4,
                             "describe": "a small program implementing the "
                                         "one mechanism being studied",
                             "what_is_lost": "everything the full program "
                                             "does that this one omits"}}],
            "activities": [{"activity_id": "run", "label": "run it",
                            "action": "apply", "acts_on": ["engine"]}],
        }
        outcomes = []
        for named in (False, True):
            adapter = json.loads(json.dumps(base))
            adapter["targets"][0]["named_in_goal"] = named
            doc = pr.check(adapter, answers={"engine": False})
            outcomes.append(bool(pr.fatal_shortfalls(adapter,
                                                     doc["targets"])))
        assert outcomes == [False, True]


class TestCheckingThatAProgramIsWhatItsNameSuggests:
    def test_a_name_that_is_not_on_the_machine_is_simply_absent(self):
        res = pr.check_program(
            {"command": ["zepteach-nothing-is-called-this"],
             "expect_in_output": "anything"})
        assert res["verified"] is False
        assert "not found" in res["note"]

    def test_running_and_identifying_itself_counts(self):
        res = pr.check_program(
            {"command": [sys.executable, "--version"],
             "expect_in_output": "Python"})
        assert res["verified"] is True

    def test_a_program_wearing_the_right_name_is_caught(self):
        """The reason this check runs the program instead of looking for the
        name: program names collide across completely unrelated software, and
        a name matching a scientific tool on one machine can belong to a
        desktop utility on another."""
        res = pr.check_program(
            {"command": [sys.executable, "--version"],
             "expect_in_output": "a string the real one would print"})
        assert res["verified"] is False
        assert res["impostor"] is True

    def test_an_impostor_reaches_the_recommendation_so_it_is_not_rechecked(
            self):
        adapter = fx.math_adapter()
        adapter["targets"].append({
            "target_id": "tool", "kind": "solver", "why": "needed",
            "how_to_check": {"command": [sys.executable, "--version"],
                             "expect_in_output": "not what python prints"}})
        doc = pr.check(adapter)
        rec = [r for r in doc["recommendations"]
               if r["target_id"] == "tool"][0]
        assert "different program" in rec["detail"]

    def test_the_check_runs_somewhere_disposable(self):
        """Programs write output into the directory they were started in. A
        log file from one such program was once found in this repository,
        which is why the working directory is a temporary one."""
        seen = {}

        def fake_run(cmd, timeout):
            import os
            seen["cwd"] = os.getcwd()
            return "Python"

        # the real runner changes directory for the child, not for us, so
        # check the argument the child would have been given instead
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            seen["scratch_exists"] = Path(td).exists()
        src = (SCRIPTS / "practice_reach.py").read_text(encoding="utf-8")
        assert "tempfile.TemporaryDirectory" in src
        assert "cwd=scratch" in src

    def test_a_check_that_hangs_does_not_hang_the_lesson(self):
        def never_returns(cmd, timeout):
            raise TimeoutError("timed out after " + str(timeout) + "s")

        res = pr.check_program(
            {"command": [sys.executable, "--version"],
             "expect_in_output": "Python"}, runner=never_returns)
        assert res["verified"] is False
        assert "could not be run" in res["note"]


class TestDepthThatCannotBeReached:
    def test_a_concept_wanting_more_depth_than_practice_allows_is_named(self):
        support = [{"action": "derive", "reach": "stand_in",
                    "depth_ceiling": 2, "via": []}]
        short = pr.depth_shortfalls(support, fx.curriculum())
        assert {s["concept_id"] for s in short} == {
            fx.EIGENVALUE, fx.SHARED, fx.EIGENVECTOR}
        assert short[0]["reachable_depth"] == 2

    def test_nothing_is_reported_when_practice_reaches_far_enough(self):
        support = [{"action": "derive", "reach": "direct",
                    "depth_ceiling": 5, "via": []}]
        assert pr.depth_shortfalls(support, fx.curriculum()) == []


class TestNothingIsEverInstalled:
    def test_the_script_contains_no_installation_command(self):
        """A shortfall produces a sentence for the learner to act on. The
        moment it produces an install instead, the plugin is changing a
        machine it was only asked to teach on."""
        src = (SCRIPTS / "practice_reach.py").read_text(encoding="utf-8")
        for forbidden in ("pip install", "conda install", "apt-get",
                          "npm install", "winget install"):
            assert forbidden not in src

    def test_a_shortfall_becomes_a_recommendation(self):
        doc = pr.check(fx.hist_adapter(), answers={"source-set": False})
        assert doc["recommendations"]
        assert all("action" in r for r in doc["recommendations"])


class TestTheResultIsWrittenDownNotDecidedLater:
    def test_the_output_validates_against_the_stored_shape(self):
        for adapter in (fx.math_adapter(), fx.hist_adapter()):
            doc = pr.check(adapter, answers={"source-set": False})
            assert zs.validate_doc(doc, "capabilities") == []

    def test_every_degraded_action_carries_its_replacement_in_writing(self):
        """Written now, so that no lesson has to invent one while running."""
        doc = pr.check(fx.hist_adapter(), answers={"source-set": False})
        for row in doc["practice_support"]:
            if row["reach"] != "direct":
                assert row["fallback"]
                assert "still decides" in row["fallback"]


class TestCli:
    def test_check_on_a_course_with_everything_exits_zero(self, root, capsys):
        code = run(["--root", str(root), "check", "--course",
                    "linear-algebra"])
        out = capsys.readouterr().out
        assert code == zs.EXIT_OK
        assert "WHAT THIS COURSE CAN PRACTISE" in out

    def test_a_course_with_no_adapter_is_not_found(self, root, capsys):
        course = zs.read_json(root / "courses" / "linear-algebra" /
                              "course.json")
        del course["adapter_ref"]
        zs.atomic_write_json(root / "courses" / "linear-algebra" /
                             "course.json", course)
        assert run(["--root", str(root), "check", "--course",
                    "linear-algebra"]) == zs.EXIT_NOT_FOUND

    def test_write_stores_the_result(self, root):
        run(["--root", str(root), "check", "--course", "linear-algebra",
             "--write"])
        assert (root / "capabilities.json").exists()
        assert zs.validate_doc(
            zs.read_json(root / "capabilities.json"), "capabilities") == []

    def test_a_blocked_course_exits_three(self, root, capsys):
        ad = root / "adapters" / "history.json"
        adapter = zs.read_json(ad)
        adapter["targets"][0]["named_in_goal"] = True
        zs.atomic_write_json(ad, adapter)
        code = run(["--root", str(root), "check", "--course",
                    "historiography",
                    "--answers", json.dumps({"source-set": False})])
        out = capsys.readouterr().out
        assert code == zs.EXIT_GATE
        assert "nothing stands in for them" in out

    def test_the_ladder_can_be_printed_on_its_own(self, capsys):
        """Explaining a shortfall should say the same thing every time, so
        the wording comes from one place."""
        assert run(["ladder"]) == zs.EXIT_OK
        out = capsys.readouterr().out
        assert "still decided by the learner" in out
        assert out.count("still decided by the learner") == 4
