"""轻量级 LLM 调用追踪器，用于可观测性 Dashboard。"""
from __future__ import annotations

import threading
import time
from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CallRecord:
    timestamp: float
    operation: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    status: str = "success"
    player_id: str = ""
    npc_id: str = ""
    error_msg: str = ""
    parse_success: bool = True
    schema_violations: list[str] = field(default_factory=list)


class CallTracker:
    """LLM 调用追踪器（单例），维护最近 1000 条调用记录。"""

    def __init__(self, maxlen: int = 1000) -> None:
        self._records: deque[CallRecord] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._read_lock = threading.Lock()

    def record(self, call: CallRecord) -> None:
        with self._lock:
            self._records.append(call)

    def summary(self, window_s: float = 300.0) -> dict[str, Any]:
        with self._read_lock:
            now = time.time()
            cutoff = now - window_s
            records = [r for r in self._records if r.timestamp >= cutoff]
            if not records:
                return {
                    "total_calls": 0,
                    "success_rate": 0.0,
                    "avg_latency_ms": 0.0,
                    "p50_latency_ms": 0.0,
                    "p95_latency_ms": 0.0,
                    "total_tokens_in": 0,
                    "total_tokens_out": 0,
                    "by_operation": {},
                }
            total = len(records)
            successes = sum(1 for r in records if r.status == "success")
            latencies = sorted(r.latency_ms for r in records)
            by_op: dict[str, list[CallRecord]] = {}
            for r in records:
                by_op.setdefault(r.operation, []).append(r)
            by_operation: dict[str, dict[str, Any]] = {}
            for op, op_records in by_op.items():
                op_total = len(op_records)
                op_success = sum(1 for r in op_records if r.status == "success")
                op_latencies = sorted(r.latency_ms for r in op_records)
                by_operation[op] = {
                    "total_calls": op_total,
                    "success_rate": round(op_success / op_total, 4) if op_total else 0.0,
                    "avg_latency_ms": round(sum(op_latencies) / len(op_latencies), 2) if op_latencies else 0.0,
                    "p50_latency_ms": round(op_latencies[len(op_latencies) // 2], 2) if op_latencies else 0.0,
                    "total_tokens_in": sum(r.tokens_in for r in op_records),
                    "total_tokens_out": sum(r.tokens_out for r in op_records),
                }
            return {
                "total_calls": total,
                "success_rate": round(successes / total, 4) if total else 0.0,
                "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
                "p50_latency_ms": round(latencies[len(latencies) // 2], 2) if latencies else 0.0,
                "p95_latency_ms": round(latencies[int(len(latencies) * 0.95)], 2) if latencies else 0.0,
                "total_tokens_in": sum(r.tokens_in for r in records),
                "total_tokens_out": sum(r.tokens_out for r in records),
                "by_operation": by_operation,
            }

    def eval_summary(self, window_s: float = 3600.0) -> dict[str, Any]:
        with self._read_lock:
            now = time.time()
            cutoff = now - window_s
            records = [r for r in self._records if r.timestamp >= cutoff]
            if not records:
                return {
                    "parse_success_rate": 0.0,
                    "common_violations": [],
                    "by_npc": {},
                }
            total = len(records)
            parse_ok = sum(1 for r in records if r.parse_success)
            violation_counter: Counter[str] = Counter()
            for r in records:
                for v in r.schema_violations:
                    violation_counter[v] += 1
            by_npc: dict[str, dict[str, Any]] = {}
            npc_records: dict[str, list[CallRecord]] = {}
            for r in records:
                if r.npc_id:
                    npc_records.setdefault(r.npc_id, []).append(r)
            for npc_id, nr in npc_records.items():
                n_total = len(nr)
                n_fail = sum(1 for r in nr if not r.parse_success)
                by_npc[npc_id] = {
                    "total": n_total,
                    "parse_failures": n_fail,
                    "parse_failure_rate": round(n_fail / n_total, 4) if n_total else 0.0,
                }
            return {
                "parse_success_rate": round(parse_ok / total, 4) if total else 0.0,
                "common_violations": violation_counter.most_common(10),
                "by_npc": by_npc,
            }

    def recent_calls(self, n: int = 20) -> list[dict[str, Any]]:
        with self._read_lock:
            records = list(self._records)[-n:]
            return [asdict(r) for r in records]


_tracker: CallTracker | None = None


def get_tracker() -> CallTracker:
    global _tracker
    if _tracker is None:
        _tracker = CallTracker()
    return _tracker
