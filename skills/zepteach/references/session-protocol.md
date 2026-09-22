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

Ask for energy if the learner did not say. Use `interaction.py energy` and
show the inline choices when the host supports them. The learner may also
describe their condition in their own words. Do not ask again when they have
already said it.

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
- `UNPROVEN` items: ask 2-4 quick questions before teaching. Give the parts
  separate named inputs using `interaction.py request`. Not a test — a
  check that the ground is where the model thinks it is. Record the results
  as attempts with `kind: probe`; probes never move state.
- If the learner has already said a prerequisite or target is unfamiliar,
  do not use a probe to rediscover that declaration. Start teaching at the
  missing foundation. Probe only other prerequisites whose state is still
  genuinely unknown.
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

Use `sources.py plan` and the mapped teaching span where available. Check
the source's definition and notation before delivering the explanation.
When no reliable source is available, say the lesson is unanchored rather
than presenting remembered detail as verified course material.

If the learner says a topic was never taught or asks for the basics, deliver
the explanation in the visible response first. Invite them to name what is
unclear, answer that, then offer one small practice item. A prompt or a
tool-only trace is not the explanation. Do not record a teaching event for
content the learner could not see.

Use the concept's domain register. If the learner names a gap in that
subfield, update only that setting with `learner.py set-register` and their
reason; do not treat the whole course as uniformly easy or hard.

End every new concept with an explain-back. Record it.

## 7. Practise

Choose an exercise for the evidence still needed: anchored for externally
set difficulty, variant for a changed condition, modeling for a real task.
These are available forms, not three required items in every lesson. Once
the course has two or more concepts at `practiced` or above, include a
short interleaved drill whose prompts do not announce the method. Do not
turn a small execution error into a repeated full exercise.

Record every attempt:

```
learner.py record --course <slug> --data '<attempt json>'
```

Carry the open `session_id` on exercises and attempts. A same-session
execution slip cannot trigger another full item on the same concepts.
Explain the local error, offer a single targeted correction only when the
course goal needs it, then move on. A learner can ask for another full item;
record that request and its reason. For a multi-concept item, record each
concept's result separately; the overall verdict is only a summary.

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

## Ending a lesson, and moving on

```
curriculum.py advance --course <slug> --lesson <id>
```

It refuses while the lesson still has concepts nobody explained, or concepts
explained that nobody has said back. Either finish them, or decide with the
learner to leave them and record that:

```
curriculum.py defer --course <slug> --lesson <id> --concepts <a,b> --because <their words>
```

Both outcomes are fine. Drifting is not, and drifting is what happens by
default, because going deeper always feels like the responsible choice from
inside the lesson. One real lesson ran four hours on a course with five
weeks to cover seventy-eight concepts, and nothing anywhere was tracking
that. The learner had to say it.

`curriculum.py` also reports when a lesson passes twice its estimate. That
is a sentence to say out loud, not a stop - a lesson can be worth twice its
estimate, and the thing that is worth nothing is nobody noticing.

## Time they were not here is not study time

`session.py turn` compares each turn against the last one. Past
`idle_gap_minutes`, it says so and tells you to ask - working slowly and
having walked away look identical from the outside, and only one of them is
study time. If they were away:

```
session.py turn --session <id> --away <minutes>
```

That comes off `actual_minutes` and stays in `elapsed_minutes`. The two were
one number until a learner spent over an hour away, twice in one session,
and had to tell the system both times that the clock meant nothing.

**Review intervals keep using the calendar.** Somebody who was away for a
week has forgotten a week's worth whether or not they were studying. That is
the one thing elapsed time is right for, and the reason the two numbers are
kept apart rather than one being corrected into the other.
