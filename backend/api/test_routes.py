from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path as FastPath
from pydantic import BaseModel

TESTS_DIR = Path(__file__).resolve().parents[2] / "tests"
_run_lock = asyncio.Lock()


def _guard_test_routes() -> None:
    if os.environ.get("ENABLE_TEST_ROUTES", "0") != "1":
        raise HTTPException(403, "测试路由已禁用。设置环境变量 ENABLE_TEST_ROUTES=1 以启用。")


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
    exit_code: Optional[int] = None


def _get_test_description(file_path: Path) -> str:
    """从测试文件的第一行docstring获取描述"""
    try:
        content = file_path.read_text(encoding="utf-8")
        first_line = content.split("\n")[0].strip()
        if first_line.startswith('"""') or first_line.startswith("'''"):
            return first_line.strip('"\'').strip()
        return file_path.stem.replace("_", " ").replace("test ", "").title()
    except Exception:
        return file_path.stem


@router.get("/list")
async def list_tests():
    """列出所有可用的测试脚本"""
    tests = []
    if TESTS_DIR.exists():
        for f in sorted(TESTS_DIR.glob("test_*.py")):
            tests.append(TestInfo(
                name=f.stem,
                description=_get_test_description(f),
                file_path=str(f.relative_to(TESTS_DIR.parent))
            ))
    return {"count": len(tests), "tests": tests}


@router.post("/run/{test_name}")
async def run_test(test_name: str = FastPath(..., min_length=1, max_length=64, pattern=r'^[a-zA-Z_][a-zA-Z0-9_]*$')):
    """执行指定的测试脚本"""
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', test_name):
        raise HTTPException(400, "无效的测试名称")
    test_file = TESTS_DIR / f"{test_name}.py"
    if not test_file.resolve().is_relative_to(TESTS_DIR.resolve()):
        raise HTTPException(403, "路径越界")
    if not test_file.exists():
        raise HTTPException(404, f"测试 {test_name} 不存在")

    if _run_lock.locked():
        raise HTTPException(429, "已有测试正在运行，请稍后再试")

    async with _run_lock:
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(test_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(test_file.parent.parent)
            )

            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)

            output = stdout.decode("utf-8", errors="replace")

            return TestResult(
                test_name=test_name,
                success=(proc.returncode == 0),
                output=output,
                exit_code=proc.returncode
            )

        except asyncio.TimeoutError:
            raise HTTPException(408, f"Test timed out: {test_name}")
        except Exception as e:
            raise HTTPException(500, f"Failed to run test: {str(e)}")


# DEPRECATED: GET-based test execution removed for security (CSRF risk).
# Use POST /api/tests/run/{test_name} instead.
