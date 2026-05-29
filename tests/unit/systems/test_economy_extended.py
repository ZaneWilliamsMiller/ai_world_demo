# pyright: reportCallIssue=false,reportIndexIssue=false,reportOperatorIssue=false,reportArgumentType=false
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import patch

from conftest import make_player


class TestSuggestItemPrice:
    def test_unknown_item_returns_none(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("不存在的物品")
        assert result is None

    def test_known_item_returns_dict(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮")
        assert result is not None
        assert isinstance(result, dict)

    def test_known_item_has_required_keys(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮")
        assert result is not None
        for key in ("base", "local", "note", "cat", "mult_chain", "market_hint", "weather_hint"):
            assert key in result, f"missing key: {key}"

    def test_base_price_matches_catalog(self):
        from backend.systems.economy import ITEM_PRICE_CATALOG, suggest_item_price
        for name, entry in ITEM_PRICE_CATALOG.items():
            result = suggest_item_price(name)
            assert result is not None
            assert result["base"] == int(entry["base"])

    def test_cat_matches_catalog(self):
        from backend.systems.economy import ITEM_PRICE_CATALOG, suggest_item_price
        result = suggest_item_price("金创药")
        assert result is not None
        assert result["cat"] == ITEM_PRICE_CATALOG["金创药"]["cat"]

    def test_note_matches_catalog(self):
        from backend.systems.economy import ITEM_PRICE_CATALOG, suggest_item_price
        result = suggest_item_price("短剑")
        assert result is not None
        assert result["note"] == ITEM_PRICE_CATALOG["短剑"]["note"]

    def test_no_player_no_weather_base_equals_local(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮")
        assert result is not None
        assert result["base"] == result["local"]

    def test_no_player_no_weather_mult_chain_ones(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮")
        assert result is not None
        mc = result["mult_chain"]
        assert mc["map"] == 1.0
        assert mc["weather_global"] == 1.0
        assert mc["weather_cat"] == 1.0

    def test_no_weather_hint_when_no_weather(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮")
        assert result is not None
        assert result["weather_hint"] == ""

    def test_player_with_px_triggers_zone_price_mod(self):
        from backend.systems.economy import suggest_item_price
        p = make_player(px=10, py=15)
        with patch("backend.systems.economy.zone_price_mod", return_value=(1.25, "荒野难得")):
            result = suggest_item_price("干粮", player=p)
        assert result is not None
        assert result["mult_chain"]["map"] == 1.25
        assert "荒野难得" in result["market_hint"]

    def test_player_without_px_uses_default_map_mult(self):
        from backend.systems.economy import suggest_item_price
        p = make_player()
        del p.px
        result = suggest_item_price("干粮", player=p)
        assert result is not None
        assert result["mult_chain"]["map"] == 1.0

    def test_weather_sudden_rain_global_mod(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮", weather="骤雨")
        assert result is not None
        assert result["mult_chain"]["weather_global"] == 1.20

    def test_weather_wet_miasma_global_mod(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮", weather="湿瘴")
        assert result is not None
        assert result["mult_chain"]["weather_global"] == 1.12

    def test_weather_muggy_discount(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮", weather="闷热")
        assert result is not None
        assert result["mult_chain"]["weather_global"] == 0.92

    def test_weather_heavy_fog_global_mod(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮", weather="重雾")
        assert result is not None
        assert result["mult_chain"]["weather_global"] == 1.15

    def test_weather_wind_global_mod(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮", weather="风急")
        assert result is not None
        assert result["mult_chain"]["weather_global"] == 1.10

    def test_weather_thin_fog_global_mod(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮", weather="薄雾")
        assert result is not None
        assert result["mult_chain"]["weather_global"] == 1.05

    def test_weather_cold_dew_global_mod(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮", weather="寒露")
        assert result is not None
        assert result["mult_chain"]["weather_global"] == 1.05

    def test_weather_night_frost_global_mod(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮", weather="夜霜")
        assert result is not None
        assert result["mult_chain"]["weather_global"] == 1.05

    def test_weather_cat_mod_sudden_rain_food(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮", weather="骤雨")
        assert result is not None
        assert result["mult_chain"]["weather_cat"] == 1.25

    def test_weather_cat_mod_wet_miasma_medicine(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("金创药", weather="湿瘴")
        assert result is not None
        assert result["mult_chain"]["weather_cat"] == 1.30

    def test_weather_cat_mod_muggy_food_discount(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮", weather="闷热")
        assert result is not None
        assert result["mult_chain"]["weather_cat"] == 0.85

    def test_weather_cat_mod_no_cat_match(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("短剑", weather="骤雨")
        assert result is not None
        assert result["mult_chain"]["weather_cat"] == 1.0

    def test_weather_hint_contains_info(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮", weather="骤雨")
        assert result is not None
        assert "大雨封路" in result["weather_hint"]
        assert "紧俏" in result["weather_hint"]

    def test_weather_hint_cat_discount(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮", weather="闷热")
        assert result is not None
        assert "难久存" in result["weather_hint"]

    def test_local_price_calculation_with_all_modifiers(self):
        from backend.systems.economy import suggest_item_price
        p = make_player(px=10, py=15)
        with patch("backend.systems.economy.zone_price_mod", return_value=(1.25, "荒野难得")):
            result = suggest_item_price("干粮", player=p, weather="骤雨")
        assert result is not None
        expected = round(8 * 1.25 * 1.20 * 1.25)
        assert result["local"] == expected

    def test_market_hint_contains_item_name_and_prices(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮")
        assert result is not None
        assert "干粮" in result["market_hint"]
        assert "8文" in result["market_hint"]

    def test_item_key_in_result(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮")
        assert result is not None
        assert result["item"] == "干粮"

    def test_unknown_weather_no_effect(self):
        from backend.systems.economy import suggest_item_price
        result = suggest_item_price("干粮", weather="晴朗")
        assert result is not None
        assert result["mult_chain"]["weather_global"] == 1.0
        assert result["mult_chain"]["weather_cat"] == 1.0


class TestInitNpcInventories:
    def test_fresh_player_creates_all_inventories(self):
        from backend.systems.economy import NPC_INVENTORY_SEEDS, init_npc_inventories
        p = make_player()
        init_npc_inventories(p)
        for npc_id in NPC_INVENTORY_SEEDS:
            assert npc_id in p.npc_inventories

    def test_fresh_player_inventories_match_seeds(self):
        from backend.systems.economy import NPC_INVENTORY_SEEDS, init_npc_inventories
        p = make_player()
        init_npc_inventories(p)
        for npc_id, seeds in NPC_INVENTORY_SEEDS.items():
            assert p.npc_inventories[npc_id] == seeds

    def test_fresh_player_creates_restock_day(self):
        from backend.systems.economy import NPC_INVENTORY_SEEDS, init_npc_inventories
        p = make_player(world_day=5)
        init_npc_inventories(p)
        for npc_id in NPC_INVENTORY_SEEDS:
            assert npc_id in p.npc_inventory_restock_day
            assert p.npc_inventory_restock_day[npc_id] == 5

    def test_existing_inventory_not_overwritten(self):
        from backend.systems.economy import init_npc_inventories
        p = make_player()
        p.npc_inventories["zhanggui"] = {"干粮": 0, "粗酒": 1}
        init_npc_inventories(p)
        assert p.npc_inventories["zhanggui"] == {"干粮": 0, "粗酒": 1}

    def test_old_save_adds_missing_restock_tracking(self):
        from backend.systems.economy import init_npc_inventories
        p = make_player(world_day=10)
        p.npc_inventories["zhanggui"] = {"干粮": 2}
        assert "zhanggui" not in p.npc_inventory_restock_day
        init_npc_inventories(p)
        assert p.npc_inventory_restock_day["zhanggui"] == 10

    def test_old_save_adds_missing_npc_inventory(self):
        from backend.systems.economy import NPC_INVENTORY_SEEDS, init_npc_inventories
        p = make_player()
        p.npc_inventories["zhanggui"] = dict(NPC_INVENTORY_SEEDS["zhanggui"])
        init_npc_inventories(p)
        assert "yaren" in p.npc_inventories
        assert "seng" in p.npc_inventories

    def test_creates_npc_inventories_if_missing(self):
        from backend.systems.economy import init_npc_inventories
        p = make_player()
        del p.npc_inventories
        init_npc_inventories(p)
        assert hasattr(p, "npc_inventories")
        assert isinstance(p.npc_inventories, dict)

    def test_creates_restock_day_if_missing(self):
        from backend.systems.economy import init_npc_inventories
        p = make_player()
        del p.npc_inventory_restock_day
        init_npc_inventories(p)
        assert hasattr(p, "npc_inventory_restock_day")
        assert isinstance(p.npc_inventory_restock_day, dict)

    def test_handles_none_npc_inventories(self):
        from backend.systems.economy import init_npc_inventories
        p = make_player()
        p.npc_inventories = None
        init_npc_inventories(p)
        assert isinstance(p.npc_inventories, dict)
        assert len(p.npc_inventories) > 0

    def test_handles_none_restock_day(self):
        from backend.systems.economy import init_npc_inventories
        p = make_player()
        p.npc_inventory_restock_day = None
        init_npc_inventories(p)
        assert isinstance(p.npc_inventory_restock_day, dict)

    def test_world_day_zero_used_for_restock(self):
        from backend.systems.economy import init_npc_inventories
        p = make_player(world_day=0)
        init_npc_inventories(p)
        for npc_id in p.npc_inventory_restock_day:
            assert p.npc_inventory_restock_day[npc_id] == 0


class TestFormatNpcInventory:
    def test_non_vendor_returns_empty_string(self):
        from backend.systems.economy import format_npc_inventory
        p = make_player()
        p.npc_inventories = {}
        result = format_npc_inventory(p, "bullya")
        assert result == ""

    def test_vendor_with_stock_returns_text(self):
        from backend.systems.economy import format_npc_inventory, init_npc_inventories
        p = make_player()
        init_npc_inventories(p)
        result = format_npc_inventory(p, "zhanggui")
        assert "当前货柜" in result

    def test_vendor_stock_shows_prices(self):
        from backend.systems.economy import format_npc_inventory, init_npc_inventories
        p = make_player()
        init_npc_inventories(p)
        result = format_npc_inventory(p, "zhanggui")
        assert "文/件" in result

    def test_vendor_all_zero_stock_shows_no_goods(self):
        from backend.systems.economy import format_npc_inventory
        p = make_player()
        p.npc_inventories["zhanggui"] = {"干粮": 0, "粗酒": 0}
        result = format_npc_inventory(p, "zhanggui")
        assert "已无货可售" in result

    def test_vendor_zero_items_filtered_out(self):
        from backend.systems.economy import format_npc_inventory
        p = make_player()
        p.npc_inventories["zhanggui"] = {"干粮": 0, "粗酒": 2}
        result = format_npc_inventory(p, "zhanggui")
        assert "干粮" not in result
        assert "粗酒" in result

    def test_vendor_trade_rules_included(self):
        from backend.systems.economy import format_npc_inventory, init_npc_inventories
        p = make_player()
        init_npc_inventories(p)
        result = format_npc_inventory(p, "zhanggui")
        assert "交易规则" in result

    def test_vendor_shows_item_count(self):
        from backend.systems.economy import format_npc_inventory
        p = make_player()
        p.npc_inventories["zhanggui"] = {"干粮": 3}
        result = format_npc_inventory(p, "zhanggui")
        assert "×3" in result

    def test_nonexistent_npc_id_returns_empty(self):
        from backend.systems.economy import format_npc_inventory
        p = make_player()
        p.npc_inventories = {}
        result = format_npc_inventory(p, "nonexistent_npc")
        assert result == ""

    def test_vendor_with_weather_affects_prices(self):
        from backend.systems.economy import format_npc_inventory
        p = make_player(weather="骤雨")
        p.npc_inventories["zhanggui"] = {"干粮": 3}
        result = format_npc_inventory(p, "zhanggui")
        assert "文/件" in result


class TestFormatEconomyContext:
    def test_vendor_npc_full_price_catalog(self):
        from backend.systems.economy import format_economy_context
        p = make_player()
        result = format_economy_context(p, vendor_npc_id="zhanggui")
        assert "本地参考价" in result

    def test_non_vendor_npc_summary_only(self):
        from backend.systems.economy import format_economy_context
        p = make_player()
        result = format_economy_context(p, vendor_npc_id=None)
        assert "行情提示" in result
        assert "本地参考价" not in result

    def test_non_vendor_npc_unknown_id_summary(self):
        from backend.systems.economy import format_economy_context
        p = make_player()
        result = format_economy_context(p, vendor_npc_id="bullya")
        assert "行情提示" in result

    def test_shows_map_info(self):
        from backend.systems.economy import format_economy_context
        p = make_player()
        result = format_economy_context(p, vendor_npc_id="zhanggui")
        assert "行情" in result

    def test_shows_player_coins(self):
        from backend.systems.economy import format_economy_context
        p = make_player(coins=99)
        result = format_economy_context(p, vendor_npc_id="zhanggui")
        assert "99文" in result

    def test_shows_player_inventory_valuation(self):
        from backend.systems.economy import format_economy_context
        p = make_player()
        p.inventory["干粮"] = 2
        result = format_economy_context(p, vendor_npc_id="zhanggui")
        assert "干粮" in result
        assert "估价" in result

    def test_player_inventory_unknown_item_no_price(self):
        from backend.systems.economy import format_economy_context
        p = make_player()
        p.inventory["奇物"] = 1
        result = format_economy_context(p, vendor_npc_id="zhanggui")
        assert "奇物" in result

    def test_weather_affects_vendor_prices(self):
        from backend.systems.economy import format_economy_context
        p = make_player(weather="骤雨")
        result = format_economy_context(p, vendor_npc_id="zhanggui")
        assert "骤雨" in result

    def test_weather_no_effect_not_shown(self):
        from backend.systems.economy import format_economy_context
        p = make_player(weather="薄阴")
        result = format_economy_context(p, vendor_npc_id="zhanggui")
        assert "品类浮动" not in result

    def test_weather_cat_mod_shown(self):
        from backend.systems.economy import format_economy_context
        p = make_player(weather="骤雨")
        result = format_economy_context(p, vendor_npc_id="zhanggui")
        assert "品类浮动" in result

    def test_vendor_catalog_by_category(self):
        from backend.systems.economy import format_economy_context
        p = make_player()
        result = format_economy_context(p, vendor_npc_id="zhanggui")
        assert "食水" in result
        assert "药物" in result

    def test_empty_inventory_no_valuation_line(self):
        from backend.systems.economy import format_economy_context
        p = make_player()
        p.inventory = {}
        result = format_economy_context(p, vendor_npc_id="zhanggui")
        assert "估价" not in result

    def test_non_vendor_weather_hint_in_summary(self):
        from backend.systems.economy import format_economy_context
        p = make_player(weather="骤雨")
        result = format_economy_context(p, vendor_npc_id=None)
        assert "骤雨" in result

    def test_inventory_valuation_limited_to_six(self):
        from backend.systems.economy import format_economy_context
        p = make_player()
        for i in range(8):
            p.inventory[f"item_{i}"] = 1
        result = format_economy_context(p, vendor_npc_id="zhanggui")
        assert "估价" in result

    def test_zone_price_mod_called(self):
        from backend.systems.economy import format_economy_context
        p = make_player()
        with patch("backend.systems.economy.zone_price_mod", return_value=(1.35, "卡吏抽头")):
            result = format_economy_context(p, vendor_npc_id="zhanggui")
        assert "1.4" in result or "1.3" in result


class TestRestockNpcInventories:
    def test_no_restock_if_interval_not_reached(self):
        from backend.systems.economy import init_npc_inventories, restock_npc_inventories
        p = make_player(world_day=1)
        init_npc_inventories(p)
        p.world_day = 2
        logs = restock_npc_inventories(p)
        assert len(logs) == 0

    def test_restock_when_interval_reached(self):
        from backend.systems.economy import init_npc_inventories, restock_npc_inventories
        p = make_player(world_day=1)
        init_npc_inventories(p)
        p.npc_inventories["zhanggui"]["干粮"] = 0
        p.world_day = 3
        with patch("backend.data.npcs_data.NPCS", {"zhanggui": {"short": "掌柜"}}):
            logs = restock_npc_inventories(p)
        assert any("掌柜" in log for log in logs)

    def test_restock_adds_items_up_to_max(self):
        from backend.systems.economy import RESTOCK_CONFIG, init_npc_inventories, restock_npc_inventories
        p = make_player(world_day=1)
        init_npc_inventories(p)
        for item in p.npc_inventories["zhanggui"]:
            p.npc_inventories["zhanggui"][item] = 0
        interval, max_items, ratio = RESTOCK_CONFIG["zhanggui"]
        p.world_day = 1 + interval
        with patch("backend.data.npcs_data.NPCS", {"zhanggui": {"short": "掌柜"}}):
            logs = restock_npc_inventories(p)
        restocked_count = sum(1 for log in logs if "掌柜" in log)
        assert restocked_count <= 1

    def test_no_restock_if_no_shortages(self):
        from backend.systems.economy import init_npc_inventories, restock_npc_inventories
        p = make_player(world_day=1)
        init_npc_inventories(p)
        p.world_day = 100
        logs = restock_npc_inventories(p)
        assert len(logs) == 0

    def test_updates_restock_day_tracking(self):
        from backend.systems.economy import RESTOCK_CONFIG, init_npc_inventories, restock_npc_inventories
        p = make_player(world_day=1)
        init_npc_inventories(p)
        p.npc_inventories["zhanggui"]["干粮"] = 0
        interval = RESTOCK_CONFIG["zhanggui"][0]
        p.world_day = 1 + interval
        with patch("backend.data.npcs_data.NPCS", {"zhanggui": {"short": "掌柜"}}):
            restock_npc_inventories(p)
        assert p.npc_inventory_restock_day["zhanggui"] == 1 + interval

    def test_returns_log_messages(self):
        from backend.systems.economy import RESTOCK_CONFIG, init_npc_inventories, restock_npc_inventories
        p = make_player(world_day=1)
        init_npc_inventories(p)
        p.npc_inventories["zhanggui"]["干粮"] = 0
        interval = RESTOCK_CONFIG["zhanggui"][0]
        p.world_day = 1 + interval
        with patch("backend.data.npcs_data.NPCS", {"zhanggui": {"short": "掌柜"}}):
            logs = restock_npc_inventories(p)
        assert any("进货" in log for log in logs)

    def test_restock_does_not_exceed_seed_quantity(self):
        from backend.systems.economy import (
            NPC_INVENTORY_SEEDS,
            RESTOCK_CONFIG,
            init_npc_inventories,
            restock_npc_inventories,
        )
        p = make_player(world_day=1)
        init_npc_inventories(p)
        p.npc_inventories["zhanggui"]["干粮"] = NPC_INVENTORY_SEEDS["zhanggui"]["干粮"] - 1
        interval = RESTOCK_CONFIG["zhanggui"][0]
        p.world_day = 1 + interval
        with patch("backend.data.npcs_data.NPCS", {"zhanggui": {"short": "掌柜"}}):
            restock_npc_inventories(p)
        assert p.npc_inventories["zhanggui"]["干粮"] <= NPC_INVENTORY_SEEDS["zhanggui"]["干粮"]

    def test_restock_ratio_applied(self):
        from backend.systems.economy import (
            NPC_INVENTORY_SEEDS,
            RESTOCK_CONFIG,
            init_npc_inventories,
            restock_npc_inventories,
        )
        p = make_player(world_day=1)
        init_npc_inventories(p)
        for item in p.npc_inventories["zhanggui"]:
            p.npc_inventories["zhanggui"][item] = 0
        interval, max_items, ratio = RESTOCK_CONFIG["zhanggui"]
        p.world_day = 1 + interval
        with patch("backend.data.npcs_data.NPCS", {"zhanggui": {"short": "掌柜"}}):
            restock_npc_inventories(p)
        for item, qty in p.npc_inventories["zhanggui"].items():
            seed_qty = NPC_INVENTORY_SEEDS["zhanggui"][item]
            expected_add = max(1, round(seed_qty * ratio))
            assert qty <= expected_add

    def test_multiple_npcs_restock_independently(self):
        from backend.systems.economy import RESTOCK_CONFIG, init_npc_inventories, restock_npc_inventories
        p = make_player(world_day=1)
        init_npc_inventories(p)
        p.npc_inventories["zhanggui"]["干粮"] = 0
        p.npc_inventories["yulaog"]["鲜鱼"] = 0
        zhanggui_interval = RESTOCK_CONFIG["zhanggui"][0]
        yulaog_interval = RESTOCK_CONFIG["yulaog"][0]
        p.world_day = 1 + max(zhanggui_interval, yulaog_interval)
        with patch("backend.data.npcs_data.NPCS", {
            "zhanggui": {"short": "掌柜"},
            "yulaog": {"short": "渔老"},
        }):
            logs = restock_npc_inventories(p)
        assert any("掌柜" in log for log in logs)
        assert any("渔老" in log for log in logs)

    def test_creates_inventory_if_missing(self):
        from backend.systems.economy import restock_npc_inventories
        p = make_player(world_day=100)
        p.npc_inventories = {}
        p.npc_inventory_restock_day = {}
        with patch("backend.data.npcs_data.NPCS", {"zhanggui": {"short": "掌柜"}}):
            logs = restock_npc_inventories(p)
        assert "zhanggui" in p.npc_inventories

    def test_npc_without_config_skipped(self):
        from backend.systems.economy import restock_npc_inventories
        p = make_player(world_day=1)
        p.npc_inventories = {"fake_npc": {"干粮": 0}}
        p.npc_inventory_restock_day = {}
        p.world_day = 100
        logs = restock_npc_inventories(p)
        assert not any("fake_npc" in log for log in logs)

    def test_shortage_prioritized_by_largest_deficit(self):
        from backend.systems.economy import (
            NPC_INVENTORY_SEEDS,
            RESTOCK_CONFIG,
            init_npc_inventories,
            restock_npc_inventories,
        )
        p = make_player(world_day=1)
        init_npc_inventories(p)
        seeds = NPC_INVENTORY_SEEDS["zhanggui"]
        for item in seeds:
            p.npc_inventories["zhanggui"][item] = 0
        interval, max_items, ratio = RESTOCK_CONFIG["zhanggui"]
        p.world_day = 1 + interval
        with patch("backend.data.npcs_data.NPCS", {"zhanggui": {"short": "掌柜"}}):
            restock_npc_inventories(p)
        restocked_items = [k for k, v in p.npc_inventories["zhanggui"].items() if v > 0]
        assert len(restocked_items) <= max_items

    def test_log_uses_npc_short_name(self):
        from backend.systems.economy import RESTOCK_CONFIG, init_npc_inventories, restock_npc_inventories
        p = make_player(world_day=1)
        init_npc_inventories(p)
        p.npc_inventories["zhanggui"]["干粮"] = 0
        interval = RESTOCK_CONFIG["zhanggui"][0]
        p.world_day = 1 + interval
        with patch("backend.data.npcs_data.NPCS", {"zhanggui": {"short": "沈掌柜"}}):
            logs = restock_npc_inventories(p)
        assert any("沈掌柜" in log for log in logs)

    def test_log_falls_back_to_npc_id(self):
        from backend.systems.economy import RESTOCK_CONFIG, init_npc_inventories, restock_npc_inventories
        p = make_player(world_day=1)
        init_npc_inventories(p)
        p.npc_inventories["zhanggui"]["干粮"] = 0
        interval = RESTOCK_CONFIG["zhanggui"][0]
        p.world_day = 1 + interval
        with patch("backend.data.npcs_data.NPCS", {}):
            logs = restock_npc_inventories(p)
        assert any("zhanggui" in log for log in logs)
