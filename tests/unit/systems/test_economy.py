# pyright: reportCallIssue=false
"""离线单元测试 — economy 模块"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conftest import make_player


class TestAddRemoveItems:
    def test_add_item_creates_key(self):
        from backend.systems.economy import add_items
        p = make_player()
        added = add_items(p, ["干粮"])
        assert "干粮" in p.inventory
        assert p.inventory["干粮"] == 1
        assert added == ["干粮"]

    def test_add_item_stacks(self):
        from backend.systems.economy import add_items
        p = make_player()
        add_items(p, ["干粮"])
        add_items(p, ["干粮"])
        assert p.inventory["干粮"] == 2

    def test_add_item_dedup(self):
        from backend.systems.economy import add_items
        p = make_player()
        add_items(p, ["干粮", "干粮", "金创药"])
        assert p.inventory["干粮"] == 2
        assert p.inventory["金创药"] == 1

    def test_add_item_empty_name_skipped(self):
        from backend.systems.economy import add_items
        p = make_player()
        add_items(p, ["", "  ", "干粮"])
        assert len(p.inventory) == 1

    def test_remove_item(self):
        from backend.systems.economy import add_items, remove_items
        p = make_player()
        add_items(p, ["干粮", "干粮"])
        lost = remove_items(p, ["干粮"])
        assert p.inventory["干粮"] == 1
        assert lost == ["干粮"]

    def test_remove_item_deletes_at_zero(self):
        from backend.systems.economy import add_items, remove_items
        p = make_player()
        add_items(p, ["干粮"])
        remove_items(p, ["干粮"])
        assert "干粮" not in p.inventory

    def test_remove_item_not_owned_skipped(self):
        from backend.systems.economy import remove_items
        p = make_player()
        lost = remove_items(p, ["不存在的物品"])
        assert lost == []


class TestApplyCoinDelta:
    def test_positive_delta(self):
        from backend.systems.economy import apply_coin_delta
        p = make_player(coins=50)
        delta = apply_coin_delta(p, 30)
        assert p.coins == 80
        assert delta == 30

    def test_negative_delta(self):
        from backend.systems.economy import apply_coin_delta
        p = make_player(coins=50)
        delta = apply_coin_delta(p, -20)
        assert p.coins == 30
        assert delta == -20

    def test_negative_delta_clamped(self):
        from backend.systems.economy import apply_coin_delta
        p = make_player(coins=10)
        delta = apply_coin_delta(p, -50)
        assert p.coins == 0
        assert delta == -10


class TestApplyNpcTrade:
    def test_npc_gives_item_player_receives(self):
        from backend.systems.economy import apply_npc_trade
        p = make_player()
        p.npc_inventories["zhanggui"] = {"干粮": 3}
        received = apply_npc_trade(p, "zhanggui", [], ["干粮"])
        assert "干粮" in p.inventory
        assert p.inventory["干粮"] == 1
        assert p.npc_inventories["zhanggui"]["干粮"] == 2
        assert received == ["干粮"]

    def test_npc_no_stock_skipped(self):
        from backend.systems.economy import apply_npc_trade
        p = make_player()
        p.npc_inventories["zhanggui"] = {}
        received = apply_npc_trade(p, "zhanggui", [], ["干粮"])
        assert "干粮" not in p.inventory
        assert received == []

    def test_npc_zero_stock_skipped(self):
        from backend.systems.economy import apply_npc_trade
        p = make_player()
        p.npc_inventories["zhanggui"] = {"干粮": 0}
        received = apply_npc_trade(p, "zhanggui", [], ["干粮"])
        assert "干粮" not in p.inventory
        assert received == []

    def test_npc_stock_depleted_key_removed(self):
        from backend.systems.economy import apply_npc_trade
        p = make_player()
        p.npc_inventories["zhanggui"] = {"干粮": 1}
        apply_npc_trade(p, "zhanggui", [], ["干粮"])
        assert "干粮" not in p.npc_inventories["zhanggui"]

    def test_player_gives_item_npc_receives(self):
        from backend.systems.economy import apply_npc_trade
        p = make_player()
        p.npc_inventories["zhanggui"] = {}
        received = apply_npc_trade(p, "zhanggui", ["信物"], [])
        assert p.npc_inventories["zhanggui"]["信物"] == 1
        assert received == []

    def test_duplicate_items_npc_insufficient(self):
        from backend.systems.economy import apply_npc_trade
        p = make_player()
        p.npc_inventories["zhanggui"] = {"干粮": 1}
        received = apply_npc_trade(p, "zhanggui", [], ["干粮", "干粮"])
        assert p.inventory["干粮"] == 1
        assert received == ["干粮"]


class TestUsePlayerItem:
    def test_use_item_tracker_day_reset_preserves_survival_keys(self):
        from backend.systems.economy import use_player_item
        p = make_player()
        p.inventory["干粮"] = 5
        p.item_use_tracker = {"_day": 1, "fish_1": 2, "fruit_1": 1}
        p.world_day = 2
        use_player_item(p, "干粮")
        assert "fish_1" in p.item_use_tracker
        assert "fruit_1" in p.item_use_tracker
        assert p.item_use_tracker["_day"] == 2
