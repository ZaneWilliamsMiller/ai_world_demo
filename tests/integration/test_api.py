from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import AsyncMock, patch

from backend.app import app
from backend.memory import AgentMind
from backend.models.player import PlayerState
from fastapi.testclient import TestClient

client = TestClient(app)


def make_player(player_id: str = "test_player", **overrides) -> PlayerState:
    defaults = {
        "player_id": player_id,
        "display_name": "测试侠客",
        "gender": "未言",
        "permadeath": False,
        "dead": False,
        "ended": False,
        "map_id": "world",
        "px": 16,
        "py": 30,
        "coins": 120,
        "vigor": 80,
        "vigor_max": 100,
        "spirit": 80,
        "spirit_max": 100,
        "sleep_debt": 0,
        "unconscious_ticks": 0,
        "move_locked": False,
        "enslaved": False,
        "world_day": 1,
        "world_shichen": 4,
        "weather": "薄阴",
    }
    defaults.update(overrides)
    return PlayerState(**defaults)


def _register_player(p: PlayerState) -> None:
    from backend.session.store import room
    room.players[p.player_id] = p


def _remove_player(player_id: str) -> None:
    from backend.session.store import room
    room.players.pop(player_id, None)


class TestHealthRoutes:
    def test_health_endpoint(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "llm_configured" in data
        assert "world" in data

    @patch("backend.session.store.SessionStore.get_or_create", new_callable=AsyncMock)
    @patch("backend.api.player_routes.init_npc_positions")
    @patch("backend.api.player_routes.init_npc_inventories")
    def test_hello_endpoint(self, mock_init_inv, mock_init_npc, mock_get_or_create):
        p = make_player(player_id="hello_test")
        mock_get_or_create.return_value = p
        response = client.post("/api/hello", json={
            "player_id": "hello_test",
            "display_name": "测试侠客",
            "gender": "未言",
            "permadeath": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert "player_id" in data
        assert data["player_id"] == "hello_test"
        assert "display_name" in data
        assert data["display_name"] == "测试侠客"
        assert "world_name" in data
        assert "player" in data
        assert "maps" in data
        assert "npc_catalog" in data
        mock_init_npc.assert_called_once_with(p)
        mock_init_inv.assert_called_once_with(p)


class TestPlayerRoutes:
    @patch("backend.api.player_routes._post_move_world_update", new_callable=AsyncMock)
    @patch("backend.api.player_routes._walk_path")
    @patch("backend.api.player_routes.find_path")
    @patch("backend.api.player_routes.should_trigger_encounter", return_value=False)
    def test_move_endpoint(self, mock_encounter, mock_find_path, mock_walk, mock_post_update):
        p = make_player(player_id="move_test", px=16, py=30)
        _register_player(p)
        mock_find_path.return_value = [(16, 30), (17, 30)]
        mock_walk.return_value = (
            [(16, 30), (17, 30)],
            -5,
            -2,
            [],
            None,
        )
        mock_post_update.return_value = (None, False)
        try:
            response = client.post("/api/move", json={
                "player_id": "move_test",
                "to_x": 17,
                "to_y": 30,
            })
            assert response.status_code == 200
            data = response.json()
            assert "player" in data
            assert "path" in data
            assert "delta" in data
            assert "npcs_here" in data
            assert "danger_sense" in data
            assert "atmosphere" in data
            assert "events" in data
        finally:
            _remove_player("move_test")

    def test_move_endpoint_unknown_player(self):
        response = client.post("/api/move", json={
            "player_id": "nonexistent_player",
            "to_x": 17,
            "to_y": 30,
        })
        assert response.status_code == 404

    def test_state_endpoint(self):
        p = make_player(player_id="state_test")
        _register_player(p)
        try:
            response = client.get("/api/state/state_test")
            assert response.status_code == 200
            data = response.json()
            assert "player" in data
            assert "display_name" in data
            assert data["display_name"] == "测试侠客"
            assert "npcs_here" in data
            assert "danger_sense" in data
            assert "flags" in data
            assert "ended" in data
            assert "favor" in data
            assert "rumors" in data
            assert "atmosphere" in data
            assert "events" in data
            assert "factions" in data
            assert "npc_catalog" in data
            assert "map_locations" in data
        finally:
            _remove_player("state_test")

    def test_state_endpoint_unknown_player(self):
        response = client.get("/api/state/nonexistent_player")
        assert response.status_code == 404

    def test_journal_endpoint(self):
        p = make_player(player_id="journal_test")
        p.history["jiang"] = [
            {"user": "你好", "assistant": "幸会", "day": 1, "shichen": "辰时"}
        ]
        _register_player(p)
        try:
            response = client.get("/api/journal/journal_test")
            assert response.status_code == 200
            data = response.json()
            assert "history" in data
            assert "events" in data
            assert "rumors" in data
            assert isinstance(data["history"], list)
        finally:
            _remove_player("journal_test")

    def test_journal_endpoint_unknown_player(self):
        response = client.get("/api/journal/nonexistent_player")
        assert response.status_code == 404


class TestSaveRoutes:
    @patch("backend.api.save_routes.save_game")
    def test_save_endpoint(self, mock_save):
        p = make_player(player_id="save_test")
        _register_player(p)
        try:
            response = client.post("/api/save", json={"player_id": "save_test"})
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            mock_save.assert_called_once_with(p)
        finally:
            _remove_player("save_test")

    def test_save_endpoint_unknown_player(self):
        response = client.post("/api/save", json={"player_id": "nonexistent_player"})
        assert response.status_code == 404

    @patch("backend.api.save_routes.init_npc_positions")
    @patch("backend.api.save_routes.init_npc_inventories")
    @patch("backend.api.save_routes.load_game")
    def test_load_endpoint(self, mock_load, mock_init_inv, mock_init_npc):
        p = make_player(player_id="load_test")
        mock_load.return_value = p
        response = client.post("/api/load", json={
            "player_id": "load_test",
            "display_name": "测试侠客",
            "gender": "未言",
            "permadeath": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert "player_id" in data
        assert data["player_id"] == "load_test"
        assert "player" in data
        assert "maps" in data
        mock_init_npc.assert_called_once()
        mock_init_inv.assert_called_once()
        _remove_player("load_test")

    @patch("backend.api.save_routes.load_game", return_value=None)
    def test_load_endpoint_not_found(self, mock_load):
        response = client.post("/api/load", json={
            "player_id": "missing_save",
            "display_name": "测试侠客",
            "gender": "未言",
            "permadeath": False,
        })
        assert response.status_code == 404

    @patch("backend.api.save_routes.load_game")
    def test_load_endpoint_dead_permadeath(self, mock_load):
        p = make_player(player_id="dead_perm", dead=True, permadeath=True)
        mock_load.return_value = p
        response = client.post("/api/load", json={
            "player_id": "dead_perm",
            "display_name": "测试侠客",
            "gender": "未言",
            "permadeath": True,
        })
        assert response.status_code == 400

    @patch("backend.api.save_routes.delete_save", return_value=True)
    def test_delete_endpoint(self, mock_delete):
        p = make_player(player_id="delete_test")
        _register_player(p)
        try:
            response = client.post("/api/delete-save", json={"player_id": "delete_test"})
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            mock_delete.assert_called_once_with("delete_test")
        finally:
            _remove_player("delete_test")

    def test_saves_list_endpoint(self):
        response = client.get("/api/saves")
        assert response.status_code == 200
        data = response.json()
        assert "saves" in data
        assert isinstance(data["saves"], list)


class TestNpcRoutes:
    @patch("backend.systems.save_system.save_game")
    @patch("backend.systems.core.rest_at_location")
    def test_rest_endpoint(self, mock_rest, mock_save):
        p = make_player(player_id="rest_test")
        _register_player(p)
        mock_rest.return_value = {
            "ok": True,
            "reason": "你在客栈歇了一歇",
            "delta": {"vigor": 10, "spirit": 20, "sleep_debt": -5},
            "ticks_passed": 2,
            "note": "精神为之一振",
        }
        try:
            response = client.post("/api/rest", json={"player_id": "rest_test"})
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "player" in data
            assert "delta" in data
            assert "danger_sense" in data
            assert "atmosphere" in data
            assert "events" in data
            mock_rest.assert_called_once()
        finally:
            _remove_player("rest_test")

    def test_rest_endpoint_unknown_player(self):
        response = client.post("/api/rest", json={"player_id": "nonexistent"})
        assert response.status_code == 404

    @patch("backend.systems.core.rest_at_location")
    def test_rest_endpoint_dead_player(self, mock_rest):
        p = make_player(player_id="dead_rest", dead=True)
        _register_player(p)
        try:
            response = client.post("/api/rest", json={"player_id": "dead_rest"})
            assert response.status_code == 400
            mock_rest.assert_not_called()
        finally:
            _remove_player("dead_rest")

    @patch("backend.systems.core.rest_at_location")
    def test_rest_endpoint_ended_player(self, mock_rest):
        p = make_player(player_id="ended_rest", ended=True)
        _register_player(p)
        try:
            response = client.post("/api/rest", json={"player_id": "ended_rest"})
            assert response.status_code == 400
            mock_rest.assert_not_called()
        finally:
            _remove_player("ended_rest")

    @patch("backend.systems.core.rest_at_location")
    def test_rest_endpoint_unconscious_player(self, mock_rest):
        p = make_player(player_id="unconscious_rest", unconscious_ticks=3)
        _register_player(p)
        try:
            response = client.post("/api/rest", json={"player_id": "unconscious_rest"})
            assert response.status_code == 400
            mock_rest.assert_not_called()
        finally:
            _remove_player("unconscious_rest")

    @patch("backend.systems.core.rest_at_location")
    def test_rest_endpoint_enslaved_player(self, mock_rest):
        p = make_player(player_id="enslaved_rest", enslaved=True)
        _register_player(p)
        try:
            response = client.post("/api/rest", json={"player_id": "enslaved_rest"})
            assert response.status_code == 403
            mock_rest.assert_not_called()
        finally:
            _remove_player("enslaved_rest")

    @patch("backend.systems.core.rest_at_location")
    def test_rest_endpoint_move_locked_player(self, mock_rest):
        p = make_player(player_id="locked_rest", move_locked=True)
        _register_player(p)
        try:
            response = client.post("/api/rest", json={"player_id": "locked_rest"})
            assert response.status_code == 409
            mock_rest.assert_not_called()
        finally:
            _remove_player("locked_rest")

    @patch("backend.api.npc_routes.format_bounty_board", return_value="悬赏榜内容")
    @patch("backend.api.npc_routes.generate_bounties")
    @patch("backend.api.npc_routes.refresh_bounties")
    def test_bounty_refresh(self, mock_refresh, mock_generate, mock_format):
        p = make_player(player_id="bounty_test")
        _register_player(p)
        mock_generate.return_value = [
            {"type": "讨伐", "title": "山贼头目", "desc": "剿灭山贼", "reward": {"coins": 50}, "id": "b1"}
        ]
        try:
            response = client.post("/api/bounty/refresh", json={"player_id": "bounty_test"})
            assert response.status_code == 200
            data = response.json()
            assert "bounties" in data
            assert "board_text" in data
            assert "player" in data
        finally:
            _remove_player("bounty_test")

    @patch("backend.api.npc_routes.format_bounty_board", return_value="")
    @patch("backend.api.npc_routes.refresh_bounties")
    def test_bounty_list_empty(self, mock_refresh, mock_format):
        p = make_player(player_id="bounty_empty")
        _register_player(p)
        try:
            response = client.post("/api/bounty/refresh", json={"player_id": "bounty_empty"})
            assert response.status_code == 200
            data = response.json()
            assert "bounties" in data
            assert isinstance(data["bounties"], list)
        finally:
            _remove_player("bounty_empty")

    @patch("backend.api.npc_routes.accept_bounty")
    def test_bounty_accept(self, mock_accept):
        p = make_player(player_id="bounty_accept")
        _register_player(p)
        mock_accept.return_value = (True, "已接取悬赏")
        try:
            response = client.post("/api/bounty/accept", json={
                "player_id": "bounty_accept",
                "bounty_id": "b1",
            })
            assert response.status_code == 200
            data = response.json()
            assert "ok" in data
            assert "message" in data
            assert "player" in data
        finally:
            _remove_player("bounty_accept")

    @patch("backend.api.npc_routes.check_bounty_progress")
    def test_bounty_check_no_active(self, mock_check):
        p = make_player(player_id="bounty_check")
        _register_player(p)
        mock_check.return_value = None
        try:
            response = client.post("/api/bounty/check", json={"player_id": "bounty_check"})
            assert response.status_code == 200
            data = response.json()
            assert data["has_active"] is False
        finally:
            _remove_player("bounty_check")

    @patch("backend.api.npc_routes.check_bounty_progress")
    def test_bounty_check_active(self, mock_check):
        p = make_player(player_id="bounty_check2")
        _register_player(p)
        mock_check.return_value = {"progress": 0.5, "detail": "进行中"}
        try:
            response = client.post("/api/bounty/check", json={"player_id": "bounty_check2"})
            assert response.status_code == 200
            data = response.json()
            assert data["has_active"] is True
            assert "progress" in data
        finally:
            _remove_player("bounty_check2")

    @patch("backend.api.npc_routes.complete_bounty")
    def test_bounty_complete(self, mock_complete):
        p = make_player(player_id="bounty_complete")
        _register_player(p)
        mock_complete.return_value = (True, "悬赏已完成", {"coins": 50})
        try:
            response = client.post("/api/bounty/complete", json={"player_id": "bounty_complete"})
            assert response.status_code == 200
            data = response.json()
            assert "ok" in data
            assert "message" in data
            assert "reward" in data
        finally:
            _remove_player("bounty_complete")

    @patch("backend.api.npc_routes.abandon_bounty")
    def test_bounty_abandon(self, mock_abandon):
        p = make_player(player_id="bounty_abandon")
        _register_player(p)
        mock_abandon.return_value = (True, "已放弃悬赏")
        try:
            response = client.post("/api/bounty/abandon", json={"player_id": "bounty_abandon"})
            assert response.status_code == 200
            data = response.json()
            assert "ok" in data
            assert "message" in data
        finally:
            _remove_player("bounty_abandon")

    def test_agent_mind_no_mind(self):
        p = make_player(player_id="mind_test")
        _register_player(p)
        try:
            response = client.get("/api/agent/mind_test/jiang/mind")
            assert response.status_code == 200
            data = response.json()
            assert data["npc_id"] == "jiang"
            assert "npc_name" in data
            assert "items" in data
            assert "plan_day" in data
            assert "plan_summary" in data
            assert "plan_by_shichen" in data
            assert "affect_valence" in data
            assert "affect_arousal" in data
            assert "affect_mood" in data
            assert "affect_cause" in data
        finally:
            _remove_player("mind_test")

    def test_agent_mind_with_mind(self):
        p = make_player(player_id="mind_test2")
        mind = AgentMind()
        mind.plan_day = 1
        mind.plan_summary = "巡视码头"
        mind.affect_mood = "警觉"
        mind.affect_valence = -2.0
        mind.affect_arousal = 7.0
        p.minds["jiang"] = mind
        _register_player(p)
        try:
            response = client.get("/api/agent/mind_test2/jiang/mind")
            assert response.status_code == 200
            data = response.json()
            assert data["npc_id"] == "jiang"
            assert data["plan_day"] == 1
            assert data["plan_summary"] == "巡视码头"
            assert data["affect_mood"] == "警觉"
            assert data["affect_valence"] == -2.0
            assert data["affect_arousal"] == 7.0
            assert isinstance(data["items"], list)
        finally:
            _remove_player("mind_test2")

    def test_agent_mind_unknown_player(self):
        response = client.get("/api/agent/nonexistent/jiang/mind")
        assert response.status_code == 404

    def test_agent_mind_unknown_npc(self):
        p = make_player(player_id="mind_bad_npc")
        _register_player(p)
        try:
            response = client.get("/api/agent/mind_bad_npc/nonexistent_npc/mind")
            assert response.status_code == 404
        finally:
            _remove_player("mind_bad_npc")

    def test_agent_mind_dead_player(self):
        p = make_player(player_id="mind_dead", dead=True)
        _register_player(p)
        try:
            response = client.get("/api/agent/mind_dead/jiang/mind")
            assert response.status_code == 400
        finally:
            _remove_player("mind_dead")

    def test_agent_mind_ended_player(self):
        p = make_player(player_id="mind_ended", ended=True)
        _register_player(p)
        try:
            response = client.get("/api/agent/mind_ended/jiang/mind")
            assert response.status_code == 400
        finally:
            _remove_player("mind_ended")

    @patch("backend.agents.brain.chat_completion", new_callable=AsyncMock)
    def test_agent_reflect(self, mock_llm):
        mock_llm.return_value = '{"insights": ["江湖险恶，需多加小心", "此人似有善意"]}'
        p = make_player(player_id="reflect_test")
        _register_player(p)
        try:
            response = client.post("/api/agent/reflect", json={
                "player_id": "reflect_test",
                "npc_id": "jiang",
            })
            assert response.status_code == 200
            data = response.json()
            assert "added" in data
            assert "count" in data
            assert "player" in data
        finally:
            _remove_player("reflect_test")

    def test_agent_reflect_unknown_player(self):
        response = client.post("/api/agent/reflect", json={
            "player_id": "nonexistent",
            "npc_id": "jiang",
        })
        assert response.status_code == 404

    def test_agent_reflect_unknown_npc(self):
        p = make_player(player_id="reflect_bad_npc")
        _register_player(p)
        try:
            response = client.post("/api/agent/reflect", json={
                "player_id": "reflect_bad_npc",
                "npc_id": "nonexistent_npc",
            })
            assert response.status_code == 404
        finally:
            _remove_player("reflect_bad_npc")

    @patch("backend.agents.brain.chat_completion", new_callable=AsyncMock)
    def test_agent_plan(self, mock_llm):
        mock_llm.return_value = '{"summary": "巡视码头", "schedule": {"辰时": "巡码头", "巳时": "查货"}}'
        p = make_player(player_id="plan_test")
        _register_player(p)
        try:
            response = client.post("/api/agent/plan", json={
                "player_id": "plan_test",
                "npc_id": "jiang",
            })
            assert response.status_code == 200
            data = response.json()
            assert "ok" in data
            assert "plan_day" in data
            assert "plan_summary" in data
            assert "plan_by_shichen" in data
            assert "player" in data
        finally:
            _remove_player("plan_test")

    @patch("backend.api.npc_routes.parse_npc_reply_json")
    @patch("backend.api.npc_routes.chat_completion", new_callable=AsyncMock)
    @patch("backend.api.npc_routes.build_npc_messages")
    def test_npc_talk(self, mock_build_msgs, mock_llm, mock_parse):
        mock_build_msgs.return_value = [{"role": "user", "content": "你好"}]
        mock_llm.return_value = '{"visible_text": "幸会幸会", "state_update": {}}'
        from backend.models.llm_schema import NpcResponseSchema
        mock_parse.return_value = NpcResponseSchema(  # type: ignore[call-arg]
            visible_text="幸会幸会",
            state_update={},
        )
        p = make_player(player_id="talk_test")
        _register_player(p)
        try:
            response = client.post("/api/npc/talk", json={
                "player_id": "talk_test",
                "npc_id": "jiang",
                "message": "你好",
            })
            assert response.status_code in (200, 400, 404)
        finally:
            _remove_player("talk_test")

    @patch("backend.api.npc_routes.parse_finale")
    @patch("backend.api.npc_routes.chat_completion", new_callable=AsyncMock)
    def test_finale_endpoint(self, mock_llm, mock_parse_finale):
        mock_llm.return_value = "这是一段终局叙事。ENDING_TITLE: 江湖远行"
        mock_parse_finale.return_value = ("这是一段终局叙事。", "江湖远行")
        p = make_player(player_id="finale_test")
        p.history["jiang"] = [
            {"user": "你好", "assistant": "幸会", "day": 1, "shichen": "辰时"}
        ]
        _register_player(p)
        try:
            response = client.post("/api/finale", json={
                "player_id": "finale_test",
                "closing_note": "愿江湖安好",
            })
            assert response.status_code == 200
            data = response.json()
            assert "ending_label" in data
            assert "epilogue" in data
            assert "player" in data
            assert "flags" in data
            assert data["ending_label"] == "江湖远行"
        finally:
            _remove_player("finale_test")

    def test_finale_already_ended(self):
        p = make_player(player_id="finale_ended", ended=True, ending_label="旧日终章")
        _register_player(p)
        try:
            response = client.post("/api/finale", json={
                "player_id": "finale_ended",
            })
            assert response.status_code == 200
            data = response.json()
            assert data["already"] is True
            assert data["ending_label"] == "旧日终章"
        finally:
            _remove_player("finale_ended")

    def test_finale_dead_player(self):
        p = make_player(player_id="finale_dead", dead=True)
        _register_player(p)
        try:
            response = client.post("/api/finale", json={
                "player_id": "finale_dead",
            })
            assert response.status_code == 400
        finally:
            _remove_player("finale_dead")

    @patch("backend.systems.economy.use_player_item")
    def test_item_use(self, mock_use):
        p = make_player(player_id="item_test")
        _register_player(p)
        mock_use.return_value = {"success": True, "note": "使用了金创药", "item_consumed": "金创药"}
        try:
            response = client.post("/api/item/use", json={
                "player_id": "item_test",
                "item": "金创药",
            })
            assert response.status_code == 200
            data = response.json()
            assert "player" in data
            assert data["success"] is True
        finally:
            _remove_player("item_test")

    def test_item_use_unknown_player(self):
        response = client.post("/api/item/use", json={
            "player_id": "nonexistent",
            "item": "金创药",
        })
        assert response.status_code == 404

    @patch("backend.systems.economy.use_player_item")
    def test_item_use_dead_player(self, mock_use):
        p = make_player(player_id="item_dead", dead=True)
        _register_player(p)
        try:
            response = client.post("/api/item/use", json={
                "player_id": "item_dead",
                "item": "金创药",
            })
            assert response.status_code == 400
            mock_use.assert_not_called()
        finally:
            _remove_player("item_dead")
