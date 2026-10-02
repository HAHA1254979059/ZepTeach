"""Private actual-event journals never invent progress or overwrite answers."""

import json

import pytest

import feedback as fb


def event(identity="e1", thread="learning-one", **changes):
    row = {"schema_version": 1, "event_id": identity,
           "timestamp_utc": "2026-10-01T00:00:00Z", "learning_thread_id": thread,
           "lab_id": "experiment", "part_id": "one", "event_type": "ui_feedback",
           "source": {"kind": "learner_message", "reference": "fixture-message"},
           "actual_user_input": "The button was not readable.",
           "observed_ui_behavior": "User reported missing button text."}
    return dict(row, **changes)


def test_reading_no_feedback_creates_nothing(tmp_path):
    result = fb.pending(tmp_path, "learning-one", tmp_path / "receipts.jsonl")
    assert result["events"] == []
    assert list(tmp_path.iterdir()) == []


def test_append_preserves_bytes_and_retries_without_duplicate(tmp_path):
    assert fb.append_events(tmp_path, "learning-one", [event()]) == 1
    path = tmp_path / fb.EVENT_LOG
    before = path.read_bytes()
    assert fb.append_events(tmp_path, "learning-one", [event()]) == 0
    assert path.read_bytes() == before
    assert fb.append_events(tmp_path, "learning-one", [event("e2")]) == 1
    assert path.read_bytes().startswith(before)
    assert not list(tmp_path.rglob("mastery.jsonl"))
    assert not list(tmp_path.rglob("attempts.jsonl"))


def test_changed_identity_and_mixed_scope_are_refused_before_writing(tmp_path):
    fb.append_events(tmp_path, "learning-one", [event()])
    before = (tmp_path / fb.EVENT_LOG).read_bytes()
    with pytest.raises(ValueError):
        fb.append_events(tmp_path, "learning-one", [event(actual_user_input="different")])
    with pytest.raises(ValueError):
        fb.append_events(tmp_path, "learning-one", [event("e2"), event("other", "private-other")])
    assert (tmp_path / fb.EVENT_LOG).read_bytes() == before


def test_receipts_handle_only_scoped_new_events_and_remain_separate(tmp_path):
    fb.append_events(tmp_path, "learning-one", [event()])
    fb.append_events(tmp_path, "private-other", [event("other", "private-other")])
    receipts = tmp_path / "receipts.jsonl"
    assert [e["event_id"] for e in fb.pending(tmp_path, "learning-one", receipts)["events"]] == ["e1"]
    evidence = tmp_path / "qa.json"
    evidence.write_text('{"synthetic_preview": true}', encoding="utf-8")
    original = (tmp_path / fb.EVENT_LOG).read_bytes()
    assert fb.record_receipt(tmp_path, "learning-one", receipts, "e1",
                             "implemented_tested", "Controls checked", [str(evidence)]) == 1
    assert fb.record_receipt(tmp_path, "learning-one", receipts, "e1",
                             "implemented_tested", "Controls checked", [str(evidence)]) == 0
    assert fb.pending(tmp_path, "learning-one", receipts)["events"] == []
    fb.append_events(tmp_path, "learning-one", [event("e2")])
    assert [e["event_id"] for e in fb.pending(tmp_path, "learning-one", receipts)["events"]] == ["e2"]
    assert (tmp_path / fb.EVENT_LOG).read_bytes().startswith(original)


def test_lock_and_torn_tail_refuse_instead_of_repairing_history(tmp_path):
    path = tmp_path / fb.EVENT_LOG
    path.parent.mkdir()
    lock = path.with_suffix('.jsonl.lock')
    lock.write_text('', encoding="utf-8")
    with pytest.raises(RuntimeError):
        fb.append_events(tmp_path, "learning-one", [event()])
    assert lock.exists()
    lock.unlink()
    path.write_bytes(b'{"incomplete":')
    with pytest.raises(ValueError):
        fb.append_events(tmp_path, "learning-one", [event()])
    assert path.read_bytes() == b'{"incomplete":'


def test_missing_artifact_not_claimed_but_past_evidence_stays_readable(tmp_path):
    artifact = tmp_path / "view.html"
    row = event(artifact_path_if_exists=str(artifact))
    with pytest.raises(ValueError):
        fb.append_events(tmp_path, "learning-one", [row])
    artifact.write_text('<div>view</div>', encoding="utf-8")
    fb.append_events(tmp_path, "learning-one", [row])
    artifact.unlink()
    assert fb.pending(tmp_path, "learning-one", tmp_path / "receipts.jsonl")["events"] == [row]


def test_ingestion_requires_received_packet_and_does_not_infer_confidence(tmp_path):
    packet = fb.MARKER + json.dumps({"schema_version": 1, "learning_thread_id": "learning-one",
                                    "events": [event()]})
    rows = fb.packet_events(packet, "learning-one")
    fb.append_events(tmp_path, "learning-one", rows)
    assert "confidence_if_supplied" not in fb.read_rows(tmp_path / fb.EVENT_LOG)[0]
    with pytest.raises(ValueError):
        fb.packet_events('{"draft": "answer"}', "learning-one")
    with pytest.raises(ValueError):
        fb.packet_events(packet, "private-other")
