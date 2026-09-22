#!/usr/bin/env python3
"""ZepTeach state engine.

Single owner of the learning data root. Every write goes through schema
validation plus a layer of semantic rules that encode the invariants the
system must not be talked out of:

  - a pass verdict must quote the evidence that earned it
  - mastered requires a delayed retest AND a transfer test, days apart
  - a concept may not be taken deeper than its declared depth target
  - an exercise without a grading spec may not be issued
  - an active course may not teach before its environment setup ran

These live here, in code with exit codes, rather than in prose, so that
behaviour does not drift with whichever model drives the session.

Exit codes:
  0  ok
  2  schema or semantic validation failure
  3  gate precondition not met
  4  budget exceeded
  5  not found / not initialised
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

EXIT_OK = 0
EXIT_VALIDATION = 2
EXIT_GATE = 3
EXIT_BUDGET = 4
EXIT_NOT_FOUND = 5


# --------------------------------------------------------------------------
# root resolution and layout
# --------------------------------------------------------------------------

def default_root() -> Path:
    """Where a learner's records live, on any machine.

    The home directory on every platform. An earlier version returned a
    fixed drive letter on Windows because that is where the author keeps
    this data, which meant the plugin created, or failed to create, a
    directory on a drive most people do not have. Set ZEPTEACH_ROOT to put
    it somewhere else.
    """
    env = os.environ.get("ZEPTEACH_ROOT")
    if env:
        return Path(env)
    return Path.home() / "ZepTeach"


LAYOUT_DIRS = [
    "learner",
    "courses",
    "notes",
    "notes/concepts",
    "notes/journal",
    "logs",
]


def resolve_in_root(root: Path, relpath: str) -> Path:
    """Join relpath onto root, refusing anything that escapes the root."""
    if os.path.isabs(relpath):
        raise ValueError("path must be relative to the data root: " + relpath)
    target = (root / relpath).resolve()
    root_r = root.resolve()
    if root_r != target and root_r not in target.parents:
        raise ValueError("path escapes the data root: " + relpath)
    return target


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# --------------------------------------------------------------------------
# minimal JSON Schema validator (self-contained: no third-party dependency,
# so the plugin behaves identically on any machine it is copied to)
# --------------------------------------------------------------------------

_TYPES = {
    "string": str,
    "object": dict,
    "array": list,
    "boolean": bool,
    "null": type(None),
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:?\d{2})?$"
)


def _type_ok(value, tname: str) -> bool:
    if tname == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if tname == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if tname == "boolean":
        return isinstance(value, bool)
    py = _TYPES.get(tname)
    if py is None:
        return True
    if py is not bool and isinstance(value, bool):
        return False
    return isinstance(value, py)


def _resolve_ref(ref: str, root_schema: dict):
    if not ref.startswith("#/"):
        raise ValueError("only local refs are supported: " + ref)
    node = root_schema
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        node = node[part]
    return node


def validate(instance, schema: dict, root_schema=None, path: str = "$") -> list:
    """Return a list of human-readable validation errors."""
    if root_schema is None:
        root_schema = schema
    errors = []

    if "$ref" in schema:
        return validate(instance, _resolve_ref(schema["$ref"], root_schema),
                        root_schema, path)

    if "type" in schema:
        tnames = schema["type"]
        if isinstance(tnames, str):
            tnames = [tnames]
        if not any(_type_ok(instance, t) for t in tnames):
            errors.append(path + ": expected type " + "/".join(tnames) +
                          ", got " + type(instance).__name__)
            return errors

    if "const" in schema and instance != schema["const"]:
        errors.append(path + ": must equal " + json.dumps(schema["const"]))

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(path + ": " + json.dumps(instance, ensure_ascii=False) +
                      " not one of " + json.dumps(schema["enum"]))

    for sub in schema.get("allOf", []):
        errors.extend(validate(instance, sub, root_schema, path))

    if "anyOf" in schema:
        if not any(not validate(instance, s, root_schema, path)
                   for s in schema["anyOf"]):
            errors.append(path + ": does not match any allowed variant")

    if "oneOf" in schema:
        hits = sum(1 for s in schema["oneOf"]
                   if not validate(instance, s, root_schema, path))
        if hits != 1:
            errors.append(path + ": must match exactly one variant, matched " +
                          str(hits))

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(path + ": shorter than minLength " +
                          str(schema["minLength"]))
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(path + ": longer than maxLength " +
                          str(schema["maxLength"]))
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(path + ": does not match pattern " +
                          schema["pattern"])
        fmt = schema.get("format")
        if fmt == "date" and not _DATE_RE.match(instance):
            errors.append(path + ": not a YYYY-MM-DD date")
        if fmt == "date-time" and not _DATETIME_RE.match(instance):
            errors.append(path + ": not an ISO date-time")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(path + ": below minimum " + str(schema["minimum"]))
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(path + ": above maximum " + str(schema["maximum"]))

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(path + ": fewer than minItems " +
                          str(schema["minItems"]))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(path + ": more than maxItems " +
                          str(schema["maxItems"]))
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(instance):
                errors.extend(validate(item, item_schema, root_schema,
                                       path + "[" + str(i) + "]"))

    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(path + ": missing required field " + req)
        props = schema.get("properties", {})
        for key, value in instance.items():
            if key in props:
                errors.extend(validate(value, props[key], root_schema,
                                       path + "." + key))
            elif schema.get("additionalProperties") is False:
                errors.append(path + ": unexpected field " + key)

    return errors


# --------------------------------------------------------------------------
# schema registry
# --------------------------------------------------------------------------

def schema_names() -> list:
    return sorted(p.name[: -len(".schema.json")]
                  for p in SCHEMA_DIR.glob("*.schema.json"))


SHARED_PATH = SCHEMA_DIR / "_shared.json"
_shared_cache = {}


def shared_defs() -> dict:
    """Enum values that several schemas need, held in one place.

    The discipline leak this project had to undo got in precisely because an
    enum was copied: the same eleven-value list of exercise forms sat in four
    schema files, so no one file was the truth and all four drifted towards
    whichever subject was on the author's mind. Anything more than one schema
    needs now lives in _shared.json and is expanded here.
    """
    if not _shared_cache:
        _shared_cache.update(json.loads(
            SHARED_PATH.read_text(encoding="utf-8")))
    return _shared_cache


def expand_shared(node):
    """Replace {"$shared": "name"} with that definition, anywhere in a schema.

    Deliberately not general $ref support: one hop, no remote lookups, no
    cycles possible. The validator stays small enough to read in one sitting,
    which is the whole reason it has no third-party dependency."""
    if isinstance(node, dict):
        key = node.get("$shared")
        if isinstance(key, str):
            defs = shared_defs()
            if key not in defs:
                raise KeyError("no shared definition named " + key +
                               " (have: " + ", ".join(
                                   k for k in defs if not k.startswith("_")) +
                               ")")
            merged = dict(defs[key])
            # a local key wins, so a schema may narrow the description
            for k, v in node.items():
                if k != "$shared":
                    merged[k] = v
            return merged
        return dict((k, expand_shared(v)) for k, v in node.items())
    if isinstance(node, list):
        return [expand_shared(v) for v in node]
    return node


def load_schema(name: str) -> dict:
    p = SCHEMA_DIR / (name + ".schema.json")
    if not p.exists():
        raise FileNotFoundError("no such schema: " + name +
                                " (have: " + ", ".join(schema_names()) + ")")
    return expand_shared(json.loads(p.read_text(encoding="utf-8")))


def validate_doc(doc, schema_name: str) -> list:
    return validate(doc, load_schema(schema_name))


# --------------------------------------------------------------------------
# mastery state machine
# --------------------------------------------------------------------------

MASTERY_STATES = ["unseen", "introduced", "practiced",
                  "consolidating", "mastered", "shaky"]

MASTERY_TRANSITIONS = {
    "unseen": ["introduced"],
    "introduced": ["practiced", "shaky"],
    "practiced": ["consolidating", "shaky"],
    "consolidating": ["mastered", "shaky"],
    # a mastered concept can only fall; it is never re-promoted from above
    "mastered": ["shaky"],
    # recovery re-earns each rung and never jumps straight back to mastered
    "shaky": ["introduced", "practiced", "consolidating"],
}

# what evidence a state must be able to point at
STATE_EVIDENCE_REQUIREMENTS = {
    "unseen": [],
    "introduced": [],
    "practiced": [("inclass", "assessment")],
    "consolidating": [("delayed_retest",)],
    "mastered": [("delayed_retest",), ("transfer_test",)],
    "shaky": [],
}


def can_transition(old: str, new: str) -> bool:
    if old == new:
        return True
    return new in MASTERY_TRANSITIONS.get(old, [])


def _parse_dt(s):
    if not isinstance(s, str):
        return None
    try:
        t = s.replace("Z", "+00:00").replace("z", "+00:00")
        d = datetime.fromisoformat(t)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except ValueError:
        return None


# --------------------------------------------------------------------------
# semantic rules -- the part that cannot be argued with
# --------------------------------------------------------------------------

class Finding:
    def __init__(self, code: str, where: str, message: str,
                 severity: str = "error"):
        self.code = code
        self.where = where
        self.message = message
        self.severity = severity

    def __str__(self) -> str:
        return ("[" + self.severity.upper() + " " + self.code + "] " +
                self.where + ": " + self.message)


def rule_attempt(att: dict, where: str) -> list:
    out = []
    concept_ids = att.get("concept_ids") or []
    results = att.get("concept_results")
    if isinstance(results, list):
        result_ids = [r.get("concept_id") for r in results
                      if isinstance(r, dict)]
        valid_ids = (len(result_ids) == len(results) == len(concept_ids)
                     and all(isinstance(cid, str) for cid in result_ids + concept_ids)
                     and len(set(result_ids)) == len(result_ids)
                     and len(set(concept_ids)) == len(concept_ids)
                     and sorted(result_ids) == sorted(concept_ids))
        if not valid_ids:
            out.append(Finding(
                "ATT010", where,
                "concept_results must name each concept exactly once; an "
                "unassessed concept must say unassessed rather than inherit "
                "the whole item's verdict"))
        answer = (att.get("answer") or "") + " " + " ".join(
            str(value) for value in (att.get("response_values") or {}).values())
        answer = re.sub(r"\s+", " ", answer).strip().lower()
        for result in results:
            if not isinstance(result, dict):
                continue
            cid = result.get("concept_id")
            if result.get("verdict") == "pass":
                quotes = result.get("evidence_quotes") or []
                if not quotes or any(not isinstance(q, str) or
                                     re.sub(r"\s+", " ", q).strip().lower()
                                     not in answer for q in quotes):
                    out.append(Finding(
                        "ATT011", where,
                        "a pass for " + str(cid) + " needs quotes from that "
                        "concept's actual answer"))
            if result.get("verdict") == "unassessed" and (
                    result.get("evidence_quotes") or result.get("failure_points")):
                out.append(Finding(
                    "ATT012", where,
                    "unassessed " + str(cid) + " cannot carry pass or "
                    "failure evidence"))
            if len(concept_ids) > 1 and att.get("kind") != "probe" and \
                    result.get("verdict") != "unassessed" and \
                    not result.get("latency_rating"):
                out.append(Finding(
                    "ATT015", where,
                    "rate recall for " + str(cid) + " separately; a hint "
                    "on another concept must not affect it"))
        if att.get("verdict") == "pass" and any(
                r.get("verdict") != "pass" for r in results
                if isinstance(r, dict)):
            out.append(Finding(
                "ATT013", where,
                "the whole item cannot pass when a concept did not pass"))
    if att.get("verdict") == "pass" and not att.get("evidence_quotes"):
        out.append(Finding(
            "ATT001", where,
            "a pass verdict must quote the specific lines that earned it; "
            "nothing quoted means this is not a pass"))
    if att.get("kind") == "transfer_test":
        if att.get("tier") != "modeling" and len(att.get("concept_ids", [])) < 2:
            out.append(Finding(
                "ATT002", where,
                "a transfer test must be a modeling-tier item or combine at "
                "least two concepts; otherwise it is just another retest"))
    if att.get("verdict") == "fail" and not att.get("failure_points"):
        out.append(Finding(
            "ATT003", where,
            "a fail must name what went wrong, so it can be repaired",
            severity="warning"))
    if att.get("latency_rating") and not att.get("latency_source"):
        out.append(Finding(
            "ATT005", where,
            "record where the recall-effort rating came from: Zep inferred "
            "it, the learner said it, or the learner corrected Zep. The "
            "review interval leans on this, so an unattributed rating is "
            "worth less",
            severity="warning"))

    # tier describes an exercise. A probe and an explain-back are not
    # exercises, so they have no tier; everything else must declare one.
    exempt = att.get("kind") == "probe" or att.get("form") == "explain_back"
    if not att.get("tier") and not exempt:
        out.append(Finding(
            "ATT006", where,
            "an exercise attempt must say which tier it came from; only a "
            "probe or an explain-back is exempt"))
    if att.get("tier") and exempt:
        out.append(Finding(
            "ATT006", where,
            "a probe or explain-back has no exercise tier",
            severity="warning"))

    if att.get("verdict") == "pass" and att.get("kind") != "probe" \
            and not att.get("depth_demonstrated"):
        out.append(Finding(
            "ATT007", where,
            "say what depth this answer actually proved; without it the "
            "depth ceiling can never be enforced and a concept can quietly "
            "be taken far past its target",
            severity="warning"))

    if att.get("kind") != "probe" and not att.get("latency_rating"):
        out.append(Finding(
            "ATT008", where,
            "rate how hard the recall was (instant / fluent / effortful / "
            "recovered_with_hint). It is the main input to the next review "
            "interval, and without it the schedule falls back to assuming "
            "the answer took work",
            severity="warning"))

    if att.get("interleaved") and len(att.get("concept_ids", [])) < 2:
        out.append(Finding(
            "ATT009", where,
            "an interleaved item draws on more than one concept; with a "
            "single concept the learner already knows which method applies"))
    return out


def rule_exercise(ex: dict, where: str) -> list:
    out = []
    grader = ex.get("grader") or {}
    gtype = grader.get("type")
    tier = ex.get("tier")
    if tier == "modeling" and gtype != "rubric":
        out.append(Finding(
            "EXE001", where,
            "a modeling-tier item is open-ended and must be rubric-graded"))
    if (tier == "modeling" or gtype == "rubric") and not ex.get("rubric_id"):
        out.append(Finding("EXE002", where,
                           "rubric-graded item has no rubric_id"))
    if not tier and ex.get("form") != "explain_back":
        out.append(Finding(
            "EXE006", where,
            "this item says which tier it belongs to nowhere. Only an "
            "explain-back is exempt, because it is not drawn from a source, "
            "not a variant of one, and not an open-ended task"))
    if ex.get("interleaved") and len(ex.get("concept_ids", [])) < 2:
        out.append(Finding(
            "EXE005", where,
            "an interleaved item must span at least two concepts; otherwise "
            "the prompt still tells the learner which method to reach for"))
    if ex.get("interleaved") and ex.get("reveals_method"):
        out.append(Finding(
            "EXE007", where,
            "this is marked as part of a mixed set and its wording names the "
            "method to use. Choosing the method is the whole thing a mixed "
            "set practises, so this is single-topic practice wearing a "
            "label"))
    if ex.get("transfer_dimensions") == ["knowledge_domain"]:
        out.append(Finding(
            "EXE008", where,
            "this transfer test moves only along knowledge domain, which the "
            "weaker criterion it replaced already did. The setting, the form "
            "and the stakes are all unchanged", severity="warning"))
    if tier == "anchored":
        if not ex.get("source_ref"):
            out.append(Finding(
                "EXE003", where,
                "an anchored-tier item must cite exactly where it came from; "
                "that citation is what keeps its difficulty from being "
                "self-assessed"))
        if not ex.get("anchor_kind"):
            out.append(Finding(
                "EXE004", where,
                "an anchored-tier item must say what kind of source anchors "
                "it: textbook, paper, official_doc, course_assignment or "
                "benchmark. A course with no textbook still anchors "
                "somewhere; what it may not do is invent the item and call "
                "it hard"))
    return out


def rule_mastery(m: dict, where: str, min_days=None,
                 global_concepts=None) -> list:
    out = []
    min_days = min_days or {}
    state = m.get("state")

    # global_concepts is None when no registry exists yet; an empty set means
    # the registry exists and is empty, which is a different thing
    if global_concepts is not None:
        cid = m.get("concept_id")
        if cid and cid not in global_concepts:
            out.append(Finding(
                "CON004", where,
                "mastery recorded for " + cid + ", which is not in the "
                "concept registry; a concept the system tracks but cannot "
                "name is how two ideas quietly become one"))
    ev = m.get("evidence", []) or []
    passed_kinds = set(e.get("kind") for e in ev if e.get("verdict") == "pass")

    for group in STATE_EVIDENCE_REQUIREMENTS.get(state, []):
        if not passed_kinds.intersection(group):
            out.append(Finding(
                "MAS001", where,
                "state " + str(state) + " requires a passed " +
                " or ".join(group) + ", but none is recorded"))

    down = m.get("downstream") or {}
    if state == "shaky" and not (down.get("hold") or down.get("bypassed")):
        out.append(Finding(
            "MAS002", where,
            "this concept is shaky, so everything depending on it is held "
            "back by default; the record does not say whether the hold is "
            "in force or the learner chose to carry on",
            severity="warning"))
    if down.get("bypassed") and not down.get("bypass_reason"):
        out.append(Finding(
            "MAS005", where,
            "carrying on past a shaky prerequisite is allowed, but the "
            "reason has to be on the record; repeated bypasses on one "
            "concept are themselves a finding"))

    targets = [t.get("depth_target") for t in m.get("depth_targets", [])
               if isinstance(t.get("depth_target"), int)]
    dr = m.get("depth_reached")
    if targets and isinstance(dr, int) and dr > max(targets):
        out.append(Finding(
            "MAS003", where,
            "depth reached " + str(dr) + " exceeds the highest declared "
            "target " + str(max(targets)) + " across the courses that use "
            "this concept; going deeper needs an explicit raise or a "
            "sidequest"))
    seen_courses = [t.get("course_id") for t in m.get("depth_targets", [])]
    dupes = sorted(set(c for c in seen_courses if seen_courses.count(c) > 1))
    if dupes:
        out.append(Finding("MAS006", where,
                           "a course states its depth target once: " +
                           ", ".join(str(d) for d in dupes)))

    # Minimum gaps. These are a floor, not a schedule: the real next-review
    # date is computed per concept from its own recall history, because the
    # delayed retest is there to strengthen the memory, not just to audit it.
    #
    # Recording an early retest is fine; it happened. What is not fine is a
    # state that rests on one. So this checks the claim, not the log: does
    # any qualifying evidence actually sit outside the floor?
    first = _parse_dt(m.get("first_taught", ""))
    needed_kinds = {
        "consolidating": ["delayed_retest"],
        "mastered": ["delayed_retest", "transfer_test"],
    }.get(state, [])
    if first and needed_kinds:
        for kind in needed_kinds:
            key, default = {
                "delayed_retest": ("delayed_retest_min_days", 3),
                "transfer_test": ("transfer_test_min_days", 7),
            }[kind]
            need = min_days.get(key, default)
            dates = [_parse_dt(e.get("date", "")) for e in ev
                     if e.get("kind") == kind and e.get("verdict") == "pass"]
            dates = [d for d in dates if d]
            if dates and max((d - first).days for d in dates) < need:
                out.append(Finding(
                    "MAS004", where,
                    "state " + str(state) + " rests on a " + kind +
                    " that came less than " + str(need) + " days after the "
                    "concept was first taught; recall that soon does not "
                    "consolidate anything, so it does not count"))
    return out


def rule_curriculum(cur: dict, where: str, global_concepts=None) -> list:
    """global_concepts: ids known to the registry, so a prerequisite taught by
    another course resolves instead of looking dangling. None means no
    registry exists yet, so membership is not enforced."""
    registry_known = global_concepts is not None
    global_concepts = set(global_concepts or [])
    out = []
    concept_ids = []
    lesson_ids = []
    module_ids = []
    prereq_edges = {}

    for mod in cur.get("modules", []):
        module_ids.append(mod.get("module_id"))
        for les in mod.get("lessons", []):
            lesson_ids.append(les.get("lesson_id"))
            for c in les.get("concepts", []):
                cid = c.get("concept_id")
                concept_ids.append(cid)
                prereq_edges[cid] = list(c.get("prereq", []) or [])

    for label, ids in (("module_id", module_ids), ("lesson_id", lesson_ids),
                       ("concept_id", concept_ids)):
        dupes = sorted(set(i for i in ids if ids.count(i) > 1))
        if dupes:
            out.append(Finding("CUR001", where,
                               "duplicate " + label + ": " + ", ".join(dupes)))

    if registry_known:
        for cid in concept_ids:
            if cid and cid not in global_concepts:
                out.append(Finding(
                    "CON002", where,
                    cid + " is taught here but is not in the concept "
                    "registry; register it so other courses can reuse it "
                    "instead of re-teaching it"))

    known = set(concept_ids) | global_concepts
    for cid, prereqs in prereq_edges.items():
        for p in prereqs:
            if p == cid:
                out.append(Finding("CUR002", where,
                                   cid + " lists itself as a prerequisite"))
            elif p not in known:
                out.append(Finding(
                    "CUR003", where,
                    cid + " requires " + p + ", which is neither in this "
                    "curriculum nor in the global concept registry; if it "
                    "is assumed background, put it in external_prereq "
                    "instead"))

    colour = {}

    def visit(node, stack):
        colour[node] = 1
        for nxt in prereq_edges.get(node, []):
            if nxt not in prereq_edges:
                continue
            if colour.get(nxt) == 1:
                if nxt in stack:
                    cyc = stack[stack.index(nxt):] + [nxt]
                else:
                    cyc = [node, nxt]
                out.append(Finding("CUR004", where,
                                   "prerequisite cycle: " + " -> ".join(cyc)))
            elif colour.get(nxt, 0) == 0:
                visit(nxt, stack + [nxt])
        colour[node] = 2

    for cid in prereq_edges:
        if colour.get(cid, 0) == 0:
            visit(cid, [cid])

    return out


def rule_course(course: dict, where: str) -> list:
    out = []
    env = course.get("environment") or {}
    if course.get("status") == "active" and not env.get("completed_at"):
        out.append(Finding(
            "CRS001", where,
            "this course is active but its environment setup never ran; "
            "teaching is blocked until it does"))
    return out


def rule_config(cfg: dict, where: str) -> list:
    out = []
    notes = cfg.get("notes") or {}
    if notes and not notes.get("markdown_dir"):
        out.append(Finding(
            "CFG001", where,
            "notes need a markdown_dir. That copy is the one this plugin "
            "reads back, so without it a later lesson cannot find out what "
            "was already established"))
    if notes.get("document_dir") and             notes.get("document_format") == "none":
        out.append(Finding(
            "CFG002", where,
            "a folder for readable documents is set but the format is none, "
            "so nothing would ever be written there", severity="warning"))
    ocr = cfg.get("ocr") or {}
    for key, val in ocr.items():
        if key == "api_key_env":
            continue
        if isinstance(val, str) and re.match(r"^[A-Za-z0-9_\-]{30,}$", val):
            out.append(Finding(
                "CFG003", where,
                "field " + key + " looks like a raw API key; store only the "
                "name of the environment variable that holds it"))
    return out


def _norm_name(s) -> str:
    return re.sub(r"[\s_-]+", "", str(s).strip().lower())


def rule_profile(prof: dict, where: str) -> list:
    """What the learner said about themselves, and what it may be used for.

    The central constraint comes from measurement. Self-rated knowledge gain
    correlates at about zero with gain measured by testing, and self-reported
    level runs consistently above measured level. What learners do report
    accurately is WHICH material they have previously encountered. So a stated
    level is a hypothesis about where to start probing, and never a reason to
    skip the probe. Nothing in code can force a probe to happen, but this rule
    makes the distinction visible wherever the profile is read.
    """
    out = []
    for i, row in enumerate(prof.get("background", []) or []):
        at = where + " background[" + str(i) + "]"
        basis = row.get("basis")
        if not basis:
            out.append(Finding(
                "PRF001", at,
                "this says the learner is at level " + str(row.get("level")) +
                " in " + str(row.get("domain")) + " but not how that was "
                "established. Say self_declared, probe_verified or assessed; "
                "self_declared levels may not be used to skip a prerequisite "
                "probe, and without the basis nobody can tell which this is",
                severity="warning"))
        if basis in ("probe_verified", "assessed") and not row.get("evidence"):
            out.append(Finding(
                "PRF002", at,
                "a level claimed as " + basis + " has to say what established "
                "it; otherwise it is a self-declared level wearing a stronger "
                "label", severity="warning"))

    depth = prof.get("depth_expectation")
    if depth and not (prof.get("purpose") or {}).get("statement"):
        out.append(Finding(
            "PRF003", where,
            "a default depth of " + str(depth) + " is set but there is no "
            "statement of what the learner is studying for. How deep is deep "
            "enough is a consequence of why they are here, and it cannot be "
            "measured later the way their knowledge can",
            severity="warning"))
    return out


def rule_concept_registry(reg: dict, where: str) -> list:
    """Concepts are shared across courses, so the registry is the one place
    where a naming mistake turns into two different ideas being treated as
    one. These checks are the cost of that sharing."""
    out = []
    entries = reg.get("concepts", []) or []

    ids = [e.get("concept_id") for e in entries]
    dupes = sorted(set(i for i in ids if ids.count(i) > 1))
    if dupes:
        out.append(Finding("CON001", where,
                           "duplicate concept_id: " + ", ".join(dupes)))

    # same-looking names in different namespaces: usually a genuine homonym
    # (the same word meaning different things in two fields), occasionally an
    # accidental split. Either way a human decides, once.
    by_name = {}
    for e in entries:
        cid = e.get("concept_id")
        names = [e.get("canonical_title")] + list(e.get("aliases", []) or [])
        for n in names:
            if n:
                by_name.setdefault(_norm_name(n), set()).add(cid)
    declared = {}
    for e in entries:
        declared[e.get("concept_id")] = set(e.get("distinct_from", []) or [])
    for name, cids in by_name.items():
        if len(cids) < 2:
            continue
        unresolved = False
        for a in cids:
            for b in cids:
                if a != b and b not in declared.get(a, set()):
                    unresolved = True
        if unresolved:
            out.append(Finding(
                "CON003", where,
                "these share a name: " + ", ".join(sorted(cids)) + ". "
                "Confirm they really are different ideas by listing each in "
                "the distinct_from of the other, or merge them into one "
                "concept",
                severity="warning"))
    return out


SEMANTIC_RULES = {
    "attempt": rule_attempt,
    "exercise": rule_exercise,
    "course": rule_course,
    "config": rule_config,
    "profile": rule_profile,
    "concept_registry": rule_concept_registry,
}


def semantic_check(doc, schema_name: str, where: str, min_days=None,
                   global_concepts=None) -> list:
    if schema_name == "mastery":
        return rule_mastery(doc, where, min_days, global_concepts)
    if schema_name == "curriculum":
        return rule_curriculum(doc, where, global_concepts)
    fn = SEMANTIC_RULES.get(schema_name)
    return fn(doc, where) if fn else []


# --------------------------------------------------------------------------
# io
# --------------------------------------------------------------------------

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(str(path) + " line " + str(i) + ": " + str(exc))
    return out


def atomic_write_json(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def append_jsonl(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------
# whole-root validation
# --------------------------------------------------------------------------

JSONL_SCHEMAS = {
    "learner/mastery.jsonl": "mastery",
    "learner/energy_log.jsonl": "energy",
}

COURSE_FILES = {
    "course.json": "course",
    "curriculum.json": "curriculum",
    "review_queue.json": "review_queue",
    "sources/index.json": "sources_index",
}

COURSE_JSONL = {
    "attempts.jsonl": "attempt",
    # What the learner produced, and what the teacher delivered. Both, and
    # in the same shape, because for a long time only the first existed and
    # the system quietly became one that only tested.
    "expositions.jsonl": "exposition",
    # The questions themselves. They used to live only in the conversation,
    # which is why nothing could check an explanation against the questions
    # it was meant to be separate from.
    "exercises.jsonl": "exercise",
}


def load_registry(root: Path) -> dict:
    """Return {concept_id: entry}. Empty when no registry exists yet."""
    p = root / "concepts.json"
    if not p.exists():
        return {}
    try:
        reg = read_json(p)
    except json.JSONDecodeError:
        return {}
    return dict((e.get("concept_id"), e)
                for e in reg.get("concepts", []) or []
                if e.get("concept_id"))


def registry_ids(root: Path):
    """Known concept ids, or None when no registry exists yet. An empty set
    and None mean different things: an empty registry still enforces."""
    if not (root / "concepts.json").exists():
        return None
    return set(load_registry(root))


def validate_root(root: Path) -> list:
    findings = []
    if not root.exists():
        return [Finding("ROOT001", str(root),
                        "data root does not exist; run init first")]

    known_concepts = registry_ids(root)
    reg_path = root / "concepts.json"
    if known_concepts is not None:
        doc = read_json(reg_path)
        for e in validate_doc(doc, "concept_registry"):
            findings.append(Finding("SCHEMA", "concepts.json", e))
        findings.extend(rule_concept_registry(doc, "concepts.json"))

    min_days = {}
    cfg_path = root / "config.json"
    if cfg_path.exists():
        try:
            cfg = read_json(cfg_path)
        except json.JSONDecodeError as exc:
            findings.append(Finding("JSON001", "config.json", str(exc)))
            cfg = None
        if cfg is not None:
            min_days = dict(cfg.get("defaults") or {})
            for e in validate_doc(cfg, "config"):
                findings.append(Finding("SCHEMA", "config.json", e))
            findings.extend(semantic_check(cfg, "config", "config.json"))

    prof = root / "learner" / "profile.json"
    if prof.exists():
        pdoc = read_json(prof)
        for e in validate_doc(pdoc, "profile"):
            findings.append(Finding("SCHEMA", "learner/profile.json", e))
        findings.extend(semantic_check(pdoc, "profile",
                                       "learner/profile.json"))

    caps = root / "capabilities.json"
    if caps.exists():
        for e in validate_doc(read_json(caps), "capabilities"):
            findings.append(Finding("SCHEMA", "capabilities.json", e))

    declared_targets = {}   # concept_id -> {course_id: depth_target}
    mastery_rows = []       # (where, row)

    for rel, sname in JSONL_SCHEMAS.items():
        for i, row in enumerate(read_jsonl(root / rel), 1):
            where = rel + ":" + str(i)
            for e in validate_doc(row, sname):
                findings.append(Finding("SCHEMA", where, e))
            findings.extend(semantic_check(row, sname, where, min_days,
                                           known_concepts))
            if sname == "mastery":
                mastery_rows.append((where, row))

    courses_dir = root / "courses"
    if courses_dir.exists():
        for cdir in sorted(p for p in courses_dir.iterdir() if p.is_dir()):
            for fname, sname in COURSE_FILES.items():
                p = cdir / fname
                if not p.exists():
                    continue
                where = "courses/" + cdir.name + "/" + fname
                doc = read_json(p)
                for e in validate_doc(doc, sname):
                    findings.append(Finding("SCHEMA", where, e))
                findings.extend(semantic_check(doc, sname, where, min_days,
                                               known_concepts))
                if sname == "curriculum":
                    cid_course = doc.get("course_id")
                    for mod in doc.get("modules", []):
                        for les in mod.get("lessons", []):
                            for c in les.get("concepts", []):
                                cc = c.get("concept_id")
                                declared_targets.setdefault(cc, {})[cid_course] = \
                                    c.get("depth_target")
            for fname, sname in COURSE_JSONL.items():
                for i, row in enumerate(read_jsonl(cdir / fname), 1):
                    where = "courses/" + cdir.name + "/" + fname + ":" + str(i)
                    for e in validate_doc(row, sname):
                        findings.append(Finding("SCHEMA", where, e))
                    findings.extend(semantic_check(row, sname, where, min_days))
            exdir = cdir / "exercises"
            if exdir.exists():
                for p in sorted(exdir.rglob("*.json")):
                    where = str(p.relative_to(root)).replace(os.sep, "/")
                    doc = read_json(p)
                    for e in validate_doc(doc, "exercise"):
                        findings.append(Finding("SCHEMA", where, e))
                    findings.extend(semantic_check(doc, "exercise", where))
            findings.extend(cross_check_course(cdir, root))

    # a concept is one thing, so the depth each course asks of it must match
    # what that course actually declared in its curriculum
    for where, row in mastery_rows:
        cid = row.get("concept_id")
        if cid not in declared_targets:
            continue
        for t in row.get("depth_targets", []):
            course_id = t.get("course_id")
            declared = declared_targets[cid].get(course_id)
            if declared is None:
                findings.append(Finding(
                    "CON006", where,
                    "claims course " + str(course_id) + " wants " + str(cid) +
                    ", but that curriculum does not list it"))
            elif declared != t.get("depth_target"):
                findings.append(Finding(
                    "CON006", where,
                    "course " + str(course_id) + " asks for depth " +
                    str(declared) + " on " + str(cid) + ", but this record "
                    "says " + str(t.get("depth_target"))))
    return findings


def cross_check_course(cdir: Path, root: Path) -> list:
    """Checks that need more than one file to see."""
    out = []
    label = "courses/" + cdir.name

    cpath = cdir / "course.json"
    curpath = cdir / "curriculum.json"
    course = read_json(cpath) if cpath.exists() else None
    cur = read_json(curpath) if curpath.exists() else None

    if course and cur and course.get("source_anchored"):
        for mod in cur.get("modules", []):
            for les in mod.get("lessons", []):
                concepts = les.get("concepts", []) or []
                has = les.get("source_span") or (
                    bool(concepts) and all(c.get("source_span") for c in concepts))
                if not has:
                    out.append(Finding(
                        "CUR005", label + "/curriculum.json",
                        "lesson " + str(les.get("lesson_id")) + " has no "
                        "source span, but this course is source-anchored"))

    attempts = read_jsonl(cdir / "attempts.jsonl")
    seen_inclass = {}
    for a in attempts:
        for cid in a.get("concept_ids", []):
            if a.get("kind") == "inclass":
                seen_inclass.setdefault(cid, set()).add(a.get("exercise_id"))
            elif a.get("kind") in ("delayed_retest", "transfer_test"):
                if a.get("exercise_id") in seen_inclass.get(cid, set()):
                    out.append(Finding(
                        "ATT004", label + "/attempts.jsonl",
                        "concept " + cid + " was retested with the very same "
                        "item used in class (" + str(a.get("exercise_id")) +
                        "); a retest must use a different item"))
    return out


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_init(args) -> int:
    root = Path(args.root) if args.root else default_root()
    root.mkdir(parents=True, exist_ok=True)
    for d in LAYOUT_DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)
    marker = root / ".zepteach-root"
    if not marker.exists():
        marker.write_text("schema_version=1\ncreated=" + now_iso() + "\n",
                          encoding="utf-8")
    reg = root / "concepts.json"
    if not reg.exists():
        # seeded empty on purpose: concepts are global, and the checks that
        # keep that honest only run once a registry exists
        atomic_write_json(reg, {"schema_version": 1, "updated": now_iso(),
                                "concepts": []})
    print("data root ready: " + str(root))
    if (root / "config.json").exists():
        print("config.json present: setup stage 1 has run")
    else:
        print("config.json absent: setup stage 1 has NOT run yet.")
        print("One question blocks starting: which language to teach in.")
        print("Everything else is asked when it matters - run "
              "intake.py next --group start, then get on with it.")
        print("None of these are defaulted on their behalf.")
    return EXIT_OK


def _load_input(args):
    if getattr(args, "data", None):
        return json.loads(args.data)
    if getattr(args, "file", None):
        return json.loads(Path(args.file).read_text(encoding="utf-8"))
    return json.loads(sys.stdin.read())


def _report(findings: list, quiet: bool = False) -> int:
    errs = [f for f in findings if f.severity == "error"]
    warns = [f for f in findings if f.severity != "error"]
    for f in findings:
        stream = sys.stderr if f.severity == "error" else sys.stdout
        print(str(f), file=stream)
    if not quiet:
        print("errors: " + str(len(errs)) + "  warnings: " + str(len(warns)))
    return EXIT_VALIDATION if errs else EXIT_OK


def cmd_root(args) -> int:
    print(str(Path(args.root) if args.root else default_root()))
    return EXIT_OK


def cmd_schemas(args) -> int:
    for n in schema_names():
        print(n)
    return EXIT_OK


def cmd_schema(args) -> int:
    try:
        print(json.dumps(load_schema(args.name), ensure_ascii=False, indent=2))
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_NOT_FOUND
    return EXIT_OK


def _context(args):
    """Registry ids and gap thresholds, when a data root is reachable."""
    root = Path(args.root) if args.root else default_root()
    known = registry_ids(root) if root.exists() else None
    min_days = {}
    cfg = root / "config.json"
    if cfg.exists():
        try:
            min_days = dict(read_json(cfg).get("defaults") or {})
        except json.JSONDecodeError:
            pass
    return known, min_days


def cmd_check(args) -> int:
    doc = _load_input(args)
    known, min_days = _context(args)
    findings = [Finding("SCHEMA", args.schema, e)
                for e in validate_doc(doc, args.schema)]
    findings.extend(semantic_check(doc, args.schema, args.schema,
                                   min_days, known))
    if not findings:
        print("valid against schema " + args.schema)
        return EXIT_OK
    return _report(findings)


def cmd_validate(args) -> int:
    root = Path(args.root) if args.root else default_root()
    findings = validate_root(root)
    if not findings:
        print("clean: " + str(root))
        return EXIT_OK
    return _report(findings)


def _guarded_write(args, append: bool) -> int:
    root = Path(args.root) if args.root else default_root()
    doc = _load_input(args)
    known, min_days = _context(args)
    findings = [Finding("SCHEMA", args.path, e)
                for e in validate_doc(doc, args.schema)]
    findings.extend(semantic_check(doc, args.schema, args.path,
                                   min_days, known))
    if any(f.severity == "error" for f in findings):
        verb = "append" if append else "write"
        print("refusing to " + verb + ": validation failed", file=sys.stderr)
        return _report(findings)
    target = resolve_in_root(root, args.path)
    if append:
        append_jsonl(target, doc)
        print("appended to " + str(target))
    else:
        atomic_write_json(target, doc)
        print("wrote " + str(target))
    for f in findings:
        print(str(f))
    return EXIT_OK


def cmd_write(args) -> int:
    return _guarded_write(args, append=False)


def cmd_append(args) -> int:
    return _guarded_write(args, append=True)


def cmd_read(args) -> int:
    root = Path(args.root) if args.root else default_root()
    target = resolve_in_root(root, args.path)
    if not target.exists():
        print("not found: " + str(target), file=sys.stderr)
        return EXIT_NOT_FOUND
    if target.suffix == ".jsonl":
        print(json.dumps(read_jsonl(target), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(read_json(target), ensure_ascii=False, indent=2))
    return EXIT_OK


def cmd_transitions(args) -> int:
    print(json.dumps({
        "states": MASTERY_STATES,
        "allowed_transitions": MASTERY_TRANSITIONS,
        "evidence_required": dict(
            (k, [list(g) for g in v])
            for k, v in STATE_EVIDENCE_REQUIREMENTS.items()),
    }, ensure_ascii=False, indent=2))
    return EXIT_OK


def cmd_gate(args) -> int:
    root = Path(args.root) if args.root else default_root()
    cpath = root / "courses" / args.course / "course.json"
    if not cpath.exists():
        print("no such course: " + args.course, file=sys.stderr)
        return EXIT_NOT_FOUND
    course = read_json(cpath)
    env = course.get("environment") or {}
    if args.name != "course-env":
        print("unknown gate: " + args.name, file=sys.stderr)
        return EXIT_NOT_FOUND
    if not env.get("completed_at"):
        print("GATE FAILED: environment setup (stage 2) has not run for "
              "course " + args.course, file=sys.stderr)
        missing = [c.get("target_id")
                   for c in env.get("required_targets", [])]
        if missing:
            print("it still needs to settle: " + ", ".join(missing),
                  file=sys.stderr)
        return EXIT_GATE

    reach = dict((r.get("target_id"), r) for r in env.get("resolution", []))
    required = [t for t in env.get("required_targets", [])
                if t.get("criticality") == "required"]

    gone = sorted(t.get("target_id") for t in required
                  if reach.get(t.get("target_id"), {}).get("reach")
                  in (None, "out_of_reach"))
    if gone:
        print("GATE FAILED: required and out of reach: " + ", ".join(gone),
              file=sys.stderr)
        return EXIT_GATE

    # The ruling that decides whether a shortfall is fatal. A stand-in can
    # carry understanding a long way, and by the evidence often carries it
    # further than the real tool does, because building the thing forces
    # every choice into the open. What it can never do is stand in for
    # competence WITH the real thing. So the question is not how good the
    # substitute is; it is whether the goal names the target. Explaining how
    # a technique organises time survives a constructed example. Reading one
    # particular chapter closely does not survive an imitation of it.
    named = sorted(t.get("target_id") for t in required
                   if t.get("named_in_goal")
                   and reach.get(t.get("target_id"), {}).get("reach")
                   != "direct")
    if named:
        print("GATE FAILED: the goal names these, so nothing substitutes for "
              "them: " + ", ".join(named), file=sys.stderr)
        print("either get hold of them, or rewrite the goal so it asks for "
              "understanding rather than competence with the thing itself.",
              file=sys.stderr)
        return EXIT_GATE

    print("gate ok: course-env for " + args.course)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="zt_state.py",
        description="ZepTeach state engine: schemas, invariants, gates.")
    p.add_argument("--root", help="data root (default: ZEPTEACH_ROOT env, "
                                  "else ZepTeach in your home directory)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("root").set_defaults(func=cmd_root)
    sub.add_parser("init").set_defaults(func=cmd_init)
    sub.add_parser("schemas").set_defaults(func=cmd_schemas)
    sub.add_parser("transitions").set_defaults(func=cmd_transitions)
    sub.add_parser("validate").set_defaults(func=cmd_validate)

    sp = sub.add_parser("schema")
    sp.add_argument("name")
    sp.set_defaults(func=cmd_schema)

    sp = sub.add_parser("check")
    sp.add_argument("--schema", required=True)
    sp.add_argument("--file")
    sp.add_argument("--data")
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("write")
    sp.add_argument("--path", required=True)
    sp.add_argument("--schema", required=True)
    sp.add_argument("--file")
    sp.add_argument("--data")
    sp.set_defaults(func=cmd_write)

    sp = sub.add_parser("append")
    sp.add_argument("--path", required=True)
    sp.add_argument("--schema", required=True)
    sp.add_argument("--file")
    sp.add_argument("--data")
    sp.set_defaults(func=cmd_append)

    sp = sub.add_parser("read")
    sp.add_argument("--path", required=True)
    sp.set_defaults(func=cmd_read)

    sp = sub.add_parser("gate")
    sp.add_argument("name")
    sp.add_argument("--course", required=True)
    sp.set_defaults(func=cmd_gate)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return EXIT_VALIDATION


if __name__ == "__main__":
    sys.exit(main())
