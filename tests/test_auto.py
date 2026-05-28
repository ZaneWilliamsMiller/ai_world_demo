#!/usr/bin/env python3
"""
Living Paper 自动化测试脚本
测试后端 API、LLM 交互、Web/Godot 前端连通性
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import httpx
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8765")
REPORT_DIR = PROJECT_ROOT / "tools" / "test_reports"

API_KEY = os.environ.get("LLM_API_KEY", "")
if not API_KEY:
    print("⚠️ 请设置环境变量 LLM_API_KEY")
    sys.exit(1)

# ── 测试结果收集 ──
results: list[dict] = []


def log_test(name: str, passed: bool, detail: str = "", duration: float = 0) -> None:
    entry = {
        "name": name,
        "passed": passed,
        "detail": detail,
        "duration_ms": round(duration * 1000, 1),
        "timestamp": datetime.now().isoformat(),
    }
    results.append(entry)
    status = "[PASS]" if passed else "[FAIL]"
    dur = f" ({duration*1000:.0f}ms)" if duration else ""
    print(f"  {status} {name}{dur}")
    if detail and not passed:
        print(f"         ↳ {detail}")


async def test_backend_health() -> bool:
    """测试后端健康检查"""
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(f"{BACKEND_URL}/api/health")
            data = r.json()
            ok = r.status_code == 200 and data.get("status") == "ok"
            log_test("后端健康检查", ok, f"status={r.status_code} model={data.get('model','?')}", time.time() - t0)
            return ok
    except Exception as e:
        log_test("后端健康检查", False, str(e), time.time() - t0)
        return False


async def test_llm_direct() -> bool:
    """直接测试 LLM API（通过 backend.config 读取密钥）"""
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={
                    "model": settings.llm_model,
                    "messages": [{"role": "user", "content": "请用一句话介绍江湖"}],
                    "max_tokens": 100,
                },
            )
            ok = r.status_code == 200
            detail = ""
            if ok:
                data = r.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                detail = f"response_len={len(content)}"
            else:
                detail = r.text[:200]
            log_test(f"LLM 直连 ({settings.llm_model})", ok, detail, time.time() - t0)
            return ok
    except Exception as e:
        log_test(f"LLM 直连 ({settings.llm_model})", False, str(e), time.time() - t0)
        return False


async def test_llm_models_list() -> bool:
    """测试 LLM 模型列表（通过 backend.config 读取密钥）"""
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(
                f"{settings.llm_base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {API_KEY}"},
            )
            ok = r.status_code == 200
            model_ids = []
            if ok:
                data = r.json()
                model_ids = [m["id"] for m in data.get("data", [])]
                ok = settings.llm_model in model_ids
            log_test("LLM 模型列表", ok, f"models={len(model_ids)}, target={settings.llm_model} found={settings.llm_model in model_ids}", time.time() - t0)
            return ok
    except Exception as e:
        log_test("LLM 模型列表", False, str(e), time.time() - t0)
        return False


async def test_hello_endpoint() -> bool:
    """测试角色创建端点"""
    t0 = time.time()
    try:
        pid = f"auto_test_{int(time.time())}"
        async with httpx.AsyncClient(timeout=120.0) as c:
            r = await c.post(
                f"{BACKEND_URL}/api/hello",
                json={"player_id": pid, "display_name": "测试侠客", "gender": "男", "permadeath": False},
            )
            ok = r.status_code == 200
            detail = ""
            if ok:
                data = r.json()
                p = data.get("player", {})
                detail = f"map={p.get('map_id')} pos=({p.get('px')},{p.get('py')}) npcs={len(data.get('npcs_here',[]))} maps={len(data.get('maps',{}))}"
            else:
                detail = r.text[:200]
            log_test("角色创建 (/api/hello)", ok, detail, time.time() - t0)
            return ok
    except Exception as e:
        log_test("角色创建 (/api/hello)", False, str(e), time.time() - t0)
        return False


async def test_npc_talk() -> bool:
    """测试 NPC 对话（完整 LLM 交互链路）"""
    t0 = time.time()
    try:
        pid = f"talk_test_{int(time.time())}"
        async with httpx.AsyncClient(timeout=180.0) as c:
            # 先创建角色
            r = await c.post(
                f"{BACKEND_URL}/api/hello",
                json={"player_id": pid, "display_name": "对话测试者", "gender": "女", "permadeath": False},
            )
            if r.status_code != 200:
                log_test("NPC 对话", False, "hello 失败", time.time() - t0)
                return False

            data = r.json()
            npcs = data.get("npcs_here", [])
            if not npcs:
                log_test("NPC 对话", False, "无可用 NPC", time.time() - t0)
                return False

            npc_id = npcs[0]["id"]

            # 发起对话
            r2 = await c.post(
                f"{BACKEND_URL}/api/npc/talk",
                json={"player_id": pid, "npc_id": npc_id, "message": "你好，有什么消息吗？"},
            )
            ok = r2.status_code == 200
            detail = ""
            if ok:
                d2 = r2.json()
                vt = d2.get("visible_text", "")
                detail = f"npc={npc_id} reply_len={len(vt)} fallback={d2.get('llm_fallback','N/A')}"
            else:
                detail = r2.text[:200]
            log_test("NPC 对话 (LLM 链路)", ok, detail, time.time() - t0)
            return ok
    except Exception as e:
        log_test("NPC 对话 (LLM 链路)", False, str(e), time.time() - t0)
        return False


async def test_move() -> bool:
    """测试移动端点"""
    t0 = time.time()
    try:
        pid = f"move_test_{int(time.time())}"
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(
                f"{BACKEND_URL}/api/hello",
                json={"player_id": pid, "display_name": "移动测试", "gender": "男", "permadeath": False},
            )
            if r.status_code != 200:
                log_test("移动", False, "hello 失败", time.time() - t0)
                return False

            data = r.json()
            p = data.get("player", {})
            cur_x, cur_y = p.get("px", 0), p.get("py", 0)

            # 尝试移动到相邻格
            r2 = await c.post(
                f"{BACKEND_URL}/api/move",
                json={"player_id": pid, "to_x": cur_x + 1, "to_y": cur_y},
            )
            ok = r2.status_code == 200
            detail = ""
            if ok:
                d2 = r2.json()
                path = d2.get("path", [])
                detail = f"from=({cur_x},{cur_y}) path_len={len(path)}"
            else:
                detail = r2.text[:200]
            log_test("角色移动 (/api/move)", ok, detail, time.time() - t0)
            return ok
    except Exception as e:
        log_test("角色移动 (/api/move)", False, str(e), time.time() - t0)
        return False


async def test_save_load() -> bool:
    """测试存档/读档"""
    t0 = time.time()
    try:
        pid = f"save_test_{int(time.time())}"
        async with httpx.AsyncClient(timeout=30.0) as c:
            # 创建角色
            await c.post(
                f"{BACKEND_URL}/api/hello",
                json={"player_id": pid, "display_name": "存档测试", "gender": "女", "permadeath": False},
            )
            # 存档
            r1 = await c.post(f"{BACKEND_URL}/api/save", json={"player_id": pid})
            save_ok = r1.status_code == 200 and r1.json().get("ok", False)

            # 读档列表
            r2 = await c.get(f"{BACKEND_URL}/api/saves")
            saves_ok = r2.status_code == 200

            # 加载存档
            r3 = await c.post(f"{BACKEND_URL}/api/load", json={"player_id": pid})
            load_ok = r3.status_code == 200

            ok = save_ok and saves_ok and load_ok
            detail = f"save={save_ok} list={saves_ok} load={load_ok}"
            log_test("存档/读档", ok, detail, time.time() - t0)
            return ok
    except Exception as e:
        log_test("存档/读档", False, str(e), time.time() - t0)
        return False


async def test_web_static() -> bool:
    """测试 Web 静态文件服务"""
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(f"{BACKEND_URL}/")
            ok = r.status_code == 200 and "江湖行纪" in r.text
            log_test("Web 静态页面", ok, f"status={r.status_code} len={len(r.text)}", time.time() - t0)
            return ok
    except Exception as e:
        log_test("Web 静态页面", False, str(e), time.time() - t0)
        return False


async def run_all_tests() -> dict:
    """运行所有测试并生成报告"""
    print(f"\n{'='*60}")
    print(f"  Living Paper 自动化测试 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # 并行运行独立测试
    await asyncio.gather(
        test_backend_health(),
        test_llm_models_list(),
        test_web_static(),
    )

    # 顺序运行依赖测试
    await test_llm_direct()
    await test_hello_endpoint()
    await test_npc_talk()
    await test_move()
    await test_save_load()

    # 汇总
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    total_duration = sum(r["duration_ms"] for r in results)

    print(f"\n{'='*60}")
    print(f"  结果: {passed}/{total} 通过, {failed} 失败, 总耗时 {total_duration:.0f}ms")
    print(f"{'='*60}\n")

    # 生成报告
    REPORT_DIR.mkdir(exist_ok=True)
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {"total": total, "passed": passed, "failed": failed, "total_ms": total_duration},
        "results": results,
    }
    report_path = REPORT_DIR / f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  报告已保存: {report_path}")

    return report


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    report = asyncio.run(run_all_tests())
    sys.exit(0 if report["summary"]["failed"] == 0 else 1)
