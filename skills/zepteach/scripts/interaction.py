#!/usr/bin/env python3
"""Build a learner input request and its optional inline conversation view.

The request is host-independent. The view contains only what the learner may
see, never a grader, expected answer, or private course record. Hosts that
cannot display it can ask from the same request in plain text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zt_state as zs  # noqa: E402


def energy_request() -> dict:
    return {
        "request_id": "session-energy",
        "prompt": "今天状态怎么样？",
        "response": {"mode": "choice", "options": [
            {"option_id": "low", "text": "精力较低，少学一些"},
            {"option_id": "normal", "text": "状态正常"},
            {"option_id": "high", "text": "精力充足，可以多学一些"},
        ]},
    }


def from_exercise(item: dict) -> dict:
    """Whitelist presentation fields; grading data must not reach the view."""
    response = item.get("response") or {}
    shown = {"mode": response.get("mode")}
    if response.get("fields"):
        shown["fields"] = [
            {key: field[key] for key in ("field_id", "label", "hint")
             if key in field}
            for field in response["fields"]
        ]
    if response.get("options"):
        shown["options"] = [
            {key: option[key] for key in ("option_id", "text")
             if key in option}
            for option in response["options"]
        ]
    return {"request_id": item.get("exercise_id"),
            "prompt": item.get("prompt"), "response": shown}


def validate_request(request: dict) -> list[str]:
    errors = []
    if not isinstance(request, dict):
        return ["request must be an object"]
    for key in ("request_id", "prompt"):
        if not isinstance(request.get(key), str) or not request[key].strip():
            errors.append(key + " is required")
    response = request.get("response")
    if not isinstance(response, dict):
        return errors + ["response is required"]
    mode = response.get("mode")
    if mode not in ("choice", "free_text", "fill_blanks", "numeric", "upload"):
        errors.append("unknown response mode")
    fields = response.get("fields") or []
    options = response.get("options") or []
    if not isinstance(fields, list) or not isinstance(options, list):
        return errors + ["fields and options must be arrays"]
    if mode == "choice":
        if len(options) < 2:
            errors.append("choice needs at least two options")
        ids = [o.get("option_id") for o in options if isinstance(o, dict)]
        labels = [o.get("text") for o in options if isinstance(o, dict)]
        valid = (len(ids) == len(options) and
                 all(isinstance(x, str) and x.strip() for x in ids + labels))
        if not valid:
            errors.append("each option needs an id and text")
        elif len(set(ids)) != len(ids) or len(set(labels)) != len(labels):
            errors.append("option ids and texts must be unique")
    if mode == "fill_blanks" and not fields:
        errors.append("fill_blanks needs named fields")
    if fields:
        ids = [f.get("field_id") for f in fields if isinstance(f, dict)]
        labels = [f.get("label") for f in fields if isinstance(f, dict)]
        valid = (len(ids) == len(fields) and
                 all(isinstance(x, str) and x.strip() for x in ids + labels))
        if not valid:
            errors.append("each field needs an id and label")
        elif len(set(ids)) != len(ids):
            errors.append("field ids must be unique")
    return errors


def plain_text(request: dict) -> str:
    """Same question when this host has no inline input surface."""
    response = request["response"]
    lines = [request["prompt"]]
    if response["mode"] == "choice":
        lines.extend(o["option_id"] + ". " + o["text"]
                     for o in response["options"])
        lines.append("请回复选项编号，也可以直接说明你的情况。")
    elif response.get("fields"):
        lines.extend(f["field_id"] + ": " + f["label"]
                     for f in response["fields"])
        lines.append("请按字段名称回答。")
    elif response["mode"] == "upload":
        lines.append("请用对话的附件功能发送文件或照片。")
    return "\n".join(lines)


def inline_html(request: dict) -> str:
    """Return an inline fragment; the host embeds it in the conversation."""
    if request["response"]["mode"] == "upload":
        raise ValueError("upload needs the host attachment control")
    # Prevent a learner-controlled prompt from ending the script element.
    data = json.dumps(request, ensure_ascii=False).replace("<", "\\u003c")
    return """<div id="zepteach-input" role="group" aria-label="学习回答"></div>
<style>
#zepteach-input { color: var(--foreground); max-width: 100%; }
#zepteach-input .zt-prompt { white-space: pre-wrap; margin: 0 0 12px; }
#zepteach-input .zt-field { display: block; margin: 10px 0; }
#zepteach-input .zt-field span { display: block; margin-bottom: 4px; }
#zepteach-input input[type=text], #zepteach-input input[type=number],
#zepteach-input textarea { box-sizing: border-box; width: 100%; padding: 8px;
  color: var(--foreground); background: var(--background);
  border: 1px solid var(--border); border-radius: 6px; font: inherit; }
#zepteach-input textarea { min-height: 96px; resize: vertical; }
#zepteach-input .zt-choice { display: block; margin: 8px 0; }
#zepteach-input .zt-choice input { margin-right: 8px; }
#zepteach-input button { margin-top: 10px; padding: 7px 12px;
  color: var(--primary-foreground); background: var(--primary);
  border: 0; border-radius: 6px; font: inherit; }
#zepteach-input .zt-status { margin-top: 8px; color: var(--muted-foreground); }
</style>
<script>
(() => {
  const spec = """ + data + """;
  const root = document.getElementById('zepteach-input');
  const form = document.createElement('form');
  const prompt = document.createElement('p');
  prompt.className = 'zt-prompt';
  prompt.textContent = spec.prompt;
  form.appendChild(prompt);
  const mode = spec.response.mode;
  const fields = spec.response.fields || [];
  const saved = window.openai?.widgetState?.privateContent?.draft || {};
  function field(id, label, kind, hint) {
    const wrap = document.createElement('label');
    wrap.className = 'zt-field';
    const title = document.createElement('span');
    title.textContent = label;
    const input = document.createElement(kind === 'free_text' ? 'textarea' : 'input');
    if (input.tagName === 'INPUT') {
      input.type = kind === 'numeric' ? 'number' : 'text';
      if (kind === 'numeric') input.step = 'any';
    }
    input.name = id;
    input.required = true;
    if (hint) input.placeholder = hint;
    if (saved[id]) input.value = saved[id];
    wrap.append(title, input);
    form.appendChild(wrap);
  }
  if (mode === 'choice') {
    spec.response.options.forEach((option, i) => {
      const label = document.createElement('label');
      label.className = 'zt-choice';
      const radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = 'choice';
      radio.value = option.option_id;
      radio.required = true;
      radio.checked = saved.choice === option.option_id;
      label.append(radio, document.createTextNode(option.text));
      form.appendChild(label);
    });
  } else if (fields.length) {
    fields.forEach(f => field(f.field_id, f.label,
      mode === 'numeric' ? 'numeric' : mode === 'free_text' ? 'free_text' : 'text', f.hint));
  } else {
    field('answer', '你的回答', mode);
  }
  const submit = document.createElement('button');
  submit.type = 'submit';
  submit.textContent = '提交回答';
  const status = document.createElement('div');
  status.className = 'zt-status';
  status.setAttribute('role', 'status');
  form.append(submit, status);
  root.appendChild(form);
  if (!window.openai?.sendFollowUpMessage) {
    submit.disabled = true;
    status.textContent = '此客户端无法提交内联回答。请在对话中发送答案。';
  }
  form.addEventListener('input', () => {
    const draft = Object.fromEntries(new FormData(form).entries());
    try {
      Promise.resolve(window.openai?.setWidgetState?.({modelContent: null, privateContent: {draft}}))
        .catch(() => {});
    } catch (_) {}
  });
  form.addEventListener('keydown', event => {
    if (event.key === 'Enter' && event.ctrlKey && event.target.tagName === 'TEXTAREA') {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(form).entries());
    if (!Object.keys(values).length) return;
    if (!window.openai?.sendFollowUpMessage) {
      status.textContent = '此客户端无法提交内联回答。请在对话中发送答案。';
      return;
    }
    submit.disabled = true;
    status.textContent = '正在提交';
    try {
      await window.openai.sendFollowUpMessage({prompt: '[ZepTeach answer] ' + JSON.stringify({request_id: spec.request_id, values})});
      status.textContent = '已提交';
    } catch (_) {
      submit.disabled = false;
      status.textContent = '提交失败，请在对话中发送答案。';
    }
  });
})();
</script>
"""


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "-", value).strip("-")[:64] or "input"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Prepare a learner input view")
    parser.add_argument("kind", choices=("energy", "request", "exercise"))
    parser.add_argument("--file", help="JSON request or exercise")
    parser.add_argument("--root", help="learner data root")
    args = parser.parse_args(argv)
    if args.kind != "energy" and not args.file:
        parser.error("--file is required for request and exercise")
    request = energy_request() if args.kind == "energy" else json.loads(
        Path(args.file).read_text(encoding="utf-8"))
    if args.kind == "exercise":
        request = from_exercise(request)
    errors = validate_request(request)
    if errors:
        print("invalid input request: " + "; ".join(errors), file=sys.stderr)
        return zs.EXIT_VALIDATION
    if request["response"]["mode"] == "upload":
        print(plain_text(request))
        return zs.EXIT_OK
    root = Path(args.root) if args.root else zs.default_root()
    if not root.is_dir():
        print("learner data root not found: " + str(root), file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    output_dir = root / "interaction_views"
    output_dir.mkdir(exist_ok=True)
    content = inline_html(request)
    if len(content.encode("utf-8")) >= 1_000_000:
        print("input view is too large", file=sys.stderr)
        return zs.EXIT_VALIDATION
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    output = output_dir / (safe_name(request["request_id"]) + "-" + digest + ".html")
    output.write_text(content, encoding="utf-8")
    print("INLINE  " + str(output.resolve()))
    print("TEXT FALLBACK\n" + plain_text(request))
    return zs.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
