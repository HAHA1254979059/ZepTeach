# Interactive learning and its evidence

> Implements: learning principle 3 and principle 4 (teach from the learner's actual
> starting point, one manageable step), engineering principle 1, principle 4 and principle 9
> (real practice, durable evidence, fix the shared cause of feedback).

Use this route for a requested interactive experiment, lab or decision with
observable consequences. The learner's current request selects the activity;
a previous course's review queue does not replace it. Read the requested
material and preserve its source status before adapting one current part.
Assessment still uses the existing grading rules when actual assessment is
requested. An exploration is not a scored exercise merely because it has
buttons.

## Produce one usable step

In Codex, read the available `visualize` skill in full before authoring a
fragment. Its actual rendering reference, theme utilities and host bridge
take precedence over remembered examples. When the requested method needs
an inline experiment, a text-only fallback requires an actual host limitation
and an explanation of that limitation.

`interactive_lab.py build --root <data-root> --spec <step.json> --scene <scene.html> --fragment
<simulation.html> --script <simulation.js>` combines a subject-neutral
prediction/feedback shell with the teacher's current experiment. The
`interactive_step` schema defines the spec: exact learning thread ID,
interaction/lab/part IDs, title, question, prediction fields, and optional
confidence collection. Do not preload the correct choice. Keep solutions,
private QA and future parts outside the spec.

Write the simulation as literal fragment markup and a separate script body.
Write an answer-neutral scene separately. It is visible before the prediction
form; only experiment controls and results start locked. Show the real objects
or pending sample positions without revealing the answer. Use a short current
step title rather than repeating a course name in a large heading.

Prediction fields use one column, with the reason below them. In custom
layouts, mixed-height fields must be stacked or top-aligned; bottom alignment
moves the shorter field below the beginning of the longer one. Start with one
primary action and reveal secondary experiments afterwards. Keep the scene
and controls unframed unless a bounded surface materially helps the task.
Use host utilities unchanged. The builder rejects direct utility selectors
in authored scene/simulation styles; custom wrappers may control layout.

The script receives `root` and `lab`. Use `root.querySelector(...)` for its
controls and `lab.prediction` for the saved prediction. Bind each experiment
action to `lab.perform({id, label, parameters}, work)`. `work` computes the
experiment and returns `{observed_ui_behavior, values}` with a concise actual
result. Keep the recorded result a bounded summary, not thousands of raw
samples. The interface may display a larger sample separately.

For a discrete outcome scene, use `ZepTeachOutcome.mount(container, options)`
and `view.render({total, matchCount, visibleMatchIndices})`. The shared helper
is available in generated steps. `matchCount: null` means not sampled; zero
means an actual sample with no matching outcome. Never make a random sample
positive just to display a highlight. If only part of a population is shown,
the omitted group must show its own actual matching count. A legend example
must be labeled separately from real sample marks. The helper refuses totals
that cannot be reconciled with shown and omitted outcomes.

Check pending, zero, positive in the shown group, positive only in the omitted
group, mixed, all-positive, parameter reset and state restoration. Verify the
real mark's computed color and shape, not only a CSS class. Run
`interactive_lab.py verify-outcomes --artifact <absolute.html> --qa-report
<outcome-qa.json>` on the deterministic preview report in light/dark themes
at the two actual inner-frame widths. A random run without a match cannot
test whether the positive mark works. Test operations remain outside learner
records.

The shared shell requires a prediction and reason before unlocking the
experiment. A simulation action enables the observation field. The learner
can then request a teacher check of the current part. Neither that request,
file generation, nor feedback submission advances a question or lab. Check
the learner's actual answer and observation, discuss any gap, and obtain the
required confirmation before the next part or lab. Progress remains in the
course's own records and is written only from actual evidence.

If the teacher's check calls for another attempt on the same part, issue a
new `interaction_id` for that revised attempt. The earlier prediction and
confirmation stay in the journal; do not erase them or treat a reopened
part as completed.

The generated file path and final-response reference are printed together.
Include that real reference in the final response in the same turn. A
download link, screenshot, plan, or HTML filename is not the inline reference.

## Receive before recording

The host bridge sends `[ZepTeach interaction]` followed by a JSON packet.
It contains stable event IDs, UTC times, exact learning thread ID, lab/part,
actual inputs and observed controls/results. Confidence appears only when
the learner supplies it. A local draft, widget state update or resolved send
request is not proof that the assistant received the answer.

After receiving the actual message, save that exact message privately and
run:

```
python scripts/feedback.py --root <data-root> --thread-id <exact-id> ingest --message-file <received-message.txt>
```

This appends to `feedback/interactive-learning-feedback.jsonl`. Duplicate
event IDs with the same content are harmless retries. The same ID with
different content is refused. A locked or incomplete journal is refused;
do not remove the lock or trim history to get past it. No operation in this
script writes grades, mastery, completion or the next lab.

For a typed learner answer or a real relayed user report, create one
`feedback_event` from that actual text and its source, then use `append
--file <event.json>`. Do not label an assistant instruction, predicted answer,
browser test or missing user data as a learner event. Record only the
authorized learning feedback, not unrelated messages or profile data.

The inline buffer is bounded and best-effort. It keeps events until the
learning assistant acknowledges their disk receipt. When rebuilding the
same step, supply only actually ingested IDs in `acknowledged_event_ids` to
release those buffered events. Without a send bridge, the shell displays
the same packet for the learner to send in the conversation. A fallback
does not pretend that the packet was received.

## Verify delivery without claiming visibility

Keep these evidence levels distinct:

| Evidence | What it establishes |
|---|---|
| Existing readable file and hash | An artifact was produced |
| Browser QA in an isolated preview | Tested controls and layouts worked in that preview |
| Matching reference in the actual final response | That response requested inline display of this artifact |
| Learner's actual visibility report | What the learner says they saw |
| Received interaction packet appended to the journal | Those actual submitted events were recorded |

`interactive_lab.py check-delivery --artifact <absolute.html> --reply-file
<actual-final-response.txt>` checks the file and reference. It explicitly
leaves controls unconfirmed without `--qa-report`; user visibility remains
unconfirmed even with preview evidence. A proposed reply is only
a preflight check; use the actual reply afterwards to establish delivery
evidence.

Run the artifact in a browser preview with the host styles and sandbox.
At actual inner-frame widths 736 and 360, capture both the initial state and
the state after operations. Check the visible initial scene, field order,
one primary action, DOM overflow and frame cropping, then inspect the actual
screenshots for readability. Outer browser width alone is not that evidence.
Check prediction validation, locked/unlocked state,
the primary experiment's result, repeat actions, invalid input, keyboard
operation, and desktop and narrow widths. Test the host bridge with a local
mock that cannot message a task. Never append test clicks to the learner log.
Use a temporary working directory for the browser process and keep QA output
private. Browser QA supports a receipt, not a claim that the learner saw it.
Check effective visibility after each action, including intermediate states.
An element carrying `hidden` can still be painted if another CSS rule wins.
The shared shell preserves hidden-state semantics; a CSS class or attribute
alone is not evidence of a correctly displayed mark or concealed result.

Before emitting the inline reference, run `interactive_lab.py verify-qa
--artifact <absolute.html> --qa-report <browser-qa.json>`. It requires both
widths and phases, passing layout/interaction checks, matching file hashes
and existing screenshot hashes. Missing initial captures or a file changed
since inspection are refused. `check-delivery` can take the same `--qa-report`
to combine preview and actual-reference evidence. Keep each completed QA
report and its screenshots in a new private output directory; do not overwrite
evidence already cited by a receipt. These commands do not establish actual
client return or user acceptance.

Absent historical QA records mean the earlier acceptance process is unknown,
not proof that it was skipped. `pending` is an on-demand read; no automatic
listener or scheduled monitoring is enabled by this workflow.

## Desktop, mobile and unsupported clients

Responsive layout, successful script execution, host styles, host return,
and actual device acceptance are distinct. Never call a narrow desktop
preview a real mobile-app test. Do not branch on a device name; check the
capability needed. The shared runtime reports only script/style/return-method
availability, without collecting device identifiers. Its state-saving and
send callbacks do not establish conversation receipt.

Always keep the current question and named answer fields available in the
ordinary response, including on a client where the inline result is blank.
The builder prints `text_backup` and includes static question/field markup.
Without JavaScript, the primary action stays disabled. Missing host styles
select a visible message directing the learner to the ordinary conversation.
This fallback does not manufacture a submitted answer or run the next part.

`presentation.py --spec <step.json> --client-evidence <evidence.json>` selects
`conversation` after an actual learner report of an unusable display or a
missing execution/style capability. An isolated preview never establishes
actual device acceptance. Preserve the same prediction, reason and optional
confidence. After receiving them, run a real course adapter experiment and
return a readable result/table/image in the conversation. Do not replace the
experiment with invented results or substitute an easier assessment.

OpenAI's [Visualizations availability documentation](https://learn.chatgpt.com/docs/visualizations)
describes mobile rollout as account/app-version dependent. Availability is
not guaranteed by installing this method plugin. When actual mobile rendering
remains unknown or unusable, say so and use the tested conversational path;
do not change account or security settings or deploy a new service by default.
Test touch-browser preview, disabled JavaScript, missing host styles and
missing return separately. Only real device evidence can close mobile
acceptance.

## Read and handle authorized feedback incrementally

In a development task, use:

```
python scripts/feedback.py --root <authorized-data-root> --thread-id <exact-id> --receipts <private-receipts.jsonl> pending
```

Only unhandled events for that exact thread are returned. A read with no
events creates no journal. Receipt records are a separate append-only file,
so status changes cannot overwrite what the learner said. Each receipt
references the original event's content hash. Use `receipt --event-id <id>
--status <status> --note <result> --evidence <absolute-file>` after handling
it. `implemented_tested` needs a concrete QA file; `waiting_for_learner`
records that visibility or usability still needs actual user evidence.
Identical receipts are idempotent. New user reports create new events.

Trace each problem through selection, artifact generation, reference,
interaction receipt and logging before deciding the fix. Test the same
mechanism on a different interaction, not only the reported example. Keep
private feedback and receipts outside Git and distribution. This workflow
does not grant permission to message another task, deploy, publish, install
an updated plugin or change security settings.

For unavailable official assessment questions, preserve their unavailable
status. An original adaptation must visibly say
`按官方大纲原创练习（非官方原题）`. Do not obtain leaked question banks or
submit a platform's graded coursework on the learner's behalf.
