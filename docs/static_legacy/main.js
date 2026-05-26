/**
 * Main Module - Game initialization, movement, and UI orchestration.
 * Focus: performance, correctness, and expanded playability.
 */
import { store, LS_KEY } from "./store.js";
import { pingModel, startGame, fetchState, movePlayer, submitFinale, inquireTile } from "./api.js";
import { el, escapeHtml, showToast } from "./ui/utils.js";
import { renderSidebar } from "./ui/sidebar.js";
import { initDialogue, setInteractionBusy, appendLog } from "./ui/dialogue.js";
import { initJournal } from "./ui/journal.js";
import { renderMap, getLocationInfo } from "./map.js";
import { initEffects, destroyEffects } from "./effects.js";

// ─── State ───
let moveAnimating = false;
let uiPhase = "idle"; // idle | moving | encounter | locked
let moveMode = "free";
let lastPlayerKey = "";
const TILE_MENU_ID = "tileMenu";

// ─── Init ───
initDialogue(redrawMap);
initJournal();
setupWASD();
setupKeyboardShortcuts();
registerCustomEvents();

// ─── UI Phase Management ───
function syncUiPhaseByState() {
  const s = store.getState();
  if (s.ended || s.player.dead) { uiPhase = "idle"; return; }
  if (s.player.move_locked) { uiPhase = "locked"; return; }
  if (uiPhase !== "moving" && uiPhase !== "encounter") uiPhase = "idle";
}

function setUiPhase(next) {
  uiPhase = next;
  el("mapHost")?.classList.toggle("map-await", next === "moving");
  setInteractionBusy(next === "moving" || next === "encounter");
}

// ─── Store Subscription with rAF throttling ───
let sidebarRafId = 0, statRafId = 0;
store.subscribe((state) => {
  updateFinaleUI(state);
  if (moveAnimating) {
    if (!statRafId) statRafId = requestAnimationFrame(() => {
      statRafId = 0;
      updateStatStrip(state);
    });
    if (!sidebarRafId) sidebarRafId = requestAnimationFrame(() => {
      sidebarRafId = 0;
      renderSidebar(state);
    });
  } else {
    cancelAnimationFrame(statRafId); statRafId = 0;
    cancelAnimationFrame(sidebarRafId); sidebarRafId = 0;
    updateStatStrip(state);
    renderSidebar(state);
  }
});

// ─── Keyboard Shortcuts ───
function setupKeyboardShortcuts() {
  document.addEventListener("keydown", (ev) => {
    if (ev.target.tagName === "INPUT" || ev.target.tagName === "TEXTAREA") return;

    switch (ev.key.toLowerCase()) {
      case "j": el("btnJournal")?.click(); break;
      case "t": el("msg")?.focus(); break;
      case "s": if (!ev.ctrlKey) el("btnSend")?.click(); break;
      case "escape": hideTileMenu(); break;
    }
  });
}

// ─── WASD Movement ───
function setupWASD() {
  let keyHeld = false;
  const DIR_MAP = {
    w: [0, -1], arrowup: [0, -1],
    s: [0, 1], arrowdown: [0, 1],
    a: [-1, 0], arrowleft: [-1, 0],
    d: [1, 0], arrowright: [1, 0]
  };

  document.addEventListener("keydown", async (ev) => {
    if (ev.repeat || keyHeld) return;
    if (ev.target.tagName === "INPUT" || ev.target.tagName === "TEXTAREA") return;

    // Toggle move mode with M
    if (ev.key.toLowerCase() === "m") {
      moveMode = moveMode === "wasd" ? "free" : "wasd";
      el("modePill").textContent = moveMode === "wasd" ? "WASD" : "点击";
      el("modePill").classList.toggle("mode-wasd", moveMode === "wasd");
      appendLog("系统", moveMode === "wasd"
        ? "已切换为 WASD 逐格步行,按 M 切回点击寻路"
        : "已切回点击寻路模式", "bubble-meta");
      return;
    }

    const dir = DIR_MAP[ev.key.toLowerCase()];
    if (!dir) return;
    ev.preventDefault();

    const state = store.getState();
    if (!state.playerId || state.ended || state.player.dead || state.player.move_locked) return;
    if (uiPhase !== "idle" || moveAnimating) return;

    const [dx, dy] = dir;
    const tx = state.player.px + dx;
    const ty = state.player.py + dy;
    const info = getLocationInfo(state.player.map_id, state.maps, tx, ty);
    if (!info || !info.walkable) return;

    keyHeld = true;
    await doWalk(tx, ty);
    keyHeld = false;
  });
  document.addEventListener("keyup", () => { keyHeld = false; });
}

// ─── Movement ───
async function doWalk(tx, ty) {
  const state = store.getState();
  if (!state.playerId || state.ended || state.player.dead || uiPhase !== "idle") return;
  hideTileMenu();
  setUiPhase("moving");
  try {
    const data = await movePlayer(tx, ty);
    await applyMoveResult(data);
  } catch (err) {
    appendLog("系统", `移动失败：${err.message}`, "bubble-meta");
  } finally {
    if (uiPhase === "moving") {
      syncUiPhaseByState();
      if (uiPhase !== "locked") setUiPhase("idle");
    }
  }
}

// ─── Apply Move Result ───
async function applyMoveResult(data) {
  if (!data) return;
  const currState = store.getState();

  // Build route overlay from path
  let routeOverlay = null;
  if (Array.isArray(data.path) && data.path.length) {
    routeOverlay = {
      mapId: data.path_map_id || currState.player.map_id,
      path: data.path,
      cost: Number(data.path_cost || 0),
      ticks: Number(data.path_ticks || 0),
      steps: data.path.length
    };
  }

  store.setState({
    npcCatalog: Array.isArray(data.npc_catalog) ? data.npc_catalog : currState.npcCatalog,
    events: data.events || currState.events,
    lastRouteOverlay: routeOverlay,
    atmosphere: data.atmosphere || currState.atmosphere || "",
    lastInjuryEvents: data.injuries || []
  });

  // Show injury messages
  if (Array.isArray(data.injuries) && data.injuries.length) {
    for (const inj of data.injuries) {
      appendLog("险", `⚠ ${inj}`, "bubble-meta");
    }
  }

  if (data.dynamic_encounter?.scene) {
    appendLog("天意", data.dynamic_encounter.scene, "bubble-meta");
    if (data.dynamic_encounter.hint) {
      appendLog("风闻", data.dynamic_encounter.hint, "bubble-meta");
    }
  }

  const hasTrace = Array.isArray(data.move_trace) && data.move_trace.length;
  if (hasTrace) {
    await playMoveTrace(data.move_trace, routeOverlay);
  }

  store.updatePlayer(data.player);
  syncUiPhaseByState();

  if (data.forced_encounter?.npc_id) {
    store.setState({ activeNpc: data.forced_encounter.npc_id });
  }

  buildTabs(data.npcs_here || []);

  if (data.player.dead) {
    handleDeath(store.getState());
    return;
  }

  if (!hasTrace) {
    await animateRouteOverlay(routeOverlay);
  }

  redrawMap();

  if (data.forced_encounter) {
    setUiPhase("encounter");
    const { doTalk } = await import("./ui/dialogue.js");
    await doTalk(data.forced_encounter.user_line, data.forced_encounter.npc_id, redrawMap);
    syncUiPhaseByState();
  } else if (data.player?.move_locked) {
    const lockNpc = data.player.move_lock_npc_id || "jiang";
    const reason = data.player.trap_reason || "身陷险局";
    store.setState({ activeNpc: lockNpc });
    buildTabs(data.npcs_here || []);
    appendLog("系统",
      `你已被困：${reason}\n请在下方写一句「你打算如何脱身」，由眼前对头与世道判定走向。`,
      "bubble-meta");
    el("msg").focus();
  }

  if (uiPhase !== "locked") setUiPhase("idle");
}

// ─── Route Animation ───
async function animateRouteOverlay(routeOverlay) {
  if (!routeOverlay || !Array.isArray(routeOverlay.path) || routeOverlay.path.length <= 2) return;
  const maxFrames = Math.min(routeOverlay.path.length, 12);
  const step = Math.max(1, Math.floor(routeOverlay.path.length / maxFrames));
  for (let i = 2; i <= routeOverlay.path.length; i += step) {
    const partial = { ...routeOverlay, path: routeOverlay.path.slice(0, i), steps: i };
    store.setState({ lastRouteOverlay: partial });
    const live = store.getState();
    renderMap(el("mapHost"), {
      mapId: live.player.map_id, maps: live.maps, player: live.player,
      npcCatalog: live.npcCatalog, ambushMarkers: live.ambushMarkers,
      moveLocked: !!live.player.move_locked, routeOverlay: partial
    }, () => {});
    await wait(35);
  }
  store.setState({ lastRouteOverlay: routeOverlay });
}

// ─── Move Trace Playback ───
async function playMoveTrace(moveTrace, routeOverlay) {
  if (!Array.isArray(moveTrace) || !moveTrace.length) return;
  moveAnimating = true;
  const FRAME_MS = 80;
  const pathSoFar = [];

  try {
    for (let i = 0; i < moveTrace.length; i++) {
      const t0 = performance.now();
      const frame = moveTrace[i];
      pathSoFar.push([frame.px, frame.py]);

      const live = store.getState();
      const playerPatch = {
        ...live.player, map_id: frame.map_id, px: frame.px, py: frame.py,
        vigor: frame.vigor, spirit: frame.spirit
      };
      const partialOverlay = routeOverlay
        ? { ...routeOverlay, path: pathSoFar.slice(), steps: Math.max(0, pathSoFar.length - 1) }
        : null;

      store.setState({ player: playerPatch, lastRouteOverlay: partialOverlay });
      renderMap(el("mapHost"), {
        mapId: playerPatch.map_id, maps: live.maps, player: playerPatch,
        npcCatalog: live.npcCatalog, ambushMarkers: live.ambushMarkers,
        moveLocked: !!playerPatch.move_locked, routeOverlay: partialOverlay
      }, () => {});

      await wait(Math.max(0, FRAME_MS - (performance.now() - t0)));
    }
  } finally {
    moveAnimating = false;
  }
}

// ─── Stat Strip ───
function updateStatStrip(state) {
  const mid = state.player.map_id;
  const mn = state.maps[mid]?.name || mid;
  el("statMap").textContent = mn;
  el("statPos").textContent = `(${state.player.px}, ${state.player.py})`;
  el("statCoins").textContent = String(state.player.coins ?? 0);
  el("statGender").textContent = state.player.gender || "—";
  el("statHard").textContent = state.player.permadeath ? "开" : "关";
  el("mapName").textContent = mn;

  const scene = el("sceneLine");
  if (scene) {
    if (state.player.move_locked) {
      const reason = state.player.trap_reason || "身陷险局";
      const attempts = Number(state.player.trap_attempts || 0);
      scene.textContent = `身陷险局：${reason}${attempts > 0 ? `（已周旋 ${attempts} 次）` : ""}。请在下方自由叙述脱困之法。`;
    } else if (state.lastRouteOverlay) {
      const r = state.lastRouteOverlay;
      scene.textContent = `自动寻路：步数 ${r.steps}，代价 ${r.cost}，时辰 +${r.ticks}`;
    } else {
      const atmo = state.atmosphere;
      if (atmo) {
        const lines = atmo.split("\n");
        const sight = lines.find(l => l.startsWith("目之所及："));
        const header = lines.find(l => l.startsWith("【此地此刻】"));
        scene.textContent = sight ? sight.replace("目之所及：", "") : (header || atmo).replace(/【.*?】/, "");
      } else {
        scene.textContent = `${state.player.world_phase || ""}·${state.player.weather || ""} · 点击地格移动`;
      }
    }
  }

  const atmoPanel = el("atmosphereText");
  if (atmoPanel) {
    atmoPanel.textContent = state.atmosphere || "";
    atmoPanel.classList.toggle("is-hidden", !state.atmosphere);
  }
}

// ─── Character Sheet ───
function setCharacterSheetLocked(locked) {
  const name = el("displayName"), perm = el("permadeath"), top = el("topActions");
  if (name) { name.readOnly = !!locked; name.classList.toggle("is-readonly", !!locked); }
  if (perm) perm.disabled = !!locked;
  document.querySelectorAll("input[name='gender']").forEach(r => { r.disabled = !!locked; });
  top?.classList.toggle("character-locked", !!locked);
}

// ─── NPC Tabs ───
function buildTabs(npcs) {
  const tabs = el("npcTabs");
  tabs.innerHTML = "";
  const { activeNpc } = store.getState();

  if (!npcs?.length) {
    tabs.innerHTML = `<span class="muted">此格无人可谈（仅风闻）。</span>`;
    store.setState({ activeNpc: "jiang" });
    return;
  }

  let newActive = activeNpc;
  if (!npcs.some((n) => n.id === activeNpc)) newActive = npcs[0].id;
  store.setState({ activeNpc: newActive });

  const frag = document.createDocumentFragment();
  for (const n of npcs) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = n.name;
    b.dataset.id = n.id;
    if (n.id === newActive) b.classList.add("active");
    b.addEventListener("click", () => {
      store.setState({ activeNpc: n.id });
      [...tabs.children].forEach(c => c.classList.remove("active"));
      b.classList.add("active");
    });
    frag.appendChild(b);
  }
  tabs.appendChild(frag);
}

// ─── Death Handler ───
function handleDeath(state) {
  const tip = state.player.death_reason || "路断人亡";
  const wipe = state.player.permadeath
    ? "\n\n「真实江湖」已启用：本机存档已清，江湖另起一行。"
    : "";
  showToast(`江湖无常：${tip}${wipe}`, "error");
  if (state.player.permadeath) localStorage.removeItem(LS_KEY);
  setTimeout(() => location.reload(), 2500);
}

// ─── Finale UI ───
function updateFinaleUI(state) {
  el("btnFinale").disabled = state.ended;
  el("closingNote").disabled = state.ended;
  if (state.ended && state.endingLabel) {
    el("ending").textContent = `已收束：${state.endingLabel}`;
  }
}

// ─── Tile Click Menu ───
function showTileMenu(tx, ty, ev) {
  hideTileMenu();
  const state = store.getState();
  const info = getLocationInfo(state.player.map_id, state.maps, tx, ty);
  if (!info) return;

  const npcHere = (state.npcCatalog || []).find(
    (n) => n.map === state.player.map_id && n.x === tx && n.y === ty
  );

  const menu = document.createElement("div");
  menu.id = TILE_MENU_ID;
  menu.className = "tile-menu";
  const walkTag = info.walkable ? "" : " ⛔不可通行";
  let html = `<div class="tile-menu-head">${info.mapName} (${tx},${ty}) · ${info.terrain}${walkTag}</div>`;

  if (info.walkable) {
    html += `<button class="tile-menu-btn" data-act="pathfind">⏩ 自动寻路前往</button>`;
  }
  if (npcHere) {
    html += `<button class="tile-menu-btn" data-act="talk">💬 与${npcHere.name}交谈</button>`;
  }
  html += `<button class="tile-menu-btn" data-act="inquire">🔍 向风闻子打探此地</button>`;
  html += `<button class="tile-menu-btn tile-menu-cancel">✕ 取消</button>`;
  menu.innerHTML = html;

  menu.addEventListener("click", async (e) => {
    const btn = e.target.closest(".tile-menu-btn");
    if (!btn) return;
    const act = btn.dataset.act;
    hideTileMenu();
    if (act === "pathfind") await doWalk(tx, ty);
    else if (act === "inquire") await doInquire(tx, ty);
    else if (act === "talk" && npcHere) await doNpcTalk(npcHere.id, npcHere.name);
  });

  const mapHost = el("mapHost");
  const hr = mapHost.getBoundingClientRect();
  const x = Math.min(ev.clientX - hr.left + 8, hr.width - 200);
  const y = Math.min(ev.clientY - hr.top + 8, hr.height - 150);
  menu.style.left = `${Math.max(4, x)}px`;
  menu.style.top = `${Math.max(4, y)}px`;
  mapHost.appendChild(menu);
  setTimeout(() => document.addEventListener("click", hideTileMenu, { once: true }), 0);
}

function hideTileMenu() {
  document.getElementById(TILE_MENU_ID)?.remove();
}

// ─── NPC Talk ───
async function doNpcTalk(npcId, npcName) {
  const state = store.getState();
  if (!state.playerId || state.ended || state.player.dead) return;
  store.setState({ activeNpc: npcId });
  appendLog("你", `走向${npcName || npcId}……`);
  el("msg")?.focus();
}

// ─── Inquire Tile ───
async function doInquire(tx, ty) {
  const info = getLocationInfo(store.getState().player.map_id, store.getState().maps, tx, ty);
  if (!info) return;

  appendLog("你", `[打探] 向风闻子询问 ${info.mapName}(${tx},${ty}) · ${info.terrain}`);
  setInteractionBusy(true);
  try {
    const data = await inquireTile(tx, ty);
    if (data?.reply) {
      appendLog("风闻子", data.reply);
      if (data.flags) store.setState({ flags: data.flags });
      if (data.favor) store.setState({ favor: { ...store.getState().favor, ...data.favor } });
      if (data.rumors) store.setState({ rumors: data.rumors });
      if (data.events) store.setState({ events: data.events });
      store.updatePlayer(data.player);
      if (data.npcs_here) store.setState({ npcsHere: data.npcs_here });
      if (data.atmosphere) store.setState({ atmosphere: data.atmosphere });
    }
  } catch (e) {
    appendLog("风闻子", `[打探失败] ${e.message || "网络不通"}`, "bubble-meta");
  } finally {
    setInteractionBusy(false);
  }
}

// ─── Map Rendering ───
let currentMapRender = null;
function redrawMap() {
  syncUiPhaseByState();
  if (moveAnimating && uiPhase === "moving") return;
  const state = store.getState();
  const host = el("mapHost");

  if (!state.playerId || !state.maps || !Object.keys(state.maps).length) {
    host.innerHTML = `<div class="map-placeholder muted">请先「踏入江湖」载入地图。</div>`;
    host.className = "map-host-wrap";
    return;
  }
  host.className = "map-host-wrap";

  const playerKey = `${state.player.px},${state.player.py}`;
  if (playerKey !== lastPlayerKey) {
    lastPlayerKey = playerKey;
  }

  if (currentMapRender?.destroy) {
    try { currentMapRender.destroy(); } catch (_) {}
  }
  currentMapRender = renderMap(
    host,
    {
      mapId: state.player.map_id, maps: state.maps, player: state.player,
      npcCatalog: state.npcCatalog, ambushMarkers: state.ambushMarkers,
      moveLocked: !!state.player.move_locked,
      routeOverlay: state.lastRouteOverlay,
      injuryEvents: state.lastInjuryEvents || []
    },
    async (tx, ty, ev) => {
      const currState = store.getState();
      if (!currState.playerId || currState.ended || currState.player.dead || uiPhase !== "idle") return;
      hideTileMenu();

      const dx = Math.abs(tx - currState.player.px);
      const dy = Math.abs(ty - currState.player.py);

      if (dx <= 1 && dy <= 1 && !(dx === 0 && dy === 0)) {
        const info = getLocationInfo(currState.player.map_id, currState.maps, tx, ty);
        if (info && !info.walkable) {
          const npcHere = (currState.npcCatalog || []).find(
            (n) => n.map === currState.player.map_id && n.x === tx && n.y === ty
          );
          if (npcHere) await doNpcTalk(npcHere.id, npcHere.name);
        } else {
          await doWalk(tx, ty);
        }
      } else if (dx !== 0 || dy !== 0) {
        showTileMenu(tx, ty, ev);
      }
    }
  );
}

// ─── Save Hydration ───
async function hydrateFromSaveIfAny() {
  const { playerId } = store.getState();
  if (!playerId) return;
  el("savePill").textContent = `存档：${playerId.slice(0, 8)}……（请核对名号后点「踏入江湖」）`;
  try {
    const d = await fetchState();
    if (d) {
      if (Array.isArray(d.npc_catalog)) store.setState({ npcCatalog: d.npc_catalog });
      if (d.display_name) el("displayName").value = d.display_name;
      const g = d.player?.gender;
      if (g && ["男", "女", "未言"].includes(g)) {
        document.querySelector(`input[name="gender"][value="${g}"]`)?.click();
      }
      if (typeof d.player?.permadeath === "boolean") el("permadeath").checked = d.player.permadeath;
    }
  } catch {
    el("savePill").textContent = `存档：${playerId.slice(0, 8)}……（无法连接服务端）`;
  }
}

// ─── Utility ───
function wait(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ─── Custom Event Registration ───
function registerCustomEvents() {
  document.addEventListener("flash-coins", (e) => {
    const tip = el("statCoinsDelta");
    if (!tip || !e.detail) return;
    tip.textContent = `${e.detail > 0 ? "+" : ""}${e.detail}`;
    tip.classList.remove("delta-up", "delta-down");
    tip.classList.add(e.detail > 0 ? "delta-up" : "delta-down");
    setTimeout(() => {
      tip.textContent = "";
      tip.classList.remove("delta-up", "delta-down");
    }, 2200);
  });
}

// ─── Button Event Bindings ───
el("btnStart").addEventListener("click", async () => {
  const { playerId } = store.getState();
  if (!el("displayName").value.trim() && playerId) {
    await hydrateFromSaveIfAny();
  }
  const displayName = el("displayName").value.trim();
  if (!displayName) {
    showToast("请先填写名号，再点「踏入江湖」。", "error");
    return;
  }
  const gender = document.querySelector("input[name='gender']:checked")?.value || "未言";
  const permadeath = el("permadeath").checked;

  el("btnStart").disabled = true;
  el("btnStart").classList.add("is-loading");

  try {
    const data = await startGame(displayName, gender, permadeath);

    const npcLabels = {};
    for (const [id, v] of Object.entries(data.npc_labels || {})) {
      npcLabels[id] = v;
    }

    store.setState({
      playerId: data.player_id,
      maps: data.maps || {},
      npcCatalog: data.npc_catalog || [],
      npcLabels,
      factions: data.factions || {},
      ambushMarkers: Array.isArray(data.ambush_markers) ? data.ambush_markers : [],
      flags: data.flags || { order: 0, truth: 0, hope: 0, chaos: 0 },
      favor: data.favor || {},
      rumors: Array.isArray(data.rumors) ? data.rumors : [],
      events: Array.isArray(data.events) ? data.events : [],
      ended: data.ended, endingLabel: data.ending_label,
      worldTitle: data.world_name, intro: data.intro,
      atmosphere: ""
    });
    store.updatePlayer(data.player);

    el("savePill").textContent = `存档：${data.player_id.slice(0, 8)}……`;
    if (data.world_name) {
      el("worldTitle").textContent = data.world_name;
      document.title = `${data.world_name} · 江湖行纪`;
    }
    el("intro").textContent = data.intro;
    buildTabs(data.npcs_here || []);
    el("btnJournal").disabled = false;
    setInteractionBusy(false);
    if (data.ended && data.ending_label) {
      el("ending").textContent = `已收束：${data.ending_label}`;
    }
    redrawMap();
    setCharacterSheetLocked(true);
    initEffects();
  } finally {
    el("btnStart").disabled = false;
    el("btnStart").classList.remove("is-loading");
  }
});

el("btnNew").addEventListener("click", () => {
  localStorage.removeItem(LS_KEY);
  location.reload();
});

el("btnToggleRight").addEventListener("click", () => {
  const sb = el("panel-sidebar-right");
  sb.classList.toggle("collapsed");
  document.querySelector(".playfield")?.classList.toggle("sb-right-collapsed");
  el("btnToggleRight").textContent = sb.classList.contains("collapsed") ? "▶" : "◀";
});

el("btnFinale").addEventListener("click", async () => {
  const state = store.getState();
  if (!state.playerId || state.ended || state.player.dead) return;
  const closingNote = el("closingNote").value.trim() || null;

  el("btnFinale").disabled = true;
  el("btnFinale").classList.add("is-loading");
  el("ending").textContent = "收束中……";

  try {
    const data = await submitFinale(closingNote);
    if (data.already) {
      store.setState({ ended: true, endingLabel: data.ending_label });
      setInteractionBusy(false);
      return;
    }
    store.setState({ ended: true, endingLabel: data.ending_label, flags: data.flags });
    setInteractionBusy(false);
    el("ending").textContent = `${data.ending_label || ""}\n\n${data.epilogue ?? ""}`;
  } finally {
    el("btnFinale").classList.remove("is-loading");
  }
});

// ─── Bootstrap ───
async function init() {
  try {
    const d = await pingModel();
    if (d) {
      el("modelPill").textContent = `模型：${d.model}${d.world ? ` · ${d.world}` : ""}`;
    } else {
      el("modelPill").textContent = "模型：离线";
      el("modelPill").classList.add("pill", "danger");
    }
  } catch {
    el("modelPill").textContent = "模型：离线";
    el("modelPill").classList.add("pill", "danger");
  }

  if (store.getState().playerId) {
    try { await hydrateFromSaveIfAny(); } catch { /* silent */ }
  }

  const overlay = document.getElementById("loadingOverlay");
  if (overlay) {
    overlay.addEventListener("transitionend", () => overlay.remove(), { once: true });
    overlay.classList.add("is-hidden-fade");
  }
}

init();