"""Circuit Breaker for LLM API — 2026 优化

防止对故障 LLM 端点的级联调用。三态状态机：

CLOSED → (失败率 > 阈值) → OPEN
OPEN → (冷却时间到) → HALF_OPEN
HALF_OPEN → (成功) → CLOSED | (失败) → OPEN

配置：
- 故障阈值：30s 内 3 次失败
- 冷却时间：15s（API 恢复后快速自愈）
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from enum import Enum

log = logging.getLogger("circuit_breaker")


class CircuitState(Enum):
    CLOSED = "closed"       # 正常通行
    OPEN = "open"           # 熔断，拒绝请求
    HALF_OPEN = "half_open"  # 试探性恢复


class CircuitBreaker:
    """针对 LLM API 的轻量熔断器。"""

    __slots__ = (
        "_failure_window_s", "_failure_threshold",
        "_cooldown_s", "_state", "_failure_times",
        "_last_failure_at", "_opened_at", "_lock",
        "_total_requests", "_total_failures",
        "_rejected_requests",
    )

    def __init__(
        self,
        failure_window_s: float = 30.0,
        failure_threshold: int = 3,
        cooldown_s: float = 15.0,
    ):
        self._failure_window_s = failure_window_s
        self._failure_threshold = failure_threshold
        self._cooldown_s = cooldown_s
        self._state = CircuitState.CLOSED
        self._failure_times: deque[float] = deque()
        self._last_failure_at = 0.0
        self._opened_at = 0.0
        self._lock = asyncio.Lock()
        # 统计
        self._total_requests = 0
        self._total_failures = 0
        self._rejected_requests = 0

    async def allow(self) -> bool:
        """检查是否允许请求通过。"""
        async with self._lock:
            self._total_requests += 1

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                if time.time() - self._opened_at > self._cooldown_s:
                    self._state = CircuitState.HALF_OPEN
                    log.info("Circuit breaker: OPEN → HALF_OPEN (cooldown elapsed)")
                    return True
                self._rejected_requests += 1
                return False

            # HALF_OPEN: 允许通过（试探）
            return True

    async def success(self) -> None:
        """记录成功。"""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_times.clear()
                log.info("Circuit breaker: HALF_OPEN → CLOSED (probe success)")

    async def failure(self) -> None:
        """记录失败。"""
        now = time.time()
        async with self._lock:
            self._total_failures += 1
            self._last_failure_at = now
            self._failure_times.append(now)

            # 清除窗口外的旧失败
            cutoff = now - self._failure_window_s
            while self._failure_times and self._failure_times[0] < cutoff:
                self._failure_times.popleft()

            recent_failures = len(self._failure_times)

            if self._state == CircuitState.HALF_OPEN:
                # 试探失败 → 重新打开
                self._state = CircuitState.OPEN
                self._opened_at = now
                log.warning(
                    "Circuit breaker: HALF_OPEN → OPEN (%d failures in %ds)",
                    recent_failures, self._failure_window_s,
                )
            elif self._state == CircuitState.CLOSED and recent_failures >= self._failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = now
                log.warning(
                    "Circuit breaker: CLOSED → OPEN (%d failures in %ds)",
                    recent_failures, self._failure_window_s,
                )

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def stats(self) -> dict:
        return {
            "state": self._state.value,
            "total_requests": self._total_requests,
            "total_failures": self._total_failures,
            "rejected": self._rejected_requests,
            "recent_failures": len(self._failure_times),
            "last_failure_age_s": (
                time.time() - self._last_failure_at if self._last_failure_at else None
            ),
        }


class NoOpCircuitBreaker:
    """禁用熔断时的空操作熔断器，始终允许所有请求。"""
    state = CircuitState.CLOSED

    async def allow(self) -> bool: return True
    async def success(self) -> None: pass
    async def failure(self) -> None: pass
    @property
    def stats(self) -> dict[str, object]:
        return {"state": "disabled", "total_requests": 0, "total_failures": 0, "rejected": 0, "recent_failures": 0, "last_failure_age_s": None}


# 全局单例
_cb: CircuitBreaker | NoOpCircuitBreaker | None = None


def get_circuit_breaker() -> CircuitBreaker | NoOpCircuitBreaker:
    global _cb
    if _cb is None:
        from .config import settings
        if not settings.llm_circuit_breaker:
            _cb = NoOpCircuitBreaker()
        else:
            _cb = CircuitBreaker(
                failure_window_s=settings.llm_cb_failure_window_s,
                failure_threshold=settings.llm_cb_failure_threshold,
                cooldown_s=settings.llm_cb_cooldown_s,
            )
    return _cb
