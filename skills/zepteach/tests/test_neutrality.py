"""The plugin must not know what you are studying, and must not carry a syllabus.

Two failures this file exists to prevent, both of which already happened once.

The first is discipline leak. The core once had a grader enum naming two
specific chemistry programs, an exercise-form list mixing simulations with
close readings, and a course field enumerating six permitted subjects. None
of it was deliberate: every example reached for while writing came from the
same field, and examples harden into assumptions. Review does not catch this,
because the leak reads perfectly naturally to whoever wrote it.

The second is shipped content. Fixture courses are scaffolding for testing
this plugin. A plugin that claims to know no subject must not ship with a
mathematics course inside it. See PACKAGING.md.
"""

import re
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[3]
SKILL = PLUGIN / "skills" / "zepteach"
SCHEMAS = SKILL / "scripts" / "schemas"
SCRIPTS = SKILL / "scripts"
REFS = SKILL / "references"


# Names of particular tools, works, packages and subjects. Not an exhaustive
# list and cannot be - it is a tripwire, not a proof. It is weighted towards
# the fields this project's author works in, because those are the ones that
# leak.
DISCIPLINE_WORDS = [
    "gaussian", "gromacs", "lammps", "orca", "vasp", "quantum espresso",
    "pytorch", "tensorflow", "numpy", "scipy", "cuda", "transformer",
    "eigenvalue", "hamiltonian", "thermostat", "ensemble sampling",
    "ulysses", "shakespeare", "thucydides",
    "math-for-ai", "ai-llm", "comp-chem", "molecular-dynamics",
    "md_traj", "gaussian_log",
]

# Words that are fine in the core because they describe the plugin itself or
# a generic mechanism, even though they collide with the list above.
ALLOWED_CONTEXT = re.compile(
    r"(pytest|python|encoding|coding|/usr/bin/orca is the GNOME)",
    re.IGNORECASE)


def shipped_files():
    """Everything a learner would receive."""
    out = []
    for pattern in ("scripts/*.py", "scripts/schemas/*.json",
                    "references/**/*.md", "SKILL.md"):
        out.extend(p for p in SKILL.glob(pattern) if p.is_file())
    out.extend(p for p in PLUGIN.glob("*.md") if p.is_file())
    for d in ("commands", "agents", "hooks"):
        out.extend(p for p in (PLUGIN / d).rglob("*") if p.is_file())
    return [p for p in out if "tests" not in p.parts]


class TestNoDisciplineInTheCore:
    def test_the_shipped_surface_names_no_particular_subject(self):
        offences = []
        for path in shipped_files():
            # this file's own prose, and the packaging rules, quote the
            # forbidden words in order to forbid them
            if path.name in ("PACKAGING.md", "PHILOSOPHY.md", "README.md"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                low = line.lower()
                for word in DISCIPLINE_WORDS:
                    if word in low and not ALLOWED_CONTEXT.search(line):
                        offences.append(
                            path.relative_to(PLUGIN).as_posix() + ":" +
                            str(i) + "  " + word + "  |  " + line.strip()[:90])
        assert offences == [], (
            "a subject got into the shipped plugin:\n" + "\n".join(offences))

    def test_no_schema_enumerates_disciplines(self):
        """A fixed list of subject names is the same mistake as a fixed list
        of installed software, and it is easy to reintroduce as an enum."""
        import json
        bad = []
        for path in SCHEMAS.glob("*.json"):
            doc = json.loads(path.read_text(encoding="utf-8"))

            def walk(node, where):
                if isinstance(node, dict):
                    values = node.get("enum")
                    if isinstance(values, list):
                        for v in values:
                            if isinstance(v, str) and any(
                                    w in v.lower() for w in DISCIPLINE_WORDS):
                                bad.append(path.name + " " + where + " = " + v)
                    for k, v in node.items():
                        walk(v, where + "/" + k)
                elif isinstance(node, list):
                    for i, v in enumerate(node):
                        walk(v, where + "/" + str(i))

            walk(doc, "")
        assert bad == [], "\n".join(bad)

    def test_the_cognitive_actions_describe_thinking_not_doing(self):
        """The core vocabulary has to survive translation into any subject.
        Anything naming an activity rather than a mental operation will fit
        one field and exclude the rest."""
        import sys
        sys.path.insert(0, str(SCRIPTS))
        import zt_state as zs
        actions = zs.shared_defs()["cognitive_action"]["enum"]
        activity_words = ["simulation", "coding", "parameter_study",
                          "close_reading", "experiment_design", "computation",
                          "argument_reconstruction", "modeling"]
        assert not set(actions) & set(activity_words)
        assert set(actions) == {"recall", "derive", "apply", "construct",
                                "analyze", "critique", "explain_back"}


class TestNothingHasToBeInstalled:
    """The plugin claims to run on any machine with Python and nothing else.

    That claim is what lets someone clone this and start, and it is the kind
    of claim that erodes one convenient import at a time. A validator, a
    scheduler and a document writer were all written here rather than pulled
    in, so the cost of this property has already been paid; letting it lapse
    quietly would waste that.
    """

    STDLIB = {
        "argparse", "json", "re", "sys", "os", "math", "zipfile",
        "subprocess", "tempfile", "shutil", "posixpath", "shlex",
        "unicodedata", "datetime", "pathlib", "collections", "xml",
        "__future__", "typing", "io", "csv", "itertools", "textwrap",
    }

    def test_no_shipped_script_imports_anything_third_party(self):
        import re as _re
        bad = []
        for path in sorted(SCRIPTS.glob("*.py")):
            for i, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), 1):
                m = _re.match(r"^(?:import|from)\s+([A-Za-z_]\w*)", line)
                if not m:
                    continue
                mod = m.group(1)
                if mod in self.STDLIB or (SCRIPTS / (mod + ".py")).exists():
                    continue
                bad.append(path.name + ":" + str(i) + " " + mod)
        assert bad == [], (
            "a shipped script imports something that is not in the standard "
            "library and not part of this plugin: " + ", ".join(bad))

    def test_the_readme_still_says_so(self):
        """If the property is ever dropped deliberately, the claim has to go
        with it. A README promising no dependencies while the code has them
        is worse than either."""
        s = (PLUGIN / "README.md").read_text(encoding="utf-8")
        assert "No dependencies" in s


class TestNoSyllabusShips:
    # JSON that is part of the plugin rather than part of anybody's
    # learning. Listed by name so that a new file has to be argued for
    # rather than appearing because the pattern happened to match.
    WIRING = {"plugin.json", "hooks.json"}

    def test_no_course_or_curriculum_data_outside_the_tests(self):
        stray = []
        for path in PLUGIN.rglob("*.json"):
            if "tests" in path.parts or "__pycache__" in path.parts:
                continue
            if path.parent.name == "schemas" or path.name in self.WIRING:
                continue
            stray.append(path.relative_to(PLUGIN).as_posix())
        assert stray == [], (
            "learner data or sample content in the plugin tree: " +
            ", ".join(stray))

    def test_no_run_artifacts_left_in_the_plugin_tree(self):
        """Verifying that a program is what it claims means running it, and
        programs write files where they are started. One such log really did
        turn up in this directory, which is why probes now run somewhere
        disposable."""
        allowed_suffix = {".py", ".md", ".json", ".txt", ".gitignore"}
        stray = []
        for path in SKILL.rglob("*"):
            if not path.is_file() or "tests" in path.parts:
                continue
            if "__pycache__" in path.parts or ".pytest_cache" in path.parts:
                continue
            if path.suffix not in allowed_suffix:
                stray.append(path.relative_to(PLUGIN).as_posix())
        assert stray == [], "run artifacts: " + ", ".join(stray)


class TestTheFixtureWorldStaysMixed:
    def test_the_two_fixture_courses_are_not_both_stem(self):
        """The mechanism that keeps the rest of this file honest. With two
        science courses in the fixtures, nothing was ever inconvenienced by a
        science assumption, and several got in."""
        import conftest as fx
        domains = {fx.course()["domain"], fx.hist_course()["domain"]}
        assert len(domains) == 2
        assert "history" in domains

    def test_the_shared_concept_crosses_the_two_fields(self):
        import conftest as fx
        entry = [c for c in fx.registry()["concepts"]
                 if c["concept_id"] == fx.SHARED][0]
        assert sorted(entry["courses"]) == ["hist", "linalg"]
