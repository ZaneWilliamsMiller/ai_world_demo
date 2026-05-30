from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.llm.client import (
    LLMClientManager,
    _is_retryable_error,
    _parse_stream_line,
    cached_system,
    parse_finale,
    uncached,
)


class TestIsRetryableError(unittest.TestCase):

    def test_connect_error(self):
        self.assertTrue(_is_retryable_error(httpx.ConnectError("conn")))

    def test_network_error(self):
        self.assertTrue(_is_retryable_error(httpx.NetworkError("net")))

    def test_timeout_exception(self):
        self.assertTrue(_is_retryable_error(httpx.TimeoutException("timeout")))

    def test_remote_protocol_error(self):
        self.assertTrue(_is_retryable_error(httpx.RemoteProtocolError("proto")))

    def test_value_error(self):
        self.assertFalse(_is_retryable_error(ValueError("val")))

    def test_json_decode_error(self):
        self.assertFalse(_is_retryable_error(json.JSONDecodeError("json", "", 0)))

    def test_plain_exception(self):
        self.assertFalse(_is_retryable_error(Exception("plain")))


class TestParseStreamLine(unittest.TestCase):

    def test_empty_line(self):
        self.assertIsNone(_parse_stream_line(""))

    def test_comment_line(self):
        self.assertIsNone(_parse_stream_line(": this is a comment"))

    def test_done_signal(self):
        self.assertIsNone(_parse_stream_line("data: [DONE]"))

    def test_valid_json_line(self):
        line = 'data: {"choices":[{"delta":{"content":"hello"}}]}'
        self.assertEqual(_parse_stream_line(line), "hello")

    def test_invalid_json_line(self):
        self.assertIsNone(_parse_stream_line("data: {invalid}"))

    def test_no_choices_line(self):
        self.assertIsNone(_parse_stream_line('data: {"choices":[]}'))

    def test_non_data_line(self):
        self.assertIsNone(_parse_stream_line("event: message_start"))


class TestParseFinale(unittest.TestCase):

    def test_no_ending_title(self):
        text = "This is a normal ending."
        body, title = parse_finale(text)
        self.assertEqual(body, text.strip())
        self.assertIsNone(title)

    def test_with_ending_title(self):
        text = "The story ends here.\nENDING_TITLE: A New Dawn"
        body, title = parse_finale(text)
        self.assertEqual(body, "The story ends here.")
        self.assertEqual(title, "A New Dawn")

    def test_title_truncated_over_32(self):
        long_title = "A" * 50
        text = f"Body text\nENDING_TITLE: {long_title}"
        body, title = parse_finale(text)
        self.assertEqual(len(title), 32)
        self.assertEqual(title, "A" * 32)

    def test_title_strip_brackets(self):
        text = 'Body text\nENDING_TITLE: 《My Title》'
        body, title = parse_finale(text)
        self.assertEqual(title, "My Title")

    def test_empty_title(self):
        text = "Body text\nENDING_TITLE: "
        body, title = parse_finale(text)
        self.assertIsNone(title)

    def test_title_strip_quotes(self):
        text = "Body text\nENDING_TITLE: \"My Title\""
        body, title = parse_finale(text)
        self.assertEqual(title, "My Title")

    def test_title_strip_single_quotes(self):
        text = "Body text\nENDING_TITLE: 'My Title'"
        body, title = parse_finale(text)
        self.assertEqual(title, "My Title")


class TestCachedSystem(unittest.TestCase):

    @patch("backend.llm.client.settings")
    def test_cached_system_enabled(self, mock_settings):
        mock_settings.llm_enable_prompt_cache = True
        result = cached_system("hello")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "text")
        self.assertEqual(result[0]["text"], "hello")
        self.assertEqual(result[0]["cache_control"], {"type": "ephemeral"})

    @patch("backend.llm.client.settings")
    def test_cached_system_disabled(self, mock_settings):
        mock_settings.llm_enable_prompt_cache = False
        result = cached_system("hello")
        self.assertIsInstance(result, str)
        self.assertEqual(result, "hello")


class TestUncached(unittest.TestCase):

    @patch("backend.llm.client.settings")
    def test_uncached_enabled(self, mock_settings):
        mock_settings.llm_enable_prompt_cache = True
        result = uncached("hello")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "text")
        self.assertEqual(result[0]["text"], "hello")
        self.assertNotIn("cache_control", result[0])

    @patch("backend.llm.client.settings")
    def test_uncached_disabled(self, mock_settings):
        mock_settings.llm_enable_prompt_cache = False
        result = uncached("hello")
        self.assertIsInstance(result, str)
        self.assertEqual(result, "hello")


class TestLLMClientManager(unittest.TestCase):

    def setUp(self):
        LLMClientManager._instance = None

    def tearDown(self):
        LLMClientManager._instance = None

    def test_get_instance_singleton(self):
        async def _test():
            inst1 = await LLMClientManager.get_instance()
            inst2 = await LLMClientManager.get_instance()
            self.assertIs(inst1, inst2)
        asyncio.run(_test())

    @patch("backend.llm.client.settings")
    def test_get_semaphore_lazy_init(self, mock_settings):
        mock_settings.llm_max_concurrency = 5
        manager = LLMClientManager()
        self.assertIsNone(manager._semaphore)
        sem = manager.get_semaphore()
        self.assertIsInstance(sem, asyncio.Semaphore)
        sem2 = manager.get_semaphore()
        self.assertIs(sem, sem2)

    def test_close_client(self):
        async def _test():
            manager = LLMClientManager()
            mock_client = AsyncMock()
            mock_client.is_closed = False
            mock_client.aclose = AsyncMock()
            manager._client = mock_client

            mock_custom = AsyncMock()
            mock_custom.is_closed = False
            mock_custom.aclose = AsyncMock()
            manager._custom_clients = {"k1": mock_custom}

            await manager.close_client()

            mock_client.aclose.assert_awaited_once()
            mock_custom.aclose.assert_awaited_once()
            self.assertIsNone(manager._client)
            self.assertEqual(len(manager._custom_clients), 0)

        asyncio.run(_test())

    def test_close_client_already_closed(self):
        async def _test():
            manager = LLMClientManager()
            mock_client = AsyncMock()
            mock_client.is_closed = True
            manager._client = mock_client

            await manager.close_client()

            mock_client.aclose.assert_not_awaited()

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
