"""Shared fixtures for the ZepTeach test suite.

Builds a small two-course world with one course in mathematics and one in
history. That pairing is load-bearing, not decoration. An earlier version had
two STEM courses, and under it the core quietly filled up with assumptions
about computation - a grader enum naming two chemistry programs, an exercise
form list mixing simulations with close readings, a course field enumerating
permitted disciplines. Nothing caught it, because nothing in the tests was
ever inconvenienced by it. With a humanities course in the fixture world, code
that assumes a subject fails here instead of in front of a learner.

The two courses share reason.necessary-sufficient, which is what the global
concept registry is for: the same idea is doing work in a proof and in a
causal claim about the past, and the second course should benefit from the
first having taught it.
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import zt_state as zs  # noqa: E402


EIGENVALUE = "linalg.eigenvalue"
EIGENVECTOR = "linalg.eigenvector"

# Shared across the two courses, and deliberately not a STEM concept: telling
# a necessary condition from a sufficient one is the same skill whether the
# claim is about a matrix or about why a treaty failed.
SHARED = "reason.necessary-sufficient"
SOURCE_CRITIQUE = "hist.source-critique"


def config(**over):
    doc = {
        "schema_version": 1,
        "learner_id": "learner",
        "teaching_language": "zh-CN",
        "setup": {"stage1_completed_at": "2026-09-01T00:00:00+00:00"},
        "notes": {"markdown_dir": "E:/notes", "document_dir": "E:/docs",
                  "journal_dir": "E:/notes/journal"},
        "persona": {"name": "Zep", "closeness": 4, "banter": 2},
        "agent_models": {"sidequest_tutor": "sonnet", "grader": "opus",
                         "curriculum_architect": "opus"},
        "defaults": {"turn_budget": 40, "checkpoint_at": 0.6,
                     "hard_stop_at": 0.9, "session_minutes": 45,
                     "delayed_retest_min_days": 3,
                     "transfer_test_min_days": 7},
    }
    doc.update(over)
    return doc


def profile(**over):
    doc = {
        "schema_version": 1,
        "learner_id": "learner",
        "display_name": "Z",
        "background": [
            {"domain": "semiconductor-physics", "level": "expert",
             "basis": "self_declared"},
            {"domain": "mathematics", "level": "working",
             "basis": "self_declared"},
        ],
        "registers": [
            {"domain": "*", "register": "technical_with_gloss",
             "max_analogies_per_concept": 1},
            {"domain": "semiconductor-physics", "register": "terse_technical",
             "max_analogies_per_concept": 0, "formalism_tolerance": 5},
            {"domain": "humanities", "register": "analogy_first",
             "max_analogies_per_concept": 2, "formalism_tolerance": 2},
        ],
        "pacing": {"weekly_minutes": 300, "preferred_session_minutes": 45,
                   "max_new_concepts_per_session": 3,
                   "max_new_concepts_low_energy": 1},
    }
    doc.update(over)
    return doc


def registry(**over):
    doc = {
        "schema_version": 1,
        "concepts": [
            {"concept_id": EIGENVALUE, "canonical_title": "Eigenvalue",
             "domain": "mathematics/linear-algebra",
             "courses": ["linalg"],
             "note_path": "notes/concepts/" + EIGENVALUE + ".md"},
            {"concept_id": EIGENVECTOR, "canonical_title": "Eigenvector",
             "domain": "mathematics/linear-algebra", "courses": ["linalg"]},
            {"concept_id": SHARED,
             "canonical_title": "Necessary and sufficient conditions",
             "domain": "reasoning", "courses": ["linalg", "hist"],
             "note_path": "notes/concepts/" + SHARED + ".md"},
            {"concept_id": SOURCE_CRITIQUE,
             "canonical_title": "Source critique",
             "domain": "history/method", "courses": ["hist"]},
        ],
    }
    doc.update(over)
    return doc


def course(course_id="linalg", slug="linear-algebra", **over):
    doc = {
        "schema_version": 1,
        "course_id": course_id,
        "slug": slug,
        "title": "Linear algebra for AI",
        "goal": "Model a real problem with eigen-decomposition unaided.",
        "domain": "mathematics",
        "adapter_ref": "adapters/mathematics.json",
        "status": "active",
        "weekly_minutes": 300,
        "milestones": [
            {"date": "2026-10-15",
             "capability": "Diagonalise a 3x3 matrix by hand and say when it "
                           "cannot be done."},
        ],
        "depth_policy": {"default_depth_target": 3, "allow_depth_raise": True,
                         "raise_requires_sidequest": True},
        "environment": {
            "completed_at": "2026-09-05T00:00:00+00:00",
            "required_targets": [
                {"target_id": "problem-set", "kind": "problem set",
                 "named_in_goal": False, "criticality": "required",
                 "why": "the anchored tier needs problems someone else set"}],
            "resolution": [{"target_id": "problem-set", "reach": "direct",
                            "depth_ceiling": 5, "where": "local"}],
        },
    }
    doc.update(over)
    return doc


def curriculum(course_id="linalg", **over):
    doc = {
        "schema_version": 1,
        "course_id": course_id,
        "version": 1,
        "modules": [{
            "module_id": "m1",
            "title": "Eigen-structure",
            "lessons": [
                {"lesson_id": "l1", "title": "Eigenvalues",
                 "estimated_minutes": 60,
                "concepts": [{"concept_id": EIGENVALUE,
                               "title": "Eigenvalue", "depth_target": 3,
                               "domain": "mathematics/linear-algebra",
                               "exercise_types": ["derive", "apply",
                                                  "construct"]},
                    {"concept_id": SHARED,
                     "title": "Necessary and sufficient conditions",
                     "depth_target": 3, "domain": "reasoning",
                               "exercise_types": ["derive", "critique"]}]},
                {"lesson_id": "l2", "title": "Eigenvectors",
                 "estimated_minutes": 60,
                "concepts": [{"concept_id": EIGENVECTOR,
                               "title": "Eigenvector", "depth_target": 3,
                               "domain": "mathematics/linear-algebra",
                               "prereq": [EIGENVALUE]}]},
            ],
        }],
    }
    doc.update(over)
    return doc


def hist_curriculum(**over):
    """The humanities course. It reuses the shared reasoning concept at a
    lower depth than the mathematics course does, which is the case the
    per-course depth target exists for: a historian needs to USE the
    distinction, a proof writer needs to derive with it."""
    doc = {
        "schema_version": 1,
        "course_id": "hist",
        "modules": [{
            "module_id": "m1",
            "title": "Reading a historian",
            "lessons": [{
                "lesson_id": "l1", "title": "What the sources will bear",
                "estimated_minutes": 90,
                "concepts": [
                    {"concept_id": SHARED,
                     "title": "Necessary and sufficient conditions",
                     "depth_target": 1},
                    {"concept_id": SOURCE_CRITIQUE, "title": "Source critique",
                     "depth_target": 3, "domain": "history/method",
                     "prereq": [SHARED],
                     "exercise_types": ["analyze", "critique", "construct"]},
                ],
            }],
        }],
    }
    doc.update(over)
    return doc


# kept under the old name so nothing silently reads a stale fixture
llm_curriculum = hist_curriculum


def math_adapter(**over):
    """Mathematics needs nothing installed. Declaring that explicitly, rather
    than leaving the target list empty, is what lets the setup check report
    'this course needs nothing' instead of 'this course was never examined'."""
    doc = {
        "schema_version": 1,
        "adapter_id": "mathematics",
        "field": "mathematics",
        "generated_at": "2026-09-05T00:00:00+00:00",
        "generated_for": "linalg",
        "goal_quoted": "Model a real problem with eigen-decomposition "
                       "unaided.",
        "targets": [
            {"target_id": "paper", "kind": "the learner's own written work",
             "why": "every derivation is done by hand; there is nothing to "
                    "install and nothing to obtain",
             "named_in_goal": False},
            {"target_id": "problem-set", "kind": "problem set",
             "why": "the hardest tier has to draw on problems someone else "
                    "set, or its difficulty is only this system's opinion",
             "named_in_goal": False,
             "substitute": {
                 "level": "stand_in", "depth_ceiling": 3,
                 "describe": "problems composed for the occasion",
                 "what_is_lost": "difficulty is no longer fixed by an "
                                 "outside source, so it drifts towards what "
                                 "the learner can already do"}},
        ],
        "activities": [
            {"activity_id": "prove", "label": "prove a statement",
             "action": "derive", "acts_on": ["paper"], "depth_range": [3, 4]},
            {"activity_id": "compute", "label": "carry out a computation",
             "action": "apply", "acts_on": ["paper"], "depth_range": [1, 2]},
            {"activity_id": "model", "label": "set up a model of a situation",
             "action": "construct", "acts_on": ["paper"],
             "depth_range": [3, 5]},
            {"activity_id": "find-method",
             "label": "work out which method a problem calls for",
             "action": "analyze", "acts_on": ["paper"], "depth_range": [2, 4]},
        ],
        "anchor_sources": [
            {"label": "published problem sets", "reachable": True}],
        "register_hint": {"suggested": "technical_with_gloss",
                          "why": "notation is dense and easy to misread"},
    }
    doc.update(over)
    return doc


def hist_adapter(**over):
    """History practises on documents, and whether the learner can reach them
    is a question only they can answer, which is why how_to_check asks rather
    than runs anything."""
    doc = {
        "schema_version": 1,
        "adapter_id": "history",
        "field": "history",
        "generated_at": "2026-09-05T00:00:00+00:00",
        "generated_for": "hist",
        "goal_quoted": "Reconstruct a historian's argument and judge whether "
                       "the sources bear it.",
        "targets": [
            {"target_id": "source-set", "kind": "primary sources",
             "why": "judging whether a claim is supported requires the "
                    "documents the claim rests on",
             "named_in_goal": False,
             "how_to_check": {
                 "ask_the_learner": "Which document collections can you "
                                    "actually open - through a library, an "
                                    "archive, or online?"},
             "substitute": {
                 "level": "stand_in", "depth_ceiling": 4,
                 "describe": "a small document set assembled for the lesson, "
                             "with its provenance stated",
                 "what_is_lost": "the documents were chosen knowing what "
                                 "argument they would be used to test, so "
                                 "the learner never faces the real problem "
                                 "of a record that is silent on the question "
                                 "being asked"}},
            {"target_id": "monograph", "kind": "secondary work",
             "why": "the argument being reconstructed has to be somebody's "
                    "actual argument",
             "named_in_goal": False},
        ],
        "activities": [
            {"activity_id": "close-read", "label": "read a passage closely",
             "action": "analyze", "acts_on": ["monograph"],
             "depth_range": [2, 4]},
            {"activity_id": "reconstruct",
             "label": "reconstruct an argument",
             "action": "construct", "acts_on": ["monograph"],
             "depth_range": [3, 5]},
            {"activity_id": "weigh-sources",
             "label": "judge whether the sources support the claim",
             "action": "critique", "acts_on": ["source-set", "monograph"],
             "depth_range": [3, 5]},
            {"activity_id": "date-it",
             "label": "place a document in its context",
             "action": "apply", "acts_on": ["source-set"],
             "depth_range": [1, 2]},
        ],
        "anchor_sources": [
            {"label": "review essays in the field's journals",
             "detail": "published disagreements about a work supply "
                       "difficulty nobody here invented",
             "reachable": True}],
        "register_hint": {"suggested": "analogy_first",
                          "why": "the learner's background is in the "
                                 "sciences, so the standards of evidence here "
                                 "need building before the vocabulary does"},
    }
    doc.update(over)
    return doc


def mastery(concept_id=EIGENVALUE, state="introduced", courses=("linalg",),
            depth_targets=None, **over):
    doc = {
        "schema_version": 1,
        "concept_id": concept_id,
        "courses": list(courses),
        "state": state,
        "depth_targets": depth_targets or [
            {"course_id": c, "depth_target": 3} for c in courses],
        "first_taught": "2026-09-01T09:00:00+00:00",
        "evidence": [],
    }
    doc.update(over)
    return doc


def exposition(concept_id=EIGENVALUE, course_id="linalg", **over):
    """One concept actually being explained.

    Every test that records an attempt now needs one of these, which is the
    point: before this existed, a test could drive a concept from unseen to
    mastered without anything ever claiming to have taught it, and so could
    the real system.
    """
    doc = {
        "schema_version": 1,
        "exposition_id": "x1",
        "course_id": course_id,
        "lesson_id": "l1",
        "concept_id": concept_id,
        "delivered_at": "2026-09-01T09:00:00+00:00",
        "register": "technical_with_gloss",
        "rungs": [
            {"rung": 3,
             "said": "Take the smallest case with the feature in it and "
                     "work it through by hand before generalising."},
            {"rung": 4,
             "said": "The formal statement, written out, with each symbol "
                     "named as it first appears."},
        ],
        "terms": [{"term": "the term under discussion",
                   "operational_definition": "how you would compute or "
                                             "check it, in one line"}],
        "boundary": "Where this stops holding, and the neighbouring idea it "
                    "is most often confused with.",
        "led_by": "exposition_first",
    }
    doc.update(over)
    return doc


def teach(root_path, concept_id=EIGENVALUE, course="linear-algebra",
          course_id="linalg", **over):
    """Record an explanation the way the system requires, from a test."""
    sys.path.insert(0, str(SCRIPTS))
    import learner as ln
    doc = exposition(concept_id, course_id, **over)
    return ln.main(["--root", str(root_path), "teach", "--course", course,
                    "--data", json.dumps(doc)])


def attempt(**over):
    doc = {
        "schema_version": 1,
        "attempt_id": "a1",
        "course_id": "linalg",
        "lesson_id": "l1",
        "exercise_id": "e1",
        "concept_ids": [EIGENVALUE],
        "kind": "inclass",
        "tier": "anchored",
        "verdict": "pass",
        "graded_by": "script:numeric",
        "form": "derive",
        "submitted_at": "2026-09-01T10:00:00+00:00",
        "evidence_quotes": ["formed the characteristic polynomial correctly"],
        "latency_rating": "effortful",
        "latency_source": "inferred",
    }
    doc.update(over)
    return doc


@pytest.fixture
def root(tmp_path):
    """A fully initialised data root with two courses that share a concept."""
    import zt_state as z
    z.main(["--root", str(tmp_path), "init"])
    z.atomic_write_json(tmp_path / "config.json", config())
    z.atomic_write_json(tmp_path / "concepts.json", registry())
    z.atomic_write_json(tmp_path / "learner" / "profile.json", profile())

    d = tmp_path / "courses" / "linear-algebra"
    d.mkdir(parents=True, exist_ok=True)
    z.atomic_write_json(d / "course.json", course())
    z.atomic_write_json(d / "curriculum.json", curriculum())

    d2 = tmp_path / "courses" / "historiography"
    d2.mkdir(parents=True, exist_ok=True)
    z.atomic_write_json(d2 / "course.json", hist_course())
    z.atomic_write_json(d2 / "curriculum.json", hist_curriculum())

    ad = tmp_path / "adapters"
    ad.mkdir(exist_ok=True)
    z.atomic_write_json(ad / "mathematics.json", math_adapter())
    z.atomic_write_json(ad / "history.json", hist_adapter())
    return tmp_path


def hist_course(**over):
    """A humanities course whose practice lands on sources rather than on
    software. Its goal deliberately does NOT name a particular text, so a
    missing source is answerable with a constructed stand-in; the test that
    needs the opposite ruling builds its own goal."""
    doc = course(
        course_id="hist", slug="historiography",
        title="Reading historians",
        goal="Reconstruct a historian's argument and judge whether the "
             "sources bear it.",
        domain="history",
        adapter_ref="adapters/history.json",
        milestones=[{"date": "2026-10-20",
                     "capability": "Take apart one monograph chapter and "
                                   "name every load-bearing source."}],
        environment={
            "completed_at": "2026-09-05T00:00:00+00:00",
            "required_targets": [
                {"target_id": "source-set", "kind": "primary sources",
                 "named_in_goal": False, "criticality": "required",
                 "why": "source critique has to act on real documents"}],
            "resolution": [{"target_id": "source-set", "reach": "direct",
                            "depth_ceiling": 5, "where": "learner"}],
        })
    doc.update(over)
    return doc


def write_mastery(root_path, rows):
    p = root_path / "learner" / "mastery.jsonl"
    if p.exists():
        p.unlink()
    for r in rows:
        zs.append_jsonl(p, r)
