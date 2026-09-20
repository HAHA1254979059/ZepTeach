# Second setup: what this course will practise on

> Implements: engineering principle 1 (practice must act on something real),
> engineering principle 6 (hard-code neither the environment nor the subject),
> learning principle 7 (applying knowledge in a new setting does not happen
> automatically).

This runs after a course goal exists, never before. What a course needs
depends on what it is for, and asking earlier produces a list of things that
may all turn out to be irrelevant.

Order: ask where they will use this, write the adapter from that answer
(`adapter-contract.md`), then `practice_reach.py check --course <slug>`, then
have the conversation below, then `--write`.

The first step is not optional and is not a formality. What practice should
act on comes from where the learner will use the knowledge, not from what the
field conventionally uses. Get that answer first and as specifically as they
can give it; everything below is shaped by it.

## The plugin knows nothing until it is told

Nothing about the learner's equipment, accounts or material is assumed. What
they have not mentioned does not exist as far as this conversation is
concerned, and is not offered as an option. Proposing something elaborate to
someone working on a laptop wastes their time and implies the course needs
what it does not.

A resource becomes known one of two ways: a check finds it, or the learner
says they have it. There is no third way, and in particular nothing is
assumed to exist because the subject usually involves one.

## Report the shortfall in terms of the work, not the thing

The output of the check names targets. Do not read it out that way. A learner
hearing "the solver is not installed" or "the archive is not reachable"
learns nothing they can act on.

Say what changes about the work:

> Without the documents, judging whether a claim is supported becomes working
> with a set I put together. That still practises the reasoning, but the
> documents will have been chosen knowing what they would be used to test, so
> you never hit the real problem: a record that simply has nothing to say
> about the question you are asking.

That sentence contains a decision the learner can actually make. The
alternative does not.

## Give the levels and their costs, then let them choose

When more than one level is workable, say what each costs and ask. Do not
pick quietly. `practice_reach.py ladder` prints the four levels in fixed
wording so the explanation is the same every time it is given.

Record the choice on the course. It is settled once, not re-decided in each
lesson, because a decision made mid-lesson will be made under time pressure
and will drift towards whatever is easiest that day.

## The one shortfall that cannot be worked around

If the goal names the thing that is missing, no substitute counts, and the
check exits 3.

This is not about the substitute being poor. A substitute can be excellent —
building a small working version of a mechanism often teaches the mechanism
better than operating a full tool does, because building forces every choice
into the open where using hides it behind a result. What building can never
establish is that the learner can operate the real thing.

So there are exactly two ways forward, and both belong to the learner:

1. Obtain it.
2. Change the goal, so it asks for understanding rather than competence with
   the thing itself.

Offer both. Do not offer a third. In particular, do not offer to keep the
goal and work around the gap, which is the option that feels most helpful and
is the one that produces a course claiming something it did not deliver.

## Depth that cannot be reached

The check also compares what the course wants against what the available
practice can honestly establish. Where a concept asks for more depth than any
available activity can certify, say so now.

Lowering a depth target is a legitimate answer. Lowering it silently is not:
it is recorded on the course and appears in progress reports for as long as
the course exists. The learner should hear that before agreeing, in one line:

> We can still cover it, but only to the point where you can derive it, not
> to the point where you could judge someone else's use of it. That will show
> in the progress report as a target that was lowered, and why.

## Nothing is installed

A shortfall becomes a written suggestion. ZepTeach does not install software,
create accounts, obtain files, or change any environment, and does not offer
to. It says what is missing, why it matters, and where to get it, and then
the learner decides.

This holds even when the learner would obviously agree. Machines are often
shared, environments are easy to break in ways that are hard to notice, and
the person who has to live with the consequences should be the one who acted.

## Write down what they have, and how they use it

Once the conversation settles, record it with `resources.py`: the material
they supplied, and the tools their environment offers. Then read
`resources-and-tools.md`, which is otherwise never loaded.

The part that repays the effort is not the list of names. Ask, for each tool,
what they know about using it well — the setting that matters, the thing that
catches people out, what its output means when it looks wrong — and record
that. It is knowledge they already have and will not volunteer, and without
it every lesson reconstructs it from scratch.

A tool the learner operates themselves is a proper entry and usually the
common case. Only record how to run something if this plugin will run it, and
only with the directories they explicitly permitted.

Where a tool has a procedure worth capturing, `resources.py review` says
whether to wire it up and as what — an existing plugin or server, a
project-level skill, a shortcut, or nothing. Nothing is often right. Anything
written into their project is shown to them first.
