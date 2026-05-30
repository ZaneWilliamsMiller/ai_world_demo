from __future__ import annotations

import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from backend.observability.tracker import CallRecord, CallTracker, get_tracker


def _record(tracker: CallTracker, call: CallRecord) -> None:
    tracker.record(call)


@pytest.fixture(autouse=True)
def _reset_tracker():
    import backend.observability.tracker as mod
    mod._tracker = None
    yield
    mod._tracker = None


class TestCallRecord:

    def test_default_values(self):
        r = CallRecord(timestamp=1000.0, operation="npc_talk", model="gpt-4")
        assert r.tokens_in == 0
        assert r.tokens_out == 0
        assert r.latency_ms == 0.0
        assert r.status == "success"
        assert r.player_id == ""
        assert r.npc_id == ""
        assert r.error_msg == ""
        assert r.parse_success is True
        assert r.schema_violations == []

    def test_asdict_serialization(self):
        r = CallRecord(
            timestamp=1000.0,
            operation="npc_talk",
            model="gpt-4",
            tokens_in=10,
            tokens_out=20,
            latency_ms=150.0,
            status="success",
            player_id="p1",
            npc_id="npc1",
            error_msg="",
            parse_success=True,
            schema_violations=["missing_field"],
        )
        d = asdict(r)
        assert d["timestamp"] == 1000.0
        assert d["operation"] == "npc_talk"
        assert d["model"] == "gpt-4"
        assert d["tokens_in"] == 10
        assert d["tokens_out"] == 20
        assert d["latency_ms"] == 150.0
        assert d["status"] == "success"
        assert d["player_id"] == "p1"
        assert d["npc_id"] == "npc1"
        assert d["parse_success"] is True
        assert d["schema_violations"] == ["missing_field"]


class TestCallTracker:

    def test_record_adds_entry(self):
        tracker = CallTracker()
        assert len(tracker._records) == 0
        _record(tracker, CallRecord(timestamp=time.time(), operation="npc_talk", model="gpt-4"))
        assert len(tracker._records) == 1

    def test_summary_empty_returns_zeros(self):
        tracker = CallTracker()
        s = tracker.summary()
        assert s["total_calls"] == 0
        assert s["success_rate"] == 0.0
        assert s["avg_latency_ms"] == 0.0
        assert s["p50_latency_ms"] == 0.0
        assert s["p95_latency_ms"] == 0.0
        assert s["total_tokens_in"] == 0
        assert s["total_tokens_out"] == 0
        assert s["by_operation"] == {}

    def test_summary_calculates_success_rate(self):
        tracker = CallTracker()
        now = time.time()
        for i in range(3):
            _record(tracker, CallRecord(timestamp=now, operation="npc_talk", model="gpt-4", status="success"))
        _record(tracker, CallRecord(timestamp=now, operation="npc_talk", model="gpt-4", status="failed"))
        s = tracker.summary()
        assert s["total_calls"] == 4
        assert s["success_rate"] == 0.75

    def test_summary_calculates_latency(self):
        tracker = CallTracker()
        now = time.time()
        for ms in [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0]:
            _record(tracker, CallRecord(timestamp=now, operation="npc_talk", model="gpt-4", latency_ms=ms))
        s = tracker.summary()
        assert s["avg_latency_ms"] == 550.0
        assert s["p50_latency_ms"] == 600.0
        assert s["p95_latency_ms"] == 1000.0

    def test_summary_by_operation(self):
        tracker = CallTracker()
        now = time.time()
        _record(tracker, CallRecord(timestamp=now, operation="npc_talk", model="gpt-4", latency_ms=100.0, tokens_in=10, tokens_out=20))
        _record(tracker, CallRecord(timestamp=now, operation="npc_talk", model="gpt-4", latency_ms=200.0, tokens_in=5, tokens_out=10))
        _record(tracker, CallRecord(timestamp=now, operation="reflect", model="gpt-4", latency_ms=300.0, tokens_in=30, tokens_out=40))
        s = tracker.summary()
        assert "npc_talk" in s["by_operation"]
        assert "reflect" in s["by_operation"]
        assert s["by_operation"]["npc_talk"]["total_calls"] == 2
        assert s["by_operation"]["npc_talk"]["success_rate"] == 1.0
        assert s["by_operation"]["npc_talk"]["avg_latency_ms"] == 150.0
        assert s["by_operation"]["npc_talk"]["p50_latency_ms"] == 200.0
        assert s["by_operation"]["npc_talk"]["total_tokens_in"] == 15
        assert s["by_operation"]["npc_talk"]["total_tokens_out"] == 30
        assert s["by_operation"]["reflect"]["total_calls"] == 1

    def test_summary_token_counts(self):
        tracker = CallTracker()
        now = time.time()
        _record(tracker, CallRecord(timestamp=now, operation="npc_talk", model="gpt-4", tokens_in=100, tokens_out=200))
        _record(tracker, CallRecord(timestamp=now, operation="npc_talk", model="gpt-4", tokens_in=50, tokens_out=80))
        s = tracker.summary()
        assert s["total_tokens_in"] == 150
        assert s["total_tokens_out"] == 280

    def test_eval_summary_empty(self):
        tracker = CallTracker()
        s = tracker.eval_summary()
        assert s["parse_success_rate"] == 0.0
        assert s["common_violations"] == []
        assert s["by_npc"] == {}

    def test_eval_summary_parse_rate(self):
        tracker = CallTracker()
        now = time.time()
        for i in range(3):
            _record(tracker, CallRecord(timestamp=now, operation="npc_talk", model="gpt-4", parse_success=True))
        _record(tracker, CallRecord(timestamp=now, operation="npc_talk", model="gpt-4", parse_success=False))
        s = tracker.eval_summary()
        assert s["parse_success_rate"] == 0.75

    def test_eval_summary_common_violations(self):
        tracker = CallTracker()
        now = time.time()
        _record(tracker, CallRecord(timestamp=now, operation="npc_talk", model="gpt-4", schema_violations=["missing_field", "type_error"]))
        _record(tracker, CallRecord(timestamp=now, operation="npc_talk", model="gpt-4", schema_violations=["missing_field"]))
        _record(tracker, CallRecord(timestamp=now, operation="npc_talk", model="gpt-4", schema_violations=["type_error"]))
        s = tracker.eval_summary()
        violations = s["common_violations"]
        assert violations[0] == ("missing_field", 2)
        assert violations[1] == ("type_error", 2)

    def test_eval_summary_by_npc(self):
        tracker = CallTracker()
        now = time.time()
        _record(tracker, CallRecord(timestamp=now, operation="npc_talk", model="gpt-4", npc_id="npc1", parse_success=True))
        _record(tracker, CallRecord(timestamp=now, operation="npc_talk", model="gpt-4", npc_id="npc1", parse_success=False))
        _record(tracker, CallRecord(timestamp=now, operation="npc_talk", model="gpt-4", npc_id="npc2", parse_success=True))
        s = tracker.eval_summary()
        assert "npc1" in s["by_npc"]
        assert "npc2" in s["by_npc"]
        assert s["by_npc"]["npc1"]["total"] == 2
        assert s["by_npc"]["npc1"]["parse_failures"] == 1
        assert s["by_npc"]["npc1"]["parse_failure_rate"] == 0.5
        assert s["by_npc"]["npc2"]["total"] == 1
        assert s["by_npc"]["npc2"]["parse_failures"] == 0

    def test_recent_calls(self):
        tracker = CallTracker()
        now = time.time()
        for i in range(25):
            _record(tracker, CallRecord(timestamp=now, operation=f"op_{i}", model="gpt-4"))
        calls = tracker.recent_calls(10)
        assert len(calls) == 10
        assert calls[0]["operation"] == "op_15"
        assert calls[-1]["operation"] == "op_24"

    def test_deque_maxlen_overflow(self):
        tracker = CallTracker(maxlen=5)
        now = time.time()
        for i in range(10):
            _record(tracker, CallRecord(timestamp=now, operation=f"op_{i}", model="gpt-4"))
        assert len(tracker._records) == 5
        assert next(iter(tracker._records)).operation == "op_5"
        assert list(tracker._records)[-1].operation == "op_9"


class TestGetTracker:

    def test_returns_singleton(self):
        t1 = get_tracker()
        t2 = get_tracker()
        assert t1 is t2
