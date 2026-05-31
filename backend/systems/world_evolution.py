"""世界演进引擎 —— 离线推演 NPC 行为与故事事件。

在玩家不在线时，模拟世界 5 天的演进：NPC 按计划行动、对话、反思，
故事事件自然发生，最终生成悬赏供玩家回归后接取。

设计要点：
  - 异步生成器 run() 逐步 yield SSE 事件，前端可实时展示进度
  - LLM 成本控制：70% 模板对话 + 仅关键 NPC 反思 + 演进期用回退故事事件
  - 取消安全：随时可取消，取消时仍生成基础悬赏
"""
from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import AsyncGenerator
from typing import Any

from backend.agents.actor import decide_next_action, execute_plan_step_async
from backend.agents.brain import plan_day, record_observation, reflect
from backend.agents.game_state import get_or_init_mind
from backend.data.maps_data import MAP_LOCATIONS
from backend.data.npcs_data import NPCS
from backend.memory import AgentMind
from backend.models.player import PlayerState
from backend.systems.bounty_board import generate_bounties_from_events
from backend.systems.core import init_npc_positions
from backend.systems.economy import init_npc_inventories
from backend.systems.npc_state import maybe_wander_npcs, update_npc_state_dynamic
from backend.systems.story_events import _fallback_story_events, generate_story_events, write_story_events_to_memory
from backend.systems.time_weather import advance_clock, shichen_name

log = logging.getLogger("world_evolution")

_MAX_DAYS = 5
_SCHICHEN_PER_DAY = 12
_NPC_ACTIONS_PER_TICK = (2, 3)
_REFLECT_NPCS_PER_DAY = (2, 3)
_PLAYER_ACTION_INTERVAL = 3
_STORY_EVENT_INTERVAL = 6
_TEMPLATE_DIALOGUE_CHANCE = 0.70

_DIALOGUE_TEMPLATES: dict[str, list[str]] = {
    "生意往来": [
        "{a}与{b}在{loc}谈了一笔生意，双方各让三分。",
        "{a}向{b}催了一笔旧账，{b}推说下月再结。",
        "{a}在{loc}向{b}打听了一批货的来路，{b}笑而不答。",
        "{a}托{b}代售几件物什，{b}应了，但说要先看货。",
        "{a}与{b}在{loc}论了半天价，最后各退一步。",
        "{b}向{a}借了些银钱周转，说月底一定还。",
    ],
    "交好": [
        "{a}与{b}在{loc}碰面，寒暄了几句家常。",
        "{a}给{b}带了些吃食，两人在{loc}分了。",
        "{a}与{b}在{loc}闲坐，说起旧事，都笑了。",
        "{a}帮{b}搭了把手，{b}连声道谢。",
        "{a}与{b}在{loc}下了一盘棋，{a}赢了半子。",
    ],
    "面上客气": [
        "{a}在{loc}与{b}点了点头，各走各路。",
        "{a}与{b}在{loc}客套了几句，话里都留着三分。",
        "{a}向{b}拱了拱手，{b}也还了一礼，便不再多言。",
        "{a}与{b}在{loc}擦肩而过，彼此只打了个照面。",
    ],
    "心存芥蒂": [
        "{a}在{loc}远远看见{b}，便绕道走了。",
        "{a}与{b}在{loc}碰面，话没说三句便冷了场。",
        "{a}听人提起{b}，脸色一沉，岔开了话头。",
        "{a}在{loc}故意没理{b}，{b}也装作没看见。",
    ],
    "互不招惹": [
        "{a}与{b}在{loc}各忙各的，互不相扰。",
        "{a}路过{b}的摊前，没停也没看。",
        "{a}与{b}在{loc}同处一隅，谁也没先开口。",
    ],
    "default": [
        "{a}与{b}在{loc}说了几句话，便各自散了。",
        "{a}在{loc}遇见{b}，随意聊了两句天气。",
        "{a}与{b}在{loc}打了个招呼，便各自忙去。",
        "{a}向{b}问了个路，{b}指了指方向。",
        "{a}与{b}在{loc}点了点头，算是打了招呼。",
    ],
}

_PLAYER_ACTION_TEMPLATES: list[str] = [
    "你在{loc}帮{npc}卸了一趟货",
    "你在{loc}替{npc}跑了一趟腿",
    "你在{loc}与{npc}闲聊了几句",
    "你在{loc}歇了歇脚，听人说了些闲话",
    "你在{loc}帮{npc}搬了些东西",
    "你在{loc}替{npc}传了个话",
    "你在{loc}与{npc}讨了口水喝",
    "你在{loc}看了看热闹",
    "你在{loc}打了个盹",
    "你在{loc}四处转了转",
    "你在{loc}向{npc}打听了一下行情",
    "你在{loc}帮{npc}看了会儿摊",
]

_PLAYER_SOLO_TEMPLATE = "你在{loc}歇了歇脚，听人说了些闲话"


def _get_relationship_type(npc_a: str, npc_b: str) -> str:
    try:
        from backend.data.relationships import NPC_RELATIONSHIPS
        rels = NPC_RELATIONSHIPS.get(npc_a, [])
        for r in rels:
            if r.get("target") == npc_b:
                attitude = r.get("attitude", "")
                mapping = {
                    "挚交": "交好", "交好": "交好", "旧交": "交好",
                    "暧昧线人": "交好",
                    "生意伙伴": "生意往来", "主顾": "生意往来", "老主顾": "生意往来",
                    "面上客气": "面上客气", "面熟": "面上客气", "面上恭敬": "面上客气",
                    "心存芥蒂": "心存芥蒂", "势同水火": "心存芥蒂",
                    "互不招惹": "互不招惹",
                }
                return mapping.get(attitude, "default")
    except Exception:
        pass
    return "default"


def _pick_location_for_npc(p: PlayerState, npc_id: str) -> str:
    pos = p.npc_positions.get(npc_id)
    if pos and len(pos) >= 3:
        locs = MAP_LOCATIONS.get(str(pos[0]), {})
        px, py = int(pos[1]), int(pos[2])
        best_name = "市口"
        best_dist = 999
        for name, coords in locs.items():
            if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                d = abs(int(coords[0]) - px) + abs(int(coords[1]) - py)
                if d < best_dist:
                    best_dist = d
                    best_name = name
        return best_name
    loc_names = list(MAP_LOCATIONS.get(p.map_id, {}).keys())
    return random.choice(loc_names) if loc_names else "市口"


def _generate_template_dialogue(
    p: PlayerState, npc_a: str, npc_b: str,
) -> dict[str, str] | None:
    name_a = NPCS.get(npc_a, {}).get("short", npc_a)
    name_b = NPCS.get(npc_b, {}).get("short", npc_b)
    loc = _pick_location_for_npc(p, npc_a)
    rel_type = _get_relationship_type(npc_a, npc_b)
    templates = _DIALOGUE_TEMPLATES.get(rel_type, _DIALOGUE_TEMPLATES["default"])
    tmpl = random.choice(templates)
    line = tmpl.format(a=name_a, b=name_b, loc=loc)
    return {"speaker_a": name_a, "speaker_b": name_b, "line": line}


def _get_visible_npcs() -> list[str]:
    return [nid for nid, m in NPCS.items() if not m.get("hidden") and not m.get("always")]


def _get_active_npcs(p: PlayerState) -> list[str]:
    visible = _get_visible_npcs()
    active = []
    for nid in visible:
        pos = p.npc_positions.get(nid)
        if pos and len(pos) >= 3 and str(pos[0]) == p.map_id:
            active.append(nid)
    return active if active else visible


def _npcs_at_same_location(p: PlayerState, npc_id: str) -> list[str]:
    pos = p.npc_positions.get(npc_id)
    if not pos or len(pos) < 3:
        return []
    mid, cx, cy = str(pos[0]), int(pos[1]), int(pos[2])
    others = []
    for oid, opos in p.npc_positions.items():
        if oid == npc_id or oid == "player":
            continue
        if not isinstance(opos, (list, tuple)) or len(opos) < 3:
            continue
        if str(opos[0]) == mid and abs(int(opos[1]) - cx) <= 2 and abs(int(opos[2]) - cy) <= 2:
            others.append(oid)
    return others


class WorldEvolution:
    def __init__(self, p: PlayerState, player_display_name: str) -> None:
        self.p = p
        self.player_display_name = player_display_name
        self._cancelled = False
        self._player_mind: AgentMind | None = None

    def cancel(self) -> None:
        self._cancelled = True

    async def run(self) -> AsyncGenerator[dict[str, Any], None]:
        p = self.p
        total_ticks = _MAX_DAYS * _SCHICHEN_PER_DAY
        current_tick = 0

        init_npc_positions(p)
        init_npc_inventories(p)

        visible_npcs = _get_visible_npcs()
        for nid in visible_npcs:
            get_or_init_mind(p, nid)

        self._player_mind = AgentMind()
        p.minds["player"] = self._player_mind

        for nid in visible_npcs:
            meta = NPCS.get(nid, {})
            mind = get_or_init_mind(p, nid)
            try:
                await plan_day(
                    npc_id=nid,
                    npc_name=meta.get("name", nid),
                    npc_blurb=meta.get("short", ""),
                    mind=mind,
                    world_day=int(p.world_day),
                )
            except Exception as e:
                log.warning("plan_day failed for %s: %s", nid, e)

        yield {"type": "progress", "current": 0, "total": total_ticks}

        for day in range(_MAX_DAYS):
            if self._cancelled:
                break

            world_day = int(p.world_day)

            for shichen_idx in range(_SCHICHEN_PER_DAY):
                if self._cancelled:
                    break

                current_tick += 1
                advance_clock(p, 1)
                sh_name = shichen_name(p.world_shichen)
                world_day = int(p.world_day)

                for nid in visible_npcs:
                    try:
                        update_npc_state_dynamic(p, nid)
                    except Exception as e:
                        log.debug("update_npc_state_dynamic failed for %s: %s", nid, e)

                maybe_wander_npcs(p, 1)

                active_npcs = _get_active_npcs(p)
                n_actions = random.randint(*_NPC_ACTIONS_PER_TICK)
                action_npcs = random.sample(active_npcs, min(n_actions, len(active_npcs)))

                for nid in action_npcs:
                    if self._cancelled:
                        break
                    meta = NPCS.get(nid, {})
                    npc_short = meta.get("short", nid)
                    mind = get_or_init_mind(p, nid)
                    try:
                        action = decide_next_action(mind, p, nid)
                        if action.value == "talk" and random.random() < _TEMPLATE_DIALOGUE_CHANCE:
                            others = _npcs_at_same_location(p, nid)
                            if others:
                                other_id = random.choice(others)
                                other_short = NPCS.get(other_id, {}).get("short", other_id)
                                dlg = _generate_template_dialogue(p, nid, other_id)
                                if dlg:
                                    yield {
                                        "type": "dialogue",
                                        "speaker_a": dlg["speaker_a"],
                                        "speaker_b": dlg["speaker_b"],
                                        "line": dlg["line"],
                                    }
                                    record_observation(
                                        mind,
                                        dlg["line"],
                                        world_day=world_day,
                                        world_shichen=sh_name,
                                        importance=3.0,
                                    )
                                    other_mind = get_or_init_mind(p, other_id)
                                    record_observation(
                                        other_mind,
                                        dlg["line"],
                                        world_day=world_day,
                                        world_shichen=sh_name,
                                        importance=3.0,
                                    )
                                    continue

                        result = await execute_plan_step_async(p, nid, mind)
                        if result.success and result.description:
                            if result.action_type.value == "talk" and result.raw_dialogue:
                                lines = result.raw_dialogue
                                if lines:
                                    speaker_a = npc_short
                                    speaker_b = ""
                                    line_text = ""
                                    for entry in lines:
                                        s = entry.get("speaker", "")
                                        l = entry.get("line", "")
                                        if s and l:
                                            if not speaker_b or speaker_b == s:
                                                speaker_b = s
                                            line_text = l
                                            break
                                    yield {
                                        "type": "dialogue",
                                        "speaker_a": speaker_a,
                                        "speaker_b": speaker_b or "路人",
                                        "line": line_text,
                                    }
                                else:
                                    yield {
                                        "type": "tick",
                                        "day": world_day,
                                        "shichen": sh_name,
                                        "text": f"🗣️ {result.description[:60]}",
                                    }
                            else:
                                icon = {"move": "🚶", "rest": "💤", "idle": "🟢"}.get(
                                    result.action_type.value, "•"
                                )
                                yield {
                                    "type": "tick",
                                    "day": world_day,
                                    "shichen": sh_name,
                                    "text": f"{icon} {result.description[:60]}",
                                }
                    except Exception as e:
                        log.warning("action failed for %s: %s", nid, e)

                if shichen_idx > 0 and shichen_idx % _PLAYER_ACTION_INTERVAL == 0:
                    player_text = self._player_action(p)
                    yield {
                        "type": "player_action",
                        "text": player_text,
                    }

                if shichen_idx > 0 and shichen_idx % _STORY_EVENT_INTERVAL == 0:
                    events = _fallback_story_events(p, count=2)
                    for evt in events:
                        p.story_events = getattr(p, "story_events", []) or []
                        p.story_events.append(evt)
                        write_story_events_to_memory(p, [evt])
                        yield {
                            "type": "event",
                            "title": evt.get("title", ""),
                            "desc": evt.get("desc", ""),
                        }

                yield {
                    "type": "progress",
                    "current": current_tick,
                    "total": total_ticks,
                }

                await asyncio.sleep(0.05)

            if self._cancelled:
                break

            n_reflect = random.randint(*_REFLECT_NPCS_PER_DAY)
            reflect_npcs = random.sample(active_npcs, min(n_reflect, len(active_npcs)))
            for nid in reflect_npcs:
                if self._cancelled:
                    break
                meta = NPCS.get(nid, {})
                mind = get_or_init_mind(p, nid)
                try:
                    await reflect(
                        npc_id=nid,
                        npc_name=meta.get("name", nid),
                        npc_blurb=meta.get("short", ""),
                        mind=mind,
                        world_day=int(p.world_day),
                        world_shichen=shichen_name(p.world_shichen),
                    )
                except Exception as e:
                    log.warning("reflect failed for %s: %s", nid, e)

            if day < _MAX_DAYS - 1:
                for nid in visible_npcs:
                    if self._cancelled:
                        break
                    meta = NPCS.get(nid, {})
                    mind = get_or_init_mind(p, nid)
                    try:
                        await plan_day(
                            npc_id=nid,
                            npc_name=meta.get("name", nid),
                            npc_blurb=meta.get("short", ""),
                            mind=mind,
                            world_day=int(p.world_day),
                        )
                    except Exception as e:
                        log.warning("plan_day failed for %s: %s", nid, e)

        if self._cancelled:
            await self._generate_fallback_bounties(p)
            yield {"type": "cancelled"}
            return

        await self._finalize(p)

        yield {
            "type": "done",
            "player_id": p.player_id,
            "summary": f"世界已演进{_MAX_DAYS}日，江湖风云已变，悬赏榜已更新。",
        }

    def _player_action(self, p: PlayerState) -> str:
        active_npcs = _get_active_npcs(p)
        if "player" not in p.npc_positions:
            p.npc_positions["player"] = (p.map_id, p.px, p.py)
        loc = _pick_location_for_npc(p, "player")
        if active_npcs and random.random() < 0.6:
            npc_id = random.choice(active_npcs)
            npc_short = NPCS.get(npc_id, {}).get("short", "某人")
            tmpl = random.choice(_PLAYER_ACTION_TEMPLATES)
            return tmpl.format(loc=loc, npc=npc_short)
        return _PLAYER_SOLO_TEMPLATE.format(loc=loc)

    async def _generate_fallback_bounties(self, p: PlayerState) -> None:
        try:
            events = _fallback_story_events(p, count=3)
            p.story_events = getattr(p, "story_events", []) or []
            p.story_events.extend(events)
            write_story_events_to_memory(p, events)
            bounties = generate_bounties_from_events(p, events)
            p.bounties = bounties
            p.last_bounty_refresh_day = int(p.world_day)
            self._save(p)
        except Exception as e:
            log.warning("fallback bounty generation failed: %s", e)

    async def _finalize(self, p: PlayerState) -> None:
        try:
            events = await generate_story_events(p, count=3)
            p.story_events = getattr(p, "story_events", []) or []
            p.story_events.extend(events)
            write_story_events_to_memory(p, events)
            bounties = generate_bounties_from_events(p, events)
            p.bounties = bounties
            p.last_bounty_refresh_day = int(p.world_day)
        except Exception as e:
            log.warning("LLM story event generation failed in finalize: %s, using fallback", e)
            events = _fallback_story_events(p, count=3)
            p.story_events = getattr(p, "story_events", []) or []
            p.story_events.extend(events)
            write_story_events_to_memory(p, events)
            bounties = generate_bounties_from_events(p, events)
            p.bounties = bounties

        self._save(p)

    @staticmethod
    def _save(p: PlayerState) -> None:
        try:
            from backend.systems.save_system import save_game
            save_game(p)
            log.info("Auto-saved after world evolution for player %s", p.player_id)
        except Exception as e:
            log.warning("Auto-save failed after world evolution: %s", e)


_active_evolutions: dict[str, WorldEvolution] = {}


def get_evolution(player_id: str) -> WorldEvolution | None:
    return _active_evolutions.get(player_id)


def register_evolution(player_id: str, evolution: WorldEvolution) -> None:
    _active_evolutions[player_id] = evolution


def unregister_evolution(player_id: str) -> None:
    _active_evolutions.pop(player_id, None)
