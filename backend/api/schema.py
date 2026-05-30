"""API 响应模型定义——所有端点的返回值类型契约。

FastAPI 的 response_model 参数引用此文件中的模型，
自动生成 OpenAPI 文档并在运行时校验返回值。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── 基础组件模型 ──────────────────────────────────────────


class NpcBrief(BaseModel):
    id: str
    name: str


class NpcCatalogEntry(BaseModel):
    id: str
    name: str
    map: str = Field(alias="map")
    x: int
    y: int

    model_config = {"populate_by_name": True}


class DangerSense(BaseModel):
    alert: str | None = None
    scan: str | None = None


class TrapStatePublic(BaseModel):
    active: bool = False
    reason: str | None = None
    attempts: int = 0
    type: str | None = None


class MoveDelta(BaseModel):
    vigor: int = 0
    spirit: int = 0


class RestDelta(BaseModel):
    vigor: int = 0
    spirit: int = 0
    sleep_debt: int = 0


class TalkDelta(BaseModel):
    coins: int = 0
    items_gain: list[str] = Field(default_factory=list)
    items_lose: list[str] = Field(default_factory=list)
    rep: dict[str, int] = Field(default_factory=dict)
    favor: int = 0
    events: list[Any] = Field(default_factory=list)
    vigor: int = 0
    spirit: int = 0


class MapData(BaseModel):
    name: str
    rows: list[str] = Field(default_factory=list)
    portals: list[Any] = Field(default_factory=list)


class PlayerPublic(BaseModel):
    map_id: str = "world"
    px: int = 0
    py: int = 0
    coins: int = 0
    gender: str = "未言"
    permadeath: bool = False
    dead: bool = False
    death_reason: str | None = None
    ended: bool = False
    ending_label: str | None = None
    move_locked: bool = False
    move_lock_npc_id: str | None = None
    trap_reason: str | None = None
    trap_attempts: int = 0
    trap_type: str | None = None
    enslaved: bool = False
    enslaved_reason: str | None = None
    vigor: int = 0
    vigor_max: int = 100
    spirit: int = 0
    spirit_max: int = 100
    sleep_debt: int = 0
    unconscious_ticks: int = 0
    rescue_needed: bool = False
    life_burn_ticks: int = 0
    life_burn_max: int = 0
    world_day: int = 1
    world_shichen_idx: int = 0
    world_shichen: str = "子时"
    world_phase: str = "夜"
    world_is_night: bool = True
    weather: str = "晴"
    inventory: dict[str, int] = Field(default_factory=dict)
    reputation: dict[str, int] = Field(default_factory=dict)
    npc_states: dict[str, str] = Field(default_factory=dict)
    bounties: list[Any] = Field(default_factory=list)
    active_bounty: Any = None
    completed_bounties: list[Any] = Field(default_factory=list)
    flags: dict[str, int] = Field(default_factory=dict)
    favor: dict[str, int] = Field(default_factory=dict)


class ForcedEncounter(BaseModel):
    npc_id: str
    user_line: str = ""
    blurb: str = ""


class GameEvent(BaseModel):
    day: int | None = None
    shichen: str | None = None
    text: str = ""
    scope: str | None = None
    actor: str | None = None

    model_config = {"extra": "allow"}


class AgentMindItem(BaseModel):
    model_config = {"extra": "allow"}


class ActStepResult(BaseModel):
    action: str
    description: str
    success: bool


class AdminPlayerBrief(BaseModel):
    player_id: str
    display_name: str
    map_id: str
    px: int
    py: int
    dead: bool
    ended: bool


class AdminNpcStateEntry(BaseModel):
    pos: Any = None
    state: str = "idle"
    plan_summary: str = ""

    model_config = {"extra": "allow"}


# ── 端点响应模型 ──────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    llm_configured: str = "false"
    shutdown_configured: str = "false"
    world: str = ""


class InitResponse(BaseModel):
    player_id: str
    display_name: str
    world_name: str
    intro: str
    maps: dict[str, MapData]
    npc_catalog: list[Any]
    player: PlayerPublic
    npcs_here: list[NpcBrief]
    danger_sense: DangerSense
    flags: dict[str, int] = Field(default_factory=dict)
    ended: bool = False
    ending_label: str | None = None
    favor: dict[str, int] = Field(default_factory=dict)
    rumors: list[Any] = Field(default_factory=list)
    npc_labels: dict[str, str] = Field(default_factory=dict)
    ambush_markers: list[Any] = Field(default_factory=list)
    factions: dict[str, str] = Field(default_factory=dict)
    map_locations: dict[str, dict[str, list[int]]] = Field(default_factory=dict)
    events: list[Any] = Field(default_factory=list)


class MoveResponse(BaseModel):
    player: PlayerPublic
    npcs_here: list[NpcBrief]
    danger_sense: DangerSense
    path_map_id: str
    path: list[list[int]]
    forced_encounter: ForcedEncounter | None = None
    trap_state: TrapStatePublic
    delta: MoveDelta
    injuries: list[str] = Field(default_factory=list)
    atmosphere: str = ""
    events: list[Any] = Field(default_factory=list)
    npc_catalog: list[Any] = Field(default_factory=list)
    map_locations: dict[str, dict[str, list[int]]] = Field(default_factory=dict)
    respawn_msg: str | None = None


class StateResponse(BaseModel):
    display_name: str = ""
    player: PlayerPublic
    npcs_here: list[NpcBrief]
    danger_sense: DangerSense
    flags: dict[str, int] = Field(default_factory=dict)
    ended: bool = False
    ending_label: str | None = None
    favor: dict[str, int] = Field(default_factory=dict)
    rumors: list[Any] = Field(default_factory=list)
    atmosphere: str = ""
    events: list[Any] = Field(default_factory=list)
    factions: dict[str, str] = Field(default_factory=dict)
    npc_catalog: list[Any] = Field(default_factory=list)
    map_locations: dict[str, dict[str, list[int]]] = Field(default_factory=dict)


class JournalNpcHistory(BaseModel):
    npc_id: str
    npc_name: str
    turns: list[Any] = Field(default_factory=list)


class JournalResponse(BaseModel):
    history: list[JournalNpcHistory]
    events: list[Any] = Field(default_factory=list)
    rumors: list[Any] = Field(default_factory=list)


class ItemUseResponse(BaseModel):
    success: bool
    note: str = ""
    delta: RestDelta | None = None
    item_consumed: str | None = None
    player: PlayerPublic

    model_config = {"extra": "allow"}


class RestResponse(BaseModel):
    ok: bool
    reason: str = ""
    delta: RestDelta | None = None
    ticks_passed: int = 0
    note: str = ""
    player: PlayerPublic
    npcs_here: list[NpcBrief]
    danger_sense: DangerSense
    atmosphere: str = ""
    events: list[Any] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class WaitResponse(BaseModel):
    ok: bool = True
    note: str = ""
    ticks_passed: int = 1
    unconscious: bool = False
    player: PlayerPublic
    npcs_here: list[NpcBrief]
    danger_sense: DangerSense
    atmosphere: str = ""
    events: list[Any] = Field(default_factory=list)


class TalkResponse(BaseModel):
    visible_text: str = ""
    reply: str = ""
    flags: dict[str, int] = Field(default_factory=dict)
    favor: dict[str, int] = Field(default_factory=dict)
    rumors: list[Any] = Field(default_factory=list)
    events: list[Any] = Field(default_factory=list)
    player: PlayerPublic
    npcs_here: list[NpcBrief]
    atmosphere: str = ""
    delta: TalkDelta
    trap_resolution: Any = None
    server_ms: int = 0
    llm_fallback: bool | None = None

    model_config = {"extra": "allow"}


class AgentMindResponse(BaseModel):
    npc_id: str
    npc_name: str
    items: list[Any] = Field(default_factory=list)
    importance_since_reflect: float = 0.0
    plan_day: int | None = None
    plan_summary: str = ""
    plan_by_shichen: dict[str, Any] = Field(default_factory=dict)
    affect_valence: float = 0.0
    affect_arousal: float = 5.0
    affect_mood: str = "平静"
    affect_cause: str = ""


class AgentReflectResponse(BaseModel):
    added: list[Any] = Field(default_factory=list)
    count: int = 0
    player: PlayerPublic


class AgentPlanResponse(BaseModel):
    ok: bool
    plan_day: int | None = None
    plan_summary: str = ""
    plan_by_shichen: dict[str, Any] = Field(default_factory=dict)
    player: PlayerPublic


class AgentActResponse(BaseModel):
    action: str
    description: str
    success: bool
    mind_summary: str = ""
    player: PlayerPublic
    npcs_here: list[NpcBrief]


class AgentActLoopResponse(BaseModel):
    steps: list[ActStepResult]
    total_steps: int
    reflected: bool = False
    player: PlayerPublic


class FinaleResponse(BaseModel):
    ending_label: str
    epilogue: str | None = None
    flags: dict[str, int] = Field(default_factory=dict)
    player: PlayerPublic
    server_ms: int = 0
    already: bool | None = None


class BountyRefreshResponse(BaseModel):
    bounties: list[Any] = Field(default_factory=list)
    board_text: str = ""
    player: PlayerPublic


class BountyAcceptResponse(BaseModel):
    ok: bool
    message: str = ""
    player: PlayerPublic


class BountyCheckResponse(BaseModel):
    has_active: bool
    player: PlayerPublic

    model_config = {"extra": "allow"}


class BountyCompleteResponse(BaseModel):
    ok: bool
    message: str = ""
    reward: Any = None
    player: PlayerPublic


class BountyAbandonResponse(BaseModel):
    ok: bool
    message: str = ""
    player: PlayerPublic


class BountyStateResponse(BaseModel):
    bounty_id: str
    state: str
    sub_steps: list[Any] = Field(default_factory=list)
    completed_steps: list[Any] = Field(default_factory=list)
    transition_log: list[Any] = Field(default_factory=list)


class SavesListResponse(BaseModel):
    saves: list[Any] = Field(default_factory=list)


class SaveResponse(BaseModel):
    ok: bool = True


class DeleteSaveResponse(BaseModel):
    ok: bool = False


class AdminMetricsResponse(BaseModel):
    total_calls: int = 0
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    by_operation: dict[str, Any] = Field(default_factory=dict)
    circuit_breaker: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class AdminCircuitBreakerResponse(BaseModel):
    state: str = "closed"
    total_requests: int = 0
    total_failures: int = 0
    rejected: int = 0
    recent_failures: int = 0
    last_failure_age_s: float | None = None

    model_config = {"extra": "allow"}


class AdminPlayersResponse(BaseModel):
    players: list[AdminPlayerBrief]


class AdminNpcStatesResponse(BaseModel):
    model_config = {"extra": "allow"}


class AdminEvalResponse(BaseModel):
    parse_success_rate: float = 0.0
    common_violations: list[Any] = Field(default_factory=list)
    by_npc: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class AdminRecentCallsResponse(BaseModel):
    calls: list[Any] = Field(default_factory=list)


# ── SSE 事件模型（流式端点） ──────────────────────────────


class TalkStreamChunkEvent(BaseModel):
    chunk: str


class TalkStreamDoneEvent(BaseModel):
    done: bool = True
    interrupted: bool | None = None
    error: str | None = None

    model_config = {"extra": "allow"}


class ActLoopStepEvent(BaseModel):
    step: int
    action: str
    description: str | None = None
    success: bool | None = None
    chunk: str | None = None
    done: bool = False


class ActLoopDoneEvent(BaseModel):
    done: bool = True
    total_steps: int = 0
    reflected: bool = False
    player: PlayerPublic | None = None
    npcs_here: list[NpcBrief] | None = None


# ── Dev/Test 响应模型 ─────────────────────────────────────


class TestInfoResponse(BaseModel):
    name: str
    description: str
    file_path: str


class TestResultResponse(BaseModel):
    test_name: str
    success: bool
    output: str
    exit_code: int | None = None
    elapsed: float = 0.0
    cases_passed: int = 0
    cases_failed: int = 0
    cases_skipped: int = 0


class ModuleInfoResponse(BaseModel):
    id: str
    label: str
    count: int
    tests: list[TestInfoResponse]


class ModuleResultResponse(BaseModel):
    module_id: str
    total: int
    passed: int
    failed: int
    skipped: int = 0
    results: list[TestResultResponse]


class TestListResponse(BaseModel):
    count: int
    tests: list[TestInfoResponse]


class TestModulesResponse(BaseModel):
    count: int
    modules: list[ModuleInfoResponse]


class InteractiveTestInfoResponse(BaseModel):
    name: str
    description: str
    module_id: str


class InteractiveModuleInfoResponse(BaseModel):
    id: str
    label: str
    icon: str
    count: int
    tests: list[InteractiveTestInfoResponse]


class InteractiveTestResultResponse(BaseModel):
    test_name: str
    success: bool
    output: str
    elapsed: float = 0.0
    npc_reply: str = ""
    favor_delta: int = 0
    coin_delta: int = 0
    dialogue_log: list[Any] = Field(default_factory=list)


class InteractiveModuleResultResponse(BaseModel):
    module_id: str
    total: int
    passed: int
    failed: int
    results: list[InteractiveTestResultResponse]


class InteractiveModulesResponse(BaseModel):
    count: int
    modules: list[InteractiveModuleInfoResponse]


class ResetCircuitBreakerResponse(BaseModel):
    status: str = "ok"
    state: str = "closed"
