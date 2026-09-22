# ZepTeach design philosophy

This document is the foundation. Every doctrine file, every refusal built into
a script, and every adjustable number either traces back to a principle stated
here, or has not been thought through.

Why it exists. The earlier design was a list of fixes for specific things that
went wrong when using web-based AI for tutoring: sixteen complaints, sixteen
mechanisms. Designing that way has two problems. It only addresses failures
that have already been noticed, so anything not yet encountered stays
unaddressed. And separately written fixes can contradict each other without
anyone noticing, because there is no single statement of intent to check them
against.

## 0. Three inputs

The design draws on three sources. All three are needed, and each one can
settle a different kind of question.

| Source | What it can settle | What it cannot |
|---|---|---|
| **Research on learning and cognition** | How people remember, forget, and misjudge their own understanding. How long to wait before retesting, what counts as evidence of learning, where difficulty should be placed | How many turns one session should run for, where state should be stored, how to behave consistently across different models |
| **Engineering experience** | What is achievable, what it costs, how to avoid breaking, how to stay portable and inspectable | What is worth doing, and what counts as having learned something |
| **User feedback** | Where it actually hurts in use. It reports **symptoms**, not requirements | What is causing the symptom, or what would fix it |

When two sources disagree, the order is: **research decides the goal,
engineering decides the method, feedback decides what to build first.**
Research establishes that the first retest must come after a delay.
Engineering decides whether that schedule is stored in a JSON-lines file or a
database. Feedback decides whether the review system or the exercise system
gets built first.

This ordering does not work in reverse. A request for a feature is not by
itself a reason to build it: the study methods people pick for themselves are
the least effective ones (see Fact 3 below). And the fact that something can
be built is not a reason to build it either.

The sixteen complaints belong to the third source. They divide into three
groups:

- Some are **learning-science problems** — marking that is too lenient, notes
  that turn into a diary of what was discussed, lessons that keep going deeper
  than intended. The causes of these are in the principles below.
- Some are **limits of what a web chat can do** — exercises that can only be
  discussed rather than performed, no access to tools, no ability to start
  anything on its own. These follow from a web chat being unable to run
  programs, unable to keep files between sessions, and unable to start a
  separate process with its own context. The decision to build a local plugin
  is what addresses them, and they have nothing to do with how memory works.
- Some are **both** — the cost of a long session is partly a question of how
  much text is being carried, and partly a question of how much new material a
  person can connect in one sitting.

Treating a limitation of the previous tool as if it were a fact about learning
would attribute it to the wrong cause and produce the wrong fix. That is why
this document has two sets of principles: eight about how people learn, nine
about how this is built.

**The sixteen complaints are not a complete list, and addressing all of them
would not make this system good.** They are the problems that happened to be
noticed. One purpose of this document is to find the problems nobody reported
but the principles predict. Doing that turned up three: practising topics
mixed together, having the learner produce answers rather than receive them,
and how transfer to new situations is tested.

---

## 1. Three findings that contradict intuition

### Fact 1: learning something and being able to recall it are different, and often move in opposite directions

Bjork and Bjork's New Theory of Disuse describes memory using two separate
quantities:

- **Retrieval strength** — whether it can be brought to mind right now. This
  rises and falls sharply with recent use and with time.
- **Storage strength** — how thoroughly it is learned and how many other things
  it connects to. This only ever increases.

The finding that matters: **when someone successfully recalls something, the
harder that recall was, the more storage strength increases.** Recall that
takes effort builds durable knowledge. Recall that is immediate builds almost
none.

The consequence is uncomfortable. **Any arrangement that makes a lesson feel
smooth at the time may be reducing what is retained afterwards.** How
comfortable studying feels and how much is retained are close to opposite
measures. A system that optimises for the first will produce a learner who
retains little, and neither the learner nor the system will notice while it is
happening, because the experience will be pleasant throughout.

### Fact 2: people cannot tell whether they have learned something

Koriat and Bjork call this the illusion of competence: when material reads
easily, people conclude they understand it. What is actually happening is that
**retrieval strength is being mistaken for storage strength**. Retrieval
strength is at its highest immediately after something has been explained,
which is exactly when learners are asked how well they understood it. So
self-assessment taken at the end of a lesson is reliably too high.

Consequence: **a learner's own assessment cannot be used to decide whether to
move on. Nor can the teacher's impression during the lesson.** Both are reading
retrieval strength. The only measurement that reflects storage strength is an
independent attempt at recall after a delay.

### Fact 3: which study methods work was settled years ago, and the answer contradicts what people choose

Dunlosky and colleagues (2013) rated ten common study techniques by how well
the evidence supports them. Only two rated high: **testing yourself** and
**spreading practice out over time**. Rereading, highlighting, summarising and
keyword mnemonics all rated low.

The techniques people choose without guidance are the low-rated ones, because
those are the ones that feel fluent while doing them — which is Fact 1 again.

Consequence: **when in doubt, the system should test and should space, not
explain again.** A request for another explanation is information about what is
happening, and needs a response, but granting it directly is usually the wrong
response.

---

## 2. Eight principles about learning

Each one gives the principle, the evidence behind it, what it becomes in the
plugin, and which of the original complaints it happens to address.

### Principle 1 — Difficulty during practice improves the result

**Evidence**: Bjork's work on desirable difficulties. Spacing practice out,
mixing topics, recalling rather than rereading, generating answers before being
told, and varying the conditions of practice all lower performance measured
during practice and raise it when measured later.

**What it becomes**:

- Review intervals are set by how much effort the recall took, not only by
  whether the answer was right. Items recalled with effort come back sooner,
  but the effort is not treated as a failure.
- A retest that needed a hint does not advance the concept's state. The hint
  supplied the part that was supposed to be retrieved, so the retrieval that
  would have strengthened the memory did not happen.
- Answering correctly during the lesson advances nothing on its own. That is
  the moment when retrieval strength is highest, so a correct answer then says
  very little about whether the knowledge will still be there next week.

**Also addresses**: complaint 13 (marking too lenient), complaint 15 (treating
"explain it clearly" as "make it as easy as possible").

### Principle 2 — Only evidence that is delayed and independent counts

**Evidence**: Fact 2, plus the testing effect. Establishing that something was
learned requires a gap in time, a change in how the question is asked, and
someone judging who did not watch it being taught.

**What it becomes**:

- Five states of mastery. Moving up accepts only three kinds of evidence: a
  retest after a delay, a test in an unfamiliar setting, or a stage assessment.
  Practice done during the lesson reaches the state called "practiced" and goes
  no further.
- Marking something as passed requires quoting the specific sentence in the
  learner's answer that earned the pass. If no such sentence can be quoted, it
  did not pass.
- Marking runs in a separate process that is given the question, the criteria
  and the answer, and is not given the lesson transcript. It is also not
  presented as Zep, so it has no relationship with the learner to protect.
- Progress reports are calculated from recorded answers only. No one's
  impression of how it went is used as input.

**Also addresses**: complaint 5 (never starts a review on its own), complaint
13 (feedback is always positive).

### Principle 3 — How to explain something depends on how much the learner already knows in that particular field

**Evidence**: the expertise reversal effect (Kalyuga and Sweller). Techniques
that help beginners a great deal — fully worked examples, steps broken down,
analogies — stop helping and start hurting once the learner has some grounding.
For someone with grounding, that material is information they do not need, and
processing it uses up the attention they would otherwise spend on the actual
content.

This is the real reason the language setting is stored per field rather than
once per person. It is not about accommodating a preference. It is that **the
same person needs structurally different explanations in different fields.** In
a field they know well, terminology should be used directly with no analogy. In
a field new to them, intuition should be built before formalism. Choosing
wrongly produces either an explanation full of things they already know, or one
they cannot follow at all.

**What it becomes**:

- Language settings are stored per field. The most specific match applies, and
  a subfield inherits from its parent field when it has no setting of its own.
- Each setting fixes three things: the maximum number of analogies allowed per
  concept, whether every new term must come with a statement of how to compute
  or check it, and how much formal notation is acceptable.
- The summary printed at the start of a session states which setting applies
  before anything else.

**Also addresses**: complaint 3 (misjudges what the learner already knows),
complaint 15 (explanations land badly), complaint 16 (no method for subjects
outside the sciences).

### Principle 4 — There is a limit to how many new connections can be formed at once

**Evidence**: Cowan (2001) — working memory holds roughly four items at a time,
with a range across individuals of about two to six. Understanding is built by
connecting new material to what is already known, and that connecting happens
in working memory.

**What it becomes**:

- A limit on how many new concepts one session introduces, three by default,
  adjustable by declared energy and by person.
- A limit on how much transcript accumulates before the session is required to
  write a summary and discard the original text. This controls cost, and it
  also prevents one session from accumulating more unprocessed material than
  can be connected to anything.

**Also addresses**: complaint 4 (cost), complaint 14 (sessions that run too
long).

### Principle 5 — Practising several topics mixed together is harder than practising one at a time, and produces better results

**Evidence**: Rohrer and Taylor. With the same number of problems and the same
spacing, mixing topics produces worse performance during the practice session
and **twice the score on a test given the following day**. Examining the errors
shows where the benefit comes from: mixed practice is the only arrangement that
requires choosing which method a problem calls for. When all the problems in a
set use the same method, the learner is told which method to use by the
structure of the set itself, so choosing is never practised.

**What it became**: `exercise.py drill` assembles a set across concepts and
lessons, alternates concepts rather than grouping them, and excludes prompts
that reveal the method. `is_really_mixed` checks the completed set because a
sequence can be blocked practice even when every item looks acceptable alone.
Once two concepts are practised, the session rules require an interleaved
drill rather than offering one as an option.

### Principle 6 — Having the learner produce the answer beats explaining it to them

**Evidence**: the self-explanation effect (Chi) — students who spontaneously
explain material to themselves while studying score more than twice as high on
later tests as students who do not. The generation effect more broadly. And
productive failure (Kapur) — **letting learners attempt a problem before it has
been taught, allowing them to fail at it, and only then teaching it** produces
better conceptual understanding than teaching first, and does not reduce their
ability to carry out the procedure.

**What it became**:

- For conceptual material with solid prerequisites, an untaught attempt can
  be useful when the learner agrees to try it and the explanation follows.
  When the learner names a missing foundation or asks to be taught first,
  deliver that explanation before another test.
- Every lesson ends with the learner restating the material without help, and
  `curriculum.py advance` refuses to move on while an explain-back is owed.

### Principle 7 — Applying knowledge in a new setting does not happen automatically

**Evidence**: Barnett and Ceci's framework for transfer. Whether knowledge
learned in one setting can be used in another depends on how far apart the two
settings are along six dimensions: the field of knowledge, the physical
setting, the time between them, whether the setting is academic or real, the
social setting, and the form the material takes. Where two situations look
similar but work differently underneath, transfer frequently fails.

**What it becomes**:

- A test of transfer states which of the six dimensions it stretched, rather
  than being described only as taking place in a new setting.
- Open-ended items must be set in real situations, which is what stretches the
  academic-versus-real dimension.
- Keeping concepts globally unique and shared between courses creates
  opportunities to stretch the field-of-knowledge dimension: a concept first
  taught in one course has to be recognised again in another, and the effect is
  largest when the two courses are in different fields.

**Also addresses**: complaint 7 (everything stays theoretical), complaint 12
(the upper end of the depth scale — being able to evaluate or create something
is the ability to apply knowledge in a new setting).

### Principle 8 — Courses fail because the learner stops, not because the learner forgets

**Evidence**: reviewing an item later than scheduled costs about one percentage
point of retention. Meanwhile the recognised main failure mode of spaced
repetition systems is a different one: overdue items accumulate, the queue
becomes large enough to be discouraging, and the learner stops opening the
system at all.

This conflicts with Principle 1 and the conflict has to be settled explicitly.
Principle 1 says difficulty produces better learning. This one says that past a
point, difficulty causes people to quit. **The line between them is that
difficulty belongs in the material, not in the process of getting to the
material.** The problems may be hard. The list of things waiting may not be so
long that it discourages starting. Recall may take effort. Opening the system
may not.

**What it becomes**:

- Overdue review work is classified into three levels of severity. One session
  takes on one session's worth. At the most severe level, new material stops
  entirely and the system says so rather than quietly continuing.
- Declared low energy reduces the size of everything, including how much Zep
  jokes around.
- Detecting fatigue produces "that is enough for today", never "you have not
  understood this".
- Overdue work is never silently rescheduled to make the queue look shorter.
  Doing that would remove the discouragement and also remove the information
  that the learner is behind.

**Also addresses**: complaint 14 (workload), complaint 6 (keeping the plan
moving without applying pressure).

---

## 2b. Nine principles about how this is built

The learning principles say what should happen. This section says what makes
those things achievable, and what must not break while doing them. These are
not drawn from research. They are the conditions for this being something that
works in practice. The entire argument for building a plugin rather than
continuing to use a web chat is here.

### Engineering 1 — Practice must act on something real, rather than stopping at describing it

**The principle**: a teaching system has to let the learner act on the actual
object its subject is about, not only describe that object. A web chat can
only discuss. A local tool can act.

This is why the plugin exists. It is also the only way to satisfy the
academic-versus-real dimension in Principle 7: **practising on real problems
requires actually working with real things.** Without that, open-ended work
never leaves paper.

**What that real object is depends on the subject, and the core of the plugin
does not know and must not know**:

| Subject | What practice acts on |
|---|---|
| Computational chemistry | a calculation that actually runs |
| Literature | the text itself |
| History | the original documents |
| Mathematics | the learner's own paper — **nothing external at all** |
| Languages | authentic material, or someone to speak with |

**What it becomes**: exercises carry criteria that can be checked by running
something; a check performed at course setup decides which kinds of practice
can be carried out for real; anything that cannot be is replaced according to a
ladder decided in advance rather than improvised during a lesson.

### Engineering 2 — Requirements that must not be violated belong in code, not in instructions

Anything that must not go wrong is written as a script that refuses, returning
a specific exit code. Only the teaching itself is left to the model's
judgement.

There are two reasons. The first is behaving the same across models: how
closely a model follows written instructions varies between models and between
versions, while a script that exits with code 2 does not vary. The second is
that a model can be argued out of an instruction, including by itself. A model
reasoning about whether an answer was good enough can construct a case for
accepting it. It cannot construct a case that changes what a validator does.

**What it becomes**: passing requires citing evidence; advancing a concept's
mastery state requires two separate pieces of delayed evidence; a lesson cannot
go deeper than the concept's stated depth; an exercise with no criteria for
marking it cannot be issued. All of these are refusals performed by code, not
reminders written in prose.

### Engineering 3 — Loaded context costs money and reduces accuracy

Every additional document loaded costs tokens, and also makes the instructions
that matter for the current task a smaller fraction of what the model is
reading. So the default is not to load everything available, but to **select
what to load based on what is about to be done.**

**What it becomes**: `SKILL.md` contains only a table mapping intentions to
files. Teaching loads five files, marking loads one, checking progress loads
none. Loading is conditional, so a course with no registered reading material
never loads the doctrine about citing reading material. Scripts print short
summaries rather than the contents of files.

### Engineering 4 — State is written to disk, and the session can be thrown away

A session ends and its contents are gone. Learning continues across sessions.
So everything that has to survive between sessions is written to disk, and the
session itself should be discardable at any moment without losing anything.

This also serves Principle 2: there is no such thing as delayed evidence
without something that persists between the lesson and the delayed test.

**What it becomes**: the learner profile, the mastery states, every recorded
answer, and the review queue are all files. When the turn limit is reached the
session must write a summary, and after that the transcript can be discarded.

### Engineering 5 — Running something in a separate process with different context is a capability, not an overhead

A separate process can be given a different set of inputs. This is not
primarily a way to save tokens. It is what makes strict marking possible: the
process doing the marking is not given the lesson transcript, so it does not
know which learner produced the answer, has no rapport with them, and has no
basis for lowering the standard out of sympathy.

**What it becomes**: three separate processes — one for marking, one for
filling a gap in background knowledge without interrupting the lesson, and one
for designing a course. Each is given only the inputs it needs.

### Engineering 6 — Do not write the environment into the code, and do not write the subject into it either

The plugin does not know which machine it will be copied onto, **and it does
not know what it will be used to study**. Code written on the assumption that a
particular program is installed will fail on a machine where it is not. Code
written on the assumption that the subject is a particular one will produce
wrong behaviour for every other subject. These are the same mistake in two
forms, and both are hard to notice, because the code works correctly for
whoever wrote it.

**It follows that adapters are generated rather than shipped.** The core
carries only the specification for an adapter — a schema describing what one
must declare, plus instructions for producing one. The adapter for a particular
field is generated when a course is set up, using the learner's goal and what
was found to be available. It is stored with the learner's data, not in this
repository. The reasoning is the same as for not assuming which programs are
installed: the plugin does not know what the learner wants to study, so it
should not arrive carrying a list of subjects.

From this it follows that any list of subject names in the core is a defect,
including a list of permitted values in a schema. A course's adapter field must
not be a fixed list of field names, and the list of exercise forms must not mix
one discipline's activities with another's. **The core names what the learner's
mind is doing — recalling, deriving, applying, constructing, analysing,
evaluating, explaining back — and never what their hands are doing.** What the
hands do belongs to the adapter, which maps its own field's activities onto
those seven.

**What it becomes**: the setup check writes a file recording what practice can
act on; each kind of practice resolves to one of doable, replaced at a stated
level, or not possible; replacements are **written down in advance**, not
decided during a lesson; shortfalls produce specific suggestions for what to
obtain, and nothing is ever installed automatically. The set of example courses
used for testing contains one science course and one humanities course, so that
code assuming a subject fails during testing rather than in front of a learner.
Neutrality is held by the tests, not by the author remembering to check.

### Engineering 7 — Failures must be visible, recoverable, and leave a record

Learning takes place over months, and something will break partway through. It
has to be possible to continue afterwards, and to see what went wrong.

**What it becomes**: a fixed set of exit codes — 0 for success, 2 for invalid
data, 3 for a precondition not met, 4 for exceeding a limit, 5 for something
not found — where a non-zero code is a refusal rather than a suggestion. Files
are written in a way that cannot leave a half-written file behind. There is a
command that checks every file in the data directory at once. Overriding a
refusal requires recording a reason, and the number of overrides is counted.

### Engineering 8 — Portable, inspectable, and with no hidden requirements

The schema validator is written as part of this project and uses no
third-party library, so the plugin behaves identically on any machine that has
Python. Plugin code and learner data are kept in separate directories.
Configuration stores the name of an environment variable holding a key, never
the key itself. Whatever a course works with is recorded per course, in the
learner's own terms, together with the directories they permitted; any path
outside that list is refused, wherever the work runs.

**What it becomes**: no installation step beyond copying the directory; the
data directory can be moved by setting `ZEPTEACH_ROOT`; every adjustable number
records where its value came from; a test that fails if a subject name appears
anywhere in the files that ship.

Optional in-conversation controls may need a host display capability or an
online formula renderer. Their absence must leave the question readable and
answerable in text, rather than becoming a hidden condition for learning.

### Engineering 9 — Feedback must change the rule that produced the failure

User feedback describes what happened to one learner. Before changing the
plugin, trace that event through the whole teaching flow: what the learner
needed, which instruction the assistant read, which data was written, and
which check would have refused the bad outcome. Look for other moments that
use the same missing decision. A fix is complete when those moments share a
clear rule and a realistic check, rather than when the reported example alone
works.

This does not make every preference universal. Preserve the learner's choice
and the host's actual capabilities. In particular, a convenient way to enter
an answer must not quietly change what the answer proves. Test the behavior
that mattered to the learner, then verify the teaching still works when the
preferred interface is unavailable.

**What it becomes**: feedback records include the missing decision and its
affected paths. Shared behavior is implemented once and routed to every
relevant stage. Tests cover the teaching consequence and a usable fallback.

---

## 3. Two places where principles conflict, and how each is settled

Two pairs of principles point in opposite directions. Both need a stated
resolution rather than being left implicit.

### Conflict A: reviewing what is closest to being forgotten, versus reviewing what can still be saved cheaply

Principle 1 (Bjork) says the gain from a successful recall is largest when
retrieval strength is low, which argues for reviewing **what is closest to
being forgotten** first.

Research on clearing a backlog says that anything already forgotten has to be
learned again regardless, so it is more efficient to review **what is still
remembered**, which argues for the opposite order.

**Resolution**: the two are optimising different things and apply in different
situations.

- **When nothing is overdue**, the scheduler's goal is for each item to come up
  at the moment its retrieval strength has fallen to the target level. That is
  the point Bjork's result identifies, and it is the entire reason the
  intervals adapt to the learner.
- **When items are overdue**, that moment has already passed and cannot be
  recovered. What remains is deciding which items to spend time on when not all
  of them can be saved. Items long overdue have mostly been forgotten already
  and will need relearning, so a few more days changes little. Items only
  slightly overdue can still be held at small cost.

So: **the schedule aims at the point Bjork identified, and the backlog
procedure decides what to do once that point has been missed.** Two separate
pieces of logic, each applying in its own situation.

### Conflict B: difficulty improves learning, versus difficulty causes people to quit

See Principle 8. Resolution: **difficulty belongs in the material, not in the
process of getting to the material.**

---

## 4. Gaps this document exposed, and what happened to them

Writing this document identified three genuine gaps. These were not things done
badly; they were things not considered at all. All three are now built; the
table remains here because it records why the mechanisms exist.

| Gap | Principle it violates | Severity | Implementation |
|---|---|---|---|
| **No mixed practice anywhere** | 5 | High. Single-topic practice removes the need to choose a method | `exercise.py drill`, whole-set validation, and a mandatory session drill |
| **Nothing requires attempting before being taught, or explaining back** | 6 | High. Teaching first gives up the benefit of learner production | productive-failure routing, explain-back items, and the lesson-advance gate |
| **The criterion for a transfer test is too weak** | 7 | Medium. The earlier rule stretched only one of six dimensions | explicit `transfer_dimensions` plus strength reporting |

Two further gaps were also closed:

- **Feedback timing** is now set by item type in `teaching-contract.md` rather
  than applied globally.
- **The explanation sequence** is now trimmable by the learner's register.
  Experts start at the model or formal statement; beginners can start from the
  phenomenon or intuitive picture. The boundary remains mandatory for all.

---

## 5. The sixteen complaints, classified

The complaints report symptoms. Classifying them shows which ones are
**learning-science problems** and which are **limits of what the previous tool
could do**, because the two require completely different fixes, and treating
one as the other produces a fix that cannot work.

| Complaint | Type | Cause |
|---|---|---|
| 1 Teaching style drifts | Building | Eng 4: nothing persists between sessions, so the setting has nowhere to live |
| 2 Does not switch teaching mode | Learning | Principles 5, 6: the mode should be decided by the type of material and the stage of learning |
| 3 Misjudges existing knowledge | Learning | Principle 3: follows directly from the expertise reversal effect |
| 4 Cost grows out of control | Both | Eng 3 (loaded context costs money) and Principle 4 (limit on connections formed at once) |
| 5 Never starts a review | Both | Principle 2 (only delayed evidence counts) and Eng 4 (something must persist between sessions) |
| 6 Does not advance the plan | Building | Eng 4: falling behind can only be measured against recorded progress |
| 7 Exercises limited to discussion | **Building** | **Eng 1: a web chat cannot run anything. This is the main reason for building a plugin** |
| 8 Background questions derail the lesson | Building | Eng 5: a separate process with its own context |
| 9 Does not read the supplied material | Both | Eng 1 (must be able to open files) and Principle 1 (an outside source is what makes difficulty objective rather than self-assessed) |
| 10 No access to tools | **Building** | **Eng 1: same cause** |
| 11 Notes turn into a diary | Learning | Principles 1, 2: notes exist to hold durable knowledge, not a record of what was discussed |
| 12 Lessons go deeper than intended | Learning | Principles 4, 7: a depth target is a budget for how many connections to build |
| 13 Marking is too lenient | Both | Principles 1, 2 for what counts as a pass, and Eng 2, 5 for what actually prevents leniency |
| 14 Workload grows out of control | Both | Principles 4, 8, and Eng 4 (recognising the learner's state requires history) |
| 15 Explanations land badly | Learning | Principle 3: clarity is not one standard, it is matching the learner's position in that field |
| 16 No method for subjects outside the sciences | Learning | Principle 3: an unfamiliar field should use a different explanation setting |

Totals: six purely learning science, four purely about what the tool can do,
six both.

**Applying learning science to a problem that is about capability does not
work.** No change to teaching method fixes complaints 7 and 10. Only the
ability to run programs and open files does, which is why the first step was
building a plugin rather than writing better instructions for a web chat.

The reverse also holds. Complaint 13 is not fixed by capability alone: putting
the marking in a separate process is something the plugin can do, but what
counts as a pass has to be decided by Principles 1 and 2.

**The sixteen are not a complete list.** Working from the principles produced
three requirements none of them mention, listed in the previous section. From
here on, every mechanism added has to be traceable to research, to a constraint
on building it, or to reported experience. Anything that traces to none of the
three does not get built.

---

## 6. What later stages are required to produce

| Principle | Doctrine file it produces |
|---|---|
| Learning 1, 2 | `mastery-policy.md`, `assessment-rubrics.md` |
| Learning 3 | `teaching-contract.md` (per-field settings, and a shortenable explanation sequence) |
| Learning 4 and Eng 3 | `context-budget.md`, `load-and-energy.md` |
| Learning 5, 6 | `mode-router.md` (must include attempting before being taught, and assembling mixed practice), `exercise-engine.md` |
| Learning 7 and Eng 1 | `exercise-engine.md` (the six transfer dimensions), `source-anchoring.md`, `practice-reach.md` |
| Learning 8 | `session-protocol.md`, `persona-zep.md` |
| Eng 5 | `sidequest-protocol.md`, `assessment-rubrics.md` (keeping the marker separate) |
| Eng 6 | `practice-reach.md`, `adapter-contract.md`, `resources-and-tools.md` |

The rule: **every doctrine file opens by naming which principle it implements.
A learning principle or a building principle, either is acceptable, but it must
be possible to name one. A file for which none can be named should not exist.**

---

## References

- Bjork & Bjork 1992, *A new theory of disuse and an old theory of stimulus fluctuation* — storage strength and retrieval strength
- Bjork 1994 and later work, desirable difficulties
- Koriat & Bjork 2005, *Illusions of competence in monitoring one's knowledge*
- Dunlosky, Rawson, Marsh, Nathan & Willingham 2013, *Improving Students' Learning With Effective Learning Techniques*, Psychological Science in the Public Interest 14(1) — ten techniques rated by strength of evidence
- Cepeda, Vul, Rohrer, Wixted & Pashler 2008, *Spacing Effects in Learning: A Temporal Ridgeline of Optimal Retention*, Psychological Science — the best gap is 10 to 20 percent of how long the material must be retained
- Karpicke & Roediger 2007, *Expanding Retrieval Practice Promotes Short-Term Retention, but Equally Spaced Retrieval Enhances Long-Term Retention* — delaying the first recall attempt is what matters most
- Taylor & Rohrer 2010, *The Effects of Interleaved Practice*, Applied Cognitive Psychology — mixed practice doubles scores on a delayed test
- Kalyuga & Sweller, the expertise reversal effect
- Cowan 2001, *The magical number 4 in short-term memory*, Behavioral and Brain Sciences
- Chi et al., the self-explanation effect
- Kapur, productive failure
- Barnett & Ceci 2002, *When and where do we apply what we learn? A taxonomy for far transfer*, Psychological Bulletin
- Kulik & Kulik 1988, *Timing of Feedback and Verbal Learning*, Review of Educational Research
- Wilson & Korn 2007, *Attention During Lectures: Beyond Ten Minutes*, Teaching of Psychology — the claim that attention lasts 10 to 15 minutes is not supported by the evidence
- Locke & Latham 2006, *New Directions in Goal-Setting Theory*, Current Directions in Psychological Science — goals that are specific, demanding and near-term
- Bhanji et al. 2012, *The Retrospective Pre-Post*, Academic Emergency Medicine — self-rated learning gain correlates near zero with measured gain
