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


def manifest(host):
    return json.loads(text(PLUGIN / ("." + host + "-plugin") / "plugin.json"))


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
    def test_there_is_exactly_one_way_in(self):
        """There were nine. Nine commands means the learner has to know
        which of nine applies before they can say what they want, which is a
        menu standing in for a conversation - and in practice they used one
        and ignored the rest.

        One entry point also removes a whole class of defect: with nine
        files, an improvement to the way in gets written into whichever one
        was open, and the other eight keep the old behaviour.
        """
        assert [p.name for p in commands()] == ["zt.md"]

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

    def test_the_one_command_routes_rather_than_listing(self):
        """It must hand the decision to the router, not re-describe the
        intents. A command file that lists them is the menu again, one file
        further down, and it goes stale the first time an intent changes."""
        s = text(commands()[0])
        assert "route.py next" in s
        assert "--said" in s

    def test_changing_the_plan_goes_through_the_same_door(self):
        """Mid-course, a learner says "this is too slow" or "I need X before
        my internship". Those are the requests most likely to be answered
        with a lecture instead of a change, because they do not look like
        commands."""
        s = text(commands()[0])
        assert "replan" in s
        assert "too slow" in s

    def test_every_routed_intent_is_reachable_from_the_router(self):
        """The coverage check that used to be done against the command files.
        Moved here because the guarantee was never that a command file
        mentions an intent - it was that a learner can get to it."""
        step_names = set(rt.ROUTES)
        reachable = {"setup1", "course-new", "setup2", "lesson", "upgrade"}
        for alt in rt.alternatives({}, [{"slug": "a"}, {"slug": "b"}]):
            reachable.add(alt["intent"])
        for intent in ("replan", "sidequest", "notes", "status", "assess"):
            assert intent in reachable, intent
            assert intent in step_names, intent


class TestPluginManifests:
    def test_both_hosts_have_a_manifest(self):
        assert (PLUGIN / ".claude-plugin" / "plugin.json").is_file()
        assert (PLUGIN / ".codex-plugin" / "plugin.json").is_file()

    def test_manifest_identity_cannot_drift_between_hosts(self):
        claude = manifest("claude")
        codex = manifest("codex")
        for field in ("name", "version"):
            assert claude[field] == codex[field]
        assert claude["version"] == text(PLUGIN / "VERSION").strip()

    def test_codex_manifest_exposes_the_skill(self):
        codex = manifest("codex")
        assert codex["skills"] == "./skills/"
        assert codex["interface"]["displayName"] == "ZepTeach"
        assert codex["interface"]["defaultPrompt"]

    def test_short_entry_points_to_the_same_teaching_method(self):
        short = text(PLUGIN / "skills" / "zt" / "SKILL.md")
        assert "name: zt" in short
        assert "../zepteach/SKILL.md" in short
        assert "route.py next" in short


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


class TestItWorksOnAHostWithOnlyTheSkill:
    """Codex, and anything else that loads a skill and nothing else.

    This is not a nice-to-have. For most people who will use this, Codex is
    the main tool; the slash commands, the subagents and the session hook are
    Claude Code's and do not exist there. Codex reads `SKILL.md`, `scripts/`
    and `references/`, which means anything a learner needs in order to get
    started, keep going, or recover has to be reachable from inside this
    directory.

    The failure this prevents has already happened once: an entry point was
    improved by writing a new command file, and the improvement was invisible
    to the host it was written for.
    """

    def test_the_whole_entry_point_is_inside_the_skill(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        assert "route.py next" in text, (
            "SKILL.md is the only entry point some hosts have. If the way in "
            "is documented anywhere else, those hosts do not have one")
        assert "commands/" not in text

    def test_no_script_reaches_outside_the_skill_directory(self):
        """A script that reads `../../commands` or `../../agents` works here
        and fails silently wherever the skill was linked on its own."""
        bad = []
        for path in sorted((SKILL / "scripts").glob("*.py")):
            body = path.read_text(encoding="utf-8")
            for i, line in enumerate(body.splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                for marker in ("parents[2]", "parents[3]",
                               '"commands"', "'commands'",
                               '"agents"', "'agents'"):
                    if marker in line:
                        bad.append(path.name + ":" + str(i) + " " + marker)
        assert bad == [], (
            "a shipped script depends on files outside the skill: " +
            ", ".join(bad))

    def test_every_routed_intent_names_only_things_inside_the_skill(self):
        missing = []
        for intent in rt.ROUTES:
            res = rt.resolve(intent)
            missing.extend(intent + ": " + m for m in res["missing"])
            for cmd in res.get("run", []):
                script = cmd.split()[0]
                if script.endswith(".py") and \
                        not (SKILL / "scripts" / script).exists():
                    missing.append(intent + ": " + script)
        assert missing == []

    def test_recovering_an_old_data_root_does_not_need_a_command_file(self):
        """Someone who updates the plugin and reopens their records has to be
        told what changed. On a host with no slash commands, the only place
        that can come from is the router."""
        assert "upgrade" in rt.ROUTES
        res = rt.resolve("upgrade")
        assert any("migrate.py" in r for r in res["run"])

    def test_grading_stays_possible_without_subagents(self):
        """The isolation that keeps marking honest is the marker not having
        the teaching, not the mechanism that delivers it. On a host with no
        subagents that means a package a person can carry to a fresh
        conversation, so the package builder has to be a script."""
        assert (SKILL / "scripts" / "grade.py").exists()
        out = subprocess.run(
            [sys.executable, str(SKILL / "scripts" / "grade.py"), "--help"],
            capture_output=True, text=True)
        assert "package" in out.stdout
