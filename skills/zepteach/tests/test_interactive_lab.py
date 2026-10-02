"""Generation and final-reference checks do not assert learner visibility."""

import json

import pytest

import interactive_lab as il

SCENE = '<div role="img" aria-label="Pending sample positions">Pending positions</div>'


def spec(**overrides):
    return dict({"schema_version": 1, "interaction_id": "capacity-test",
                 "learning_thread_id": "test-thread", "lab_id": "capacity", "part_id": "a",
                 "title": "Capacity test", "prompt": "Predict and explain your choice.",
                 "prediction_fields": [{"field_id": "capacity", "label": "Capacity",
                                        "kind": "numeric", "min": 1, "max": 100}]}, **overrides)


def test_shared_shell_and_custom_experiment_do_not_write_progress(tmp_path):
    path = il.build(tmp_path, spec(), '<button class="btn" data-run>Run</button>',
                    "root.querySelector('[data-run]').addEventListener('click', () => lab.perform({id:'run', label:'Run'}, () => ({observed_ui_behavior:'Result shown', values:{count:1}})));", scene=SCENE)
    assert path.is_file()
    assert list(tmp_path.iterdir()) == [tmp_path / "interaction_views"]
    assert "[ZepTeach interaction]" in path.read_text(encoding="utf-8")
    reference = 'visualize' + json.dumps({"path": str(path)}) + ''
    checked = il.check_delivery(path, reference)
    assert checked["reference_verified"] is True
    assert checked["user_visibility"] == "unconfirmed"
    assert checked["controls_verified"] is False
    with pytest.raises(ValueError):
        il.check_delivery(path, "A plain file link to " + str(path))
    with pytest.raises(ValueError):
        il.check_delivery(path, "```text\n" + reference + "\n```")


def test_fields_are_not_tied_to_one_experiment(tmp_path):
    alternative = spec(interaction_id="policy-test", prediction_fields=[
        {"field_id": "policy", "kind": "choice", "label": "Policy", "options": [
            {"value": "a", "label": "First"}, {"value": "b", "label": "Second"}]},
        {"field_id": "assumption", "kind": "text", "label": "Assumption"}])
    first = il.build(tmp_path, spec(), '<div>Current experiment</div>', '', scene=SCENE)
    second = il.build(tmp_path, alternative, '<div>Different experiment</div>', '', scene=SCENE)
    assert first != second
    assert il.check_delivery(second, 'visualize' + json.dumps({"path": str(second)}) + '')["file_verified"]


def test_reserved_fields_and_network_calls_are_refused(tmp_path):
    with pytest.raises(ValueError):
        il.build(tmp_path, spec(prediction_fields=[{"field_id": "reason", "kind": "text", "label": "x"}]), '<div>x</div>', '', scene=SCENE)
    with pytest.raises(ValueError):
        il.build(tmp_path, spec(), '<div>x</div>', "fetch('https://example.invalid')", scene=SCENE)
    with pytest.raises(ValueError):
        il.build(tmp_path, spec(), '<html>page</html>', '', scene=SCENE)


def test_missing_initial_scene_and_utility_overrides_are_refused(tmp_path):
    with pytest.raises(ValueError):
        il.build(tmp_path, spec(), '<div>Controls</div>', '', scene='')
    with pytest.raises(ValueError):
        il.build(tmp_path, spec(), '<style>.btn {padding:99px}</style><div>Controls</div>', '', scene=SCENE)


def test_shared_outcome_scene_cannot_pass_layout_qa_without_semantic_cases(tmp_path):
    artifact = il.build(tmp_path, spec(), '<div>Controls</div>',
                        'const view = ZepTeachOutcome.mount(root.querySelector("[data-zt-scene]"));', scene=SCENE)
    with pytest.raises(ValueError, match='semantic QA'):
        il.verify_qa(artifact, {})


def test_preview_acceptance_requires_both_phases_and_actual_widths(tmp_path):
    import hashlib
    artifact = il.build(tmp_path, spec(), '<div>Controls</div>', '', scene=SCENE)
    screenshot = tmp_path / 'synthetic-screenshot.png'
    screenshot.write_bytes(b'unit-test-only-screenshot-identity')
    checks = {key: True for key in ['inner_width_matches', 'no_horizontal_overflow',
              'no_dom_overflow', 'frame_content_fits', 'scene_visible', 'fields_ordered',
              'scene_before_fields', 'one_primary_action', 'interaction_verified']}
    checks['hidden_states_respected'] = True
    snapshot = {'checks': checks, 'screenshot': str(screenshot),
                'screenshot_sha256': hashlib.sha256(screenshot.read_bytes()).hexdigest()}
    report = {'synthetic_operations_only': True, 'no_events_appended_to_learning_log': True,
              'cases': [{'artifact': str(artifact), 'artifact_sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
                         'width': width, 'initial': snapshot, 'interacted': snapshot}
                        for width in (736, 360)]}
    assert il.verify_qa(artifact, report)['user_visibility'] == 'unconfirmed'
    broken = json.loads(json.dumps(report))
    del broken['cases'][0]['initial']
    with pytest.raises(ValueError):
        il.verify_qa(artifact, broken)
    broken = json.loads(json.dumps(report))
    broken['cases'][1]['width'] = 320
    with pytest.raises(ValueError):
        il.verify_qa(artifact, broken)
    artifact.write_text('changed after inspection', encoding='utf-8')
    with pytest.raises(ValueError):
        il.verify_qa(artifact, report)
