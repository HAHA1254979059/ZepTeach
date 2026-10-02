import pytest

import presentation as pr
import interactive_lab as il
from test_interactive_lab import spec, SCENE


def test_narrow_preview_is_not_actual_mobile_acceptance():
    result = pr.plan(spec(), {"origin":"isolated_preview", "inline_display":"verified", "width":360})
    assert result['actual_client_display'] == 'unconfirmed'
    assert result['mode'] == 'inline_with_text_backup'
    assert result['progress_written'] is False


def test_unusable_client_preserves_the_same_question_and_reason():
    request = spec(prompt='Original question remains visible')
    result = pr.plan(request, {'origin':'learner_report', 'inline_display':'reported_unusable'})
    assert result['mode'] == 'conversation'
    assert request['prompt'] in result['text_backup']
    assert 'capacity' in result['text_backup'] and 'reason' in result['text_backup']
    assert result['actual_client_return'] == 'unconfirmed'


def test_missing_capability_selects_fallback_without_a_device_name():
    assert pr.plan(spec(), {'origin':'client_probe','host_styles':False})['mode'] == 'conversation'
    assert pr.plan(spec(), {'origin':'client_probe','script_execution':False})['mode'] == 'conversation'


def test_static_content_is_present_and_escaped_before_javascript(tmp_path):
    request = spec(title='<unsafe title>', prompt='Question <not markup>')
    artifact = il.build(tmp_path, request, '<div>Controls</div>', '', scene=SCENE)
    initial = artifact.read_text(encoding='utf-8').split('<script>')[0]
    assert '&lt;unsafe title&gt;' in initial and '&lt;not markup&gt;' in initial
    assert 'name="capacity"' in initial and 'noscript' in initial
    assert '<unsafe title>' not in initial
