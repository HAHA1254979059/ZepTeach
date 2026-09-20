# Setting exercises

> Implements: learning principle 1 (difficulty during practice improves the
> result), learning principle 5 (practising topics mixed together), learning
> principle 7 (applying knowledge in a new setting does not happen
> automatically), engineering principle 1 (practice must act on something
> real).

`exercise.py` refuses the cases below. This file says what to do instead.

## Three tiers, and where difficulty comes from

Every lesson owes all three. Missing one is not a shorter lesson, it is a
different and weaker one.

**Anchored.** A real problem somebody else set, taken from a source and cited
precisely enough to find again. Its difficulty comes from outside this system
entirely.

This is the tier that keeps the other two honest. A system that invents all
its own problems calibrates difficulty against what it expects the learner to
manage, and that expectation drifts downwards without anyone deciding to
lower it. An external problem does not move.

Every field has a source of these. Published problem sets. The derivations in
an original paper. A documented specification. A public assignment. A
standard passage set. Review essays that disagree with each other. If the
adapter records none, that is a gap in the adapter, not a property of the
field.

`anchor_kind` and `source_ref` are required and the script refuses without
them. An anchored item whose source cannot be named is an item this system
invented and then called hard.

**Variant.** The anchored item with conditions changed, parameters altered,
or the question reversed. Still mechanically checkable. Its difficulty is
inherited from the item it came from.

Reversing is usually the most useful change: give the result and ask what
conditions produce it. It tests the same knowledge in a direction rote
practice does not cover.

**Modeling.** A real situation the learner has to set up themselves: decide
what matters, choose an approach, state what they are assuming, say what
would make the answer wrong. Marked by rubric, which the script requires.

The situation must be real rather than tidied. That is what stretches the
academic-versus-real dimension in Principle 7, and it is the dimension most
often skipped, because a tidied situation is much easier to write and reads
almost the same.

## Mixed practice

Not optional. The evidence: same problems, same spacing, mixing topics scores
worse during practice and doubles the score on a test the next day. The
benefit is located precisely: mixed practice is the only arrangement where
the learner has to work out which method a problem calls for.

`exercise.py drill` composes a set. Three ways a set that looks mixed is not,
each refused:

**One concept.** The item itself announces which method applies.

**The wording names the method.** "Use the characteristic polynomial to..."
hands over the exact choice being practised. Describe the situation and stop.
Marked with `reveals_method`, and such items are excluded from composed sets.

**Drawn from a single lesson.** Within one lesson the learner knows what is
in play whatever the item says. Mixed sets draw across lessons, and
`mixed_from` records which.

A fourth failure is invisible item by item and appears only in the assembled
set: consecutive items sharing a concept. The learner works out the method
once and coasts through the rest of the run. `is_really_mixed` checks the
whole set for this; the composer alternates rather than groups.

**Say it will feel worse before starting.** Performance during mixed practice
genuinely drops. A learner who is not told reads that as going backwards, and
the reasonable response to going backwards is to stop doing the thing that
caused it. One sentence prevents that:

> 这组是混着来的，会比刚才难，当场做得差是正常的。隔一天再测会比分开练高。

## Transfer tests

A transfer test must state which of the six context dimensions it moves
along: knowledge domain, physical context, temporal context, functional
context, social context, modality. `transfer_dimensions` is required and
checked.

The requirement exists because "test it in a new context" cannot be checked
afterwards, and in practice becomes changing the surface of the question
while its structure stays put.

**Naming only knowledge domain is the weak case** and produces a warning. It
is what the previous criterion already did: an open-ended item, or one
spanning two concepts. The setting, the form and the stakes are unchanged.

Ways to move along the others, in any subject:

| Dimension | What changes |
|---|---|
| Physical context | worked on paper instead of in the tool, or in the field instead of at a desk |
| Temporal context | long enough afterwards that the lesson is no longer being recalled as an episode |
| Functional context | a real situation with real stakes instead of an exercise |
| Social context | explaining it to someone, or defending it against disagreement, instead of answering alone |
| Modality | saying it instead of writing it, drawing it instead of stating it, reading someone else's version instead of producing one |

Moving along two dimensions at once is a stronger test than either alone, and
harder. Use one for a first transfer test and two once the concept has held.

## Explain-back

Every lesson owes one per concept taught. `owed_explain_backs` lists what is
outstanding; nothing lets the lesson close while the list is non-empty.

It has no tier: it is not from a source, not a variant, and not an open-ended
task. The exercise id is fixed as `explain-back:<concept_id>` so that reusing
the same one later as a delayed retest is caught rather than passing
unnoticed.

The prompt asks for three things, and the third is the one that gets skipped:

1. What it is.
2. Why it is needed.
3. Where it stops working.

Nodding is not an explain-back. Neither is repeating the definition back.
What is being tested is whether they can produce it unaided, which is the
generation effect and the strongest single thing available here.

## Degraded forms

When the reach check says practice cannot act on the real thing, the
substitute is already written down in the adapter, with what it loses. Use
it. Do not improvise a replacement during the lesson: mid-lesson the cheapest
move is always the easier item, and the substitute that gets invented under
time pressure is reliably weaker than the one written in advance.

If the substitute's depth ceiling is below the concept's target, that is a
gate failure, not a judgement call. Either obtain what is missing or lower
the target and record it.

## What is never set

- An item with no stated way of marking it. Decided afterwards, marking is
  shaped by the answer.
- An anchored item with no citable source.
- A mixed set that is not mixed.
- A transfer test that does not say what it moved.
- An item deeper than the concept's depth target on the main line. That is
  what a side branch or an explicit raise is for.
