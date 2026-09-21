---
description: Start or continue learning. Works out what is needed and does it.
argument-hint: "[what you want to study, or nothing to carry on]"
---

The single entry point. Use this rather than picking from the other nine.

```
python skills/zepteach/scripts/route.py next --said "$ARGUMENTS"
```

That reads what is on disk and prints three things: the intent to run now,
the intent that follows it, and the files to read for the first one.

Then **carry both out without stopping to ask.** When it prints
`THEN <intent> (continue without being asked again)`, that is not a
suggestion to relay; it means the learner has already said what they want and
being asked to type another command is friction they did not agree to.

Stop and ask only when the learner has to supply something nobody can work
out for them: the teaching language, why they are studying, which material
they hold, whether a target is within reach. Those are questions. "Shall I
now create the course you just asked for" is not.

## What it does with what they said

`--said` carries the learner's actual words. It does not decide the step;
the state does that. It changes what gets said, because answering somebody's
request with an instruction to run a different command reads as a refusal
even when it is not.

If they named a subject and setup has already run, go straight to building
that course. Do not announce that setup was already complete unless they ask.

## When a step genuinely cannot continue

A script exits non-zero. That is a refusal with a reason attached, and the
reason is printed. Relay it in one line, say what would unblock it, and stop
there. Do not try a different phrasing of the same thing.
