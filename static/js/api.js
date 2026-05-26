// ═══════════════════════════════════════════════════════
//  api.js — 后端 API 调用封装
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  /** POST 辅助 */
  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function(r) {
      if (!r.ok) throw new Error(url + " " + r.status);
      return r.json();
    });
  }

  /** GET 辅助 */
  function get(url) {
    return fetch(url).then(function(r) {
      if (!r.ok) throw new Error(url + " " + r.status);
      return r.json();
    });
  }

  // ═══════════════════════════════════════════
  //  角色初始化 / 恢复
  // ═══════════════════════════════════════════

  /** 创建新角色 */
  App.createPlayer = async function(name, gender, permadeath) {
    var pid = "web_" + Date.now();
    var data = await post(App.API + "/hello", {
      player_id: pid,
      display_name: name,
      gender: gender,
      permadeath: permadeath
    });
    return { data: data, pid: pid };
  };

  /** 加载已有存档 */
  App.loadPlayer = async function(playerId) {
    return await post(App.API + "/load", { player_id: playerId });
  };

  /** 获取存档列表 */
  App.fetchSaves = async function() {
    return (await get(App.API + "/saves")).saves || [];
  };

  // ═══════════════════════════════════════════
  //  游戏操作
  // ═══════════════════════════════════════════

  /** 移动 */
  App.doMove = async function(tx, ty) {
    return await post(App.API + "/move", {
      player_id: App.playerId,
      to_x: tx,
      to_y: ty
    });
  };

  /** 查询状态 */
  App.fetchState = async function() {
    if (!App.playerId) return null;
    return await get(App.API + "/state/" + App.playerId);
  };

  /** 手动存档 */
  App.doSave = async function() {
    return await post(App.API + "/save", { player_id: App.playerId });
  };

  // ═══════════════════════════════════════════
  //  流式对话（SSE）
  // ═══════════════════════════════════════════

  /**
   * 发起流式对话，返回 { reader, onChunk, onDone } 钩子。
   * 调用方负责 read 循环与 UI 更新。
   */
  App.talkStream = async function(npcId, message) {
    var res = await fetch(App.API + "/npc/talk_stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_id: App.playerId, npc_id: npcId, message: message })
    });
    if (!res.ok) throw new Error("talk_stream " + res.status);
    return res.body.getReader();
  };

})(window.App);