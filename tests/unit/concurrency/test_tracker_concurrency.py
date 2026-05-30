from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from backend.observability.tracker import CallRecord, CallTracker


class TestTrackerConcurrency:

    def test_concurrent_record_count(self):
        tracker = CallTracker(maxlen=10000)
        n = 1000

        def worker() -> None:
            for _ in range(n):
                tracker.record(CallRecord(timestamp=time.time(), operation="test", model="gpt-4"))

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(tracker._records) == n * 10

    def test_concurrent_record_no_loss(self):
        tracker = CallTracker(maxlen=10000)
        n = 500

        def worker(thread_id: int) -> None:
            for i in range(n):
                tracker.record(
                    CallRecord(
                        timestamp=time.time(),
                        operation=f"op_{thread_id}_{i}",
                        model="gpt-4",
                    )
                )

        threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(tracker._records) == n * 10

    def test_concurrent_record_and_read(self):
        tracker = CallTracker()
        n = 200
        summary_results = []

        def writer() -> None:
            for _ in range(n):
                tracker.record(CallRecord(timestamp=time.time(), operation="write", model="gpt-4"))

        def reader() -> None:
            for _ in range(n):
                s = tracker.summary()
                summary_results.append(s["total_calls"])

        t_write = threading.Thread(target=writer)
        t_read = threading.Thread(target=reader)
        t_write.start()
        t_read.start()
        t_write.join()
        t_read.join()

        final = tracker.summary()
        assert final["total_calls"] == n

    def test_concurrent_record_different_operations(self):
        tracker = CallTracker()
        n = 100

        def worker(op_name: str) -> None:
            for _ in range(n):
                tracker.record(
                    CallRecord(
                        timestamp=time.time(),
                        operation=op_name,
                        model="gpt-4",
                        latency_ms=100.0,
                    )
                )

        threads = [
            threading.Thread(target=worker, args=(f"op_{i}",))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(tracker._records) == n * 5

    def test_deque_overflow_under_contention(self):
        tracker = CallTracker(maxlen=100)
        n = 200

        def worker() -> None:
            for _ in range(n):
                tracker.record(CallRecord(timestamp=time.time(), operation="overflow", model="gpt-4"))

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(tracker._records) <= 100
