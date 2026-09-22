"""One learner input contract across session questions and exercises."""

import json

import interaction as it
import route as rt
import zt_state as zs


def test_energy_is_a_real_choice_and_accepts_plain_text():
    request = it.energy_request()
    assert it.validate_request(request) == []
    assert [o["option_id"] for o in request["response"]["options"]] == [
        "low", "normal", "high"]
    fallback = it.plain_text(request)
    assert "今天状态怎么样" in fallback
    assert "直接说明" in fallback


def test_exercise_view_does_not_disclose_grading_or_wrong_answer_reasons():
    source = {
        "exercise_id": "probe-1", "prompt": "Choose the next step",
        "grader": {"type": "numeric", "expected": "SECRET_ANSWER"},
        "response": {"mode": "choice", "options": [
            {"option_id": "a", "text": "First path", "why_wrong": "SECRET_REASON"},
            {"option_id": "b", "text": "Second path"}]},
    }
    shown = it.from_exercise(source)
    page = it.inline_html(shown)
    assert "SECRET_ANSWER" not in page
    assert "SECRET_REASON" not in page
    assert "First path" in page
    assert "sendFollowUpMessage" in page
    assert "request_id" in page and "values" in page


def test_multipart_probe_keeps_named_inputs_and_escapes_script_end():
    request = {"request_id": "probe", "prompt": "<script>bad</script>",
               "response": {"mode": "fill_blanks", "fields": [
                   {"field_id": "dot", "label": "点积"},
                   {"field_id": "norm", "label": "模长"}]}}
    assert it.validate_request(request) == []
    page = it.inline_html(request)
    assert "</script>bad" not in page
    assert "\\u003cscript>" in page
    assert "dot" in page and "norm" in page
    fallback = it.plain_text(request)
    assert "dot: 点积" in fallback and "norm: 模长" in fallback


def test_notation_and_compact_grid_survive_exercise_conversion():
    source = {"exercise_id": "e", "prompt": r"Find \(x^2\)",
              "answer_key": "private answer",
              "response": {"mode": "fill_blanks", "fields": [
                  {"field_id": "formula", "label": "Expression",
                   "expects_notation": True, "symbols": ["^", "="]},
                  {"field_id": "grid", "label": "Grid",
                   "grid": {"rows": 2, "columns": 2}}]}}
    shown = it.from_exercise(source)
    assert it.validate_request(shown) == []
    page = it.inline_html(shown)
    assert "private answer" not in page
    assert "zt-keypad" in page and "MathJax" in page
    assert shown["response"]["fields"][1]["grid"] == {
        "rows": 2, "columns": 2}


def test_invalid_choice_or_unnamed_part_is_refused_before_rendering():
    bad_choice = {"request_id": "x", "prompt": "Choose",
                  "response": {"mode": "choice", "options": [
                      {"option_id": "a", "text": "Only one"}]}}
    assert it.validate_request(bad_choice)
    bad_parts = {"request_id": "x", "prompt": "Answer",
                 "response": {"mode": "fill_blanks", "fields": [
                     {"field_id": "same", "label": "One"},
                     {"field_id": "same", "label": "Two"}]}}
    assert "field ids must be unique" in it.validate_request(bad_parts)


def test_view_is_written_only_to_learner_root(tmp_path, capsys):
    code = it.main(["energy", "--root", str(tmp_path)])
    assert code == zs.EXIT_OK
    files = list((tmp_path / "interaction_views").glob("*.html"))
    assert len(files) == 1
    assert "INLINE" in capsys.readouterr().out
    assert "role=\"group\"" in files[0].read_text(encoding="utf-8")
    assert zs.validate_root(tmp_path) == []


def test_upload_uses_attachment_fallback_without_fake_view(tmp_path, capsys):
    request = {"request_id": "paper", "prompt": "Send your work",
               "response": {"mode": "upload"}}
    source = tmp_path / "request.json"
    source.write_text(json.dumps(request), encoding="utf-8")
    assert it.main(["request", "--file", str(source), "--root", str(tmp_path)]) == 0
    assert "附件" in capsys.readouterr().out
    assert not (tmp_path / "interaction_views").exists()


def test_relevant_routes_read_the_same_input_contract():
    for intent in ("setup1", "course-new", "setup2", "replan", "lesson",
                   "exercise", "review", "sidequest", "assess"):
        assert "interaction-contract.md" in rt.resolve(intent)["read"]
