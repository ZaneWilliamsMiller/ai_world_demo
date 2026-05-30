from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
from pydantic import ValidationError

from backend.config import settings
from backend.llm.cache import get_llm_cache
from backend.llm.circuit_breaker import get_circuit_breaker
from backend.models.llm_schema import NpcResponseSchema
from backend.observability.tracker import CallRecord, get_tracker
from backend.systems.constants import RETRY_BACKOFF_JITTER_MAX, RETRY_JITTER_MAX, RETRYABLE_HTTP_STATUSES

log = logging.getLogger("llm_client")


# ══════════════════════════════════════════════════════════════
#  LLMClientManager 单例类
#  修复 Critical #1：将全局变量封装为单例类，提供更好的封装和生命周期管理
# ══════════════════════════════════════════════════════════════

class LLMClientManager:
    """LLM 客户端管理器（单例模式）。

    封装 httpx.AsyncClient 连接池和并发信号量，解决全局变量并发安全问题。
    提供统一的客户端获取、关闭接口，确保资源正确释放。
    """
    _instance: LLMClientManager | None = None

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()
        self._semaphore: asyncio.Semaphore | None = None
        self._custom_clients: dict[str, httpx.AsyncClient] = {}
        self._custom_lock = asyncio.Lock()

    @classmethod
    async def get_instance(cls) -> LLMClientManager:
        """获取单例实例（线程安全）。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_client(self) -> httpx.AsyncClient:
        """获取共享的 httpx AsyncClient（连接池），懒初始化 + 双重检查锁。"""
        if self._client is None or self._client.is_closed:
            async with self._client_lock:
                if self._client is None or self._client.is_closed:
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
                    self._client = httpx.AsyncClient(
                        timeout=timeout,
                        limits=limits,
                        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                    )
        return self._client

    async def get_custom_client(self, base_url: str, api_key: str) -> httpx.AsyncClient:
        cache_key = f"{base_url}:{api_key}"
        if cache_key in self._custom_clients:
            client = self._custom_clients[cache_key]
            if not client.is_closed:
                return client

        async with self._custom_lock:
            if cache_key in self._custom_clients:
                client = self._custom_clients[cache_key]
                if not client.is_closed:
                    return client

            timeout = httpx.Timeout(
                connect=settings.llm_pool_connect_timeout,
                read=settings.llm_pool_read_timeout,
                write=10.0,
                pool=5.0,
            )
            client = httpx.AsyncClient(
                timeout=timeout,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            self._custom_clients[cache_key] = client
            return client

    async def close_client(self) -> None:
        """关闭所有 client（共享 + 自定义）。"""
        errors = []
        if self._client and not self._client.is_closed:
            try:
                await self._client.aclose()
            except Exception as e:
                errors.append(e)
            finally:
                self._client = None
        for _key, client in list(self._custom_clients.items()):
            if not client.is_closed:
                try:
                    await client.aclose()
                except Exception as e:
                    errors.append(e)
        self._custom_clients.clear()
        if errors:
            log.warning("close_client encountered %d error(s): %s", len(errors), errors)

    def get_semaphore(self) -> asyncio.Semaphore:
        """获取并发限速信号量（懒初始化）。"""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(settings.llm_max_concurrency)
        return self._semaphore


# ── 向后兼容的便捷函数（保持公共 API 不变）──

async def _get_client() -> httpx.AsyncClient:
    """向后兼容：获取共享的 httpx AsyncClient。"""
    manager = await LLMClientManager.get_instance()
    return await manager.get_client()


async def _close_client() -> None:
    """向后兼容：关闭共享 client。"""
    manager = await LLMClientManager.get_instance()
    await manager.close_client()


def _sync_close_all_clients() -> None:
    """同步上下文中关闭所有 httpx 客户端的统一入口。

    合并原 _close_client_sync 和 _cleanup 的逻辑，
    统一处理共享 client 和自定义 client 的关闭。
    """
    inst = LLMClientManager._instance
    if inst is None:
        return

    all_clients: list[httpx.AsyncClient] = []
    if inst._client and not inst._client.is_closed:
        all_clients.append(inst._client)
    for client in list(inst._custom_clients.values()):
        if not client.is_closed:
            all_clients.append(client)

    if not all_clients:
        inst._client = None
        inst._custom_clients.clear()
        return

    async def _close_all():
        for c in all_clients:
            try:
                await c.aclose()
            except Exception:
                log.debug("close client failed", exc_info=True)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(lambda: asyncio.run(_close_all())).result(5)
        else:
            loop.run_until_complete(_close_all())
    except Exception:
        log.debug("_sync_close_all_clients failed", exc_info=True)
    finally:
        inst._client = None
        inst._custom_clients.clear()


def _close_client_sync() -> None:
    """同步关闭共享 client（用于 shutdown 线程中调用）。"""
    _sync_close_all_clients()


async def _get_semaphore() -> asyncio.Semaphore:
    """向后兼容：获取并发限速信号量。"""
    manager = await LLMClientManager.get_instance()
    return manager.get_semaphore()


# ══════════════════════════════════════════════════════════════
#  公共工具函数（修复 Major #7：消除重复代码）
# ══════════════════════════════════════════════════════════════

def _build_request_body(
    messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int,
    model: str,
    response_format: dict[str, Any] | None = None,
    stream: bool = False,
) -> dict[str, Any]:
    """构建 LLM API 请求体。

    提取自 chat_completion 和 stream_chat_completion 的重复逻辑。
    """
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        body["response_format"] = response_format
    if stream:
        body["stream"] = True
    return body


def _is_retryable_error(error: Exception) -> bool:
    """判断异常是否可重试（修复 Major #5：细化异常类型）。

    可重试异常：
    - httpx.ConnectError: 连接失败（网络抖动）
    - httpx.NetworkError: 网络层错误
    - httpx.TimeoutException: 超时

    不可重试异常：
    - ValueError / TypeError: 参数错误（重试无意义）
    - json.JSONDecodeError: 响应解析失败
    - 其他未知异常
    """
    retryable_types = (
        httpx.ConnectError,
        httpx.NetworkError,
        httpx.TimeoutException,
        httpx.RemoteProtocolError,
    )
    return isinstance(error, retryable_types)


async def _execute_with_retry(
    request_func,
    max_retries: int,
    base_delay: float,
    circuit_breaker,
    operation_name: str = "LLM",
) -> Any:
    """执行带重试的请求（修复 Major #7：提取公共重试逻辑）。

    Args:
        request_func: 异步请求函数（无参数 callable）
        max_retries: 最大重试次数
        base_delay: 基础退避延迟（秒）
        circuit_breaker: 熔断器实例
        operation_name: 操作名称（用于日志）

    Returns:
        请求函数的返回值
    """
    for attempt in range(max_retries):
        try:
            return await request_func()

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            is_retryable_status = status in RETRYABLE_HTTP_STATUSES

            if is_retryable_status and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, RETRY_JITTER_MAX)
                log.warning(
                    f"{operation_name} API {status} error (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {delay:.1f}s: {e.response.text[:128]}"
                )
                await asyncio.sleep(delay)
                continue

            await circuit_breaker.failure()
            log.error(f"{operation_name} API Error: {e.response.text[:512]}")
            tracker = get_tracker()
            tracker.record(CallRecord(
                timestamp=time.time(), operation=operation_name, model="",
                status="failed", error_msg=f"HTTP {status}: {e.response.text[:128]}",
            ))
            raise

        except Exception as e:
            if _is_retryable_error(e) and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, RETRY_BACKOFF_JITTER_MAX)
                log.warning(
                    f"{operation_name} request failed (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {delay:.1f}s: {e}"
                )
                await asyncio.sleep(delay)
                continue

            await circuit_breaker.failure()
            log.error(f"{operation_name} Request Failed: {e}")
            tracker = get_tracker()
            tracker.record(CallRecord(
                timestamp=time.time(), operation=operation_name, model="",
                status="failed", error_msg=str(e)[:128],
            ))
            raise

    tracker = get_tracker()
    tracker.record(CallRecord(
        timestamp=time.time(), operation=operation_name, model="",
        status="failed", error_msg=f"all {max_retries} retries exhausted",
    ))
    raise RuntimeError(f"{operation_name}: all {max_retries} retries exhausted")


async def _handle_llm_response(response_data: dict[str, Any], cache, circuit_breaker, messages, *, temperature: float = 0.0, model: str = "", max_tokens: int = 0, response_format: dict[str, Any] | None = None, start_time: float = 0.0, operation: str = "chat_completion", base_url: str = "") -> str:
    """处理 LLM 响应并写入缓存（修复 Major #7：提取公共响应解析逻辑）。

    Returns:
        解析后的文本内容
    """
    usage = response_data.get("usage", {})
    prompt_tokens = 0
    completion_tokens = 0
    if isinstance(usage, dict):
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)
        cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
        log.info(
            "LLM usage: prompt=%d completion=%d total=%d cached=%d",
            prompt_tokens, completion_tokens, total_tokens, cached_tokens,
        )

    choices = response_data.get("choices") or []
    content = ""
    if choices:
        msg = choices[0].get("message", {})
        content = msg.get("content") or ""
    content = content or ""

    if settings.llm_cache_enabled:
        await cache.set(messages, content, temperature=temperature, model=model, max_tokens=max_tokens, response_format=response_format, base_url=base_url)
    await circuit_breaker.success()

    tracker = get_tracker()
    latency_ms = (time.time() - start_time) * 1000 if start_time else 0.0
    tracker.record(CallRecord(
        timestamp=time.time(), operation=operation, model=model,
        tokens_in=prompt_tokens, tokens_out=completion_tokens,
        latency_ms=round(latency_ms, 2), status="success",
    ))

    return content


def _parse_stream_line(line: str) -> str | None:
    """解析 SSE 流式响应的一行数据。

    Returns:
        解析出的文本片段，或 None（空行/结束标记/解析失败）
    """
    if not line or line.startswith(":"):
        return None
    if line.startswith("data: "):
        payload = line[6:].strip()
        if payload == "[DONE]":
            return None
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
        choice0 = (data.get("choices") or [{}])[0]
        delta = choice0.get("delta") or {}
        piece = delta.get("content")
        return piece
    return None


# ══════════════════════════════════════════════════════════════
#  Prompt Cache (OpenAI 兼容)
# ══════════════════════════════════════════════════════════════


def cached_system(content: str) -> str | list[dict[str, Any]]:
    """生成 system content。

    llm_enable_prompt_cache=True  → 带 cache_control 标记的 content 数组（OpenAI 兼容）。
    llm_enable_prompt_cache=False → 纯文本字符串（兼容非 OpenAI API）。
    """
    if settings.llm_enable_prompt_cache:
        return [{
            "type": "text",
            "text": content,
            "cache_control": {"type": "ephemeral"},
        }]
    else:
        return content


def uncached(content: str) -> str | list[dict[str, Any]]:
    """生成不带缓存的 content。

    当 prompt cache 启用时返回数组格式，关闭时返回纯文本。
    """
    if settings.llm_enable_prompt_cache:
        return [{"type": "text", "text": content}]
    else:
        return content


# ══════════════════════════════════════════════════════════════
#  核心接口
# ══════════════════════════════════════════════════════════════

async def chat_completion(
    messages: list[dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 1024,
    response_format: dict[str, Any] | None = None,
    llm_base_url: str | None = None,
    llm_api_key: str | None = None,
    llm_model: str | None = None,
) -> str:
    """OpenAI 兼容聊天补全（带连接池 + 熔断器 + 缓存 + 智能重试）。

    如果提供了 llm_base_url/llm_api_key/llm_model，则使用自定义配置，否则使用全局配置。
    """
    use_custom = bool(llm_base_url or llm_api_key or llm_model)
    base_url = (llm_base_url or settings.llm_base_url) if use_custom else settings.llm_base_url
    api_key = (llm_api_key or settings.llm_api_key) if use_custom else settings.llm_api_key
    model = (llm_model or settings.llm_model) if use_custom else settings.llm_model

    cache = get_llm_cache()
    cb = get_circuit_breaker()
    sem = await _get_semaphore()

    if settings.llm_cache_enabled:
        cached = await cache.get(messages, temperature=temperature, model=model,
                                  max_tokens=max_tokens, response_format=response_format,
                                  base_url=base_url)
        if cached is not None:
            return cached

    if not await cb.allow():
        raise RuntimeError(
            f"LLM API circuit breaker OPEN (state={cb.state.value}); "
            "requests blocked to prevent cascading failures"
        )

    url = f"{base_url.rstrip('/')}/chat/completions"
    body = _build_request_body(messages, temperature, max_tokens, model,
                                response_format=response_format)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    manager = await LLMClientManager.get_instance()
    client = await (manager.get_custom_client(base_url, api_key)
                    if use_custom else manager.get_client())

    max_retries = settings.llm_max_retries
    base_delay = settings.llm_retry_base_delay_s
    _start = time.time()
    operation = "chat_completion_custom" if use_custom else "chat_completion"

    async with sem:
        async def _do_request():
            r = await client.post(url, json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
            return await _handle_llm_response(
                data, cache, cb, messages,
                temperature=temperature, model=model,
                max_tokens=max_tokens, response_format=response_format,
                start_time=_start, operation=operation, base_url=base_url,
            )

        return await _execute_with_retry(_do_request, max_retries, base_delay, cb, "LLM")


async def stream_chat_completion(
    messages: list[dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 1024,
    llm_base_url: str | None = None,
    llm_api_key: str | None = None,
    llm_model: str | None = None,
) -> AsyncIterator[str]:
    """OpenAI 兼容流式输出（带连接池 + 熔断器 + 智能重试）。

    如果提供了 llm_base_url/llm_api_key/llm_model，则使用自定义配置，否则使用全局配置。
    """
    use_custom = bool(llm_base_url or llm_api_key or llm_model)
    base_url = (llm_base_url or settings.llm_base_url) if use_custom else settings.llm_base_url
    api_key = (llm_api_key or settings.llm_api_key) if use_custom else settings.llm_api_key
    model = (llm_model or settings.llm_model) if use_custom else settings.llm_model

    cb = get_circuit_breaker()
    sem = await _get_semaphore()
    _start = time.time()

    if not await cb.allow():
        raise RuntimeError(
            f"LLM API circuit breaker OPEN (state={cb.state.value}); "
            "streaming request blocked"
        )

    url = f"{base_url.rstrip('/')}/chat/completions"
    body = _build_request_body(messages, temperature, max_tokens, model, stream=True)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    manager = await LLMClientManager.get_instance()
    client = await (manager.get_custom_client(base_url, api_key)
                    if use_custom else manager.get_client())
    operation = "stream_custom" if use_custom else "stream_chat_completion"

    async with sem:
        max_retries = settings.llm_max_retries
        base_delay = settings.llm_retry_base_delay_s

        for attempt in range(max_retries):
            try:
                async with client.stream("POST", url, json=body, headers=headers) as r:
                    try:
                        r.raise_for_status()
                        async for line in r.aiter_lines():
                            piece = _parse_stream_line(line)
                            if piece:
                                yield piece
                    except Exception as stream_err:
                        log.error(f"Stream processing error (attempt {attempt + 1}): {stream_err}")
                        raise

                await cb.success()
                tracker = get_tracker()
                latency_ms = (time.time() - _start) * 1000
                tracker.record(CallRecord(
                    timestamp=time.time(), operation=operation, model=model,
                    latency_ms=round(latency_ms, 2), status="success",
                ))
                return

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in RETRYABLE_HTTP_STATUSES and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, RETRY_JITTER_MAX)
                    log.warning(
                        f"LLM Stream {status} error (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                    continue

                await cb.failure()
                log.error(f"LLM Stream API Error: {e.response.text[:512]}")
                raise

            except Exception as e:
                if _is_retryable_error(e) and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, RETRY_BACKOFF_JITTER_MAX)
                    log.warning(
                        f"LLM stream failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                    continue

                await cb.failure()
                log.error(f"LLM Stream Request Failed: {e}")
                raise


def _extract_json(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    i = start
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == '\\':
                i += 2
                continue
            if ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i+1]
        i += 1
    return None


def parse_npc_reply_json(text: str) -> NpcResponseSchema:
    """尝试将 LLM 输出解析为 NpcResponseSchema"""
    json_str = _extract_json(text) or text

    try:
        data = json.loads(json_str)
        return NpcResponseSchema(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        log.error(f"Failed to parse NPC reply as JSON: {e}\nRaw text: {text[:200]}")
        return NpcResponseSchema(visible_text=text.replace("```json", "").replace("```", "").strip())  # type: ignore[call-arg]


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
    """进程退出时尽力关闭共享 client（同步上下文 fallback）。

    注意：如果进程是在事件循环运行中退出（如 uvicorn 正常关闭），
    _close_client() 已通过 FastAPI shutdown 事件调用，此处仅为
    非 FastAPI 上下文（如测试、脚本）的兜底。
    """
    _sync_close_all_clients()


atexit.register(_cleanup)
