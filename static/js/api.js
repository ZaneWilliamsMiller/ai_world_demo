// ═══════════════════════════════════════════════════════
//  api.js — 后端 API 调用封装（支持后端/独立双模式）
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  // ── 后端模式 API ──

  var _defaultTimeout = 30000;

  function backendPost(url, body, timeoutMs) {
    var path = url.startsWith("/api") ? url.substring(4) : url;
    var fullUrl = App.API + path;
    var controller = new AbortController();
    var timeoutId = setTimeout(function() { controller.abort(); }, timeoutMs || _defaultTimeout);
    return fetch(fullUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal
    }).then(async function(r) {
      clearTimeout(timeoutId);
      if (!r.ok) {
        let errorMsg = url + " " + r.status;
        try {
          const errorJson = await r.json();
          errorMsg = errorJson.detail || errorJson.message || errorMsg;
        } catch (e) {
        }
        throw new Error(errorMsg);
      }
      return r.json();
    }).catch(function(e) {
      clearTimeout(timeoutId);
      if (e.name === 'AbortError') throw new Error('请求超时');
      throw e;
    });
  }

  function backendGet(url, timeoutMs) {
    var path = url.startsWith("/api") ? url.substring(4) : url;
    var fullUrl = App.API + path;
    var controller = new AbortController();
    var timeoutId = setTimeout(function() { controller.abort(); }, timeoutMs || _defaultTimeout);
    return fetch(fullUrl, { cache: 'no-store', signal: controller.signal }).then(async function(r) {
      clearTimeout(timeoutId);
      if (!r.ok) {
        let errorMsg = url + " " + r.status;
        try {
          const errorJson = await r.json();
          errorMsg = errorJson.detail || errorJson.message || errorMsg;
        } catch (e) {
        }
        throw new Error(errorMsg);
      }
      return r.json();
    }).catch(function(e) {
      clearTimeout(timeoutId);
      if (e.name === 'AbortError') throw new Error('请求超时');
      throw e;
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
    if (App.apiMode !== "backend") return [];
    return (await backendGet("/api/saves")).saves || [];
  };

  // ═══════════════════════════════════════════
  //  游戏操作
  // ═══════════════════════════════════════════

  App.doMove = async function(tx, ty) {
    if (App._isMoving) return null;
    App._isMoving = true;
    App.setLoading(true, "行走中...");
    try {
      return await backendPost("/api/move", {
        player_id: App.playerId,
        to_x: tx,
        to_y: ty
      });
    } finally {
      App._isMoving = false;
      App.setLoading(false);
    }
  };

  App.fetchState = async function() {
    if (!App.playerId || App.apiMode !== "backend") return null;
    return await backendGet("/api/state/" + App.playerId);
  };

  App.doSave = async function() {
    if (App.apiMode !== "backend") return { ok: true };
    return await backendPost("/api/save", { player_id: App.playerId });
  };

  App.doRest = async function() {
    if (App.apiMode !== "backend") return null;
    return await backendPost("/api/rest", { player_id: App.playerId });
  };

  App.useItem = async function(itemName) {
    if (App.apiMode !== "backend") return null;
    return await backendPost("/api/item/use", { player_id: App.playerId, item: itemName });
  };

  App.doFinale = async function() {
    if (App.apiMode !== "backend") return null;
    return await backendPost("/api/finale", { player_id: App.playerId });
  };

  App.bountyRefresh = async function() {
    if (App.apiMode !== "backend") return null;
    return await backendPost("/api/bounty/refresh", { player_id: App.playerId });
  };

  App.bountyAccept = async function(bountyId) {
    if (App.apiMode !== "backend") return null;
    return await backendPost("/api/bounty/accept", { player_id: App.playerId, bounty_id: bountyId });
  };

  App.bountyCheck = async function() {
    if (App.apiMode !== "backend") return null;
    return await backendPost("/api/bounty/check", { player_id: App.playerId });
  };

  App.bountyComplete = async function() {
    if (App.apiMode !== "backend") return null;
    return await backendPost("/api/bounty/complete", { player_id: App.playerId });
  };

  App.bountyAbandon = async function() {
    if (App.apiMode !== "backend") return null;
    return await backendPost("/api/bounty/abandon", { player_id: App.playerId });
  };

  // ═══════════════════════════════════════════
  //  NPC 对话
  // ═══════════════════════════════════════════

  App.talkStream = async function(npcId, message) {
    var requestBody = {
      player_id: App.playerId,
      npc_id: npcId,
      message: message
    };

    var controller = new AbortController();
    App._streamAbortController = controller;
    var connectTimeout = setTimeout(function() { controller.abort(); }, 15000);

    var res;
    try {
      res = await fetch(App.API + "/npc/talk_stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
        signal: controller.signal
      });
      clearTimeout(connectTimeout);
    } catch (e) {
      clearTimeout(connectTimeout);
      App._streamAbortController = null;
      if (e.name === 'AbortError') throw new Error('连接超时');
      throw e;
    }
    if (!res.ok) {
      App._streamAbortController = null;
      let errorMsg = "talk_stream " + res.status;
      try {
        const errorJson = await res.json();
        errorMsg = errorJson.detail || errorJson.message || errorMsg;
      } catch (e) {
      }
      throw new Error(errorMsg);
    }
    return res.body.getReader();
  };

  App.cancelTalkStream = function() {
    if (App._streamAbortController) {
      App._streamAbortController.abort();
      App._streamAbortController = null;
    }
  };

  // ═══════════════════════════════════════════
  //  连接测试
  // ═══════════════════════════════════════════

  App.testBackend = async function() {
    try {
      const data = await backendGet("/api/health");
      var model = data.model || "(unknown)";
      var world = data.world || "(unknown)";
      return { ok: true, detail: "model=" + model + " world=" + world };
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

})(window.App);
