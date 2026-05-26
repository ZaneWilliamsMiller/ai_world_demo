from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── LLM 基础配置 ──
    llm_base_url: str = "http://127.0.0.1:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen2.5:7b"
    llm_timeout_s: float = 120.0

    # ── 连接池（2026 优化）──
    llm_pool_max_connections: int = 100       # HTTP 连接池最大连接数
    llm_pool_max_keepalive: int = 20          # 最大保活连接数
    llm_pool_connect_timeout: float = 10.0    # 连接建立超时（秒）
    llm_pool_read_timeout: float = 120.0      # 读取超时（秒）

    # ── 熔断器（2026 优化）──
    llm_circuit_breaker: bool = True           # 是否启用熔断器
    llm_cb_failure_window_s: float = 30.0      # 故障时间窗口（秒）
    llm_cb_failure_threshold: int = 3          # 窗口内失败次数阈值
    llm_cb_cooldown_s: float = 15.0            # 熔断冷却时间（秒）

    # ── 响应缓存（2026 优化）──
    llm_cache_enabled: bool = True             # 是否启用 LLM 响应缓存
    llm_cache_size: int = 128                  # 缓存条目上限
    llm_cache_ttl_s: float = 300.0             # 缓存 TTL（秒）

    # ── 智能重试（2026 优化）──
    llm_max_retries: int = 3                   # 最大重试次数
    llm_retry_base_delay_s: float = 1.5        # 重试基础延迟（秒）
    llm_max_concurrency: int = 8               # 最大并发 LLM 请求数

    # ── CORS ──
    cors_allow_origins: str = "*"


settings = Settings()
