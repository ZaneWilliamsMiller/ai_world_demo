// ═══════════════════════════════════════════════════════
//  main.js — 应用入口（独立 Web 前端）
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  App.showLoadForm = async function() {
    document.getElementById("loginForm").style.display = "none";
    document.getElementById("loadForm").style.display = "block";
    try {
      var saves = await App.fetchSaves();
      var list = document.getElementById("savesList");
      list.innerHTML = "";
      saves.forEach(function(s) {
        var div = document.createElement("div");
        div.textContent = s.display_name + "  (" + s.map_id + ", 第" + s.world_day + "日)" + (s.dead ? " [亡]" : "");
        div.onclick = function() {
          var all = list.querySelectorAll("div");
          for (var i = 0; i < all.length; i++) { all[i].classList.remove("selected"); }
          div.classList.add("selected");
          div._pid = s.player_id;
        };
        list.appendChild(div);
      });
    } catch (e) {
      document.getElementById("savesList").innerHTML = '<div style="color:#ef5350;">加载存档列表失败</div>';
    }
  };

  App.showLoginForm = function() {
    document.getElementById("loadForm").style.display = "none";
    document.getElementById("loginForm").style.display = "block";
  };

  App.startNewGame = async function() {
    var btn = document.querySelector('#loginForm button[onclick*="startNewGame"]');
    if (btn) { btn.disabled = true; btn.textContent = "⏳ 进入江湖..."; }

    var name  = document.getElementById("inpName").value.trim() || "江湖客";
    var gender = document.getElementById("inpGender").value;
    var permadeath = document.getElementById("inpPermadeath").checked;
    console.log("[App] startNewGame:", { name: name, gender: gender, permadeath: permadeath });

    try {
      console.log("[App] calling createPlayer...");
      var result = await App.createPlayer(name, gender, permadeath);
      console.log("[App] createPlayer OK:", result);
      App.onGameReady(result.data, result.pid, result.data.display_name);
    } catch (e) {
      console.error("[App] createPlayer FAILED:", e);
      // 用页面内提示代替 alert（避免被浏览器拦截）
      var errDiv = document.createElement("div");
      errDiv.style.cssText = "color:#ef5350;margin-top:8px;font-size:13px;";
      errDiv.textContent = "❌ 创建角色失败：" + e.message;
      document.getElementById("loginForm").appendChild(errDiv);
      if (btn) { btn.disabled = false; btn.textContent = "踏入江湖"; }
    }
  };

  App.loadGame = async function() {
    var sel = document.querySelector(".saves-list div.selected");
    if (!sel) { alert("请先选择一个存档"); return; }
    try {
      var data = await App.loadPlayer(sel._pid);
      App.onGameReady(data, sel._pid, data.display_name);
    } catch (e) {
      alert("读档失败：" + e.message);
    }
  };

  App.onGameReady = function(data, pid, name) {
    App.playerId    = pid;
    App.displayName = name || "江湖客";
    App.mapsData    = data.maps || {};
    App.selectedNpcId = null;

    document.getElementById("loginOverlay").style.display = "none";
    document.getElementById("topbar").style.display = "flex";
    document.getElementById("mainUI").style.display = "flex";

    document.getElementById("introMsg").innerHTML =
      "<b>欢迎，" + App.displayName + "！</b><br>" + (data.intro || "江湖路远，珍重。");

    App.updateUI(data);
  };

  App.doLogout = function() {
    if (!confirm("确定退出？未存档的进度将丢失。")) return;
    App.playerId = null;
    document.getElementById("mainUI").style.display = "none";
    document.getElementById("topbar").style.display = "none";
    document.getElementById("loginOverlay").style.display = "flex";
  };

  App.doSaveFlow = async function() {
    if (!App.playerId) return;
    try {
      var data = await App.doSave();
      App.addMsg("system", data.ok ? "存档成功" : "存档失败");
    } catch (e) {
      App.addMsg("system", "存档失败: " + e.message);
    }
  };

  setInterval(function() {
    if (App.playerId && !App.isStreaming && App.apiMode === "backend") {
      App.fetchState().then(function(data) { if (data) App.updateUI(data); });
    }
  }, 30000);

  document.addEventListener("DOMContentLoaded", function() {
    var modeIndicator = document.getElementById("apiModeIndicator");
    if (modeIndicator) {
      modeIndicator.textContent = App.apiMode === "backend" ? "后端模式" : "独立模式";
    }
    var sel = document.getElementById("npcSelect");
    if (sel) {
      sel.addEventListener("change", function() {
        App.selectedNpcId = sel.value;
      });
    }
  });

})(window.App);
