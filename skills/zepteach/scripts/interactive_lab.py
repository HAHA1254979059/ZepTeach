#!/usr/bin/env python3
"""Build one interactive step and check its actual final-response reference."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from html import escape
from pathlib import Path

import zt_state as zs
import presentation

ASSETS = Path(__file__).resolve().parents[1] / "assets"


def static_fields(spec):
    fields = []
    for field in spec["prediction_fields"]:
        name = escape(field["field_id"], quote=True)
        if field["kind"] == "choice":
            control = '<select class="form-select" name="' + name + '" required><option value="">请选择</option>' + ''.join(
                '<option value="' + escape(option["value"], quote=True) + '">' + escape(option["label"]) + '</option>'
                for option in field["options"]) + '</select>'
        else:
            attrs = ''.join(' ' + key + '="' + escape(str(field[key]), quote=True) + '"' for key in ("min", "max", "step") if key in field)
            if field["kind"] == "numeric" and "step" not in field:
                attrs += ' step="any"'
            control = '<input class="form-control" name="' + name + '" type="' + ('number' if field["kind"] == "numeric" else 'text') + '"' + attrs + ' required>'
        fields.append('<label class="form-label">' + escape(field["label"]) + control + '</label>')
    return ''.join(fields)


def validate_spec(spec):
    errors = zs.validate_doc(spec, "interactive_step")
    if errors:
        raise ValueError("invalid interactive step: " + "; ".join(errors))
    fields = spec["prediction_fields"]
    ids = [field["field_id"] for field in fields]
    if len(set(ids)) != len(ids) or set(ids) & {"reason", "confidence"}:
        raise ValueError("prediction fields must be unique and not use reserved names")
    for field in fields:
        if field["kind"] == "choice" and len(field.get("options", [])) < 2:
            raise ValueError("choice needs at least two options")
        if field.get("min") is not None and field.get("max") is not None and field["min"] > field["max"]:
            raise ValueError("input minimum exceeds maximum")


def build(root: Path, spec: dict, fragment: str, script: str, *, scene: str):
    validate_spec(spec)
    if not root.is_dir():
        raise FileNotFoundError("learning data root does not exist")
    if not scene.strip():
        raise ValueError("an answer-neutral initial scene is required")
    for content in (scene, fragment):
        if re.search(r"<!doctype|<\s*(html|head|body|script)\b", content, re.I):
            raise ValueError("scene and simulation must be fragments; provide script separately")
        for styles in re.findall(r"<style\b[^>]*>(.*?)</style\s*>", content, re.I | re.S):
            for selector in re.findall(r"([^{}]+)\{", styles):
                if re.search(r"\.(?:btn(?:-primary|-ghost|-block)?|form-control|form-label|form-select|form-range|card|viz-controls)(?![\w-])", selector):
                    raise ValueError("do not restyle host utilities; use a custom layout wrapper")
    if re.search(r"\bfetch\s*\(|\b(?:XMLHttpRequest|WebSocket)\b", script):
        raise ValueError("inline simulations cannot use network APIs")
    if "</script" in script.lower():
        raise ValueError("simulation script must not close its embedding element")
    runtime = (ASSETS / "interactive-runtime.js").read_text(encoding="utf-8")
    outcomes = (ASSETS / "outcome-view.js").read_text(encoding="utf-8")
    template = (ASSETS / "interactive-lab.html").read_text(encoding="utf-8")
    signature = hashlib.sha256((json.dumps(spec, sort_keys=True) + scene + fragment + script +
                                outcomes + runtime + template).encode()).hexdigest()[:12]
    name = re.sub(r"[^a-z0-9-]", "-", spec["interaction_id"].lower()).strip("-")[:60] or "step"
    output = root / "interaction_views" / (name + "-" + signature + ".html")
    output.resolve().relative_to(root.resolve())
    root_id = "zt-step-" + signature
    config = dict(spec, artifact_path=str(output.resolve()))
    replacements = {"__SCENE__": scene, "__SIMULATION__": fragment, "__SIMULATION_SCRIPT__": script,
                    "__REQUIRES_OUTCOMES__": str(bool(re.search(r"\bZepTeachOutcome\s*\.\s*mount\s*\(", script))).lower(),
                    "__TITLE_TEXT__": escape(spec["title"]), "__PROMPT_TEXT__": escape(spec["prompt"]),
                    "__STATIC_FIELDS__": static_fields(spec),
                    "__OUTCOME_VIEW__": outcomes, "__RUNTIME__": runtime,
                    "__SPEC_JSON__": json.dumps(config, ensure_ascii=False).replace("<", "\\u003c")}
    # Replace template slots once, without interpreting learner material as
    # a second template. Only the documented root token is substituted later.
    content = re.sub(r"__(?:SCENE|SIMULATION|SIMULATION_SCRIPT|OUTCOME_VIEW|RUNTIME|SPEC_JSON|TITLE_TEXT|PROMPT_TEXT|STATIC_FIELDS|REQUIRES_OUTCOMES)__",
                     lambda match: replacements[match.group()], template)
    content = content.replace("__ROOT_ID__", root_id)
    if len(content.encode("utf-8")) >= 1_000_000:
        raise ValueError("inline step exceeds 1 MB")
    output.parent.mkdir(exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return output.resolve()


def verify_qa(artifact: Path, report: dict, outcome_report: dict = None):
    """Accept matching initial and interacted preview evidence, not visibility."""
    if not artifact.is_absolute() or not artifact.is_file():
        raise ValueError("QA artifact must be an existing absolute file")
    if 'data-zt-requires-outcomes="true"' in artifact.read_text(encoding="utf-8") and outcome_report is None:
        raise ValueError("this outcome scene also needs deterministic semantic QA")
    if outcome_report is not None:
        verify_outcomes(artifact, outcome_report)
    if not isinstance(report, dict) or not isinstance(report.get("cases"), list) or \
            any(not isinstance(case, dict) for case in report["cases"]):
        raise ValueError("QA report must contain an array of case objects")
    if report.get("synthetic_operations_only") is not True or \
            report.get("no_events_appended_to_learning_log") is not True:
        raise ValueError("QA must identify isolated synthetic operations")
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    cases = [case for case in report.get("cases", [])
             if Path(case.get("artifact", "")).resolve() == artifact.resolve()]
    for width in (736, 360):
        matches = [case for case in cases if case.get("width") == width]
        if len(matches) != 1 or matches[0].get("artifact_sha256") != sha:
            raise ValueError("QA needs one matching artifact case at inner width " + str(width))
        for phase in ("initial", "interacted"):
            snapshot = matches[0].get(phase) or {}
            checks = snapshot.get("checks") or {}
            required = ["inner_width_matches", "no_horizontal_overflow",
                        "no_dom_overflow", "frame_content_fits", "scene_visible", "hidden_states_respected",
                        "scene_before_fields", "fields_ordered"]
            required.append("one_primary_action" if phase == "initial" else "interaction_verified")
            if any(checks.get(check) is not True for check in required):
                raise ValueError("QA failed or missing checks for " + phase + " at " + str(width))
            screenshot = Path(snapshot.get("screenshot", ""))
            if not screenshot.is_absolute() or not screenshot.is_file() or \
                    hashlib.sha256(screenshot.read_bytes()).hexdigest() != snapshot.get("screenshot_sha256"):
                raise ValueError("QA screenshot is missing or has changed")
    return {"artifact_path": str(artifact.resolve()), "artifact_sha256": sha,
            "controls_verified": True, "layout_verified": True,
            "screenshots_captured": True, "user_visibility": "unconfirmed",
            "actual_client_return": "unconfirmed"}


def verify_outcomes(artifact: Path, report: dict):
    if not artifact.is_absolute() or not artifact.is_file() or not isinstance(report, dict):
        raise ValueError("outcome QA needs an existing artifact and a report object")
    if report.get("synthetic_operations_only") is not True or report.get("no_events_appended_to_learning_log") is not True:
        raise ValueError("outcome checks must be isolated from real learner events")
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    cases = [case for case in report.get("cases", []) if Path(case.get("artifact", "")).resolve() == artifact.resolve()]
    required = ("pending", "zero", "positive-visible", "positive-omitted", "positive-mixed", "all", "reset", "restore")
    for width in (736, 360):
        for theme in ("light", "dark"):
            for name in required:
                matching = [case for case in cases if (case.get("width"), case.get("theme"), case.get("case")) == (width, theme, name)]
                if len(matching) != 1 or matching[0].get("artifact_sha256") != sha or matching[0].get("consistent") is not True:
                    raise ValueError("missing or inconsistent outcome view: " + str((width, theme, name)))
    return {"artifact_sha256":sha, "outcome_mapping_verified":True,
            "actual_client_display":"unconfirmed", "actual_client_return":"unconfirmed"}


def check_delivery(artifact: Path, reply: str, qa_report: dict = None, outcome_report: dict = None):
    if not artifact.is_absolute() or not artifact.is_file():
        raise ValueError("artifact must be an existing absolute file")
    matched = False
    fenced = False
    for line in reply.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
            continue
        found = re.fullmatch(r"\s*visualize(\{[^\n]*\})\s*", line)
        if fenced or not found:
            continue
        reference = json.loads(found.group(1))
        if Path(reference.get("path", "")).resolve() == artifact.resolve():
            matched = True
    if not matched:
        raise ValueError("actual final reply has no matching Visualize reference")
    result = {"artifact_path": str(artifact.resolve()),
            "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "file_verified": True, "reference_verified": True,
            "controls_verified": False, "user_visibility": "unconfirmed"}
    if qa_report is not None:
        result.update(verify_qa(artifact, qa_report, outcome_report))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("build")
    generate.add_argument("--root", required=True)
    generate.add_argument("--spec", required=True)
    generate.add_argument("--fragment", required=True)
    generate.add_argument("--scene", required=True, help="answer-neutral visible initial scene")
    generate.add_argument("--script", required=True)
    check = sub.add_parser("check-delivery")
    check.add_argument("--artifact", required=True)
    check.add_argument("--reply-file", required=True, help="actual final message text")
    check.add_argument("--report", help="private local JSON evidence report")
    check.add_argument("--qa-report", help="matching initial/interacted browser evidence")
    check.add_argument("--outcome-report", help="deterministic outcome mapping evidence")
    qa = sub.add_parser("verify-qa")
    qa.add_argument("--artifact", required=True)
    qa.add_argument("--qa-report", required=True)
    qa.add_argument("--outcome-report")
    outcomes = sub.add_parser("verify-outcomes")
    outcomes.add_argument("--artifact", required=True)
    outcomes.add_argument("--qa-report", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            path = build(Path(args.root), json.loads(Path(args.spec).read_text(encoding="utf-8")),
                         Path(args.fragment).read_text(encoding="utf-8"),
                         Path(args.script).read_text(encoding="utf-8"),
                         scene=Path(args.scene).read_text(encoding="utf-8"))
            result = {"artifact_path": str(path), "final_response_reference":
                      'visualize' + json.dumps({"path": str(path)}, ensure_ascii=False) + '',
                      "user_visibility": "unconfirmed", "progress_written": False}
            result["text_backup"] = presentation.text_backup(json.loads(Path(args.spec).read_text(encoding="utf-8")))
        elif args.command == "verify-qa":
            outcomes = json.loads(Path(args.outcome_report).read_text(encoding="utf-8")) if args.outcome_report else None
            result = verify_qa(Path(args.artifact), json.loads(Path(args.qa_report).read_text(encoding="utf-8")), outcomes)
        elif args.command == "verify-outcomes":
            result = verify_outcomes(Path(args.artifact), json.loads(Path(args.qa_report).read_text(encoding="utf-8")))
        else:
            report = json.loads(Path(args.qa_report).read_text(encoding="utf-8")) if args.qa_report else None
            outcomes = json.loads(Path(args.outcome_report).read_text(encoding="utf-8")) if args.outcome_report else None
            result = check_delivery(Path(args.artifact), Path(args.reply_file).read_text(encoding="utf-8"), report, outcomes)
            if args.report:
                output = Path(args.report)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return zs.EXIT_OK
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    except (ValueError, TypeError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return zs.EXIT_VALIDATION


if __name__ == "__main__":
    sys.exit(main())
