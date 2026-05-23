"""pytest 配置 — 让 `python -m pytest tests/` 自动发现测试文件"""
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)