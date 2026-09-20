"""What the second walkthrough found.

Every case here is a rule some doctrine file already stated and no code
enforced, or a number nobody registered. They share a shape: nothing failed,
so nothing surfaced, and the documents went on describing a system that did
not behave that way.

This is the second time that shape has appeared. The first walkthrough found
eleven; these six are the ones that survived writing the rest of the plugin.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import checkers as ck  # noqa: E402
import conftest as fx  # noqa: E402
import constants as K  # noqa: E402
import exercise as ex  # noqa: E402
import notes as nt  # noqa: E402
import practice_reach as pr  # noqa: E402
import progress_report as prg  # noqa: E402
import session as se  # noqa: E402
import zt_state as zs  # noqa: E402
from sandbox import Refused  # noqa: E402

import test_notes as tn  # noqa: E402


def refusal(fn):
    with pytest.raises(Refused) as exc:
        fn()
    return exc.value


class TestDepthIsMeasuredAgainstTheRightPractice:
    """Taking the best action in the course hid the case the check exists
    for: a concept practised only one way, where that way does not reach far
    enough, is not rescued by some other concept being practised better."""

    def support(self):
        return [
            {"action": "apply", "reach": "stand_in", "depth_ceiling": 2,
             "via": []},
            {"action": "construct", "reach": "direct", "depth_ceiling": 5,
             "via": []},
        ]

    def curriculum(self, actions, target):
        return {"schema_version": 1, "course_id": "c", "modules": [
            {"module_id": "m", "title": "m", "lessons": [
                {"lesson_id": "l", "title": "l", "concepts": [
                    {"concept_id": "x.y", "title": "x",
                     "depth_target": target, "exercise_types": actions}]}]}]}

    def test_a_concept_limited_by_its_own_actions_is_flagged(self):
        out = pr.depth_shortfalls(self.support(),
                                  self.curriculum(["apply"], 3))
        assert out[0]["reachable_depth"] == 2
        assert out[0]["measured_against"] == "its own practice"

    def test_a_better_action_elsewhere_does_not_rescue_it(self):
        """The bug: max across every action reported no shortfall here."""
        out = pr.depth_shortfalls(self.support(),
                                  self.curriculum(["apply"], 3))
        assert out != []

    def test_a_concept_whose_actions_reach_far_enough_is_not_flagged(self):
        assert pr.depth_shortfalls(self.support(),
                                   self.curriculum(["construct"], 5)) == []

    def test_a_concept_declaring_no_actions_says_what_it_was_measured_on(
            self):
        """Nothing better can be done with no information, so the result
        says which number it used."""
        out = pr.depth_shortfalls(self.support(),
                                  self.curriculum(None, 5))
        assert out == []
        out = pr.depth_shortfalls(
            [{"action": "apply", "reach": "stand_in", "depth_ceiling": 2,
              "via": []}], self.curriculum(None, 5))
        assert "declares no actions" in out[0]["measured_against"]


class TestAnItemMayNotGoDeeperThanTheTarget:
    """`exercise-engine.md` said items deeper than the target are never set.
    Nothing checked it, and going deeper always feels like thoroughness."""

    def item(self, depth):
        return {"schema_version": 1, "exercise_id": "e", "course_id": "c",
                "concept_ids": ["x.y"], "tier": "variant", "prompt": "q",
                "depth": depth,
                "grader": {"type": "numeric", "tolerance": 0.1}}

    def test_an_item_past_the_target_is_refused(self):
        r = refusal(lambda: ex.check_issuable(self.item(5), {"x.y": 3}))
        assert r.code == "EXE018"
        assert "side branch" in r.suggestion

    def test_an_item_at_the_target_passes(self):
        assert ex.check_issuable(self.item(3), {"x.y": 3})["ok"]

    def test_with_no_targets_supplied_nothing_is_checked(self):
        """A caller that cannot say how deep a concept is meant to go has not
        established that the item is too deep either."""
        assert ex.check_issuable(self.item(5))["ok"]

    def test_the_refusal_names_which_concept_and_its_target(self):
        r = refusal(lambda: ex.check_issuable(self.item(4), {"x.y": 2}))
        assert "x.y is meant to reach 2" in r.message


class TestClosingSaysWhatWasNotSaidBack:
    """The one item every lesson owes was the easiest thing to skip, because
    nothing failed when it was missed."""

    def attempt(self, cid, form=None, **over):
        doc = fx.attempt(concept_ids=[cid], attempt_id="a" + cid)
        if form:
            doc["form"] = form
            doc["exercise_id"] = "explain-back:" + cid
        doc.update(over)
        return doc

    def test_a_concept_worked_on_without_an_explain_back_is_named(self):
        owed = se.owed_at_close([self.attempt(fx.EIGENVALUE)])
        assert owed == [fx.EIGENVALUE]

    def test_a_concept_said_back_is_not_named(self):
        owed = se.owed_at_close([
            self.attempt(fx.EIGENVALUE),
            self.attempt(fx.EIGENVALUE, form="explain_back")])
        assert owed == []

    def test_it_is_reported_rather_than_refused(self):
        """A session can end for reasons unrelated to the lesson, and
        refusing to close would strand records that are already good."""
        src = (SCRIPTS / "session.py").read_text(encoding="utf-8")
        assert "Reported rather than refused" in src
        assert "NOT SAID BACK" in src

    def test_the_message_says_to_carry_them_forward(self):
        src = (SCRIPTS / "session.py").read_text(encoding="utf-8")
        assert "Carry them into the next session" in src


class TestTheReachCheckAgeIsReported:
    """`practice-reach.md` said a stale check says so at the start of a
    session. The brief never looked at it, and the constant was unused."""

    def test_a_fresh_check_says_nothing(self, root):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        zs.atomic_write_json(root / "capabilities.json", {
            "schema_version": 1, "checked_at": now.isoformat(),
            "targets": [], "practice_support": []})
        assert se.reach_staleness(root, now)["say"] == ""

    def test_an_old_check_is_mentioned(self, root):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        old = now - datetime.timedelta(days=K.REACH_RECHECK_DAYS + 5)
        zs.atomic_write_json(root / "capabilities.json", {
            "schema_version": 1, "checked_at": old.isoformat(),
            "targets": [], "practice_support": []})
        out = se.reach_staleness(root, now)
        assert out["stale"] is True
        assert "days ago" in out["say"]

    def test_a_course_that_never_checked_is_mentioned(self, root):
        import datetime
        out = se.reach_staleness(
            root, datetime.datetime.now(datetime.timezone.utc))
        assert "nothing has established" in out["say"]

    def test_it_is_a_note_and_never_a_refusal(self, root):
        src = (SCRIPTS / "session.py").read_text(encoding="utf-8")
        assert "never a refusal" in src
        assert "would be absurd" in src


class TestTheRewriteCountActuallyCounts:
    """The doctrine reads it as a health signal. It was reported and never
    incremented, so it said whatever the caller passed in."""

    def test_a_first_write_is_zero(self, tmp_path):
        out = nt.write(tmp_path, tn.config(tmp_path), tn.note(),
                       tn.sections(), tn.HEADINGS)
        front, _ = nt.parse_markdown(
            Path(out["markdown"]).read_text(encoding="utf-8"))
        assert front["rewrite_count"] == 0

    def test_rewriting_increments_it(self, tmp_path):
        cfg = tn.config(tmp_path)
        nt.write(tmp_path, cfg, tn.note(), tn.sections(), tn.HEADINGS)
        nt.write(tmp_path, cfg, tn.note(), tn.sections(), tn.HEADINGS)
        out = nt.write(tmp_path, cfg, tn.note(), tn.sections(), tn.HEADINGS)
        front, _ = nt.parse_markdown(
            Path(out["markdown"]).read_text(encoding="utf-8"))
        assert front["rewrite_count"] == 2

    def test_the_caller_cannot_understate_it(self, tmp_path):
        """A number the writer passes in is a number the writer can forget,
        and this one is read as evidence that understanding deepened."""
        cfg = tn.config(tmp_path)
        nt.write(tmp_path, cfg, tn.note(rewrite_count=0), tn.sections(),
                 tn.HEADINGS)
        out = nt.write(tmp_path, cfg, tn.note(rewrite_count=0),
                       tn.sections(), tn.HEADINGS)
        front, _ = nt.parse_markdown(
            Path(out["markdown"]).read_text(encoding="utf-8"))
        assert front["rewrite_count"] == 1


class TestTheLastUnregisteredNumber:
    def test_the_never_retested_threshold_is_in_the_ledger(self):
        spec = K.TUNABLE["never_retested_after_days"]
        assert spec["value"] == 14
        assert spec["kind"] == "engineering"

    def test_it_says_how_it_relates_to_the_spacing_floors(self):
        spec = K.TUNABLE["never_retested_after_days"]
        assert str(K.DELAYED_RETEST_MIN_DAYS) in spec["why"]
        assert str(K.TRANSFER_TEST_MIN_DAYS) in spec["why"]

    def test_the_script_reads_it_from_there(self):
        src = (SCRIPTS / "progress_report.py").read_text(encoding="utf-8")
        assert "K.NEVER_RETESTED_AFTER_DAYS" in src
        assert "days >= 14" not in src


class TestNothingElseSlippedIn:
    def test_no_script_compares_against_a_bare_two_digit_number(self):
        """The ledger only audits what was put into it. A literal in a
        comparison never enters, which is how three size limits and this
        threshold stayed unsourced.

        A number that only decides how something is printed is exempt, and
        has to say so on its own line. Putting a truncation width in a ledger
        of learning parameters would make the ledger harder to read and the
        exemption invisible; making it say so keeps both honest.
        """
        import re
        offences = []
        for path in SCRIPTS.glob("*.py"):
            if path.name == "constants.py":
                continue
            for i, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), 1):
                if not re.search(r"[<>]=?\s*\d{2,}", line):
                    continue
                if "K." in line or line.lstrip().startswith("#"):
                    continue
                # Only this exact marker exempts a line. Accepting
                # any comment would let a real threshold be excused
                # by writing anything at all beside it.
                if "layout, not a tunable" in line:
                    continue
                offences.append(path.name + ":" + str(i) + " " +
                                line.strip()[:70])
        assert offences == [], "\n".join(offences)
