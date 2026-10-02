"""Deterministic scene QA on isolated copies, never learner operations."""
import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--node', required=True)
    parser.add_argument('--playwright', required=True)
    parser.add_argument('--render', required=True)
    parser.add_argument('--actual-artifact', help='optional protected artifact, read only')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    loader = importlib.util.spec_from_file_location('outcome_preview', args.render)
    render = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(render)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    helper = (Path(__file__).parents[1] / 'assets' / 'outcome-view.js').read_text(encoding='utf-8')
    actual = Path(args.actual_artifact).resolve() if args.actual_artifact else None
    original = actual.read_text(encoding='utf-8') if actual else None
    replacement = '''const outcome = globalThis.ZepTeachOutcome.mount(ui.students, {maxVisible:120, itemLabel:'学生', matchLabel:'生日匹配'});
      const drawScene = () => {
        ui.students.classList.remove('birthday-students');
        outcome.render({total:state.n, matchCount:state.sample ? state.sample.count : null,
          visibleMatchIndices:state.sample?.visibleMatches || []});
        ui.size.textContent = String(state.n);
        ui.detail.hidden = true;
      };
      '''
    prepared = []
    if actual:
        candidate, replaced = re.subn(r'const drawScene = \(\) => \{.*?(?=const draw = \(\) =>)',
                                     lambda _: replacement, original, flags=re.S)
        if replaced != 1:
            raise ValueError('source changed; do not guess how to adapt the protected artifact')
        candidate = candidate.replace('<script>', '<script>\n' + helper + '\n</script>\n<script>', 1)
        candidate = candidate.replace('#birthday-lab-one [hidden] { display: none; }',
                                      '#birthday-lab-one [hidden] { display: none !important; }', 1)
        candidate_path = output / 'candidate-birthday-outcome.html'
        candidate_path.write_text(candidate, encoding='utf-8')
        prepared.extend([('original',actual,original),('candidate',candidate_path,candidate)])
    generic = '<section id="generic-outcome" aria-label="Synthetic scene"></section>\n<script>\n' + helper + '''
const view = ZepTeachOutcome.mount(document.getElementById('generic-outcome'), {itemLabel:'检查对象',matchLabel:'符合条件'});
window.syntheticOutcome = data => view.render(data);
syntheticOutcome({total:264,matchCount:null});
</script>'''
    generic_path = output / 'generic-outcome.html'
    generic_path.write_text(generic, encoding='utf-8')
    prepared.append(('generic',generic_path,generic))
    with tempfile.TemporaryDirectory(prefix='zepteach-outcome-') as directory:
        work = Path(directory)
        targets = []
        for kind, artifact, content in prepared:
            snapshot = work / (kind + '.html')
            snapshot.write_text(content, encoding='utf-8')
            preview = work / (kind + '-preview.html')
            preview.write_text(render.render(snapshot), encoding='utf-8')
            targets.append({'kind':kind,'artifact':str(artifact),
                'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'preview':str(preview)})
        config = work / 'config.json'
        config.write_text(json.dumps({'output':str(output),'targets':targets}), encoding='utf-8')
        result = subprocess.run([args.node, str(Path(__file__).with_name('browser_outcomes.cjs')),
                                 args.playwright, str(config)], cwd=work, capture_output=True,
                                text=True, encoding='utf-8', timeout=120)
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode


if __name__ == '__main__':
    sys.exit(main())
