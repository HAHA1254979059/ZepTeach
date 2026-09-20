# ZepTeach

A tutor that cannot quietly lower its standards.

ZepTeach turns an AI assistant into something that teaches over months rather
than answering over minutes. It keeps a durable record of what you have
actually demonstrated, schedules retests from your own recall history, and
puts the rules that matter into scripts that refuse rather than into
instructions a model can talk itself out of.

The teacher is called Zep. Low distance, high standards, and those are not in
tension because Zep does not set the standards.

Works with Claude Code out of the box, and with any assistant that can read
files and run Python. See [AGENTS.md](AGENTS.md).

## Why

Using a chat assistant as a tutor fails in ways that are individually small
and collectively fatal. It forgets what you struggled with. It never starts a
review. It tells you a wrong answer is nearly right. It explains beautifully
and never finds out whether you can do anything. It covers material, and
covering material is not learning it.

Most of those are not teaching problems. They are the consequences of having
no memory between sessions, no ability to run anything, and no way to judge
work without also being the one who taught it.

This fixes the second set with a local plugin, and the first set with
[a stated design philosophy](PHILOSOPHY.md) rather than a list of patches.

## What is different

**Success during the lesson promotes nothing.** Answering correctly ten
minutes after being taught is the moment recall is easiest and says least
about next week. Advancing requires a retest after a delay, in a different
form, plus a test in a setting the material was not learned in.

**A pass has to quote the answer.** Marking runs in a separate process that
never sees the teaching and does not know whose work it is. For every
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

**Every number says where it came from.** Forty-seven tunable values, each
marked as supported by evidence, borrowed from an established tool, an
engineering decision, or a starting guess to be replaced by your own records.
`python skills/zepteach/scripts/constants.py table` prints the lot. "I made
this up" is an allowed answer; having no answer is not.

**It knows no subject.** The core describes what a mind is doing — recall,
derive, apply, construct, analyze, critique, explain back — and never what
hands are doing. What running a calculation or reading a text closely looks
like comes from an adapter generated when you set up a course, from your
goal and what you actually have. There is no list of supported subjects
anywhere, and a test fails if one appears.

## Install

**Claude Code**

```
git clone https://github.com/<you>/ZepTeach ~/.claude/plugins/zepteach
```

Then `/zt-setup`.

**Anything else** — clone it anywhere and read [AGENTS.md](AGENTS.md).

No dependencies. The schema validator, the scheduler and the Word-document
writer are all written here against the standard library, so the plugin
behaves identically on any machine with Python and nothing else.

Developed and tested on Python 3.13. Nothing newer than 3.9 syntax is used,
but 3.9 itself has not been run against, so treat that as the intended floor
rather than a verified one.

## Using it

```
/zt-setup      first time: who is learning, in what language, notes where
/zt-course     create a course from a goal
/zt-probe      work out what this course can practise on
/zt-learn      teach
/zt-review     run what is due
/zt-assess     stage assessment and an objective progress report
/zt-notes      write or repair the canonical notes
/zt-sidequest  fill a background gap without losing the lesson
/zt-status     where things stand
```

Two setup stages, deliberately. The first asks what cannot be measured later:
which language to teach in, why you are studying, how deep you want to go.
The second runs only after a course exists, because what a course needs
depends on what it is for.

It asks what you have studied. It never asks how well you know it:
self-rated level correlates near zero with measured level and runs
consistently high, so that answer would look like information and be used as
if it were.

## Your data

Everything about a learner lives in `ZEPTEACH_ROOT`, outside this repository:
profile, mastery states, every recorded attempt, the review queue, courses,
notes. Notes are written twice — markdown for the plugin to read back, a Word
document for you.

Nothing is sent anywhere. Nothing is installed. No directory you did not
permit is touched, reads included.

## What it will not do

Install software or change an environment. Touch a path outside what you
permitted. Store a password, key or token. Record a pass that nothing
supports, a depth nothing demonstrated, or a review that quietly moved
because the queue looked long.

## Design

[PHILOSOPHY.md](PHILOSOPHY.md) — eight principles about how people learn,
eight about building something that survives a real user, and two places
where those conflict with the ruling written out.

[PACKAGING.md](PACKAGING.md) — what ships and what must not. ZepTeach ships a
method, never a syllabus.

Twenty doctrine files under `skills/zepteach/references/`. Each opens by
naming the principle it implements; a file that cannot name one should not
exist.

790 tests. Many of them are worth reading on their own: each states, in its
name and docstring, a specific way this could go wrong while still producing
output that reads perfectly well.

## Licence

MIT. See [LICENSE](LICENSE).
