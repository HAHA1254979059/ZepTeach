"""The progress report.

A report can be accurate and still flattering. Counting concepts at each
state gives a number that rises steadily and says almost nothing about
whether anything was learned. Every test here is about a figure that looks
like progress being printed next to the thing that qualifies it.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import conftest as fx  # noqa: E402
import progress_report as pr  # noqa: E402
import zt_state as zs  # noqa: E402

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def ev(kind, verdict="pass", date="2026-09-10T10:00:00+00:00", **over):
    doc = {"attempt_id": kind + date, "course_id": "linalg", "kind": kind,
           "verdict": verdict, "date": date}
    doc.update(over)
    return doc


def row(concept_id=fx.EIGENVALUE, state="practiced", evidence=None, **over):
    doc = fx.mastery(concept_id, state=state)
    doc["evidence"] = evidence or []
    doc.update(over)
    return doc


class TestWhatTheStatesRestOn:
    def test_in_lesson_work_is_counted_separately(self):
        """It is the evidence that says least, so it never merges into a
        total with the rest."""
        out = pr.evidence_behind(row(evidence=[ev("inclass"), ev("inclass")]))
        assert out["in_lesson"] == 2
        assert out["delayed"] == 0

    def test_delayed_kinds_are_counted_together(self):
        out = pr.evidence_behind(row(evidence=[
            ev("delayed_retest"), ev("transfer_test"), ev("assessment")]))
        assert out["delayed"] == 3
        assert out["transfer"] == 1

    def test_a_failed_attempt_is_not_evidence_of_anything(self):
        out = pr.evidence_behind(row(evidence=[
            ev("delayed_retest", verdict="fail")]))
        assert out["delayed"] == 0


class TestStatesTheEvidenceDoesNotSupport:
    def test_mastered_on_one_delayed_pass_is_flagged(self):
        rows = [row(state="mastered", evidence=[ev("delayed_retest")])]
        out = pr.unsupported(rows)
        assert out[0]["needs"] == 2
        assert out[0]["delayed_evidence"] == 1

    def test_consolidating_with_nothing_delayed_is_flagged(self):
        rows = [row(state="consolidating", evidence=[ev("inclass")])]
        assert pr.unsupported(rows)[0]["state"] == "consolidating"

    def test_a_properly_supported_state_is_not_flagged(self):
        rows = [row(state="mastered", evidence=[
            ev("delayed_retest"), ev("transfer_test")])]
        assert pr.unsupported(rows) == []

    def test_it_is_recomputed_rather_than_trusted(self):
        """The state machine refuses these on the way in, so this should
        always be empty. It is checked again because a rule enforced only at
        write time stops catching anything the moment a file is edited by
        hand or written by an older version."""
        src = (SCRIPTS / "progress_report.py").read_text(encoding="utf-8")
        assert "edited by hand" in src


class TestWeakTransfers:
    def test_mastered_on_knowledge_domain_alone_is_called_out(self):
        rows = [row(state="mastered", evidence=[
            ev("delayed_retest"),
            ev("transfer_test", transfer_dimensions=["knowledge_domain"])])]
        out = pr.weak_transfers(rows)
        assert out[0]["dimensions"] == ["knowledge_domain"]

    def test_a_transfer_that_moved_further_is_not_called_out(self):
        rows = [row(state="mastered", evidence=[
            ev("delayed_retest"),
            ev("transfer_test",
               transfer_dimensions=["knowledge_domain",
                                    "functional_context"])])]
        assert pr.weak_transfers(rows) == []

    def test_a_transfer_with_no_dimension_recorded_is_called_out(self):
        rows = [row(state="mastered", evidence=[
            ev("delayed_retest"), ev("transfer_test")])]
        out = pr.weak_transfers(rows)
        assert out[0]["dimensions"] == []
        assert "did not record" in out[0]["note"]


class TestWhatWasGivenUp:
    def test_waved_through_prerequisites_are_listed_with_counts(self):
        """Allowed, and not forgotten. A course built on three bypassed
        prerequisites is a different course from one built on none."""
        rows = [row(downstream={"hold": True, "bypassed": True,
                                "bypass_count": 3,
                                "bypass_reason": "needed the later part"})]
        out = pr.bypasses(rows)
        assert out[0]["times"] == 3
        assert "needed the later part" in out[0]["reason"]

    def test_lowered_depth_targets_come_from_the_course(self):
        course = fx.course()
        course["environment"]["depth_concessions"] = [
            {"concept_id": fx.EIGENVALUE, "from_depth": 4, "to_depth": 3,
             "reason": "no way to practise judging other people's use"}]
        assert pr.depth_given_up(course)[0]["to_depth"] == 3

    def test_no_concessions_reports_an_empty_list_not_nothing(self):
        assert pr.depth_given_up(fx.course()) == []


class TestTaughtAndNeverRetested:
    def test_two_weeks_with_no_delayed_evidence_is_surfaced(self):
        """The quiet failure: covered, felt fine, never came back. It shows
        up nowhere else, because nothing failed."""
        rows = [row(state="practiced",
                    first_taught="2026-09-01T09:00:00+00:00",
                    evidence=[ev("inclass")])]
        out = pr.never_retested(rows, NOW)
        assert out[0]["days_since_taught"] == 19

    def test_something_recently_taught_is_not_surfaced(self):
        rows = [row(state="practiced",
                    first_taught="2026-09-18T09:00:00+00:00",
                    evidence=[ev("inclass")])]
        assert pr.never_retested(rows, NOW) == []

    def test_something_already_retested_is_not_surfaced(self):
        rows = [row(state="consolidating",
                    first_taught="2026-09-01T09:00:00+00:00",
                    evidence=[ev("delayed_retest")])]
        assert pr.never_retested(rows, NOW) == []


class TestTheWholeReport:
    def build(self, root, rows):
        fx.write_mastery(root, rows)
        return pr.build(root, "linear-algebra", NOW)

    def test_it_says_what_it_was_computed_from(self, root):
        r = self.build(root, [row()])
        assert "recorded attempts" in r["computed_from"]
        assert any("impression" in s for s in r["not_computed_from"])

    def test_qualifications_are_a_required_section_not_an_extra(self, root):
        """Present even when empty, so that an empty one is a statement
        rather than an omission."""
        r = self.build(root, [row(state="introduced",
                                  first_taught="2026-09-19T09:00:00+00:00")])
        assert set(r["qualifications"]) == {
            "states_the_evidence_does_not_support",
            "mastered_on_a_weak_transfer",
            "prerequisites_waved_through",
            "depth_targets_lowered",
            "taught_then_never_retested"}

    def test_the_rendered_report_prints_the_qualification(self, root):
        rows = [row(state="mastered", evidence=[ev("delayed_retest")])]
        out = pr.render(self.build(root, rows))
        assert "QUALIFICATIONS" in out
        assert "not supported by their evidence" in out

    def test_a_clean_course_says_none_rather_than_hiding_the_section(self,
                                                                    root):
        clean = row(state="introduced",
                    first_taught="2026-09-19T09:00:00+00:00")
        out = pr.render(self.build(root, [clean]))
        assert "QUALIFICATIONS" in out
        assert "none" in out

    def test_in_lesson_only_concepts_carry_their_caveat_in_the_text(self,
                                                                    root):
        rows = [row(state="practiced", evidence=[ev("inclass")])]
        out = pr.render(self.build(root, rows))
        assert "says little about next week" in out

    def test_the_closing_line_states_the_basis(self, root):
        out = pr.render(self.build(root, [row()]))
        assert "No one's impression" in out

    def test_milestones_are_reported_against_the_clock(self, root):
        r = self.build(root, [row()])
        assert r["milestones"][0]["days_away"] == 25
        assert r["milestones"][0]["met"] is False


class TestCli:
    def run(self, argv):
        try:
            return pr.main(argv)
        except SystemExit as exc:
            return exc.code

    def test_a_missing_course_exits_five(self, root):
        assert self.run(["--root", str(root), "--course", "ghost"]) == \
            zs.EXIT_NOT_FOUND

    def test_it_runs_on_a_real_course(self, root, capsys):
        fx.write_mastery(root, [row()])
        assert self.run(["--root", str(root), "--course",
                         "linear-algebra"]) == zs.EXIT_OK
        assert "PROGRESS" in capsys.readouterr().out
