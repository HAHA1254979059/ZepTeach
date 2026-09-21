# Mastery and review

> Implements: learning principle 2 (only delayed, independent evidence
> counts), learning principle 1 (difficulty during practice improves the
> result), learning principle 8 (courses fail because the learner stops, not
> because they forget).

`review.py` computes the schedule and `zt_state.py` refuses invalid state
changes. This file says what the states mean and why the rules are what they
are.

## Five states

| State | What has happened |
|---|---|
| `unseen` | not taught |
| `introduced` | the lesson on it has begun |
| `practiced` | solved a sourced item during the lesson |
| `consolidating` | passed a retest after a delay, in a different form |
| `mastered` | also passed a transfer test |
| `shaky` | failed a retest that was due |

`shaky` sits beside the others rather than below them. A concept that was
mastered and then failed is not back at the beginning; it is a known quantity
that has decayed, and it is re-earned through the same route.

## Why success during the lesson promotes nothing

Answering correctly ten minutes after being taught is the moment when
retrieval strength is at its peak. It says almost nothing about next week.

This is the rule most likely to feel wrong to the learner, so say it plainly
the first time it comes up:

> 你刚才答对了，但这不算晋级。刚讲完的东西谁都记得住。要算，得隔几天你还想得起来。

`practiced` is the ceiling for anything done in the lesson. The state machine
refuses more.

## Why the first retest is delayed

Delaying the first recall attempt is the single change with the largest
effect on long-term retention. The floor is three days, and it is a floor
rather than a schedule: the adaptive interval usually pushes further out, and
the floor only blocks the same-evening repeat.

The purpose is not auditing. **A delayed retest consolidates the memory; it
does not merely check it.** The retrieval is itself the thing that
strengthens it. So a retest is never presented as an examination, and never
framed as something to prepare for.

## Effort, not just correctness

Every recorded attempt carries how hard the recall was: instant, fluent,
effortful, or recovered with a hint. This is the main input to the next
interval, and the same correct answer earns very different schedules
depending on it.

Effortful is not failure. It is the case where the most is gained: the harder
a successful recall was, the more it strengthens the memory. Say that when it
comes up, because a learner who struggled and got there assumes they did
badly.

> 想了挺久但想出来了——这种比脱口而出的更有用，记得更牢。

**A hint changes the answer.** A retest recovered with a hint does not
promote, because the hint supplied the part that was supposed to be
retrieved, so the retrieval that would have strengthened the memory did not
happen. During teaching a hint is fine and often right. On a retest it means
it has not stuck yet.

## What counts as evidence

Three kinds, and nothing else:

- A delayed retest, at least the minimum gap later, in a different form from
  the original.
- A transfer test, naming which dimension it moved along.
- A stage assessment.

Each has to be independently marked. The verdict comes from the marking
process, which never saw the teaching. See `assessment-rubrics.md`.

Two separate pieces of delayed evidence are required to reach `mastered`, and
the state machine refuses a promotion that rests on one.

## Different form, not the same question later

A retest that repeats the original question tests whether they remember that
question. Change the surface: different numbers, the reverse direction, the
same idea inside a different situation.

Reusing an explain-back as a retest is a specific case of this, which is why
explain-back ids are conventional rather than random. It gets caught.

## When something goes shaky

A failed retest sets `shaky` and holds everything downstream of it. That hold
is a warning, not a wall: the learner can go past it, and the reason is
recorded.

**Bypassing is legitimate.** Sometimes the downstream material is what they
need this week and the prerequisite can wait. What the system does is count.
After three bypasses of the same prerequisite, say so directly:

> 这是第三次跳过这个了。跳过本身没问题，但它已经卡住三节课了。今天花二十分钟修掉可能更划算。

Not a refusal. A cost, stated once, with the decision left where it belongs.

## Retirement

Three consecutive instant recalls remove a concept from the review queue.

Neither spaced repetition system this borrows from retires anything, which
means their queues only grow. A course has an end; something the learner uses
daily does not need a slot. The streak breaks on any answer that is not
another instant pass, so the cost of retiring something too early is one
review.

## Backlog

Overdue work is banded into three levels. One session takes one session's
worth, never the whole queue.

The reasoning is that reviewing late costs about one percentage point of
retention, while the queue growing until the learner stops opening the system
costs everything. The measured failure mode of spaced repetition is
abandonment, not forgetting.

At the most severe band, new material stops entirely and the system says so.
Do not teach a little bit anyway.

**Order within a session is counterintuitive.** With a backlog, take the most
recallable first, not the most overdue. Deeply overdue items have mostly been
forgotten and will need relearning whatever happens, so a few more days cost
little. Items barely holding can be saved now at small cost.

This is the opposite of the no-backlog case, where the scheduler aims each
item at the moment its retrieval strength reaches the target. Two different
situations with two different logics; see the resolution in PHILOSOPHY.

**Never quietly reschedule.** Pushing overdue items forward makes the queue
look manageable and destroys the only signal that the learner is behind.

## Depth

Each concept carries a target depth per course: able to use, compute, derive,
evaluate, or create with it. A concept can be `mastered` at depth 2 in one
course and still be at depth 1 in another.

Depth advances only on demonstration. Record what an answer actually proved,
not what the item was aiming at. An item written for the evaluative level and
passed on its computational criteria proved the computational level.

Going past the target on the main line is refused. Going deeper is a side
branch or an explicit raise, both recorded. Depth that creeps upward is how a
course quietly becomes twice as long as agreed.

## A slip does not move a concept backwards

An attempt recorded with `execution_only: true` - every criterion about the
idea met, only execution ones unmet - leaves the state where it is. It does
not demote to `shaky`, and it does not shorten the next interval.

It does not promote either. What a promotion needs is a clean answer after a
delay, and this was not a clean answer.

`assessment-rubrics.md` has how the distinction is made and what stops it
becoming a way of being kind.
