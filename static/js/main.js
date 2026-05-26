// ═══════════════════════════════════════════════════════
//  main.js — 应用入口 & 登录流程
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  // ── 登录界面切换 ──

  App.showLoadForm = async function() {
    document.getElementById("loginForm").style.display = "none";
    document.getElementById("loadForm").style.display = "block";
    try {
      var saves = await App.fetchSaves();
      var list = document.getElementById("savesList");
      list.innerHTML = "";
      saves.forEach(function(s) {
        var div = document.createElement("div");
        div.textContent = s.display_name + "  ("
          + s.map_id + ", \u7b2c" + s.world_day + "\u65e5)"
          + (s.dead ? " \u3010\u4ea1\u3011" : "");
        div.onclick = function() {
          var all = list.querySelectorAll("div");
          for (var i = 0; i < all.length; i++) { all[i].classList.remove("selected"); }
          div.classList.add("selected");
          div._pid = s.player_id;
        };
        list.appendChild(div);
      });
    } catch (e) {
      document.getElementById("savesList").innerHTML =
        '<div style="color:var(--red);">\u52a0\u8f7d\u5b58\u6863\u5217\u8868\u5931\u8d25</div>';
    }
  };

  App.showLoginForm = function() {
    document.getElementById("loadForm").style.display = "none";
    document.getElementById("loginForm").style.display = "block";
  };

  // ── 游戏入口 ──

  App.startNewGame = async function() {
    var name  = document.getElementById("inpName").value.trim() || "\u6c5f\u6e56\u5ba2";
    var gender = document.getElementById("inpGender").value;
    var permadeath = document.getElementById("inpPermadeath").checked;
    try {
      var result = await App.createPlayer(name, gender, permadeath);
      App.onGameReady(result.data, result.pid, result.data.display_name);
    } catch (e) {
      alert("\u521b\u5efa\u89d2\u8272\u5931\u8d25\uff1a" + e.message);
    }
  };

  App.loadGame = async function() {
    var sel = document.querySelector(".saves-list div.selected");
    if (!sel) { alert("\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u5b58\u6863"); return; }
    try {
      var data = await App.loadPlayer(sel._pid);
      App.onGameReady(data, sel._pid, data.display_name);
    } catch (e) {
      alert("\u8bfb\u6863\u5931\u8d25\uff1a" + e.message);
    }
  };

  /**
   * 登录 / 读档成功后进入游戏。
   * @param {Object} data  - 后端返回
   * @param {string} pid   - 玩家 id
   * @param {string} name  - 显示名
   */
  App.onGameReady = function(data, pid, name) {
    App.playerId    = pid;
    App.displayName = name || "\u6c5f\u6e56\u5ba2";
    App.mapsData    = data.maps || {};
    App.selectedNpcId = null;

    document.getElementById("loginOverlay").style.display = "none";
    document.getElementById("topbar").style.display = "flex";
    document.getElementById("mainUI").style.display = "flex";

    document.getElementById("introMsg").innerHTML =
      "<b>\u6b22\u8fce\uff0c" + App.displayName + "\uff01</b><br>"
      + (data.intro || "\u6c5f\u6e56\u8def\u8fdc\uff0c\u73cd\u91cd\u3002");

    App.updateUI(data);
  };

  // ── 退出 ──

  App.doLogout = function() {
    if (!confirm("\u786e\u5b9a\u9000\u51fa\uff1f\u672a\u5b58\u6863\u7684\u8fdb\u5ea6\u5c06\u4e22\u5931\u3002")) return;
    App.playerId = null;
    document.getElementById("mainUI").style.display = "none";
    document.getElementById("topbar").style.display = "none";
    document.getElementById("loginOverlay").style.display = "flex";
  };

  // ── 存档 ──

  App.doSaveFlow = async function() {
    if (!App.playerId) return;
    try {
      var data = await App.doSave();
      App.addMsg("system", data.ok ? "\ud83d\udcbe \u5b58\u6863\u6210\u529f" : "\u274c \u5b58\u6863\u5931\u8d25");
    } catch (e) {
      App.addMsg("system", "\u274c \u5b58\u6863\u5931\u8d25: " + e.message);
    }
  };

  // ── 定期刷新（每 30 秒）──
  setInterval(function() {
    if (App.playerId && !App.isStreaming) App.fetchState().then(App.updateUI);
  }, 30000);

  // ── 初始化：事件监听（npcSelect 切换 & Enter 发送）──
  document.addEventListener("DOMContentLoaded", function() {
    var sel = document.getElementById("npcSelect");
    sel.addEventListener("change", function() {
      App.selectedNpcId = sel.value;
      // 刷新侧栏选中状态
      var items = document.querySelectorAll(".npc-list li");
      for (var i = 0; i < items.length; i++) {
        var li = items[i];
        li.classList.toggle("selected",
          li.textContent.replace(/\s/g,"").indexOf(sel.options[sel.selectedIndex].text) >= 0);
      }
    });
  });

})(window.App);