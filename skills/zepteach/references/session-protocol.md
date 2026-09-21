# Session protocol

> Implements: learning principle 2 (only delayed, independent evidence
> counts), principle 8 (courses fail because the learner stops), engineering
> principle 4 (state on disk) and principle 7 (failures leave a record).

The fixed sequence a teaching session runs through. Each step has a script
behind it; a non-zero exit is an instruction, not a warning.

## 1. Open

```
session.py open --course <slug> --energy <low|normal|high> [--minutes N]
```

Ask for energy if the learner did not say. One question, no preamble:
今天状态怎么样？

Exit 3 means the course never had its environment setup run. Do not teach;
run setup stage 2 first.

The brief that prints is the entire context you start from. Do not load the
learner model, the curriculum, or other doctrine files on top of it. Fetch
what you need when you need it.

## 2. Open on the real state, not on pleasantries

The brief prints what is overdue, what is shaky, what the pace looks like.
Say those things first, in one or two sentences. Do not ask what they want to
work on before reporting what is owed.

If the backlog band is `severe`, say it plainly and say new material is
paused. Do not soften it and do not reschedule the debt away.

## 3. Clear what is due before teaching anything new

Due reviews come first. This is not politeness to the queue: a delayed retest
is the only evidence that can move a concept forward, and a retest not taken
is progress that cannot be recorded.

Take the number the brief shows, not the whole queue.

Running a retest is its own job with its own doctrine. Resolve the `review`
route when you get here rather than loading it up front —
`route.py for review --course <slug>`.

## 4. Probe the ground

```
learner.py probe --course <slug> --lesson <id>
```

- Exit 3: a prerequisite is shaky and held. Repair it, or have the learner
  explicitly say to carry on and record that with `learner.py bypass`.
- `UNPROVEN` items: ask 2-4 quick questions before teaching. Not a test — a
  check that the ground is where the model thinks it is. Record the results
  as attempts with `kind: probe`; probes never move state.
- `ASSUMED BACKGROUND`: candidates for a sidequest. Do not teach them inline;
  that is how the main thread gets lost.

## 5. Record what was explained

```
learner.py teach --course <slug> --file <exposition.json>
```

One concept, one explanation, containing what was actually said. This is the
step that used to read: "taught" means the lesson has begun, not that an
explanation has been delivered. That sentence was in this file for weeks and
it was the whole defect. It made starting a lesson and teaching it the same
recorded event, so the second one could be skipped without anything noticing,
and in the first real use it was: twenty-five assessment items across three
lessons and almost nothing said.

What the document has to contain is in `teaching-contract.md`, and what will
be refused is in `teaching.py`. The check that matters most: the explanation
has to exist somewhere other than inside the questions asked about the
concept. Folding a definition into the stem of an item reads like teaching
and is assessment.

**In productive-failure mode this step comes after the first attempt, not
before.** Give them the untaught thing, let it fail, then explain into the
gap and record that. Mark the first attempt `kind: probe`; probes are the one
kind allowed on an unexplained concept, precisely so this order is possible.

Every review interval is measured from `delivered_at`, so a lesson on Monday
practised on Friday must not baseline itself to Friday.

**One call per concept, matching the new-concept cap.** There is no longer a
way to mark a whole lesson taught at once. Scoping that call used to be a
convention here; it was never enough, because the call was free either way.

## 6. Teach

If the brief shows `new concepts <= 0` — a severe backlog — **skip this step
entirely** and go to step 8. Say so plainly; do not teach a little bit anyway.

Otherwise: `curriculum.py lesson` for the lesson card, `mode-router.md` for
the mode, `teaching-contract.md` for the shape. Do not exceed the cap.

End every new concept with an explain-back. Record it.

## 7. Practise

Three tiers per lesson: anchored, variant, modeling. Plus an interleaved drill
once the course has two or more concepts at `practiced` or above.

Record every attempt:

```
learner.py record --course <slug> --data '<attempt json>'
```

A pass needs quoted evidence from the learner's own answer. If you cannot
quote it, it is not a pass — and the script will refuse the write anyway.

Every attempt also carries a recall-effort rating and, if it passed, the depth
it proved. See `teaching-contract.md`; the validator warns when they are
missing, because the schedule quietly degrades without them.

## 8. Checkpoint when told

**Call `session.py turn` once after every exchange with the learner** — one
call per round trip, all session long. Nothing else drives the budget: skip
the calls and the checkpoint never fires, the session grows unbounded, and
the mechanism that makes a session cheap to discard never runs.

`session.py turn` returns exit 4 with CHECKPOINT DUE. Write the digest per
`context-budget.md`, run `session.py checkpoint`, then drop the detail.

## 9. Write the notes

Canonical notes for concepts whose understanding changed. Journal for the rest.
See `note-doctrine.md`. Do this before closing, not "next time".

## 10. Close

```
session.py close --session <id> --reason <reason> [--digest <path>]
review.py rebuild --course <slug>
```

Reasons are honest: `completed`, `budget_reached`, `fatigue`,
`learner_stopped`, `blocked`, `crashed`. Pick the true one.

If fatigue was detected, say what it means and what it does not:
今天后半段错率上来了，停在这。这是今天到量了，不是你没学会。

Rebuild the queue last so the next session opens on current numbers.

## If the session is interrupted

State is on disk after each record and each note. A crashed session loses the
transcript and nothing else. On resume: `zt_state.py validate`, then
`session.py close --reason crashed` on the stale session, then open a new one.

Never re-record attempts that were already written. Duplicate evidence
corrupts the schedule.

## What never happens in a session

- Teaching before the environment gate passes
- Recording an attempt for a concept with no teaching event
- Promoting anything on the strength of the learner agreeing
- Asking the learner to self-assess and using the answer as evidence
- Exceeding the turn budget because the conversation was going well
