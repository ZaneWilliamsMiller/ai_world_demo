from __future__ import annotations

from backend.data.factions import FACTIONS
from backend.models.player import PlayerState
from backend.systems.constants import MAX_EVENT_LEN, MAX_EVENTS, MAX_REP_DELTA, MAX_REPUTATION
from backend.systems.time_weather import shichen_name


def clamp_rep_delta(d: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for k in FACTIONS:
        if k in d:
            v = int(d[k])
            v = min(v, MAX_REP_DELTA)
            v = max(v, -MAX_REP_DELTA)
            if v != 0:
                out[k] = v
    return out

def apply_rep_delta(p: PlayerState, d: dict[str, int] | None) -> None:
    if not d:
        return
    for k, v in clamp_rep_delta(d).items():
        cur = int(p.reputation.get(k, 0))
        nxt = max(-MAX_REPUTATION, min(MAX_REPUTATION, cur + v))
        p.reputation[k] = nxt

def push_event(p: PlayerState, text: str, *, scope: str = "near", actor: str | None = None) -> None:
    s = (text or "").strip().replace("\n", " ")
    if not s:
        return
    if len(s) > MAX_EVENT_LEN:
        s = s[:MAX_EVENT_LEN] + "…"
    p.events.append({
        "day": int(p.world_day),
        "shichen": shichen_name(p.world_shichen),
        "scope": scope,
        "actor": actor or "",
        "text": s,
    })
    if len(p.events) > MAX_EVENTS:
        p.events = p.events[-MAX_EVENTS:]
