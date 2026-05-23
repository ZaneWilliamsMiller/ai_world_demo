import { store, LS_KEY } from "./store.js";
import { pingModel, startGame, fetchState, movePlayer, submitFinale, inquireTile } from "./api.js";
import { el, escapeHtml } from "./ui/utils.js";
import { renderSidebar } from "./ui/sidebar.js";
import { initDialogue, setInteractionBusy, appendLog } from "./ui/dialogue.js";
import { initJournal } from "./ui/journal.js";
import { renderMap, getLocationInfo } from "./map.js";

// 初始化 UI
initDialogue(redrawMap);
initJournal();

let moveAnimating = false;
let uiPhase = "idle"; // idle | moving | encounter | locked
let moveMode = "free"; // "free"=点击寻路, "wasd"=手动逐格
const TILE_MENU_ID = "tileMenu";

function syncUiPhaseByState() {
  const s = store.getState();
  if (s.ended || s.player.dead) {
    uiPhase = "idle";
    return;
  }
  if (s.player.move_locked) {
    uiPhase = "locked";
    return;
  }
  if (uiPhase !== "moving" && uiPhase !== "encounter") {
    uiPhase = "idle";
  }
}

function setUiPhase(next) {
  uiPhase = next;
  const host = el("mapHost");
  host?.classList.toggle("map-await", next === "moving");
  if (next === "moving" || next === "encounter") {
    setInteractionBusy(true);
  } else {
    setInteractionBusy(false);
  }
}

// 订阅 Store 更新 UI(移动动画期间节流 sidebar,避免每帧 7 块全量重绘)
let sidebarRaf = 0;
store.subscribe((state) => {
  updateStatStrip(state);
  updateFinaleUI(state);
  if (moveAnimating) {
    if (!sidebarRaf) {
      sidebarRaf = requestAnimationFrame(() => {
        sidebarRaf = 0;
        renderSidebar(store.getState());
      });
    }
  } else {
    if (sidebarRaf) {
      cancelAnimationFrame(sidebarRaf);
      sidebarRaf = 0;
    }
    renderSidebar(state);
  }
});

function setCharacterSheetLocked(locked) {
  const name = el("displayName");
  const perm = el("permadeath");
  const top = el("topActions");
  if (name) {
    name.readOnly = !!locked;
    name.classList.toggle("is-readonly", !!locked);
  }
  if (perm) perm.disabled = !!locked;
  for (const r of document.querySelectorAll("input[name='gender']")) {
    r.disabled = !!locked;
  }
  top?.classList.toggle("character-locked", !!locked);
}

function buildTabs(npcs) {
  const tabs = el("npcTabs");
  tabs.innerHTML = "";
  const { activeNpc } = store.getState();

  if (!npcs || !npcs.length) {
    tabs.innerHTML = `<span class="muted">此格无人可谈(仅风闻)。</span>`;
    store.setState({ activeNpc: "jiang" });
    return;
  }

  let newActive = activeNpc;
  if (!npcs.some((n) => n.id === activeNpc)) {
    newActive = npcs[0].id;
    store.setState({ activeNpc: newActive });
  }

  const frag = document.createDocumentFragment();
  for (const n of npcs) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = n.name;
    b.dataset.id = n.id;
    if (n.id === newActive) b.classList.add("active");
    b.addEventListener("click", () => {
      store.setState({ activeNpc: n.id });
      [...tabs.children].forEach((c) => c.classList.remove("active"));
      b.classList.add("active");
    });
    frag.appendChild(b);
  }
  tabs.appendChild(frag);
}

function updateStatStrip(state) {
  const mid = state.player.map_id;
  const mn = state.maps[mid]?.name || mid;
  el("statMap").textContent = mn;
  el("statPos").textContent = `(${state.player.px}, ${state.player.py})`;
  el("statCoins").textContent = String(state.player.coins);
  el("statGender").textContent = state.player.gender;
  el("statHard").textContent = state.player.permadeath ? "开" : "关";
  el("mapName").textContent = mn;

  const scene = el("sceneLine");
  if (scene) {
    if (state.player.move_locked) {
      const reason = state.player.trap_reason || "身陷险局";
      const attempts = Number(state.player.trap_attempts || 0);
      scene.textContent = `身陷险局:${reason}${attempts > 0 ? `(已周旋 ${attempts} 次)` : ""}。请在下方对话框自由叙述脱困之法(贿赂、求援、跳水、硬冲、谈判......皆可),由眼前对头与世道判定走向。`;
    } else if (state.lastRouteOverlay) {
      const r = state.lastRouteOverlay;
      scene.textContent = `自动寻路(最小代价): 步数 ${r.steps}, 代价 ${r.cost}, 时辰 +${r.ticks}`;
    } else {
      // Display atmosphere text if available, otherwise show basic info
      const atmo = state.atmosphere;
      if (atmo) {
        // Show the "目之所及" part as scene description
        const lines = atmo.split("\n");
        const sight = lines.find(l => l.startsWith("目之所及:"));
        const header = lines.find(l => l.startsWith("【此地此刻】"));
        scene.textContent = sight ? sight.replace("目之所及:", "") : (header || atmo).replace(/【.*?】/, "");
      } else {
        scene.textContent = `${state.player.world_phase || ""}·${state.player.weather || ""} 点击地格移动;贴近 NPC 后可切换「本格人物」交谈。`;
      }
    }
  }
  // Update atmosphere display panel
  const atmoPanel = el("atmosphereText");
  if (atmoPanel) {
    atmoPanel.textContent = state.atmosphere || "";
    atmoPanel.classList.toggle("is-hidden", !state.atmosphere);
  }
}

function updateFinaleUI(state) {
  el("btnFinale").disabled = state.ended;
  el("closingNote").disabled = state.ended;
  if (state.ended && state.endingLabel) {
    el("ending").textContent = `已收束:${state.endingLabel}`;
  }
}

function handleDeath(state) {
  const tip = state.player.death_reason || "路断人亡";
  const wipe = state.player.permadeath ? "\n\n「真实江湖」已启用:本机存档已清,江湖另起一行。" : "";
  window.alert(`江湖无常:${tip}${wipe}`);
  if (state.player.permadeath) localStorage.removeItem(LS_KEY);
  location.reload();
}

// ──── WASD 手动移动 ────
function setupWASD() {
  let keyHeld = false;
  const DIR = {
    "w": [0, -1], "arrowup": [0, -1],
    "s": [0, 1], "arrowdown": [0, 1],
    "a": [-1, 0], "arrowleft": [-1, 0],
    "d": [1, 0], "arrowright": [1, 0],
  };

  document.addEventListener("keydown", async (ev) => {
    if (ev.repeat || keyHeld) return;
    // 不在对话输入框时响应键盘
    if (ev.target.tagName === "INPUT" || ev.target.tagName === "TEXTAREA" || ev.target.tagName === "SELECT") return;

    const dir = DIR[ev.key.toLowerCase()];
    if (!dir) return;
    ev.preventDefault();

    // 按 M 键切换移动模式
    if (ev.key.toLowerCase() === "m" && !ev.ctrlKey && !ev.metaKey) {
      moveMode = moveMode === "wasd" ? "free" : "wasd";
      el("modePill").textContent = moveMode === "wasd" ? "WASD" : "点击";
      el("modePill").classList.toggle("mode-wasd", moveMode === "wasd");
      appendLog("系统", moveMode === "wasd" ? "已切换为 WASD 逐格步行,按 M 切回点击寻路" : "已切回点击寻路模式", "bubble-meta");
      return;
    }

    const state = store.getState();
    if (!state.playerId || state.ended || state.player.dead || state.player.move_locked) return;
    if (uiPhase !== "idle" || moveAnimating) return;

    const [dx, dy] = dir;
    const tx = state.player.px + dx;
    const ty = state.player.py + dy;

    // 检查目标格是否可走
    const info = getLocationInfo(state.player.map_id, state.maps, tx, ty);
    if (!info || !info.walkable) return;

    keyHeld = true;
    await doWalk(tx, ty);
    keyHeld = false;
  });

  document.addEventListener("keyup", () => { keyHeld = false; });
}

// ──── 共享行走逻辑 ────
async function doWalk(tx, ty) {
  const state = store.getState();
  if (!state.playerId || state.ended || state.player.dead || uiPhase !== "idle") return;
  hideTileMenu();
  setUiPhase("moving");
  try {
    const data = await movePlayer(tx, ty);
    await applyMoveResult(data);
  } finally {
    if (uiPhase === "moving") {
      syncUiPhaseByState();
      if (uiPhase !== "locked") setUiPhase("idle");
    }
  }
}

async function applyMoveResult(data) {
  if (!data) return;
  const currState = store.getState();
  if (Array.isArray(data.npc_catalog)) {
    store.setState({ npcCatalog: data.npc_catalog });
  }
  let routeOverlay = null;
  if (Array.isArray(data.path) && data.path.length) {
    routeOverlay = {
      mapId: data.path_map_id || currState.player.map_id,
      path: data.path,
      cost: Number(data.path_cost || 0),
      ticks: Number(data.path_ticks || 0),
      steps: data.path.length,
    };
  }
  store.setState({
    events: data.events || currState.events,
    lastRouteOverlay: routeOverlay,
    atmosphere: data.atmosphere || currState.atmosphere || "",
    lastInjuryEvents: data.injuries || [],
  });
  // 显示受伤消息
  if (Array.isArray(data.injuries) && data.injuries.length > 0) {
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
    const fe = data.forced_encounter;
    const { doTalk } = await import('./ui/dialogue.js');
    await doTalk(fe.user_line, fe.npc_id, redrawMap);
    syncUiPhaseByState();
  } else if (data.player?.move_locked) {
    const { appendLog } = await import('./ui/dialogue.js');
    const lockNpc = data.player.move_lock_npc_id || "jiang";
    const reason = data.player.trap_reason || "身陷险局";
    store.setState({ activeNpc: lockNpc });
    buildTabs(data.npcs_here || []);
    appendLog(
      "系统",
      `你已被困:${reason}\n请在下方对话框写一句「你打算如何脱身」(贿赂、求援、跳水、硬冲、谈判皆可),由眼前对头与世道判定走向。`,
      "bubble-meta",
    );
    const msgEl = el("msg");
    if (msgEl) { msgEl.disabled = false; msgEl.focus(); }
  }
  if (uiPhase !== "locked") setUiPhase("idle");
}

// ──── 格子点击菜单 ────
function showTileMenu(tx, ty, ev) {
  hideTileMenu();
  const state = store.getState();
  const info = getLocationInfo(state.player.map_id, state.maps, tx, ty);
  if (!info || !info.walkable) return;

  const menu = document.createElement("div");
  menu.id = TILE_MENU_ID;
  menu.className = "tile-menu";
  menu.innerHTML = `
    <div class="tile-menu-head">${info.mapName} (${tx},${ty}) · ${info.terrain}</div>
    <button class="tile-menu-btn" data-act="pathfind">⏩ 自动寻路前往(${costHint(state, tx, ty)})</button>
    <button class="tile-menu-btn" data-act="inquire">🔍 向风闻子打探此地</button>
    <button class="tile-menu-btn tile-menu-cancel">✕ 取消</button>
  `;

  menu.addEventListener("click", async (e) => {
    const btn = e.target.closest(".tile-menu-btn");
    if (!btn) return;
    const act = btn.dataset.act;
    hideTileMenu();
    if (act === "pathfind") {
      await doWalk(tx, ty);
    } else if (act === "inquire") {
      await doInquire(tx, ty);
    }
  });

  // 定位菜单:贴在地图区域内部,避免超出边界
  const mapHost = el("mapHost");
  const hr = mapHost.getBoundingClientRect();
  const x = Math.min(ev.clientX - hr.left + 8, hr.width - 200);
  const y = Math.min(ev.clientY - hr.top + 8, hr.height - 150);
  menu.style.left = `${Math.max(4, x)}px`;
  menu.style.top = `${Math.max(4, y)}px`;

  mapHost.appendChild(menu);
  // 点击其他地方关闭
  setTimeout(() => {
    document.addEventListener("click", hideTileMenu, { once: true });
  }, 0);
}

function hideTileMenu() {
  const m = document.getElementById(TILE_MENU_ID);
  if (m) m.remove();
}

function costHint(state, tx, ty) {
  const dx = Math.abs(tx - state.player.px);
  const dy = Math.abs(ty - state.player.py);
  const dist = dx + dy;
  if (dist <= 1) return "迈步";
  if (dist <= 3) return `约${dist}格`;
  return `约${dist}格`;
}

// ──── 向风闻子打探 ────
async function doInquire(tx, ty) {
  const state = store.getState();
  const info = getLocationInfo(state.player.map_id, state.maps, tx, ty);
  if (!info) return;

  appendLog("你", `[打探] 向风闻子询问 ${info.mapName}(${tx},${ty}) · ${info.terrain}`);
  setInteractionBusy(true);
  try {
    const data = await inquireTile(tx, ty);
    if (data?.reply) {
      appendLog("风闻子", data.reply);
      // 仍然更新状态
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

function redrawMap() {
  syncUiPhaseByState();
  if (moveAnimating && uiPhase === "moving") return;
  const state = store.getState();
  const host = el("mapHost");
  if (!state.playerId || !state.maps || Object.keys(state.maps).length === 0) {
    host.innerHTML = `<div class="map-placeholder muted">请先「踏入江湖」载入地图。</div>`;
    host.className = "map-host-wrap";
    return;
  }
  host.className = "map-host-wrap";

  renderMap(
    host,
    {
      mapId: state.player.map_id,
      maps: state.maps,
      player: state.player,
      npcCatalog: state.npcCatalog,
      ambushMarkers: state.ambushMarkers,
      moveLocked: !!state.player.move_locked,
      routeOverlay: state.lastRouteOverlay,
      injuryEvents: state.lastInjuryEvents || [],
    },
    async (tx, ty, ev) => {
      const currState = store.getState();
      if (!currState.playerId || currState.ended || currState.player.dead || uiPhase !== "idle") return;
      hideTileMenu();

      // 相邻格直接走(快速),远格弹菜单
      const dx = Math.abs(tx - currState.player.px);
      const dy = Math.abs(ty - currState.player.py);
      if (dx <= 1 && dy <= 1 && !(dx === 0 && dy === 0)) {
        await doWalk(tx, ty);
      } else if (dx !== 0 || dy !== 0) {
        // 非相邻格:弹出上下文菜单
        showTileMenu(tx, ty, ev);
      }
    }
  );
}

async function animateRouteOverlay(routeOverlay) {
  if (!routeOverlay || !Array.isArray(routeOverlay.path) || routeOverlay.path.length <= 2) return;
  const maxFrames = Math.min(routeOverlay.path.length, 12);
  const step = Math.max(1, Math.floor(routeOverlay.path.length / maxFrames));
  for (let i = 2; i <= routeOverlay.path.length; i += step) {
    const partial = {
      ...routeOverlay,
      path: routeOverlay.path.slice(0, i),
      steps: i,
    };
    store.setState({ lastRouteOverlay: partial });
    const live = store.getState();
    renderMap(el("mapHost"), {
      mapId: live.player.map_id,
      maps: live.maps,
      player: live.player,
      npcCatalog: live.npcCatalog,
      ambushMarkers: live.ambushMarkers,
      moveLocked: !!live.player.move_locked,
      routeOverlay: partial,
    }, () => {});
    await new Promise((r) => setTimeout(r, 35));
  }
  store.setState({ lastRouteOverlay: routeOverlay });
}

async function playMoveTrace(moveTrace, routeOverlay) {
  if (!Array.isArray(moveTrace) || !moveTrace.length) return;
  moveAnimating = true;
  // 加速动画：缩短帧间延迟，提升操作响应感
  const frameDelayMs = 80;
  const pathSoFar = [];
  try {
    for (let i = 0; i < moveTrace.length; i++) {
      const frame = moveTrace[i];
      const t0 = performance.now();
      pathSoFar.push([frame.px, frame.py]);
      const live = store.getState();
      const playerPatch = {
        ...live.player,
        map_id: frame.map_id,
        px: frame.px,
        py: frame.py,
        vigor: frame.vigor,
        spirit: frame.spirit,
      };
      const partialOverlay = routeOverlay
        ? { ...routeOverlay, path: pathSoFar.slice(), steps: Math.max(0, pathSoFar.length - 1) }
        : null;
      store.setState({ player: playerPatch, lastRouteOverlay: partialOverlay });
      renderMap(
        el("mapHost"),
        {
          mapId: playerPatch.map_id,
          maps: live.maps,
          player: playerPatch,
          npcCatalog: live.npcCatalog,
          ambushMarkers: live.ambushMarkers,
          moveLocked: !!playerPatch.move_locked,
          routeOverlay: partialOverlay,
        },
        () => {},
      );
      await new Promise((r) => requestAnimationFrame(() => r()));
      const rest = Math.max(0, frameDelayMs - (performance.now() - t0));
      if (rest > 0) await new Promise((r) => setTimeout(r, rest));
    }
  } finally {
    moveAnimating = false;
  }
}

async function hydrateFromSaveIfAny() {
  const { playerId } = store.getState();
  if (!playerId) return;
  el("savePill").textContent = `存档:${playerId.slice(0, 8)}...(请核对名号后点「踏入江湖」)`;
  try {
    const d = await fetchState();
    if (d) {
      if (Array.isArray(d.npc_catalog)) {
        store.setState({ npcCatalog: d.npc_catalog });
      }
      if (d.display_name) el("displayName").value = d.display_name;
      const g = d.player?.gender;
      if (g && ["男", "女", "未言"].includes(g)) {
        const radio = document.querySelector(`input[name="gender"][value="${g}"]`);
        if (radio) radio.checked = true;
      }
      if (typeof d.player?.permadeath === "boolean") el("permadeath").checked = d.player.permadeath;
    }
  } catch {
    /* ignore */
  }
}

el("btnStart").addEventListener("click", async () => {
  const { playerId } = store.getState();
  if (!el("displayName").value.trim() && playerId) {
    await hydrateFromSaveIfAny();
  }
  const displayName = el("displayName").value.trim();
  if (!displayName) {
    window.alert("请先填写名号,再点「踏入江湖」。");
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
      ended: data.ended,
      endingLabel: data.ending_label,
      worldTitle: data.world_name,
      intro: data.intro,
      atmosphere: "",
    });
    store.updatePlayer(data.player);

    el("savePill").textContent = `存档:${data.player_id.slice(0, 8)}...`;
    if (data.world_name) {
      el("worldTitle").textContent = data.world_name;
      document.title = `${data.world_name} · 江湖行纪`;
    }
    el("intro").textContent = data.intro;

    buildTabs(data.npcs_here || []);

    el("btnJournal").disabled = false;
    setInteractionBusy(false);

    if (data.ended && data.ending_label) {
      el("ending").textContent = `已收束:${data.ending_label}`;
    }

    redrawMap();
    setCharacterSheetLocked(true);
  } finally {
    el("btnStart").disabled = false;
    el("btnStart").classList.remove("is-loading");
  }
});

el("btnNew").addEventListener("click", () => {
  localStorage.removeItem(LS_KEY);
  location.reload();
});

// 右侧栏折叠切换
el("btnToggleRight").addEventListener("click", () => {
  const sb = el("panel-sidebar-right");
  const pf = document.querySelector(".playfield");
  const btn = el("btnToggleRight");
  sb.classList.toggle("collapsed");
  pf.classList.toggle("sb-right-collapsed");
  btn.textContent = sb.classList.contains("collapsed") ? "▶" : "◀";
});

el("btnFinale").addEventListener("click", async () => {
  const state = store.getState();
  if (!state.playerId || state.ended || state.player.dead) return;
  const closingNote = el("closingNote").value.trim() || null;

  el("btnFinale").disabled = true;
  el("btnFinale").classList.add("is-loading");
  el("ending").textContent = "收束中...";

  try {
    const data = await submitFinale(closingNote);
    if (data.already) {
      store.setState({ ended: true, endingLabel: data.ending_label });
      setInteractionBusy(false);
      return;
    }
    store.setState({ ended: true, endingLabel: data.ending_label, flags: data.flags });
    setInteractionBusy(false);
    const ep = data.epilogue != null ? data.epilogue : "";
    el("ending").textContent = `${data.ending_label || ""}\n\n${ep}`;
  } finally {
    el("btnFinale").classList.remove("is-loading");
  }
});

// 初始化
async function init() {
  const d = await pingModel();
  if (d) {
    el("modelPill").textContent = `模型：${d.model}${d.world ? ` · ${d.world}` : ""}`;
  } else {
    el("modelPill").textContent = "模型：离线";
  }
  
  setupWASD();
  if (store.getState().playerId) {
    void hydrateFromSaveIfAny();
  }
}

init();
