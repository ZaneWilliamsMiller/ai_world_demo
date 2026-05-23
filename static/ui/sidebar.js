import { store } from "../store.js";
import { el, escapeHtml } from "./utils.js";

export function renderSidebar(state) {
  renderFlags(state.flags);
  renderClock(state);
  renderInventory(state.player.inventory);
  renderReputation(state.player.reputation, state.factions);
  renderRumors(state.rumors);
  renderEvents(state.events);
  renderFavor(state.favor, state.activeNpc);
  renderVitals(state.player);
}

function renderVitals(player) {
  if (!player) return;
  const vigor = Number(player.vigor ?? 0);
  const vigorMax = Number(player.vigor_max ?? 100);
  const spirit = Number(player.spirit ?? 0);
  const spiritMax = Number(player.spirit_max ?? 100);

  const sv = el("statVigor");
  if (sv) sv.textContent = String(vigor);
  const svm = el("statVigorMax");
  if (svm) svm.textContent = ` / ${vigorMax}`;

  const ss = el("statSpirit");
  if (ss) ss.textContent = String(spirit);
  const ssm = el("statSpiritMax");
  if (ssm) ssm.textContent = ` / ${spiritMax}`;

  const vf = el("vigorFill");
  if (vf) {
    const pct = Math.max(0, Math.min(100, vigorMax > 0 ? (vigor / vigorMax) * 100 : 0));
    vf.style.width = `${pct}%`;
    vf.classList.toggle("resource-low", vigor <= vigorMax * 0.25);
  }
  const sf = el("spiritFill");
  if (sf) {
    const pct = Math.max(0, Math.min(100, spiritMax > 0 ? (spirit / spiritMax) * 100 : 0));
    sf.style.width = `${pct}%`;
    sf.classList.toggle("resource-low", spirit <= spiritMax * 0.25);
  }

  const burnWrap = el("lifeBurnWrap");
  const burnFill = el("lifeBurnFill");
  const burnTicks = Number(player.life_burn_ticks ?? 0);
  const burnMax = Number(player.life_burn_max ?? 0);
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
  el("fOrder").textContent = flags.order;
  el("fTruth").textContent = flags.truth;
  el("fHope").textContent = flags.hope;
  el("fChaos").textContent = flags.chaos;
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
  cp.textContent = `第 ${day} 日 · ${sh} · ${w}`;
  cp.classList.toggle("clock-night", !!state.player.world_is_night);
}

export function renderInventory(inv) {
  const ul = el("invList");
  if (!ul) return;
  ul.innerHTML = "";
  const entries = Object.entries(inv || {}).filter(([, c]) => c > 0);
  if (!entries.length) {
    const li = document.createElement("li");
    li.className = "rumor-empty";
    li.textContent = "身无长物。";
    ul.appendChild(li);
    return;
  }
  entries.sort((a, b) => a[0].localeCompare(b[0], "zh"));
  
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

export function renderReputation(rep, factions) {
  const ul = el("repList");
  if (!ul) return;
  ul.innerHTML = "";
  const order = ["yamen", "biaoju", "caobang", "shuyuan", "lulin"];
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
  ul.innerHTML = "";
  const slice = (rumors || []).slice(-6);
  if (!slice.length) {
    const li = document.createElement("li");
    li.className = "rumor-empty";
    li.textContent = "尚无风闻。多与「风闻子」叙话，坊间才有记性。";
    ul.appendChild(li);
    return;
  }
  const frag = document.createDocumentFragment();
  for (const r of slice.slice().reverse()) {
    const li = document.createElement("li");
    li.textContent = r;
    frag.appendChild(li);
  }
  ul.appendChild(frag);
}

export function renderEvents(events) {
  const ul = el("eventList");
  if (!ul) return;
  ul.innerHTML = "";
  const slice = (events || []).slice(-8);
  if (!slice.length) {
    const li = document.createElement("li");
    li.className = "rumor-empty";
    li.textContent = "江湖暂无大事录入。";
    ul.appendChild(li);
    return;
  }
  const frag = document.createDocumentFragment();
  for (const e of slice.slice().reverse()) {
    const li = document.createElement("li");
    const stamp = `第${e.day}日·${e.shichen}`;
    const actor = e.actor ? `〖${e.actor}〗` : "";
    li.innerHTML = `<span class="event-stamp">${escapeHtml(stamp)}</span> ${escapeHtml(actor)}<span>${escapeHtml(e.text || "")}</span>`;
    frag.appendChild(li);
  }
  ul.appendChild(frag);
}

export function renderFavor(favorObj, activeNpc) {
  const fe = el("statFavor");
  if (!fe) return;
  const v = (favorObj || {})[activeNpc];
  fe.textContent = v == null ? "—" : String(v);
  const fill = el("favorFill");
  if (fill) {
    const pct = v == null ? 50 : Math.max(0, Math.min(100, (Number(v) + 100) / 2));
    fill.style.width = `${pct}%`;
  }
}

let flashTimer;
export function flashCoins(coinDelta) {
  const tip = el("statCoinsDelta");
  if (!tip || !coinDelta) return;
  tip.textContent = `${coinDelta > 0 ? "+" : ""}${coinDelta}`;
  tip.classList.remove("delta-up", "delta-down");
  tip.classList.add(coinDelta > 0 ? "delta-up" : "delta-down");
  clearTimeout(flashTimer);
  flashTimer = setTimeout(() => {
    tip.textContent = "";
    tip.classList.remove("delta-up", "delta-down");
  }, 2200);
}

document.addEventListener("flash-coins", (e) => flashCoins(e.detail));
