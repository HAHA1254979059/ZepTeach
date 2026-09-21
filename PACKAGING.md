# What ships, and what must not

ZepTeach ships **a method, never a syllabus.**

Nothing that names a subject, a course, a textbook, an exercise or an exam
belongs in the distributed plugin. Those are the learner's, generated for
them when they set up a course, and they live in the learning data root
(`ZEPTEACH_ROOT`), not in this repository.

## Ships

| Path | Why it is allowed |
|---|---|
| `.claude-plugin/plugin.json` | Claude Code manifest |
| `.codex-plugin/plugin.json` | Codex manifest |
| `skills/zepteach/SKILL.md` | routing table |
| `skills/zepteach/references/*.md` | teaching doctrine — method only |
| `skills/zepteach/scripts/*.py` | state engine and gates |
| `skills/zepteach/scripts/schemas/*.json` | shapes, no content |
| `commands/`, `agents/`, `hooks/` | wiring |
| `PHILOSOPHY.md`, `README.md`, this file | design record |

## Does not ship

| Path | Why |
|---|---|
| `skills/zepteach/tests/` | The example courses in the tests exist to check this plugin, not to be taught to anyone. Their purpose is to make code that assumes a particular subject fail during development. Shipping them would place a mathematics course and a history course inside a plugin whose whole design depends on knowing neither. |
| `__pycache__/`, `.pytest_cache/` | files produced by running Python and the test runner; regenerated on any machine, and specific to the one that made them |
| files written by a check that ran an external program | see rule 2 below |

## Two rules this file exists to enforce

**1. No sample content in the shipped surface.** No example course, no
worked exercise, no exam template, no curriculum. Doctrine files may state a
rule and may show the *shape* of a thing; they may not carry a ready-made
subject. `tests/test_neutrality.py` checks this and fails the build.

**2. Checks that run an external program do so in a temporary directory.**
Establishing that a program on the machine is the one its name suggests
requires running it, and many programs write an output or log file into
whatever directory they were started from. A log file from one such program
was once found sitting in the plugin directory for exactly this reason. Every
check of this kind runs inside a temporary directory that is deleted
afterwards, never inside the plugin directory or the learner's data
directory.
