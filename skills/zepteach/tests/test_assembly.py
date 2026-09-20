"""Commands, subagents and the session hook.

These are the only files a learner interacts with directly, and they are the
easiest to let rot: nothing breaks when a command tells someone to run a
script that no longer takes those arguments. It just fails in front of them.

So each one is checked against what the scripts and routes actually are.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
PLUGIN = SKILL.parents[1]
SCRIPTS = SKILL / "scripts"
REFS = SKILL / "references"

sys.path.insert(0, str(SCRIPTS))

import route as rt  # noqa: E402


def commands():
    return sorted((PLUGIN / "commands").glob("*.md"))


def agents():
    return sorted((PLUGIN / "agents").glob("*.md"))


def text(p):
    return p.read_text(encoding="utf-8")


def frontmatter(p):
    body = text(p)
    if not body.startswith("---"):
        return {}
    block = body.split("---", 2)[1]
    out = {}
    for line in block.strip().splitlines():
        if ": " in line:
            key, val = line.split(": ", 1)
            out[key.strip()] = val.strip()
    return out


class TestCommands:
    def test_there_are_commands(self):
        assert len(commands()) >= 8

    @pytest.mark.parametrize("path", commands(), ids=lambda p: p.name)
    def test_each_has_a_description(self, path):
        assert frontmatter(path).get("description"), path.name

    @pytest.mark.parametrize("path", commands(), ids=lambda p: p.name)
    def test_every_script_it_names_exists(self, path):
        """A command that names a script nobody wrote fails in front of the
        learner, and nothing else catches it."""
        named = set(re.findall(r"`?(\w+\.py)`?", text(path)))
        missing = [n for n in named if not (SCRIPTS / n).exists()]
        assert missing == [], path.name + " names " + ", ".join(missing)

    @pytest.mark.parametrize("path", commands(), ids=lambda p: p.name)
    def test_every_doctrine_file_it_names_exists(self, path):
        named = set(re.findall(r"`([a-z0-9-]+\.md)`", text(path)))
        missing = [n for n in named if not (REFS / n).exists()]
        assert missing == [], path.name + " names " + ", ".join(missing)

    @pytest.mark.parametrize("path", commands(), ids=lambda p: p.name)
    def test_every_subcommand_it_names_is_real(self, path):
        """Catches the case where a command tells someone to run a flag that
        was renamed. Checked by asking the script itself, so it cannot drift
        from what argparse actually accepts."""
        for script, sub in re.findall(r"`(\w+\.py) ([a-z-]+)", text(path)):
            if not (SCRIPTS / script).exists():
                continue
            out = subprocess.run(
                [sys.executable, str(SCRIPTS / script), "--help"],
                capture_output=True, text=True, timeout=30)
            listed = out.stdout + out.stderr
            assert sub in listed, (
                path.name + ": " + script + " has no " + sub)

    def test_the_commands_cover_the_routed_intents(self):
        """Every intent worth a route is reachable by the learner. An intent
        with a route and no way to ask for it is doctrine nobody loads."""
        joined = " ".join(text(p) for p in commands())
        for intent in ("lesson", "review", "notes", "sidequest"):
            assert intent in joined or intent.rstrip("s") in joined, intent


class TestSubagents:
    def test_the_three_exist(self):
        assert {p.stem for p in agents()} == {
            "zt-grader", "zt-sidequest-tutor", "zt-curriculum-architect"}

    @pytest.mark.parametrize("path", agents(), ids=lambda p: p.name)
    def test_each_declares_a_name_and_description(self, path):
        fm = frontmatter(path)
        assert fm.get("name") == path.stem
        assert fm.get("description")

    def test_the_marker_is_told_what_it_does_not_have(self):
        """The isolation is the whole mechanism. Stated in the agent file as
        well as in the doctrine, because the agent file is what loads."""
        s = text(PLUGIN / "agents" / "zt-grader.md")
        assert "did not teach this" in s
        assert "do not know who wrote it" in s
        assert "transcript" in s

    def test_the_marker_is_told_to_refuse_a_leaking_package(self):
        """Isolation that depends on the sender getting it right is not
        isolation. The receiver checks too."""
        s = text(PLUGIN / "agents" / "zt-grader.md")
        assert "something has gone wrong upstream" in s

    def test_the_marker_must_quote(self):
        s = text(PLUGIN / "agents" / "zt-grader.md")
        assert "quote the words" in s
        assert "fair paraphrase" in s

    def test_the_side_branch_returns_a_summary_not_a_transcript(self):
        s = text(PLUGIN / "agents" / "zt-sidequest-tutor.md")
        assert "Do not return the transcript" in s
        assert "two hundred words" in s

    def test_the_side_branch_has_a_depth_ceiling(self):
        s = text(PLUGIN / "agents" / "zt-sidequest-tutor.md")
        assert "depth ceiling is a real limit" in s

    def test_the_architect_is_warned_about_the_two_easy_mistakes(self):
        s = text(PLUGIN / "agents" / "zt-curriculum-architect.md")
        assert "conventional orderings" in s
        assert "depth target" in s.lower()

    @pytest.mark.parametrize("path", agents(), ids=lambda p: p.name)
    def test_no_agent_is_given_the_teaching_doctrine(self, path):
        """Each of these exists because it should not know something. Loading
        teaching doctrine into any of them gives back what the separation was
        for."""
        s = text(path)
        assert "teaching-contract.md" not in s
        assert "persona-zep.md" not in s


class TestTheSessionHook:
    def test_it_parses(self):
        json.loads(text(PLUGIN / "hooks" / "hooks.json"))

    def test_it_runs_at_session_start(self):
        doc = json.loads(text(PLUGIN / "hooks" / "hooks.json"))
        assert "SessionStart" in doc["hooks"]

    def test_it_carries_a_timeout(self):
        doc = json.loads(text(PLUGIN / "hooks" / "hooks.json"))
        hook = doc["hooks"]["SessionStart"][0]["hooks"][0]
        assert hook["timeout"] > 0

    def test_it_cannot_block_a_session_that_has_nothing_to_do_with_this(self):
        """A hook runs on every session, including ones that are not about
        learning. Failing loudly there would make the plugin something people
        uninstall."""
        doc = json.loads(text(PLUGIN / "hooks" / "hooks.json"))
        cmd = doc["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        assert "|| true" in cmd

    def test_the_command_it_runs_exists_and_accepts_its_flags(self):
        out = subprocess.run(
            [sys.executable, str(SCRIPTS / "learner.py"), "show", "--help"],
            capture_output=True, text=True, timeout=30)
        assert "--brief" in out.stdout + out.stderr

    def test_it_says_nothing_when_there_is_nothing_to_say(self, tmp_path):
        """A line that appears every session whether or not it carries
        information stops being read, and takes the sessions that do carry
        something with it."""
        out = subprocess.run(
            [sys.executable, str(SCRIPTS / "learner.py"),
             "--root", str(tmp_path), "show", "--brief"],
            capture_output=True, text=True, timeout=30)
        assert out.stdout.strip() == ""
        assert out.returncode == 0
