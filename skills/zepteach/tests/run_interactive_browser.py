"""Opt-in QA using an existing browser/runtime; creates no learner events."""

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import interactive_lab as il
import interaction as ordinary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--node', required=True)
    parser.add_argument('--playwright', required=True)
    parser.add_argument('--render', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--actual-artifact')
    args = parser.parse_args()
    loader = importlib.util.spec_from_file_location('preview_render', args.render)
    render = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(render)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    base = {'schema_version': 1, 'interaction_id': 'capacity-qa',
            'learning_thread_id': 'synthetic-qa-thread', 'lab_id': 'capacity', 'part_id': 'a',
            'title': 'Development preview', 'prompt': 'Predict a capacity and give your reason.',
            'collect_confidence': True,
            'prediction_fields': [{'field_id': 'capacity', 'label': 'Capacity', 'kind': 'numeric', 'min': 1, 'max': 100}]}
    fragment = '''<div class="viz-row">
<button class="btn" type="button" data-fixture-run>Run once</button>
<button class="btn" type="button" data-fixture-batch>Run a batch</button>
</div><p data-fixture-result aria-live="polite">Not run.</p>'''
    scene = '''<svg viewBox="0 0 280 64" role="img" aria-label="Six pending sample positions" style="width:100%;height:auto">
<g fill="var(--muted)"><circle cx="25" cy="32" r="12"/><circle cx="70" cy="32" r="12"/>
<circle cx="115" cy="32" r="12"/><circle cx="160" cy="32" r="12"/>
<circle cx="205" cy="32" r="12"/><circle cx="250" cy="32" r="12"/></g></svg>'''
    script = '''for (const [selector, count] of [['[data-fixture-run]', 1], ['[data-fixture-batch]', 8]]) {
root.querySelector(selector).addEventListener('click', () => lab.perform({id: 'run', label: 'Run ' + count, parameters: {count}}, () => {
root.querySelector('[data-fixture-result]').textContent = 'Generated ' + count + ' observations.';
return {observed_ui_behavior: 'Displayed ' + count + ' observations.', values: {count}};
}));}'''
    with tempfile.TemporaryDirectory(prefix='zepteach-browser-') as directory:
        work = Path(directory)
        cases = []
        first = il.build(work, base, fragment, script, scene=scene)
        alternative = dict(base, interaction_id='policy-qa', prediction_fields=[
            {'field_id': 'policy', 'label': 'Policy', 'kind': 'choice', 'options': [
                {'value': 'a', 'label': 'First policy'}, {'value': 'b', 'label': 'Second policy'}]},
            {'field_id': 'assumption', 'label': 'A longer assumption label that wraps at narrow widths', 'kind': 'text'}])
        second = il.build(work, alternative, fragment, script, scene=scene)
        question = work / 'ordinary-input.html'
        question.write_text(ordinary.inline_html({'request_id': 'ordinary-qa',
            'prompt': 'Explain your prediction.', 'response': {'mode': 'free_text'}}), encoding='utf-8')
        artifacts = [(first, 'capacity', False, False), (second, 'policy', False, True)]
        artifacts.append((question, 'ordinary-input', False, False))
        if args.actual_artifact:
            artifacts.append((Path(args.actual_artifact).resolve(), 'learning-artifact', True, False))
        for artifact, name, actual, choice in artifacts:
            raw = artifact.read_bytes()
            captured = work / (name + '-captured.html')
            captured.write_bytes(raw)
            preview = work / (name + '-preview.html')
            preview.write_text(render.render(captured), encoding='utf-8')
            cases.append({'artifact': str(artifact), 'preview': str(preview), 'name': name,
                          'artifact_sha256': hashlib.sha256(raw).hexdigest(),
                          'actual': actual, 'choice': choice, 'ordinary': name == 'ordinary-input'})
        config = work / 'browser-config.json'
        config.write_text(json.dumps({'output': str(output), 'cases': cases}), encoding='utf-8')
        result = subprocess.run([args.node, str(Path(__file__).with_name('browser_interactive.cjs')),
                                 args.playwright, str(config)], cwd=work, capture_output=True,
                                text=True, encoding='utf-8', timeout=120)
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode


if __name__ == '__main__':
    sys.exit(main())
