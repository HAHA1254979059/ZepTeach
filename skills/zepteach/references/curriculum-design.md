# Designing a course

> Implements: learning principle 7 (applying knowledge in a new setting does
> not happen automatically), learning principle 4 (a limit on how many
> connections can be formed at once), engineering principle 4 (state on disk,
> sessions disposable).

Read with `adapter-contract.md`. The adapter says what doing this subject
looks like; this file says how to lay out one course through it.

Run `curriculum.py validate` before anything is taught. A course with a cycle
in its prerequisites, or a concept nothing registers, is refused rather than
discovered halfway through.

## The goal is one sentence about what they will be able to do

Not a list of topics. Topics are what gets covered; a capability is what
changes.

- weak: 学习线性代数的特征值部分
- usable: 拿到一个实际问题，能自己判断该不该用特征分解，能算，能说清什么时候它不适用

The evidence on goal setting is consistent: specific and demanding beats
vague, and on complex work a goal about learning beats a goal about
performing. A goal phrased as a grade or a completion target produces
different behaviour from one phrased as a capability, and the difference is
not in the learner's favour.

Write it in their words where possible. A goal the learner would not
recognise as theirs is a goal they have no reason to hold to.

## Near-term milestones, not only an end date

A single distant deadline does not drive behaviour on complex work. Each
milestone is a date and a capability, written the same way as the goal.

Three or four across a course is usually right. They exist to make "am I
behind" answerable this week rather than at the end, and `curriculum.py
drift` measures against the nearest one.

A milestone that cannot be stated as something the learner will be able to do
is a topic list with a date attached, and will not do the job.

## Concepts

A concept is the smallest thing that can be separately known, separately
practised, and separately forgotten. If two things are always right or wrong
together, they are one concept.

**Ids are global and namespaced**: `<field>.<concept>`. Two courses using the
same id are deliberately talking about the same thing, and share mastery,
notes and review. This is the mechanism that lets a second course benefit
from the first having taught something, and the benefit is largest when the
two courses are in different fields.

Before registering a new concept, check whether it exists. `curriculum.py
register-concepts` reports reuse. Two entries whose names look alike are
flagged for a decision, because the same word meaning different things in two
fields is common and merging them silently is worse than either.

## Prerequisites

Only real ones. A prerequisite edge means the second concept cannot be
understood without the first, not that a textbook happens to order them that
way.

Over-declaring is not cautious. It produces probe questions the learner does
not need, blocks material they could already handle, and makes the hold that
follows a failed retest wider than it should be.

Cycles are refused. If two concepts genuinely need each other, they are one
concept, or there is a smaller third thing both depend on.

## Depth targets

Each concept carries a target per course: able to use it, compute with it,
derive it, evaluate work that uses it, or create with it.

Default comes from the learner's stated expectation. Raise it above that only
where the goal actually needs it, and be able to say which part of the goal.

**Depth is a budget, not an aspiration.** A higher target means more
connections to build, which means more sessions. A course where everything is
set to the evaluative level is a course that will not finish, and the
shortfall will show up as pressure to pass things that were not demonstrated.

Most concepts in most courses should sit below their course's maximum. The
ones at the top are the ones the goal names.

## Lesson size

A lesson introduces at most a few new concepts, three by default, fewer when
energy is low. The limit comes from working memory holding about four things
at once: understanding is built by connecting new material to existing
material, and connections that cannot be held together cannot be made.

Lessons are also where a concept's clock starts. Everything scheduled after
it is measured from the moment teaching began, so a lesson that introduces
six concepts starts six clocks at once and their first retests all arrive
together.

## Ordering

Prerequisites first, obviously. Beyond that, two things worth deliberately
arranging:

**Put something reusable early.** A concept that several later lessons depend
on gets more retrievals for free, and each of those is a review that does not
have to be scheduled.

**Leave room for mixing.** Mixed practice needs at least three concepts with
practised items. A course that spends its first four lessons on one long
prerequisite chain has nothing to mix until lesson five. Where the material
allows, introduce a second strand early so mixed sets become possible sooner.

## Deadline and pace

`weekly_minutes` is what the learner said they can give, not what the course
needs. If the course needs more, that is a fact to state now:

> 按你说的每周时间，到期限差大概两周的量。要么把目标缩一点，要么把期限推后，要么每周多花四十分钟。这三个里选一个，别指望后面赶。

`curriculum.py drift` recomputes this every session open. Being told early is
cheap; being told at the end is not actionable.

## What not to put in a curriculum

- Exercises. Those are set when the lesson runs, against what the learner has
  actually done.
- Explanations. The curriculum says what is covered, not how it is taught.
- Anything the adapter already says. The curriculum is this course's path
  through the field, not a description of the field.
