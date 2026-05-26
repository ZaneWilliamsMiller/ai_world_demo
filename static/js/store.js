// ═══════════════════════════════════════════════════════
//  store.js — 全局应用状态（独立 Web 前端）
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  // ── API 配置（可切换后端/独立模式）──
  App.BACKEND_URL = "http://127.0.0.1:8765";  // 后端服务地址（独立打开时使用）
  App.LLM_API_URL = "https://llmapi.paratera.com/v1";  // LLM API 直连
  App.LLM_API_KEY = "sk-o5exptybwJAro8OfIqqmjQ";
  App.LLM_MODEL = "DeepSeek-V4-Pro";

  // 当前模式: "backend" | "standalone"
  App.apiMode = "backend";

  // 检测是否由后端 serve（同源），是则使用相对路径
  var _sameOrigin = (window.location.port === "8765");

  // 便捷属性：当前 API 基地址
  Object.defineProperty(App, "API", {
    get: function() {
      if (App.apiMode === "backend") {
        return _sameOrigin ? "/api" : App.BACKEND_URL + "/api";
      }
      return App.LLM_API_URL;
    }
  });

  // ── 玩家身份 ──
  App.playerId = null;
  App.displayName = null;

  // ── 世界数据 ──
  App.mapsData = {};
  App.currentMapId = null;
  App.npcCatalog = [];

  // ── NPC ──
  App.npcsHere = [];
  App.selectedNpcId = null;

  // ── 流式对话状态 ──
  App.isStreaming = false;

  // ── API 模式切换 ──
  App.setApiMode = function(mode) {
    App.apiMode = mode;
    var indicator = document.getElementById("apiModeIndicator");
    if (indicator) {
      indicator.textContent = mode === "backend" ? "后端模式" : "独立模式";
      indicator.className = "mode-badge " + mode;
    }
    console.log("[App] API mode →", mode);
  };

  App.getState = function() {
    return {
      playerId: App.playerId,
      displayName: App.displayName,
      mapsData: App.mapsData,
      currentMapId: App.currentMapId,
      npcsHere: App.npcsHere,
      selectedNpcId: App.selectedNpcId,
      isStreaming: App.isStreaming,
      apiMode: App.apiMode
    };
  };

  // ── 持久化 API 配置 ──
  App.saveConfig = function() {
    try {
      localStorage.setItem("lp_config", JSON.stringify({
        apiMode: App.apiMode,
        backendUrl: App.BACKEND_URL,
        llmApiUrl: App.LLM_API_URL,
        llmApiKey: App.LLM_API_KEY,
        llmModel: App.LLM_MODEL
      }));
    } catch(e) {}
  };

  App.loadConfig = function() {
    try {
      var cfg = JSON.parse(localStorage.getItem("lp_config") || "{}");
      if (cfg.apiMode) App.apiMode = cfg.apiMode;
      if (cfg.backendUrl) App.BACKEND_URL = cfg.backendUrl;
      if (cfg.llmApiUrl) App.LLM_API_URL = cfg.llmApiUrl;
      if (cfg.llmApiKey) App.LLM_API_KEY = cfg.llmApiKey;
      if (cfg.llmModel) App.LLM_MODEL = cfg.llmModel;
    } catch(e) {}
  };

  // 启动时加载配置
  App.loadConfig();

})(window.App);
