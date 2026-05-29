"""青石江湖·万里图 — 150×100 大地图生成器

用法:
    python tools/gen_map.py > backend/data/map_rows.txt
    (然后复制 map_rows.txt 内容到 maps_data.py)

设计:
    - 150×100 ≈ 15000 格 (原 72×48 ≈ 3456 格，约 4.3 倍)
    - 13 个区域 (原 10 个 + 3 个新区域)
    - 主河 + 3 条支流
    - 新增区域: 北关塞(fortress)、东港(eastport)、南泽(southmarsh)
"""
import random
import sys


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    random.seed(2026)  # 可复现

    W, H = 150, 100

    # ── 初始化全图草地 ──
    grid = [["," for _ in range(W)] for _ in range(H)]

    # ── 边界墙 ──
    for y in range(H):
        grid[y][0] = grid[y][W - 1] = "#"
    for x in range(W):
        grid[0][x] = grid[H - 1][x] = "#"

    # ── 北方山脉 (y:2-12, 大片 m//) ──
    for y in range(2, 13):
        for x in range(2, W - 2):
            dist_south = y - 2
            prob = 0.45 - dist_south * 0.04
            if 60 < x < 90:  # 关隘通道——降低山脉密度
                prob -= 0.25
            if random.random() < prob:
                grid[y][x] = random.choice(["m", "m", "/", "^"])

    # ── 西方山脉 (x:2-18, y:10-40) ──
    for y in range(10, 40):
        for x in range(2, 18):
            dist_east = x - 2
            prob = 0.4 - dist_east * 0.03
            if random.random() < prob:
                grid[y][x] = random.choice(["m", "/", "^"])

    # ── 东方丘陵 (x:125-148, y:20-70) ──
    for y in range(20, 70):
        for x in range(125, W - 2):
            dist_west = 148 - x
            prob = 0.3 - dist_west * 0.02
            if random.random() < prob:
                grid[y][x] = random.choice(["m", "/", "^"])

    # ── 南方沼泽地带 (y:85-98) ──
    for y in range(85, H - 2):
        for x in range(2, W - 2):
            if random.random() < 0.5:
                grid[y][x] = random.choice([";", ";", "~", ","])


    # ══════════════════════════════════════════════════════
    #  主河 (=) : 自西北流向东南，纵贯全图
    # ══════════════════════════════════════════════════════
    river_main = []
    rx, ry = 30, 2
    while ry < H - 2:
        river_main.append((rx, ry))
        # 河道蜿蜒
        rx += random.choice([0, 0, 1, 1, 1, 2])
        ry += 1
        rx = min(W - 5, rx)

    for px, py in river_main:
        if not (1 <= py < H - 1 and 1 <= px < W - 1):
            continue
        # 河道宽度：主脉 =, 两岸险水 ~
        for dy in (-1, 0, 1):
            ny = py + dy
            if 1 <= ny < H - 1 and grid[ny][px] not in ("#", "T", "M", "Y", "B", "I"):
                grid[ny][px] = "~"
        grid[py][px] = "="

    # ── 支流 1: 从主河分叉向东北，经帮坞入海 ──
    branch1 = []
    bx, by = 85, 30
    for _ in range(40):
        branch1.append((bx, by))
        bx += random.choice([0, 1, 1, 2])
        by += random.choice([-1, 0, 0, 1])
        if bx >= W - 3 or by >= H - 3:
            break

    for px, py in branch1:
        if 1 <= py < H - 1 and 1 <= px < W - 1:
            if grid[py][px] not in ("#",):
                grid[py][px] = "="
            for dy in (-1, 1):
                ny = py + dy
                if 1 <= ny < H - 1 and grid[ny][px] not in ("#", "T", "M", "Y", "B"):
                    grid[ny][px] = "~"

    # ── 支流 2: 从主河分叉向西南，经芦花墟 ──
    branch2 = []
    bx, by = 45, 55
    for _ in range(45):
        branch2.append((bx, by))
        bx += random.choice([0, 0, 1])
        by += random.choice([1, 1, 2])
        if bx >= W - 3 or by >= H - 3:
            break

    for px, py in branch2:
        if 1 <= py < H - 1 and 1 <= px < W - 1:
            if grid[py][px] not in ("#",):
                grid[py][px] = "="
            for dy in (-1, 1):
                ny = py + dy
                if 1 <= ny < H - 1 and grid[ny][px] not in ("#", "T", "M", "Y", "B"):
                    grid[ny][px] = "~"

    # ── 支流 3: 驿站附近小溪 ──
    branch3 = []
    bx, by = 100, 58
    for _ in range(20):
        branch3.append((bx, by))
        bx += random.choice([0, 1])
        by += random.choice([1, 1, 2])
        if by >= H - 3:
            break

    for px, py in branch3:
        if 1 <= py < H - 1 and 1 <= px < W - 1 and grid[py][px] in (",", ".", "F", ";"):
            grid[py][px] = "~"


    # ══════════════════════════════════════════════════════
    #  区域填充
    # ══════════════════════════════════════════════════════

    # ── 1. 青石县城 (city): x:10-50, y:25-45 ──
    for y in range(25, 46):
        for x in range(10, 51):
            if grid[y][x] in (",", "."):
                grid[y][x] = ","

    # 城内道路
    for x in range(12, 48):
        if grid[34][x] in (",", "."):
            grid[34][x] = "."
    for x in range(12, 48):
        if grid[38][x] in (",", "."):
            grid[38][x] = "."
    for y in range(26, 45):
        if grid[y][22] in (",", "."):
            grid[y][22] = "."
        if grid[y][35] in (",", "."):
            grid[y][35] = "."

    # 城内关键建筑
    grid[30][16] = "T"   # 同福栈
    grid[31][17] = "T"   # 同福栈副楼
    grid[28][25] = "M"   # 市集(大)
    grid[29][26] = "M"   # 市集(副)
    grid[33][22] = "Y"   # 衙前
    grid[34][22] = "Y"   # 衙前(副)
    grid[35][14] = "T"   # 牙行
    grid[36][30] = "T"   # 镖局
    grid[30][40] = "T"   # 东门客栈
    grid[26][18] = "M"   # 北市

    # ── 2. 卧佛寺 (temple): x:40-65, y:10-25 ──
    for y in range(10, 25):
        for x in range(40, 66):
            if grid[y][x] in (",", ".", "m", "/"):
                if random.random() < 0.15:
                    grid[y][x] = "/"
                else:
                    grid[y][x] = ","
    grid[14][50] = "Y"   # 山门
    grid[15][52] = "T"   # 寺廊
    grid[16][53] = "T"   # 佛殿
    grid[13][48] = "T"   # 知客寮

    # 寺前石阶
    for y in range(16, 22):
        if grid[y][47] in (",", "."):
            grid[y][47] = "/"

    # ── 3. 北关塞 (fortress) [NEW]: x:60-90, y:4-14 ──
    for y in range(4, 15):
        for x in range(60, 91):
            if grid[y][x] in (",", ".", "m", "/", "^"):
                grid[y][x] = ","
    grid[7][75] = "Y"    # 关楼
    grid[8][76] = "T"    # 关驿
    grid[9][78] = "M"    # 军市
    grid[6][70] = "T"    # 烽火台
    grid[10][82] = "T"   # 屯田所

    # 关隘通道(清空山脉)
    for y in range(5, 14):
        for x in range(68, 84):
            if grid[y][x] in ("m", "^", "/"):
                if random.random() < 0.7:
                    grid[y][x] = ","
                else:
                    grid[y][x] = "/"

    # ── 4. 渡口沿岸 (dock): x:70-100, y:42-62 ──
    for y in range(42, 63):
        for x in range(70, 101):
            if grid[y][x] in (",", "."):
                grid[y][x] = ","
    grid[50][78] = "T"   # 渡头
    grid[51][80] = "B"   # 桥
    grid[52][82] = "B"   # 桥(副)
    grid[53][85] = "T"   # 画舫
    grid[48][75] = "T"   # 西出口渡
    grid[55][90] = "T"   # 码头仓库

    # ── 5. 漕口帮坞 (guild): x:110-138, y:15-35 ──
    for y in range(15, 36):
        for x in range(110, 139):
            if grid[y][x] in (",", ".", "m", "/"):
                grid[y][x] = ","
    grid[20][120] = "M"  # 帮坞厅
    grid[22][122] = "T"  # 码口
    grid[18][115] = "T"  # 船坞
    grid[25][128] = "T"  # 赌坊

    # ── 6. 竹林书院 (academy): x:108-138, y:36-55 ──
    for y in range(36, 56):
        for x in range(108, 139):
            if grid[y][x] in (",", "."):
                if random.random() < 0.3:
                    grid[y][x] = "F"  # 竹林
                else:
                    grid[y][x] = ","
    grid[42][118] = "T"  # 书院廊
    grid[40][122] = "T"  # 竹径
    grid[44][125] = "M"  # 藏书阁
    grid[38][112] = "T"  # 山长居

    # ── 7. 芦花墟 (village): x:10-48, y:65-88 ──
    for y in range(65, 89):
        for x in range(10, 49):
            if grid[y][x] in (",", "."):
                grid[y][x] = ","
    grid[74][20] = "T"   # 里正宅
    grid[75][30] = "M"   # 墟口
    grid[78][35] = "T"   # 芦花祠
    grid[72][15] = "T"   # 野径中
    grid[80][25] = "M"   # 南墟

    # ── 8. 碾坊 (mill): x:50-70, y:65-82 ──
    for y in range(65, 83):
        for x in range(50, 71):
            if grid[y][x] in (",", "."):
                if random.random() < 0.2:
                    grid[y][x] = ";"
                else:
                    grid[y][x] = ","
    grid[72][58] = "M"   # 碾坊
    grid[70][62] = "T"   # 碾坊副楼
    grid[75][55] = "T"   # 东碾坊口

    # ── 9. 驿舍 (post): x:75-105, y:55-75 ──
    for y in range(55, 76):
        for x in range(75, 106):
            if grid[y][x] in (",", "."):
                grid[y][x] = ","
    grid[62][90] = "T"   # 驿舍
    grid[64][95] = "M"   # 驿市
    grid[60][82] = "T"   # 驿马监

    # ── 10. 厘卡哨 (checkpoint): x:108-135, y:60-80 ──
    for y in range(60, 81):
        for x in range(108, 136):
            if grid[y][x] in (",", "."):
                grid[y][x] = ","
    grid[68][118] = "Y"  # 卡亭
    grid[70][120] = "T"  # 哨房
    grid[72][125] = "T"  # 验引亭

    # ── 11. 东港 (eastport) [NEW]: x:120-146, y:72-92 ──
    for y in range(72, 93):
        for x in range(120, 147):
            if grid[y][x] in (",", ".", ";", "~"):
                grid[y][x] = ","
    grid[80][132] = "M"  # 港市
    grid[82][135] = "T"  # 港务司
    grid[78][128] = "T"  # 盐仓
    grid[85][140] = "T"  # 海神庙
    grid[76][124] = "T"  # 船厂

    # ── 12. 南泽 (southmarsh) [NEW]: x:35-75, y:85-97 ──
    for y in range(85, 98):
        for x in range(35, 76):
            if grid[y][x] in (",", ".", ";"):
                if random.random() < 0.4:
                    grid[y][x] = "~"
                elif random.random() < 0.5:
                    grid[y][x] = ";"
                else:
                    grid[y][x] = ","
    grid[90][50] = "T"   # 泽中观
    grid[92][55] = "T"   # 泽民棚
    grid[88][45] = "T"   # 南泽口

    # ── 13. 西陵山 (western mountains, interior): x:3-18, y:42-65 ──
    for y in range(42, 66):
        for x in range(3, 19):
            if grid[y][x] in (",", "."):
                if random.random() < 0.35:
                    grid[y][x] = random.choice(["m", "/", "^"])
                elif random.random() < 0.3:
                    grid[y][x] = "F"
    grid[52][8] = "T"    # 山家
    grid[55][12] = "T"   # 采药人窝棚
    grid[48][5] = "@"    # 古矿废墟


    # ══════════════════════════════════════════════════════
    #  野外森林填充
    # ══════════════════════════════════════════════════════
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            if grid[y][x] == ",":
                # 根据位置添加不同密度森林
                if 15 < y < 25 and 20 < x < 40:      # 县城与寺之间
                    if random.random() < 0.3:
                        grid[y][x] = "F"
                elif 25 < y < 42 and 50 < x < 70:     # 中部野林
                    if random.random() < 0.4:
                        grid[y][x] = "F"
                elif 45 < y < 65 and 10 < x < 50:    # 西南野林
                    if random.random() < 0.35:
                        grid[y][x] = "F"
                elif 30 < y < 55 and 90 < x < 110 and random.random() < 0.25:
                        grid[y][x] = "F"

    # 剩余 , 变为土路 . (零星)
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            if grid[y][x] == "," and random.random() < 0.08:
                grid[y][x] = "."


    # ══════════════════════════════════════════════════════
    #  险地 & 伏击点
    # ══════════════════════════════════════════════════════

    # 裂隙 (!)
    chasm_spots = [
        (55, 8), (56, 8), (57, 8),          # 北方裂隙
        (30, 55), (31, 55), (32, 55),         # 中部裂隙
        (110, 28), (111, 28), (112, 28),      # 东部裂隙
        (40, 82), (41, 82), (42, 82),         # 南方裂隙
        (95, 68), (96, 68),                   # 驿道旁裂隙
        (140, 45), (141, 45),                 # 远东裂隙
    ]
    for x, y in chasm_spots:
        if 1 <= y < H - 1 and 1 <= x < W - 1:
            grid[y][x] = "!"

    # 废墟 (@)
    ruin_spots = [
        (25, 50), (26, 50), (27, 50),         # 西部废墟
        (60, 28), (61, 28), (62, 28),          # 中部废墟
        (100, 50), (101, 50),                  # 东部废墟
        (45, 78), (46, 78),                    # 南部废墟
        (130, 55), (131, 55),                  # 远东废墟
        (15, 62), (16, 62),                    # 西山废墟
    ]
    for x, y in ruin_spots:
        if 1 <= y < H - 1 and 1 <= x < W - 1:
            grid[y][x] = "@"

    # 黑店 & 伏击草
    grid[45][18] = "I"    # 黑店(西野)
    grid[55][65] = "I"    # 黑店(中路)
    grid[35][48] = "&"    # 剪径草丛(城外)
    grid[48][55] = "&"    # 剪径草丛(渡口西)
    grid[68][40] = "&"    # 剪径草丛(墟北)
    grid[82][110] = "&"   # 剪径草丛(东港外)


    # ══════════════════════════════════════════════════════
    #  道路系统
    # ══════════════════════════════════════════════════════

    # 1. 县城→寺: 纵向
    for y in range(25, 35):
        if grid[y][22] not in ("#", "=", "~", "!", "T", "M", "Y", "B", "I", "&"):
            grid[y][22] = "."

    # 2. 县城→渡口: 横向
    for x in range(35, 75):
        if grid[38][x] not in ("#", "=", "~", "!", "T", "M", "Y", "B", "I", "&"):
            grid[38][x] = "."

    # 3. 渡口→驿舍: 纵向
    for y in range(50, 62):
        if grid[y][80] not in ("#", "=", "~", "!", "T", "M", "Y", "B", "I", "&"):
            grid[y][80] = "."

    # 4. 驿舍→帮坞: 横向
    for x in range(95, 120):
        if grid[62][x] not in ("#", "=", "~", "!", "T", "M", "Y", "B", "I", "&"):
            grid[62][x] = "."

    # 5. 县城→墟: 纵向
    for y in range(46, 72):
        if grid[y][22] not in ("#", "=", "~", "!", "T", "M", "Y", "B", "I", "&"):
            grid[y][22] = "."

    # 6. 墟→碾坊: 横向
    for x in range(30, 58):
        if grid[74][x] not in ("#", "=", "~", "!", "T", "M", "Y", "B", "I", "&"):
            grid[74][x] = "."

    # 7. 碾坊→驿舍: 横向
    for x in range(62, 90):
        if grid[72][x] not in ("#", "=", "~", "!", "T", "M", "Y", "B", "I", "&"):
            grid[72][x] = "."

    # 8. 帮坞→书院: 纵向
    for y in range(25, 42):
        if grid[y][120] not in ("#", "=", "~", "!", "T", "M", "Y", "B", "I", "&"):
            grid[y][120] = "."

    # 9. 北关→寺: 横向
    for x in range(50, 65):
        if grid[10][x] not in ("#", "=", "~", "!", "T", "M", "Y", "B", "I", "&"):
            grid[10][x] = "."

    # 10. 关→帮坞: 横向
    for x in range(90, 115):
        if grid[10][x] not in ("#", "=", "~", "!", "T", "M", "Y", "B", "I", "&"):
            grid[10][x] = "."

    # 11. 东港→厘卡: 纵向
    for y in range(68, 80):
        if grid[y][125] not in ("#", "=", "~", "!", "T", "M", "Y", "B", "I", "&"):
            grid[y][125] = "."

    # 12. 厘卡→书院: 纵向
    for y in range(55, 60):
        if grid[y][118] not in ("#", "=", "~", "!", "T", "M", "Y", "B", "I", "&"):
            grid[y][118] = "."

    # 13. 南泽→碾坊: 横向
    for x in range(50, 58):
        if grid[85][x] not in ("#", "=", "~", "!", "T", "M", "Y", "B", "I", "&"):
            grid[85][x] = "."


    # ══════════════════════════════════════════════════════
    #  确保所有建筑符号不被覆盖
    # ══════════════════════════════════════════════════════
    # (在前面已设置，这里确保关键建筑仍在)
    KEY_BUILDINGS = {
        # 县城
        (16, 30): "T", (17, 31): "T", (25, 28): "M", (26, 29): "M",
        (22, 33): "Y", (22, 34): "Y", (14, 35): "T", (30, 36): "T",
        (40, 30): "T", (18, 26): "M",
        # 寺
        (50, 14): "Y", (52, 15): "T", (53, 16): "T", (48, 13): "T",
        # 关塞
        (75, 7): "Y", (76, 8): "T", (78, 9): "M", (70, 6): "T", (82, 10): "T",
        # 渡口
        (78, 50): "T", (80, 51): "B", (82, 52): "B", (85, 53): "T",
        (75, 48): "T", (90, 55): "T",
        # 帮坞
        (120, 20): "M", (122, 22): "T", (115, 18): "T", (128, 25): "T",
        # 书院
        (118, 42): "T", (122, 40): "T", (125, 44): "M", (112, 38): "T",
        # 墟
        (20, 74): "T", (30, 75): "M", (35, 78): "T", (15, 72): "T", (25, 80): "M",
        # 碾坊
        (58, 72): "M", (62, 70): "T", (55, 75): "T",
        # 驿舍
        (90, 62): "T", (95, 64): "M", (82, 60): "T",
        # 厘卡
        (118, 68): "Y", (120, 70): "T", (125, 72): "T",
        # 东港
        (132, 80): "M", (135, 82): "T", (128, 78): "T", (140, 85): "T", (124, 76): "T",
        # 南泽
        (50, 90): "T", (55, 92): "T", (45, 88): "T",
        # 西陵山
        (8, 52): "T", (12, 55): "T",
        # 黑店/伏击
        (18, 45): "I", (65, 55): "I",
        (48, 35): "&", (55, 48): "&", (40, 68): "&", (110, 82): "&",
    }

    for (x, y), ch in KEY_BUILDINGS.items():
        if 0 <= y < H and 0 <= x < W:
            grid[y][x] = ch


    # ══════════════════════════════════════════════════════
    #  输出
    # ══════════════════════════════════════════════════════
    rows = ["".join(row) for row in grid]

    # 验证行宽一致性
    for i, row in enumerate(rows):
        if len(row) != W:
            print(f"# WARNING: row {i} has width {len(row)} != {W}", file=sys.stderr)

    print(f"# Map size: {W} x {H} = {W*H} tiles")
    print(f"# Rows: {len(rows)}")
    print()

    for row in rows:
        print(f'            "{row}",')


if __name__ == '__main__':
    main()
