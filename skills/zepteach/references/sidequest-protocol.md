# Filling a gap without losing the lesson

> Implements: engineering principle 5 (running something in a separate
> process with different context is a capability), engineering principle 3
> (loaded context costs money and reduces accuracy), learning principle 4 (a
> limit on how many connections can be formed at once).

A gap appears mid-lesson: something the learner needs and does not have,
which is not what today is about.

Handling it inline is what makes a lesson wander. Each step is reasonable,
nobody notices the drift, and an hour later the thing that was supposed to be
learned has not been. Refusing to handle it is also wrong: the gap is real
and the lesson cannot proceed over it.

The answer is a separate process with its own context, which returns a short
summary rather than a conversation.

## Decide inline or separate, once

**Handle it inline** when a sentence closes it. A term they have not met, a
step they have forgotten, a notation difference. Say it, use it, move on.

**Open a side branch** when any of these is true:

- It needs teaching, not telling.
- It has prerequisites of its own.
- It would take more than a few exchanges.
- It is interesting enough that it will pull the lesson towards itself.

The last one is the case most often missed, and the one worth being strict
about. A genuinely interesting tangent is more dangerous to a lesson than a
difficult one, because nobody wants to stop it.

**Do not decide twice.** Starting to handle something inline and then opening
a branch halfway costs the worst of both. If it looks like it might need a
branch, open one.

## What the separate process gets

- The gap, stated as a question.
- The language register for that field.
- A depth ceiling. Usually one level below the main line's target for
  whatever needed it. This is a gap being filled, not a second course.
- A time box.

It does not get the lesson transcript. Not for secrecy: it is faster and more
accurate without it, and a process that knows what the main lesson is about
will bend the explanation towards that lesson instead of explaining the thing
as it is.

## What comes back

Three things, and nothing else:

1. **A short summary.** Aim for under two hundred words. What the learner now
   knows, written as knowledge, not as an account of the exchange.
2. **One canonical note**, in the same form as any other.
3. **A mastery entry** for the concept, at whatever state was actually
   reached. Usually `introduced`, sometimes `practiced`. A side branch can
   reach `practiced` if it included a real item; it cannot reach further,
   because everything beyond that needs a delay.

The transcript does not come back. If it did, the isolation would have saved
nothing, which is the failure mode to watch for: a side branch whose entire
conversation ends up pasted into the main line has cost extra and gained
nothing.

## Returning to the lesson

Say what was filled and go back:

> 补完了。<那个概念> 是 <一句话>。回到刚才那步——现在这个条件为什么成立？

Do not recap the side branch. Do not ask whether they followed it. The
summary is on disk and the note exists; if it did not work, that will surface
when the concept next comes up, which is a better test than asking.

## The depth ceiling is a real limit

A side branch that goes deeper than the main line needs has inverted the
lesson: the gap becomes the subject and the actual subject becomes the
tangent. The ceiling is what prevents that, and it is enforced as a
constraint on the branch rather than as a judgement made while inside it,
because inside it there is always one more thing worth explaining.

If the gap turns out to be genuinely larger than a branch can hold, that is
information about the course, not a reason to expand the branch. Say so, and
put it in the curriculum:

> 这块比我预计的大，不是一次能补完的。先按够用的程度处理，然后我把它加进课程里，当成一节课来上。
