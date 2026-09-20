# Writing a course adapter

> Implements: engineering principle 6 (do not write the environment into the
> code, and do not write the subject into it either), engineering principle 1
> (practice must act on something real), learning principle 3 (how to explain
> depends on what this learner already knows in this field).

The core knows how people learn and nothing about what they are learning. An
adapter supplies the second half, for one course, written when that course is
set up. It lives in the learner's data as `adapters/<name>.json`, pointed at
by the course's `adapter_ref`. It is not part of the plugin: if it were, the
plugin would arrive assuming a set of subjects, and everything outside that
set would be second-class.

Validate with `zt_state.py check --schema adapter --file <path>`.

## What an adapter is for

Above all: **saying what doing this subject looks like, in terms the core
understands.**

The core understands seven things a mind can be doing — recall, derive,
apply, construct, analyze, critique, explain back. It does not understand
running a calculation, reading closely, or taking apart a judgment. The
adapter maps the second list onto the first, and once that exists everything
else works: scheduling, depth limits, marking, notes.

Three smaller jobs follow: naming what practice acts on, supplying anything
that can check an answer, and saying where problems of established difficulty
come from.

## Writing one

### Start from where they will use it, not from what the field usually uses

Before writing any target, ask:

> Where do you actually expect to use this? Be as specific as you can — what
> would you be doing, and what would be in front of you?

That answer is stored on the course as `application_scenario` and copied into
the adapter. **Targets are derived from it.** Each one records, in
`from_scenario`, which part of the answer makes it necessary. A target that
cannot be traced back to something they said was chosen by convention, and
convention is what this whole mechanism exists to avoid.

There is no standard answer for a subject. Two people studying the same field
for different purposes should practise on different things, and picking what
the field conventionally uses hands both of them the wrong one. Someone who
will argue about a text in a seminar and someone who will cite it in a thesis
are not doing the same exercise, even in the same course.

**Propose, then ask.** Working the candidates out is this plugin's job.
Deciding is the learner's, and they know their situation. Set
`confirmed_by_learner` when they agreed, not when they did not object.

Then read the course goal and keep it verbatim in `goal_quoted`, because one
judgement here depends entirely on its wording and has to stay checkable.

That judgement is `named_in_goal`. For each target, ask: **does the goal want
competence with this specific thing, or understanding of what it does?**

- "Explain how a technique organises time" — understanding. Without the
  particular work, a constructed passage can carry the lesson.
- "Read this chapter closely and trace its allusions" — competence with that
  text. Nothing written in its place will do.

Set this by reading the goal. **Never set it by how hard the thing is to
obtain.** The temptation runs one way: something difficult to get invites
marking it as not really required. That converts a course the learner cannot
currently do into a course they can, while leaving the title unchanged.

### When the answer is nothing external, say so explicitly

Sometimes the scenario implies the learner needs nothing but their own
working-out. Declare that as a target anyway, with `from_scenario` saying
why. An empty `targets` list reads as a question nobody answered; a target
whose kind is their own written work reads as a considered answer, and the
check can then report that this course needs nothing obtained.

Do not reach for that answer because the subject sounds like one where it
usually applies. Check it against the scenario. The same subject studied to
read other people's work, to produce work, or to teach it lands on different
things.

### Map activities honestly, including the ones that sound alike

The same activity name can map to different actions depending on what is being
practised, and the mapping decides how the work is scheduled and how deep it
can count for.

- A problem with the method already chosen is `apply`. Working out which
  method it calls for and then using it is `analyze` then `apply` — record
  both.
- Building something that did not exist is `construct`, whether the product
  is code, prose or a diagram.
- Judging existing work against stated grounds is `critique`. Reacting to it
  is not.

`depth_range` says the shallowest and deepest concept depth an activity can
serve. Be strict here. An activity that only ever demonstrates that the
learner can carry out a procedure cannot certify that they can evaluate it,
however elaborate the procedure.

### Checking whether a program is what its name suggests

If a target is a program, `how_to_check` should run it, not merely locate it.
A name on the system is not evidence: program names collide, and a name that
matches a well-known scientific tool on one machine belongs to something
completely unrelated on another. Give a command and a string that must appear
in its output.

Two constraints on the command:

- It runs in a temporary directory that is deleted afterwards. Many programs
  write a log or output file into whatever directory they were started in, and
  one such file has already turned up inside this repository.
- It has a timeout. A check that hangs would take the lesson down with it.

### Write the substitute now

For every target that might not be reachable, write what practice becomes
without it, before any lesson needs it. Each substitute states three things:
which level of the ladder it sits at, what it actually is, and **what the
learner no longer has to decide**.

That last field is not optional and not a formality. A substitute described as
losing nothing has not been examined. Something is always lost; the question
is whether what is lost matters for this goal. Writing it down is what lets
that question be answered instead of assumed.

A substitute the system constructs is often good. Building a small working
version of a mechanism teaches the mechanism thoroughly, sometimes better than
operating a complete tool does, because building forces every choice into the
open where using hides it behind a result. What building can never do is
establish that the learner can operate the real thing. That distinction is the
entire content of `named_in_goal`.

## What must not go into an adapter

- **Teaching method.** How to explain, when to test, how long to wait, what
  counts as a pass — all in the core, all subject-independent. An adapter
  that describes how to teach will drift from the core's rules unnoticed.
- **A curriculum.** The adapter describes the field; what to study in what
  order belongs in the course's curriculum.
- **Exercises.** Activities are categories, not problems.
- **Claims about the learner.** Their standing is in their profile and is
  established by probing, not by an assumption about who studies this
  subject. `register_hint` is a suggestion to raise with them, nothing more.
- **Any key or password.** Configuration stores the name of an environment
  variable, never its contents.

## Reusing one

An adapter from another course in the same field is a starting point, but it
was written against one goal and one scenario. `named_in_goal` and every
`from_scenario` are statements about those, and are very likely wrong for a
different learner or purpose. Re-derive them before reusing, and change
`generated_for`.
