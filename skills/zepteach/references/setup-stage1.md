# First setup: the opening interview

> Implements: learning principle 3 (how to explain depends on what this
> learner already knows in this field), engineering principle 4 (state on
> disk, sessions disposable), learning principle 2 (only delayed, independent
> evidence counts — which is why level is measured rather than asked).

Run `intake.py known` first, then `intake.py questions`. The script holds the
questions, the reason for each, and the reason certain obvious ones are not
asked. This file says how to conduct it.

## Read before asking

`intake.py known` reports what is already recorded. Ask about nothing it
returns. A system that asks again what it was already told is the thing this
project exists to replace, and the first conversation is where that
impression forms.

If it reports that the first setup already ran, do not re-run the interview.
Ask only what the learner says has changed.

## Ask what they encountered, never how well they know it

This is the one rule here with measurement behind it. Self-rated knowledge
gain correlates at about zero with gain measured by testing, and self-reported
level runs consistently above measured level. What learners do report
accurately is which courses, books and projects they went through.

So:

- "Which courses or books have you been through?" — ask this.
- "How comfortable are you with it, out of five?" — never ask this.

The second question would produce a number, the number would be stored, and
something downstream would use it as though it meant something. No answer is
better than an answer that looks like information and is not.

Anything the learner says about their own level is recorded as `self_declared`
and **may never be used to skip a prerequisite check.** It says where to start
asking, nothing more.

## The teaching language is never chosen for them

Ask it, and ask it first. Choosing silently decides how every explanation they
ever read will sound, and by the time it becomes noticeable it feels rude to
raise. If the answer is not given, `intake.py write` refuses and nothing is
stored, which is the intended behaviour and not a bug to work around.

## Say what tone does and does not affect

When asking how close Zep should be, say the second half out loud:

> How close should I be — colleague, or someone you share a desk with? Either
> way it changes how I talk and nothing about what counts as a right answer.
> Marking is done by something that never sees our conversation.

It costs one sentence and it prevents the expectation that a friendly tutor is
a lenient one, which otherwise has to be disappointed later.

## Why they are studying is the one thing that cannot be measured later

Everything else about a learner can be established by watching them work.
Their reason for being here cannot. It also settles how deep is deep enough,
which otherwise gets renegotiated in every single lesson and slowly drifts
towards whatever felt interesting that day.

Ask it plainly, accept the answer in their words, and follow it with the
default depth. Those two go together: someone preparing to do research and
someone who wants to read papers without getting lost need different answers
to how far to push, and the difference comes from the first question.

## Do not ask about equipment

It looks efficient to gather everything while they are answering questions. It
is not, because what a course needs depends on what the course is, and no
course exists yet. Asking now produces a list of things that may all turn out
to be irrelevant, and misses whatever the actual course needs.

That belongs to the second stage, `setup-stage2.md`, once a goal exists.

## Ending it

`intake.py write` validates before storing. If it refuses, a required answer
is missing; go back and ask that one question rather than filling the gap
with something plausible.

When it succeeds, say what happens next in one sentence: a course gets
created, its goal is written as something they will be able to *do*, and only
then does it make sense to work out what practice will act on.

## Ask one group at a time, and only when it blocks something

`intake.py next --group <start|course|notes|item>` returns only the questions
standing between here and that thing. Before the first lesson that is one
question: which language to teach in.

The interview used to be nine questions in one message, and the first real
learner's first complaint was exactly that - too much at once, split it into
groups and ask each group when it matters. It is worse than tiring. Two of
the nine asked them to decide what belonged in a course about a field they
had not started, and the answer they gave was a guess that then sat in the
records looking like a decision.

**Propose, do not interrogate.** Whenever anything already said supports an
answer, state it and ask them to correct it. Somebody who has just described
their job has answered why they are studying; asking it back reads as not
having listened, and it was the third thing they complained about. Keep an
open question for what genuinely cannot be inferred.

**The tone is not a question.** It was, with a one-to-five scale, and the
learner's instruction was to stop asking: if the tone is wrong they will say
so. Asking someone to predict their preference about an experience they have
not had yet produces an answer worth less than a default they can correct.
`persona.closeness` still exists, and is set when they say something, never
by asking.

**Notes get a place and an announcement, not a question.** They go under the
data root, and the first time notes are written, say where. A stated default
is correctable in one sentence; a required path is a decision about the end
of a session standing in front of the first word of the first lesson.
