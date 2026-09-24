# Handing the material over

> Implements: learning principle 4 (a limit on how many connections can be
> formed at once), learning principle 3 (how to explain depends on what this
> learner already knows in this field), learning principle 1 (difficulty
> during practice improves the result).

## Deliver it in pieces the learner asks for

**Do not send a lesson's worth of explanation in one message.** Deliver one
coherent idea, with enough purpose, definition and concrete detail to make
it understandable, then let the learner start the next piece. One piece can
take several paragraphs and a worked example. A single sentence followed by
a question is not a teaching segment merely because it is short.

The evidence is specific about the mechanism. Segments the learner advances
themselves, against the same material delivered continuously, was supported
in ten of ten tests with a median effect size of 0.79, and 0.98 in one set of
transfer tests. The benefit comes from **the learner controlling when the
next piece arrives**, not from the pieces being small. Chopping the output
finely and then sending every piece in one message implements the appearance
and none of the mechanism.

Each piece ends with something they can respond to:

- An invitation to point out the step or term that remains unclear. Use this
  after new or repaired teaching before scored practice. If nothing is
  unclear, continue to one small exercise.
- A short question about what was just said when the learner has already had
  enough explanation and is ready to try retrieval.
- Occasionally a choice of direction.

Do not treat "I follow" or "go on" as evidence of mastery. It controls the
pace, not the score.

When the learner is a beginner or has just reported a missing foundation,
the first piece starts from a familiar concrete case. Do not include the
abstract shortcut, every edge case and a full derivation in that same reply.
If they ask why a later step works, rebuild the chain from the last agreed
step; do not keep explaining one symbol at a time in the original proof.
Pausing between pieces is part of the explanation, not a delay before a test.

### How much is one piece

**One idea, cut where you could ask them something.** A starting rule, not a
finding: no study gives a segment size, the literature says it depends on the
content, the task and the learner, and warns that over-segmenting slows
comprehension. Finer than one idea is a known failure, not a safer default.

Their own behaviour settles it, visible during the session:

- They keep saying "go on" immediately → the pieces are too small. Enlarge.
- They answer the check-back wrongly or partially → too large. Reduce.
- They start answering a piece ahead → they know this already; check the
  register rather than the size.

### When to segment less

The effect is largest when the material is complex, the pace fast, and the
learner new to it — the same boundary as the expertise reversal effect. In a
field they work in, small pieces interrupt rather than help. Under
`terse_technical`, group several ideas per piece and let the closing question
carry more weight.

Low energy shrinks the pieces, not the questions. Tired means less at a time,
not less being asked.

## Decide how they answer, and write it on the item

Every item carries a `response` block saying how the answer arrives:
`free_text`, `choice`, `fill_blanks`, `numeric` or `upload`. An item without
one cannot be issued — `exercise.py` refuses it.

This is a field on the item rather than a decision in the moment because a
decision in the moment does not survive the next item. In the first real use
of this plugin the teacher built an interactive form, the learner said it was
much better, and about twenty minutes later the answers were back to being
typed into chat. Nobody decided that. Nothing remembered, and nothing could
refuse an item that ignored it. The learner had to notice and say so, twice.

**Response mode is not difficulty.** `form` says what the mind is doing;
`response` says what the hands are doing. Deriving a result can be answered
by typing the derivation or by filling in the steps that carry the point.
Choosing between candidate derivations may instead measure recognition, so
do not assume it proves the same thing. Pick the least burdensome input that
still shows the intended thinking. A learner who spends four minutes typing
subscripts has been measured on their patience.

**Notation gets its own channel.** `profile.notation_input` records how this
person supplies anything prose typing handles badly — formulas, structures,
diagrams, tables, non-Latin script. Options are typing it plainly, typing it
as markup, photographing work done on paper, or picking between candidates.
An item that needs typed notation from somebody who said they would
photograph it is refused, not discouraged.

This is why it is a field and not a line in the free-text constraints list:
`formulas must be LaTeX` reads perfectly clearly and gates nothing.

**Name the slots.** When an item has parts, give them `field_id`s. Then the
answer comes back as data, they can redo part three without retyping parts
one and two, and the next attempt at the same item is comparable to this one.
An answer that arrives as one paragraph has to be read by a person to be
used at all, which is how an assessment ends up living in the conversation
instead of in the records.

**How the item is shown follows `interaction-contract.md`.** Generate the
learner input request from its `response` block. If the host can show and
submit a conversation-inline view, use it. Otherwise present the same named
fields in the conversation. Never replace the intended evidence just to get
a convenient control.
