import { store } from "../store.js";
import { el, escapeHtml } from "./utils.js";
import { fetchJournal, fetchAgentMind, triggerAgentReflect, triggerAgentPlan } from "../api.js";

let journalActiveTab = "events";
let journalCache = null;

export function initJournal() {
  el("btnJournal")?.addEventListener("click", openJournal);
  document.querySelectorAll("#journalDrawer [data-close]").forEach((n) =>
    n.addEventListener("click", closeJournal),
  );
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && !el("journalDrawer").classList.contains("is-hidden")) {
      closeJournal();
    }
  });
}

export async function openJournal() {
  const { playerId } = store.getState();
  if (!playerId) return;
  const drawer = el("journalDrawer");
  drawer.classList.remove("is-hidden");
  await loadJournal();
}

export function closeJournal() {
  el("journalDrawer").classList.add("is-hidden");
}

async function loadJournal() {
  const body = el("journalBody");
  body.innerHTML = `<p class="muted">翻阅中…</p>`;
  try {
    journalCache = await fetchJournal();
  } catch (e) {
    body.innerHTML = `<p class="muted">网络异常或读取失败。</p>`;
    return;
  }
  buildJournalTabs();
  renderJournalBody();
}

function buildJournalTabs() {
  const tabs = el("journalTabs");
  tabs.innerHTML = "";
  const items = [
    { id: "events", label: "世事流" },
    { id: "rumors", label: "风闻" },
    { id: "minds", label: "心迹（NPC 内心）" },
  ];
  for (const h of journalCache?.history || []) {
    items.push({ id: `npc:${h.npc_id}`, label: h.npc_name });
  }
  const frag = document.createDocumentFragment();
  for (const it of items) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = it.label;
    b.dataset.tab = it.id;
    if (it.id === journalActiveTab) b.classList.add("active");
    b.addEventListener("click", () => {
      journalActiveTab = it.id;
      [...tabs.children].forEach((c) => c.classList.toggle("active", c.dataset.tab === it.id));
      renderJournalBody();
    });
    frag.appendChild(b);
  }
  tabs.appendChild(frag);
}

function renderJournalBody() {
  const body = el("journalBody");
  if (!journalCache) {
    body.innerHTML = `<p class="muted">无数据。</p>`;
    return;
  }
  if (journalActiveTab === "minds") {
    renderMindsTab();
    return;
  }
  if (journalActiveTab === "events") {
    const evs = journalCache.events || [];
    if (!evs.length) {
      body.innerHTML = `<p class="muted">江湖暂无大事。</p>`;
      return;
    }
    body.innerHTML = evs
      .slice()
      .reverse()
      .map((e) => {
        const stamp = `第${e.day}日·${e.shichen}`;
        const actor = e.actor ? `〖${e.actor}〗` : "";
        return `<div class="journal-line"><span class="event-stamp">${escapeHtml(
          stamp,
        )}</span> ${escapeHtml(actor)} <span>${escapeHtml(e.text || "")}</span></div>`;
      })
      .join("");
    return;
  }
  if (journalActiveTab === "rumors") {
    const rs = journalCache.rumors || [];
    if (!rs.length) {
      body.innerHTML = `<p class="muted">尚无风闻。</p>`;
      return;
    }
    body.innerHTML = rs
      .slice()
      .reverse()
      .map((r) => `<div class="journal-line">· ${escapeHtml(r)}</div>`)
      .join("");
    return;
  }
  if (journalActiveTab.startsWith("npc:")) {
    const id = journalActiveTab.slice(4);
    const node = (journalCache.history || []).find((h) => h.npc_id === id);
    if (!node) {
      body.innerHTML = `<p class="muted">未与此人交谈过。</p>`;
      return;
    }
    body.innerHTML = (node.turns || [])
      .map((t) => {
        const stamp = t.day && t.shichen ? `〔第${t.day}日·${t.shichen}〕` : "";
        return `
          <div class="journal-turn">
            <div class="journal-stamp">${escapeHtml(stamp)} ${escapeHtml(t.weather || "")}</div>
            <div class="journal-u"><span class="who">你</span><span class="txt"></span></div>
            <div class="journal-a"><span class="who">${escapeHtml(node.npc_name)}</span><span class="txt"></span></div>
          </div>
        `;
      })
      .join("");
    // textContent 注入避免 XSS
    const wraps = body.querySelectorAll(".journal-turn");
    (node.turns || []).forEach((t, i) => {
      const w = wraps[i];
      if (!w) return;
      w.querySelector(".journal-u .txt").textContent = t.user || "";
      w.querySelector(".journal-a .txt").textContent = t.assistant || "";
    });
  }
}

function renderMindsTab() {
  const body = el("journalBody");
  const { npcCatalog, activeNpc } = store.getState();
  const npcs = (journalCache?.history || []).map((h) => ({ id: h.npc_id, name: h.npc_name }));
  
  const seen = new Set(npcs.map((n) => n.id));
  for (const n of npcCatalog || []) {
    if (!seen.has(n.id)) npcs.push({ id: n.id, name: n.name });
  }
  body.innerHTML = `
    <div class="mind-pickrow">
      <label class="muted">看谁的内心：</label>
      <select id="mindNpcSel">
        ${npcs.map((n) => `<option value="${escapeHtml(n.id)}">${escapeHtml(n.name)}</option>`).join("")}
      </select>
      <button type="button" class="btn ghost" id="btnMindReflect">让其反思</button>
      <button type="button" class="btn ghost" id="btnMindPlan">让其规划当日</button>
    </div>
    <div id="mindBox" class="mind-box"><p class="muted">选一位 NPC，载入其心迹。</p></div>
  `;
  const sel = el("mindNpcSel");
  if (sel) {
    sel.addEventListener("change", () => loadMindFor(sel.value));
    if (sel.options.length) {
      const initial = activeNpc && [...sel.options].some((o) => o.value === activeNpc) ? activeNpc : sel.options[0].value;
      sel.value = initial;
      loadMindFor(initial);
    }
  }
  el("btnMindReflect")?.addEventListener("click", async () => {
    const id = el("mindNpcSel")?.value;
    if (!id) return;
    el("mindBox").innerHTML = `<p class="muted">让其翻自己的心思……（一次 LLM 调用）</p>`;
    try {
      await triggerAgentReflect(id);
    } catch {
      /* ignore */
    }
    await loadMindFor(id);
  });
  el("btnMindPlan")?.addEventListener("click", async () => {
    const id = el("mindNpcSel")?.value;
    if (!id) return;
    el("mindBox").innerHTML = `<p class="muted">让其安排今日……（一次 LLM 调用）</p>`;
    try {
      await triggerAgentPlan(id);
    } catch {
      /* ignore */
    }
    await loadMindFor(id);
  });
}

async function loadMindFor(npcId) {
  const box = el("mindBox");
  if (!box) return;
  box.innerHTML = `<p class="muted">载入心迹……</p>`;
  try {
    const d = await fetchAgentMind(npcId);
    const items = d.items || [];
    const groups = { seed: [], reflection: [], observation: [], plan: [] };
    for (const m of items) {
      const k = groups[m.kind] ? m.kind : "observation";
      groups[k].push(m);
    }
    const planLines = Object.entries(d.plan_by_shichen || {})
      .map(([sh, txt]) => `<li><b>${escapeHtml(sh)}</b>：${escapeHtml(txt)}</li>`)
      .join("");
    const planBlock = (d.plan_summary || planLines)
      ? `<div class="mind-section">
            <h4>当日计议${d.plan_day != null ? `（第 ${d.plan_day} 日）` : ""}</h4>
            ${d.plan_summary ? `<p class="mind-plan-summary">${escapeHtml(d.plan_summary)}</p>` : ""}
            ${planLines ? `<ul class="mind-plan-list">${planLines}</ul>` : ""}
          </div>`
      : `<div class="mind-section"><h4>当日计议</h4><p class="muted">尚未规划。</p></div>`;
    const seedBlock = `<div class="mind-section">
        <h4>本心（角色种子记忆）</h4>
        ${groups.seed.length
          ? `<ul class="mind-list">${groups.seed.map((m) => `<li>· ${escapeHtml(m.text)}</li>`).join("")}</ul>`
          : `<p class="muted">无</p>`}
      </div>`;
    const reflBlock = `<div class="mind-section">
        <h4>反思 / 心得</h4>
        ${groups.reflection.length
          ? `<ul class="mind-list">${groups.reflection
              .slice()
              .reverse()
              .map((m) => `<li><span class="mind-stamp">第${m.created_day}日·${escapeHtml(m.created_shichen)}</span> ${escapeHtml(m.text)}</li>`)
              .join("")}</ul>`
          : `<p class="muted">尚未反思。可点击右上「让其反思」。</p>`}
      </div>`;
    const obsBlock = `<div class="mind-section">
        <h4>观察 / 见闻（最近 ${Math.min(20, groups.observation.length)} 条）</h4>
        ${groups.observation.length
          ? `<ul class="mind-list">${groups.observation
              .slice(-20)
              .reverse()
              .map((m) => `<li><span class="mind-stamp">第${m.created_day}日·${escapeHtml(m.created_shichen)} · 重要 ${m.importance.toFixed(0)}</span> ${escapeHtml(m.text)}</li>`)
              .join("")}</ul>`
          : `<p class="muted">尚无观察。多与其交谈即可累积。</p>`}
      </div>`;
    const headBits = [];
    if (typeof d.importance_since_reflect === "number") {
      headBits.push(`未反思累计重要 ${d.importance_since_reflect.toFixed(1)} / 35`);
    }
    box.innerHTML = `
      ${headBits.length ? `<p class="muted mind-meta">${headBits.join(" · ")}</p>` : ""}
      ${planBlock}
      ${seedBlock}
      ${reflBlock}
      ${obsBlock}
    `;
  } catch {
    box.innerHTML = `<p class="muted">网络异常。</p>`;
  }
}
