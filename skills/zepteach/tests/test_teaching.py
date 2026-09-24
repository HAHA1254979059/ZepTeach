"""The teaching side has to prove itself, the way the marking side does.

Everything in this file exists because of one real failure, and the failure
is worth stating precisely because it did not look like a failure while it
was happening.

Every gate in this plugin checked the learner. A pass had to quote the
learner's answer. A promotion needed a delayed retest and a transfer test.
An item without a marking spec could not be issued. Nothing checked the
teacher: marking a concept as taught was one command with three string
arguments and no content in it.

Across three lessons of real use, the result was twenty-five assessment items
and almost no teaching. The few things the teacher said in chat were mostly
"the form is above, fill it in". The learner eventually wrote that concepts
were being tested that had never been explained, and that arithmetic slips
were being read as not having understood. Every gate was green throughout.

So each test below names one way the gap could reopen.
"""

import json

import pytest

import conftest as fx
import exercise as ex
import learner as ln
import teaching as tp
import zt_state as zs
from sandbox import Refused


def refusal(fn):
    with pytest.raises(Refused) as e:
        fn()
    return e.value


class TestAnExplanationHasToSayWhatWasSaid:
    def test_a_complete_one_is_accepted(self):
        got = tp.check_exposition(fx.exposition())
        assert got["rungs_covered"] == [3, 4]

    def test_nothing_recorded_as_said_is_refused(self):
        r = refusal(lambda: tp.check_exposition(fx.exposition(rungs=[])))
        assert r.code == "EXP001"

    def test_no_boundary_is_refused(self):
        """Rung 5 is mandatory in every register, and was mandatory in the
        doctrine long before anything could refuse its absence."""
        r = refusal(lambda: tp.check_exposition(fx.exposition(boundary="")))
        assert r.code == "EXP002"
        assert "confused with" in r.suggestion

    def test_an_analogy_that_is_not_bounded_is_refused(self):
        r = refusal(lambda: tp.check_exposition(fx.exposition(
            analogies=[{"mapping": "it is like a spring", "stops_where": ""}])))
        assert r.code == "EXP003"

    def test_a_term_introduced_without_a_usable_definition_is_refused(self):
        r = refusal(lambda: tp.check_exposition(fx.exposition(
            terms=[{"term": "orthogonal", "operational_definition": "  "}])))
        assert r.code == "EXP004"

    def test_a_register_that_does_not_gloss_may_skip_definitions(self):
        got = tp.check_exposition(
            fx.exposition(register="terse_technical",
                          terms=[{"term": "orthogonal",
                                  "operational_definition": " "}]),
            require_operational_definition=False)
        assert got["ok"]

    def test_starting_below_the_register_is_allowed_but_said_out_loud(self):
        got = tp.check_exposition(fx.exposition(
            register="terse_technical",
            rungs=[{"rung": 1, "said": "here is the phenomenon"}]))
        assert got["started_below_register"] == [1]
        assert "register is wrong" in got["note"]

    def test_intuition_first_must_actually_supply_intuition(self):
        r = refusal(lambda: tp.check_exposition(
            fx.exposition(register="analogy_first")))
        assert r.code == "EXP006"
        good = fx.exposition(register="analogy_first", rungs=[
            {"rung": 1, "said": "The problem this solves is visible here."},
            {"rung": 3, "said": "One small worked case."},
            {"rung": 4, "said": "Here is the formal rule."}])
        assert tp.check_exposition(good)["ok"]

    def test_beginner_cannot_jump_from_intuition_to_formalism(self):
        r = refusal(lambda: tp.check_exposition(fx.exposition(
            register="analogy_first", rungs=[
                {"rung": 1, "said": "The purpose."},
                {"rung": 4, "said": "A full formula."}])))
        assert r.code == "EXP007"


class TestAnExplanationMustExistOutsideTheQuestions:
    """The one that catches what actually happened.

    The observed move was not skipping the explanation outright. It was
    folding the definition into the stem of the question being marked: "the
    prior is your belief before the evidence; so which quantity is the prior
    here?" That reads like teaching. The learner has to extract the
    definition from the item they are being assessed on, which is the
    opposite of having been taught it.
    """

    SAID = "A prior is what you believed before the evidence arrived."

    def _expo(self):
        return fx.exposition(rungs=[{"rung": 2, "said": self.SAID}])

    def test_an_explanation_that_only_lives_in_the_question_is_refused(self):
        prompt = self.SAID + " So which quantity here is the prior?"
        r = refusal(lambda: tp.check_exposition(self._expo(), [prompt]))
        assert r.code == "EXP005"
        assert "being marked" in r.suggestion

    def test_the_same_words_said_somewhere_else_are_fine(self):
        got = tp.check_exposition(
            self._expo(), ["Which quantity here is the prior?"])
        assert got["ok"]

    def test_one_rung_outside_the_questions_is_enough(self):
        expo = fx.exposition(rungs=[
            {"rung": 2, "said": self.SAID},
            {"rung": 4, "said": "Formally, it is the distribution over the "
                                "hypothesis before conditioning."}])
        assert tp.check_exposition(expo, [self.SAID + " So which is it?"])["ok"]

    def test_with_no_questions_supplied_the_check_cannot_run(self):
        """Stated rather than left implicit. A check that silently does
        nothing when its input is missing is the shape of every gate in this
        project that turned out not to exist."""
        assert tp.check_exposition(self._expo(), [])["ok"]


class TestNothingIsMarkedUntilSomethingWasTaught:
    def _attempt(self, **over):
        return fx.attempt(**over)

    def test_recording_an_attempt_with_no_explanation_on_file_is_refused(
            self, root, capsys):
        code = ln.main(["--root", str(root), "record", "--course",
                        "linear-algebra", "--data",
                        json.dumps(self._attempt())])
        assert code == zs.EXIT_GATE
        err = capsys.readouterr().err
        assert "nothing on file explains" in err
        assert ln.load_mastery(root) == []

    def test_a_probe_on_something_untaught_is_still_allowed(self, root):
        """Productive failure has to survive this. Being handed something
        untaught, failing, and being explained into the gap is a deliberate
        order and often the better one; the defect was never that it
        happened, it was that the explanation afterwards never arrived."""
        code = ln.main(["--root", str(root), "record", "--course",
                        "linear-algebra", "--data",
                        json.dumps(self._attempt(kind="probe",
                                                 verdict="fail"))])
        assert code == zs.EXIT_OK

    def test_teaching_first_then_recording_works(self, root):
        assert fx.teach(root) == zs.EXIT_OK
        code = ln.main(["--root", str(root), "record", "--course",
                        "linear-algebra", "--data",
                        json.dumps(self._attempt())])
        assert code == zs.EXIT_OK
        assert ln.load_mastery(root)[0]["state"] != "unseen"

    def test_an_explanation_recorded_afterwards_does_not_count(
            self, root, capsys):
        """Otherwise the whole thing is satisfiable in arrears: assess all
        session, explain everything at the end, and every attempt in it
        becomes retroactively taught."""
        fx.teach(root, delivered_at="2026-09-30T10:00:00+00:00")
        capsys.readouterr()
        code = ln.main(["--root", str(root), "record", "--course",
                        "linear-algebra", "--data",
                        json.dumps(self._attempt(
                            submitted_at="2026-09-01T10:00:00+00:00"))])
        assert code == zs.EXIT_GATE

    def test_the_explanation_is_kept_where_it_can_be_read_back(self, root):
        fx.teach(root)
        rows = ln.load_expositions(root)
        assert len(rows) == 1
        assert rows[0]["concept_id"] == fx.EIGENVALUE
        assert rows[0]["boundary"]

    def test_a_thin_explanation_never_reaches_disk(self, root, capsys):
        # whitespace rather than empty: the schema catches an empty string
        # on its own, and what is being tested here is the semantic check
        # behind it, which is the one that can be argued with
        code = ln.main(["--root", str(root), "teach", "--course",
                        "linear-algebra", "--data",
                        json.dumps(fx.exposition(boundary="   "))])
        assert code == zs.EXIT_GATE
        assert "EXP002" in capsys.readouterr().err
        assert ln.load_expositions(root) == []
        assert ln.load_mastery(root) == []

    def test_teaching_a_concept_the_named_lesson_does_not_contain_is_refused(
            self, root, capsys):
        code = ln.main(["--root", str(root), "teach", "--course",
                        "linear-algebra", "--data",
                        json.dumps(fx.exposition(fx.SOURCE_CRITIQUE,
                                                 lesson_id="l1"))])
        assert code in (zs.EXIT_GATE, zs.EXIT_NOT_FOUND)


class TestTheAuditForRootsWrittenBeforeThis:
    """A rule added today is worth nothing against records written yesterday,
    and the honest way to find that out is to look rather than assume."""

    def test_concepts_marked_taught_with_nothing_behind_them_are_listed(self):
        mastery = [fx.mastery(fx.EIGENVALUE, state="practiced"),
                   fx.mastery(fx.EIGENVECTOR, state="unseen")]
        got = tp.never_explained([], mastery)
        assert [g["concept_id"] for g in got] == [fx.EIGENVALUE]

    def test_once_explained_it_drops_off_the_list(self):
        mastery = [fx.mastery(fx.EIGENVALUE, state="practiced")]
        assert tp.never_explained([fx.exposition()], mastery) == []

    def test_explanations_that_would_be_refused_today_are_findable(self):
        rows = [fx.exposition(), fx.exposition(exposition_id="x2",
                                               boundary="   ")]
        bad = tp.thin(rows)
        assert [b["exposition_id"] for b in bad] == ["x2"]
        assert bad[0]["code"] == "EXP002"


class TestTheTwoSidesAreNowSymmetric:
    def test_both_a_pass_and_an_explanation_have_to_quote_themselves(self):
        """The property this whole file exists to hold.

        Stated as a test so that removing either half fails loudly. A pass
        must point at words in the learner's answer; an explanation must
        point at words the learner was shown, somewhere other than inside the
        question being marked.
        """
        import grade
        assert "evidence_quotes" in zs.load_schema("attempt")["properties"]
        assert "rungs" in zs.load_schema("exposition")["required"]
        assert callable(grade.check_verdict)
        assert callable(tp.check_exposition)

    def test_the_record_gate_reads_explanations_not_a_state_flag(self):
        """The old gate asked the mastery state, which only recorded that a
        content-free command had been called. Asking the teacher whether it
        taught is not a check."""
        import inspect
        src = inspect.getsource(ln.cmd_record)
        assert "untaught_in" in src
        assert "state\", \"unseen\") == \"unseen\"" not in src
