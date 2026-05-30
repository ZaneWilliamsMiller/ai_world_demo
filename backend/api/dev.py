"""开发专用路由 — 功能测试与交互测试。

仅在 ENABLE_TEST_ROUTES=1 时挂载，生产环境不暴露。
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib
import os
import re
import sys
import time
import traceback
import unittest
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.api.schema import (
    InteractiveModuleResultResponse,
    InteractiveModulesResponse,
    InteractiveTestResultResponse,
    ModuleResultResponse,
    ResetCircuitBreakerResponse,
    TestListResponse,
    TestModulesResponse,
    TestResultResponse,
)
from backend.config import settings

TESTS_DIR = Path(__file__).resolve().parents[2] / "tests"
_func_lock = asyncio.Lock()
_interactive_lock = asyncio.Lock()


def _guard_test_routes() -> None:
    if not settings.enable_test_routes:
        raise HTTPException(403, "测试路由已禁用。设置 ENABLE_TEST_ROUTES=1 以启用。")


router = APIRouter(
    prefix="/api/tests",
    tags=["tests"],
    dependencies=[Depends(_guard_test_routes)],
)


class TestInfo(BaseModel):
    name: str
    description: str
    file_path: str


class TestResult(BaseModel):
    test_name: str
    success: bool
    output: str
    exit_code: int | None = None
    elapsed: float = 0.0
    cases_passed: int = 0
    cases_failed: int = 0
    cases_skipped: int = 0


class ModuleInfo(BaseModel):
    id: str
    label: str
    count: int
    tests: list[TestInfo]


class ModuleResult(BaseModel):
    module_id: str
    total: int
    passed: int
    failed: int
    skipped: int = 0
    results: list[TestResult]


def _get_test_description(file_path: Path) -> str:
    try:
        content = file_path.read_text(encoding="utf-8")
        first_line = content.split("\n")[0].strip()
        if first_line.startswith('"""') or first_line.startswith("'''"):
            return first_line.strip('"\'').strip()
        return file_path.stem.replace("_", " ").replace("test ", "").title()
    except Exception:
        return file_path.stem


def _discover_tests() -> list[tuple[Path, str]]:
    if not TESTS_DIR.exists():
        return []
    results = []
    for f in sorted(TESTS_DIR.rglob("test_*.py")):
        rel = str(f.relative_to(TESTS_DIR)).replace("\\", "/")
        if rel.startswith("interactive/"):
            continue
        results.append((f, rel))
    return results


def _module_id_from_rel(rel: str) -> str:
    parts = rel.split("/")
    if len(parts) >= 2:
        return "/".join(parts[:-1])
    return ""


_MODULE_LABELS: dict[str, str] = {
    "integration": "功能测试 · 集成",
    "unit/agents": "功能测试 · Agent",
    "unit/api": "功能测试 · API",
    "unit/data": "功能测试 · 数据",
    "unit/llm": "功能测试 · LLM",
    "unit/memory": "功能测试 · 记忆",
    "unit/models": "功能测试 · 模型",
    "unit/services": "功能测试 · 服务",
    "unit/session": "功能测试 · 会话",
    "unit/systems": "功能测试 · 系统",
}


@router.get("/list", response_model=TestListResponse)
async def list_tests():
    tests = []
    for f, rel in _discover_tests():
        tests.append(TestInfo(
            name=rel,
            description=_get_test_description(f),
            file_path=str(f.relative_to(TESTS_DIR.parent))
        ))
    return {"count": len(tests), "tests": tests}


@router.get("/modules", response_model=TestModulesResponse)
async def list_modules():
    all_tests = _discover_tests()
    module_map: dict[str, list[TestInfo]] = {}

    for f, rel in all_tests:
        mid = _module_id_from_rel(rel)
        if mid not in module_map:
            module_map[mid] = []
        module_map[mid].append(TestInfo(
            name=rel,
            description=_get_test_description(f),
            file_path=str(f.relative_to(TESTS_DIR.parent))
        ))

    modules = []
    for mid in sorted(module_map.keys()):
        label = _MODULE_LABELS.get(mid, mid.replace("/", " · ").title())
        modules.append(ModuleInfo(
            id=mid,
            label=label,
            count=len(module_map[mid]),
            tests=module_map[mid],
        ))

    return {"count": len(all_tests), "modules": modules}


def _parse_pytest_counts(output: str) -> tuple[int, int, int]:
    passed = failed = skipped = 0
    for line in output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if " passed" in line or " failed" in line or " skipped" in line:
            m = re.search(r"(\d+)\s+passed", line)
            if m:
                passed = int(m.group(1))
            m = re.search(r"(\d+)\s+failed", line)
            if m:
                failed = int(m.group(1))
            m = re.search(r"(\d+)\s+skipped", line)
            if m:
                skipped = int(m.group(1))
            return passed, failed, skipped
    return passed, failed, skipped


async def _run_single(test_path: str) -> TestResult:
    test_name = test_path.replace("/", os.sep).replace("\\", os.sep)
    test_file = TESTS_DIR / test_name

    env = os.environ.copy()
    project_root = str(TESTS_DIR.parent)
    pythonpath = env.get("PYTHONPATH", "")
    if pythonpath:
        env["PYTHONPATH"] = project_root + os.pathsep + pythonpath
    else:
        env["PYTHONPATH"] = project_root

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m", "pytest",
        str(test_file),
        "-v", "--tb=short", "--no-header",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=project_root,
        env=env,
    )

    t0 = asyncio.get_running_loop().time()
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
    elapsed = round(asyncio.get_running_loop().time() - t0, 1)
    output = stdout.decode("utf-8", errors="replace")

    cp, cf, cs = _parse_pytest_counts(output)

    return TestResult(
        test_name=test_path,
        success=(proc.returncode == 0),
        output=output,
        exit_code=proc.returncode,
        elapsed=elapsed,
        cases_passed=cp,
        cases_failed=cf,
        cases_skipped=cs,
    )


@router.post("/run/{test_path:path}", response_model=TestResultResponse)
async def run_test(test_path: str):
    test_name = test_path.replace("/", os.sep).replace("\\", os.sep)
    if ".." in test_name or not re.match(r'^[\w/\\]+\.py$', test_name.replace(os.sep, "/")):
        raise HTTPException(400, "无效的测试路径")
    test_file = TESTS_DIR / test_name
    if not test_file.resolve().is_relative_to(TESTS_DIR.resolve()):
        raise HTTPException(403, "路径越界")
    if not test_file.exists():
        raise HTTPException(404, f"测试 {test_path} 不存在")

    if _func_lock.locked():
        try:
            await asyncio.wait_for(_func_lock.acquire(), timeout=10.0)
            _func_lock.release()
        except TimeoutError:
            raise HTTPException(429, "已有功能测试正在运行，请稍后再试") from None

    async with _func_lock:
        try:
            return await _run_single(test_path)
        except TimeoutError:
            raise HTTPException(408, f"Test timed out: {test_name}") from None
        except Exception as e:
            raise HTTPException(500, f"Failed to run test: {e!s}") from e


@router.post("/run-module/{module_id:path}", response_model=ModuleResultResponse)
async def run_module(module_id: str):
    if ".." in module_id or not re.match(r'^[\w/]*$', module_id):
        raise HTTPException(400, "无效的模块路径")

    all_tests = _discover_tests()
    module_tests = [(f, rel) for f, rel in all_tests if _module_id_from_rel(rel) == module_id]

    if not module_tests:
        raise HTTPException(404, f"模块 {module_id} 不存在或没有测试")

    if _func_lock.locked():
        try:
            await asyncio.wait_for(_func_lock.acquire(), timeout=10.0)
            _func_lock.release()
        except TimeoutError:
            raise HTTPException(429, "已有功能测试正在运行，请稍后再试") from None

    async with _func_lock:
        results = []
        for f, rel in module_tests:
            try:
                r = await _run_single(rel)
                results.append(r)
            except TimeoutError:
                results.append(TestResult(
                    test_name=rel, success=False,
                    output="TIMEOUT (120s)", exit_code=-1,
                ))
            except Exception as e:
                results.append(TestResult(
                    test_name=rel, success=False,
                    output=str(e), exit_code=-1,
                ))

    passed = sum(1 for r in results if r.success)
    skipped = sum(r.cases_skipped for r in results)
    return ModuleResult(
        module_id=module_id,
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        skipped=skipped,
        results=results,
    )


@router.post("/run-all", response_model=ModuleResultResponse)
async def run_all():
    if _func_lock.locked():
        try:
            await asyncio.wait_for(_func_lock.acquire(), timeout=10.0)
            _func_lock.release()
        except TimeoutError:
            raise HTTPException(429, "已有功能测试正在运行，请稍后再试") from None

    all_tests = _discover_tests()

    async with _func_lock:
        results = []
        for f, rel in all_tests:
            try:
                r = await _run_single(rel)
                results.append(r)
            except TimeoutError:
                results.append(TestResult(
                    test_name=rel, success=False,
                    output="TIMEOUT (120s)", exit_code=-1,
                ))
            except Exception as e:
                results.append(TestResult(
                    test_name=rel, success=False,
                    output=str(e), exit_code=-1,
                ))

    passed = sum(1 for r in results if r.success)
    skipped = sum(r.cases_skipped for r in results)
    return ModuleResult(
        module_id="",
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        skipped=skipped,
        results=results,
    )


INTERACTIVE_DIR = TESTS_DIR / "interactive"

_INTERACTIVE_MODULE_LABELS: dict[str, str] = {
    "interactive/personality": "NPC 个性",
    "interactive/coherence": "对话连贯",
    "interactive/knowledge": "世界观知识",
    "interactive/emotional": "情感响应",
}

_INTERACTIVE_ICONS: dict[str, str] = {
    "interactive/personality": "🎭",
    "interactive/coherence": "🔗",
    "interactive/knowledge": "🌍",
    "interactive/emotional": "💖",
}


class InteractiveTestInfo(BaseModel):
    name: str
    description: str
    module_id: str


class InteractiveModuleInfo(BaseModel):
    id: str
    label: str
    icon: str
    count: int
    tests: list[InteractiveTestInfo]


class InteractiveTestResult(BaseModel):
    test_name: str
    success: bool
    output: str
    elapsed: float = 0.0
    npc_reply: str = ""
    favor_delta: int = 0
    coin_delta: int = 0
    dialogue_log: list[dict] = []


class InteractiveModuleResult(BaseModel):
    module_id: str
    total: int
    passed: int
    failed: int
    results: list[InteractiveTestResult]


def _discover_interactive_tests() -> list[tuple[Path, str]]:
    if not INTERACTIVE_DIR.exists():
        return []
    results = []
    for f in sorted(INTERACTIVE_DIR.rglob("test_*.py")):
        rel = str(f.relative_to(TESTS_DIR)).replace("\\", "/")
        results.append((f, rel))
    return results


def _interactive_module_id(rel: str) -> str:
    parts = rel.split("/")
    if len(parts) >= 2:
        return "/".join(parts[:-1])
    return "interactive"


@router.get("/interactive/modules", response_model=InteractiveModulesResponse)
async def list_interactive_modules():
    all_tests = _discover_interactive_tests()
    module_map: dict[str, list[InteractiveTestInfo]] = {}

    for f, rel in all_tests:
        mid = _interactive_module_id(rel)
        if mid not in module_map:
            module_map[mid] = []
        stem = f.stem.replace("test_", "").replace("_", " ").title()
        module_map[mid].append(InteractiveTestInfo(
            name=rel,
            description=stem,
            module_id=mid,
        ))

    modules = []
    for mid in sorted(module_map.keys()):
        label = _INTERACTIVE_MODULE_LABELS.get(mid, mid.replace("/", " · ").title())
        icon = _INTERACTIVE_ICONS.get(mid, "🧪")
        modules.append(InteractiveModuleInfo(
            id=mid,
            label=label,
            icon=icon,
            count=len(module_map[mid]),
            tests=module_map[mid],
        ))

    return {"count": len(all_tests), "modules": modules}


async def _run_interactive_single(test_path: str) -> InteractiveTestResult:
    test_file = TESTS_DIR / test_path
    if not test_file.exists():
        return InteractiveTestResult(
            test_name=test_path, success=False,
            output=f"测试文件不存在: {test_path}",
        )

    _run_id = f"_itest_{test_path.replace('/', '_').replace('.', '_')}_{int(time.time()*1000)}"

    def _run_sync() -> InteractiveTestResult:
        t0 = time.time()
        try:
            spec = importlib.util.spec_from_file_location(_run_id, str(test_file))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            test_class = None
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if isinstance(attr, type) and attr_name.startswith("Test") and issubclass(attr, unittest.TestCase):
                    test_class = attr
                    break

            if not test_class:
                return InteractiveTestResult(
                    test_name=test_path, success=False,
                    output="未找到测试类",
                    elapsed=round(time.time() - t0, 1),
                )

            suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
            result = unittest.TestResult()
            suite.run(result)

            elapsed = round(time.time() - t0, 1)
            output_lines = []
            if result.errors:
                for test, tb in result.errors:
                    output_lines.append(f"ERROR: {test}\n{tb}")
            if result.failures:
                for test, tb in result.failures:
                    output_lines.append(f"FAIL: {test}\n{tb}")
            if result.skipped:
                for test, reason in result.skipped:
                    output_lines.append(f"SKIP: {test} ({reason})")

            output = "\n".join(output_lines) if output_lines else f"Ran {result.testsRun} tests OK"

            from tests.interactive.conftest import InteractiveClient as _IC
            dialogue_log = _IC.get_dialogue_log()

            dialogue_summary = ""
            for entry in dialogue_log:
                npc_name = entry.get("npc_name", entry.get("npc", "?"))
                player_msg = entry.get("player", "")
                reply = entry.get("reply", "")
                fav = entry.get("favor_delta", 0)
                coin = entry.get("coin_delta", 0)
                dialogue_summary += f"\n【{npc_name}】你：{player_msg}\n"
                dialogue_summary += f"【{npc_name}】{reply}\n"
                if fav != 0 or coin != 0:
                    changes = []
                    if fav != 0:
                        changes.append(f"好感{'+'if fav>0 else ''}{fav}")
                    if coin != 0:
                        changes.append(f"金钱{'+'if coin>0 else ''}{coin}")
                    dialogue_summary += f"  → {', '.join(changes)}\n"

            full_output = output
            if dialogue_summary:
                full_output = "━━━ 对话记录 ━━━" + dialogue_summary + "\n━━━ 测试结果 ━━━\n" + output

            return InteractiveTestResult(
                test_name=test_path,
                success=result.wasSuccessful(),
                output=full_output,
                elapsed=elapsed,
                dialogue_log=dialogue_log,
            )
        except Exception:
            return InteractiveTestResult(
                test_name=test_path, success=False,
                output=traceback.format_exc(),
                elapsed=round(time.time() - t0, 1),
            )

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run_sync)


@router.post("/interactive/reset-circuit-breaker", response_model=ResetCircuitBreakerResponse)
async def reset_circuit_breaker():
    from backend.llm.circuit_breaker import get_circuit_breaker
    cb = get_circuit_breaker()
    await cb.reset()
    return {"status": "ok", "state": cb.stats["state"]}


@router.post("/interactive/run/{test_path:path}", response_model=InteractiveTestResultResponse)
async def run_interactive_test(test_path: str):
    if ".." in test_path or not test_path.startswith("interactive/"):
        raise HTTPException(400, "无效的交互测试路径")
    test_file = TESTS_DIR / test_path
    if not test_file.resolve().is_relative_to(TESTS_DIR.resolve()):
        raise HTTPException(403, "路径越界")
    if not test_file.exists():
        raise HTTPException(404, f"测试 {test_path} 不存在")

    if _interactive_lock.locked():
        try:
            await asyncio.wait_for(_interactive_lock.acquire(), timeout=10.0)
            _interactive_lock.release()
        except TimeoutError:
            raise HTTPException(429, "已有交互测试正在运行，请稍后再试") from None

    async with _interactive_lock:
        return await _run_interactive_single(test_path)


@router.get("/interactive/stream/{test_path:path}")
async def stream_interactive_test(test_path: str):
    if ".." in test_path or not test_path.startswith("interactive/"):
        raise HTTPException(400, "无效的交互测试路径")
    test_file = TESTS_DIR / test_path
    if not test_file.resolve().is_relative_to(TESTS_DIR.resolve()):
        raise HTTPException(403, "路径越界")
    if not test_file.exists():
        raise HTTPException(404, f"测试 {test_path} 不存在")

    if _interactive_lock.locked():
        try:
            await asyncio.wait_for(_interactive_lock.acquire(), timeout=10.0)
            _interactive_lock.release()
        except TimeoutError:
            raise HTTPException(429, "已有交互测试正在运行，请稍后再试") from None

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def _on_entry(entry: dict):
        with contextlib.suppress(Exception):
            loop.call_soon_threadsafe(queue.put_nowait, entry)

    async def _run_and_queue():
        from tests.interactive.conftest import InteractiveClient as _IC
        _IC._on_dialogue = _on_entry
        try:
            async with _interactive_lock:
                result = await _run_interactive_single(test_path)
            await queue.put({"__done__": True, "result": result.model_dump()})
        except Exception:
            await queue.put({"__done__": True, "result": {
                "test_name": test_path, "success": False,
                "output": traceback.format_exc(), "elapsed": 0.0,
                "dialogue_log": [],
            }})
        finally:
            _IC._on_dialogue = None

    async def _event_stream():
        task = asyncio.create_task(_run_and_queue())
        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=120.0)
                except TimeoutError:
                    yield f"data: {__import__('json').dumps({'__error__': '超时'})}\n\n"
                    break

                if isinstance(item, dict) and item.get("__done__"):
                    result = item["result"]
                    yield f"data: {__import__('json').dumps(result)}\n\n"
                    break
                else:
                    yield f"data: {__import__('json').dumps(item)}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


@router.post("/interactive/run-module/{module_id:path}", response_model=InteractiveModuleResultResponse)
async def run_interactive_module(module_id: str):
    if ".." in module_id or not module_id.startswith("interactive"):
        raise HTTPException(400, "无效的交互测试模块路径")

    all_tests = _discover_interactive_tests()
    module_tests = [(f, rel) for f, rel in all_tests if _interactive_module_id(rel) == module_id]

    if not module_tests:
        raise HTTPException(404, f"交互测试模块 {module_id} 不存在或没有测试")

    if _interactive_lock.locked():
        try:
            await asyncio.wait_for(_interactive_lock.acquire(), timeout=10.0)
            _interactive_lock.release()
        except TimeoutError:
            raise HTTPException(429, "已有交互测试正在运行，请稍后再试") from None

    async with _interactive_lock:
        results = []
        for f, rel in module_tests:
            r = await _run_interactive_single(rel)
            results.append(r)

    passed = sum(1 for r in results if r.success)
    return InteractiveModuleResult(
        module_id=module_id,
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        results=results,
    )


@router.post("/interactive/run-all", response_model=InteractiveModuleResultResponse)
async def run_interactive_all():
    if _interactive_lock.locked():
        try:
            await asyncio.wait_for(_interactive_lock.acquire(), timeout=10.0)
            _interactive_lock.release()
        except TimeoutError:
            raise HTTPException(429, "已有交互测试正在运行，请稍后再试") from None

    all_tests = _discover_interactive_tests()

    async with _interactive_lock:
        results = []
        for f, rel in all_tests:
            r = await _run_interactive_single(rel)
            results.append(r)

    passed = sum(1 for r in results if r.success)
    return InteractiveModuleResult(
        module_id="interactive",
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        results=results,
    )
