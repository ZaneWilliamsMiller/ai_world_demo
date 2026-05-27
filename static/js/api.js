// ═══════════════════════════════════════════════════════
//  api.js — 后端 API 调用封装（支持后端/独立双模式）
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  // ── 后端模式 API ──

  function backendPost(url, body) {
    const path = url.startsWith("/api") ? url.substring(4) : url;
    const fullUrl = App.API + path;
    return fetch(fullUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(async function(r) {
      if (!r.ok) {
        let errorMsg = url + " " + r.status;
        try {
          const errorJson = await r.json();
          errorMsg = errorJson.detail || errorJson.message || errorMsg;
        } catch (e) {
          // JSON 解析失败，保留默认错误信息
        }
        throw new Error(errorMsg);
      }
      return r.json();
    });
  }

  function backendGet(url) {
    const path = url.startsWith("/api") ? url.substring(4) : url;
    const fullUrl = App.API + path;
    return fetch(fullUrl, { cache: 'no-store' }).then(async function(r) {
      if (!r.ok) {
        let errorMsg = url + " " + r.status;
        try {
          const errorJson = await r.json();
          errorMsg = errorJson.detail || errorJson.message || errorMsg;
        } catch (e) {
          // JSON 解析失败，保留默认错误信息
        }
        throw new Error(errorMsg);
      }
      return r.json();
    });
  }

  // ── LLM 直连 API（独立模式）──

  function llmChat(messages, options) {
    options = options || {};
    return fetch(App.LLM_API_URL + "/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + App.LLM_API_KEY
      },
      body: JSON.stringify({
        model: App.LLM_MODEL,
        messages: messages,
        temperature: options.temperature || 0.7,
        max_tokens: options.maxTokens || 1024,
        stream: options.stream || false
      })
    }).then(function(r) {
      if (!r.ok) throw new Error("LLM API " + r.status + ": " + r.statusText);
      return r.json();
    });
  }

  // ═══════════════════════════════════════════
  //  角色初始化 / 恢复
  // ═══════════════════════════════════════════

  App.createPlayer = async function(name, gender, permadeath) {
    if (App.apiMode === "backend") {
      const pid = "web_" + Date.now();
      const data = await backendPost("/api/hello", {
        player_id: pid,
        display_name: name,
        gender: gender,
        permadeath: permadeath
      });
      return { data: data, pid: pid };
    } else {
      const pid = "standalone_" + Date.now();
      return {
        data: { player_id: pid, display_name: name, intro: "独立模式 — 仅 LLM 对话" },
        pid: pid
      };
    }
  };

  App.loadPlayer = async function(playerId) {
    return await backendPost("/api/load", { player_id: playerId });
  };

  App.fetchSaves = async function() {
    if (App.apiMode !== "backend") return { saves: [] };
    return (await backendGet("/api/saves")).saves || [];
  };

  // ═══════════════════════════════════════════
  //  游戏操作
  // ═══════════════════════════════════════════

  App.doMove = async function(tx, ty) {
    return await backendPost("/api/move", {
      player_id: App.playerId,
      to_x: tx,
      to_y: ty
    });
  };

  App.fetchState = async function() {
    if (!App.playerId || App.apiMode !== "backend") return null;
    return await backendGet("/api/state/" + App.playerId);
  };

  App.doSave = async function() {
    if (App.apiMode !== "backend") return { ok: true };
    return await backendPost("/api/save", { player_id: App.playerId });
  };

  // ═══════════════════════════════════════════
  //  NPC 对话
  // ═══════════════════════════════════════════

  App.talkStream = async function(npcId, message) {
    const requestBody = {
      player_id: App.playerId,
      npc_id: npcId,
      message: message
    };

    if (App.apiMode !== "backend") {
      requestBody.llm_base_url = App.LLM_API_URL;
      requestBody.llm_api_key = App.LLM_API_KEY;
      requestBody.llm_model = App.LLM_MODEL;
    }

    const res = await fetch(App.API + "/npc/talk_stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody)
    });
    if (!res.ok) {
      let errorMsg = "talk_stream " + res.status;
      try {
        const errorJson = await res.json();
        errorMsg = errorJson.detail || errorJson.message || errorMsg;
      } catch (e) {
        // JSON 解析失败，保留默认错误信息
      }
      throw new Error(errorMsg);
    }
    return res.body.getReader();
  };

  // ═══════════════════════════════════════════
  //  连接测试
  // ═══════════════════════════════════════════

  App.testBackend = async function() {
    try {
      const data = await backendGet("/health");
      return { ok: true, detail: "model=" + data.model + " world=" + data.world };
    } catch (e) {
      return { ok: false, detail: e.message };
    }
  };

  App.testLLM = async function() {
    try {
      const data = await llmChat([{ role: "user", content: "你好" }], { maxTokens: 20 });
      const content = data.choices[0].message.content;
      return { ok: true, detail: "reply_len=" + content.length };
    } catch (e) {
      return { ok: false, detail: e.message };
    }
  };

  App.testModels = async function() {
    try {
      const res = await fetch(App.LLM_API_URL + "/models", {
        headers: { "Authorization": "Bearer " + App.LLM_API_KEY }
      });
      const data = await res.json();
      const ids = data.data.map(function(m) { return m.id; });
      return { ok: ids.includes(App.LLM_MODEL), detail: "models=" + ids.length + " target=" + App.LLM_MODEL };
    } catch (e) {
      return { ok: false, detail: e.message };
    }
  };

})(window.App);
