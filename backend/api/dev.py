"""开发专用路由 — 功能测试与交互测试。

仅在 ENABLE_TEST_ROUTES=1 时挂载，生产环境不暴露。
"""
from __future__ import annotations

import asyncio
import importlib
import os
import re
import sys
import time
import traceback
import unittest
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.config import settings

TESTS_DIR = Path(__file__).resolve().parents[2] / "tests"
_run_lock = asyncio.Lock()


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


@router.get("/list")
async def list_tests():
    tests = []
    for f, rel in _discover_tests():
        tests.append(TestInfo(
            name=rel,
            description=_get_test_description(f),
            file_path=str(f.relative_to(TESTS_DIR.parent))
        ))
    return {"count": len(tests), "tests": tests}


@router.get("/modules")
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

    t0 = asyncio.get_event_loop().time()
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
    elapsed = round(asyncio.get_event_loop().time() - t0, 1)
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


@router.post("/run/{test_path:path}")
async def run_test(test_path: str):
    test_name = test_path.replace("/", os.sep).replace("\\", os.sep)
    if ".." in test_name or not re.match(r'^[\w/\\]+\.py$', test_name.replace(os.sep, "/")):
        raise HTTPException(400, "无效的测试路径")
    test_file = TESTS_DIR / test_name
    if not test_file.resolve().is_relative_to(TESTS_DIR.resolve()):
        raise HTTPException(403, "路径越界")
    if not test_file.exists():
        raise HTTPException(404, f"测试 {test_path} 不存在")

    if _run_lock.locked():
        raise HTTPException(429, "已有测试正在运行，请稍后再试")

    async with _run_lock:
        try:
            return await _run_single(test_path)
        except TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            raise HTTPException(408, f"Test timed out: {test_name}") from None
        except Exception as e:
            raise HTTPException(500, f"Failed to run test: {e!s}") from e


@router.post("/run-module/{module_id:path}")
async def run_module(module_id: str):
    if ".." in module_id or not re.match(r'^[\w/]*$', module_id):
        raise HTTPException(400, "无效的模块路径")

    all_tests = _discover_tests()
    module_tests = [(f, rel) for f, rel in all_tests if _module_id_from_rel(rel) == module_id]

    if not module_tests:
        raise HTTPException(404, f"模块 {module_id} 不存在或没有测试")

    if _run_lock.locked():
        raise HTTPException(429, "已有测试正在运行，请稍后再试")

    async with _run_lock:
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


@router.post("/run-all")
async def run_all():
    if _run_lock.locked():
        raise HTTPException(429, "已有测试正在运行，请稍后再试")

    all_tests = _discover_tests()

    async with _run_lock:
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


@router.get("/interactive/modules")
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

    module_rel = test_path.replace("\\", "/").replace("/", ".").replace(".py", "")
    parts = module_rel.split(".")
    if parts[-1].startswith("test_"):
        module_name = "tests." + module_rel

    t0 = time.time()
    try:
        if module_name in sys.modules:
            mod = sys.modules[module_name]
        else:
            spec = importlib.util.spec_from_file_location(module_name, str(test_file))
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
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

        return InteractiveTestResult(
            test_name=test_path,
            success=result.wasSuccessful(),
            output=output,
            elapsed=elapsed,
        )
    except Exception as e:
        return InteractiveTestResult(
            test_name=test_path, success=False,
            output=traceback.format_exc(),
            elapsed=round(time.time() - t0, 1),
        )


@router.post("/interactive/run/{test_path:path}")
async def run_interactive_test(test_path: str):
    if ".." in test_path or not test_path.startswith("interactive/"):
        raise HTTPException(400, "无效的交互测试路径")
    test_file = TESTS_DIR / test_path
    if not test_file.resolve().is_relative_to(TESTS_DIR.resolve()):
        raise HTTPException(403, "路径越界")
    if not test_file.exists():
        raise HTTPException(404, f"测试 {test_path} 不存在")

    if _run_lock.locked():
        raise HTTPException(429, "已有测试正在运行，请稍后再试")

    async with _run_lock:
        return await _run_interactive_single(test_path)


@router.post("/interactive/run-module/{module_id:path}")
async def run_interactive_module(module_id: str):
    if ".." in module_id or not module_id.startswith("interactive"):
        raise HTTPException(400, "无效的交互测试模块路径")

    all_tests = _discover_interactive_tests()
    module_tests = [(f, rel) for f, rel in all_tests if _interactive_module_id(rel) == module_id]

    if not module_tests:
        raise HTTPException(404, f"交互测试模块 {module_id} 不存在或没有测试")

    if _run_lock.locked():
        raise HTTPException(429, "已有测试正在运行，请稍后再试")

    async with _run_lock:
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


@router.post("/interactive/run-all")
async def run_interactive_all():
    if _run_lock.locked():
        raise HTTPException(429, "已有测试正在运行，请稍后再试")

    all_tests = _discover_interactive_tests()

    async with _run_lock:
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
