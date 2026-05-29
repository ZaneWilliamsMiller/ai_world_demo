"""开发专用路由 — 测试脚本列表与执行。

仅在 ENABLE_TEST_ROUTES=1 时挂载，生产环境不暴露。
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
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
    "integration": "集成测试",
    "unit/agents": "Agent 模块",
    "unit/api": "API 路由",
    "unit/llm": "LLM 模块",
    "unit/memory": "记忆模块",
    "unit/services": "服务层",
    "unit/session": "会话存储",
    "unit/systems": "游戏系统",
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

    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
    output = stdout.decode("utf-8", errors="replace")

    return TestResult(
        test_name=test_path,
        success=(proc.returncode == 0),
        output=output,
        exit_code=proc.returncode,
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
    return ModuleResult(
        module_id=module_id,
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
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
    return ModuleResult(
        module_id="",
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        results=results,
    )
