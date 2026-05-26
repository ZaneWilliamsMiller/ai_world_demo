from __future__ import annotations
from typing import Any
from backend.data.factions import FACTIONS
from backend.models.player import PlayerState
from backend.systems.time_weather import shichen_name

def clamp_rep_delta(d: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for k in FACTIONS.keys():
        if k in d:
            v = int(d[k])
            if v > 2:
                v = 2
            if v < -2:
                v = -2
            if v != 0:
                out[k] = v
    return out

def apply_rep_delta(p: PlayerState, d: dict[str, int] | None) -> None:
    if not d:
        return
    for k, v in clamp_rep_delta(d).items():
        cur = int(p.reputation.get(k, 0))
        nxt = max(-100, min(100, cur + v))
        p.reputation[k] = nxt

def push_event(p: PlayerState, text: str, *, scope: str = "near", actor: str | None = None) -> None:
    """把一条 LLM 给出的关键事件落到全局事件流，供其他 NPC 引用。"""
    s = (text or "").strip().replace("\n", " ")
    if not s:
        return
    if len(s) > 80:
        s = s[:80] + "…"
    p.events.append({
        "day": int(p.world_day),
        "shichen": shichen_name(p.world_shichen),
        "scope": scope,  # "near"=同图/相关；"far"=他处风闻
        "actor": actor or "",
        "text": s,
    })
    if len(p.events) > 24:
        p.events = p.events[-24:]
