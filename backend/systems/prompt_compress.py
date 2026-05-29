"""
Prompt 压缩策略（2026-05-26 新增）

核心思路：
  1. 当 NPC 对话历史超过 COMPRESS_THRESHOLD 轮时，将早期对话压缩为摘要
  2. 摘要保留：话题演进线索、情感变化、关键承诺/决策
  3. 原始终位于最近 K 轮保留，确保短对话的"接着问"语义不被破坏
  4. 压缩通过 LLM 完成（一次压缩多轮，而非逐轮压缩）
"""
from __future__ import annotations
import logging
from typing import Any

from backend.llm_client import chat_completion
from backend.llm_params import COMPRESS_TEMPERATURE, COMPRESS_MAX_TOKENS

log = logging.getLogger("compress")

# 超过此轮数触发压缩
COMPRESS_THRESHOLD = 14
# 压缩后保留最近 K 轮原始对话（不会压缩这 K 轮）
KEEP_RECENT = 6
# 每次压缩的最早 N 轮（压缩窗口）
COMPRESS_WINDOW = 8


async def compress_conversation_history(
    hist: list[dict[str, Any]],
    npc_name: str = "",
) -> list[dict[str, Any]]:
    """压缩对话历史：将早期轮次摘要化，保留最近轮次原文。

    输入 hist: list of {"user": "...", "assistant": "...", ...}
    输出：压缩后的历史（长度 ≤ COMPRESS_THRESHOLD），格式与输入一致

    非破坏性：如果 hist 不大则不修改。
    """
    n = len(hist)
    if n <= COMPRESS_THRESHOLD:
        return hist

    compress_end = n - KEEP_RECENT
    if compress_end <= 0:
        return hist

    to_compress = hist[:compress_end]
    to_keep = hist[compress_end:]

    compress_window = to_compress[-COMPRESS_WINDOW:] if len(to_compress) > COMPRESS_WINDOW else to_compress

    old_span = None
    if len(to_compress) > COMPRESS_WINDOW:
        old_span = to_compress[:-COMPRESS_WINDOW]

    dialog_text = ""
    for turn in compress_window:
        user_msg = turn.get("user", "")
        asst_msg = turn.get("assistant", "")
        dialog_text += f"玩家: {user_msg[:120]}\n{npc_name or 'NPC'}: {asst_msg[:120]}\n"

    try:
        summary = await _llm_summarize(dialog_text, npc_name)
    except Exception as e:
        log.warning("compress_history failed: %s; keeping uncompressed", e)
        return hist

    compressed: list[dict[str, Any]] = []

    if old_span:
        old_count = len(old_span)
        compressed.append({
            "user": f"[系统:此前还有{old_count}轮对话，从略。]",
            "assistant": "(知晓)",
        })

    compressed.append({
        "user": f"[系统:此前{len(compress_window)}轮对话概要——{summary}]",
        "assistant": "(知晓)",
    })

    compressed.extend(to_keep)

    return compressed


async def _llm_summarize(dialog_text: str, npc_name: str) -> str:
    """调用 LLM 将对话压缩为 2-3 句摘要。"""
    messages = [
        {
            "role": "system",
            "content": (
                "你是对话摘要器。将以下对话压缩为 2-3 句中文摘要，保留：\n"
                "1. 话题的变化路线\n"
                "2. 金钱/物品的往来（如有）\n"
                "3. 情感与态度变化\n"
                "4. 重要承诺或决策\n"
                "只输出摘要，不要添加引号或其他格式。"
            ),
        },
        {
            "role": "user",
            "content": f"请摘要以下{npc_name}的对话：\n{dialog_text}",
        },
    ]
    raw = await chat_completion(messages, temperature=COMPRESS_TEMPERATURE, max_tokens=COMPRESS_MAX_TOKENS)
    summary = raw.strip()
    # 清理可能出现的引号
    for ch in ('"', '"', '"', "'", "'", "'"):
        summary = summary.strip(ch)
    return summary[:250]