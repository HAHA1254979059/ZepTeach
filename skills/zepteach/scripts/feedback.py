#!/usr/bin/env python3
"""Append real learning feedback and read only unhandled events in one scope.

This journal is separate from attempts, grades and course progress. Browser
state is not the journal: the learning assistant appends only after receiving
the learner's message or an actual submitted interaction packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import zt_state as zs

MARKER = "[ZepTeach interaction] "
EVENT_LOG = "feedback/interactive-learning-feedback.jsonl"
RECEIPT_LOG = "feedback/interactive-development-receipts.jsonl"


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False,
                          sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_rows(path: Path):
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("journal has an incomplete last line; nothing was changed")
    rows = []
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError("empty journal line " + str(number))
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("journal row must be an object")
        rows.append(row)
    return rows


def check_event(event: dict, thread_id: str, check_artifact: bool = True):
    errors = zs.validate_doc(event, "feedback_event")
    if errors:
        raise ValueError("invalid feedback: " + "; ".join(errors))
    if event["learning_thread_id"] != thread_id:
        raise ValueError("feedback belongs to a different learning thread")
    when = datetime.fromisoformat(event["timestamp_utc"].replace("Z", "+00:00"))
    if when.utcoffset() is None or when.utcoffset().total_seconds() != 0:
        raise ValueError("feedback time must be UTC")
    artifact = event.get("artifact_path_if_exists")
    if artifact and (not Path(artifact).is_absolute() or
                     (check_artifact and not Path(artifact).is_file())):
        raise ValueError("feedback artifact must be an existing absolute file")


def append_rows(path: Path, rows: list, key: str):
    """Lock, validate identity, append and fsync; never rewrite the history."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("journal must not be a symbolic link")
    lock = path.with_suffix(path.suffix + ".lock")
    try:
        descriptor = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        raise RuntimeError("journal is locked; do not bypass or remove the lock")
    try:
        os.close(descriptor)
        existing = {}
        for row in read_rows(path):
            identity = row.get(key)
            if identity in existing and existing[identity] != row:
                raise ValueError("conflicting stored identity: " + str(identity))
            existing[identity] = row
        additions = []
        for row in rows:
            identity = row[key]
            if identity in existing:
                if existing[identity] != row:
                    raise ValueError("identity already exists with different content: " + identity)
                continue
            existing[identity] = row
            additions.append(row)
        if additions:
            content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) +
                              "\n" for row in additions).encode("utf-8")
            with path.open("ab") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        return len(additions)
    finally:
        lock.unlink()


def append_events(root: Path, thread_id: str, events: list):
    if not root.is_dir():
        raise FileNotFoundError("learning data root does not exist")
    if not events:
        raise ValueError("no received events; do not create an empty feedback log")
    for event in events:
        check_event(event, thread_id)
    path = root / EVENT_LOG
    # A junction in the feedback directory must not write outside this root.
    path.resolve().relative_to(root.resolve())
    return append_rows(path, events, "event_id")


def packet_events(text: str, thread_id: str):
    if not text.startswith(MARKER):
        raise ValueError("not a submitted interaction packet")
    packet = json.loads(text[len(MARKER):])
    if not isinstance(packet, dict) or set(packet) != {"schema_version", "learning_thread_id", "events"}:
        raise ValueError("unexpected interaction packet fields")
    if packet["schema_version"] != 1 or packet["learning_thread_id"] != thread_id:
        raise ValueError("interaction packet has the wrong version or thread")
    if not isinstance(packet["events"], list) or len(packet["events"]) > 80:
        raise ValueError("invalid event batch")
    return packet["events"]


def scoped_events(root: Path, thread_id: str):
    events = {}
    for event in read_rows(root / EVENT_LOG):
        if event.get("learning_thread_id") != thread_id:
            continue
        check_event(event, thread_id, check_artifact=False)
        identity = event["event_id"]
        if identity in events and events[identity] != event:
            raise ValueError("conflicting event identity")
        events[identity] = event
    return events


def pending(root: Path, thread_id: str, receipts: Path, limit: int = 20):
    events = scoped_events(root, thread_id)
    handled = set()
    for row in read_rows(receipts):
        if row.get("learning_thread_id") != thread_id:
            continue
        errors = zs.validate_doc(row, "feedback_receipt")
        if errors:
            raise ValueError("invalid receipt: " + "; ".join(errors))
        event = events.get(row["event_id"])
        if event is None or digest(event) != row["event_sha256"]:
            raise ValueError("receipt does not match its immutable source event")
        handled.add(row["event_id"])
    unseen = [event for identity, event in events.items() if identity not in handled]
    return {"learning_thread_id": thread_id, "unhandled_count": len(unseen),
            "events": unseen[:limit]}


def record_receipt(root: Path, thread_id: str, receipts: Path,
                   event_id: str, status: str, note: str, evidence: list):
    events = scoped_events(root, thread_id)
    if event_id not in events:
        raise ValueError("receipt must refer to an actual scoped event")
    proof = []
    for filename in evidence:
        path = Path(filename)
        if not path.is_absolute() or not path.is_file():
            raise ValueError("receipt evidence must be an existing absolute file")
        proof.append({"path": str(path.resolve()),
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    body = {"schema_version": 1, "learning_thread_id": thread_id,
            "event_id": event_id, "event_sha256": digest(events[event_id]),
            "status": status, "note": note, "evidence": proof}
    identity = "receipt-" + digest(body)
    for old in read_rows(receipts):
        if old.get("receipt_id") == identity:
            return 0
    row = dict(body, receipt_id=identity, timestamp_utc=utcnow())
    errors = zs.validate_doc(row, "feedback_receipt")
    if errors:
        raise ValueError("invalid receipt: " + "; ".join(errors))
    if status == "implemented_tested" and not proof:
        raise ValueError("tested receipt needs concrete local evidence")
    return append_rows(receipts, [row], "receipt_id")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--receipts", help="private local receipt journal")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("append")
    add.add_argument("--file", required=True, help="one real event JSON")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--message-file", required=True, help="actual received message")
    poll = sub.add_parser("pending")
    poll.add_argument("--limit", type=int, default=20)
    receipt = sub.add_parser("receipt")
    receipt.add_argument("--event-id", required=True)
    receipt.add_argument("--status", required=True, choices=[
        "implemented_tested", "waiting_for_learner", "needs_information", "out_of_scope"])
    receipt.add_argument("--note", required=True)
    receipt.add_argument("--evidence", action="append", default=[])
    args = parser.parse_args(argv)
    root = Path(args.root)
    receipts = Path(args.receipts) if args.receipts else root / RECEIPT_LOG
    try:
        if args.command == "pending":
            if args.limit < 1 or args.limit > 100:
                raise ValueError("limit must be 1-100")
            result = pending(root, args.thread_id, receipts, args.limit)
        elif args.command == "receipt":
            result = {"appended": record_receipt(root, args.thread_id, receipts,
                      args.event_id, args.status, args.note, args.evidence)}
        else:
            if args.command == "append":
                events = [json.loads(Path(args.file).read_text(encoding="utf-8"))]
            else:
                events = packet_events(Path(args.message_file).read_text(encoding="utf-8"),
                                       args.thread_id)
            result = {"appended": append_events(root, args.thread_id, events),
                      "acknowledged_event_ids": [event["event_id"] for event in events]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return zs.EXIT_OK
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return zs.EXIT_GATE
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return zs.EXIT_NOT_FOUND
    except (ValueError, TypeError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return zs.EXIT_VALIDATION


if __name__ == "__main__":
    sys.exit(main())
