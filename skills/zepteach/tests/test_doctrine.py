"""The doctrine files have to earn their place in context.

Two rules from PHILOSOPHY.md are enforced here:

  1. every doctrine file states which principle it implements - a file that
     cannot name one should not exist
  2. the files stay small, because every one of them is paid for in context
     on the turn it loads

Plus the specific requirements the research pass added: productive failure and
interleaving must actually appear in the mode router, and the explanation
ladder must be trimmable rather than one path for everyone.
"""

import re
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
REF_DIR = SKILL_DIR / "references"
PLUGIN_ROOT = SKILL_DIR.parents[1]

sys.path.insert(0, str(SKILL_DIR / "scripts"))
import constants as K  # noqa: E402
import route as rt  # noqa: E402


def doctrine_files():
    return sorted(p for p in REF_DIR.rglob("*.md"))


def text(p):
    return p.read_text(encoding="utf-8")


class TestEveryFileNamesItsPrinciple:
    def test_there_are_doctrine_files_to_check(self):
        assert len(doctrine_files()) >= 6

    @pytest.mark.parametrize("path", doctrine_files(), ids=lambda p: p.name)
    def test_it_states_what_it_implements(self, path):
        head = "\n".join(text(path).splitlines()[:12])
        assert re.search(r">\s*Implements:", head), (
            path.name + " does not say which principle it implements")

    @pytest.mark.parametrize("path", doctrine_files(), ids=lambda p: p.name)
    def test_it_names_a_principle_that_exists(self, path):
        head = "\n".join(text(path).splitlines()[:12])
        claim = head.split("Implements:")[1]
        assert re.search(r"(principle|engineering principle)\s*\d", claim), (
            path.name + " names no numbered principle")

    def test_the_philosophy_it_points_at_is_really_there(self):
        """The headers above are worthless if they cite principles that do not
        exist, which is exactly what happens when the philosophy is renumbered
        and the doctrine is not."""
        phil = text(PLUGIN_ROOT / "PHILOSOPHY.md")
        for n in range(1, 9):
            assert "### Principle " + str(n) + " " in phil, n
            assert "### Engineering " + str(n) + " " in phil, n
        assert "### Engineering 9 " in phil


class TestTheyStaySmall:
    """A lesson loads several of these at once, and length is a real cost.

    The ceilings are switched off while the doctrine is being written.
    Writing to fit a ceiling shapes the writing, and it was already cutting
    content before that content had been judged on its merits. They stay
    recorded and measured; enforcement returns once the doctrine is complete,
    when compressing means editing rather than omitting.
    """

    @pytest.mark.parametrize("path", doctrine_files(), ids=lambda p: p.name)
    def test_no_single_file_is_bloated(self, path):
        n = len(text(path).splitlines())
        if not K.enforced("doctrine_file_max_lines"):
            pytest.skip(str(n) + " lines, ceiling " +
                        str(K.DOCTRINE_FILE_MAX_LINES) + ", not enforced yet")
        assert n <= K.DOCTRINE_FILE_MAX_LINES, path.name

    def test_a_lesson_does_not_load_a_book(self):
        res = rt.resolve("lesson")
        total = sum(len(text(REF_DIR / f).splitlines())
                    for f in res["read"] if (REF_DIR / f).exists())
        if not K.enforced("lesson_doctrine_max_lines"):
            pytest.skip(str(total) + " lines, ceiling " +
                        str(K.LESSON_DOCTRINE_MAX_LINES) +
                        ", not enforced yet")
        assert total <= K.LESSON_DOCTRINE_MAX_LINES

    def test_a_switched_off_ceiling_says_why(self):
        """Switched off is a decision with a reason, not a limit somebody
        quietly stopped checking."""
        for name in ("lesson_doctrine_max_lines", "doctrine_file_max_lines",
                     "skill_file_max_lines"):
            if not K.enforced(name):
                assert K.TUNABLE[name].get("deferred_because"), name

    def test_the_skill_file_is_a_routing_table_not_a_manual(self):
        s = text(SKILL_DIR / "SKILL.md")
        if K.enforced("skill_file_max_lines"):
            assert len(s.splitlines()) <= K.SKILL_FILE_MAX_LINES
        # doctrine must live in the routed files, not inline here
        for leaked in ("explanation ladder", "现象 → 直觉图像",
                       "productive_failure", "六个必需章节"):
            assert leaked not in s, "doctrine leaked into SKILL.md: " + leaked


class TestTheLimitsThemselvesHaveASource:
    """The rule is that a number without a stated source may not exist. The
    ledger enforcing it only ever audited numbers that had been put into it,
    so three limits written straight into the assertions above sat unsourced
    for the whole project. This closes that: the thresholds this file checks
    against must come from the ledger, and the ledger requires a reason."""

    def test_the_size_limits_come_from_the_ledger(self):
        src = text(Path(__file__))
        body = src.split("class TestTheLimitsThemselvesHaveASource")[0]
        bare = re.findall(r"<=\s*(\d+)", body)
        assert bare == [], (
            "a size limit is written as a literal instead of coming from "
            "constants.py: " + ", ".join(bare))

    def test_each_one_says_why_it_is_that_number(self):
        for name in ("lesson_doctrine_max_lines", "doctrine_file_max_lines",
                     "skill_file_max_lines"):
            spec = K.TUNABLE[name]
            assert spec["kind"] in K.KINDS
            assert len(spec["why"]) > 80, name

    def test_the_lesson_budget_admits_that_lines_are_a_stand_in(self):
        """Lines are not what costs anything; tokens are. Counting lines is a
        concession to having no tokenizer and no dependencies, and the entry
        has to say so rather than implying the figure is precise."""
        spec = K.TUNABLE["lesson_doctrine_max_lines"]
        assert "token" in (spec["why"] + spec.get("caveat", "")).lower()


class TestTheResearchDrivenRequirements:
    def test_the_router_actually_routes_to_productive_failure(self):
        s = text(REF_DIR / "mode-router.md")
        assert "productive_failure" in s
        assert "conceptual" in s
        # and states when it must NOT be used
        assert re.search(r"Do not use it for", s)

    def test_interleaving_is_mandatory_not_optional(self):
        s = text(REF_DIR / "mode-router.md")
        assert "interleaved_drill" in s
        assert "mandatory" in s.lower()
        # the prompt must not reveal the method, or it is not interleaving
        assert "not announce" in s or "does not reveal" in s

    def test_explain_back_is_required_after_new_material(self):
        s = text(REF_DIR / "mode-router.md")
        assert "Explain-back is not optional" in s

    def test_the_explanation_ladder_is_trimmable(self):
        s = text(REF_DIR / "teaching-contract.md")
        assert "trimmable" in s
        # each register starts at a different rung
        assert "terse_technical`: start at" in s
        assert "analogy_first`: start at" in s

    def test_the_boundary_rung_is_never_trimmed(self):
        s = text(REF_DIR / "teaching-contract.md")
        assert "mandatory in every register" in s

    def test_feedback_timing_is_decided_per_item_type(self):
        s = text(REF_DIR / "teaching-contract.md")
        assert "Feedback timing" in s
        for kind in ("anchored", "variant", "Modeling", "transfer test"):
            assert kind in s

    def test_the_language_rules_are_stated(self):
        """Tone and honesty were covered; how the sentences read was not, and
        a model with no instruction on that drifts towards writing that
        sounds impressive and teaches less."""
        s = text(REF_DIR / "persona-zep.md")
        assert "Main point first" in s
        assert "No decorative metaphor" in s
        assert "No emoji" in s
        assert "No jargon the learner has not been given" in s

    def test_teaching_analogies_are_not_caught_by_the_metaphor_ban(self):
        """Two rules that look contradictory. Without the distinction stated,
        one of them gets ignored, and it will be whichever is less convenient
        at the time."""
        s = text(REF_DIR / "persona-zep.md")
        assert "not a decorative metaphor and is not banned" in s
        assert "cashed out" in s

    def test_the_persona_cannot_touch_a_verdict(self):
        s = text(REF_DIR / "persona-zep.md")
        assert "does not set the standards" in s
        assert "grader is not Zep" in s

    def test_empty_praise_is_banned_with_examples(self):
        s = text(REF_DIR / "persona-zep.md")
        assert "No empty praise" in s
        assert "good question" in s

    def test_notes_have_the_anti_ledger_rule(self):
        s = text(REF_DIR / "note-doctrine.md")
        assert "goes to the journal by default" in s
        assert "用户问了" in s  # named as forbidden

    def test_the_digest_says_what_may_be_dropped(self):
        s = text(REF_DIR / "context-budget.md")
        assert "What may be dropped after a checkpoint" in s
        assert "must not be dropped" in s

    def test_the_protocol_records_what_was_explained(self):
        """This test used to assert the opposite, and the sentence it
        asserted was the defect.

        It required the protocol to say that "taught" means the lesson has
        begun rather than that an explanation has been delivered. That made
        starting a lesson and teaching it one recorded event, so the second
        could go missing without anything noticing - and across three
        lessons of real use, it did.
        """
        s = text(REF_DIR / "session-protocol.md")
        assert "learner.py teach" in s
        assert "exposition" in s
        assert "the lesson has begun, not that an" in s, (
            "the old reading should be quoted as the thing that was wrong, "
            "not silently dropped")
        assert "one concept, one explanation" in s.lower()


class TestTheRouteMatchesWhatExists:
    def test_written_files_are_reported_as_written(self):
        res = rt.resolve("lesson")
        for f in res["read"]:
            exists = (REF_DIR / f).exists()
            assert (f in res["missing"]) != exists, f

    def test_the_audit_counts_what_is_on_disk(self, capsys):
        rt.main(["audit"])
        out = capsys.readouterr().out
        written = len([l for l in out.splitlines() if l.startswith("ok ")])
        assert written == len([p for p in doctrine_files()
                               if p.parent == REF_DIR])
