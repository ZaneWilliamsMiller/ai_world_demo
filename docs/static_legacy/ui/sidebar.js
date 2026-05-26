/**
 * Sidebar Module - Selective rendering: only re-render sections that changed.
 */
import { store } from "../store.js";
import { el, escapeHtml } from "./utils.js";

/** Track last rendered values to skip unchanged sections */
const _cache = {
  vigor: null, spirit: null, spiritMax: null,
  vigorMax: null, coins: null, gender: null,
  world_day: null, world_shichen: null, weather: null,
  world_is_night: null,
  inventory: null,
  favor: null,
  rumors: null,
  events: null,
  flags: null,
  npcsHere: null,
};

function deepEqual(a, b) {
  if (a === b) return true;
  if (a == null || b == null) return a === b;
  if (typeof a !== typeof b) return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  if (Array.isArray(a)) return JSON.stringify(a) === JSON.stringify(b);
  if (typeof a === "object") return JSON.stringify(a) === JSON.stringify(b);
  return a === b;
}

export function renderSidebar(state) {
  renderVitals(state.player);
  renderClock(state);
  renderInventory(state.player.inventory);
  renderReputation(state.player.reputation, state.factions);
  renderRumors(state.rumors);
  renderEvents(state.events);
  renderFavor(state.favor, state.activeNpc);
  renderFlags(state.flags);
  renderNpcHere(state.npcsHere, state.npcLabels);
}

function renderVitals(player) {
  if (!player) return;
  const vigor = Number(player.vigor ?? 0);
  const vigorMax = Number(player.vigor_max ?? 100);
  const spirit = Number(player.spirit ?? 0);
  const spiritMax = Number(player.spirit_max ?? 100);

  if (!deepEqual(_cache.vigor, vigor)) {
    _cache.vigor = vigor;
    const sv = el("statVigor");
    if (sv) sv.textContent = String(vigor);
  }
  if (!deepEqual(_cache.vigorMax, vigorMax)) {
    _cache.vigorMax = vigorMax;
    const svm = el("statVigorMax");
    if (svm) svm.textContent = ` / ${vigorMax}`;
    const vf = el("vigorFill");
    if (vf) {
      const pct = Math.max(0, Math.min(100, vigorMax > 0 ? (vigor / vigorMax) * 100 : 0));
      vf.style.width = `${pct}%`;
      vf.classList.toggle("resource-low", vigor <= vigorMax * 0.25);
    }
  }
  if (!deepEqual(_cache.spirit, spirit)) {
    _cache.spirit = spirit;
    const ss = el("statSpirit");
    if (ss) ss.textContent = String(spirit);
    const sf = el("spiritFill");
    if (sf) {
      const pct = Math.max(0, Math.min(100, spiritMax > 0 ? (spirit / spiritMax) * 100 : 0));
      sf.style.width = `${pct}%`;
      sf.classList.toggle("resource-low", spirit <= spiritMax * 0.25);
    }
  }
  if (!deepEqual(_cache.spiritMax, spiritMax)) {
    _cache.spiritMax = spiritMax;
    const ssm = el("statSpiritMax");
    if (ssm) ssm.textContent = ` / ${spiritMax}`;
  }

  const burnTicks = Number(player.life_burn_ticks ?? 0);
  const burnMax = Number(player.life_burn_max ?? 0);
  const burnWrap = el("lifeBurnWrap");
  const burnFill = el("lifeBurnFill");
  if (burnWrap && burnFill) {
    const active = burnTicks > 0 && burnMax > 0;
    burnWrap.classList.toggle("is-hidden", !active);
    if (active) {
      const pct = Math.max(0, Math.min(100, (burnTicks / burnMax) * 100));
      burnFill.style.width = `${pct}%`;
      burnFill.classList.toggle("resource-low", pct <= 35);
    }
  }
}

export function renderFlags(flags) {
  if (!flags) return;
  if (!deepEqual(_cache.flags, flags)) {
    _cache.flags = { ...flags };
    el("fOrder").textContent = flags.order;
    el("fTruth").textContent = flags.truth;
    el("fHope").textContent = flags.hope;
    el("fChaos").textContent = flags.chaos;
  }
}

export function renderClock(state) {
  const cp = el("clockPill");
  if (!cp) return;
  if (!state.playerId) {
    cp.textContent = "江湖纪：—";
    cp.classList.toggle("clock-night", false);
    return;
  }
  const day = state.player.world_day || 1;
  const sh = state.player.world_shichen || "—";
  const w = state.player.weather || "—";
  const isNight = !!state.player.world_is_night;

  if (!deepEqual(_cache.world_day, day) || !deepEqual(_cache.world_shichen, sh) ||
      !deepEqual(_cache.weather, w) || !deepEqual(_cache.world_is_night, isNight)) {
    _cache.world_day = day;
    _cache.world_shichen = sh;
    _cache.weather = w;
    _cache.world_is_night = isNight;
    cp.textContent = `第 ${day} 日 · ${sh} · ${w}`;
    cp.classList.toggle("clock-night", isNight);
  }
}

export function renderInventory(inv) {
  const ul = el("invList");
  if (!ul) return;
  const entries = Object.entries(inv || {}).filter(([, c]) => c > 0).sort((a, b) => a[0].localeCompare(b[0], "zh"));
  const serial = JSON.stringify(entries);

  if (!deepEqual(_cache.inventory, serial)) {
    _cache.inventory = serial;
    ul.innerHTML = "";
    if (!entries.length) {
      ul.innerHTML = '<li class="rumor-empty">身无长物。</li>';
      return;
    }
    const frag = document.createDocumentFragment();
    for (const [name, c] of entries) {
      const li = document.createElement("li");
      li.innerHTML = `<span class="inv-name">${escapeHtml(name)}</span>${
        c > 1 ? `<span class="inv-count">×${c}</span>` : ""
      }`;
      frag.appendChild(li);
    }
    ul.appendChild(frag);
  }
}

export function renderReputation(rep, factions) {
  const ul = el("repList");
  if (!ul) return;
  const order = ["yamen", "biaoju", "caobang", "shuyuan", "lulin"];
  const serial = JSON.stringify({ rep, order });

  if (!deepEqual(_cache.reputation, serial)) {
    _cache.reputation = serial;
    ul.innerHTML = "";
    const frag = document.createDocumentFragment();
    for (const k of order) {
      if (!(k in factions)) continue;
      const v = Number((rep || {})[k] || 0);
      const li = document.createElement("li");
      li.className = `rep-row ${repTone(v)}`;
      const pct = Math.max(0, Math.min(100, (v + 100) / 2));
      li.innerHTML = `
        <div class="rep-row-head">
          <span class="rep-name">${escapeHtml(factions[k])}</span>
          <span class="rep-num">${v >= 0 ? "+" : ""}${v}</span>
        </div>
        <div class="rep-track"><span class="rep-fill" style="width:${pct}%"></span></div>
      `;
      frag.appendChild(li);
    }
    ul.appendChild(frag);
  }
}

function repTone(v) {
  if (v >= 25) return "rep-warm";
  if (v >= 8) return "rep-tepid";
  if (v <= -25) return "rep-cold";
  if (v <= -8) return "rep-cool";
  return "rep-flat";
}

export function renderRumors(rumors) {
  const ul = el("rumorList");
  if (!ul) return;
  const slice = (rumors || []).slice(-6).reverse();
  const serial = JSON.stringify(slice);

  if (!deepEqual(_cache.rumors, serial)) {
    _cache.rumors = serial;
    ul.innerHTML = "";
    if (!slice.length) {
      ul.innerHTML = '<li class="rumor-empty">尚无风闻。多与「风闻子」叙话。</li>';
      return;
    }
    const frag = document.createDocumentFragment();
    for (const r of slice) {
      const li = document.createElement("li");
      li.textContent = r;
      frag.appendChild(li);
    }
    ul.appendChild(frag);
  }
}

export function renderEvents(events) {
  const ul = el("eventList");
  if (!ul) return;
  const slice = (events || []).slice(-8).reverse();
  const serial = JSON.stringify(slice);

  if (!deepEqual(_cache.events, serial)) {
    _cache.events = serial;
    ul.innerHTML = "";
    if (!slice.length) {
      ul.innerHTML = '<li class="rumor-empty">江湖暂无大事录入。</li>';
      return;
    }
    const frag = document.createDocumentFragment();
    for (const e of slice) {
      const li = document.createElement("li");
      const stamp = `第${e.day}日·${e.shichen}`;
      const actor = e.actor ? `〖${e.actor}〗` : "";
      li.innerHTML = `<span class="event-stamp">${escapeHtml(stamp)}</span> ${escapeHtml(actor)}<span>${escapeHtml(e.text || "")}</span>`;
      frag.appendChild(li);
    }
    ul.appendChild(frag);
  }
}

export function renderFavor(favorObj, activeNpc) {
  const fe = el("statFavor");
  if (!fe) return;
  const v = (favorObj || {})[activeNpc];
  const fill = el("favorFill");

  if (!deepEqual(_cache.favor, { v, activeNpc })) {
    _cache.favor = { v, activeNpc };
    fe.textContent = v == null ? "—" : String(v);
    if (fill) {
      const pct = v == null ? 50 : Math.max(0, Math.min(100, (Number(v) + 100) / 2));
      fill.style.width = `${pct}%`;
    }
  }
}

export function renderNpcHere(npcsHere, npcLabels) {
  const el2 = el("npcsHereList");
  if (!el2) return;
  const serial = JSON.stringify(npcsHere);

  if (!deepEqual(_cache.npcsHere, serial)) {
    _cache.npcsHere = serial;
    el2.innerHTML = "";
    if (!npcsHere?.length) {
      el2.innerHTML = '<li class="rumor-empty">此处无NPC。</li>';
      return;
    }
    const frag = document.createDocumentFragment();
    for (const n of npcsHere) {
      const li = document.createElement("li");
      const label = npcLabels?.[n.id] || n.name || n.id;
      li.textContent = label;
      frag.appendChild(li);
    }
    el2.appendChild(frag);
  }
}

let _flashTimer = null;
export function flashCoins(coinDelta) {
  const tip = el("statCoinsDelta");
  if (!tip || !coinDelta) return;
  tip.textContent = `${coinDelta > 0 ? "+" : ""}${coinDelta}`;
  tip.classList.remove("delta-up", "delta-down");
  tip.classList.add(coinDelta > 0 ? "delta-up" : "delta-down");
  clearTimeout(_flashTimer);
  _flashTimer = setTimeout(() => {
    tip.textContent = "";
    tip.classList.remove("delta-up", "delta-down");
  }, 2200);
}

document.addEventListener("flash-coins", (e) => flashCoins(e.detail));