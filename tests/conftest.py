"""pytest 配置 — 让 `python -m pytest tests/` 自动发现测试文件

所有测试通过 BASE_URL 统一读取后端地址，也可通过环境变量 TESTS_BASE_URL 覆盖。
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 统一后端测试地址（默认 8765，可通过环境变量覆盖）
BASE_URL = os.environ.get("TESTS_BASE_URL", "http://127.0.0.1:8765")
