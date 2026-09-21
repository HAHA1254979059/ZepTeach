# ZepTeach

![ZepTeach](docs/cover.webp)

[![tests](https://github.com/HAHA1254979059/ZepTeach/actions/workflows/tests.yml/badge.svg)](https://github.com/HAHA1254979059/ZepTeach/actions/workflows/tests.yml)

ZepTeach turns an AI assistant into something that teaches over months rather
than answering over minutes. It keeps a durable record of what you have
actually demonstrated, schedules retests from your own recall history, and
puts the rules that matter into scripts that refuse rather than into
instructions a model can talk itself out of.

## Why

Using a chat assistant as a tutor fails in ways that are individually small
and collectively fatal. It forgets what you struggled with. It never starts a
review. It tells you a wrong answer is nearly right. It explains beautifully
and never finds out whether you can do anything. It covers material, and
covering material is not learning it.

Most of those are not teaching problems. They follow from having no memory
between sessions, no ability to run anything, and no way to judge work
without also being the one who taught it.

## What is different

**Success during the lesson promotes nothing.** Answering correctly ten
minutes after being taught is the moment recall is easiest and says least
about next week. Advancing requires a retest after a delay, in a different
form, plus a test in a setting the material was not learned in.

**A pass has to quote the answer.** Marking runs separately from teaching,
without the transcript, and does not know whose work it is. For every
criterion it marks as met, it quotes the words that met it, and those quotes
are checked against the submitted answer. A criterion nothing can be quoted
for was not met.

**Difficulty comes from outside.** The hardest tier of every exercise is a
real problem someone else set, cited precisely. A system that invents all its
own problems calibrates difficulty against what it expects you to manage, and
that expectation drifts down without anyone deciding to lower it.

**Mixed practice, enforced.** Practising several topics shuffled scores worse
during practice and twice as well on a test the next day, because it is the
only arrangement where you have to work out which method applies. Three ways
a set can look mixed and not be are refused in code.

**Explanations arrive in pieces you ask for**, not as a lecture in one
message. The benefit is specific: it comes from you controlling when the next
piece arrives, so each piece ends with a question rather than "shall I go
on?".

**Every number says where it came from.** Forty-seven tunable values, each
marked as supported by evidence, borrowed from an established tool, an
engineering decision, or a starting guess to be replaced by your own records.
`python skills/zepteach/scripts/constants.py table` prints the lot. "I made
this up" is an allowed answer; having no answer is not.

**It knows no subject.** The core describes what a mind is doing — recall,
derive, apply, construct, analyze, critique, explain back — and never what
hands are doing. What running a calculation or reading a text closely looks
like comes from an adapter generated when you set up a course, from your goal
and what you actually have. There is no list of supported subjects anywhere,
and a test fails if one appears.

## Requirements

Python, and nothing else. No packages, no services, no account. The schema
validator, the spaced-repetition scheduler and the Word-document writer are
all written here against the standard library, so this behaves identically on
any machine with Python and nothing installed.

Developed and tested on 3.13, on Linux, macOS and Windows. Nothing newer than
3.9 syntax is used, though 3.9 has not been run against directly.

## Install

Clone it once, then point your assistant at it. Linking rather than copying
means an update is a `git pull` with nothing to reinstall.

```bash
git clone https://github.com/HAHA1254979059/ZepTeach
```

### Claude Code

```bash
ln -s "$PWD/ZepTeach/skills/zepteach"  ~/.claude/skills/zepteach
ln -s "$PWD/ZepTeach/commands"         ~/.claude/commands/zepteach
ln -s "$PWD/ZepTeach/agents"           ~/.claude/agents/zepteach
```

Windows, in a normal prompt with no administrator rights:

```bat
mklink /J "%USERPROFILE%\.claude\skills\zepteach"   "C:\path\to\ZepTeach\skills\zepteach"
mklink /J "%USERPROFILE%\.claude\commands\zepteach" "C:\path\to\ZepTeach\commands"
mklink /J "%USERPROFILE%\.claude\agents\zepteach"   "C:\path\to\ZepTeach\agents"
```

Start a new session and run `/zepteach:zt`. That is the only command; it is
namespaced by the folder it is linked under.

The three subagents give marking, background gaps and course design their own
context. That isolation is the reason marking cannot go soft, so it is worth
linking rather than skipping.

### Codex

Codex reads skills from `~/.agents/skills` for personal use, or from
`<repo>/.agents/skills` for one project. The layout ZepTeach already has —
`SKILL.md` beside `scripts/` and `references/` — is exactly what Codex
expects, so the skill is the whole install.

```bash
mkdir -p ~/.agents/skills
ln -s "$PWD/ZepTeach/skills/zepteach" ~/.agents/skills/zepteach
```

Windows:

```bat
mkdir "%USERPROFILE%\.agents\skills"
mklink /J "%USERPROFILE%\.agents\skills\zepteach" "C:\path\to\ZepTeach\skills\zepteach"
```

Invoke it with `$zepteach`, or just say what you want to study and let Codex
pick it up from the description.

**Codex has no subagents, so marking has to be kept separate by hand.** That
matters more than it sounds: a marker that watched the teaching is the single
most reliable way for standards to slip. Run

```bash
python skills/zepteach/scripts/grade.py package \
    --item item.json --rubric rubric.json --answer answer.txt
```

which prints exactly what a marker should receive, assembled from an allowed
list rather than by stripping things out. Paste it into a **fresh
conversation** together with `agents/zt-grader.md`, and bring the verdict
back. The isolation is real either way: what makes it work is the marker not
having the teaching, not the mechanism that delivers it.

Everything the entry point needs lives inside the skill, which is what Codex
loads. Nothing here depends on the `commands/`, `agents/` or `hooks/`
directories, and a test fails if that stops being true.

### Anything else that reads files and runs a shell

Read [AGENTS.md](AGENTS.md). It covers the routing entry point, where learner
data goes, and how to keep marking isolated without subagents.

## Using it

```
/zt                     carry on
/zt quantum chemistry   start that
/zt this is too slow    change the plan
```

One command. Say what you want, or say nothing and it continues from where
the records leave off. It works out whether that means first-time setup,
designing a course, teaching, running reviews, or rewriting the plan, and
then does it rather than telling you which command to type next.

There were nine commands. Nine means you have to know which of nine applies
before you can say what you want, which is a menu standing in for a
conversation, and in practice people used one and ignored the rest.

Changing your mind mid-course goes through the same door. "Skip the proofs",
"I need reinforcement learning before my internship", "go back to Tuesday" -
all of those are plan changes, they get recorded with your reason, and the
plugin refuses to quietly drop material you have already been taught without
saying so.

**Before the first lesson it asks one question: which language to teach in.**
Everything else is asked when it matters - what you are studying for when a
course is being designed, how you would rather write a formula before it sets
one. Whenever something already said answers a question, it proposes the
answer and asks you to correct it instead of asking you cold.

It asks what you have studied. It never asks how well you know it: self-rated
level correlates near zero with measured level and runs consistently high, so
that answer would look like information and be used as if it were.

## Your data

Everything about a learner lives in `ZEPTEACH_ROOT`, outside this repository:
profile, mastery states, every recorded attempt, the review queue, courses,
notes. Notes are written twice — Markdown for the plugin to read back, a Word
document for you.

```bash
export ZEPTEACH_ROOT=~/zepteach-data
```

Defaults to a `ZepTeach` directory in your home directory: `~/ZepTeach`,
or `C:\Users\<you>\ZepTeach` on Windows.

Nothing is sent anywhere. Nothing is installed. No directory you did not
permit is touched, reads included.

## What it will not do

Install software or change an environment. Touch a path outside what you
permitted. Store a password, key or token. Record a pass that nothing
supports, a depth nothing demonstrated, or a review that quietly moved
because the queue looked long.

## Before you start

No real learner has used this yet. Every quantity marked `calibrated` is a
documented starting value waiting for actual records to replace it, and the
session length in particular is a placeholder that says so.

If a number feels wrong in use, that is not a bug report; it is what those
markings are for. `python skills/zepteach/scripts/constants.py table` shows
which numbers are guesses and which are not.

## Tests

```bash
python -m pytest skills/zepteach/tests -q
```

853 tests, run on Linux, macOS and Windows against Python 3.10 and 3.13. Many
are worth reading on their own: each states, in its name and docstring, a
specific way this could go wrong while still producing output that reads
perfectly well.

## Licence

MIT. See [LICENSE](LICENSE).
