"""Every item has to decide how it will be answered, and write that down.

The defect this prevents is not that typing answers is bad. It is that
nothing in the data model had a place to record how an item was to be
answered, so the decision lived only in whoever was teaching at the time.

In the first real use that produced an interactive form, which the learner
liked and said so. Twenty minutes later it was gone and the answers were back
to being typed into chat, not because anyone decided that but because nothing
remembered. The learner had to notice and complain, and the same thing
happened again later with a different item. Meanwhile the form itself came
from a tool belonging to the host application, so on any other host the
better experience did not exist at all.

Both halves of that are the same shape as every other defect this project has
found: a good decision with nowhere to live and nothing able to refuse an
item that ignored it.
"""

import json

import pytest

import conftest as fx
import exercise as ex
import zt_state as zs
from sandbox import Refused


def refusal(fn):
    with pytest.raises(Refused) as e:
        fn()
    return e.value


def item(**over):
    doc = {
        "schema_version": 1,
        "exercise_id": "e1",
        "course_id": "linalg",
        "concept_ids": [fx.EIGENVALUE],
        "tier": "variant",
        "prompt": "a question",
        "grader": {"type": "numeric", "tolerance": 0.01},
        "response": {"mode": "free_text"},
    }
    doc.update(over)
    return doc


class TestAnItemWithoutAnAnswerShapeCannotBeIssued:
    def test_no_response_block_is_refused(self):
        doc = item()
        doc.pop("response")
        r = refusal(lambda: ex.check_issuable(doc))
        assert r.code == "EXE020"
        assert "without anyone choosing that" in r.suggestion

    def test_the_schema_requires_it_too(self):
        """Belt and braces on purpose. The schema stops a bad item being
        written down; the refusal stops one being put in front of somebody.
        An item can reach a learner without ever being written to disk."""
        assert "response" in zs.load_schema("exercise")["required"]

    def test_a_declared_mode_comes_back_out_of_the_check(self):
        """So that whatever is rendering the item is told what to render,
        rather than deciding for itself and then forgetting."""
        got = ex.check_issuable(item(response={"mode": "choice", "options": [
            {"option_id": "a", "text": "one"},
            {"option_id": "b", "text": "two"}]}))
        assert got["response_mode"] == "choice"


class TestAChoiceItemHasToOfferARealChoice:
    def test_one_option_is_not_a_choice(self):
        r = refusal(lambda: ex.check_issuable(item(response={
            "mode": "choice",
            "options": [{"option_id": "a", "text": "the answer"}]})))
        assert r.code == "EXE021"

    def test_two_options_saying_the_same_thing_are_refused(self):
        r = refusal(lambda: ex.check_issuable(item(response={
            "mode": "choice",
            "options": [{"option_id": "a", "text": "Perpendicular"},
                        {"option_id": "b", "text": "perpendicular "}]})))
        assert r.code == "EXE022"
        assert "shrink the real choice" in r.suggestion

    def test_a_distractor_can_carry_the_belief_that_leads_to_it(self):
        """Written when the item is written. Otherwise a wrong choice gets
        answered by repeating the right answer, which teaches nothing about
        why the wrong one was attractive."""
        doc = item(response={"mode": "choice", "options": [
            {"option_id": "a", "text": "the gradient has the shape of w"},
            {"option_id": "b", "text": "the gradient is a single number",
             "why_wrong": "summing the partial derivatives instead of "
                          "collecting them"}]})
        assert ex.check_issuable(doc)["ok"]
        assert zs.validate_doc(doc, "exercise") == []


class TestFillBlanksHasToNameItsBlanks:
    def test_unnamed_blanks_are_refused(self):
        r = refusal(lambda: ex.check_issuable(
            item(response={"mode": "fill_blanks"})))
        assert r.code == "EXE023"
        assert "cannot be stored as data" in r.suggestion

    def test_named_blanks_pass(self):
        assert ex.check_issuable(item(response={
            "mode": "fill_blanks",
            "fields": [{"field_id": "step1", "label": "the dot product"},
                       {"field_id": "step2", "label": "the norm"}]}))["ok"]

    def test_a_grid_has_a_declared_shape(self):
        bad = item(response={"mode": "fill_blanks", "fields": [
            {"field_id": "grid", "label": "value",
             "grid": {"rows": 0, "columns": 2}}]})
        assert refusal(lambda: ex.check_issuable(bad)).code == "EXE025"

    def test_a_grid_obeys_notation_input_preference(self):
        grid = item(response={"mode": "fill_blanks", "fields": [
            {"field_id": "grid", "label": "value",
             "grid": {"rows": 2, "columns": 2}}]})
        assert refusal(lambda: ex.check_issuable(
            grid, notation_input=["photographs"])).code == "EXE024"


class TestNotationIsNotTypedByPeopleWhoSaidTheyWouldNotTypeIt:
    """The learner said, in the middle of a lesson, that typing formulas was
    painful and that these could be multiple choice. Nothing could act on
    that, because the only place to put it was a free-text constraints list,
    where `formulas must be LaTeX` reads clearly and gates nothing.
    """

    NOTATION = {"mode": "free_text", "expects_notation": True}

    def test_asking_for_typed_notation_from_someone_who_photographs_it(self):
        r = refusal(lambda: ex.check_issuable(
            item(response=self.NOTATION),
            notation_input=["photographs", "picks_from_options"]))
        assert r.code == "EXE024"
        assert "measures their patience" in r.suggestion

    def test_someone_who_types_markup_is_asked_normally(self):
        assert ex.check_issuable(item(response=self.NOTATION),
                                 notation_input=["types_markup"])["ok"]

    def test_the_same_item_as_a_choice_is_fine_for_anyone(self):
        doc = item(response={
            "mode": "choice", "expects_notation": True,
            "options": [{"option_id": "a", "text": "2(w.x - y)x"},
                        {"option_id": "b", "text": "2(w.x - y)"}]})
        assert ex.check_issuable(doc, notation_input=["photographs"])["ok"]

    def test_a_photograph_is_a_way_of_answering(self):
        assert ex.check_issuable(
            item(response={"mode": "upload", "expects_notation": True}),
            notation_input=["photographs"])["ok"]

    def test_one_field_needing_notation_is_enough_to_trigger_the_check(self):
        r = refusal(lambda: ex.check_issuable(
            item(response={"mode": "fill_blanks", "fields": [
                {"field_id": "a", "label": "in words"},
                {"field_id": "b", "label": "the derivative",
                 "expects_notation": True}]}),
            notation_input=["picks_from_options"]))
        assert r.code == "EXE024"

    def test_with_nothing_known_about_the_learner_nothing_is_checked(self):
        """The honest behaviour. A caller that cannot say how this person
        supplies notation has not established that this item asks too much
        of them either."""
        assert ex.check_issuable(item(response=self.NOTATION))["ok"]

    def test_the_profile_has_somewhere_to_put_the_answer(self):
        props = zs.load_schema("profile")["properties"]
        assert "notation_input" in props
        assert "picks_from_options" in props["notation_input"]["items"]["enum"]


class TestTheQuestionsThemselvesAreKept:
    def test_issuing_an_item_writes_it_down(self, root, capsys):
        path = root / "item.json"
        path.write_text(json.dumps(item()), encoding="utf-8")
        code = ex.main(["issue", "--root", str(root),
                        "--course", "linear-algebra", "--file", str(path)])
        assert code == zs.EXIT_OK
        kept = zs.read_jsonl(root / "courses" / "linear-algebra" /
                             "exercises.jsonl")
        assert [k["exercise_id"] for k in kept] == ["e1"]

    def test_a_refused_item_is_not_written_down(self, root, capsys):
        doc = item()
        doc.pop("response")
        path = root / "item.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        code = ex.main(["issue", "--root", str(root),
                        "--course", "linear-algebra", "--file", str(path)])
        assert code in (zs.EXIT_GATE, zs.EXIT_VALIDATION)
        assert zs.read_jsonl(root / "courses" / "linear-algebra" /
                             "exercises.jsonl") == []

    def test_keeping_them_is_what_lets_teaching_be_checked_against_them(
            self, root):
        """The two halves of this change meet here.

        An explanation has to exist somewhere other than inside the questions
        asked about the concept. That check needs the questions, and until
        items were kept, the questions existed only in the conversation and
        the check had nothing to read.
        """
        import learner as ln
        said = "An eigenvalue is a scale factor along a direction the map "
        said += "leaves alone."
        path = root / "item.json"
        path.write_text(json.dumps(item(
            prompt=said + " Which value is it here?")), encoding="utf-8")
        ex.main(["issue", "--root", str(root), "--course", "linear-algebra",
                 "--file", str(path)])

        code = ln.main(["--root", str(root), "teach", "--course",
                        "linear-algebra", "--data", json.dumps(
                            fx.exposition(rungs=[{"rung": 3, "said": said}]))])
        assert code == zs.EXIT_GATE
