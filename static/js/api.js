// ═══════════════════════════════════════════════════════
//  api.js — 后端 API 调用封装（支持后端/独立双模式）
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  // ── 后端模式 API ──

  function backendPost(url, body) {
    // 使用 App.API 自动处理同源/跨域 URL
    var path = url.startsWith("/api") ? url.substring(4) : url;
    var fullUrl = App.API + path;
    return fetch(fullUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(async function(r) {
      if (!r.ok) {
        try {
          var errorJson = await r.json();
          throw new Error(errorJson.detail || errorJson.message || url + " " + r.status);
        } catch (e) {
          throw new Error(url + " " + r.status);
        }
      }
      return r.json();
    });
  }

  function backendGet(url) {
    var path = url.startsWith("/api") ? url.substring(4) : url;
    var fullUrl = App.API + path;
    return fetch(fullUrl).then(async function(r) {
      if (!r.ok) {
        try {
          var errorJson = await r.json();
          throw new Error(errorJson.detail || errorJson.message || url + " " + r.status);
        } catch (e) {
          throw new Error(url + " " + r.status);
        }
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
      var pid = "web_" + Date.now();
      var data = await backendPost("/api/hello", {
        player_id: pid,
        display_name: name,
        gender: gender,
        permadeath: permadeath
      });
      return { data: data, pid: pid };
    } else {
      // 独立模式：仅本地创建状态
      var pid = "standalone_" + Date.now();
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
    if (App.apiMode === "backend") {
      var res = await fetch(App.API + "/npc/talk_stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          player_id: App.playerId,
          npc_id: npcId,
          message: message
        })
      });
      if (!res.ok) {
        try {
          var errorJson = await res.json();
          throw new Error(errorJson.detail || errorJson.message || "talk_stream " + res.status);
        } catch (e) {
          throw new Error("talk_stream " + res.status);
        }
      }
      return res.body.getReader();
    } else {
      // 独立模式：直接调用 LLM API
      var systemPrompt = "你是江湖中的一位人物，以古风对话风格回应。保持简练、有趣、符合武侠世界观。";
      var res = await fetch(App.LLM_API_URL + "/chat/completions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer " + App.LLM_API_KEY
        },
        body: JSON.stringify({
          model: App.LLM_MODEL,
          messages: [
            { role: "system", content: systemPrompt },
            { role: "user", content: message }
          ],
          max_tokens: 512,
          stream: true
        })
      });
      if (!res.ok) throw new Error("LLM stream " + res.status);
      return res.body.getReader();
    }
  };

  // ═══════════════════════════════════════════
  //  连接测试
  // ═══════════════════════════════════════════

  App.testBackend = async function() {
    try {
      var data = await backendGet("/health");
      return { ok: true, detail: "model=" + data.model + " world=" + data.world };
    } catch (e) {
      return { ok: false, detail: e.message };
    }
  };

  App.testLLM = async function() {
    try {
      var data = await llmChat([{ role: "user", content: "你好" }], { maxTokens: 20 });
      var content = data.choices[0].message.content;
      return { ok: true, detail: "reply_len=" + content.length };
    } catch (e) {
      return { ok: false, detail: e.message };
    }
  };

  App.testModels = async function() {
    try {
      var res = await fetch(App.LLM_API_URL + "/models", {
        headers: { "Authorization": "Bearer " + App.LLM_API_KEY }
      });
      var data = await res.json();
      var ids = data.data.map(function(m) { return m.id; });
      return { ok: ids.includes(App.LLM_MODEL), detail: "models=" + ids.length + " target=" + App.LLM_MODEL };
    } catch (e) {
      return { ok: false, detail: e.message };
    }
  };

})(window.App);
