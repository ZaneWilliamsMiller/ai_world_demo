// ═══════════════════════════════════════════════════════
//  store.js — 全局应用状态
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  // --- API 基地址 ---
  App.API = "/api";

  // --- 玩家身份 ---
  App.playerId = null;
  App.displayName = null;

  // --- 世界数据 ---
  App.mapsData = {};
  App.currentMapId = null;

  // --- NPC ---
  /** @type {Array<{id:string, name:string}>} */
  App.npcsHere = [];
  App.selectedNpcId = null;

  // --- 流式对话状态 ---
  App.isStreaming = false;

  // --- 统一暴露给外部 ---
  App.getState = function() {
    return {
      playerId:    App.playerId,
      displayName: App.displayName,
      mapsData:    App.mapsData,
      currentMapId: App.currentMapId,
      npcsHere:    App.npcsHere,
      selectedNpcId: App.selectedNpcId,
      isStreaming: App.isStreaming
    };
  };

})(window.App);