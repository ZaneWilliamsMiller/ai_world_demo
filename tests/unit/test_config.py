import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestSettings(unittest.TestCase):
    def _make_settings(self, **kwargs):
        from pydantic_settings import BaseSettings, SettingsConfigDict

        class _TestSettings(BaseSettings):
            model_config = SettingsConfigDict(extra="ignore")

            llm_base_url: str = ""
            llm_api_key: str = ""
            llm_model: str = ""
            llm_pool_max_connections: int = 100
            llm_pool_max_keepalive: int = 20
            llm_pool_connect_timeout: float = 10.0
            llm_pool_read_timeout: float = 120.0
            llm_circuit_breaker: bool = True
            llm_cb_failure_window_s: float = 30.0
            llm_cb_failure_threshold: int = 3
            llm_cb_cooldown_s: float = 15.0
            llm_cache_enabled: bool = True
            llm_cache_size: int = 128
            llm_cache_ttl_s: float = 300.0
            llm_enable_prompt_cache: bool = False
            llm_max_retries: int = 3
            llm_retry_base_delay_s: float = 1.5
            llm_max_concurrency: int = 8
            auto_save_interval_s: float = 300.0
            cors_allow_origins: str = "*"
            enable_test_routes: bool = False
            shutdown_secret: str = ""

        return _TestSettings(**kwargs)

    def test_llm_base_url_type(self):
        s = self._make_settings()
        self.assertIsInstance(s.llm_base_url, str)

    def test_llm_pool_max_connections_type(self):
        s = self._make_settings()
        self.assertIsInstance(s.llm_pool_max_connections, int)

    def test_enable_test_routes_default_false(self):
        s = self._make_settings()
        self.assertFalse(s.enable_test_routes)

    def test_shutdown_secret_default_empty(self):
        s = self._make_settings()
        self.assertEqual(s.shutdown_secret, "")

    def test_llm_cache_enabled_default_true(self):
        s = self._make_settings()
        self.assertTrue(s.llm_cache_enabled)

    def test_llm_max_retries_default_3(self):
        s = self._make_settings()
        self.assertEqual(s.llm_max_retries, 3)


if __name__ == "__main__":
    unittest.main()
