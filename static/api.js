import { store, LS_KEY } from "./store.js";
import { showToast } from "./ui/utils.js";

const API_BASE = "";

async function fetchApi(endpoint, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
    });
    if (!res.ok) {
      const text = await res.text();
      const err = new Error(text || `HTTP error ${res.status}`);
      err.status = res.status;
      if (Array.isArray(options.silentStatuses) && options.silentStatuses.includes(res.status)) {
        err.__silent = true;
      }
      throw err;
    }
    return await res.json();
  } catch (err) {
    if (!err.__silent) {
      showToast(err.message, "error");
    }
    throw err;
  }
}

export async function pingModel() {
  try {
    return await fetchApi("/api/health");
  } catch {
    return null;
  }
}

export async function startGame(displayName, gender, permadeath) {
  const { playerId } = store.getState();
  const data = await fetchApi("/api/hello", {
    method: "POST",
    body: JSON.stringify({
      player_id: playerId,
      display_name: displayName || null,
      gender,
      permadeath,
    }),
  });
  localStorage.setItem(LS_KEY, data.player_id);
  return data;
}

export async function movePlayer(tx, ty) {
  const { playerId } = store.getState();
  return await fetchApi("/api/move", {
    method: "POST",
    body: JSON.stringify({ player_id: playerId, to_x: tx, to_y: ty }),
  });
}

export async function fetchState() {
  const { playerId } = store.getState();
  if (!playerId) return null;
  try {
    return await fetchApi(`/api/state/${encodeURIComponent(playerId)}`, {
      silentStatuses: [404],
    });
  } catch (err) {
    if (err.status === 404) {
      // 本地缓存的 player_id 在服务端不存在：清理失效存档，避免持续 404
      localStorage.removeItem(LS_KEY);
      store.setState({ playerId: null });
      return null;
    }
    throw err;
  }
}

export async function fetchJournal() {
  const { playerId } = store.getState();
  return await fetchApi(`/api/journal/${encodeURIComponent(playerId)}`);
}

export async function fetchAgentMind(npcId) {
  const { playerId } = store.getState();
  return await fetchApi(`/api/agent/${encodeURIComponent(playerId)}/${encodeURIComponent(npcId)}/mind`);
}

export async function triggerAgentReflect(npcId) {
  const { playerId } = store.getState();
  return await fetchApi("/api/agent/reflect", {
    method: "POST",
    body: JSON.stringify({ player_id: playerId, npc_id: npcId }),
  });
}

export async function triggerAgentPlan(npcId) {
  const { playerId } = store.getState();
  return await fetchApi("/api/agent/plan", {
    method: "POST",
    body: JSON.stringify({ player_id: playerId, npc_id: npcId }),
  });
}

export async function submitFinale(closingNote) {
  const { playerId } = store.getState();
  return await fetchApi("/api/finale", {
    method: "POST",
    body: JSON.stringify({ player_id: playerId, closing_note: closingNote }),
  });
}

export async function talkToNpcNormal(npcId, message) {
  const { playerId } = store.getState();
  return await fetchApi("/api/npc/talk", {
    method: "POST",
    body: JSON.stringify({ player_id: playerId, npc_id: npcId, message }),
  });
}

export async function inquireTile(tx, ty) {
  const { playerId } = store.getState();
  return await fetchApi("/api/npc/talk", {
    method: "POST",
    body: JSON.stringify({
      player_id: playerId,
      npc_id: "jiang",
      message: `[系统指令·问路·轻量] 玩家询问地图坐标(${tx},${ty})处的传闻。请以「风闻子」(第三方旁观口吻)简述此地有何江湖掌故/地势险要/近日怪事。若无则直言"暂无传闻"。中文2-5句，不编造不存在的人物。`,
    }),
  });
}
