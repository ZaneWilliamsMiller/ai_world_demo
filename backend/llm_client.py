from __future__ import annotations
import json
import logging
import time
import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx
from pydantic import ValidationError

from .config import settings
from .models.llm_schema import NpcResponseSchema
from .llm_cache import get_llm_cache
from .circuit_breaker import get_circuit_breaker

log = logging.getLogger("llm_client")

# ── 共享 httpx AsyncClient（连接池复用）──
#  单例模式：整个进程复用同一个 client，避免每次创建新连接
_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


async def _get_client() -> httpx.AsyncClient:
    """获取共享的 httpx AsyncClient（连接池）。"""
    global _client
    if _client is None or _client.is_closed:
        async with _client_lock:
            # 二次检查（double-check）
            if _client is None or _client.is_closed:
                timeout = httpx.Timeout(
                    connect=settings.llm_pool_connect_timeout,
                    read=settings.llm_pool_read_timeout,
                    write=10.0,
                    pool=5.0,
                )
                limits = httpx.Limits(
                    max_connections=settings.llm_pool_max_connections,
                    max_keepalive_connections=settings.llm_pool_max_keepalive,
                )
                _client = httpx.AsyncClient(
                    timeout=timeout,
                    limits=limits,
                    headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                )
    return _client


async def _close_client() -> None:
    """关闭共享 client（用于优雅退出）。"""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


# ── 并发限速（Semaphore）──
#  防止并发请求过多压垮 LLM API
_llm_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(settings.llm_max_concurrency)
    return _llm_semaphore


# ══════════════════════════════════════════════════════════════
#  Prompt Cache (OpenAI 兼容)
# ══════════════════════════════════════════════════════════════


def cached_system(content: str) -> list[dict[str, Any]]:
    """生成 system content。
    
    llm_enable_prompt_cache=True  → 带 cache_control 标记的 content 数组（OpenAI 兼容）。
    llm_enable_prompt_cache=False → 纯文本字符串（兼容非 OpenAI API）。
    """
    from backend.config import settings
    if settings.llm_enable_prompt_cache:
        return [{
            "type": "text",
            "text": content,
            "cache_control": {"type": "ephemeral"},
        }]
    else:
        # 非 OpenAI 兼容模式：返回纯文本字符串（大多数 API 只接受 str 类型的 content）
        return content


def uncached(content: str) -> str | list[dict[str, Any]]:
    """生成不带缓存的 content。
    
    当 prompt cache 启用时返回数组格式，关闭时返回纯文本。
    """
    from backend.config import settings
    if settings.llm_enable_prompt_cache:
        return [{"type": "text", "text": content}]
    else:
        return content


async def chat_completion(
    messages: list[dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 1024,
    response_format: dict[str, Any] | None = None,
) -> str:
    """OpenAI 兼容聊天补全（带连接池 + 熔断器 + 缓存 + 智能重试）。"""
    cache = get_llm_cache()
    cb = get_circuit_breaker()
    sem = _get_semaphore()

    # ── 1. 检查缓存 ──
    cached = await cache.get(messages)
    if cached is not None:
        return cached

    # ── 2. 熔断器检查 ──
    if not await cb.allow():
        raise RuntimeError(
            f"LLM API circuit breaker OPEN (state={cb.state.value}); "
            "requests blocked to prevent cascading failures"
        )

    # ── 3. 限速 ──
    async with sem:
        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        body: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            body["response_format"] = response_format

        max_retries = settings.llm_max_retries
        base_delay = settings.llm_retry_base_delay_s

        for attempt in range(max_retries):
            try:
                client = await _get_client()
                r = await client.post(url, json=body)
                r.raise_for_status()
                data = r.json()

                # 记录缓存命中信息
                usage = data.get("usage", {})
                if isinstance(usage, dict):
                    cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                    if cached_tokens:
                        log.info("Prompt cache hit: %d cached tokens", cached_tokens)

                content = data["choices"][0]["message"]["content"] or ""

                # ── 4. 写入缓存 ──
                await cache.set(messages, content)

                # ── 5. 熔断器：记录成功 ──
                await cb.success()

                return content

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                is_retryable = status in (429, 502, 503, 504)

                if is_retryable and attempt < max_retries - 1:
                    # 智能退避：指数 + 随机 jitter
                    delay = base_delay * (2 ** attempt) + (time.time() % 1.0) * 0.5
                    log.warning(
                        "LLM API %d error (attempt %d/%d), retrying in %.1fs: %s",
                        status, attempt + 1, max_retries, delay, e.response.text[:128]
                    )
                    await asyncio.sleep(delay)
                    continue

                # 非可重试错误或重试次数用尽
                await cb.failure()
                log.error("LLM API Error: %s", e.response.text[:512])
                raise

            except httpx.TimeoutException as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + (time.time() % 1.0) * 0.3
                    log.warning(
                        "LLM API timeout (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, max_retries, delay, e
                    )
                    await asyncio.sleep(delay)
                    continue
                await cb.failure()
                log.error("LLM Request Timeout: %s", e)
                raise

            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + (time.time() % 1.0) * 0.3
                    log.warning(
                        "LLM request failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, max_retries, delay, e
                    )
                    await asyncio.sleep(delay)
                    continue
                await cb.failure()
                log.error("LLM Request Failed: %s", e)
                raise

    return ""


async def stream_chat_completion(
    messages: list[dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> AsyncIterator[str]:
    """OpenAI 兼容流式输出（带连接池 + 熔断器 + 智能重试）。"""
    cb = get_circuit_breaker()
    sem = _get_semaphore()

    # 熔断器检查
    if not await cb.allow():
        raise RuntimeError(
            f"LLM API circuit breaker OPEN (state={cb.state.value}); "
            "streaming request blocked"
        )

    async with sem:
        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        body: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        max_retries = settings.llm_max_retries
        base_delay = settings.llm_retry_base_delay_s

        for attempt in range(max_retries):
            try:
                client = await _get_client()
                async with client.stream("POST", url, json=body) as r:
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

                # 流式成功 → 熔断器记录成功
                await cb.success()
                return

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                is_retryable = status in (429, 502, 503, 504)

                if is_retryable and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + (time.time() % 1.0) * 0.5
                    log.warning(
                        "LLM Stream %d error (attempt %d/%d), retrying in %.1fs",
                        status, attempt + 1, max_retries, delay
                    )
                    await asyncio.sleep(delay)
                    continue

                await cb.failure()
                log.error("LLM Stream API Error: %s", e.response.text[:512])
                raise

            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + (time.time() % 1.0) * 0.3
                    log.warning(
                        "LLM stream failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, max_retries, delay, e
                    )
                    await asyncio.sleep(delay)
                    continue
                await cb.failure()
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
    body = text[:m.start()].strip()
    title = m.group(1).strip().strip("《》").strip('"').strip("'")
    if not title:
        return body, None
    if len(title) > 32:
        title = title[:32]
    return body, title


# ── 优雅退出：关闭共享 client ──
import atexit


def _cleanup() -> None:
    """进程退出时关闭共享 client。"""
    if _client and not _client.is_closed:
        try:
            asyncio.get_event_loop().run_until_complete(_close_client())
        except Exception:
            pass


atexit.register(_cleanup)
