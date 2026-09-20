#!/usr/bin/env python3
"""Every tunable number in ZepTeach, with where it came from.

A learning system is full of numbers that look authoritative and are not.
This module exists so that none of them can hide. Each entry declares what
kind of claim it is:

  evidence    - a published finding supports this value or range
  convention  - long field use in an established tool, not a study
  engineering - a cost or product decision, with reasoning, making no claim
                about how learning works
  calibrated  - starts at a documented default and is then learned from this
                learner's own logs, because the literature has no answer

The rule this file enforces, via the test suite: a number with no source is
not allowed to exist. If something is a guess, it says so and is marked
calibrated so that the learner's own data replaces it.

Print the whole ledger:  python constants.py table
"""

from __future__ import annotations

import argparse
import json
import sys

KINDS = ("evidence", "convention", "engineering", "calibrated")


TUNABLE = {

    # ----------------------------------------------------------------
    # spacing floors
    # ----------------------------------------------------------------
    "delayed_retest_min_days": {
        "value": 3,
        "kind": "evidence",
        "source": "Karpicke & Roediger 2007, J Exp Psychol LMC; Cepeda et al. "
                  "2008, Psychological Science (n>1350)",
        "why": "Karpicke and Roediger found that delaying the FIRST retrieval "
               "is the single thing that most improves long-term retention, "
               "and that expanding schedules beat equal ones only in the "
               "short term. Cepeda puts the optimal study gap at 10-20% of "
               "how long you want to remember something. Both say the first "
               "retest should be later than intuition suggests. Three days "
               "is the floor, not the schedule: it blocks the same-evening "
               "redo while the adaptive interval usually pushes further out.",
        "caveat": "Cepeda's optimum is for a single restudy, not a multi-"
                  "review ladder, so it anchors the direction rather than "
                  "the exact number.",
    },
    "transfer_test_min_days": {
        "value": 7,
        "kind": "engineering",
        "source": "no direct study; scaled from delayed_retest_min_days",
        "why": "A transfer test asks for the idea in new ground, which only "
               "means anything once it has survived a first gap. Set at "
               "roughly double the first floor so the two tests cannot "
               "collapse into the same week.",
    },

    # ----------------------------------------------------------------
    # grading the recall
    # ----------------------------------------------------------------
    "grade_table": {
        "value": {
            "pass|instant": 5, "pass|fluent": 4, "pass|effortful": 3,
            "pass|recovered_with_hint": 2,
            "partial|instant": 2, "partial|fluent": 2,
            "partial|effortful": 1, "partial|recovered_with_hint": 1,
        },
        "kind": "convention",
        "source": "SM-2 five-point quality scale (Wozniak 1990), as used by "
                  "Anki's four buttons",
        "why": "SM-2 grades a recall 0-5 and treats 3 as the lowest passing "
               "score. The four recall-effort labels map onto that scale. "
               "Putting a hinted recall at 2 is the deliberate part: SM-2 "
               "calls 3 'correct with serious difficulty', and needing to be "
               "told is below that.",
    },
    "default_latency": {
        "value": "effortful",
        "kind": "engineering",
        "source": "asymmetric cost, not a study",
        "why": "When nothing rated the recall, assume it took work. Guessing "
               "low costs one extra review; guessing high loses the fact.",
    },
    "passing_grade": {
        "value": 3,
        "kind": "convention",
        "source": "SM-2 (Wozniak 1990)",
        "why": "SM-2's own threshold: below 3 the item re-enters learning.",
    },

    # ----------------------------------------------------------------
    # interval growth
    # ----------------------------------------------------------------
    "default_ease": {
        "value": 2.5,
        "kind": "convention",
        "source": "SM-2 initial E-Factor; Anki starting ease default 2.50",
        "why": "Unchanged from the original algorithm and from Anki's "
               "shipped default.",
    },
    "min_ease": {
        "value": 1.3,
        "kind": "convention",
        "source": "SM-2 minimum E-Factor",
        "why": "Below this the interval barely grows and the item should be "
               "re-taught rather than re-scheduled.",
    },
    "max_ease": {
        "value": 3.5,
        "kind": "engineering",
        "source": "no equivalent in SM-2, which is unbounded above",
        "why": "An upper bound stops one lucky run of instant recalls from "
               "flinging a concept years away. Anki leaves this open; a "
               "course has an end date, so we do not.",
    },
    "first_interval": {
        "value": {"3": 1.0, "4": 2.0, "5": 3.0},
        "kind": "engineering",
        "source": "graded variant of Anki's 1-day graduating interval",
        "why": "Anki graduates everything at 1 day regardless of how the "
               "recall went, which throws away the effort signal exactly "
               "when it is most informative. These are subordinate to the "
               "floors above anyway: early on, the 3-day floor dominates.",
    },
    "second_interval": {
        "value": {"3": 4.0, "4": 6.0, "5": 8.0},
        "kind": "engineering",
        "source": "graded variant of SM-2's fixed 6-day second interval",
        "why": "Same reasoning as the first interval; 6 days is SM-2's value "
               "and sits in the middle.",
    },
    "grade_factor": {
        "value": {"3": 0.85, "4": 1.0, "5": 1.15},
        "kind": "engineering",
        "source": "none; a deliberately small correction",
        "why": "Ease already accumulates the effort signal over repetitions. "
               "An earlier draft used 0.8/1.0/1.3 and produced three-fold "
               "jumps in a single step, which is double-counting. Kept small "
               "on purpose. This is the weakest number in the file and the "
               "first one to drop if it misbehaves.",
    },
    "late_credit": {
        "value": {"3": 0.0, "4": 0.5, "5": 1.0},
        "kind": "convention",
        "source": "Anki SM-2 overdue handling: full delay added for Easy, "
                  "half for Good, none for Hard",
        "why": "A late recall that still worked says the interval was too "
               "short. Copied from Anki's proportions rather than invented.",
        "caveat": "One long-running analysis of ~105k real overdue reviews "
                  "found SM-2's interval inflation for late cards may be "
                  "overstated in theory, though the measured retention cost "
                  "of lateness was only about 1 percentage point.",
    },
    "lapse_ease_penalty": {
        "value": 0.2,
        "kind": "convention",
        "source": "Anki: pressing Again reduces ease by 20 percentage points",
        "why": "Copied from Anki rather than chosen. SM-2's own formula "
               "reduces the E-Factor on a poor recall; Anki fixes the "
               "reduction at 0.20 for a lapse, which is what this is.",
    },
    "max_interval_days": {
        "value": 180.0,
        "kind": "engineering",
        "source": "far tighter than Anki's 100-year default",
        "why": "Anki's default is effectively no cap, which suits a lifetime "
               "vocabulary deck. This is coursework with a horizon, and "
               "anything genuinely over-maintained should retire out of the "
               "queue instead of drifting to a two-year interval.",
    },
    "target_retention": {
        "value": 0.9,
        "kind": "convention",
        "source": "Anki/FSRS default desired retention",
        "why": "Used only to approximate how likely something still is to be "
               "recalled, for ordering a backlog.",
        "caveat": "FSRS work puts the efficiency sweet spot nearer 0.85: "
                  "going from 0.90 to 0.95 roughly doubles review load for a "
                  "small retention gain. Exposed as config for that reason.",
    },

    # ----------------------------------------------------------------
    # backlog
    # ----------------------------------------------------------------
    "review_cap_per_session": {
        "value": 8,
        "kind": "calibrated",
        "source": "starts from the shape of Anki's daily limits (20 new / "
                  "200 reviews per day, a 10:1 ratio); then learned from the "
                  "learner's own completed sessions",
        "why": "Anki's numbers are per-day flashcard counts and do not "
               "transfer to concept-level review inside a tutoring session, "
               "so the starting value is a placeholder. What matters is the "
               "cap existing at all: the documented failure mode of spaced "
               "repetition is abandonment in the face of a wall of overdue "
               "items, not forgetting.",
    },
    "backlog_band_moderate": {
        "value": 1.0,
        "kind": "engineering",
        "source": "none",
        "why": "One session of debt is the natural line: more than a session "
               "means it cannot be cleared today whatever happens.",
    },
    "review_share_manageable": {
        "value": 0.5,
        "kind": "engineering",
        "source": "none",
        "why": "With a small debt, half the session on review still leaves "
               "room to teach. The number is a starting split, not a finding.",
    },
    "review_share_moderate": {
        "value": 0.7,
        "kind": "engineering",
        "source": "none",
        "why": "Leans the session towards clearing debt while still leaving "
               "space for one new concept, so the course does not stall.",
    },
    "backlog_band_severe": {
        "value": 3.0,
        "kind": "engineering",
        "source": "none",
        "why": "Three sessions is roughly a week of debt at a normal pace, "
               "which is the point at which pausing new material costs less "
               "than letting the queue keep growing.",
    },

    # ----------------------------------------------------------------
    # retirement
    # ----------------------------------------------------------------
    "retire_after_instant": {
        "value": 3,
        "kind": "engineering",
        "source": "no equivalent in Anki or SuperMemo, which never retire",
        "why": "Three in a row is short enough to stop wasting sessions on "
               "things the learner uses daily, and the streak breaks on any "
               "answer that is not another instant pass, so the cost of "
               "being wrong is one review.",
    },
    "bypass_warning_count": {
        "value": 3,
        "kind": "convention",
        "source": "loosely after Anki's leech threshold of 8 lapses",
        "why": "Anki flags an item after 8 failures. Waving a shaky "
               "prerequisite through is a deliberate act rather than a "
               "failure, so it is flagged sooner.",
    },

    # ----------------------------------------------------------------
    # checking what practice can act on
    # ----------------------------------------------------------------
    "probe_timeout_seconds": {
        "value": 20,
        "kind": "engineering",
        "source": "none; a cost decision about a lesson, not a claim about "
                  "anything",
        "why": "Establishing that a program is the one its name suggests "
               "means running it, and a program that hangs would hang the "
               "lesson with it. Twenty seconds is long enough for a version "
               "banner from something slow to start, short enough that four "
               "failed checks still cost under two minutes.",
    },
    "reach_recheck_days": {
        "value": 7,
        "kind": "engineering",
        "source": "none",
        "why": "What is installed and what the learner can get hold of both "
               "change, but slowly, and re-checking is not free. A week means "
               "a change is noticed within one week of study rather than "
               "discovered mid-lesson. Staleness produces a note at the start "
               "of a session, never a refusal: blocking a lesson because a "
               "check is eight days old would be absurd.",
    },
    "default_substitute_depth_ceiling": {
        "value": 3,
        "kind": "engineering",
        "source": "none; the conservative reading of the depth scale",
        "why": "Used only when an adapter declares a substitute without "
               "saying how deep it can certify. Depth 3 is can-derive, which "
               "a built substitute can genuinely support; 4 is can-critique, "
               "which usually needs the real thing to have surprised you at "
               "least once. Guessing low costs an unnecessary conversation; "
               "guessing high lets a course claim a depth it never reached.",
    },

    "max_command_timeout_seconds": {
        "value": 1800,
        "kind": "engineering",
        "source": "none; a limit on waiting, not a claim about anything",
        "why": "Every command gets a time limit, because one that hangs "
               "otherwise waits for as long as the learner is willing to sit "
               "there. Half an hour is the outer bound for something waited "
               "on during a lesson. Work that genuinely takes longer is "
               "something the learner starts and comes back to.",
    },
    "shared_resource_size_limit": {
        "value": 4,
        "kind": "engineering",
        "source": "none; a starting limit for anything other people also "
                  "depend on",
        "why": "Where nothing else rations a shared thing, an agreed number "
               "is the only limit on one piece of work taking all of it. Four "
               "is small enough to be unobjectionable almost anywhere, and is "
               "meant to be raised deliberately rather than relied on.",
    },

    "never_retested_after_days": {
        "value": 14,
        "kind": "engineering",
        "source": "none; derived from the two spacing floors rather than "
                  "measured",
        "why": "How long something can sit taught and never retested before "
               "the progress report names it. The first retest floor is 3 "
               "days and the transfer floor is 7, so anything past 14 has "
               "missed both by a clear margin and did not simply arrive "
               "early. It is a reporting threshold, not a schedule: nothing "
               "is rescheduled by it, and being wrong costs one line in a "
               "report.",
    },

    # ----------------------------------------------------------------
    # mixed practice
    # ----------------------------------------------------------------
    "mixed_set_min_concepts": {
        "value": 3,
        "kind": "convention",
        "source": "the arrangement used in the interleaving experiments, "
                  "written abcbcacab - three topics shuffled",
        "why": "Two topics can be told apart by elimination after the first "
               "one, so choosing is barely practised. Three is the smallest "
               "number at which the learner has to actually recognise which "
               "situation they are in, and is what the experiments that "
               "produced the doubled delayed-test scores actually used.",
    },
    "mixed_set_size": {
        "value": 6,
        "kind": "calibrated",
        "source": "none; the experiments fixed the number of problems to "
                  "match their blocked condition rather than optimising it",
        "why": "Nothing establishes how long a mixed set should be. Six is "
               "two passes through three concepts, which is the least that "
               "can show whether the learner is choosing or guessing. It is "
               "marked calibrated because the right length shows up in the "
               "learner's own record: if they get every first-encounter "
               "wrong and every second right, the set is too short to "
               "practise choosing.",
    },

    # ----------------------------------------------------------------
    # how much doctrine rides along on every lesson
    # ----------------------------------------------------------------
    #
    # These three were written straight into test assertions and never
    # registered here, which is how three unsourced numbers survived in a
    # project whose stated rule is that a number without a source may not
    # exist. The ledger only ever audited what had been put into it.
    "lesson_doctrine_max_lines": {
        "value": 600,
        "kind": "engineering",
        "enforced": False,
        "deferred_because": "Writing to fit a ceiling produces documents "
                            "shaped by the ceiling rather than by what has "
                            "to be said, and it was already causing "
                            "content to be cut before it had been judged on "
                            "its merits. The limit stays recorded and "
                            "measured; enforcement waits until the doctrine "
                            "is complete, when compressing is editing rather "
                            "than omitting.",
        "source": "none; a cost decision, and lines are a stand-in for what "
                  "actually costs anything",
        "why": "Doctrine is re-read at the start of every lesson, so its size "
               "is a recurring charge and it competes for attention with the "
               "material being taught. The real unit is tokens, but this "
               "plugin has no tokenizer and deliberately no dependencies, so "
               "lines are counted instead. At roughly 12 to 15 tokens per "
               "line of prose, 600 lines is on the order of 8,000 tokens: "
               "about the size of the conversation it is meant to govern, "
               "which is the reasoning behind the figure. Nothing measured "
               "this; it is a ceiling chosen so that doctrine cannot quietly "
               "become the largest thing in the context.",
        "caveat": "Lines and tokens diverge badly between prose and tables. "
                  "If this ever needs to be precise, count tokens instead of "
                  "arguing about the line figure.",
    },
    "doctrine_file_max_lines": {
        "value": 160,
        "kind": "engineering",
        "enforced": False,
        "deferred_because": "see lesson_doctrine_max_lines",
        "source": "none",
        "why": "A per-file ceiling exists so that a file which outgrows its "
               "subject gets split rather than quietly absorbing a second "
               "one. It has already done that once, pushing the delivery "
               "rules out of the teaching contract into their own file. The "
               "number matters less than the fact that hitting it forces a "
               "decision about structure.",
    },
    "skill_file_max_lines": {
        "value": 130,
        "kind": "engineering",
        "enforced": False,
        "deferred_because": "see lesson_doctrine_max_lines",
        "source": "none",
        "why": "SKILL.md is loaded unconditionally, before anything is known "
               "about what is being done, so it is the most expensive file in "
               "the system per unit of usefulness. It holds a routing table "
               "and the rules that are enforced by code; everything else "
               "belongs in a file that loads only when relevant.",
    },

    # ----------------------------------------------------------------
    # progress against the plan
    # ----------------------------------------------------------------
    "drift_behind_ratio": {
        "value": 1.05,
        "kind": "engineering",
        "source": "none",
        "why": "How far the required pace may exceed the agreed pace before "
               "the course is called behind. Five percent is deliberately "
               "tight: being told early is cheap, and the alternative is "
               "finding out when the remaining time can no longer absorb it.",
    },
    "drift_ahead_ratio": {
        "value": 0.75,
        "kind": "engineering",
        "source": "none",
        "why": "How far below the agreed pace counts as ahead. Set much "
               "looser than the behind threshold on purpose: being ahead "
               "needs no action, so announcing it early has no value, while "
               "announcing it wrongly invites slowing down.",
    },
    "probe_questions": {
        "value": [2, 4],
        "kind": "engineering",
        "source": "none; bounded by what a probe is for",
        "why": "A prerequisite check establishes whether it is safe to build "
               "on something, not what the learner's level is. One question "
               "can be answered by luck; beyond about four it stops being a "
               "check and becomes a test the learner did not agree to sit, "
               "at the start of a lesson about something else.",
    },

    # ----------------------------------------------------------------
    # how much to say before stopping
    # ----------------------------------------------------------------
    "segment_is_learner_paced": {
        "value": True,
        "kind": "evidence",
        "source": "Mayer 2009/2021, Multimedia Learning, ch. 9 'The "
                  "Segmenting Principle'; restated in Mayer & Fiorella 2022, "
                  "Cambridge Handbook of Multimedia Learning. Supported in "
                  "10 of 10 experimental tests, median effect size 0.79; one "
                  "set of three problem-solving transfer tests gave 0.98",
        "why": "The finding is specifically about user-paced segments, EACH "
               "ONE STARTED BY THE LEARNER, against the same material "
               "delivered continuously. The benefit comes from the learner "
               "controlling when the next piece arrives, not from the pieces "
               "being small. A system that chops its output finely and then "
               "delivers all the pieces in one message has implemented the "
               "cosmetic half and none of the mechanism.",
        "caveat": "The effect is largest when the material is complex, the "
                  "pace is fast, and the learner is new to it. For someone "
                  "working in a field they know well, it matters much less, "
                  "which is the same boundary as the expertise reversal "
                  "effect and is why the register can shorten this.",
    },
    "ideas_per_segment": {
        "value": 1,
        "kind": "calibrated",
        "source": "no study gives a segment size; the literature is explicit "
                  "that it depends on the content, the task and the learner, "
                  "and warns that over-segmenting slows comprehension",
        "why": "So this is a starting rule rather than a finding: one segment "
               "carries one idea, and the boundary goes where the learner "
               "could be asked something. That is chosen to be checkable "
               "rather than to be a size. It is marked calibrated because the "
               "right amount for THIS learner is visible in their own logs - "
               "where they ask to go on immediately, the segment was too "
               "small; where they answer the check-back wrongly, it was too "
               "large - and those records should replace this.",
        "caveat": "Cutting more finely than one idea is a known failure mode, "
                  "not a safer default.",
    },
    "segment_check_back": {
        "value": "question",
        "kind": "engineering",
        "source": "none; follows from the mechanism above",
        "why": "Since the benefit comes from the learner starting the next "
               "piece, each segment has to end with something they answer. "
               "Asking whether they are ready to continue does not count: it "
               "is answered yes by default and tests nothing. A question "
               "about the segment both hands over the pacing and produces a "
               "retrieval attempt, which is the highest-utility thing the "
               "system can do anyway.",
    },

    # ----------------------------------------------------------------
    # session shape
    # ----------------------------------------------------------------
    "turn_budget": {
        "value": 40,
        "kind": "engineering",
        "source": "none; this is a context-cost control, not a teaching claim",
        "why": "Nothing about learning says 40. It bounds how much transcript "
               "accumulates before a digest is forced, which is what keeps a "
               "long session from quietly costing more and remembering less. "
               "Calibrate it against actual usage, not against pedagogy.",
    },
    "checkpoint_at": {
        "value": 0.6,
        "kind": "engineering",
        "source": "none",
        "why": "Early enough that there is still room to act on the digest, "
               "late enough that there is something worth digesting.",
    },
    "hard_stop_at": {
        "value": 0.9,
        "kind": "engineering",
        "source": "none",
        "why": "Leaves a margin to close the session properly rather than "
               "being cut off mid-explanation.",
    },
    "session_minutes": {
        "value": 45,
        "kind": "calibrated",
        "source": "NOT the 10-15 minute attention span figure, which Wilson "
                  "& Korn (2007, Teaching of Psychology) reviewed and found "
                  "unsupported; learned from the learner's own energy log",
        "why": "There is no defensible universal session length. The popular "
               "figure is a myth, and vigilance-decrement work (decline after "
               "20-30 min) comes from monotonous monitoring tasks, not active "
               "learning. So this starts as a placeholder and is replaced by "
               "what this learner actually completes.",
    },
    "max_new_concepts_per_session": {
        "value": 3,
        "kind": "evidence",
        "source": "Cowan 2001, Behavioral and Brain Sciences: working memory "
                  "holds about 4 chunks, individually 2-6",
        "why": "Introducing more distinct new ideas at once than can be held "
               "together means they cannot be related to each other, which is "
               "where understanding comes from.",
        "caveat": "Cowan's limit is about simultaneous holding, not about a "
                  "whole session, so this is a soft anchor. It is also "
                  "individual (2-6), which is why it is per-learner config.",
    },
    "energy_scaling": {
        "value": {
            "low": {"budget": 0.6, "minutes": 0.6, "banter": 0, "reviews": 3},
            "normal": {"budget": 1.0, "minutes": 1.0, "banter": None,
                       "reviews": 5},
            "high": {"budget": 1.3, "minutes": 1.3, "banter": None,
                     "reviews": 8},
        },
        "kind": "calibrated",
        "source": "none; starting guesses",
        "why": "How much a tired evening should shrink a session is a fact "
               "about this person, not about people. These are placeholders "
               "until the energy log has enough completed sessions to "
               "measure the real ratio.",
    },
    "fatigue_error_rise": {
        "value": 0.25,
        "kind": "engineering",
        "source": "vigilance-decrement literature shows rising error rates "
                  "with time on task, but gives no threshold for this setting",
        "why": "A quarter is large enough not to fire on noise in a handful "
               "of answers. It triggers a suggestion to stop, never a "
               "conclusion about understanding, so a false positive is cheap.",
    },
    "fatigue_min_attempts": {
        "value": 4,
        "kind": "engineering",
        "source": "none",
        "why": "Below four answers, halves of two cannot say anything.",
    },
}


def value(name):
    return TUNABLE[name]["value"]


def enforced(name) -> bool:
    """Whether a limit is currently refused on, or only measured.

    A limit that is recorded but not enforced is a deliberate state, not an
    oversight: the size ceilings are switched off while the doctrine is being
    written, because writing to fit a ceiling shapes the writing. Each one
    that is off says why, and the numbers are still reported.
    """
    return TUNABLE[name].get("enforced", True)


def _int_keys(d):
    return dict((int(k), v) for k, v in d.items())


# ---- module-level names used by the rest of the code ---------------------

DELAYED_RETEST_MIN_DAYS = value("delayed_retest_min_days")
TRANSFER_TEST_MIN_DAYS = value("transfer_test_min_days")

GRADE_TABLE = dict((tuple(k.split("|")), v)
                   for k, v in value("grade_table").items())
DEFAULT_LATENCY = value("default_latency")
PASSING_GRADE = value("passing_grade")

DEFAULT_EASE = value("default_ease")
MIN_EASE = value("min_ease")
MAX_EASE = value("max_ease")
FIRST_INTERVAL = _int_keys(value("first_interval"))
SECOND_INTERVAL = _int_keys(value("second_interval"))
GRADE_FACTOR = _int_keys(value("grade_factor"))
LATE_CREDIT = _int_keys(value("late_credit"))
MAX_INTERVAL_DAYS = value("max_interval_days")
TARGET_RETENTION = value("target_retention")

DEFAULT_REVIEW_CAP = value("review_cap_per_session")
BAND_MODERATE = value("backlog_band_moderate")
BAND_SEVERE = value("backlog_band_severe")
REVIEW_SHARE_MANAGEABLE = value("review_share_manageable")
REVIEW_SHARE_MODERATE = value("review_share_moderate")
LAPSE_EASE_PENALTY = value("lapse_ease_penalty")

RETIRE_AFTER_INSTANT = value("retire_after_instant")
BYPASS_WARNING_COUNT = value("bypass_warning_count")

TURN_BUDGET = value("turn_budget")
CHECKPOINT_AT = value("checkpoint_at")
HARD_STOP_AT = value("hard_stop_at")
SESSION_MINUTES = value("session_minutes")
MAX_NEW_CONCEPTS = value("max_new_concepts_per_session")
ENERGY = value("energy_scaling")
FATIGUE_ERROR_RISE = value("fatigue_error_rise")
FATIGUE_MIN_ATTEMPTS = value("fatigue_min_attempts")

PROBE_TIMEOUT_SECONDS = value("probe_timeout_seconds")
REACH_RECHECK_DAYS = value("reach_recheck_days")
DEFAULT_SUBSTITUTE_DEPTH_CEILING = value("default_substitute_depth_ceiling")
MAX_COMMAND_TIMEOUT_SECONDS = value("max_command_timeout_seconds")
SHARED_RESOURCE_SIZE_LIMIT = value("shared_resource_size_limit")

SEGMENT_IS_LEARNER_PACED = value("segment_is_learner_paced")
IDEAS_PER_SEGMENT = value("ideas_per_segment")
SEGMENT_CHECK_BACK = value("segment_check_back")

NEVER_RETESTED_AFTER_DAYS = value("never_retested_after_days")
MIXED_SET_MIN_CONCEPTS = value("mixed_set_min_concepts")
MIXED_SET_SIZE = value("mixed_set_size")

LESSON_DOCTRINE_MAX_LINES = value("lesson_doctrine_max_lines")
DOCTRINE_FILE_MAX_LINES = value("doctrine_file_max_lines")
SKILL_FILE_MAX_LINES = value("skill_file_max_lines")
DRIFT_BEHIND_RATIO = value("drift_behind_ratio")
DRIFT_AHEAD_RATIO = value("drift_ahead_ratio")
PROBE_QUESTIONS = tuple(value("probe_questions"))


# ---- cli -----------------------------------------------------------------

def cmd_table(args) -> int:
    rows = sorted(TUNABLE.items(),
                  key=lambda kv: (KINDS.index(kv[1]["kind"]), kv[0]))
    if args.json:
        print(json.dumps(dict(rows), ensure_ascii=False, indent=2))
        return 0
    current = None
    for name, spec in rows:
        if spec["kind"] != current:
            current = spec["kind"]
            print("\n== " + current.upper() + " ==")
        val = spec["value"]
        shown = json.dumps(val, ensure_ascii=False) if isinstance(
            val, (dict, list)) else str(val)
        if len(shown) > 60:
            shown = shown[:57] + "..."
        print("  " + name + " = " + shown)
        print("      source: " + spec["source"])
        if spec.get("caveat"):
            print("      caveat: " + spec["caveat"])
    counts = {}
    for _, spec in rows:
        counts[spec["kind"]] = counts.get(spec["kind"], 0) + 1
    print("\n" + ", ".join(k + ": " + str(counts.get(k, 0)) for k in KINDS))
    return 0


def cmd_kind(args) -> int:
    for name, spec in sorted(TUNABLE.items()):
        if spec["kind"] == args.kind:
            print(name)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="constants.py",
        description="Where every tunable number came from.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("table")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_table)
    sp = sub.add_parser("kind")
    sp.add_argument("kind", choices=KINDS)
    sp.set_defaults(func=cmd_kind)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
