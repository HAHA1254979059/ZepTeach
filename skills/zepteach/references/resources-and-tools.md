# Materials, tools, and wiring them up

> Implements: engineering principle 6 (hard-code neither the environment nor
> the subject), engineering principle 1 (practice must act on something
> real), engineering principle 8 (portable, inspectable, no hidden
> requirements), engineering principle 2 (requirements that must not be
> violated belong in code, not in instructions).

Loaded only when a course has tools registered. A course whose practice is
reading, writing and thinking never reads this file.

Everything here is recorded per course in `resources.json`, alongside the
course, and nothing in it is assumed by the plugin. An entry exists because
the learner said so, or because a check found it. There is no third way.

## Two things get recorded, and the second is the valuable one

**Material** — what they supplied to learn from. Enough detail to find a
specific place in it again, which means the edition matters: a citation to a
section number is worthless if two people hold different printings.

**Tools** — what their environment offers, and **how to use each one well**.
The second half is the part worth writing down. What a tool is called is
trivia; which flag matters, what its output actually means, and the mistake
everyone makes the first time are things that would otherwise be worked out
again in every lesson, badly, and sometimes wrongly.

Ask for that directly, because the learner usually knows it and will not
volunteer it:

> Anything I should know about using it? The setting that matters, the thing
> that catches people out, what its output means when it looks wrong?

Record what they say in `how_to_use`, and record what the tool cannot do, or
does misleadingly, in `limits`. That second field prevents a whole class of
wasted lesson.

## A tool the learner operates themselves is a proper entry

Most useful tools are not things this plugin runs. Something the learner
opens, runs and reports back from belongs in this file exactly as much as
something scriptable. Record what it does, where it is, and how they use it.

Only fill in `invocation` for something the plugin runs itself, and only with
the paths the learner explicitly permitted. Leaving it out is not an
incomplete entry; it is the common case.

## Wiring a tool up, once

When a tool has a procedure worth capturing, set up the wiring for it rather
than re-explaining it every lesson. Four shapes, in order of what to reach
for first:

- **An existing plugin or MCP server already covers it.** Use that. Record it
  in `integrations` with the tool it serves, so that later someone can see
  where the capability came from.
- **A project-level skill.** For a tool with a real procedure: the steps, the
  flags that matter, the checks that catch the usual mistakes. This is the
  common case, and it is where `how_to_use` and `limits` should end up.
- **A command.** For something used constantly enough that typing it out each
  time is friction.
- **Nothing.** Often correct. A tool used twice does not need wiring; it
  needs a sentence in `how_to_use`.

Three rules on this:

1. **Show the learner before writing anything outside this plugin's own
   data.** Wiring goes into their project. Record `confirmed_by_learner`.
2. **Say what it saves.** An integration that saves nothing is clutter that
   still has to be maintained. If the answer is vague, do not build it.
3. **Record where it went.** Something nobody remembers configuring is worse
   than something absent, because it will be found later by someone who
   cannot tell whether removing it is safe.

## What is refused, wherever work runs

These are enforced by `sandbox.py`, which refuses with exit code 3 and
explains why. They are in code rather than in prose because a model reasoning
about whether an exception is justified can construct a case for one, and
cannot construct a case that changes what a validator does.

**Paths outside what the learner permitted, reads included.** A directory
they did not mention is not this plugin's to look in, even harmlessly. Also
refused: climbing out with `..` however it is written; anything starting with
`~`, which means a different directory depending on who is logged in;
relative paths, which depend on where a command happened to start; and
everything at all when nothing was permitted.

One case worth knowing because it is invisible when reading code:
`/home/u/workdir-evil` is not inside `/home/u/workdir`, but a string
comparison says it is. Paths are compared one component at a time for this
reason.

**Anything that changes an environment.** Installing or removing packages.
Changing a package environment. Loading modules. Editing startup files.
Setting variables that persist. Changing permissions or ownership. Anything
elevated. Global settings for another tool. Anything that keeps running
afterwards. Deleting broadly.

This holds even when the learner would obviously agree. Environments break in
ways that surface days later, often on someone else's work, and the person
who lives with the consequences should be the one who acted.

**Refusing is half the job.** Say what is missing in one line, specific
enough to act on:

> That analysis needs a package this environment does not have. I have not
> installed it — that is yours to decide. It is `<name>`, needed for
> `<the specific step>`.

A refusal with no alternative gets worked around, and the workaround will be
worse than what was refused.

**Anything without a time limit.** Without one, something that hangs waits
for as long as the learner is willing to sit there, and the lesson ends
without anyone deciding to end it. Half an hour is the outer bound for
anything waited on. Longer work is something they start and come back to.

## Where other people are affected

When the learner says something is shared — a machine, a quota, an account —
every piece of work states its size, and the limit they set is enforced.
Where nothing else rations it, that number is the only thing preventing one
exercise from taking all of it.

Before anything substantial, say what it will consume. Someone else's work
being displaced by a learning exercise is a real cost and not one to impose
quietly.

## Credentials

Store the **name** of an environment variable, or the **path** of a file.
Never a password, key or token, in any field.

A value never reaches a command line, because anything there is visible to
everyone who can list processes and lands in shell history. A value is never
printed, including in an error: a refusal gets printed, and printed things
end up in transcripts. If something that looks like a credential is about to
be stored, `sandbox.py` refuses and says where it came from without repeating
it.

## When something is declined

Record it. A suggestion turned down and then made again next week is its own
kind of failure, and the learner had a reason the first time.

## When something fails

Report what ran, where, what came back, and what it means for the lesson. Do
not retry a refused command in another form: a refusal is a decision, and
finding a phrasing that slips past it converts a boundary into an obstacle.

If a boundary is genuinely in the wrong place, say so and ask the learner to
widen it. That is a conversation, not a workaround.
