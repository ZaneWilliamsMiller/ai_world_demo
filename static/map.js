// 视口渲染：以玩家为中心，根据容器实际尺寸动态计算列/行数
// 自适应屏幕宽高比，矩形容器→矩形网格，填满不留白
const TARGET_TILE = 32; // 目标格子尺寸（含 gap 2px）
const MIN_TILES = 9;   // 单方向最少格数
const MAX_TILES = 51;  // 单方向最多格数（性能上限）

const BASE_TERRAIN_CLASSES = [
  "tile-wall",
  "tile-cliff",
  "tile-water",
  "tile-grass",
  "tile-forest",
  "tile-mud",
  "tile-mountainpath",
  "tile-mountain",
  "tile-tavern",
  "tile-market",
  "tile-yamen",
  "tile-bridge",
  "tile-river",
  "tile-chasm",
  "tile-ruins",
];

const DYNAMIC_TILE_CLASSES = [
  "tile-player",
  "tile-npc",
  "tile-route",
  "tile-route-end",
  "tile-danger",
  "tile-hurt",
  "tile-ambush",
  "tile-unwalkable",
];

const LABEL_MAP = {
  "#": "墙", "^": "悬崖", "~": "险水", ",": "草地", ".": "土路",
  "F": "林子", ";": "泥地", "/": "山道", "m": "山岭",
  "T": "客栈", "I": "客栈", "M": "市集", "Y": "衙前", "B": "桥",
  "=": "河道", "!": "裂隙", "@": "废墟", "&": "密林",
};

const ELEV = {
  "#": 99, "^": 9, m: 7, "/": 6, "!": 99, "@": 5,
  F: 4, "&": 4, ";": 3,
  ",": 2, ".": 2, T: 2, M: 2, Y: 2, B: 2, I: 2,
  "~": 1, "=": 1,
};

const DANGER_SET = new Set(["~", "!", "@", "^"]);
const CACHE = new WeakMap();

/**
 * 以玩家为中心的视口渲染。
 * - 首次或视口偏移时重建 grid（仅 VIEW_SIZE×VIEW_SIZE 格）
 * - 后续动态更新样式
 * - 玩家始终位于视口中央（地图边缘时贴边）
 */
export function renderMap(host, opts, onCellPick) {
  const {
    mapId,
    maps,
    player,
    npcCatalog,
    ambushMarkers = [],
    moveLocked = false,
    routeOverlay = null,
    injuryEvents = [],
  } = opts;
  const m = maps[mapId];
  if (!m || !m.rows || !m.rows.length) {
    host.textContent = "地图未载入";
    return;
  }
  const rows = m.rows;
  const mapH = rows.length;
  const mapW = rows[0].length;

  // 1. 根据容器实际尺寸动态计算视口宽/高（非正方形，随屏幕比例自适应）
  const rect = host.getBoundingClientRect();
  const gap = 2;
  const colsFit = Math.max(MIN_TILES, Math.floor((rect.width + gap) / (TARGET_TILE + gap)));
  const rowsFit = Math.max(MIN_TILES, Math.floor((rect.height + gap) / (TARGET_TILE + gap)));
  const viewW = Math.min(colsFit, mapW, MAX_TILES);
  const viewH = Math.min(rowsFit, mapH, MAX_TILES);

  // 2. 视口原点：玩家居中，贴边时 clamp
  const playerOnMap = player.map_id === mapId;
  const vx = clamp(
    (playerOnMap ? player.px : Math.floor(mapW / 2)) - Math.floor(viewW / 2),
    0, Math.max(0, mapW - viewW),
  );
  const vy = clamp(
    (playerOnMap ? player.py : Math.floor(mapH / 2)) - Math.floor(viewH / 2),
    0, Math.max(0, mapH - viewH),
  );
  const viewKey = `${mapId}:${vx},${vy}:${viewW}x${viewH}`;

  // 3. 缓存判断
  let cache = CACHE.get(host);
  const layoutChanged = !cache || cache.viewKey !== viewKey || cache.viewW !== viewW || cache.viewH !== viewH;

  if (layoutChanged) {
    cache = buildViewportGrid(host, viewKey, m, rows, vx, vy, viewW, viewH);
    cache.viewW = viewW;
    cache.viewH = viewH;
    CACHE.set(host, cache);
  }

  // 4. 事件代理（只需绑定一次）
  if (!cache.delegated) {
    host.addEventListener("click", (ev) => {
      const c = CACHE.get(host);
      if (!c) return;
      const btn = ev.target.closest(".tile");
      if (!btn || !host.contains(btn) || btn.disabled) return;
      const fn = c.onCellPick;
      if (typeof fn !== "function") return;
      fn(Number(btn.dataset.x), Number(btn.dataset.y), ev);
      ev.stopPropagation();
    });
    cache.delegated = true;
  }
  cache.onCellPick = onCellPick;

  // 5. 容器 resize 时自动重建（rAF 轮询，比 ResizeObserver 兼容性更好）
  if (!cache._resizeTick) {
    cache._resizeTick = requestAnimationFrame(function tick() {
      const r = host.getBoundingClientRect();
      if (Math.abs(r.width - cache._resizeW) > 4 || Math.abs(r.height - cache._resizeH) > 4) {
        cache.viewKey = null; // 强制重建
        const cb = cache._resizeCb;
        if (cb) cb();
      }
      cache._resizeTick = requestAnimationFrame(tick);
    });
  }
  cache._resizeW = rect.width;
  cache._resizeH = rect.height;
  cache._resizeCb = () => {
    const opts2 = { mapId, maps, player, npcCatalog, ambushMarkers, moveLocked, routeOverlay, injuryEvents };
    renderMap(host, opts2, onCellPick);
  };

  // 6. 应用 CSS 变量和类
  host.classList.add("map-host-wrap", "map-host");
  host.style.setProperty("--view-cols", String(viewW));
  host.style.setProperty("--view-rows", String(viewH));
  host.classList.toggle("map-move-locked", !!moveLocked);

  // --- 动态状态 ---
  const dead = !!player.dead;
  const canStep = !dead && !moveLocked;
  // 不可通行地形集合（前端与 getLocationInfo 保持一致）
  const UNWALKABLE_SET = new Set(["#", "^", "!"]);
  const routeSet = new Set();
  let routeEndKey = "";
  if (routeOverlay && routeOverlay.mapId === mapId && Array.isArray(routeOverlay.path)) {
    for (const p of routeOverlay.path) routeSet.add(`${p[0]},${p[1]}`);
    if (routeOverlay.path.length) {
      const end = routeOverlay.path[routeOverlay.path.length - 1];
      routeEndKey = `${end[0]},${end[1]}`;
    }
  }
  const npcSet = new Set(
    (npcCatalog || []).filter((n) => n.map === mapId).map((n) => `${n.x},${n.y}`),
  );
  const ambushAt = new Map();
  for (const am of ambushMarkers) {
    if (am && am.map === mapId) ambushAt.set(`${am.x},${am.y}`, am.glyph);
  }
  const hurtKeys = new Set();
  if (injuryEvents && Array.isArray(injuryEvents) && injuryEvents.length > 0) {
    hurtKeys.add(`${player.px},${player.py}`);
  }
  const playerKey = player.map_id === mapId ? `${player.px},${player.py}` : "";

  // 更新每个视口内格子
  for (const btn of cache.tileByKey.values()) {
    const x = Number(btn.dataset.x);
    const y = Number(btn.dataset.y);
    const key = `${x},${y}`;
    const ch = rows[y][x];
    const here = playerKey === key;
    const hasNpc = npcSet.has(key);
    const amb = ambushAt.get(key);

    for (const cls of DYNAMIC_TILE_CLASSES) btn.classList.remove(cls);
    if (here) btn.classList.add("tile-player");
    if (hasNpc) btn.classList.add("tile-npc");
    if (routeSet.has(key)) btn.classList.add("tile-route");
    if (routeEndKey === key) btn.classList.add("tile-route-end");
    if (amb) btn.classList.add("tile-ambush");
    if (DANGER_SET.has(ch)) btn.classList.add("tile-danger");
    if (hurtKeys.has(key)) btn.classList.add("tile-hurt");

    btn.disabled = !canStep;
    if (UNWALKABLE_SET.has(ch)) btn.classList.add("tile-unwalkable");
    btn.title = `${m.name} (${x},${y}) \u00b7 ${LABEL_MAP[ch] || "\u672a\u77e5"}${DANGER_SET.has(ch) ? " \u26a0\u9669" : ""}`;

    const main = tileGlyph(ch, here, hasNpc);
    if (here && amb) {
      btn.innerHTML = `<span class="tile-stack" title="\u4fa0\u00b7\u9669"><span class="tile-major">\u4fa0</span><span class="tile-minor">${escapeHtml(amb)}</span></span>`;
    } else if (amb && !here) {
      if (main) {
        btn.innerHTML = `<span class="tile-stack"><span class="tile-major">${escapeHtml(main)}</span><span class="tile-minor">${escapeHtml(amb)}</span></span>`;
      } else {
        btn.textContent = amb;
      }
    } else {
      btn.textContent = main;
    }
  }

  cache.prevDynamic = {
    playerKey,
    npcSet: new Set(npcSet),
    routeSet: new Set(routeSet),
    routeEndKey,
    ambushKeys: new Set(ambushAt.keys()),
    hurtKeys: new Set(hurtKeys),
    canStep,
  };
}

function buildViewportGrid(host, viewKey, mapInfo, rows, vx, vy, viewW, viewH) {
  host.innerHTML = "";
  const frag = document.createDocumentFragment();
  const tileByKey = new Map();

  for (let dy = 0; dy < viewH; dy++) {
    for (let dx = 0; dx < viewW; dx++) {
      const x = vx + dx;
      const y = vy + dy;
      const ch = rows[y][x];
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tile";
      btn.dataset.x = String(x);
      btn.dataset.y = String(y);
      applyTerrainClass(btn, ch);
      btn.title = `${mapInfo.name} (${x},${y}) \u00b7 ${LABEL_MAP[ch] || "\u672a\u77e5"}${DANGER_SET.has(ch) ? " \u26a0\u9669" : ""}`;
      frag.appendChild(btn);
      tileByKey.set(`${x},${y}`, btn);
    }
  }
  host.appendChild(frag);
  return { viewKey, tileByKey, prevDynamic: null, onCellPick: null, delegated: false };
}

// === 工具函数 ===

function clamp(v, lo, hi) {
  return v < lo ? lo : v > hi ? hi : v;
}

function applyTerrainClass(btn, ch) {
  for (const c of BASE_TERRAIN_CLASSES) btn.classList.remove(c);
  const map = {
    "#": "tile-wall", "^": "tile-cliff", "~": "tile-water",
    ",": "tile-grass", ".": "tile-grass", F: "tile-forest",
    "&": "tile-forest", ";": "tile-mud", "/": "tile-mountainpath",
    m: "tile-mountain", T: "tile-tavern", I: "tile-tavern",
    M: "tile-market", Y: "tile-yamen", B: "tile-bridge",
    "=": "tile-river", "!": "tile-chasm", "@": "tile-ruins",
  };
  btn.classList.add(map[ch] || "tile-grass");
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function tileGlyph(ch, playerHere, npcHere) {
  if (playerHere) return "\u4fa0";
  if (npcHere) return "\u4eba";
  const g = {
    "#": "", "^": "", "~": "", "=": "\u2248", "!": "\u88c2",
    "@": "\u589f", "&": "", ",": "", ".": "", F: "", ";": "",
    "/": "\u5f84", m: "\u5cad", T: "\u6808", I: "\u6808",
    M: "\u5e02", Y: "\u8859", B: "\u6865",
  };
  return g[ch] || "";
}

const TERRAIN_CN = {
  "#": "\u5899", "^": "\u60ac\u5d16", "~": "\u9669\u6c34", ",": "\u8349\u5730", ".": "\u571f\u8def",
  "F": "\u6797\u5b50", ";": "\u6ce5\u5730", "/": "\u5c71\u9053", "m": "\u5c71\u5cad",
  "T": "\u5ba2\u6808", "I": "\u5ba2\u6808", "M": "\u5e02\u96c6", "Y": "\u8859\u524d", "B": "\u6865",
  "=": "\u6cb3\u9053", "!": "\u88c2\u9699", "@": "\u5e9f\u589f", "&": "\u5bc6\u6797",
};

export function getLocationInfo(mapId, maps, tx, ty) {
  const m = maps[mapId];
  if (!m || !m.rows || ty < 0 || ty >= m.rows.length) return null;
  const row = m.rows[ty];
  if (tx < 0 || tx >= row.length) return null;
  const ch = row[tx];
  // 不可通行地形：墙(#)、悬崖(^)、裂隙(!)
  const UNWALKABLE = new Set(["#", "^", "!"]);
  // 危险但可通行地形：险水(~)、废墟(@)——可走但概率受伤
  const DANGER_SET = new Set(["~", "!", "@", "^"]);
  const walkable = !UNWALKABLE.has(ch);
  return {
    mapId, mapName: m.name,
    x: tx, y: ty,
    glyph: ch,
    terrain: TERRAIN_CN[ch] || "\u672a\u77e5",
    walkable,
    dangerous: DANGER_SET.has(ch),
  };
}