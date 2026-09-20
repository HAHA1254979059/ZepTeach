#!/usr/bin/env python3
"""What ZepTeach is allowed to touch, and what it will not do.

One guard, applied wherever work runs. The rules do not vary by where a tool
lives, because the reasons for them do not: a directory nobody mentioned is
not this plugin's to look in, whether it sits on the machine running these
scripts or somewhere the learner reaches on its behalf.

Two kinds of refusal:

  Paths outside what the learner permitted. Including reads.

  Commands that change the environment. Installing packages, loading modules,
  editing startup files, setting variables that persist. These are refused
  and referred to the learner, even when the learner would obviously say yes,
  because an environment other people depend on can be changed in ways that
  are hard to undo and hard to notice.

This file decides. It does not carry anything out, and it holds no notion of
how a tool is reached: that is recorded per course in the resources file, in
whatever terms the learner gave.

Exit codes: 0 allowed, 3 refused.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import shlex
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

sys.path.insert(0, str(Path(__file__).resolve().parent))

import constants as K  # noqa: E402
import zt_state as zs  # noqa: E402


class Refused(Exception):
    """Raised instead of returning a value, so that a caller that forgets to
    check the result still does not proceed."""

    def __init__(self, code: str, message: str, suggestion: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.suggestion = suggestion

    def as_dict(self):
        out = {"allowed": False, "code": self.code, "why": self.message}
        if self.suggestion:
            out["instead"] = self.suggestion
        return out


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------

def normalise(path: str, posix: bool = True) -> str:
    """Reduce a path to its plainest form without touching the filesystem.

    Done without the filesystem on purpose. The path may name somewhere this
    code cannot see, and a check that only works for paths it can open would
    be exactly the wrong half of the guard.
    """
    p = str(path).strip().replace("\\", "/") if posix else str(path).strip()
    if posix:
        # posixpath.normpath removes . and resolves .. textually, which is
        # what is wanted here: a caller that writes a/../../b is asking for
        # the parent, whatever the filesystem happens to contain.
        p = posixpath.normpath(p)
    return p


def _is_within(candidate: str, prefix: str) -> bool:
    """Whether candidate is the prefix directory or something inside it.

    Compared component by component rather than as strings. The string
    comparison is the classic error in this kind of code and it is not
    obvious by reading: "/home/u/work-notes".startswith("/home/u/work") is
    true, and those are two unrelated directories.
    """
    c = PurePosixPath(normalise(candidate)).parts
    p = PurePosixPath(normalise(prefix)).parts
    return len(c) >= len(p) and c[:len(p)] == p


def check_path(path: str, allowlist, purpose: str = "touch") -> str:
    """Return the path if it is permitted, otherwise refuse.

    An empty allowlist refuses everything. That is the intended reading:
    where nothing was permitted, nothing may be done, and defaulting the
    other way would turn a configuration mistake into an unrestricted one.
    """
    allowlist = list(allowlist or [])
    raw = str(path)

    if not allowlist:
        raise Refused(
            "SBX001",
            "no directories were permitted here, so " + raw + " cannot be " +
            purpose + "ed",
            "ask the learner which directories may be used, and record them")

    if raw.startswith("~"):
        raise Refused(
            "SBX002",
            raw + " starts with ~, which means a different directory "
            "depending on who is logged in",
            "give the path in full")

    if re.match(r"^[a-zA-Z]+://", raw):
        raise Refused(
            "SBX003", raw + " is a URL, not a path",
            "fetch material through the tools meant for it, not through "
            "the part that runs commands")

    if raw.startswith("\\\\") or raw.startswith("//"):
        raise Refused(
            "SBX004",
            raw + " points at a network share, which is outside anything "
            "the learner listed",
            "copy what is needed into a permitted directory first")

    if not PureWindowsPath(raw).is_absolute() and \
            not PurePosixPath(normalise(raw)).is_absolute():
        raise Refused(
            "SBX005",
            raw + " is relative, so what it refers to depends on where the "
            "command happens to start",
            "give the path in full")

    norm = normalise(raw)
    for prefix in allowlist:
        if _is_within(norm, prefix):
            return norm

    raise Refused(
        "SBX006",
        norm + " is not inside anything the learner permitted (" +
        ", ".join(allowlist) + ")",
        "either work inside a permitted directory, or ask the learner to "
        "add this one and say why")


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
#
# Each pattern says what it catches and what to do instead. The suggestion is
# not politeness: a refusal with no alternative gets worked around, and the
# workaround will be worse than the thing that was refused.

ENV_CHANGES = [
    (r"\b(pip|pip3|python\s+-m\s+pip)\s+(install|uninstall)\b",
     "installs or removes a Python package",
     "tell the learner exactly what is missing and let them install it"),
    (r"\b(conda|mamba)\s+(install|remove|create|env)\b",
     "changes a conda environment",
     "tell the learner what is missing; environments are often shared"),
    (r"\b(apt|apt-get|yum|dnf|brew|pacman|zypper)\s+(install|remove)\b",
     "installs system software",
     "this needs the learner, and usually their administrator"),
    (r"\bmodule\s+(load|unload|purge|swap)\b",
     "changes which modules are loaded on a shared machine",
     "ask the learner which modules to use and put them in the job script "
     "they approve"),
    (r"\b(npm|yarn|pnpm)\s+(install|add|remove)\b",
     "installs a package",
     "tell the learner what is missing"),
    (r">>?\s*[^|]*\.(bashrc|zshrc|profile|bash_profile|cshrc)\b",
     "edits a startup file, which changes every future session",
     "nothing ZepTeach does should need this; if it seems to, say so and "
     "stop"),
    (r"\bexport\s+[A-Za-z_]\w*=",
     "sets an environment variable",
     "pass what is needed to the one command that needs it, rather than "
     "changing the environment"),
    (r"\b(chmod|chown|chgrp)\b",
     "changes who may read or write a file",
     "permissions belong to the learner and to whoever else uses the "
     "machine"),
    (r"\b(systemctl|service|crontab)\b",
     "changes something that keeps running after this is over",
     "ZepTeach does not leave anything running behind it"),
    (r"\b(rm|rmdir)\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)*(/|~|\*)",
     "deletes broadly, from a root or home directory or by wildcard",
     "name the specific file, inside a permitted directory"),
    (r"\bgit\s+config\s+--global\b",
     "changes git settings for every repository on the machine",
     "if a setting is needed, it is needed for one repository"),
    (r"\bsudo\b|\bsu\s",
     "runs as another user",
     "anything needing this needs the learner to do it themselves"),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), what, instead)
             for p, what, instead in ENV_CHANGES]


def check_command(command, allowlist=None, timeout=None,
                  paths_in_command=None) -> dict:
    """Refuse a command that changes the environment, or has no time limit.

    command may be a string or an argument list. The string form is checked
    as written, because that is what a shell would receive.
    """
    text = command if isinstance(command, str) else " ".join(
        shlex.quote(str(a)) for a in command)

    for pattern, what, instead in _COMPILED:
        if pattern.search(text):
            raise Refused(
                "SBX010",
                "this " + what + ", which ZepTeach does not do without "
                "being told to each time: " + text.strip()[:120],
                instead + ". Say what is needed and why, and let the learner "
                "decide")

    if timeout is None:
        raise Refused(
            "SBX011",
            "no time limit was given for: " + text.strip()[:120],
            "every command gets a limit. A run that hangs otherwise waits "
            "for as long as the learner is willing to sit there")

    if timeout <= 0 or timeout > K.MAX_COMMAND_TIMEOUT_SECONDS:
        raise Refused(
            "SBX012",
            "the time limit " + str(timeout) + "s is outside what is "
            "allowed (1 to " + str(K.MAX_COMMAND_TIMEOUT_SECONDS) + ")",
            "if the work genuinely takes longer, it should be submitted as "
            "a job rather than waited on")

    checked = []
    for p in (paths_in_command or []):
        checked.append(check_path(p, allowlist, purpose="us"))

    return {"allowed": True, "command": text, "timeout_seconds": timeout,
            "paths": checked}


def check_job(spec: dict, where: dict) -> dict:
    """A piece of work to run somewhere, checked as a whole.

    where is a tool's invocation block from the course resources file. The
    same checks apply wherever the work runs, which is the point of this
    file: the rules were written once and tested once.
    """
    allow = where.get("allowed_paths") or where.get(
        "workdir_allowlist") or []
    workdir = spec.get("workdir") or where.get("workdir")
    if not workdir:
        raise Refused("SBX020", "no directory was given to work in",
                      "name one inside what the learner permitted")

    checked_workdir = check_path(workdir, allow, purpose="work in")

    timeout = spec.get("timeout_seconds") or where.get("timeout_seconds")
    result = check_command(spec.get("command"), allow, timeout,
                           spec.get("paths"))

    cores = spec.get("cores")
    budget = where.get("size_limit")
    if where.get("shared_with_others"):
        if cores is None:
            raise Refused(
                "SBX021",
                "other people depend on this and the work does not say how "
                "much of it to take",
                "state a number; where nothing else rations it, this is the "
                "only thing stopping one piece of work taking everything")
        if budget and cores > budget:
            raise Refused(
                "SBX022",
                "this asks for " + str(cores) + " and the limit the learner "
                "set is " + str(budget),
                "reduce it, or ask the learner whether the limit should "
                "change")

    result["workdir"] = checked_workdir
    if cores is not None:
        result["cores"] = cores
    return result


# ---------------------------------------------------------------------------
# credentials
# ---------------------------------------------------------------------------

SECRET_SHAPES = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "a private key"),
    (re.compile(r"\bsk-[A-Za-z0-9]{16,}"), "an API key"),
    (re.compile(r"(?i)\b(password|passwd|pwd|secret|token)\s*[:=]\s*\S+"),
     "a password or token"),
]


def check_no_secret(text: str, where: str = "this value") -> None:
    """Refuse to store or log something that looks like a credential.

    Configuration holds the NAME of an environment variable, or the path of a
    file. Never the contents. This catches the case where a value was pasted
    into the wrong field, which is easy to do and quiet when it happens.
    """
    for pattern, what in SECRET_SHAPES:
        if pattern.search(str(text)):
            raise Refused(
                "SBX030",
                where + " contains what looks like " + what,
                "store the name of an environment variable, or the path of "
                "the file holding it. The value itself is never written "
                "down here and never appears on a command line")


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def _report(fn, args) -> int:
    try:
        out = fn()
    except Refused as r:
        if args.json:
            print(json.dumps(r.as_dict(), ensure_ascii=False, indent=2))
        else:
            print("REFUSED [" + r.code + "]  " + r.message, file=sys.stderr)
            if r.suggestion:
                print("instead: " + r.suggestion, file=sys.stderr)
        return zs.EXIT_GATE
    print(json.dumps(out, ensure_ascii=False, indent=2) if args.json
          else "allowed")
    return zs.EXIT_OK


def cmd_path(args) -> int:
    return _report(lambda: {"allowed": True,
                            "path": check_path(args.path, args.allow)}, args)


def cmd_command(args) -> int:
    return _report(
        lambda: check_command(args.command, args.allow, args.timeout), args)


def cmd_job(args) -> int:
    spec = json.loads(args.spec)
    where = json.loads(args.where)
    return _report(lambda: check_job(spec, where), args)


def cmd_rules(args) -> int:
    """Print what gets refused. Used when explaining a refusal, so the
    explanation is the same every time it is given."""
    if args.json:
        print(json.dumps(
            [{"catches": w, "instead": i} for _, w, i in ENV_CHANGES],
            ensure_ascii=False, indent=2))
        return zs.EXIT_OK
    print("REFUSED: changes to the environment")
    for _, what, instead in ENV_CHANGES:
        print("  - " + what)
        print("      instead: " + instead)
    print("")
    print("REFUSED: paths outside what the learner permitted, reads "
          "included")
    print("REFUSED: any command with no time limit")
    print("REFUSED: storing a password, key or token anywhere")
    return zs.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sandbox.py",
        description="What may be touched, and what will not be done.")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("path")
    sp.add_argument("path")
    sp.add_argument("--allow", action="append", default=[])
    sp.set_defaults(func=cmd_path)

    sp = sub.add_parser("command")
    sp.add_argument("command")
    sp.add_argument("--allow", action="append", default=[])
    sp.add_argument("--timeout", type=int)
    sp.set_defaults(func=cmd_command)

    sp = sub.add_parser("job")
    sp.add_argument("--spec", required=True)
    sp.add_argument("--where", required=True,
                    help="a tool's invocation block from the course "
                         "resources file")
    sp.set_defaults(func=cmd_job)

    sp = sub.add_parser("rules")
    sp.set_defaults(func=cmd_rules)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
