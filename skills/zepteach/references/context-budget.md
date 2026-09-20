# Context budget

> Implements: engineering principle 3 (loaded context costs money and reduces
> accuracy), engineering principle 4 (state on disk, sessions disposable),
> learning principle 4 (a limit on connections formed at once).

Two problems, one mechanism. A long session costs more per turn and remembers
less, because the transcript grows while the useful signal in it does not. And
a session that introduces more than can be integrated produces the feeling of
a lot covered and the reality of nothing built.

The turn budget fixes both by forcing the session to periodically convert
transcript into durable state, and then drop the transcript.

## How it runs

`session.py open` sets the budget from config, scaled by declared energy.

**Call `session.py turn` exactly once after every exchange with the learner.**
One call per round trip, from open to close. This is the only thing driving
the budget — there is no timer and no automatic counter. Skipping the calls
does not save anything; it just removes the mechanism.

| Exit | Meaning | What to do |
|---|---|---|
| 0 | fine | carry on |
| 4, "CHECKPOINT DUE" | 60% of budget used with no digest since the last one | write the digest, run `session.py checkpoint`, then drop detail |
| 4, "BUDGET REACHED" | 90% used | close the session; do not negotiate |
| 3 | session already closed | open a new one |

Non-zero is an instruction. Working around the gate by not calling `turn` is
the one failure mode this design cannot detect, so do not do it.

## What a digest must contain

A digest is not a summary of the conversation. It is the set of things that
must survive the transcript being thrown away.

Required:

1. **Concepts touched**, each with what state it reached and why
2. **Established facts** — the substance taught, written as knowledge, not as
   narrative. Not "we discussed the main idea", but the idea itself
3. **Open threads** — what was left unfinished and where to resume
4. **Errors worth keeping** — misconceptions that surfaced, because they
   predict where this will break again
5. **Written artefacts** — which notes were created or rewritten, which
   attempts were recorded

Not in a digest: pleasantries, restated questions, the teaching sequence
itself, anything already in `attempts.jsonl` or the notes.

Write it to `courses/<slug>/sessions/<id>/digest.md`, then pass that path to
`session.py checkpoint`.

## What may be dropped after a checkpoint

Everything the digest and the on-disk state already carry:

- the verbatim explanation text
- the learner's working for attempts that have been recorded
- source spans that have been read and cited
- tool output that has been acted on

What must not be dropped:

- the current brief (register, persona, budget)
- the digest itself
- an unresolved thread the session is still in the middle of

## Do not try to save context by skipping the state writes

Recording an attempt and writing a note look like overhead inside a single
session. They are the only reason the session can be thrown away cheaply. A
session that teaches well and records nothing has produced nothing: the next
session starts blind, and the delayed retest that would have proved the
learning never gets scheduled.

Order of operations at every natural break: **record, write, then compress.**

## Session sizing

New concepts per session are capped — default 3, dropping to 1 on low energy.
This is anchored on working-memory capacity of about four chunks, so it is a
soft limit about how much can be *connected*, not about how much can be
mentioned. Mentioning more is not cheaper; it is just uncounted.

If the material genuinely needs more concepts to make sense as a unit, that is
a curriculum problem: the lesson is too big. Split it rather than overrunning
the cap.
