from typing import Any

def format_npc_character_sheet(npc: dict[str, Any]) -> str:
    ch = npc.get("character")
    if not ch or not isinstance(ch, dict):
        return ""
    lines = ["【人物底稿 · 对戏分层】"]

    # ── 声口（说话风格）优先── 这是最重要的行为指令，必须放在最显眼的位置
    voice = ch.get("声口")
    if isinstance(voice, str) and voice.strip():
        lines.append(f"★【说话风格——必须遵守】{voice.strip()}")
        lines.append("★ 你的每句台词、每个动作描写都应符合上述风格。不要跑偏。")

    for label, val in ch.items():
        if label == "声口":
            continue  # 已在上方单独处理
        if isinstance(val, str) and val.strip():
            lines.append(f"· {label}：{val.strip()}")
    return "\n".join(lines) + "\n"
