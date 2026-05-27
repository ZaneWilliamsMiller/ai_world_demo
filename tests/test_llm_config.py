#!/usr/bin/env python3
"""测试 LLM API 配置"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import settings
from backend.llm_client import chat_completion


async def test_llm_config():
    """测试 LLM API 配置"""
    print("=== LLM 配置测试 ===")
    print(f"Base URL: {settings.llm_base_url}")
    print(f"Model: {settings.llm_model}")
    print(f"Prompt cache enabled: {settings.llm_enable_prompt_cache}")
    print()
    
    try:
        print("正在测试 LLM API 连接...")
        messages = [
            {"role": "system", "content": "你是一个助手，请用简洁的语言回答。"},
            {"role": "user", "content": "请说一句话介绍你自己。"}
        ]
        result = await chat_completion(messages, temperature=0.7, max_tokens=200)
        print("✓ LLM API 调用成功！")
        print(f"响应: {result}")
        print()
        print("=== 配置测试通过 ===")
        return True
    except Exception as e:
        print(f"✗ LLM API 调用失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_llm_config())
    sys.exit(0 if success else 1)
