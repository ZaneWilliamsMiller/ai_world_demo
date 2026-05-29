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
from .systems.constants import RETRYABLE_HTTP_STATUSES, RETRY_JITTER_MAX, RETRY_BACKOFF_JITTER_MAX

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
        for key, client in list(self._custom_clients.items()):
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


def _close_client_sync() -> None:
    """同步关闭共享 client（用于 shutdown 线程中调用）。"""
    try:
        inst = LLMClientManager._instance
        if inst is None:
            return
        if inst._client and not inst._client.is_closed:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        pool.submit(lambda: asyncio.run(inst._client.aclose())).result(5)
                    return
            except RuntimeError:
                pass
            asyncio.run(inst._client.aclose())
        inst._client = None
        inst._custom_clients.clear()
    except Exception:
        log.debug("close_client_sync failed", exc_info=True)


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
                delay = base_delay * (2 ** attempt) + (time.time() % 1.0) * RETRY_JITTER_MAX
                log.warning(
                    f"{operation_name} API {status} error (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {delay:.1f}s: {e.response.text[:128]}"
                )
                await asyncio.sleep(delay)
                continue

            await circuit_breaker.failure()
            log.error(f"{operation_name} API Error: {e.response.text[:512]}")
            raise

        except Exception as e:
            # 修复 Major #5：区分可重试和不可重试异常
            if _is_retryable_error(e) and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + (time.time() % 1.0) * RETRY_BACKOFF_JITTER_MAX
                log.warning(
                    f"{operation_name} request failed (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {delay:.1f}s: {e}"
                )
                await asyncio.sleep(delay)
                continue

            await circuit_breaker.failure()
            log.error(f"{operation_name} Request Failed: {e}")
            raise

    return None


async def _handle_llm_response(response_data: dict[str, Any], cache, circuit_breaker, messages, *, temperature: float = 0.0, model: str = "", max_tokens: int = 0) -> str:
    """处理 LLM 响应并写入缓存（修复 Major #7：提取公共响应解析逻辑）。

    Returns:
        解析后的文本内容
    """
    usage = response_data.get("usage", {})
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
    content = choices[0]["message"]["content"] if choices else ""
    content = content or ""

    await cache.set(messages, content, temperature=temperature, model=model, max_tokens=max_tokens)
    await circuit_breaker.success()

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
    use_custom = llm_base_url or llm_api_key or llm_model
    
    if use_custom:
        url = f"{(llm_base_url or settings.llm_base_url).rstrip('/')}/chat/completions"
        body = _build_request_body(
            messages, temperature, max_tokens,
            llm_model or settings.llm_model,
            response_format=response_format,
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {llm_api_key or settings.llm_api_key}",
        }

        manager = await LLMClientManager.get_instance()
        client = await manager.get_custom_client(
            llm_base_url or settings.llm_base_url,
            llm_api_key or settings.llm_api_key,
        )
        max_retries = 2
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            r = None
            try:
                r = await client.post(url, json=body, headers=headers)
                r.raise_for_status()
                data = r.json()
                choices = data.get("choices") or []
                content = choices[0]["message"]["content"] if choices else ""
                content = content or ""
                return content
            except Exception as exc:
                last_exc = exc
                status = getattr(r, "status_code", 0) if r else 0
                if status not in RETRYABLE_HTTP_STATUSES or attempt == max_retries:
                    raise
                import random as _rng
                backoff = (2 ** attempt) + _rng.uniform(0, RETRY_BACKOFF_JITTER_MAX)
                log.warning("custom LLM retry %d/%d after %.1fs: %s", attempt + 1, max_retries, backoff, exc)
                await asyncio.sleep(backoff)
        raise last_exc
    
    cache = get_llm_cache()
    cb = get_circuit_breaker()
    sem = await _get_semaphore()

    # ── 1. 检查缓存 ──
    cached = await cache.get(messages, temperature=temperature, model=settings.llm_model, max_tokens=max_tokens)
    if cached is not None:
        return cached

    # ── 2. 熔断器检查 ──
    if not await cb.allow():
        raise RuntimeError(
            f"LLM API circuit breaker OPEN (state={cb.state.value}); "
            "requests blocked to prevent cascading failures"
        )

    # ── 3. 限速 + 请求 ──
    async with sem:
        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        body = _build_request_body(
            messages, temperature, max_tokens,
            settings.llm_model,
            response_format=response_format,
        )

        max_retries = settings.llm_max_retries
        base_delay = settings.llm_retry_base_delay_s

        async def _do_request():
            client = await _get_client()
            r = await client.post(url, json=body)
            r.raise_for_status()
            data = r.json()
            return await _handle_llm_response(data, cache, cb, messages, temperature=temperature, model=settings.llm_model, max_tokens=max_tokens)

        result = await _execute_with_retry(_do_request, max_retries, base_delay, cb, "LLM")
        return result or ""


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
    use_custom = llm_base_url or llm_api_key or llm_model
    
    if use_custom:
        url = f"{(llm_base_url or settings.llm_base_url).rstrip('/')}/chat/completions"
        body = _build_request_body(
            messages, temperature, max_tokens,
            llm_model or settings.llm_model,
            stream=True,
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {llm_api_key or settings.llm_api_key}",
        }

        manager = await LLMClientManager.get_instance()
        client = await manager.get_custom_client(
            llm_base_url or settings.llm_base_url,
            llm_api_key or settings.llm_api_key,
        )
        async with client.stream("POST", url, json=body, headers=headers) as r:
            try:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    piece = _parse_stream_line(line)
                    if piece:
                        yield piece
            except Exception as stream_err:
                log.error(f"Custom config stream error: {stream_err}")
                yield f"[STREAM_ERROR] {stream_err}"
        return
    
    else:
        cb = get_circuit_breaker()
        sem = await _get_semaphore()

        if not await cb.allow():
            raise RuntimeError(
                f"LLM API circuit breaker OPEN (state={cb.state.value}); "
                "streaming request blocked"
            )

        async with sem:
            url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
            body = _build_request_body(
                messages, temperature, max_tokens,
                settings.llm_model,
                stream=True,
            )

            max_retries = settings.llm_max_retries
            base_delay = settings.llm_retry_base_delay_s

            for attempt in range(max_retries):
                stream_had_error = False
                try:
                    client = await _get_client()
                    # 修复 Major #6：使用 try/finally 确保流在异常时优雅关闭
                    async with client.stream("POST", url, json=body) as r:
                        try:
                            r.raise_for_status()
                            async for line in r.aiter_lines():
                                piece = _parse_stream_line(line)
                                if piece:
                                    yield piece
                        except Exception as stream_err:
                            stream_had_error = True
                            log.error(f"Stream processing error (attempt {attempt + 1}): {stream_err}")
                            yield f"[STREAM_ERROR] {stream_err}"
                            raise

                    # 流式成功 → 熔断器记录成功
                    await cb.success()
                    return

                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    is_retryable_status = status in RETRYABLE_HTTP_STATUSES

                    if is_retryable_status and attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt) + (time.time() % 1.0) * RETRY_JITTER_MAX
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
                    # 修复 Major #5：区分可重试和不可重试异常
                    if _is_retryable_error(e) and attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt) + (time.time() % 1.0) * RETRY_BACKOFF_JITTER_MAX
                        log.warning(
                            f"LLM stream failed (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {delay:.1f}s: {e}"
                        )
                        await asyncio.sleep(delay)
                        continue

                    await cb.failure()
                    log.error(f"LLM Stream Request Failed: {e}")
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
        log.error(f"Failed to parse NPC reply as JSON: {e}\nRaw text: {text[:200]}")
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
    """进程退出时尽力关闭共享 client（同步上下文 fallback）。

    注意：如果进程是在事件循环运行中退出（如 uvicorn 正常关闭），
    _close_client() 已通过 FastAPI shutdown 事件调用，此处仅为
    非 FastAPI 上下文（如测试、脚本）的兜底。
    在运行中的事件循环内调用 run_until_complete 会抛 RuntimeError，
    此处直接同步关闭 client 即可。
    """
    import asyncio
    if LLMClientManager._instance is None:
        return
    mgr = LLMClientManager._instance
    if mgr._client and not mgr._client.is_closed:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                pass
            else:
                loop.run_until_complete(mgr._client.aclose())
        except Exception:
            log.debug("_cleanup close client failed", exc_info=True)
        finally:
            mgr._client = None
    for key, client in list(mgr._custom_clients.items()):
        if not client.is_closed:
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    loop.run_until_complete(client.aclose())
            except Exception:
                log.debug("_cleanup close custom client failed", exc_info=True)
    mgr._custom_clients.clear()


atexit.register(_cleanup)
