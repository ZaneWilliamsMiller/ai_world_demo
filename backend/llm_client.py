import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
from pydantic import ValidationError

from .config import settings
from .models.llm_schema import NpcResponseSchema

log = logging.getLogger("llm_client")

# ═══════════════════════════════════════════════════════════════
#  Prompt Cache (GLM-4 / OpenAI 兼容)
# ═══════════════════════════════════════════════════════════════
# 原理：
#   - 将大段静态 system prompt 标记 cache_control={type:"ephemeral"}，
#     缓存命中时 API 跳过该块的推理计费，延迟降低 30~60%。
#   - GLM-4 在缓存窗口内（约 5 min）自动复用相同前缀 content。
#   - 对于不支持 cache_control 的端点，标记会被静默忽略（不报错）。
#   - 关键优化：talk_service.build_npc_messages 将 SOCIETY_BIBLE +
#     角色卡等静态块放入 system 可缓存层；动态 context 放在
#     后续 user message 中非缓存传递。


def cached_system(content: str) -> list[dict[str, Any]]:
    """生成带 cache_control 标记的 system content 数组。

    把一大段静态 system prompt 包在一个 ephemeral cache 块里，
    后续调用相同 content 即可命中缓存。
    """
    return [{
        "type": "text",
        "text": content,
        "cache_control": {"type": "ephemeral"},
    }]


def uncached(content: str) -> list[dict[str, Any]]:
    """生成不带缓存的 content 数组（动态上下文块）。
    
    与 cached_system 配对使用：先拼 cached_system 块，再拼 uncached 动态块，
    确保 API 只对缓存后的新内容计费。
    """
    return [{"type": "text", "text": content}]


async def chat_completion(
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 1024,
    response_format: dict[str, Any] | None = None,
) -> str:
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    body: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        body["response_format"] = response_format

    # 简单重试逻辑
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_s) as client:
                r = await client.post(url, headers=headers, json=body)
                r.raise_for_status()
                data = r.json()
            # 记录缓存命中信息（如果 API 返回了 usage.cache 相关字段）
            usage = data.get("usage", {})
            if isinstance(usage, dict):
                cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                if cached_tokens:
                    log.info("Prompt cache hit: %d cached tokens", cached_tokens)
            return data["choices"][0]["message"]["content"] or ""
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                import asyncio
                await asyncio.sleep(2 ** attempt)
                continue
            log.error("LLM API Error: %s", e.response.text[:512])
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                import asyncio
                await asyncio.sleep(2 ** attempt)
                continue
            log.error("LLM Request Failed: %s", e)
            raise
    return ""


async def stream_chat_completion(
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> AsyncIterator[str]:
    """OpenAI 兼容流式：逐段产出 delta content（智谱 / vLLM 等常见）。"""
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    body: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_s) as client:
                async with client.stream("POST", url, headers=headers, json=body) as r:
                    r.raise_for_status()
                    async for line in r.aiter_lines():
                        if not line or line.startswith(":"):
                            continue
                        if line.startswith("data: "):
                            payload = line[6:].strip()
                            if payload == "[DONE]":
                                break
                            try:
                                data = json.loads(payload)
                            except json.JSONDecodeError:
                                continue
                            choice0 = (data.get("choices") or [{}])[0]
                            delta = choice0.get("delta") or {}
                            piece = delta.get("content")
                            if piece:
                                yield piece
            break
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                import asyncio
                await asyncio.sleep(2 ** attempt)
                continue
            log.error("LLM Stream API Error: %s", e.response.text[:512])
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                import asyncio
                await asyncio.sleep(2 ** attempt)
                continue
            log.error("LLM Stream Request Failed: %s", e)
            raise


def parse_npc_reply_json(text: str) -> NpcResponseSchema:
    """尝试将 LLM 输出解析为 NpcResponseSchema"""
    import re
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    json_str = json_match.group(0) if json_match else text

    try:
        data = json.loads(json_str)
        return NpcResponseSchema(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        log.error("Failed to parse NPC reply as JSON: %s\nRaw text: %.200s", e, text)
        return NpcResponseSchema(visible_text=text.replace("```json", "").replace("```", "").strip())


def parse_finale(text: str) -> tuple[str, str | None]:
    import re
    pattern = re.compile(
        r"ENDING_TITLE:\s*(.+?)\s*$",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return text.strip(), None
    body = text[: m.start()].strip()
    title = m.group(1).strip().strip("《》").strip('"').strip("'")
    if not title:
        return body, None
    if len(title) > 32:
        title = title[:32]
    return body, title