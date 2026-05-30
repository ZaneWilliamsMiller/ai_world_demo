from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.llm.prompt_compress import (
    COMPRESS_THRESHOLD,
    COMPRESS_WINDOW,
    KEEP_RECENT,
    _llm_summarize,
    compress_conversation_history,
)


def _make_hist(n: int) -> list[dict]:
    return [{"user": f"msg{i}", "assistant": f"reply{i}"} for i in range(n)]


class TestCompressBelowThreshold:

    async def _run(self, hist, npc_name=""):
        return await compress_conversation_history(hist, npc_name)

    def test_returns_unchanged_when_below_threshold(self):
        hist = _make_hist(10)
        result = asyncio.run(self._run(hist))
        assert result is hist

    def test_returns_unchanged_at_exact_threshold(self):
        hist = _make_hist(COMPRESS_THRESHOLD)
        result = asyncio.run(self._run(hist))
        assert result is hist


class TestCompressAboveThreshold:

    @patch("backend.llm.prompt_compress._llm_summarize", new_callable=AsyncMock, return_value="摘要内容")
    def test_keeps_recent_entries(self, _mock_summ):
        hist = _make_hist(20)
        result = asyncio.run(compress_conversation_history(hist, "掌柜"))
        recent_users = [t.get("user", "") for t in result[-KEEP_RECENT:]]
        expected = [f"msg{i}" for i in range(14, 20)]
        assert recent_users == expected

    @patch("backend.llm.prompt_compress._llm_summarize", new_callable=AsyncMock, return_value="摘要内容")
    def test_old_span_marker(self, _mock_summ):
        hist = _make_hist(25)
        result = asyncio.run(compress_conversation_history(hist, "掌柜"))
        first_user = result[0].get("user", "")
        assert "从略" in first_user

    @patch("backend.llm.prompt_compress._llm_summarize", new_callable=AsyncMock, return_value="摘要内容")
    def test_compress_window_size(self, _mock_summ):
        hist = _make_hist(25)
        asyncio.run(compress_conversation_history(hist, "掌柜"))
        call_args = _mock_summ.call_args[0][0]
        line_count = call_args.count("玩家:")
        assert line_count <= COMPRESS_WINDOW

    @patch("backend.llm.prompt_compress._llm_summarize", new_callable=AsyncMock, side_effect=RuntimeError("LLM down"))
    def test_llm_failure_returns_original(self, _mock_summ):
        hist = _make_hist(20)
        result = asyncio.run(compress_conversation_history(hist, "掌柜"))
        assert result is hist


class TestLlmSummarize:

    @patch("backend.llm.prompt_compress.chat_completion", new_callable=AsyncMock, return_value="  这是摘要  ")
    def test_strips_surrounding_quotes(self, _mock_cc):
        result = asyncio.run(_llm_summarize("对话内容", "掌柜"))
        assert result.strip() == result

    @patch("backend.llm.prompt_compress.chat_completion", new_callable=AsyncMock, return_value='"带引号的摘要"')
    def test_strips_double_quotes(self, _mock_cc):
        result = asyncio.run(_llm_summarize("对话内容", "掌柜"))
        assert result == "带引号的摘要"

    @patch("backend.llm.prompt_compress.chat_completion", new_callable=AsyncMock, return_value="x" * 300)
    def test_truncates_long_summary(self, _mock_cc):
        result = asyncio.run(_llm_summarize("对话内容", "掌柜"))
        assert len(result) <= 250
