from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 相对于项目根目录（config.py 在 backend/ 下，.env 在项目根）
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH) if _ENV_PATH.is_file() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM 基础配置 ──
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    # ── 连接池（2026 优化）──
    llm_pool_max_connections: int = 100       # HTTP 连接池最大连接数
    llm_pool_max_keepalive: int = 20          # 最大保活连接数
    llm_pool_connect_timeout: float = 10.0    # 连接建立超时（秒）
    llm_pool_read_timeout: float = 120.0      # 读取超时（秒），替代已废弃的 llm_timeout_s

    # ── 熔断器（2026 优化）──
    llm_circuit_breaker: bool = True           # 是否启用熔断器
    llm_cb_failure_window_s: float = 30.0      # 故障时间窗口（秒）
    llm_cb_failure_threshold: int = 3          # 窗口内失败次数阈值
    llm_cb_cooldown_s: float = 15.0            # 熔断冷却时间（秒）

    # ── 响应缓存（2026 优化）──
    llm_cache_enabled: bool = True             # 是否启用 LLM 响应缓存
    llm_cache_size: int = 128                  # 缓存条目上限
    llm_cache_ttl_s: float = 300.0             # 缓存 TTL（秒）

    # ── Prompt Cache（OpenAI 兼容）──
    llm_enable_prompt_cache: bool = False      # 是否启用 prompt_cache（cache_control 标记）
                                     # 非 OpenAI API 不支持时设为 False

    # ── 智能重试（2026 优化）──
    llm_max_retries: int = 3                   # 最大重试次数
    llm_retry_base_delay_s: float = 1.5        # 重试基础延迟（秒）
    llm_max_concurrency: int = 8               # 最大并发 LLM 请求数

    # ── 自动存档 ──
    auto_save_interval_s: float = 300.0       # 自动存档间隔（秒），默认 5 分钟

    # ── CORS ──
    cors_allow_origins: str = "*"

    # ── 测试路由 ──
    enable_test_routes: bool = False

    # ── 安全与控制 ──
    shutdown_secret: str = ""

    @field_validator('llm_api_key')
    def warn_empty_key(cls, v):
        if not v:
            import logging
            logging.getLogger('config').warning('LLM_API_KEY 未配置，NPC 对话功能将不可用')
        return v


settings = Settings()

if not settings.llm_api_key:
    print("WARNING: LLM_API_KEY 未配置，NPC 对话功能将不可用")
