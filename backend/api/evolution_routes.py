"""世界演进 API 路由：evolution_start, evolution_cancel, evolution_result"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.api.schema import EvolutionCancelResponse, InitResponse
from backend.api.views import build_init_response
from backend.models.player import PlayerState
from backend.systems.world_evolution import WorldEvolution, get_evolution, register_evolution, unregister_evolution

router = APIRouter()

log = logging.getLogger("evolution_routes")

_PID = Field(..., min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')


class EvolutionStartBody(BaseModel):
    player_id: str = _PID
    display_name: str = Field(..., min_length=1, max_length=24)
    gender: str = Field(default="未言", pattern="^(男|女|未言)$")
    permadeath: bool = False


class EvolutionCancelBody(BaseModel):
    player_id: str = _PID


def _sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/api/evolution/stream")
async def evolution_start(body: EvolutionStartBody) -> StreamingResponse:
    from backend.session.store import room

    existing = get_evolution(body.player_id)
    if existing:
        raise HTTPException(409, "该玩家已有演进在进行中")

    p = room.players.get(body.player_id)
    if not p:
        p = PlayerState(
            player_id=body.player_id,
            display_name=body.display_name.strip()[:24],
            gender=body.gender if body.gender in ("男", "女", "未言") else "未言",
            permadeath=bool(body.permadeath),
        )
        room.players[body.player_id] = p
        room._touch(body.player_id)

    async def event_gen():
        evolution = WorldEvolution(p, body.display_name)
        register_evolution(body.player_id, evolution)
        try:
            async for event in evolution.run():
                yield _sse(event)
                if event.get("type") in ("done", "cancelled"):
                    break
        finally:
            evolution.cancel()
            unregister_evolution(body.player_id)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/api/evolution/cancel", response_model=EvolutionCancelResponse)
async def evolution_cancel(body: EvolutionCancelBody):
    evolution = get_evolution(body.player_id)
    if not evolution:
        raise HTTPException(404, "未找到进行中的世界演进")
    evolution.cancel()
    return {"ok": True}


@router.get("/api/evolution/result/{player_id}", response_model=InitResponse)
async def evolution_result(player_id: str):
    from backend.session.store import room

    p = room.players.get(player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    return build_init_response(p)
