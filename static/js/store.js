window.App = window.App || {};

(function(App) {
  "use strict";

  (function() {
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem("lp_config") || "{}"); } catch(_e) {}
    if (saved && saved.backendUrl) {
      App.BACKEND_URL = saved.backendUrl;
    } else {
      App.BACKEND_URL = window.location.origin;
    }
  })();

  Object.defineProperty(App, "API", {
    get: function() { return App.BACKEND_URL + "/api"; }
  });

  App.playerId = null;
  App.displayName = null;

  App.mapsData = {};
  App.currentMapId = null;
  App.npcCatalog = [];

  App.npcsHere = [];
  App.selectedNpcId = null;

  App.isStreaming = false;

  App.SHUTDOWN_SECRET = "";

  App.saveConfig = function() {
    try {
      var cfg = {
        backendUrl: App.BACKEND_URL
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
      var cfg = JSON.parse(localStorage.getItem("lp_config") || "{}");
      if (cfg.backendUrl) App.BACKEND_URL = cfg.backendUrl;

      if (cfg.llmApiKey || cfg.llmApiUrl) {
        var safeCfg = {
          backendUrl: cfg.backendUrl || App.BACKEND_URL
        };
        localStorage.setItem("lp_config", JSON.stringify(safeCfg));
      }

      if (cfg.shutdownSecret) {
        App.SHUTDOWN_SECRET = cfg.shutdownSecret;
        var secretEl = document.getElementById("cfgShutdownSecret");
        if (secretEl) secretEl.value = cfg.shutdownSecret;
      }

    } catch(e) {
      console.warn("[App] 加载配置失败:", e);
    }
  };

  App.loadConfig();

})(window.App);
