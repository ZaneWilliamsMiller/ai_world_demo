from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_base_url: str = "http://127.0.0.1:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen2.5:7b"
    llm_timeout_s: float = 120.0

    # 逗号分隔的前端来源；留空或 * 表示任意来源（浏览器下不可与 Cookie 凭证同时使用，见 app CORS）
    cors_allow_origins: str = "*"


settings = Settings()
