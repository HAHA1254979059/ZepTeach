# Learner input in the conversation

> Implements: learning principle 8 (difficulty belongs in the material, not
> in reaching it), engineering principle 8 (portable without hidden
> requirements), engineering principle 9 (fix the shared cause of feedback).

Every question asking the learner to choose, calculate, explain, fill a slot,
or report their condition has an answer shape before it is shown. This applies
to setup, session energy, prerequisite probes, lessons, exercises, reviews,
side branches, and course changes. The answer shape is separate from what the
answer proves. A convenient control cannot replace an explanation with a
guess or turn a derivation into recognition without changing the assessment.

## One request, several hosts

Use `interaction.py energy` for the session condition. Use
`interaction.py exercise --file <item.json>` for an issued item. For a probe
or another question, write a small request with `request_id`, `prompt`, and
the same `response` shape as an exercise, then run
`interaction.py request --file <request.json>`. These commands print an
absolute inline view path and a text fallback. They write only a view under
the permitted learner data root. The exercise conversion exposes the prompt
and input labels but never the grader, expected answer, or reasons an option
is wrong.

For a multi-part probe, the request can be as small as:

```json
{
  "request_id": "probe-one",
  "prompt": "Answer each part without looking at notes.",
  "response": {
    "mode": "fill_blanks",
    "fields": [
      {"field_id": "part_one", "label": "First part"},
      {"field_id": "part_two", "label": "Second part"}
    ]
  }
}
```

When the host supports a conversation-inline input view, show that view with
native controls and a visible submit action. The view belongs in the message
flow. Do not use floating choices over the composer or controls that cover
the lesson. The learner can select or enter with a mouse or keyboard. A
multi-part question has separate labeled fields; do not ask the learner to
retype earlier parts to correct one answer.

In Codex, when local inline visualizations are available, include the view
in the final message using the host's visualization content reference with
the absolute path printed by `interaction.py`:

```text
visualize{"path":"<absolute-path-to-generated-html>"}
```

The view sends the selected or entered values back as a new learner message.
Read `request_id` and `values`
from that message before interpreting or recording an answer. A selection
in widget state alone is not a submitted answer. If the view cannot submit,
use the printed text fallback in the conversation.

In Claude Code, use a conversation-inline input tool only when that host
offers one with the required controls. Keep the same request and answer
fields. If it cannot render or submit such a view, present the printed text
fallback in the message. Do not claim that a file or a floating prompt is
inline interaction.

For an `upload` response, use the host's normal attachment path. The inline
view generator deliberately does not pretend a local file input can deliver
a photograph to the model. Keep the item in `upload` mode and explain how to
attach it in that host.

## Keep the teaching decision intact

- Offer short choices for condition and preference questions when the options
  cover ordinary answers. Always accept a learner's own words as a correction.
- Use numeric fields for numbers and separate fields for a multi-part probe.
- Use free text for an explanation that must be produced unaided. Do not turn
  it into a choice solely to save typing.
- Select an answer channel the learner can use. If notation is hard to type,
  offer a faithful alternative or ask for a photograph. If no alternative
  preserves the evidence needed, state the tradeoff before changing the item.
- Submit and record the learner's actual answer. An unsubmitted draft is not
  an attempt and cannot move mastery.

The input request is a presentation contract. It does not grade, teach, or
advance a concept. Those decisions remain with the existing exercise,
teaching, and evidence checks.
