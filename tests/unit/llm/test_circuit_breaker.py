from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import time
from unittest.mock import MagicMock, patch

import pytest
from backend.llm.circuit_breaker import CircuitBreaker, CircuitState, NoOpCircuitBreaker, get_circuit_breaker


@pytest.fixture(autouse=True)
def _reset_global_cb():
    import backend.llm.circuit_breaker as mod
    mod._cb = None
    yield
    mod._cb = None


class TestCircuitBreakerInit:
    def test_default_parameters(self):
        cb = CircuitBreaker()
        assert cb._failure_window_s == 30.0
        assert cb._failure_threshold == 3
        assert cb._cooldown_s == 15.0
        assert cb._state == CircuitState.CLOSED
        assert len(cb._failure_times) == 0
        assert cb._last_failure_at == 0.0
        assert cb._opened_at == 0.0
        assert cb._total_requests == 0
        assert cb._total_failures == 0
        assert cb._rejected_requests == 0

    def test_custom_parameters(self):
        cb = CircuitBreaker(failure_window_s=60.0, failure_threshold=5, cooldown_s=30.0)
        assert cb._failure_window_s == 60.0
        assert cb._failure_threshold == 5
        assert cb._cooldown_s == 30.0


class TestCircuitBreakerAllow:
    async def test_closed_allows(self):
        cb = CircuitBreaker()
        assert await cb.allow() is True

    async def test_closed_increments_total_requests(self):
        cb = CircuitBreaker()
        await cb.allow()
        await cb.allow()
        assert cb._total_requests == 2

    async def test_open_denies_within_cooldown(self):
        cb = CircuitBreaker()
        cb._state = CircuitState.OPEN
        cb._opened_at = time.time()
        assert await cb.allow() is False

    async def test_open_increments_rejected(self):
        cb = CircuitBreaker()
        cb._state = CircuitState.OPEN
        cb._opened_at = time.time()
        await cb.allow()
        assert cb._rejected_requests == 1

    async def test_open_transitions_to_half_open_after_cooldown(self):
        cb = CircuitBreaker(cooldown_s=10.0)
        cb._state = CircuitState.OPEN
        cb._opened_at = time.time() - 11.0
        result = await cb.allow()
        assert result is True
        assert cb._state == CircuitState.HALF_OPEN

    async def test_open_does_not_transition_before_cooldown(self):
        cb = CircuitBreaker(cooldown_s=10.0)
        cb._state = CircuitState.OPEN
        cb._opened_at = time.time() - 5.0
        result = await cb.allow()
        assert result is False
        assert cb._state == CircuitState.OPEN

    async def test_half_open_allows(self):
        cb = CircuitBreaker()
        cb._state = CircuitState.HALF_OPEN
        assert await cb.allow() is True

    async def test_half_open_increments_total_requests(self):
        cb = CircuitBreaker()
        cb._state = CircuitState.HALF_OPEN
        await cb.allow()
        assert cb._total_requests == 1


class TestCircuitBreakerSuccess:
    async def test_half_open_transitions_to_closed(self):
        cb = CircuitBreaker()
        cb._state = CircuitState.HALF_OPEN
        cb._failure_times.append(time.time())
        await cb.success()
        assert cb._state == CircuitState.CLOSED

    async def test_half_open_clears_failure_times(self):
        cb = CircuitBreaker()
        cb._state = CircuitState.HALF_OPEN
        cb._failure_times.append(100.0)
        cb._failure_times.append(200.0)
        await cb.success()
        assert len(cb._failure_times) == 0

    async def test_closed_stays_closed_on_success(self):
        cb = CircuitBreaker()
        await cb.success()
        assert cb._state == CircuitState.CLOSED

    async def test_open_stays_open_on_success(self):
        cb = CircuitBreaker()
        cb._state = CircuitState.OPEN
        cb._opened_at = time.time()
        await cb.success()
        assert cb._state == CircuitState.OPEN


class TestCircuitBreakerFailure:
    async def test_increments_total_failures(self):
        cb = CircuitBreaker()
        await cb.failure()
        assert cb._total_failures == 1
        await cb.failure()
        assert cb._total_failures == 2

    async def test_records_failure_time(self):
        cb = CircuitBreaker()
        now = time.time()
        await cb.failure()
        assert len(cb._failure_times) == 1
        assert abs(cb._failure_times[0] - now) < 1.0

    async def test_updates_last_failure_at(self):
        cb = CircuitBreaker()
        now = time.time()
        await cb.failure()
        assert abs(cb._last_failure_at - now) < 1.0

    async def test_closed_to_open_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, failure_window_s=30.0)
        now = time.time()
        for _ in range(3):
            cb._failure_times.append(now)
        cb._failure_times.append(now)
        await cb.failure()
        assert cb._state == CircuitState.OPEN

    async def test_closed_stays_closed_below_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, failure_window_s=30.0)
        await cb.failure()
        await cb.failure()
        assert cb._state == CircuitState.CLOSED

    async def test_half_open_to_open_on_failure(self):
        cb = CircuitBreaker()
        cb._state = CircuitState.HALF_OPEN
        await cb.failure()
        assert cb._state == CircuitState.OPEN

    async def test_half_open_sets_opened_at(self):
        cb = CircuitBreaker()
        cb._state = CircuitState.HALF_OPEN
        now = time.time()
        await cb.failure()
        assert abs(cb._opened_at - now) < 1.0

    async def test_sliding_window_removes_old_failures(self):
        cb = CircuitBreaker(failure_window_s=10.0, failure_threshold=3)
        now = time.time()
        cb._failure_times.append(now - 20.0)
        cb._failure_times.append(now - 15.0)
        await cb.failure()
        assert len(cb._failure_times) == 1

    async def test_sliding_window_prevents_false_open(self):
        cb = CircuitBreaker(failure_window_s=10.0, failure_threshold=3)
        now = time.time()
        cb._failure_times.append(now - 20.0)
        cb._failure_times.append(now - 15.0)
        await cb.failure()
        assert cb._state == CircuitState.CLOSED

    async def test_open_stays_open_on_failure(self):
        cb = CircuitBreaker()
        cb._state = CircuitState.OPEN
        cb._opened_at = time.time()
        await cb.failure()
        assert cb._state == CircuitState.OPEN


class TestCircuitBreakerState:
    def test_returns_current_state(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        cb._state = CircuitState.OPEN
        assert cb.state == CircuitState.OPEN
        cb._state = CircuitState.HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN


class TestCircuitBreakerStats:
    def test_initial_stats(self):
        cb = CircuitBreaker()
        s = cb.stats
        assert s["state"] == "closed"
        assert s["total_requests"] == 0
        assert s["total_failures"] == 0
        assert s["rejected"] == 0
        assert s["recent_failures"] == 0
        assert s["last_failure_age_s"] is None

    def test_stats_after_requests(self):
        cb = CircuitBreaker()
        cb._total_requests = 10
        cb._total_failures = 3
        cb._rejected_requests = 2
        cb._failure_times.append(time.time())
        s = cb.stats
        assert s["total_requests"] == 10
        assert s["total_failures"] == 3
        assert s["rejected"] == 2
        assert s["recent_failures"] == 1

    def test_last_failure_age_s(self):
        cb = CircuitBreaker()
        cb._last_failure_at = time.time() - 5.0
        s = cb.stats
        assert s["last_failure_age_s"] is not None
        assert abs(s["last_failure_age_s"] - 5.0) < 1.0

    def test_stats_reflects_open_state(self):
        cb = CircuitBreaker()
        cb._state = CircuitState.OPEN
        assert cb.stats["state"] == "open"

    def test_stats_reflects_half_open_state(self):
        cb = CircuitBreaker()
        cb._state = CircuitState.HALF_OPEN
        assert cb.stats["state"] == "half_open"


class TestCircuitBreakerTimeBasedTransitions:
    async def test_full_cycle_closed_open_half_open_closed(self):
        cb = CircuitBreaker(failure_threshold=2, failure_window_s=30.0, cooldown_s=5.0)
        assert cb.state == CircuitState.CLOSED
        assert await cb.allow() is True
        now = time.time()
        cb._failure_times.append(now)
        cb._failure_times.append(now)
        await cb.failure()
        assert cb.state == CircuitState.OPEN
        assert await cb.allow() is False
        cb._opened_at = now - 6.0
        assert await cb.allow() is True
        assert cb.state == CircuitState.HALF_OPEN
        await cb.success()
        assert cb.state == CircuitState.CLOSED

    async def test_half_open_back_to_open_on_failure(self):
        cb = CircuitBreaker(failure_threshold=2, cooldown_s=5.0)
        cb._state = CircuitState.HALF_OPEN
        await cb.failure()
        assert cb.state == CircuitState.OPEN

    @patch("backend.llm.circuit_breaker.time.time")
    async def test_cooldown_boundary(self, mock_time):
        mock_time.return_value = 100.0
        cb = CircuitBreaker(cooldown_s=10.0)
        cb._state = CircuitState.OPEN
        cb._opened_at = 90.0
        mock_time.return_value = 99.9
        assert await cb.allow() is False
        mock_time.return_value = 100.1
        assert await cb.allow() is True
        assert cb.state == CircuitState.HALF_OPEN

    @patch("backend.llm.circuit_breaker.time.time")
    async def test_failure_window_sliding(self, mock_time):
        mock_time.return_value = 0.0
        cb = CircuitBreaker(failure_window_s=10.0, failure_threshold=3)
        mock_time.return_value = 0.0
        await cb.failure()
        mock_time.return_value = 5.0
        await cb.failure()
        assert cb.state == CircuitState.CLOSED
        mock_time.return_value = 11.0
        await cb.failure()
        assert cb.state == CircuitState.CLOSED
        mock_time.return_value = 12.0
        await cb.failure()
        assert cb.state == CircuitState.OPEN


class TestNoOpCircuitBreaker:
    async def test_allow_always_true(self):
        cb = NoOpCircuitBreaker()
        assert await cb.allow() is True

    async def test_success_is_noop(self):
        cb = NoOpCircuitBreaker()
        await cb.success()

    async def test_failure_is_noop(self):
        cb = NoOpCircuitBreaker()
        await cb.failure()

    def test_state_is_closed(self):
        cb = NoOpCircuitBreaker()
        assert cb.state == CircuitState.CLOSED

    def test_stats_returns_disabled(self):
        cb = NoOpCircuitBreaker()
        s = cb.stats
        assert s["state"] == "disabled"
        assert s["total_requests"] == 0
        assert s["total_failures"] == 0
        assert s["rejected"] == 0
        assert s["recent_failures"] == 0
        assert s["last_failure_age_s"] is None


class TestGetCircuitBreaker:
    def test_returns_noop_when_disabled(self):
        mock_settings = MagicMock()
        mock_settings.llm_circuit_breaker = False
        import backend.llm.circuit_breaker as mod
        mod._cb = None
        with patch("backend.config.settings", mock_settings):
            result = get_circuit_breaker()
            assert isinstance(result, NoOpCircuitBreaker)

    def test_singleton_noop(self):
        mock_settings = MagicMock()
        mock_settings.llm_circuit_breaker = False
        import backend.llm.circuit_breaker as mod
        mod._cb = None
        with patch("backend.config.settings", mock_settings):
            result = get_circuit_breaker()
            result2 = get_circuit_breaker()
            assert result2 is result

    def test_singleton_circuit_breaker(self):
        mock_settings = MagicMock()
        mock_settings.llm_circuit_breaker = True
        mock_settings.llm_cb_failure_window_s = 60.0
        mock_settings.llm_cb_failure_threshold = 5
        mock_settings.llm_cb_cooldown_s = 30.0
        import backend.llm.circuit_breaker as mod
        mod._cb = None
        with patch("backend.config.settings", mock_settings):
            result = get_circuit_breaker()
            assert isinstance(result, CircuitBreaker)
            assert result._failure_window_s == 60.0
            assert result._failure_threshold == 5
            assert result._cooldown_s == 30.0
            result2 = get_circuit_breaker()
            assert result2 is result

    def test_returns_existing_singleton(self):
        import backend.llm.circuit_breaker as mod
        existing = CircuitBreaker()
        mod._cb = existing
        assert get_circuit_breaker() is existing
