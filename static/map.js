// 统一大地图渲染：以角色为中心画布，支持险地穿越（无拦截弹窗）
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
];

const LABEL_MAP = {
  "#": "墙",
  "^": "悬崖",
  "~": "险水",
  ",": "草地",
  ".": "土路",
  "F": "林子",
  ";": "泥地",
  "/": "山道",
  "m": "山岭",
  "T": "客栈",
  "I": "客栈",
  "M": "市集",
  "Y": "衙前",
  "B": "桥",
  "=": "河道",
  "!": "裂隙",
  "@": "废墟",
  "&": "密林",
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
 * 以玩家为中心渲染大地图视口。
 * 首次渲染构建整张 grid，后续增量更新动态样式。
 * 每次渲染后自动滚动使玩家居中。
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
  const h = rows.length;
  const w = rows[0].length;
  const layoutKey = `${mapId}:${w}x${h}`;

  let cache = CACHE.get(host);
  const layoutChanged = !cache || cache.layoutKey !== layoutKey;
  if (layoutChanged) {
    const wasDelegated = !!(cache && cache.delegated);
    cache = buildGrid(host, layoutKey, m, rows, w, h);
    cache.delegated = wasDelegated;
    CACHE.set(host, cache);
  }

  // 事件代理
  if (!cache.delegated) {
    host.addEventListener("click", (ev) => {
      const c = CACHE.get(host);
      if (!c) return;
      const btn = ev.target.closest(".tile");
      if (!btn) return;
      if (!host.contains(btn)) return;
      const fn = c.onCellPick;
      if (typeof fn !== "function") return;
      const x = Number(btn.dataset.x);
      const y = Number(btn.dataset.y);
      fn(x, y, ev);
      ev.stopPropagation();
    });
    cache.delegated = true;
  }
  cache.onCellPick = onCellPick;

  if (layoutChanged) {
    host.classList.add("map-host-wrap", "map-host");
    host.style.gridTemplateColumns = `repeat(${w}, minmax(0, 1fr))`;
    host.style.gridTemplateRows = `repeat(${h}, minmax(0, 1fr))`;
  } else if (!host.classList.contains("map-host")) {
    host.classList.add("map-host-wrap", "map-host");
  }
  host.classList.toggle("map-move-locked", !!moveLocked);

  const dead = !!player.dead;
  const canStep = !dead && !moveLocked;
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

  // 受伤闪烁：本帧受伤的格子
  const hurtKeys = new Set();
  if (injuryEvents && Array.isArray(injuryEvents) && injuryEvents.length > 0) {
    // 受伤时高亮玩家当前格
    hurtKeys.add(`${player.px},${player.py}`);
  }

  const playerKey = player.map_id === mapId ? `${player.px},${player.py}` : "";
  const prev = cache.prevDynamic || null;
  const forceAll = !prev || prev.canStep !== canStep;
  const changedKeys = forceAll
    ? new Set(cache.tileByKey.keys())
    : collectChangedKeys(
        prev,
        { playerKey, npcSet, routeSet, routeEndKey, ambushAt, hurtKeys, canStep },
      );

  for (const key of changedKeys) {
    const btn = cache.tileByKey.get(key);
    if (!btn) continue;
    const x = Number(btn.dataset.x);
    const y = Number(btn.dataset.y);
    const ch = rows[y][x];
    const here = playerKey === key;
    const hasNpc = npcSet.has(key);
    const amb = ambushAt.get(key);

    for (const cls of DYNAMIC_TILE_CLASSES) btn.classList.remove(cls);
    if (here) btn.classList.add("tile-player");
    if (hasNpc) btn.classList.add("tile-npc");
    if (routeSet.has(key)) btn.classList.add("tile-route");
    if (routeEndKey && routeEndKey === key) btn.classList.add("tile-route-end");
    if (amb) btn.classList.add("tile-ambush");
    // 险地标记（所有危险地形）
    if (DANGER_SET.has(ch)) btn.classList.add("tile-danger");
    // 受伤闪烁
    if (hurtKeys.has(key)) btn.classList.add("tile-hurt");

    // 统一地图：所有格子均可通行（险地靠 cost 和受伤概率平衡）
    btn.disabled = !canStep;

    btn.title = `${m.name} (${x},${y}) · ${LABEL_MAP[ch] || "未知"}${DANGER_SET.has(ch) ? " ⚠险" : ""}`;

    const main = tileGlyph(ch, here, hasNpc);
    if (here && amb) {
      btn.innerHTML = `<span class="tile-stack" title="侠·险"><span class="tile-major">侠</span><span class="tile-minor">${escapeHtml(amb)}</span></span>`;
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

  // 大地图滚动：以玩家为中心（使用 requestAnimationFrame 防闪烁）
  if (playerKey && !layoutChanged) {
    requestAnimationFrame(() => centerOnPlayer(host, player, w, h));
  }
}

/** 滚动视口使玩家居中 */
function centerOnPlayer(host, _player, _w, _h) {
  const btn = host.querySelector(".tile-player");
  if (!btn) return;
  // 查找最近的可滚动祖先（通常是 .map-viewport）
  let container = btn.parentElement;
  while (container && container !== document.body) {
    const style = window.getComputedStyle(container);
    const overflowY = style.overflowY;
    const overflowX = style.overflowX;
    if (overflowY === "auto" || overflowY === "scroll" || overflowX === "auto" || overflowX === "scroll") {
      break;
    }
    container = container.parentElement;
  }
  if (!container || container === document.body) return;
  // 先确保地图 grid 已完成布局
  requestAnimationFrame(() => {
    const rect = btn.getBoundingClientRect();
    const parentRect = container.getBoundingClientRect();
    const scrollLeft = container.scrollLeft + rect.left - parentRect.left - parentRect.width / 2 + rect.width / 2;
    const scrollTop = container.scrollTop + rect.top - parentRect.top - parentRect.height / 2 + rect.height / 2;
    container.scrollTo({
      left: Math.max(0, scrollLeft),
      top: Math.max(0, scrollTop),
      behavior: "smooth",
    });
  });
}

function buildGrid(host, layoutKey, mapInfo, rows, w, h) {
  host.innerHTML = "";
  const frag = document.createDocumentFragment();
  const tiles = [];
  const tileByKey = new Map();
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const ch = rows[y][x];
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tile";
      btn.dataset.x = String(x);
      btn.dataset.y = String(y);
      applyTerrainClass(btn, ch);
      btn.title = `${mapInfo.name} (${x},${y}) · ${LABEL_MAP[ch] || "未知"}${DANGER_SET.has(ch) ? " ⚠险" : ""}`;
      frag.appendChild(btn);
      tiles.push(btn);
      tileByKey.set(`${x},${y}`, btn);
    }
  }
  host.appendChild(frag);
  return { layoutKey, tiles, tileByKey, prevDynamic: null, onCellPick: null };
}

function collectChangedKeys(prev, next) {
  const out = new Set();
  if (prev.playerKey) out.add(prev.playerKey);
  if (next.playerKey) out.add(next.playerKey);
  if (prev.routeEndKey) out.add(prev.routeEndKey);
  if (next.routeEndKey) out.add(next.routeEndKey);
  unionDiffInto(out, prev.npcSet, next.npcSet);
  unionDiffInto(out, prev.routeSet, next.routeSet);
  unionDiffInto(out, prev.ambushKeys, next.ambushAt ? new Set(next.ambushAt.keys()) : new Set());
  unionDiffInto(out, prev.hurtKeys, next.hurtKeys || new Set());
  return out;
}

function unionDiffInto(out, a, b) {
  for (const k of a || []) if (!(b && b.has(k))) out.add(k);
  for (const k of b || []) if (!(a && a.has(k))) out.add(k);
}

function applyTerrainClass(btn, ch) {
  for (const c of BASE_TERRAIN_CLASSES) btn.classList.remove(c);
  if (ch === "#") btn.classList.add("tile-wall");
  else if (ch === "^") btn.classList.add("tile-cliff");
  else if (ch === "~") btn.classList.add("tile-water");
  else if (ch === "," || ch === ".") btn.classList.add("tile-grass");
  else if (ch === "F" || ch === "&") btn.classList.add("tile-forest");
  else if (ch === ";") btn.classList.add("tile-mud");
  else if (ch === "/") btn.classList.add("tile-mountainpath");
  else if (ch === "m") btn.classList.add("tile-mountain");
  else if (ch === "T" || ch === "I") btn.classList.add("tile-tavern");
  else if (ch === "M") btn.classList.add("tile-market");
  else if (ch === "Y") btn.classList.add("tile-yamen");
  else if (ch === "B") btn.classList.add("tile-bridge");
  else if (ch === "=") btn.classList.add("tile-river");
  else if (ch === "!") btn.classList.add("tile-chasm");
  else if (ch === "@") btn.classList.add("tile-ruins");
  else btn.classList.add("tile-grass");
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

const TERRAIN_CN = {
  "#": "墙", "^": "悬崖", "~": "险水", ",": "草地", ".": "土路",
  "F": "林子", ";": "泥地", "/": "山道", "m": "山岭",
  "T": "客栈", "I": "客栈", "M": "市集", "Y": "衙前", "B": "桥",
  "=": "河道", "!": "裂隙", "@": "废墟", "&": "密林",
};

export function getLocationInfo(mapId, maps, tx, ty) {
  const m = maps[mapId];
  if (!m || !m.rows || ty < 0 || ty >= m.rows.length) return null;
  const row = m.rows[ty];
  if (tx < 0 || tx >= row.length) return null;
  const ch = row[tx];
  return {
    mapId, mapName: m.name,
    x: tx, y: ty,
    glyph: ch,
    terrain: TERRAIN_CN[ch] || "未知",
    walkable: true,  // 统一地图：全部可通行
  };
}

function tileGlyph(ch, playerHere, npcHere) {
  if (playerHere) return "侠";
  if (npcHere) return "人";
  if (ch === "#") return "";
  if (ch === "^") return "";
  if (ch === "~") return "";
  if (ch === "=") return "≈";
  if (ch === "!") return "裂";
  if (ch === "@") return "墟";
  if (ch === "&") return "";
  if (ch === ",") return "";
  if (ch === ".") return "";
  if (ch === "F") return "";
  if (ch === ";") return "";
  if (ch === "/") return "径";
  if (ch === "m") return "岭";
  if (ch === "T" || ch === "I") return "栈";
  if (ch === "M") return "市";
  if (ch === "Y") return "衙";
  if (ch === "B") return "桥";
  return "";
}