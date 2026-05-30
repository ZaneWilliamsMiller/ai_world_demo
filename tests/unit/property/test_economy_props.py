from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.systems.economy import (
    NPC_INVENTORY_SEEDS,
    add_items,
    apply_coin_delta,
    apply_npc_trade,
    restock_npc_inventories,
)
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.property.strategies import st_inventory_item, st_player_state


@settings(max_examples=50)
@given(st_player_state(), st_inventory_item())
def test_buy_item_reduces_coins(p, item_name):
    old_coins = p.coins
    delta = apply_coin_delta(p, -10)
    assert p.coins <= old_coins
    assert p.coins >= 0


@settings(max_examples=50)
@given(st_player_state(), st_inventory_item())
def test_buy_item_reduces_npc_stock(p, item_name):
    npc_id = "zhanggui"
    p.npc_inventories[npc_id] = dict(NPC_INVENTORY_SEEDS.get(npc_id, {}))
    old_stock = p.npc_inventories[npc_id].get(item_name, 0)
    if old_stock <= 0:
        return
    apply_npc_trade(p, npc_id, [], [item_name])
    new_stock = p.npc_inventories[npc_id].get(item_name, 0)
    assert new_stock == old_stock - 1


@settings(max_examples=50)
@given(st_player_state(), st_inventory_item())
def test_sell_item_increases_coins(p, item_name):
    add_items(p, [item_name])
    old_coins = p.coins
    apply_coin_delta(p, 15)
    assert p.coins >= old_coins


@settings(max_examples=50)
@given(st_player_state())
def test_restock_does_not_exceed_seed_cap(p):
    for npc_id, seeds in NPC_INVENTORY_SEEDS.items():
        p.npc_inventories[npc_id] = dict(seeds)
        p.npc_inventory_restock_day[npc_id] = 0
    p.world_day = 999
    restock_npc_inventories(p)
    for npc_id, seeds in NPC_INVENTORY_SEEDS.items():
        inv = p.npc_inventories.get(npc_id, {})
        for item, seed_qty in seeds.items():
            assert inv.get(item, 0) <= seed_qty


@settings(max_examples=50)
@given(st_player_state(), st.integers(-99999, 99999))
def test_coins_always_nonnegative(p, delta):
    apply_coin_delta(p, delta)
    assert p.coins >= 0
