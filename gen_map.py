import random
random.seed(42)

W, H = 72, 48

# Initialize with grass
grid = [['.' for _ in range(W)] for _ in range(H)]

# --- Walls on borders ---
for y in range(H):
    grid[y][0] = grid[y][W-1] = '#'
for x in range(W):
    grid[0][x] = grid[H-1][x] = '#'

# --- Main River (=) flowing NW to SE ---
river_points = [
    (14,1),(14,2),(15,3),(15,4),(16,5),(16,6),(17,7),(17,8),(18,9),(18,10),
    (19,11),(19,12),(20,13),(21,14),(22,15),(23,16),(24,17),(25,18),(26,19),
    (27,20),(28,20),(29,21),(30,22),(31,23),(32,23),(33,24),(34,25),(35,26),
    (36,27),(37,28),(38,29),(39,30),(40,31),(41,32),(42,33),(43,34),(44,35),
    (45,36),(46,37),(47,38),(48,39),(49,40)
]
for px,py in river_points:
    for dy in [-1,0,1]:
        if 1 <= py+dy < H-1:
            grid[py+dy][px] = '~'
    grid[py][px] = '='

# Tributary river branch
branch = [(22,20),(23,20),(24,19),(25,18),(26,17),(27,17),(28,17),(29,17),(30,18),(31,19)]
for bx,by in branch:
    if 1 <= by < H-1 and 1 <= bx < W-1:
        for dy in [-1,0,1]:
            if grid[by+dy][bx] == '.':
                grid[by+dy][bx] = '~'
        grid[by][bx] = '='

# --- Mountains in NE ---
for y in range(4, 12):
    for x in range(50, 68):
        if random.random() < 0.3:
            grid[y][x] = 'm'
        elif random.random() < 0.5:
            grid[y][x] = '/'

# --- Mountains in NW ---
for y in range(2, 9):
    for x in range(4, 13):
        if x < 4 or y < 2: continue
        if random.random() < 0.25:
            grid[y][x] = 'm'
        elif random.random() < 0.4:
            grid[y][x] = '/'

# --- Temple area (North-center) ---
for y in range(5, 10):
    for x in range(20, 32):
        if grid[y][x] in ['.','/','m']:
            if random.random() < 0.15: grid[y][x] = '/'
grid[6][24] = 'Y'
grid[7][25] = 'T'
grid[8][26] = 'T'

# --- County area (center-west) ---
for y in range(12, 20):
    for x in range(5, 26):
        if grid[y][x] == '.': grid[y][x] = ','
grid[13][8] = 'T'   # 同福栈
grid[14][9] = 'T'
grid[13][13] = 'M'  # 市集
grid[13][16] = 'M'
grid[15][11] = 'Y'  # 衙前
grid[15][12] = 'Y'
grid[16][7] = 'T'   # 牙行

for x in range(7, 24):
    if grid[16][x] in [',','.']: grid[16][x] = '.'
for y in range(12, 19):
    if grid[y][14] in [',','.']: grid[y][14] = '.'

# --- Wild area (west) ---
for y in range(20, 32):
    for x in range(4, 24):
        if grid[y][x] == '.' and random.random() < 0.4: grid[y][x] = 'F'
grid[22][11] = 'I'  # 黑店
grid[24][9] = '&'   # 剪径芦荡
for y in range(22, 26):
    for x in range(12, 18):
        if grid[y][x] == 'F' and random.random() < 0.5: grid[y][x] = ';'

# --- Dock area (along river, center-right) ---
for y in range(22, 30):
    for x in range(33, 44):
        if grid[y][x] == '.': grid[y][x] = ','
grid[23][35] = 'T'  # 渡头
grid[24][36] = 'B'  # 桥
grid[24][37] = 'B'
grid[25][39] = 'T'  # 画舫

# --- Village area (south) ---
for y in range(34, 44):
    for x in range(8, 22):
        if grid[y][x] == '.': grid[y][x] = ','
grid[38][14] = 'T'  # 里正宅
grid[38][17] = 'M'  # 墟口
for y in range(34, 42):
    for x in range(5, 9):
        if grid[y][x] == ',': grid[y][x] = 'F'

# --- Academy area (east) ---
for y in range(16, 26):
    for x in range(52, 66):
        if grid[y][x] == '.':
            if random.random() < 0.35: grid[y][x] = 'F'
            else: grid[y][x] = ','
grid[20][58] = 'T'
grid[21][59] = 'T'
grid[19][57] = 'M'

# --- Post area (center-southeast) ---
for y in range(32, 38):
    for x in range(30, 45):
        if grid[y][x] == '.': grid[y][x] = ','
grid[34][37] = 'T'  # 驿舍
grid[35][40] = 'M'

# --- Guild area (east) ---
for y in range(8, 16):
    for x in range(55, 66):
        if grid[y][x] == '.': grid[y][x] = ','
grid[10][60] = 'M'  # 帮坞
grid[11][60] = 'T'

# --- Mill area (center-south) ---
for y in range(34, 40):
    for x in range(25, 33):
        if grid[y][x] == '.':
            if random.random() < 0.3: grid[y][x] = ';'
            else: grid[y][x] = ','
grid[36][28] = 'M'  # 碾坊
grid[36][29] = ';'

# --- Checkpoint area (southeast) ---
for y in range(34, 40):
    for x in range(52, 62):
        if grid[y][x] == '.': grid[y][x] = ','
grid[35][55] = 'Y'  # 卡亭
grid[36][56] = 'T'

# --- Scatter forests, mud ---
for y in range(1, H-1):
    for x in range(1, W-1):
        if grid[y][x] == '.':
            r = random.random()
            if r < 0.15: grid[y][x] = 'F'
            elif r < 0.22: grid[y][x] = ';'
            elif r < 0.25: grid[y][x] = ','

# --- Chasms in dangerous areas ---
danger_coords = [(30,6),(31,6),(32,6),(55,4),(56,4),(57,4),
                 (40,44),(41,44),(42,44),(10,42),(11,42),(12,42),
                 (65,22),(66,22),(67,22),(33,10),(34,10),(35,10)]
for x,y in danger_coords:
    if 1 <= y < H-1 and 1 <= x < W-1: grid[y][x] = '!'

# --- Ruins ---
ruin_coords = [(48,8),(49,8),(50,8),(18,44),(19,44),(20,44),
               (60,35),(61,35),(5,28),(6,28),(68,12),(69,12)]
for x,y in ruin_coords:
    if 1 <= y < H-1 and 1 <= x < W-1: grid[y][x] = '@'

# --- Roads connecting areas ---
roads = []
for y in range(20, 34): roads.append((15, y))
for x in range(26, 52): roads.append((x, 16))
for x in range(22, 30): roads.append((x, 36))
for x in range(44, 52): roads.append((x, 36))
for y in range(14, 24): roads.append((37, y))
for x,y in roads:
    if 1<=y<H-1 and 1<=x<W-1 and grid[y][x] not in ['#','=','~','!','@','Y','T','M','B','&','I']:
        grid[y][x] = '.'

# Print as Python code
for i, row in enumerate([grid[y] for y in range(H)]):
    print(f'            "{"".join(row)}",')