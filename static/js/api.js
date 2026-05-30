window.App = window.App || {};

(function(App) {
  "use strict";

  var _defaultTimeout = 30000;

  async function _handleErrorResponse(r, url) {
    var errorMsg = url + " " + r.status;
    try {
      var errorJson = await r.json();
      errorMsg = errorJson.detail || errorJson.message || errorMsg;
    } catch (_e) { /* ignore parse error */ }
    throw new Error(errorMsg);
  }

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
        await _handleErrorResponse(r, url);
      }
      return await r.json();
    } catch (e) {
      clearTimeout(timeoutId);
      if (e.name === 'AbortError') throw new Error('请求超时');
      if (e instanceof TypeError) throw new Error('网络连接中断，请检查后端服务');
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
        await _handleErrorResponse(r, url);
      }
      return await r.json();
    } catch (e) {
      clearTimeout(timeoutId);
      if (e.name === 'AbortError') throw new Error('请求超时');
      if (e instanceof TypeError) throw new Error('网络连接中断，请检查后端服务');
      throw e;
    }
  }

  App.backendPost = backendPost;
  App.backendGet = backendGet;

  App.createPlayer = async function(name, gender, permadeath) {
    const pid = "web_" + Date.now();
    const data = await backendPost("/api/hello", {
      player_id: pid,
      display_name: name,
      gender: gender,
      permadeath: permadeath
    });
    return { data: data, pid: pid };
  };

  App.loadPlayer = async function(playerId) {
    return await backendPost("/api/load", { player_id: playerId });
  };

  App.fetchSaves = async function() {
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
    if (!App.playerId) return null;
    return await backendGet("/api/state/" + App.playerId);
  };

  App.doSave = async function() {
    return await backendPost("/api/save", { player_id: App.playerId });
  };

  App.rest = async function() {
    return await backendPost("/api/rest", { player_id: App.playerId });
  };

  App.wait = async function() {
    return await backendPost("/api/wait", { player_id: App.playerId });
  };

  App.useItem = async function(itemName) {
    return await backendPost("/api/item/use", { player_id: App.playerId, item: itemName });
  };

  App.finale = async function() {
    return await backendPost("/api/finale", { player_id: App.playerId });
  };

  App.bountyRefresh = async function() {
    return await backendPost("/api/bounty/refresh", { player_id: App.playerId });
  };

  App.bountyAccept = async function(bountyId) {
    return await backendPost("/api/bounty/accept", { player_id: App.playerId, bounty_id: bountyId });
  };

  App.bountyCheck = async function() {
    return await backendPost("/api/bounty/check", { player_id: App.playerId });
  };

  App.bountyComplete = async function() {
    return await backendPost("/api/bounty/complete", { player_id: App.playerId });
  };

  App.bountyAbandon = async function() {
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
    var connectTimeout = setTimeout(function() { controller.abort(); }, 30000);

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
      await _handleErrorResponse(res, "talk_stream");
    }
    return res.body.getReader();
  };

  App.cancelTalkStream = function() {
    if (App._streamAbortController) {
      App._streamAbortController.abort();
      App._streamAbortController = null;
    }
  };

  App.actLoopStream = async function(npcId, maxSteps) {
    var requestBody = {
      player_id: App.playerId,
      npc_id: npcId,
      max_steps: maxSteps || 3
    };

    var controller = new AbortController();
    App._actLoopAbortController = controller;
    var timeoutId = setTimeout(function() { controller.abort(); }, 120000);

    var res;
    try {
      res = await fetch(App.API + "/agent/act_loop_stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
        signal: controller.signal
      });
      clearTimeout(timeoutId);
    } catch (e) {
      clearTimeout(timeoutId);
      App._actLoopAbortController = null;
      if (e.name === 'AbortError') throw new Error('行动循环超时（120秒）');
      throw e;
    }

    if (!res.ok) {
      App._actLoopAbortController = null;
      await _handleErrorResponse(res, "act_loop_stream");
    }
    return res.body.getReader();
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

  App.testBackendConnection = async function() {
    var resultEl = document.getElementById("backendTestResult");
    if (resultEl) {
      resultEl.textContent = "\u6d4b\u8bd5\u4e2d...";
      resultEl.className = "test-result testing";
    }
    var startTime = Date.now();
    try {
      var result = await App.testBackend();
      var latency = Date.now() - startTime;
      if (result.ok) {
        var msg = "\u540e\u7aef\u8fde\u63a5\u6210\u529f! \u5ef6\u8fdf: " + latency + "ms";
        if (resultEl) { resultEl.textContent = msg; resultEl.className = "test-result success"; }
        return { ok: true, latency: latency, message: msg };
      } else {
        var msg2 = "\u540e\u7aef\u8fde\u63a5\u5931\u8d25" + (result.detail || "");
        if (resultEl) { resultEl.textContent = msg2; resultEl.className = "test-result fail"; }
        return { ok: false, latency: latency, message: msg2 };
      }
    } catch (e) {
      var latency2 = Date.now() - startTime;
      var msg3 = "\u8fde\u63a5\u5931\u8d25: " + e.message;
      if (resultEl) { resultEl.textContent = msg3; resultEl.className = "test-result fail"; }
      return { ok: false, latency: latency2, message: msg3 };
    }
  };

})(window.App);
