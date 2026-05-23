import { store } from "../store.js";
import { el, escapeHtml } from "./utils.js";
import { talkToNpcNormal } from "../api.js";

const WORLD_ACTIONS = {
  explore: "[动作：探路] 你袖手低腰，沿墙根与车辙试探前路，耳听风声、狗吠与远处梆子。",
  observe: "[动作：察局] 你驻足冷眼，辨招牌、辨脚步、辨衙役与闲汉的眼色，估量这一局水有多深。",
  stealth: "[动作：潜踪] 你借檐影与货担掩身，收声敛气，不欲惊动暗桩。",
  rest: "[动作：歇脚] 你寻背风处盘膝调息，裹紧衣裳，把一口气匀回来。",
  loot: "[动作：摸货] 你在货堆、破箱、死倒旁小心翻检，看有无可用之物。",
  leave: "[动作：抽身] 你借人群一错，欲离是非之地，换条巷子说话。",
  sprint: "[动作：疾行] 你提一口气快步穿行，赌巡卒与歹人慢你半步。",
};

const ACTION_LABEL = {
  explore: "探路", observe: "察局", stealth: "潜踪", rest: "歇脚", loot: "摸货", leave: "抽身", sprint: "疾行",
  probe: "试探", deal: "议价", bribe: "行贿", pressure: "施压", help: "卖好", refuse: "推却", goodbye: "作别", woo: "献殷勤",
};

// 极简模板：一行意图 + 一行筹码/底线 + 一行台词位
const SOCIAL_TEMPLATE_BODY = {
  probe:   "意图：摸底，不摊牌。\n筹码：抛半真半假之语。\n台词：",
  deal:    "意图：谈一笔互利。\n筹码：银钱/消息/人情，任选其一。\n台词：",
  bribe:   "意图：以小钱换通融。\n出价：茶水钱若干，事成另谢。\n台词：",
  pressure:"意图：用时限或后果逼让步。\n台阶：现给交代，我留体面。\n台词：",
  help:    "意图：先施善意，再换信任。\n卖好：跑腿/垫付/传话皆可。\n台词：",
  refuse:  "意图：婉拒不翻脸。\n补偿：给替代或延后方案。\n台词：",
  goodbye: "意图：体面抽身。\n留尾：何时何地可再谈。\n台词：",
  woo:     "意图：拉近不强求。\n示好：以言语/小礼/举动表诚。\n台词：",
};

function buildSocialTemplate(action, npcName) {
  const title = ACTION_LABEL[action] || action;
  const body = SOCIAL_TEMPLATE_BODY[action] || "意图：\n筹码：\n台词：";
  return `「${title} → ${npcName}」\n${body}`;
}

export function initDialogue(onTalkEnd) {
  el("talkForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const raw = el("msg").value.trim();
    if (!raw) return;
    el("msg").value = "";
    appendLog("你", raw);
    await doTalk(raw, store.getState().activeNpc, onTalkEnd);
  });

  el("actionBar").addEventListener("click", async (ev) => {
    const btn = ev.target.closest(".action-chip");
    const state = store.getState();
    if (!btn || btn.disabled || state.ended || !state.playerId || state.player.dead) return;
    const kind = btn.getAttribute("data-kind");
    const act = btn.getAttribute("data-act");
    if (!kind || !act) return;

    if (kind === "world") {
      if (state.player.move_locked) return;
      const inner = WORLD_ACTIONS[act];
      if (!inner) return;
      appendLog("你（快捷·纪事）", `${ACTION_LABEL[act] || act}\n${inner}`);
      await doTalk(inner, "jiang", onTalkEnd);
    } else {
      const npcName = store.getState().npcLabels[state.activeNpc] || state.activeNpc;
      const msgEl = el("msg");
      if (!msgEl) return;
      msgEl.value = buildSocialTemplate(act, npcName);
      msgEl.focus();
      msgEl.setSelectionRange(msgEl.value.length, msgEl.value.length);
      appendLog("你（快捷·人情）", `已载入模板：${ACTION_LABEL[act] || act} → ${npcName}（可改写后发送）`, "bubble-meta");
    }
  });

  el("msg").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      el("talkForm").requestSubmit();
    }
  });
}

export function appendLog(who, text, extraClass = "") {
  const log = el("log");
  const wrap = document.createElement("div");
  wrap.className = "bubble" + (extraClass ? ` ${extraClass}` : "");
  wrap.innerHTML = `<div class="who">${escapeHtml(who)}</div><div class="txt"></div>`;
  wrap.querySelector(".txt").textContent = text;
  log.appendChild(wrap);
  
  // 限制日志长度，防止 DOM 膨胀
  while (log.children.length > 50) {
    log.removeChild(log.firstChild);
  }
  log.scrollTop = log.scrollHeight;
}

export function appendStreamingBubble(who) {
  const log = el("log");
  const wrap = document.createElement("div");
  wrap.className = "bubble bubble-streaming";
  wrap.innerHTML = `<div class="who">${escapeHtml(who)}</div><div class="txt"></div>`;
  const txtEl = wrap.querySelector(".txt");
  log.appendChild(wrap);
  while (log.children.length > 50) log.removeChild(log.firstChild);
  log.scrollTop = log.scrollHeight;
  return { wrap, txtEl };
}

export function appendDeltaLine(delta) {
  if (!delta) return;
  const bits = [];
  if (delta.coins) bits.push(`制钱 ${delta.coins > 0 ? "+" : ""}${delta.coins}`);
  if (Array.isArray(delta.items_gain) && delta.items_gain.length) bits.push(`得：${delta.items_gain.join("、")}`);
  if (Array.isArray(delta.items_lose) && delta.items_lose.length) bits.push(`失：${delta.items_lose.join("、")}`);
  if (delta.rep && Object.keys(delta.rep).length) {
    const repBits = [];
    const factions = store.getState().factions;
    for (const [k, v] of Object.entries(delta.rep)) {
      if (!v) continue;
      const name = factions[k] || k;
      repBits.push(`${name}${v > 0 ? "+" : ""}${v}`);
    }
    if (repBits.length) bits.push(`声望：${repBits.join(" ")}`);
  }
  if (Array.isArray(delta.events) && delta.events.length) bits.push(`事：${delta.events.join("； ")}`);
  if (!bits.length) return;
  
  const log = el("log");
  const div = document.createElement("div");
  div.className = "bubble bubble-meta";
  div.innerHTML = `<div class="who">江湖回执</div><div class="txt"></div>`;
  div.querySelector(".txt").textContent = bits.join(" · ");
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

export function setInteractionBusy(on) {
  const state = store.getState();
  const lock = !!on;
  const base = state.ended || state.player.dead;
  el("msg").disabled = lock || base;
  el("btnSend").disabled = lock || base;
  el("btnSend").classList.toggle("is-loading", lock);
  
  for (const b of document.querySelectorAll("#actionBar .action-chip")) {
    if (lock || base) {
      b.disabled = true;
    } else {
      const kind = b.getAttribute("data-kind");
      b.disabled = (kind === "world" && state.player.move_locked);
    }
  }
}

export async function doTalk(inner, npcId, onTalkEnd) {
  const state = store.getState();
  if (!state.playerId || state.ended || state.player.dead) return;
  
  const useStream = el("useNpcStream")?.checked;
  setInteractionBusy(true);
  try {
    if (useStream) {
      await talkStream(inner, npcId);
    } else {
      const data = await talkToNpcNormal(npcId, inner);
      if (data) {
        const npcName = store.getState().npcLabels[npcId] || npcId;
        appendLog(npcName, data.reply);
        applyTalkResult(data);
      }
    }
  } finally {
    setInteractionBusy(false);
    if (onTalkEnd) onTalkEnd();
  }
}

async function talkStream(inner, npcId) {
  const state = store.getState();
  const npcName = state.npcLabels[npcId] || npcId;
  let wrap = null;
  let txtEl = null;

  try {
    const r = await fetch(`/api/npc/talk_stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_id: state.playerId, npc_id: npcId, message: inner }),
    });

    if (!r.ok) {
      const errText = await r.text().catch(() => "");
      throw new Error(errText || `流式接口异常 ${r.status}`);
    }

    ({ wrap, txtEl } = appendStreamingBubble(npcName));
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let carry = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      carry += dec.decode(value, { stream: true });
      const blocks = carry.split("\n\n");
      carry = blocks.pop() ?? "";
      for (const block of blocks) {
        const lines = block.split("\n");
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const j = JSON.parse(line.slice(6));
            if (j.chunk) {
              txtEl.textContent += j.chunk;
              el("log").scrollTop = el("log").scrollHeight;
            }
            if (j.fatal) {
              wrap.classList.remove("bubble-streaming");
              if (j.error) {
                txtEl.textContent = (txtEl.textContent || "") + `\n[错误] ${j.error}`;
              }
              return;
            }
            if (j.done) {
              wrap.classList.remove("bubble-streaming");
              if (typeof j.reply === "string") txtEl.textContent = j.reply;
              applyTalkResult(j);
              return;
            }
          } catch (_e) {
            // ignore JSON parse error for partial chunks
          }
        }
      }
    }
    if (wrap) wrap.classList.remove("bubble-streaming");
  } catch (e) {
    console.error(e);
    if (!wrap) ({ wrap, txtEl } = appendStreamingBubble(npcName));
    wrap.classList.remove("bubble-streaming");
    txtEl.textContent = (txtEl.textContent || "") + `\n[错误] ${e?.message || e}`;
  }
}

function applyTalkResult(data) {
  store.setState({
    flags: data.flags || store.getState().flags,
    favor: { ...store.getState().favor, ...data.favor },
    rumors: data.rumors || store.getState().rumors,
    events: data.events || store.getState().events,
  });
  store.updatePlayer(data.player);
  
  if (data.npcs_here) {
    // Let main.js handle tabs rebuild via subscription or callback
    // For now, just update store
    store.setState({ npcsHere: data.npcs_here });
  }
  
  if (data.delta) {
    appendDeltaLine(data.delta);
    if (data.delta.coins) {
      document.dispatchEvent(new CustomEvent("flash-coins", { detail: data.delta.coins }));
    }
    if (data.delta.vigor || data.delta.spirit) {
      const bits = [];
      if (data.delta.vigor) bits.push(`体力 ${data.delta.vigor > 0 ? "+" : ""}${data.delta.vigor}`);
      if (data.delta.spirit) bits.push(`心气 ${data.delta.spirit > 0 ? "+" : ""}${data.delta.spirit}`);
      appendLog("身心起伏", bits.join(" · "), "bubble-meta");
    }
  }

  const tr = data.trap_resolution;
  if (tr?.outcome === "escaped") {
    appendLog("系统", "你已脱困，可再行旅。", "bubble-meta");
  } else if (tr?.outcome === "struggling") {
    appendLog("系统", `险局未解：${tr.reason || "仍需周旋。"}`, "bubble-meta");
  } else if (tr?.outcome === "enslaved") {
    appendLog("系统", `你已被擒作苦役：${tr.reason || ""}`, "bubble-meta");
  } else if (tr?.outcome === "dead") {
    appendLog("系统", `你在险局中殒命：${tr.reason || ""}`, "bubble-meta");
  }
}
