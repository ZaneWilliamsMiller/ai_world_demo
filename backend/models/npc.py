from typing import Any

def format_npc_character_sheet(npc: dict[str, Any]) -> str:
    ch = npc.get("character")
    if not ch or not isinstance(ch, dict):
        return ""
    lines = ["【人物底稿 · 对戏分层】"]
    for label, val in ch.items():
        if isinstance(val, str) and val.strip():
            lines.append(f"· {label}：{val.strip()}")
    return "\n".join(lines) + "\n"
