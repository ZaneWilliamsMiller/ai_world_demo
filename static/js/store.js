// ═══════════════════════════════════════════════════════
//  store.js — 全局应用状态
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  // ── API 配置 ──
  // 后端同时提供 API 和静态文件，同源部署
  // 用户可通过配置面板覆盖此值
  (function() {
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem("lp_config") || "{}"); } catch(_e) {}
    if (saved && saved.backendUrl) {
      App.BACKEND_URL = saved.backendUrl;
    } else {
      App.BACKEND_URL = window.location.origin;
    }
  })();
  // 敏感配置请通过配置面板设置，不要硬编码在代码中！
  // 安全警告：以下敏感信息仅存储在内存中（App 对象属性），
  // 不会持久化到 localStorage，以防止密钥泄露风险。
  // 用户每次启动应用都需要重新输入这些敏感配置。
  App.LLM_API_URL = "";
  App.LLM_API_KEY = "";
  App.LLM_MODEL = "";

  Object.defineProperty(App, "API", {
    get: function() { return "/api"; }
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

  // ── Shutdown 认证密钥 ──
  App.SHUTDOWN_SECRET = "";

  App.getState = function() {
    return {
      playerId: App.playerId,
      displayName: App.displayName,
      mapsData: App.mapsData,
      currentMapId: App.currentMapId,
      npcsHere: App.npcsHere,
      selectedNpcId: App.selectedNpcId,
      isStreaming: App.isStreaming
    };
  };

  // ═══════════════════════════════════════════
  //  配置持久化 - 安全策略
  //
  //  ⚠️ 安全警告：API 密钥等敏感信息不会存储到 localStorage
  //  原因：
  //  1. localStorage 可被同源所有 JavaScript 访问，存在 XSS 风险
  //  2. 浏览器开发者工具可轻松读取 localStorage 内容
  //  3. 如果用户设备被恶意软件感染，localStorage 可能被窃取
  //
  //  解决方案：
  //  - 敏感信息仅存储在内存中（App 对象属性）
  //  - 页面关闭或刷新后，用户需要重新输入敏感配置
  //  - 这是安全性与便利性的权衡，优先保障安全性
  // ═══════════════════════════════════════════

  App.saveConfig = function() {
    try {
      var cfg = {
        backendUrl: App.BACKEND_URL,
        llmModel: App.LLM_MODEL
      };
      var secretEl = document.getElementById("cfgShutdownSecret");
      if (secretEl && secretEl.value) {
        cfg.shutdownSecret = secretEl.value;
        App.SHUTDOWN_SECRET = secretEl.value;
      }
      localStorage.setItem("lp_config", JSON.stringify(cfg));
    } catch(e) {
      console.warn("[App] 保存配置失败:", e);
    }
  };

  App.loadConfig = function() {
    try {
      const cfg = JSON.parse(localStorage.getItem("lp_config") || "{}");
      if (cfg.backendUrl) App.BACKEND_URL = cfg.backendUrl;

      // ════════════════════════════════════
      // 数据迁移：清理旧版本中存储的敏感信息
      // ════════════════════════════════════
      if (cfg.llmApiKey || cfg.llmApiUrl) {
        console.warn(
          "[App] ⚠️ 安全警告：检测到旧版本配置中包含敏感信息（API 密钥）。\n" +
          "这些信息已被自动清除，不再存储在本地。\n" +
          "请重新通过配置面板输入您的 API 配置。"
        );

        const safeCfg = {
          backendUrl: cfg.backendUrl || App.BACKEND_URL,
          llmModel: cfg.llmModel || ""
        };
        localStorage.setItem("lp_config", JSON.stringify(safeCfg));
      }

      if (cfg.llmModel) App.LLM_MODEL = cfg.llmModel;

      if (cfg.shutdownSecret) {
        App.SHUTDOWN_SECRET = cfg.shutdownSecret;
        var secretEl = document.getElementById("cfgShutdownSecret");
        if (secretEl) secretEl.value = cfg.shutdownSecret;
      }

    } catch(e) {
      console.warn("[App] 加载配置失败:", e);
    }
  };

  // 启动时加载配置
  App.loadConfig();

})(window.App);
