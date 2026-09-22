"""What a course has to work with, and how to use it.

The valuable half of this file is not the list of things. It is what the
learner knows about using them, which they already have and will not
volunteer, and which every lesson would otherwise reconstruct from scratch.

The other thing these tests hold down is restraint about wiring. A project
gains integrations easily and sheds them slowly, and each one is something
whose purpose somebody later has to reconstruct.
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import resources as rs  # noqa: E402
import sandbox as sb  # noqa: E402
import zt_state as zs  # noqa: E402


def run(argv):
    try:
        return rs.main(argv)
    except SystemExit as exc:
        return exc.code


def refusal(fn):
    with pytest.raises(sb.Refused) as exc:
        fn()
    return exc.value


def empty(course_id="linalg"):
    return {"schema_version": 1, "course_id": course_id,
            "updated": "2026-09-20T00:00:00+00:00"}


def a_tool(**over):
    doc = {
        "tool_id": "checker",
        "what_it_does": "checks whether a written proof has a gap",
        "runs_where": "this machine",
        "how_to_use": "give it the statement separately from the proof, or "
                      "it assumes the statement is true and finds nothing",
        "limits": "it finds gaps, not wrong claims; a proof of something "
                  "false can pass",
    }
    doc.update(over)
    return doc


class TestNothingIsAssumed:
    def test_a_new_course_has_nothing_recorded(self):
        doc = empty()
        assert doc.get("tools") is None
        assert doc.get("materials") is None

    def test_an_entry_records_who_said_so(self):
        """Either the learner said it or a check found it. Both count; only
        the learner's word covers anything the plugin cannot see."""
        doc = rs.add_tool(empty(), a_tool())
        assert doc["tools"][0]["added_by"] == "learner"

    def test_the_result_validates(self):
        doc = rs.add_tool(empty(), a_tool())
        doc = rs.add_material(doc, {
            "material_id": "m1", "title": "a book", "kind": "textbook",
            "where": "/home/u/books/x.pdf", "edition": "3rd"})
        assert zs.validate_doc(doc, "resources") == []


class TestHowToUseIsThePoint:
    def test_what_the_learner_knows_is_kept(self):
        doc = rs.add_tool(empty(), a_tool())
        t = doc["tools"][0]
        assert "assumes the statement is true" in t["how_to_use"]
        assert "a proof of something" in t["limits"]

    def test_a_tool_the_learner_runs_themselves_is_a_proper_entry(self):
        """Most useful tools are not things this plugin runs. An entry with
        no invocation block is the common case, not an incomplete one."""
        doc = rs.add_tool(empty(), a_tool(
            tool_id="by-hand", runs_where="their own machine",
            reached_how="they run it and paste the output back"))
        assert zs.validate_doc(doc, "resources") == []
        assert "invocation" not in doc["tools"][0]

    def test_recording_the_same_tool_twice_replaces_rather_than_duplicates(
            self):
        doc = rs.add_tool(empty(), a_tool())
        doc = rs.add_tool(doc, a_tool(limits="revised"))
        assert len(doc["tools"]) == 1
        assert doc["tools"][0]["limits"] == "revised"


class TestBoundariesApplyWhereverWorkRuns:
    def test_a_tool_this_plugin_runs_needs_a_time_limit(self):
        r = refusal(lambda: rs.add_tool(empty(), a_tool(invocation={
            "command": ["check"], "workdir": "/home/u/w",
            "allowed_paths": ["/home/u/w"]})))
        assert r.code == "RES001"

    def test_a_working_directory_outside_what_was_permitted_is_refused(self):
        refusal(lambda: rs.add_tool(empty(), a_tool(invocation={
            "command": ["check"], "workdir": "/etc",
            "allowed_paths": ["/home/u/w"], "timeout_seconds": 60})))

    def test_a_workable_invocation_is_accepted(self):
        doc = rs.add_tool(empty(), a_tool(invocation={
            "command": ["check"], "workdir": "/home/u/w",
            "allowed_paths": ["/home/u/w"], "timeout_seconds": 60}))
        assert zs.validate_doc(doc, "resources") == []


class TestCredentialsNeverGetWrittenDown:
    def test_a_key_pasted_into_a_description_is_refused(self):
        r = refusal(lambda: rs.add_tool(empty(), a_tool(
            how_to_use="pass sk-abcdefghijklmnopqrstuvwxyz0123 as the key")))
        assert r.code == "SBX030"

    def test_a_password_in_the_invocation_is_refused(self):
        refusal(lambda: rs.add_tool(empty(), a_tool(invocation={
            "command": ["x"], "timeout_seconds": 60,
            "allowed_paths": ["/home/u/w"],
            "credentials_env": "password: hunter2"})))

    def test_the_name_of_a_variable_is_fine(self):
        doc = rs.add_tool(empty(), a_tool(invocation={
            "command": ["x"], "timeout_seconds": 60,
            "workdir": "/home/u/w", "allowed_paths": ["/home/u/w"],
            "credentials_env": "ZEPTEACH_CHECKER_KEY"}))
        assert doc["tools"][0]["invocation"]["credentials_env"] == \
            "ZEPTEACH_CHECKER_KEY"


class TestWiringUp:
    def integration(self, **over):
        doc = {"integration_id": "i1", "kind": "skill",
               "for_tools": ["checker"], "path": ".claude/skills/checker",
               "why": "the two flags that matter are easy to get wrong and "
                      "the failure is silent",
               "confirmed_by_learner": True}
        doc.update(over)
        return doc

    def test_wiring_for_a_recorded_tool_is_accepted(self):
        doc = rs.add_tool(empty(), a_tool())
        doc = rs.add_integration(doc, self.integration())
        assert doc["integrations"][0]["path"] == ".claude/skills/checker"

    def test_wiring_for_a_tool_nobody_recorded_is_refused(self):
        r = refusal(lambda: rs.add_integration(
            rs.add_tool(empty(), a_tool()),
            self.integration(for_tools=["something-else"])))
        assert r.code == "RES002"

    def test_writing_into_the_learners_project_needs_their_agreement(self):
        """This goes into their repository, not into this plugin's data."""
        r = refusal(lambda: rs.add_integration(
            rs.add_tool(empty(), a_tool()),
            self.integration(confirmed_by_learner=False)))
        assert r.code == "RES003"

    def test_wiring_that_does_not_say_what_it_saves_is_refused(self):
        """An integration that saves nothing is clutter somebody still has
        to maintain, and later cannot tell whether removing it is safe."""
        r = refusal(lambda: rs.add_integration(
            rs.add_tool(empty(), a_tool()), self.integration(why="")))
        assert r.code == "RES004"


class TestDecidingWhetherToWireAnythingUp:
    def test_a_tool_nobody_has_explained_and_nobody_uses_gets_nothing(self):
        out = rs.worth_wiring({"tool_id": "t", "what_it_does": "x",
                               "runs_where": "here"}, uses=0)
        assert out["build"] is None
        assert "sentence in how_to_use" in out["why"]

    def test_a_procedure_checks_existing_capabilities_first(self):
        out = rs.worth_wiring(a_tool(invocation={"command": ["x"]}))
        assert out["build"] == "check_existing"
        assert out["if_missing"] == "skill"

    def test_a_tool_the_learner_runs_still_has_a_capturable_procedure(self):
        """What they know about using it is the thing worth keeping, whether
        or not anything here can run it."""
        out = rs.worth_wiring(a_tool())
        assert out["build"] == "check_existing"
        assert out["if_missing"] == "skill"
        assert "survive being forgotten" in out["why"]

    def test_frequent_use_without_a_procedure_asks_first(self):
        out = rs.worth_wiring({"tool_id": "t", "what_it_does": "x",
                               "runs_where": "here",
                               "invocation": {"command": ["x"]}}, uses=9)
        assert out["build"] == "command"
        assert "Ask the learner" in out["why"]


class TestTurningSomethingDown:
    def test_a_declined_suggestion_is_remembered(self):
        """Making the same suggestion every week is its own failure. They
        had a reason the first time."""
        doc = rs.decline(empty(), "wire up the checker",
                         "I only use it before submitting")
        assert doc["declined"][0]["what"] == "wire up the checker"
        assert zs.validate_doc(doc, "resources") == []


class TestCli:
    def test_show_on_an_empty_course_says_none_recorded(self, root, capsys):
        assert run(["--root", str(root), "show",
                    "--course", "linear-algebra"]) == zs.EXIT_OK
        out = capsys.readouterr().out
        assert out.count("none recorded") == 2

    def test_show_on_a_missing_course(self, root):
        assert run(["--root", str(root), "show",
                    "--course", "ghost"]) == zs.EXIT_NOT_FOUND

    def test_adding_a_tool_writes_it(self, root, capsys):
        assert run(["--root", str(root), "add-tool",
                    "--course", "linear-algebra",
                    "--data", json.dumps(a_tool())]) == zs.EXIT_OK
        doc = zs.read_json(root / "courses" / "linear-algebra" /
                           "resources.json")
        assert doc["tools"][0]["tool_id"] == "checker"

    def test_a_refused_entry_exits_three_and_explains(self, root, capsys):
        code = run(["--root", str(root), "add-tool",
                    "--course", "linear-algebra",
                    "--data", json.dumps(a_tool(invocation={
                        "command": ["x"], "allowed_paths": ["/home/u/w"]}))])
        err = capsys.readouterr().err
        assert code == zs.EXIT_GATE
        assert "RES001" in err
        assert "instead:" in err

    def test_review_says_what_to_build_and_what_not_to(self, root, capsys):
        run(["--root", str(root), "add-tool", "--course", "linear-algebra",
             "--data", json.dumps(a_tool())])
        capsys.readouterr()
        assert run(["--root", str(root), "review",
                    "--course", "linear-algebra"]) == zs.EXIT_OK
        out = capsys.readouterr().out
        assert "checker  ->  check existing capabilities first" in out
        assert "if none fits: skill" in out
        assert "shown to them" in out

    def test_show_separates_what_the_plugin_runs_from_what_they_run(
            self, root, capsys):
        run(["--root", str(root), "add-tool", "--course", "linear-algebra",
             "--data", json.dumps(a_tool())])
        capsys.readouterr()
        run(["--root", str(root), "show", "--course", "linear-algebra"])
        assert "(the learner runs it)" in capsys.readouterr().out
