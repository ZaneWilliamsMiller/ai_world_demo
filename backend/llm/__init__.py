"""LLM 基础设施 — 客户端、缓存、熔断器、参数。"""
from backend.llm.cache import (  # noqa: F401
    CacheEntry,
    LlmResponseCache,
    get_llm_cache,
)
from backend.llm.circuit_breaker import (  # noqa: F401
    CircuitBreaker,
    CircuitState,
    NoOpCircuitBreaker,
    get_circuit_breaker,
)
from backend.llm.client import (  # noqa: F401
    LLMClientManager,
    _close_client,
    _close_client_sync,
    _get_client,
    _get_semaphore,
    cached_system,
    chat_completion,
    parse_finale,
    parse_npc_reply_json,
    stream_chat_completion,
    uncached,
)
from backend.llm.params import (  # noqa: F401
    COMPRESS_MAX_TOKENS,
    COMPRESS_TEMPERATURE,
    CROSS_REFLECT_MAX_TOKENS,
    CROSS_REFLECT_TEMPERATURE,
    ENCOUNTER_MAX_TOKENS,
    ENCOUNTER_TEMPERATURE,
    FINALE_MAX_TOKENS,
    FINALE_TEMPERATURE,
    PLAN_MAX_TOKENS,
    PLAN_TEMPERATURE,
    REFLECT_MAX_TOKENS,
    REFLECT_TEMPERATURE,
    TALK_FULL_MAX_TOKENS,
    TALK_LIGHT_MAX_TOKENS,
    TALK_TEMPERATURE,
)
