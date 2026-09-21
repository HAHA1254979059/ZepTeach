---
description: Learn something. Start, continue, or change the plan - say what you want.
argument-hint: "[what you want, or nothing to carry on]"
---

The only way in. There is no second command, and that is deliberate: nine
commands meant the learner had to know which of nine applied before they
could say what they wanted, which is a syllabus in the shape of a menu.

```
python skills/zepteach/scripts/route.py next --said "$ARGUMENTS"
```

That reads what is on disk and prints four things: the step the state points
at, the step that follows it, the files to read for the first one, and a
short list headed `INSTEAD, if that is what they meant`.

## Work out which one it is, then do it

The state decides the default. It cannot read a sentence, so the script does
not try - it names the moves available from here and leaves the matching to
you, because you have the sentence and it does not.

So: if what they said matches one of the `INSTEAD` lines better than the
default, take that one. Otherwise take the default.

The one worth watching for is `replan`. "This is too slow", "skip the proofs",
"I need reinforcement learning before my internship", "can we go back to that
thing from Tuesday" are all requests to change the course, and none of them
look like a command. They go through `curriculum.py replan`, which records the
change and their reason for it, and refuses to quietly drop concepts that were
already taught.

## Carry it out without stopping to ask

When the output says `THEN <intent> (continue without being asked again)`,
that is not a suggestion to relay. The learner has already said what they
want; being asked to type another command is friction they did not agree to.

Stop and ask only for what nobody can work out on their behalf: the teaching
language, why they are studying, which material they hold, whether a target
is within reach, and how they want to give you a formula. "Shall I now create
the course you just asked for" is not one of those.

## If it says `upgrade`

Their records were written by an older version. Run `migrate.py check`, tell
them in one or two lines what changed and what it costs, then
`migrate.py apply`. Nothing they learned is lost. Then carry on.

## When a step genuinely cannot continue

A script exits non-zero. That is a refusal with a reason attached, and the
reason is printed. Relay it in one line, say what would unblock it, and stop
there. Do not try a different phrasing of the same thing.
