# Running ZepTeach on any assistant

This file is the entry point. If you are an assistant with file access and a
shell, read this first.

ZepTeach is built so that the parts that must not go wrong are Python scripts
that refuse, rather than instructions you are asked to follow. That design
also makes it portable: the refusals work the same wherever the scripts run,
and what changes between platforms is only how conveniently the rest is
wired up.

## What you need

Python, and nothing else. No packages to install, no services, no account.
The schema validator, the spaced-repetition scheduler and the document writer
are all written here against the standard library, for exactly this reason.

Developed and tested on 3.13. Nothing newer than 3.9 syntax is used, though
3.9 has not been run against directly.

## Start here, every session

```
python skills/zepteach/scripts/route.py for <intent> --course <slug>
```

That prints the smallest set of files to read for what you are about to do,
what to run, and what **not** to load yet. `route.py list` shows the intents.

Do not read the doctrine files wholesale. There are twenty of them, around
27,000 tokens in total, and loading everything makes the instructions that
matter for the current task a smaller fraction of what you are reading. A
single routed intent is between 800 and 7,000 tokens.

The one file that always loads is `skills/zepteach/SKILL.md`, about 1,200
tokens. It holds the routing table and the rules the scripts enforce.

## Where the learner's data goes

Set `ZEPTEACH_ROOT` to a directory outside this repository. Everything about
one learner lives there: profile, mastery records, attempts, courses, notes.
Nothing learner-specific belongs in this repository, and a test fails if any
appears.

```
export ZEPTEACH_ROOT=~/zepteach-data
python skills/zepteach/scripts/zt_state.py init
```

## Exit codes are instructions, not suggestions

| Code | Meaning |
|---|---|
| 0 | proceed |
| 2 | the data does not match its stored shape; nothing was written |
| 3 | a precondition is not met; do not work around it |
| 4 | a budget was exceeded |
| 5 | not found |

A non-zero exit is the system refusing. Finding a phrasing that gets past it
converts a boundary into an obstacle, which is the one failure mode this
whole design exists to prevent.

## On Claude Code

Everything is wired up. Slash commands in `commands/`, three subagents in
`agents/`, and a session-start hook that prints what is overdue.

## On anything else

The scripts and doctrine work unchanged. Three conveniences are missing, and
each has a manual equivalent that keeps the property that mattered.

**Slash commands** are plain markdown in `commands/`. Read the one you want:
`commands/zt-learn.md` is what a teaching session does. They contain
instructions, not platform syntax.

**Subagent isolation** is the one that needs care, because it is a design
property rather than a convenience.

Marking must not see the teaching. On a platform without subagents, run:

```
python skills/zepteach/scripts/grade.py package \
    --item item.json --rubric rubric.json --answer answer.txt
```

That prints exactly what a marker should receive, built by whitelist. Paste
it into a **fresh conversation** with `agents/zt-grader.md` as the
instruction, and bring the verdict back. The isolation is real either way:
what makes it work is the marker not having the teaching, not the mechanism
that delivers it.

The same applies to filling a background gap (`agents/zt-sidequest-tutor.md`)
and designing a course (`agents/zt-curriculum-architect.md`). Each of those
files explains what it must not be given, and why.

**The session-start hook** prints what is overdue. Run it yourself:

```
python skills/zepteach/scripts/learner.py show --brief
```

It prints nothing when there is nothing to say.

## What this plugin will not do

- Install anything, or change any environment. It reports what is missing
  and leaves the decision where it belongs.
- Touch a directory nobody permitted, reads included.
- Store a password, key or token. Configuration holds the *name* of an
  environment variable.
- Record a pass that nothing supports, or a depth that nothing demonstrated.

## Checking it works

```
python -m pytest skills/zepteach/tests -q
```

792 tests, no dependencies beyond pytest itself. They are worth reading:
most of them state, in the test name and docstring, a specific way this could
go wrong while still producing output that reads perfectly well.

## The design, if you want it

`PHILOSOPHY.md` is the foundation. Eight principles about how people learn,
eight about building something that survives contact with a real user, two
places where those conflict and how each is settled.

Every doctrine file opens by naming which principle it implements. A file
that cannot name one should not exist.

## Installing it for development

For working on the plugin while using it, link rather than copy, so that a
change to the repository is live immediately and there is no second copy to
forget about.

On Windows, a directory junction needs no administrator rights:

```
mklink /J "%USERPROFILE%\.claude\skills\zepteach" "<repo>\skills\zepteach"
mklink /J "%USERPROFILE%\.claude\commands\zepteach" "<repo>\commands"
mklink /J "%USERPROFILE%\.claude\agents\zepteach" "<repo>\agents"
```

On macOS or Linux, `ln -s` the same three.

One consequence worth knowing: a link exposes the whole folder, including
`tests/`, which `PACKAGING.md` says must never ship. That is acceptable for a
development link and would not be for a distribution. The fixture courses
inside are scaffolding, not material for anyone to learn from.

The learner's data still goes wherever `ZEPTEACH_ROOT` points, or to
`E:\ZepTeach` on Windows and `~/ZepTeach` elsewhere by default. It is never
inside the repository.
