# When practice cannot act on the real thing

> Implements: engineering principle 1 (practice must act on something real),
> learning principle 7 (applying knowledge in a new setting does not happen
> automatically), engineering principle 6 (hard-code neither the environment
> nor the subject).

Read with `setup-stage2.md`. That file covers the conversation; this one
covers what the levels mean and how to keep a substitute honest.

## What has to survive a substitution

Not the product. **The decisions.**

A substitute is acceptable when the learner still has to make the same kinds
of choice, under the same kinds of constraint, and can still be wrong in the
same ways. It is unacceptable when it removes the choosing and leaves the
carrying-out, or removes both and leaves a description.

The test to apply, for any proposed substitute: *what can the learner now get
wrong?* If the answer is shorter than it was for the real thing, name the
difference out loud. If the answer is "nothing much", the substitute is not a
substitute; it is a demonstration.

## The four levels

`practice_reach.py ladder` prints these in fixed wording. Use that wording
rather than paraphrasing, so a learner who meets the situation twice hears
the same thing twice.

**1. Direct.** The thing is at hand and the system works with it.

**2. The learner does it themselves.** Outside this system, on their own
equipment or on paper or in a library, bringing the result back. Everything
is still decided by them. What is lost is that the system cannot see the
attempts that failed on the way, so it learns less about where they struggled
than the result suggests.

**3. A substitute is built.** A smaller version constructed for the occasion:
a passage written in the manner being studied, a document set assembled for
the lesson, a short program implementing one mechanism. The reasoning is real
and the choices are real. What is lost is that someone arranged the
situation, so the difficulties present are the ones that were put there.

**4. Set it up without carrying it out.** The learner specifies the whole
thing and defends every choice. Every decision is still theirs. What is lost
is the check: nothing tests whether the decisions were right, so a confident
and wrong setup scores the same as a confident and right one unless the
marking catches it.

## A built substitute is often not worse

Worth saying plainly, because the ladder's ordering suggests otherwise.

Building a small working version of a mechanism teaches that mechanism
thoroughly. The evidence on learning by implementing is consistent about why:
building forces every choice into the open, where using a complete tool hides
those choices behind a result that looks the same either way. The accepted
practice in fields that have studied this is to do both — build one to
understand it, then use the real tool to work with it.

So a learner without the tool is not simply worse off. They are on a path
that reaches understanding well and stops short of operational competence.

The ladder is ordered by **fidelity to the real task**, not by how much is
learned. Those come apart, and level 3 is where they come apart most.

## The line a substitute never crosses

A substitute can establish that someone understands how something works. It
can never establish that they can operate the real thing.

These are different claims about a person, and only one of them is what a
goal naming the thing was asking for. That is what `named_in_goal` records
and what the check enforces at exit code 3.

The pressure runs one way here. When something is hard to obtain, the
convenient reading is that it was not really required. Re-read the goal
rather than re-reading the difficulty.

## Saying what is lost, every time

Every substitute carries a written statement of what the learner no longer
has to decide. It is required by the stored format, not by politeness.

A substitute described as losing nothing has not been examined. Something is
always lost; whether it matters for this goal is the actual question, and it
cannot be answered until the loss is named.

Write it in the subject's own terms, concretely enough that the learner can
disagree:

- Not "some fidelity is lost", but "the documents were chosen knowing which
  argument they would be used to test, so you never meet a record that is
  silent on your question".
- Not "a simplified model", but "it integrates one mechanism and ignores
  every other force, so anything arising from their interaction will not
  appear".

## Depth ceilings

Each level states the deepest concept depth it can honestly certify, and the
exercise engine reads it rather than deciding during a lesson.

The judgement behind the default: a built substitute reaches depth 3, being
able to derive. It usually does not reach depth 4, being able to judge
someone else's work, because that normally requires having been surprised by
the real thing at least once. An adapter may state otherwise for a specific
case, and should say why.

Where a concept's target is deeper than anything available can certify, the
choice is to obtain what is missing or to lower the target and record it.
Quietly setting an easier exercise is the third option and it is the one this
whole mechanism exists to prevent.

## Re-checking

What is installed and what the learner can reach both change, slowly. The
check goes stale after a week and says so at the start of a session. That is
a note, never a refusal: blocking a lesson because a check is eight days old
would be absurd.

Re-check immediately when an exercise fails in a way that looks like the
environment rather than the learner — a command that is suddenly not found, a
file that was there last week.

## Checks run somewhere disposable

Establishing that a program is the one its name suggests means running it,
and programs write output into whatever directory they were started from. A
log file from one such program was once found sitting in this repository.
Every check of this kind runs in a temporary directory that is deleted
afterwards, never in the plugin directory or the learner's data.
