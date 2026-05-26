/**
 * Map Module - Viewport rendering with ResizeObserver for optimal performance.
 * Dynamic viewport centering on player with efficient tile updates.
 */

const TARGET_TILE = 32;
const MIN_TILES = 9;
const MAX_TILES = 51;

const DYNAMIC_TILE_CLASSES = [
  "tile-player", "tile-npc", "tile-route", "tile-route-end",
  "tile-danger", "tile-hurt", "tile-ambush", "tile-unwalkable"
];

const UNWALKABLE_SET = new Set(["#", "^", "!"]);
const DANGER_SET = new Set(["~", "!", "@", "^"]);

const TERRAIN_CLASS_MAP = {
  "#": "tile-wall", "^": "tile-cliff", "~": "tile-water",
  ",": "tile-grass", ".": "tile-grass", F: "tile-forest",
  "&": "tile-forest", ";": "tile-mud", "/": "tile-mountainpath",
  m: "tile-mountain", T: "tile-tavern", I: "tile-tavern",
  M: "tile-market", Y: "tile-yamen", B: "tile-bridge",
  "=": "tile-river", "!": "tile-chasm", "@": "tile-ruins"
};

export function renderMap(host, opts, onCellPick) {
  const {
    mapId, maps, player, npcCatalog,
    ambushMarkers = [], moveLocked = false,
    routeOverlay = null, injuryEvents = []
  } = opts;

  const m = maps[mapId];
  if (!m || !m.rows || !m.rows.length) {
    host.innerHTML = '<div class="map-placeholder muted">地图未载入</div>';
    return { destroy: () => {} };
  }

  const rows = m.rows;
  const mapW = rows[0].length;
  const mapH = rows.length;

  // Compute viewport dimensions from container
  const rect = host.getBoundingClientRect();
  const gap = 2;
  const colsFit = Math.max(MIN_TILES, Math.floor((rect.width + gap) / (TARGET_TILE + gap)));
  const rowsFit = Math.max(MIN_TILES, Math.floor((rect.height + gap) / (TARGET_TILE + gap)));
  const viewW = Math.min(colsFit, mapW, MAX_TILES);
  const viewH = Math.min(rowsFit, mapH, MAX_TILES);

  // Viewport origin: center on player, clamp at edges
  const playerOnMap = player.map_id === mapId;
  const vx = clamp(
    (playerOnMap ? player.px : Math.floor(mapW / 2)) - Math.floor(viewW / 2),
    0, Math.max(0, mapW - viewW)
  );
  const vy = clamp(
    (playerOnMap ? player.py : Math.floor(mapH / 2)) - Math.floor(viewH / 2),
    0, Math.max(0, mapH - viewH)
  );

  const viewKey = `${mapId}:${vx},${vy}:${viewW}x${viewH}`;

  // Build grid only when view key changes
  let cache = host._mapCache;
  const layoutChanged = !cache || cache.viewKey !== viewKey;

  if (layoutChanged) {
    host.innerHTML = "";
    const frag = document.createDocumentFragment();

    for (let dy = 0; dy < viewH; dy++) {
      for (let dx = 0; dx < viewW; dx++) {
        const x = vx + dx;
        const y = vy + dy;
        const ch = rows[y]?.[x] || ",";
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = `tile ${TERRAIN_CLASS_MAP[ch] || "tile-grass"}`;
        btn.dataset.x = String(x);
        btn.dataset.y = String(y);
        btn.title = `${m.name} (${x},${y}) · ${tileLabel(ch)}${DANGER_SET.has(ch) ? " ⚠" : ""}`;
        btn.textContent = tileGlyph(ch, false, false);
        frag.appendChild(btn);
      }
    }
    host.appendChild(frag);
    cache = { viewKey, cells: host.querySelectorAll(".tile") };
    host._mapCache = cache;
  }

  // Setup click handler once
  if (!cache.clickHandler) {
    const handler = (ev) => {
      const btn = ev.target.closest(".tile");
      if (!btn || !host.contains(btn) || btn.disabled || !onCellPick) return;
      const tx = Number(btn.dataset.x);
      const ty = Number(btn.dataset.y);
      onCellPick(tx, ty, ev);
      ev.stopPropagation();
    };
    host.addEventListener("click", handler);
    cache.clickHandler = handler;
  }

  // Setup ResizeObserver for responsive resizing
  if (!host._resizeObs) {
    host._resizeObs = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 8 && entry.contentRect.height > 8) {
          host._mapCache = null; // Force rebuild on resize
          renderMap(host, opts, onCellPick);
        }
      }
    });
    host._resizeObs.observe(host);
  }

  // Apply CSS variables
  host.classList.add("map-host-wrap", "map-host");
  host.style.setProperty("--view-cols", String(viewW));
  host.style.setProperty("--view-rows", String(viewH));
  host.classList.toggle("map-move-locked", !!moveLocked);

  // Render dynamic states efficiently
  renderDynamicTiles(cache.cells, {
    mapId, rows, mapW, mapH,
    player, npcCatalog, ambushMarkers,
    routeOverlay, moveLocked, injuryEvents
  });

  return {
    destroy: () => {
      if (host._resizeObs) {
        host._resizeObs.disconnect();
        host._resizeObs = null;
      }
      host._mapCache = null;
    }
  };
}

function renderDynamicTiles(cells, opts) {
  const {
    rows, mapW, mapH, player, npcCatalog,
    ambushMarkers, routeOverlay, moveLocked, injuryEvents
  } = opts;

  const mapId = opts.mapId;
  const dead = !!player.dead;
  const canStep = !dead && !moveLocked;
  const playerKey = player.map_id === mapId ? `${player.px},${player.py}` : "";

  // Build coordinate sets once
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
    (npcCatalog ||[])
    .filter((n) => n.map === mapId)
    .map((n) => `${n.x},${n.y}`)
  );

  const ambushAt = new Map();
  for (const am of ambushMarkers) {
    if (am && am.map === mapId) ambushAt.set(`${am.x},${am.y}`, am.glyph);
  }

  const hurtKeys = new Set();
  if (injuryEvents?.length) hurtKeys.add(playerKey);

  // Update each cell
  for (const btn of cells) {
    const x = Number(btn.dataset.x);
    const y = Number(btn.dataset.y);
    const key = `${x},${y}`;
    const ch = rows[y]?.[x] || ",";
    const here = playerKey === key;
    const hasNpc = npcSet.has(key);
    const amb = ambushAt.get(key);

    // Clear dynamic classes
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

    // Update glyph
    const main = tileGlyph(ch, here, hasNpc);
    const newHtml = here && amb
      ? `<span class="tile-stack"><span class="tile-major">侠</span><span class="tile-minor">${escapeHtml(amb)}</span></span>`
      : amb && !here
        ? `<span class="tile-stack"><span class="tile-major">${hasNpc ? "人" : escapeHtml(main)}</span><span class="tile-minor">${escapeHtml(amb)}</span></span>`
        : null;

    if (newHtml) {
      btn.innerHTML = newHtml;
    } else if (btn.innerHTML && btn.innerHTML !== main) {
      btn.textContent = main;
    }
  }
}

// ─── Helpers ───

function clamp(v, lo, hi) {
  return v < lo ? lo : v > hi ? hi : v;
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

function tileGlyph(ch, playerHere, npcHere) {
  if (playerHere) return "侠";
  if (npcHere) return "人";
  const g = {
    "#": "", "^": "", "~": "", "=": "≈", "!": "裂",
    "@": "墟", "&": "", ",": "", ".": "", F: "",
    ";": "", "/": "径", m: "岭", T: "栈", I: "栈",
    M: "市", Y: "衙", B: "桥"
  };
  return g[ch] || "";
}

function tileLabel(ch) {
  const labels = {
    "#": "墙", "^": "悬崖", "~": "险水", ",": "草地", ".": "土路",
    "F": "林子", ";": "泥地", "/": "山道", m: "山岭",
    "T": "客栈", I: "客栈", M: "市集", Y: "衙前", B: "桥",
    "=": "河道", "!": "裂隙", "@": "废墟", "&": "密林"
  };
  return labels[ch] || "未知";
}

export function getLocationInfo(mapId, maps, tx, ty) {
  const m = maps[mapId];
  if (!m || !m.rows || ty < 0 || ty >= m.rows.length) return null;
  const row = m.rows[ty];
  if (tx < 0 || tx >= row.length) return null;
  const ch = row[tx];
  return {
    mapId, mapName: m.name, x: tx, y: ty, glyph: ch,
    terrain: tileLabel(ch), walkable: !UNWALKABLE_SET.has(ch),
    dangerous: DANGER_SET.has(ch)
  };
}