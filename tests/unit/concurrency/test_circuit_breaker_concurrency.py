from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from backend.llm.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreakerConcurrency:

    async def test_concurrent_record_success(self):
        cb = CircuitBreaker(failure_threshold=10, failure_window_s=30.0, cooldown_s=5.0)
        n = 100

        await asyncio.gather(*[cb.success() for _ in range(n)])

        assert cb.state == CircuitState.CLOSED

    async def test_concurrent_record_failure_below_threshold(self):
        cb = CircuitBreaker(failure_threshold=200, failure_window_s=30.0, cooldown_s=5.0)
        n = 50

        await asyncio.gather(*[cb.failure() for _ in range(n)])

        assert cb._total_failures == n

    async def test_concurrent_failure_triggers_open(self):
        cb = CircuitBreaker(failure_threshold=5, failure_window_s=30.0, cooldown_s=5.0)
        n = 10

        await asyncio.gather(*[cb.failure() for _ in range(n)])

        assert cb._total_failures == n
        assert cb.state in (CircuitState.OPEN, CircuitState.HALF_OPEN)

    async def test_concurrent_allow_in_closed(self):
        cb = CircuitBreaker(failure_threshold=10, failure_window_s=30.0, cooldown_s=5.0)
        n = 100

        results = await asyncio.gather(*[cb.allow() for _ in range(n)])

        assert all(results)
        assert cb._total_requests == n

    async def test_concurrent_allow_in_open_blocks(self):
        cb = CircuitBreaker(failure_threshold=3, failure_window_s=30.0, cooldown_s=60.0)
        cb._state = CircuitState.OPEN
        cb._opened_at = time.time()
        n = 50

        results = await asyncio.gather(*[cb.allow() for _ in range(n)])

        assert cb._rejected_requests > 0
        assert not any(results)

    async def test_state_transition_closed_to_open(self):
        cb = CircuitBreaker(failure_threshold=3, failure_window_s=30.0, cooldown_s=5.0)

        for _ in range(3):
            await cb.failure()

        assert cb.state == CircuitState.OPEN

    async def test_state_transition_open_to_half_open_after_cooldown(self):
        cb = CircuitBreaker(failure_threshold=3, failure_window_s=30.0, cooldown_s=0.0)

        for _ in range(3):
            await cb.failure()
        assert cb.state == CircuitState.OPEN

        cb._opened_at = time.time() - 1.0
        allowed = await cb.allow()
        assert allowed is True
        assert cb.state == CircuitState.HALF_OPEN

    async def test_state_transition_half_open_to_closed_on_success(self):
        cb = CircuitBreaker(failure_threshold=3, failure_window_s=30.0, cooldown_s=5.0)
        cb._state = CircuitState.HALF_OPEN

        await cb.success()
        assert cb.state == CircuitState.CLOSED

    async def test_state_transition_half_open_to_open_on_failure(self):
        cb = CircuitBreaker(failure_threshold=3, failure_window_s=30.0, cooldown_s=5.0)
        cb._state = CircuitState.HALF_OPEN

        await cb.failure()
        assert cb.state == CircuitState.OPEN

    async def test_concurrent_mixed_success_failure(self):
        cb = CircuitBreaker(failure_threshold=100, failure_window_s=30.0, cooldown_s=5.0)
        n = 50

        coros = []
        for i in range(n):
            if i % 2 == 0:
                coros.append(cb.success())
            else:
                coros.append(cb.failure())

        await asyncio.gather(*coros)

        assert cb._total_failures == n // 2
        assert cb.state == CircuitState.CLOSED

    async def test_failure_count_never_exceeds_threshold_without_state_change(self):
        cb = CircuitBreaker(failure_threshold=3, failure_window_s=30.0, cooldown_s=5.0)
        n = 20

        await asyncio.gather(*[cb.failure() for _ in range(n)])

        assert cb.state != CircuitState.CLOSED
        assert cb._total_failures == n

    async def test_full_cycle_concurrent(self):
        cb = CircuitBreaker(failure_threshold=3, failure_window_s=30.0, cooldown_s=0.01)

        for _ in range(3):
            await cb.failure()
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.02)
        allowed = await cb.allow()
        assert allowed is True

        await cb.success()
        assert cb.state == CircuitState.CLOSED
