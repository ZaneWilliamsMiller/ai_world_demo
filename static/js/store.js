// ═══════════════════════════════════════════════════════
//  store.js — 全局应用状态（独立 Web 前端）
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  // ── API 配置（可切换后端/独立模式）──
  // 自动推导后端地址：同源时使用当前 host，否则默认 localhost:8765
  // 用户可通过配置面板覆盖此值
  (function() {
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem("lp_config") || "{}"); } catch(e) {}
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

  // 当前模式: "backend" | "standalone"
  App.apiMode = "backend";

  // 检测是否由后端 serve（同源），是则使用相对路径（前后端分离时永远为false）
  const _sameOrigin = false;

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

  // ── Shutdown 认证密钥 ──
  App.SHUTDOWN_SECRET = "";

  // ── API 模式切换 ──
  App.setApiMode = function(mode) {
    App.apiMode = mode;
    const indicator = document.getElementById("apiModeIndicator");
    if (indicator) {
      indicator.textContent = mode === "backend" ? "后端模式" : "独立模式";
      indicator.className = "api-mode-badge " + mode;
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
      // 只保存非敏感配置信息
      // 注意：故意不保存 LLM_API_KEY、LLM_API_URL 等敏感字段
      localStorage.setItem("lp_config", JSON.stringify({
        apiMode: App.apiMode,
        backendUrl: App.BACKEND_URL,
        // 敏感字段已移除，不再持久化：
        // - llmApiUrl: LLM API 地址可能包含认证信息
        // - llmApiKey: API 密钥，绝对不能存储在客户端
        // - llmModel: 模型名称相对安全，但为保持一致性也不存储
        llmModel: App.LLM_MODEL  // 模型名称不敏感，可以保存以提升用户体验
      }));
    } catch(e) {
      console.warn("[App] 保存配置失败:", e);
    }
  };

  App.loadConfig = function() {
    try {
      const cfg = JSON.parse(localStorage.getItem("lp_config") || "{}");
      if (cfg.apiMode && typeof App.setApiMode === "function") App.setApiMode(cfg.apiMode);
      else if (cfg.apiMode) App.apiMode = cfg.apiMode;
      if (cfg.backendUrl) App.BACKEND_URL = cfg.backendUrl;

      // ════════════════════════════════════
      // 数据迁移：清理旧版本中存储的敏感信息
      // 如果检测到旧配置包含敏感字段，清除它们并警告用户
      // ════════════════════════════════════
      if (cfg.llmApiKey || cfg.llmApiUrl) {
        console.warn(
          "[App] ⚠️ 安全警告：检测到旧版本配置中包含敏感信息（API 密钥）。\n" +
          "这些信息已被自动清除，不再存储在本地。\n" +
          "请重新通过配置面板输入您的 API 配置。"
        );

        // 清理 localStorage 中的敏感数据
        const safeCfg = {
          apiMode: cfg.apiMode || App.apiMode,
          backendUrl: cfg.backendUrl || App.BACKEND_URL,
          llmModel: cfg.llmModel || ""
        };
        localStorage.setItem("lp_config", JSON.stringify(safeCfg));

        // 不再从旧配置加载敏感信息到内存
        // App.LLM_API_URL 和 App.LLM_API_KEY 保持为空字符串
        // 用户需要重新输入
      }

      // 只加载非敏感的模型名称（如果有）
      if (cfg.llmModel) App.LLM_MODEL = cfg.llmModel;

    } catch(e) {
      console.warn("[App] 加载配置失败:", e);
    }
  };

  // 启动时加载配置
  App.loadConfig();

})(window.App);
