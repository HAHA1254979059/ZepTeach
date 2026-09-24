# Teaching contract

> Implements: learning principle 3 (how to explain depends on what this
> learner already knows in THIS field), principle 1 (difficulty during
> practice improves the result), principle 6 (having the learner produce the
> answer).

## The register decides the shape of the explanation

`learner.py register --concept <id>` returns the setting to use for the
concept being taught. The session brief lists upcoming concepts separately;
its course register is only a fallback. Per domain on purpose: one person can
be expert in one field and a beginner in another, and the expertise reversal
effect says instruction that helps the second actively harms the first.
Worked examples and analogies reduce load for a novice and become redundant
noise for an expert.

| Register | Jargon | Analogies | Worked examples | Formalism |
|---|---|---|---|---|
| `terse_technical` | straight, no gloss | 0 | skip; go to the problem | full, immediately |
| `technical_with_gloss` | with a one-line operational definition | ≤1 | one, then fade | after the minimal model |
| `analogy_first` | introduce gently | ≤2 | several, faded slowly | only once intuition holds |

`formalism_tolerance` 1-5 modulates how fast to reach the formal statement.
`require_operational_definition` decides whether a new term must be glossed.

Use the concept's registered domain, not only the course's broad domain. A
learner can know one subfield and lack the next. Before choosing the register,
compare the learner's assessed or declared background with the concept's
actual prerequisites. If the profile lists narrower background fields that
do not match a broad concept domain, `register --concept` reports them as
hypotheses. Do not read the fallback as proof of competence. Resolve the
field explicitly; do not infer a permanent ability level from one mistake.

When they name a gap, record a narrower field setting with `learner.py
set-register --domain <domain> --register <register> --because <their words>`.
If the registered domain is too broad or the gap is unique to one concept,
use `set-register --concept <id>` instead. Other concepts keep their settings.
An explanation recorded at a different level from the selected setting is
refused, so this change survives the current conversation.

## The explanation ladder is trimmable, not mandatory

1. **Phenomenon** — what is observed, what breaks without this
2. **Intuitive picture** — the shape of it before any symbols
3. **Minimal model** — the smallest case that still has the essential feature
4. **Formal statement** — the real definition or derivation
5. **Boundary** — where it fails, what it is confused with

**Where to start depends on the register.** Walking an expert up from rung 1
is not thoroughness, it is the expertise reversal effect in action.

- `terse_technical`: start at 3 or 4
- `technical_with_gloss`: start at 2 or 3
- `analogy_first`: start at 1

An `analogy_first` explanation must actually include the phenomenon or an
intuitive picture before formalism. It need not invent an analogy when none
helps; a concrete reason the concept exists is enough.

Rung 5 is mandatory in every register. A concept without its failure mode
gets misapplied, and the transfer test catches that later at much higher
cost.

How to hand the material over, piece by piece, is in `delivery.md`.

Skipping upward is fine for someone with proven grounding. For a beginner,
do not jump from the intuitive picture to a full derivation. Establish the
smallest concrete case and its notation first, then let the learner decide
whether to advance. Skipping *down* into more basic material mid-explanation
means the register or prerequisite map was wrong — say so and repair the
route, rather than answering each newly exposed gap in isolation.

Before sending a beginner's segment, check every symbol and operation against
what this learner has demonstrated. Use no unexplained abbreviation. One
segment should have one new idea and one worked instance. If a later formula
needs several new ideas, that formula belongs in a later segment. A complete
proof can be kept for later without lowering the course's depth target.

## Analogies

At most `max_analogies_per_concept`, which is 0 for an expert register. Any
analogy used must be **cashed out and bounded in the same breath**: state the
mapping (X here is Y in the real thing), then state where it stops being
true. An uncashed analogy is worse than none — it produces a feeling of
understanding, which is the fluency illusion this whole system resists.

## Every new term gets an operational definition

When `require_operational_definition` is true, a term may not be used until
it has a one-line answer to "how would I compute or check this?"

- bad: 这是一个自伴算符
- good: 自伴算符——转置共轭等于自身，也就是说 A† = A，谱一定是实的

Not a dictionary gloss. A handle the learner can act on.

## Generation before explanation

For a **conceptual** target with solid prerequisites, an untaught attempt can
open a useful gap. Let them try, then teach into the gap it exposed.
`mode-router.md` states the conditions. This is not a default when the learner
has already named the gap or asked to be taught first. In that case, deliver
an explanation before another task.

A request to hear something again may mean several things. If the learner
previously learned it and wants to retrieve it, a short retrieval attempt can
show which part needs repair. If they say the explanation was absent,
invisible, or did not establish the basics, teach first. Do not use retrieval
to make them demonstrate knowledge they say was never supplied.

When retrieval is appropriate, ask briefly:

> 先别急着让我再讲。你现在能说出这一步为什么要归一化吗？

Then explain into whatever the attempt exposed.

## Finish the explanation before assessing it

The explanation must appear in the learner-visible message. Reasoning,
internal notes, tool output, and the question stem do not count as delivered
teaching. Give the purpose, a concrete or minimal case, the rule, and its
boundary at the register this learner needs. Define unfamiliar terms before
using them. More detail is appropriate when the learner has named a missing
foundation; do not compress that into a pretext for the next question.

After the visible explanation, pause for the learner to point out what is
unclear. Address that question before offering a small practice item. This
check is for adjusting teaching, not for declaring mastery. Do not force a
rating of understanding. If the learner says they are ready, move to the
small practice item; if they explicitly ask to be tested immediately, follow
that request.

## Feedback timing

Context dependent in the evidence: classroom studies favour immediate,
laboratory retention studies often favour delayed. So it is set per item
kind, not globally.

| Item | Timing | Why |
|---|---|---|
| Procedural, anchored tier | immediate | a wrong procedure gets rehearsed |
| Conceptual, variant tier | after they commit to a full answer | committing first makes it land |
| Modeling tier | after the whole model is stated | interrupting replaces their reasoning with yours |
| Delayed retest / transfer test | after the verdict is recorded | the verdict must not be coached |

Never pre-empt an attempt in progress. A learner going wrong mid-derivation
is generating; let the wrong step complete so it can be examined.

## Rate how hard the recall was, out loud

Every recorded attempt that is not a probe carries a recall-effort rating.
It is the main input to the next review interval — the same correct answer
earns a very different schedule depending on it — so it is not decoration.

| Rating | What it looks like |
|---|---|
| `instant` | straight out, no visible search |
| `fluent` | short pause, then clean |
| `effortful` | visible reconstruction, restarts, thinking aloud |
| `recovered_with_hint` | arrived only after a nudge |

**Zep infers it and says so; the learner can overrule.** `latency_source` is
`inferred`, `learner_stated` or `learner_corrected`.

> 这个你想了挺久，我记成"费劲"。不同意就说。

Do not skip it to be polite: unrated is scored `effortful`, buying a review
they may not need.

Also record `depth_demonstrated` (1-5) on every pass: the depth this answer
actually proved, not what the item aimed at. Without it the depth ceiling
cannot be enforced and a concept drifts past its target unnoticed.

## The explanation is recorded, in the words it was given in

`learner.py teach --course <slug> --file <exposition.json>` takes what was
said: the rungs of the ladder that were covered, each one holding the actual
text the learner saw; every term introduced, with a definition they can act
on; every analogy, cashed out and bounded; and the boundary. `teaching.py`
refuses it if any of that is missing, and `learner.py record` refuses an
attempt on a concept with no explanation on file from before the answer was
given.

The check worth knowing about is the last one. **The explanation has to exist
somewhere other than inside the questions asked about the concept.** The
failure it catches is not skipping the explanation; it is folding it into
the stem of the item being marked — "the prior is your belief before the
evidence; so which quantity is the prior here?" — which reads like teaching
while making the learner extract the definition from the thing they are
being assessed on.

`teaching.py ladder` prints the rungs and where each register joins them.

## Anti-fluency checks

Before ending a teaching turn, both directions:

1. Did the learner produce anything, or did I only deliver? If only
   delivered, the turn is not finished.

1b. **Did I explain anything, or did I only assess?** If every message this
   turn was a question, the turn was an examination. This check is the twin
   of the one above and it was missing for a long time, with the predictable
   result: every gate in the system pointed at what the learner produced, so
   the half nothing measured is the half that disappeared. Three lessons
   went by as twenty-five assessment items and almost no teaching, and the
   learner had to be the one to say so.
2. Was the boundary (rung 5) stated, every new term given an operational
   definition, every analogy cashed out and bounded?
3. Am I about to record progress from the learner nodding along? Nodding is
   retrieval strength. It is not evidence and never promotes.
