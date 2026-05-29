window.App = window.App || {};

(function(App) {
  "use strict";

  var _defaultTimeout = 30000;

  async function backendPost(url, body, timeoutMs) {
    var path = url.startsWith("/api") ? url.substring(4) : url;
    var fullUrl = App.API + path;
    var controller = new AbortController();
    var timeoutId = setTimeout(function() { controller.abort(); }, timeoutMs || _defaultTimeout);
    try {
      var r = await fetch(fullUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      if (!r.ok) {
        var errorMsg = url + " " + r.status;
        try {
          var errorJson = await r.json();
          errorMsg = errorJson.detail || errorJson.message || errorMsg;
        } catch (e) { /* ignore parse error */ }
        throw new Error(errorMsg);
      }
      return await r.json();
    } catch (e) {
      clearTimeout(timeoutId);
      if (e.name === 'AbortError') throw new Error('请求超时');
      throw e;
    }
  }

  async function backendGet(url, timeoutMs) {
    var path = url.startsWith("/api") ? url.substring(4) : url;
    var fullUrl = App.API + path;
    var controller = new AbortController();
    var timeoutId = setTimeout(function() { controller.abort(); }, timeoutMs || _defaultTimeout);
    try {
      var r = await fetch(fullUrl, { cache: 'no-store', signal: controller.signal });
      clearTimeout(timeoutId);
      if (!r.ok) {
        var errorMsg = url + " " + r.status;
        try {
          var errorJson = await r.json();
          errorMsg = errorJson.detail || errorJson.message || errorMsg;
        } catch (e) { /* ignore parse error */ }
        throw new Error(errorMsg);
      }
      return await r.json();
    } catch (e) {
      clearTimeout(timeoutId);
      if (e.name === 'AbortError') throw new Error('请求超时');
      throw e;
    }
  }

  async function llmChat(messages, options) {
    options = options || {};
    var r = await fetch(App.LLM_API_URL + "/chat/completions", {
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
    });
    if (!r.ok) throw new Error("LLM API " + r.status + ": " + r.statusText);
    return await r.json();
  }

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

  App.doMove = async function(tx, ty) {
    App.setLoading(true, "行走中...");
    try {
      return await backendPost("/api/move", {
        player_id: App.playerId,
        to_x: tx,
        to_y: ty
      });
    } finally {
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

  App.rest = async function() {
    if (App.apiMode !== "backend") return null;
    return await backendPost("/api/rest", { player_id: App.playerId });
  };

  App.useItem = async function(itemName) {
    if (App.apiMode !== "backend") return null;
    return await backendPost("/api/item/use", { player_id: App.playerId, item: itemName });
  };

  App.finale = async function() {
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
      var errorMsg = "talk_stream " + res.status;
      try {
        var errorJson = await res.json();
        errorMsg = errorJson.detail || errorJson.message || errorMsg;
      } catch (e) { /* ignore parse error */ }
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

  App.testBackend = async function() {
    try {
      const data = await backendGet("/api/health");
      var llmConfigured = data.llm_configured || "false";
      var world = data.world || "(unknown)";
      return { ok: true, detail: "llm_configured=" + llmConfigured + " world=" + world };
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
