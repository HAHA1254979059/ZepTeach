# Mode router

> Implements: learning principle 5 (practising topics mixed together),
> principle 6 (having the learner produce the answer), principle 3 (teaching
> depends on standing in that field), principle 1 (difficulty during practice
> improves the result).

The teaching mode is chosen from the situation, not from the mood of the turn.
Inputs: what kind of content, what state the concept is in, the register for
this concept's domain, declared energy, and the depth target. A course's
broader domain is not enough when the learner knows one subfield but not
another.

## The nine modes

| Mode | What happens | Learner produces |
|---|---|---|
| `productive_failure` | a problem they have not been taught, then teaching into the failure | an attempt that is expected to fail |
| `worked_example` | a full solution shown, then a near-identical one faded | the faded step |
| `guided_derivation` | derive together; Zep holds the thread, learner takes the steps | each step |
| `direct_instruction` | just explain it | nothing yet |
| `socratic` | questions only; Zep does not state the answer | the answer |
| `interleaved_drill` | mixed items across concepts, method not named | the choice of method, then the solution |
| `explain_back` | learner reconstructs it unaided | the whole explanation |
| `repair` | re-teach aimed at the exact failure that broke it | corrected attempt |
| `critique` | a flawed solution or argument to take apart | the located flaw and why |

## Decision table

Read top to bottom; first match wins.

| If | Mode |
|---|---|
| a prerequisite is on hold and not bypassed | **stop** — `learner.py probe` gate, exit 3 |
| the learner explicitly says this material was never taught, or asks to learn it from the beginning | `direct_instruction` or `worked_example`; explain visibly before any diagnostic or scored item, then ask what remains unclear |
| the concept is `shaky` | `repair` |
| depth target ≥ 4 and the concept is at least `consolidating` | `critique` |
| the concept is new, **conceptual**, the probe came back clean, energy not low | `productive_failure` |
| the concept is new, **procedural**, register is `analogy_first` or `technical_with_gloss` | `worked_example` |
| the concept is new, **procedural**, register is `terse_technical` | `guided_derivation` — an expert does not need the worked example, and it costs them load |
| the concept is new, but prerequisites are thin or energy is low | `direct_instruction`, then a small check |
| the concept is `introduced` and needs consolidating in-session | `explain_back` |
| ≥ 2 concepts in this course are at `practiced` or above | `interleaved_drill` — **mandatory at least once per session when this holds** |
| a due review item is being worked | see `mastery-policy.md`, not this table |

## Productive failure: when and how

Try-then-teach beats teach-then-try for **conceptual** targets. It does not
beat it for everything, so the preconditions are real.

Use it when all hold:

- the target is conceptual (why it works, when it applies, what it trades off)
- **the probe came back clean** — either the prerequisites were already at
  `consolidating` or better, or the probe questions in protocol step 4 were
  answered correctly. Failure needs solid ground underneath, or it is just
  confusion. A failed probe kills this mode: repair or sidequest first
- energy is not `low` — this mode is expensive
- there is time for the teach half; never leave the failure unresolved
- the learner has not explicitly asked for an explanation first or said the
  necessary material is unfamiliar. Such a statement is more useful than a
  fresh failure designed to discover the same gap

Do not use it for: safety-relevant procedures, notation and conventions, or
anything where a wrong first attempt would be rehearsed rather than examined.

How to run it:

1. **Mark the first attempt `kind: probe`.** That is the one kind allowed on
   a concept nothing has explained yet, and it exists so that this mode can
   run: `learner.py record` refuses any other kind of attempt on an
   unexplained concept, exit 3.

   This used to say to run `learner.py teach` first, on the grounds that the
   teaching event meant the lesson had begun rather than that anything had
   been explained. That reading is gone. Recording teaching now means
   recording what was said, which in this mode has not happened yet — the
   whole point of the mode is that it happens at step 5.
2. Give a problem that needs the concept, without naming it.
3. Let them work. Do not rescue. A wrong complete attempt is the product.
4. Ask what they tried and where it stopped working. Their account of the
   failure is the material the teaching attaches to.
5. Record the attempt: `kind: probe`, with real `failure_points`. Probes
   never move state, which is what makes it safe to hand someone something
   they cannot yet do.
   **A failed first attempt in this mode is not a bad outcome and must not be
   framed as one.**
6. Now teach — pointing at the specific place their attempt broke — and
   record the explanation with `learner.py teach`, setting
   `led_by: after_failed_attempt` and `opened_by_attempt` to that probe's id.
   Everything after this point is an ordinary `inclass` attempt.

   Step 6 is the one that goes missing. The first five are vivid and the
   sixth is the payload; in the first real use of this plugin the pattern
   ran over and over with the explanation never arriving, and nothing
   noticed because nothing measured it. It is now measured.

Say what is happening up front, once: 这题还没教，先试，卡住是正常的。
Without that framing the learner reads it as being set up to fail.

## Interleaving

Blocked practice — three problems of the same type in a row — trains applying
a method you were already told to use. Interleaved practice forces choosing
the method, which is the part that actually transfers. It performs worse
during the session and roughly twice as well on a delayed test.

Rules:

- Once a course has ≥ 2 concepts at `practiced` or above, **every session
  includes at least one interleaved drill.**
- Interleaved items must not announce which concept they belong to. If the
  learner can tell from the prompt, it is not interleaved.
- Mark them: `interleaved: true` on the exercise and on the attempt. An
  interleaved item spanning only one concept is refused - with one concept
  the prompt still tells the learner which method to reach for.
- Mix across lessons and, where the shared concept registry allows, across
  courses. A concept first taught in one course and needed again in another
  is the best interleaving source there is, because the second course did not
  set it up for you. Concepts are global for this reason.
- Expect in-session performance to drop. Say so before starting, and do not
  treat the drop as a regression: 混着来会比刚才难，这是故意的。

## Explain-back is not optional

Every newly taught concept ends with the learner reconstructing it unaided,
before the session moves on. Record it as an attempt with `form:
explain_back`. It is the cheapest available test of whether anything was
built, and it is the direct antidote to the fluency illusion: following an
explanation feels identical to being able to produce one.

Record it like this - it has no exercise tier, because it is not an exercise:

```
kind: inclass, form: explain_back, tier: (omit),
exercise_id: "explain-back:<concept_id>",
latency_rating: <rated as usual>, depth_demonstrated: <what it proved>
```

The stable `exercise_id` is deliberate: it makes reusing the same explain-back
as a later retest a detectable error rather than an invisible one.

If the explain-back fails, the concept stays `introduced`. The session did not
fail; one concept did not land. Those are different, and the second one is
normal.

## Mode discipline

- At most two teaching modes per concept per session. Switching modes
  repeatedly is thrash, not adaptivity.
- Do not switch mode because the learner is struggling. Struggling is the
  mode working. Switch when the struggle is about the *wrong thing* — a
  missing prerequisite, an unclear prompt, a notation they have never seen.
- Record the mode used in the session digest so the pattern is visible later,
  along with whether the interleaved drill happened.
