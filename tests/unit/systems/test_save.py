# pyright: reportCallIssue=false
"""离线单元测试 — save_system / config"""
import logging
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from conftest import make_player


class TestSaveSystem:
    def test_save_and_load_roundtrip(self, tmp_path):
        from backend.systems import save_system

        p = make_player(player_id="roundtrip_test", display_name="回环侠")
        p.coins = 999
        p.vigor = 60
        p.spirit = 45
        p.world_day = 7
        p.inventory["干粮"] = 3
        p.inventory["金创药"] = 1

        with patch.object(save_system, "SAVE_DIR", tmp_path):
            save_system.save_game(p)
            loaded = save_system.load_game("roundtrip_test")

        assert loaded is not None
        assert loaded.player_id == "roundtrip_test"
        assert loaded.display_name == "回环侠"
        assert loaded.coins == 999
        assert loaded.vigor == 60
        assert loaded.spirit == 45
        assert loaded.world_day == 7
        assert loaded.inventory.get("干粮") == 3
        assert loaded.inventory.get("金创药") == 1

    def test_load_nonexistent(self, tmp_path):
        from backend.systems import save_system

        with patch.object(save_system, "SAVE_DIR", tmp_path):
            result = save_system.load_game("no_such_player")

        assert result is None

    def test_list_saves(self, tmp_path):
        from backend.systems import save_system

        p1 = make_player(player_id="list_a", display_name="甲")
        p2 = make_player(player_id="list_b", display_name="乙", coins=200)

        with patch.object(save_system, "SAVE_DIR", tmp_path):
            save_system.save_game(p1)
            save_system.save_game(p2)
            saves = save_system.list_saves()

        ids = {s["player_id"] for s in saves}
        assert "list_a" in ids
        assert "list_b" in ids

        for s in saves:
            if s["player_id"] == "list_b":
                assert s["coins"] == 200

    def test_delete_save(self, tmp_path):
        from backend.systems import save_system

        p = make_player(player_id="del_me", display_name="删除侠")

        with patch.object(save_system, "SAVE_DIR", tmp_path):
            save_system.save_game(p)
            assert save_system.load_game("del_me") is not None

            deleted = save_system.delete_save("del_me")
            assert deleted is True
            assert save_system.load_game("del_me") is None

    def test_delete_nonexistent_returns_false(self, tmp_path):
        from backend.systems import save_system

        with patch.object(save_system, "SAVE_DIR", tmp_path):
            result = save_system.delete_save("ghost_player")

        assert result is False

    def test_respawn_at_supply_point(self, tmp_path):
        from backend.systems import save_system
        from backend.systems.constants import RESPAWN_MIN_STAT, RESPAWN_RATIO

        fake_map = {
            "world": {
                "name": "测试江湖",
                "rows": [
                    "#####",
                    "#T..#",
                    "#...#",
                    "#..Y#",
                    "#####",
                ],
            }
        }

        p = make_player(player_id="respawn_test", px=2, py=2)
        p.dead = True
        p.death_reason = "重伤"
        p.vigor = 0
        p.spirit = 0
        p.vigor_max = 100
        p.spirit_max = 100
        p.move_locked = True
        p.enslaved = True
        p.unconscious_ticks = 5
        p.life_burn_ticks = 3

        with patch("backend.data.maps_data.MAPS", fake_map), \
             patch("backend.systems.reputation.push_event"):
            msg = save_system.respawn_at_supply_point(p)

        assert p.dead is False
        assert p.death_reason is None
        assert p.move_locked is False
        assert p.enslaved is False
        assert p.unconscious_ticks == 0
        assert p.life_burn_ticks == 0
        assert p.vigor == max(RESPAWN_MIN_STAT, 100 // RESPAWN_RATIO)
        assert p.spirit == max(RESPAWN_MIN_STAT, 100 // RESPAWN_RATIO)
        assert "补给" in msg or "苏醒" in msg

    def test_respawn_no_supply_point_falls_back(self, tmp_path):
        from backend.systems import save_system
        from backend.systems.constants import DEFAULT_RESPAWN_X, DEFAULT_RESPAWN_Y

        fake_map = {
            "world": {
                "name": "荒野",
                "rows": [
                    "#####",
                    "#...#",
                    "#...#",
                    "#...#",
                    "#####",
                ],
            }
        }

        p = make_player(player_id="respawn_fallback", px=2, py=2, map_id="nomap")
        p.dead = True
        p.vigor_max = 100
        p.spirit_max = 100

        with patch("backend.data.maps_data.MAPS", fake_map), \
             patch("backend.systems.reputation.push_event"):
            save_system.respawn_at_supply_point(p)

        assert p.map_id == "world"
        assert p.px == DEFAULT_RESPAWN_X
        assert p.py == DEFAULT_RESPAWN_Y

    def test_save_invalid_player_id_raises(self, tmp_path):
        from backend.systems import save_system

        p = make_player(player_id="../etc/passwd", display_name="恶意")
        with patch.object(save_system, "SAVE_DIR", tmp_path):
            try:
                save_system.save_game(p)
                raise AssertionError("Should have raised ValueError")
            except ValueError:
                pass

    def test_load_permadeath_dead_raises(self, tmp_path):
        from backend.systems import save_system

        p = make_player(player_id="perma_dead", display_name="真死侠")
        p.permadeath = True
        p.dead = True

        with patch.object(save_system, "SAVE_DIR", tmp_path):
            save_system.save_game(p)
            try:
                save_system.load_game("perma_dead")
                raise AssertionError("Should have raised ValueError")
            except ValueError:
                pass


class TestConfig:
    def test_settings_defaults(self):
        from backend.config import Settings

        f = Settings.model_fields
        assert f["llm_base_url"].default == ""
        assert f["llm_api_key"].default == ""
        assert f["llm_model"].default == ""
        assert f["llm_pool_max_connections"].default == 100
        assert f["llm_pool_max_keepalive"].default == 20
        assert f["llm_pool_connect_timeout"].default == 10.0
        assert f["llm_pool_read_timeout"].default == 120.0
        assert f["llm_circuit_breaker"].default is True
        assert f["llm_cb_failure_threshold"].default == 3
        assert f["llm_cb_cooldown_s"].default == 15.0
        assert f["llm_cache_enabled"].default is True
        assert f["llm_cache_size"].default == 128
        assert f["llm_cache_ttl_s"].default == 300.0
        assert f["llm_max_retries"].default == 3
        assert f["llm_retry_base_delay_s"].default == 1.5
        assert f["llm_max_concurrency"].default == 8
        assert f["auto_save_interval_s"].default == 300.0
        assert f["cors_allow_origins"].default == "*"

    def test_settings_warn_empty_key(self, caplog):
        from backend.config import Settings

        with caplog.at_level(logging.WARNING, logger="config"):
            s = Settings(llm_api_key="")

        assert s.llm_api_key == ""
        assert any("LLM_API_KEY" in rec.message for rec in caplog.records)
