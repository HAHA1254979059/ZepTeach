"""Opt-in client-capability previews; none is a real mobile-app verdict."""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import interactive_lab as il


def main():
    p = argparse.ArgumentParser()
    for name in ('node','playwright','render','output'):
        p.add_argument('--'+name, required=True)
    args = p.parse_args()
    loader = importlib.util.spec_from_file_location('presentation_preview', args.render)
    renderer = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(renderer)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='zepteach-capabilities-') as directory:
        work = Path(directory)
        spec = {'schema_version':1,'interaction_id':'client-qa','learning_thread_id':'synthetic-thread',
            'lab_id':'client-check','part_id':'one','title':'Synthetic client check',
            'prompt':'Predict the size and explain your reason.',
            'prediction_fields':[{'field_id':'size','label':'Predicted size','kind':'numeric'}]}
        artifact = il.build(work, spec, '<div>Experiment controls</div>', '', scene='<div>Pending scene</div>')
        raw = artifact.read_text(encoding='utf-8')
        normal = work / 'styled.html'
        normal.write_text(renderer.render(artifact), encoding='utf-8')
        bare = work / 'bare.html'
        from html import escape
        bare.write_text('<!doctype html><meta name="viewport" content="width=device-width"><iframe sandbox="allow-scripts" style="width:100%;height:900px;border:0" srcdoc="'+escape(raw,quote=True)+'"></iframe>',encoding='utf-8')
        no_script = work / 'no-script.html'
        host_css = (Path(args.render).parents[1] / 'assets' / 'visualize.css').read_text(encoding='utf-8')
        static_document = '<!doctype html><meta name="viewport" content="width=device-width"><style>'+host_css+'</style>'+raw
        no_script.write_text('<!doctype html><meta name="viewport" content="width=device-width"><iframe sandbox="" style="width:100%;height:900px;border:0" srcdoc="'+escape(static_document,quote=True)+'"></iframe>',encoding='utf-8')
        cfg = work / 'cfg.json'
        cfg.write_text(json.dumps({'normal':str(normal),'bare':str(bare),'no_script':str(no_script),'output':str(output),
            'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()}),encoding='utf-8')
        result = subprocess.run([args.node,str(Path(__file__).with_name('browser_presentation.cjs')),
            args.playwright,str(cfg)],cwd=work,capture_output=True,text=True,encoding='utf-8',timeout=90)
        print(result.stdout)
        if result.stderr: print(result.stderr,file=sys.stderr)
        return result.returncode


if __name__ == '__main__':
    sys.exit(main())
