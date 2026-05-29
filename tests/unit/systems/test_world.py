from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.agents.brain import (
    _deduplicate_observations,
    import_seeds,
    record_observation,
)
from backend.llm.client import (
    _build_request_body,
    _is_retryable_error,
    cached_system,
    parse_finale,
    parse_npc_reply_json,
    uncached,
)
from backend.llm.prompt_compress import compress_conversation_history
from backend.memory import AgentMind, Memory, make_memory
from backend.models.llm_schema import NpcResponseSchema


class TestLlmClient:

    def test_build_request_body_basic(self):
        msgs = [{"role": "user", "content": "hi"}]
        body = _build_request_body(msgs, temperature=0.7, max_tokens=512, model="gpt-test")
        assert body["model"] == "gpt-test"
        assert body["messages"] == msgs
        assert body["temperature"] == 0.7
        assert body["max_tokens"] == 512
        assert "response_format" not in body
        assert "stream" not in body

    def test_build_request_body_with_response_format(self):
        msgs = [{"role": "user", "content": "hi"}]
        rf = {"type": "json_object"}
        body = _build_request_body(msgs, temperature=0.5, max_tokens=256, model="m1", response_format=rf)
        assert body["response_format"] == rf

    def test_build_request_body_with_stream(self):
        msgs = [{"role": "user", "content": "hi"}]
        body = _build_request_body(msgs, temperature=0.5, max_tokens=256, model="m1", stream=True)
        assert body["stream"] is True

    def test_build_request_body_no_extra_keys_when_optional_none(self):
        msgs = [{"role": "user", "content": "hi"}]
        body = _build_request_body(msgs, temperature=0.5, max_tokens=256, model="m1", response_format=None, stream=False)
        assert "response_format" not in body
        assert "stream" not in body

    def test_is_retryable_error_connect(self):
        assert _is_retryable_error(httpx.ConnectError("conn")) is True

    def test_is_retryable_error_network(self):
        assert _is_retryable_error(httpx.NetworkError("net")) is True

    def test_is_retryable_error_timeout(self):
        assert _is_retryable_error(httpx.TimeoutException("timeout")) is True

    def test_is_retryable_error_remote_protocol(self):
        assert _is_retryable_error(httpx.RemoteProtocolError("proto")) is True

    def test_is_retryable_error_value_error(self):
        assert _is_retryable_error(ValueError("bad")) is False

    def test_is_retryable_error_type_error(self):
        assert _is_retryable_error(TypeError("bad")) is False

    def test_is_retryable_error_json_decode(self):
        assert _is_retryable_error(json.JSONDecodeError("x", "", 0)) is False

    def test_is_retryable_error_generic(self):
        assert _is_retryable_error(RuntimeError("x")) is False

    def test_parse_npc_reply_json_valid(self):
        payload = json.dumps({
            "visible_text": "你好",
            "favor_delta": 1,
            "coin_delta": 0,
            "items_gain": [],
            "items_lose": [],
            "events": [],
        })
        result = parse_npc_reply_json(payload)
        assert isinstance(result, NpcResponseSchema)
        assert result.visible_text == "你好"
        assert result.favor_delta == 1

    def test_parse_npc_reply_json_invalid_falls_back(self):
        raw = "这不是JSON，只是普通文本"
        result = parse_npc_reply_json(raw)
        assert isinstance(result, NpcResponseSchema)
        assert result.visible_text == raw
        assert result.favor_delta == 0

    def test_parse_npc_reply_json_with_markdown_fences(self):
        raw = '```json\n{"visible_text": "测试", "favor_delta": 0}\n```'
        result = parse_npc_reply_json(raw)
        assert isinstance(result, NpcResponseSchema)
        assert result.visible_text == "测试"

    def test_parse_npc_reply_json_partial_json(self):
        raw = '一些前缀文字 {"visible_text": "部分", "favor_delta": 2} 一些后缀'
        result = parse_npc_reply_json(raw)
        assert isinstance(result, NpcResponseSchema)
        assert result.visible_text == "部分"
        assert result.favor_delta == 2

    def test_parse_finale_with_title(self):
        text = "结局正文内容\nENDING_TITLE: 《归隐山林》"
        body, title = parse_finale(text)
        assert title == "归隐山林"
        assert "结局正文内容" in body
        assert "ENDING_TITLE" not in body

    def test_parse_finale_no_title(self):
        text = "普通文本没有结局标题"
        body, title = parse_finale(text)
        assert title is None
        assert body == text.strip()

    def test_parse_finale_title_strips_quotes(self):
        text = "正文\nENDING_TITLE: \"梦醒时分\""
        _body, title = parse_finale(text)
        assert title == "梦醒时分"

    def test_parse_finale_title_truncation(self):
        long_title = "A" * 50
        text = f"正文\nENDING_TITLE: {long_title}"
        _body, title = parse_finale(text)
        assert len(title or "") <= 32

    @patch("backend.llm.client.settings")
    def test_cached_system_enabled(self, mock_settings):
        mock_settings.llm_enable_prompt_cache = True
        result = cached_system("hello")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == "text"
        assert result[0]["text"] == "hello"
        assert result[0]["cache_control"] == {"type": "ephemeral"}

    @patch("backend.llm.client.settings")
    def test_cached_system_disabled(self, mock_settings):
        mock_settings.llm_enable_prompt_cache = False
        result = cached_system("hello")
        assert isinstance(result, str)
        assert result == "hello"

    @patch("backend.llm.client.settings")
    def test_uncached_enabled(self, mock_settings):
        mock_settings.llm_enable_prompt_cache = True
        result = uncached("world")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == "text"
        assert result[0]["text"] == "world"
        assert "cache_control" not in result[0]

    @patch("backend.llm.client.settings")
    def test_uncached_disabled(self, mock_settings):
        mock_settings.llm_enable_prompt_cache = False
        result = uncached("world")
        assert isinstance(result, str)
        assert result == "world"


class TestAgentBrain:

    def test_record_observation(self):
        mind = AgentMind()
        m = record_observation(mind, "看到了一个陌生人", world_day=1, world_shichen="辰时")
        assert isinstance(m, Memory)
        assert m.kind == "observation"
        assert m.text == "看到了一个陌生人"
        assert m in mind.items
        assert mind.importance_since_reflect > 0

    def test_record_observation_with_importance(self):
        mind = AgentMind()
        m = record_observation(mind, "重要事件", world_day=1, world_shichen="午时", importance=9.0)
        assert m.importance == 9.0

    def test_record_observation_default_importance(self):
        mind = AgentMind()
        m = record_observation(mind, "普通事件", world_day=1, world_shichen="午时")
        assert 1.0 <= m.importance <= 10.0

    def test_deduplicate_observations_empty(self):
        result = _deduplicate_observations([])
        assert result == []

    def test_deduplicate_observations_no_duplicates(self):
        mind = AgentMind()
        m1 = make_memory(kind="observation", text="完全不同的第一件事", importance=5.0, world_day=1, world_shichen="辰时")
        m2 = make_memory(kind="observation", text="完全不同的第二件事", importance=6.0, world_day=1, world_shichen="巳时")
        result = _deduplicate_observations([m1, m2])
        assert len(result) == 2

    def test_deduplicate_observations_keeps_highest_importance(self):
        mind = AgentMind()
        m1 = make_memory(kind="observation", text="张三来了又走了", importance=7.0, world_day=1, world_shichen="辰时")
        m2 = make_memory(kind="observation", text="张三来了又走了", importance=3.0, world_day=1, world_shichen="巳时")
        result = _deduplicate_observations([m2, m1])
        assert len(result) == 1
        assert result[0].importance == 7.0

    def test_deduplicate_observations_similar_texts(self):
        m1 = make_memory(kind="observation", text="今天天气很好，阳光明媚", importance=5.0, world_day=1, world_shichen="辰时")
        m2 = make_memory(kind="observation", text="今天天气很好，阳光明媚，适合出行", importance=4.0, world_day=1, world_shichen="巳时")
        m3 = make_memory(kind="observation", text="完全无关的事件发生了", importance=6.0, world_day=1, world_shichen="午时")
        def _sim(a, b):
            if "天气" in a and "天气" in b:
                return 0.7
            return 0.1
        with patch("backend.agents.brain.mem.text_relevance", side_effect=_sim):
            result = _deduplicate_observations([m1, m2, m3])
            assert len(result) == 2

    def test_import_seeds(self):
        mind = AgentMind()
        seeds = ["我信奉忠义", "江湖险恶需提防"]
        import_seeds(mind, seeds, world_day=1, world_shichen="子时")
        assert len(mind.items) == 2
        for m in mind.items:
            assert m.kind == "seed"
            assert m.importance == 6.0
        texts = [m.text for m in mind.items]
        assert "我信奉忠义" in texts
        assert "江湖险恶需提防" in texts

    def test_import_seeds_skips_empty(self):
        mind = AgentMind()
        import_seeds(mind, ["", "  ", "有效种子"], world_day=1, world_shichen="子时")
        assert len(mind.items) == 1
        assert mind.items[0].text == "有效种子"

    def test_import_seeds_empty_list(self):
        mind = AgentMind()
        import_seeds(mind, [], world_day=1, world_shichen="子时")
        assert len(mind.items) == 0


class TestPromptCompress:

    @pytest.mark.asyncio
    async def test_compress_conversation_history_short(self):
        hist = [{"user": f"msg{i}", "assistant": f"reply{i}"} for i in range(5)]
        result = await compress_conversation_history(hist, npc_name="测试NPC")
        assert result is hist
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_compress_conversation_history_triggers_compress(self):
        hist = [{"user": f"msg{i}", "assistant": f"reply{i}"} for i in range(20)]
        with patch("backend.llm.prompt_compress._llm_summarize", new_callable=AsyncMock) as mock_sum:
            mock_sum.return_value = "这是压缩后的摘要"
            result = await compress_conversation_history(hist, npc_name="测试NPC")
            mock_sum.assert_called_once()
            assert len(result) < len(hist)
            assert any("概要" in t.get("user", "") for t in result)

    @pytest.mark.asyncio
    async def test_compress_conversation_history_preserves_recent(self):
        hist = [{"user": f"msg{i}", "assistant": f"reply{i}"} for i in range(20)]
        with patch("backend.llm.prompt_compress._llm_summarize", new_callable=AsyncMock) as mock_sum:
            mock_sum.return_value = "摘要内容"
            result = await compress_conversation_history(hist, npc_name="测试NPC")
            recent_kept = result[-6:]
            for i, turn in enumerate(recent_kept):
                assert "msg" in turn.get("user", "") or "概要" in turn.get("user", "")

    @pytest.mark.asyncio
    async def test_compress_conversation_history_llm_failure_returns_original(self):
        hist = [{"user": f"msg{i}", "assistant": f"reply{i}"} for i in range(20)]
        with patch("backend.llm.prompt_compress._llm_summarize", new_callable=AsyncMock) as mock_sum:
            mock_sum.side_effect = RuntimeError("LLM down")
            result = await compress_conversation_history(hist, npc_name="测试NPC")
            assert result is hist
            assert len(result) == 20

    @pytest.mark.asyncio
    async def test_compress_conversation_history_old_span_marker(self):
        hist = [{"user": f"msg{i}", "assistant": f"reply{i}"} for i in range(30)]
        with patch("backend.llm.prompt_compress._llm_summarize", new_callable=AsyncMock) as mock_sum:
            mock_sum.return_value = "摘要"
            result = await compress_conversation_history(hist, npc_name="测试NPC")
            has_old_marker = any("此前还有" in t.get("user", "") for t in result)
            assert has_old_marker
