"""Choose a teaching presentation from actual capabilities, not device names."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def text_backup(spec: dict) -> str:
    """The same question and answer shape, without a client-side dependency."""
    lines = [spec["title"], spec["prompt"]]
    for field in spec["prediction_fields"]:
        line = field["field_id"] + ": " + field["label"]
        if field["kind"] == "choice":
            line += "（" + "；".join(option["value"] + "=" + option["label"]
                                    for option in field["options"]) + "）"
        lines.append(line)
    lines.append("reason: 你的理由")
    if spec.get("collect_confidence"):
        lines.append("confidence: 信心 0–100，可留空")
    lines.append("先提供预测与理由，再进行实验；不会自动进入下一环节。")
    return "\n".join(lines)


def plan(spec: dict, evidence: dict = None):
    evidence = evidence or {}
    if not isinstance(evidence, dict):
        raise ValueError("presentation evidence must be an object")
    origin = evidence.get("origin", "none")
    if origin not in ("none", "isolated_preview", "client_probe", "learner_report"):
        raise ValueError("unknown presentation evidence origin")
    display = evidence.get("inline_display", "unconfirmed")
    if display not in ("unconfirmed", "verified", "reported_unusable"):
        raise ValueError("unknown inline display evidence")
    # A narrow browser preview cannot establish actual mobile-app support.
    real_evidence = origin in ("client_probe", "learner_report")
    unavailable = real_evidence and (display == "reported_unusable" or
                   evidence.get("script_execution") is False or
                   evidence.get("host_styles") is False)
    return {"mode": "conversation" if unavailable else "inline_with_text_backup",
            "text_backup": text_backup(spec),
            "evidence_scope": origin,
            "actual_client_display": display if origin == "learner_report" else "unconfirmed",
            "actual_client_return": "unconfirmed",
            "progress_written": False}


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--client-evidence", help="actual learner report or capability probe")
    args = parser.parse_args(argv)
    try:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        evidence = json.loads(Path(args.client_evidence).read_text(encoding="utf-8")) if args.client_evidence else None
        print(json.dumps(plan(spec, evidence), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
