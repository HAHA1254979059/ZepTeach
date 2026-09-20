# Notes

> Implements: learning principles 1 and 2 (notes hold durable knowledge, not
> a record of what was discussed), engineering principle 4 (state on disk).

Two layers, and the whole value is in keeping them apart.

| Layer | Holds | Written how | Read when |
|---|---|---|---|
| **Canonical** `notes/concepts/<id>.md` | what is true about one concept | rewritten in place | months later, to use the thing |
| **Journal** `notes/journal/<date>.md` | what happened in a session | appended | rarely, to reconstruct a thread |

A note becomes useless the moment it turns into a log. "2026-09-19 asked
whether this can ever be negative" is meaningless in March: it records that a
conversation happened, not what is now known. The answer behind the question
is what has to survive.

## The rule that stops a note becoming a record of conversations

**A question asked in conversation goes to the journal by default.**

It is promoted into the canonical note only if it changed what is true about
the concept — and then it is rewritten as a statement of knowledge, with the
question gone.

- journal: 问了特征值能不能是复数
- canonical, under 边界与常见误区: 实矩阵的特征值不一定是实的；只有对称（自伴）矩阵才保证实谱。旋转矩阵是最短的反例。

If the promotion cannot be written as a standalone knowledge statement, it did
not belong in the canonical note.

## Canonical note structure

Six required sections. `notes.py` refuses to write anything missing one.

1. **定义** — what it is, operationally. How would you compute or check it?
2. **为什么需要** — what breaks without it. The problem it was invented for.
3. **机理** — why it works. The actual mechanism, not a restatement.
4. **边界与常见误区** — where it fails, what it gets confused with. This
   section is mandatory and is the one that decays first if not enforced.
5. **与相邻概念的关系** — `[[wiki links]]` to neighbouring concepts, each with
   one line saying what the relationship is. A bare link is not a relation.
6. **例题指针** — pointers to worked items, by exercise id, not copies.

Frontmatter carries `concept_id`, `course_id`, `depth_target`, `sections`,
`links`, `source_refs`, `updated`, `rewrite_count`.

## Rewrite, never append

The canonical note is the current best statement, not a history. When
understanding changes, the note changes — the old wording goes.

This feels lossy and is not: the history lives in `attempts.jsonl` and the
journal. What the canonical layer owes the reader is a clean statement they
can act on without archaeology.

`rewrite_count` going up is a health signal, not churn. A note rewritten four
times as understanding deepened is working correctly.

## Depth governs how much goes in

A concept at `depth_target` 1 (can-use) gets a short note: definition,
why-needed, boundary, links. The mechanism section can be one line.

A concept at 4 (can-critique) needs the mechanism in full and a boundary
section that names the live disagreements.

Writing a depth-4 note for a depth-1 concept is the same rabbit hole the depth
target exists to prevent.

## Links build the concept map

Because concepts are global and namespaced, links cross courses, and the
useful ones cross fields. When a second course reaches a concept the first
course already taught, the note gains a link in the other direction. That
cross-link is not decoration — it is the recorded trace of a transfer, and
the review system can use it.

Link liberally. A link to a concept that does not have a note yet is fine; it
marks something worth writing.

## What never goes in a canonical note

- 用户问了…… / 我们讨论了…… — any narration of the session
- praise, encouragement, meta-commentary about the learning process
- the full text of an exercise (point at its id)
- anything that would read as a diary entry to someone who was not there

## Journal

Free-form, one file per day, appended. Session digests, questions that did not
change anything, dead ends worth remembering, things to look up.

The journal is allowed to be messy. That is what it is for — it absorbs the
mess so the canonical layer stays clean.
