from __future__ import annotations

from backend.models.player import PlayerState
from backend.data.maps_data import MAPS
from backend.data.zones import zone_price_mod

# ════════════════════════════════════════════════════════════════════
#  物品定价表 — 江湖百业行情（单位：制钱/文）
# ════════════════════════════════════════════════════════════════════
#  定价逻辑：
#    · 基准价：普通市口价，不溢价不折扣
#    · 地图溢价：偏远/特定地图加价（黑店 I、荒野 &、渡口 ~）
#    · 地图折扣：产区地图减价（碾坊粮食、渡口鱼鲜）
#  此表供 NPC 对话时参考，LLM 应以它为底讨价还价。
ITEM_PRICE_CATALOG: dict[str, dict[str, object]] = {
    # ── 干粮食水 ──
    "干粮":    {"base": 8,   "note": "一包干饼/炒面，可果腹一餐", "cat": "食"},
    "鲜鱼":    {"base": 15,  "note": "现打河鱼，渡口常见", "cat": "食"},
    "野果":    {"base": 5,   "note": "林地野果，不怎么值钱", "cat": "食"},
    "粗酒":    {"base": 12,  "note": "村酿劣酒", "cat": "食"},
    "熟牛肉":  {"base": 30,  "note": "客栈招牌，饱腹力道足", "cat": "食"},
    "茶饼":    {"base": 6,   "note": "苦茶饼，嚼一口解乏", "cat": "食"},
    # ── 文书信物 ──
    "路引":    {"base": 80,  "note": "官发通行凭证，过卡必备", "cat": "文"},
    "信函":    {"base": 10,  "note": "书信，视内容可翻倍", "cat": "文"},
    "信物":    {"base": 50,  "note": "可做凭证的贴身物件，因人而异", "cat": "文"},
    "帖子":    {"base": 25,  "note": "拜帖/请帖，人情价不定", "cat": "文"},
    "缉文":    {"base": 60,  "note": "官府缉捕文书，危险但有价", "cat": "文"},
    "地图":    {"base": 40,  "note": "手绘舆图，视精度溢价", "cat": "文"},
    # ── 药物 ──
    "金创药":  {"base": 35,  "note": "止血散瘀，江湖必备", "cat": "药"},
    "解毒丸":  {"base": 45,  "note": "解瘴气蛇毒，保命的", "cat": "药"},
    "安神散":  {"base": 20,  "note": "宁心助眠，书院客栈多见", "cat": "药"},
    "蒙汗药":  {"base": 55,  "note": "黑货，一般市面不公开卖", "cat": "药"},
    # ── 日用杂物 ──
    "火折":    {"base": 5,   "note": "引火小物件", "cat": "物"},
    "草绳":    {"base": 3,   "note": "捆东西用", "cat": "物"},
    "瓷瓶":    {"base": 20,  "note": "盛水/盛药，碰碎就不值了", "cat": "物"},
    "斗笠":    {"base": 10,  "note": "挡雨遮阳", "cat": "物"},
    "雨蓑":    {"base": 18,  "note": "蓑衣，江湖人常备", "cat": "物"},
    # ── 兵器/护具 ──
    "柴刀":    {"base": 25,  "note": "砍柴兼防身，粗笨但实用", "cat": "兵"},
    "短剑":    {"base": 80,  "note": "江湖人随身，好坏价差悬殊", "cat": "兵"},
    "匕首":    {"base": 40,  "note": "藏身利刃，黑市常见", "cat": "兵"},
    "铁护腕":  {"base": 30,  "note": "挡暗器用的", "cat": "兵"},
}


# ════════════════════════════════════════════════════════════════════
#  物品消耗效果表 — 进食/用药的身心效用（🎮 游戏性扩展）
# ════════════════════════════════════════════════════════════════════
#  设计原则：
#    · 食物类（食）：主攻体力恢复，轻度心气恢复
#    · 药物类（药）：针对性效用（止血/解毒/安神），不进战斗但影响状态
#    · 杂物类（物）：大部分不可消耗，火折是例外（照明用，消耗品）
#    · 兵器/信物：不在此表（不可消耗，装备/持有类）
#
#  字段说明：
#    vigor:  体力变化（+恢复/-消耗）
#    spirit: 心气变化
#    sleep_debt: 睡眠债变化（负值=减少=好转）
#    note:   消耗后的叙事描述
#    max_per_day: 每日最多生效次数（防滥用，0=不限制）
#    requires_tile: 需要特定地形才能使用（如"睡"需要客栈/寺廊）
#
ITEM_USE_EFFECTS: dict[str, dict[str, object]] = {
    # ── 食物：饱腹回体 ──
    "干粮":     {"vigor": +18, "spirit": +6,  "sleep_debt": 0,  "note": "你嚼了几口干粮，粗粝但管饱，气力略回。", "max_per_day": 3},
    "鲜鱼":     {"vigor": +22, "spirit": +8,  "sleep_debt": 0,  "note": "你就着江水刮了几片生鱼，冷鲜却回力极快。", "max_per_day": 2},
    "野果":     {"vigor": +10, "spirit": +4,  "sleep_debt": 0,  "note": "你嚼了几口野果，甜涩交织，勉强充饥。", "max_per_day": 5},
    "粗酒":     {"vigor": -5,  "spirit": +14, "sleep_debt": -3, "note": "你灌了一碗浊酒，身子更乏了，心口却烧起一股热气。", "max_per_day": 2},
    "熟牛肉":   {"vigor": +32, "spirit": +10, "sleep_debt": 0,  "note": "你大口嚼了熟牛肉，油香满颊，浑身都是力气。", "max_per_day": 2},
    "茶饼":     {"vigor": +6,  "spirit": +10, "sleep_debt": -2, "note": "你嚼了半块茶饼，微苦回甘，夜读般的清醒漫上来。", "max_per_day": 4},
    # ── 药物：对症下药 ──
    "金创药":   {"vigor": +28, "spirit": 0,   "sleep_debt": 0,  "note": "你敷上金创药，伤口一阵刺痛后清凉下来，血算止住了。", "max_per_day": 2},
    "解毒丸":   {"vigor": +8,  "spirit": +12, "sleep_debt": 0,  "note": "你吞下一粒解毒丸，喉间苦得发麻，但胸腹间那股滞涩感散了。", "max_per_day": 2},
    "安神散":   {"vigor": -4,  "spirit": +22, "sleep_debt": -6, "note": "你冲服了安神散，眼皮渐渐发沉，心口那团乱麻慢慢松开。", "max_per_day": 2},
    # ── 蒙汗药：不可自用（对 NPC 使用，此处占位） ──
    # "蒙汗药": 不可用，跳过
    # ── 杂物：火折可消耗（照明） ──
    "火折":     {"vigor": 0,   "spirit": 0,   "sleep_debt": 0,  "note": "你点亮了火折，一圈昏黄的光推开黑暗——能看清周围几步了。", "max_per_day": 3},
}

# zone_price_mod 已迁移至 backend.data.zones，此处保留引用以兼容
# 原硬编码坐标范围已统一至 ECONOMY_ZONES 配置

# 保留字典键以兼容（已废弃，改用 zone_price_mod）
MAP_PRICE_MOD: dict[str, tuple[float, str]] = {
    "world": (1.00, "市口平价"),
}

# ════════════════════════════════════════════════════════════════════
#  天气价格系数 —— 天气直接影响江湖行情（叠加地图溢价）
# ════════════════════════════════════════════════════════════════════
#  全局倍率：(weather_mult, 说明)
WEATHER_PRICE_MOD: dict[str, tuple[float, str]] = {
    "骤雨": (1.20, "大雨封路，货运行止"),
    "湿瘴": (1.12, "湿瘴弥漫，人不出户"),
    "重雾": (1.15, "浓雾锁路，货多阻滞"),
    "风急": (1.10, "风急浪高，渡口迟滞"),
    "薄雾": (1.05, "薄雾碍眼，行商稍缓"),
    "闷热": (0.92, "天热货易腐，急于出手"),
    "寒露": (1.05, "露重天凉，行脚减少"),
    "夜霜": (1.05, "霜结路滑，货担谨慎"),
    # 晴/云遮日/小风：无溢价
}

# 品类修正：特定天气下某些品类涨跌更剧（叠加在全局倍率之上）
WEATHER_CAT_MOD: dict[str, dict[str, float]] = {
    "骤雨": {"食": 1.25, "物": 1.15, "药": 1.10},
    "湿瘴": {"药": 1.30, "食": 1.15},
    "重雾": {"兵": 1.20, "文": 1.10},
    "风急": {"物": 1.20, "食": 1.10},
    "寒露": {"药": 1.25},
    "夜霜": {"药": 1.25, "食": 1.08},
    "闷热": {"食": 0.85, "药": 1.08},
}


def apply_coin_delta(p: PlayerState, delta: int | None) -> int:
    """安全更新身上制钱；返回真正生效的 delta（钱不够时缩水到 -coins）。"""
    if not delta:
        return 0
    d = max(-MAX_COIN_DELTA, min(MAX_COIN_DELTA, int(delta)))
    if d < 0 and -d > p.coins:
        d = -p.coins
    p.coins = max(0, p.coins + d)
    return d


def add_items(p: PlayerState, names: list[str]) -> list[str]:
    out: list[str] = []
    for raw in names:
        name = (raw or "").strip().strip("「」『」\"'")[:MAX_ITEM_NAME_LEN]
        if not name:
            continue
        p.inventory[name] = int(p.inventory.get(name, 0)) + 1
        out.append(name)
    return out


def remove_items(p: PlayerState, names: list[str]) -> list[str]:
    out: list[str] = []
    for raw in names:
        name = (raw or "").strip().strip("「」『」\"'")[:MAX_ITEM_NAME_LEN]
        if not name:
            continue
        if name in p.inventory:
            p.inventory[name] -= 1
            if p.inventory[name] <= 0:
                del p.inventory[name]
            out.append(name)
    return out


def suggest_item_price(item_name: str, player: Any = None, weather: str | None = None) -> dict[str, object] | None:
    """查询物品参考价，附带地区溢价与天气浮动。

    价格计算链路：基准价 × 地区系数 × 天气全局系数 × 天气品类系数
    四重乘数叠在一起，极端天气下某些品类可涨超 70%。

    返回 None 表示该物品不在定价表中（LLM 只能凭常识估）。
    返回字典包含 base（基准价）、local（当地价）、note（物品说明）、cat（品类）、weather_hint。"""
    entry = ITEM_PRICE_CATALOG.get(item_name)
    if not entry:
        return None
    base = int(entry["base"])
    cat = str(entry.get("cat", ""))

    # 地区系数（根据玩家位置判断）
    if player and hasattr(player, 'px'):
        map_mult, map_hint = zone_price_mod(player)
    else:
        map_mult, map_hint = 1.0, "市口平价"
    # 天气全局系数
    weather_global, weather_hint = WEATHER_PRICE_MOD.get(weather or "", (1.0, ""))
    # 天气品类系数
    weather_cat = WEATHER_CAT_MOD.get(weather or "", {}).get(cat, 1.0)

    total_mult = map_mult * weather_global * weather_cat
    local = int(round(base * total_mult))

    # 构建天气提示
    weather_tip = ""
    if weather and (weather_global != 1.0 or weather_cat != 1.0):
        parts = [weather_hint] if weather_hint else []
        if weather_cat < 1.0:
            parts.append(f"此品类遇{weather}难久存故而略降")
        elif weather_cat > 1.0:
            parts.append(f"此品类遇{weather}更见紧俏")
        weather_tip = "；".join(parts) if parts else ""

    # 构建市场行情提示（含地点与倍数）
    map_id_hint = ""
    if player and hasattr(player, 'map_id'):
        map_id_hint = str(getattr(player, 'map_id', ''))
    market_hint = f"{map_hint}，{item_name}当地约{local}文（基准{base}文）"

    return {
        "item": item_name,
        "base": base,
        "local": local,
        "note": str(entry.get("note", "")),
        "cat": cat,
        "mult_chain": {
            "map": round(map_mult, 2),
            "weather_global": round(weather_global, 2),
            "weather_cat": round(weather_cat, 2),
        },
        "market_hint": market_hint,
        "weather_hint": weather_tip,
    }


# ════════════════════════════════════════════════════════════════════
#  NPC 货柜初始化 — 市井商贩各有其货
# ════════════════════════════════════════════════════════════════════
NPC_INVENTORY_SEEDS: dict[str, dict[str, int]] = {
    "zhanggui": {"干粮": 4, "熟牛肉": 3, "粗酒": 5, "茶饼": 6, "火折": 4, "雨蓑": 2},
    "yaren":    {"干粮": 2, "路引": 2, "信函": 3, "帖子": 4, "地图": 2, "斗笠": 3},
    "yulaog":   {"鲜鱼": 6, "草绳": 4, "斗笠": 2, "干粮": 2, "火折": 2},
    "lizheng":  {"茶饼": 3, "干粮": 2, "信物": 1, "帖子": 2},
    "lika":     {"路引": 3, "缉文": 2, "信函": 2},
    "seng":     {"安神散": 4, "茶饼": 5, "瓷瓶": 2},
    "yizu":     {"信函": 4, "干粮": 2, "火折": 2, "地图": 1},
}


def init_npc_inventories(p: PlayerState) -> None:
    """初始化商贩 NPC 货柜。

    新玩家：全量初始化所有商贩货柜。
    老存档加载：增量补齐新增商贩（不覆盖已有货柜，避免丢失交易状态）。
    同时也初始化缺失的补货追踪。"""
    # 获取或创建 npc_inventories（兼容老存档字段丢失的情况）
    if not hasattr(p, 'npc_inventories') or p.npc_inventories is None:
        p.npc_inventories = {}
    # 获取或创建 restock_day 追踪
    if not hasattr(p, 'npc_inventory_restock_day') or p.npc_inventory_restock_day is None:
        p.npc_inventory_restock_day = {}
    current_day = int(getattr(p, 'world_day', 1) or 0)

    for npc_id, seeds in NPC_INVENTORY_SEEDS.items():
        # 已有货柜的 NPC：跳过（保留玩家交易产生的状态）
        if npc_id in p.npc_inventories:
            # 但补货追踪可能缺失（老存档兼容）
            if npc_id not in p.npc_inventory_restock_day:
                p.npc_inventory_restock_day[npc_id] = current_day
            continue
        # 新 NPC（或老存档中未注册的）：完整初始化
        p.npc_inventories[npc_id] = dict(seeds)
        p.npc_inventory_restock_day[npc_id] = current_day


def format_npc_inventory(p: PlayerState, npc_id: str) -> str:
    """生成 NPC 当前货柜文本块,供对话 prompt 注入。

    只有商贩类 NPC 才有货柜；其他 NPC 返回空字符串。"""
    inv = p.npc_inventories.get(npc_id)
    if not inv:
        # 非商贩型 NPC,但也可能在特定剧情中获得物品
        return ""

    from backend.data.npcs_data import NPCS
    # 过滤掉数量为 0 的项
    active = {k: v for k, v in inv.items() if v > 0}
    if not active:
        return "【当前货柜】你手头已无货可售。"

    # 带当地价格的清单（含天气浮动）
    lines: list[str] = ["【当前货柜——你可出售或交换的物什】"]
    for name, count in sorted(active.items()):
        price_info = suggest_item_price(name, p, p.weather)
        if price_info:
            local = price_info["local"]
            lines.append(f"  · {name} ×{count} （当地约 {local} 文/件）")
        else:
            lines.append(f"  · {name} ×{count}")
    lines.append(
        "【交易规则】玩家可购买或物物交换。\n"
        "  你可用 items_gain 写成玩家所得的物，coin_delta 记成负数是收取银钱，正数是付钱收物。\n"
        "  交易完成后你手中该物对应减少；若售罄请如实告知。"
    )
    return "\n".join(lines)


def apply_npc_trade(
    p: PlayerState, npc_id: str,
    items_given_by_player: list[str],   # 玩家交出的物（= NPC 得到）
    items_given_by_npc: list[str],      # NPC 交出的物（= 玩家得到）
) -> None:
    """在 apply_npc_reply 之后调用,同步 NPC 货柜的增减。

    注意：
    - items_given_by_player = parsed.items_lose（玩家失去 = NPC 获得）
    - items_given_by_npc    = parsed.items_gain（玩家获得 = NPC 失去）
    """
    inv = p.npc_inventories.get(npc_id)
    if inv is None:
        inv = {}
        p.npc_inventories[npc_id] = inv

    # NPC 失去的物（卖/送给玩家的）
    for raw in items_given_by_npc:
        name = (raw or "").strip().strip("「」『」\"'")[:MAX_ITEM_NAME_LEN]
        if not name:
            continue
        current = inv.get(name, 0)
        if current > 0:
            inv[name] = current - 1
        # 如果 NPC 没有但 LLM 卖了,则不扣负,允许"剧情给物"

    # NPC 得到的物（从玩家收的）
    for raw in items_given_by_player:
        name = (raw or "").strip().strip("「」『」\"'")[:MAX_ITEM_NAME_LEN]
        if not name:
            continue
        inv[name] = inv.get(name, 0) + 1


def format_economy_context(p: PlayerState, vendor_npc_id: str | None = None) -> str:
    """生成经济上下文：当前地图行情 + 天气浮动 + 玩家随身物品估价辅助。

    注入 NPC system prompt，让 LLM 在交易时有据可依，不会无中生有。

    分层注入策略（2026-05-26 优化）：
    - vendor_npc_id 非 None（商贩 NPC）→ 完整价格目录（含逐品本地价）
    - vendor_npc_id 为 None（非商贩 NPC）→ 仅行情摘要（地点+天气波动，不含逐品目录）
    此举为每轮非商贩对话节省 ~200-300 tokens，商贩对话不受影响。"""
    map_name = MAPS.get(p.map_id, {}).get("name", p.map_id)
    map_mult, map_hint = zone_price_mod(p)

    weather = p.weather
    weather_global, weather_hint = WEATHER_PRICE_MOD.get(weather, (1.0, ""))
    weather_cat_data = WEATHER_CAT_MOD.get(weather, {})

    # 判断是否为商贩 NPC（有货柜种子的 NPC 才需要完整价格目录）
    is_vendor = vendor_npc_id is not None and vendor_npc_id in NPC_INVENTORY_SEEDS

    lines = [
        f"【行情】{map_name}：{map_hint}（地图倍率约 ×{map_mult:.1f}）。",
    ]

    # 天气行情提示（只在天气有影响时注入）
    if weather_global != 1.0 or weather_cat_data:
        weather_lines = [f"天气「{weather}」：{weather_hint}（全局倍率 ×{weather_global:.2f}）"]
        if weather_cat_data:
            cat_names = {"食": "食水", "文": "文书", "药": "药物", "物": "杂物", "兵": "兵器"}
            cat_parts = []
            for c, m in weather_cat_data.items():
                label = cat_names.get(c, c)
                direction = "涨" if m > 1.0 else "跌"
                cat_parts.append(f"{label}{direction}×{m:.2f}")
            weather_lines.append("品类浮动：" + "、".join(cat_parts))
        lines.append("\n".join(weather_lines))

    # 玩家随身物品参照（所有 NPC 都需要，方便打听行情）
    if p.inventory:
        inv_vals: list[str] = []
        for name, count in sorted(p.inventory.items()):
            price_info = suggest_item_price(name, p, weather)
            if price_info:
                local = price_info["local"]
                item_total = local * int(count)
                inv_vals.append(f"{name}×{count}(≈{item_total}文)")
            else:
                inv_vals.append(f"{name}×{count}")
        if inv_vals:
            lines.append(f"· 此人随身（估价）：{'、'.join(inv_vals[:6])}")
    lines.append(f"· 此人钱袋：{p.coins}文。")

    if is_vendor:
        # ── 商贩 NPC：完整价格目录 ──
        lines.append(
            "以下是常见物品的本地参考价（单位：文/制钱），已含天气浮动。"
            "你以此为基础讨价还价，但可因关系/急迫/稀缺做 ±50% 浮动；不可离谱（如干粮卖 200 文就不合理）。"
        )
        # 列出常见品类价格（含天气修正）
        by_cat: dict[str, list[str]] = {}
        for name, entry in ITEM_PRICE_CATALOG.items():
            cat = str(entry.get("cat", ""))
            w_cat = weather_cat_data.get(cat, 1.0)
            local_price = int(round(int(entry["base"]) * map_mult * weather_global * w_cat))
            by_cat.setdefault(cat, []).append(f"{name}({local_price}文)")

        cat_names = {"食": "食水", "文": "文书", "药": "药物", "物": "杂物", "兵": "兵器"}
        for cat, items in sorted(by_cat.items()):
            label = cat_names.get(cat, cat)
            lines.append(f"· {label}：{'、'.join(items[:6])}")
    else:
        # ── 非商贩 NPC：仅行情摘要，不罗列逐品价格 ──
        lines.append(
            "【行情提示】若有人向你打听行市物价，你可用常识作答——"
            "此地的物价因" + ("天气「" + weather + "」影响，" if weather_global != 1.0 else "") +
            "远近便利程度而异。不必背报价，话到即可。"
        )

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════
#  NPC 货柜自然补货 — 市井商贩随时间进货，江湖经济流动
# ════════════════════════════════════════════════════════════════════

# 补货配置：npc_id → (补货周期/天, 每周期最多回补品种数)
# 掌柜日间进货快（同福栈有固定货郎），驿卒/里正进货慢（等过路商队）
RESTOCK_CONFIG: dict[str, tuple[int, int, float]] = {
    "zhanggui": (2, 3, 0.70),  # 每2天补3种物，回补70%基准量
    "yaren":    (3, 2, 0.55),  # 牙人靠撮合得货，货量不稳定
    "yulaog":   (2, 2, 0.80),  # 船家打鱼自然补货快
    "lizheng":  (4, 2, 0.45),  # 里正手头紧，补得慢
    "lika":     (5, 1, 0.35),  # 卡吏靠查扣得货，补得最慢
    "seng":     (3, 2, 0.50),  # 佛寺靠香火，偶有信众布施
    "yizu":     (3, 2, 0.50),  # 驿卒随驿马往来略可进货
}


def restock_npc_inventories(p: PlayerState) -> list[str]:
    """检测所有商贩 NPC 是否需要补货，若到期则部分回补。

    补货逻辑：
    1. 对比当前世界日与 NPC 上次补货日，差 >= 配置中的周期
    2. 从该 NPC 的起始库存（种子表）中，选当前缺货最多的 k 种
    3. 每种回补基准量的 restock_ratio 份（至少1份）
    4. 更新 restock_day 追踪
    5. 返回补货日志列表

    调用时机：世界日翻篇时（advance_clock 触发跨日检查）。
    """
    current_day = int(p.world_day)
    logs: list[str] = []

    for npc_id, seeds in NPC_INVENTORY_SEEDS.items():
        config = RESTOCK_CONFIG.get(npc_id)
        if not config:
            continue
        interval_days, max_items, ratio = config

        last_day = p.npc_inventory_restock_day.get(npc_id, 0)
        if (current_day - last_day) < interval_days:
            continue

        inv = p.npc_inventories.get(npc_id)
        if inv is None:
            inv = {}
            p.npc_inventories[npc_id] = inv

        # 统计当前库存缺口：缺货越多越优先补
        shortages: list[tuple[str, int]] = []
        for item, seed_qty in seeds.items():
            current = inv.get(item, 0)
            need = seed_qty - current
            if need > 0:
                shortages.append((item, need))

        if not shortages:
            # 无缺货，仅更新追踪时间
            p.npc_inventory_restock_day[npc_id] = current_day
            continue

        # 缺货从大到小排序，取前 N 种
        shortages.sort(key=lambda kv: kv[1], reverse=True)
        to_restock = shortages[:max_items]

        items_restocked: list[str] = []
        for item, _need in to_restock:
            seed_qty = seeds[item]
            add_qty = max(1, int(round(seed_qty * ratio)))
            cur = inv.get(item, 0)
            # 不超出种子数量
            actual_add = min(add_qty, seed_qty - cur)
            if actual_add > 0:
                inv[item] = cur + actual_add
                items_restocked.append(f"{item}+{actual_add}")

        p.npc_inventory_restock_day[npc_id] = current_day

        if items_restocked:
            from backend.data.npcs_data import NPCS
            npc_name = NPCS.get(npc_id, {}).get("short", npc_id)
            log_msg = f"{npc_name}进货了：{', '.join(items_restocked)}"
            logs.append(log_msg)

    return logs


# ════════════════════════════════════════════════════════════════════
#  物品消耗 API — 玩家从背包中使用物品（🎮 游戏性）
# ════════════════════════════════════════════════════════════════════

def use_player_item(p: "PlayerState", item_name: str) -> dict[str, object]:
    """玩家消耗一个背包物品，应用其身心效用并返回叙事描述。

    返回格式：
    {
        "success": True/False,
        "note": "叙事描述或失败原因",
        "delta": {"vigor": int, "spirit": int, "sleep_debt": int},
        "item_consumed": str,  # 消耗的物品名（成功时）
    }

    边界处理：
    - 物品不在 ITEM_USE_EFFECTS 中 → 告知不可消耗
    - 物品不在背包中 → 告知没有此物
    - 超每日上限 → 告知今日已用足
    - 生命燃烧中自动解除（进食效果）
    """
    name = (item_name or "").strip().strip("「」『」\"'")[:MAX_ITEM_NAME_LEN]
    if not name:
        return {"success": False, "note": "空无一物。", "delta": {"vigor": 0, "spirit": 0, "sleep_debt": 0}}

    # 检查是否在消耗表中
    effect = ITEM_USE_EFFECTS.get(name)
    if not effect:
        # 某些物品不能直接消耗（文书、兵器、信物等）
        cat_info = ITEM_PRICE_CATALOG.get(name)
        if cat_info:
            cat = str(cat_info.get("cat", ""))
            cat_names = {"文": "文书信物", "兵": "兵器护具", "物": "日用杂物"}
            cat_label = cat_names.get(cat, "物品")
            return {
                "success": False,
                "note": f"{name}是{cat_label}，不能直接消耗。你若要用它，可寻相关NPC出示或交易。",
                "delta": {"vigor": 0, "spirit": 0, "sleep_debt": 0},
            }
        return {
            "success": False,
            "note": f"你端详着{name}，不知怎生用法——不妨问问认得此物的人。",
            "delta": {"vigor": 0, "spirit": 0, "sleep_debt": 0},
        }

    # 检查背包中是否有此物
    inv_count = int(p.inventory.get(name, 0))
    if inv_count <= 0:
        return {
            "success": False,
            "note": f"你翻遍了随身包裹，没找到{name}——怕是已经用完了。",
            "delta": {"vigor": 0, "spirit": 0, "sleep_debt": 0},
        }

    # 日上限检查
    max_per_day = int(effect.get("max_per_day", 0))
    if max_per_day > 0:
        if not hasattr(p, "item_use_tracker") or p.item_use_tracker is None:
            p.item_use_tracker = {}
        current_day = int(getattr(p, "world_day", 1) or 1)
        # 翻日清理旧记录
        if p.item_use_tracker.get("_day") != current_day:
            p.item_use_tracker = {"_day": current_day}
        used_today = int(p.item_use_tracker.get(name, 0))
        if used_today >= max_per_day:
            return {
                "success": False,
                "note": f"你再续{name}已不见效——今日用够了，再续也是糟蹋。换个时辰再说。",
                "delta": {"vigor": 0, "spirit": 0, "sleep_debt": 0},
            }

    # 应用效用
    vigor_delta = int(effect.get("vigor", 0))
    spirit_delta = int(effect.get("spirit", 0))
    sleep_debt_delta = int(effect.get("sleep_debt", 0))

    from backend.systems.core import apply_vigor_delta, apply_spirit_delta
    actual_vigor = apply_vigor_delta(p, vigor_delta)
    actual_spirit = apply_spirit_delta(p, spirit_delta)

    # 睡眠债变化
    if sleep_debt_delta < 0:
        p.sleep_debt = max(0, int(getattr(p, "sleep_debt", 0)) + sleep_debt_delta)

    # 从背包扣除
    p.inventory[name] = inv_count - 1
    if p.inventory[name] <= 0:
        del p.inventory[name]

    # 更新日用量追踪
    if max_per_day > 0:
        p.item_use_tracker[name] = used_today + 1

    # 进食后解除生命燃烧
    if int(getattr(p, "life_burn_ticks", 0)) > 0 and actual_vigor > 0:
        p.life_burn_ticks = 0
        p.life_burn_max = 0
        p.trap_reason = None
        p.move_locked = False
        p.move_lock_npc_id = None

    return {
        "success": True,
        "note": str(effect.get("note", f"你用掉了{name}。")),
        "delta": {
            "vigor": actual_vigor,
            "spirit": actual_spirit,
            "sleep_debt": sleep_debt_delta,
        },
        "item_consumed": name,
    }
