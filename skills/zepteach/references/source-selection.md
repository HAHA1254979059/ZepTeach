# Choosing a teaching source

> Implements: engineering principle 1 (practice acts on real material),
> engineering principle 6 (neither subject nor environment is hard-coded),
> engineering principle 9 (feedback changes the shared rule).

The learner's goal determines what must be taught. A reliable source anchors
the explanation and its notation; the model still has to understand it and
teach it clearly. Do this at course setup and revisit it when a new topic or
an apparent contradiction falls outside the chosen material.

1. Check material the learner has already supplied. If none is suitable,
   find an author, publisher, university course, official tutorial, or
   primary reference that covers the needed depth. Compare authority,
   accuracy, level, coverage, update date where relevant, and whether the
   learner can actually access and navigate it. Propose a primary source and
   explain why it fits this course; leave the choice with the learner when
   their preference or access matters.
2. Register the selected edition or version in `resources.json` and
   `sources/index.json`. Map the curriculum to sections, pages, headings or
   timecodes. A source that cannot be located at the point being taught is
   background reading, not an anchor for that explanation.
3. Before teaching a mapped concept, open its actual span and verify the
   definition, notation, assumptions and worked result. `sources.py plan`
   shows whether the course has an indexed source and mapped spans;
   `source-anchoring.md` governs citable spans. If the source lacks a point,
   find a supplementary source and name the distinction.
4. If an explanation is challenged or two conventions differ, pause scoring.
   Reopen the source, check the exact claim and its assumptions, then correct
   the visible teaching and any stored note. Do not defend an uncited memory
   of the topic as though it were the course's source.

Material may need a reader, text extraction, transcription, search, or another
capability before its spans are usable. Identify the specific teaching task
first, check the tools already available, then look for a suitable built-in
ability, installed plugin, MCP server or skill. Recommend the smallest useful
addition with its learning benefit, cost and limitations. Do not install or
connect it without the learner's authorization. A source that cannot be read
reliably must be reported as such; do not fabricate citations.

This policy does not force one textbook onto every course. It requires a
reasoned source choice when possible, and an honest unanchored label when it
is not. The course should not stall merely because a preferred source is
unavailable, unless the learner's goal names that exact material.
