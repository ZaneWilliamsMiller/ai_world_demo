// ═══════════════════════════════════════════════════════
//  auth.js — 登录/登出/存档/游戏就绪
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  var HtmlUtils = App.HtmlUtils;

  App.showLoadForm = async function() {
    var loginForm = document.getElementById("loginForm");
    var loadForm = document.getElementById("loadForm");
    if (loginForm) loginForm.style.display = "none";
    if (loadForm) loadForm.style.display = "block";

    try {
      var saves = await App.fetchSaves();
      var list = document.getElementById("savesList");
      list.replaceChildren();
      if (saves.length === 0) {
        var emptyDiv = document.createElement("div");
        emptyDiv.textContent = "暂无存档";
        emptyDiv.style.cssText = "color:#888;padding:12px;text-align:center;";
        list.appendChild(emptyDiv);
      }
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
    } catch (_e) {
      var savesList = document.getElementById("savesList");
      HtmlUtils.setTrustedHtml(savesList, '<div style="color:#ef5350;">加载存档列表失败</div>');
    }
  };

  App.showLoginForm = function() {
    var loadForm = document.getElementById("loadForm");
    var loginForm = document.getElementById("loginForm");
    if (loadForm) loadForm.style.display = "none";
    if (loginForm) loginForm.style.display = "block";
  };

  App.startNewGame = async function() {
    var btn = document.querySelector('#loginForm button[onclick*="startNewGame"]');
    var nameEl = document.getElementById("inpName");
    var name = nameEl ? nameEl.value.trim() : "";
    if (!name) {
      var loginFormEl = document.getElementById("loginForm");
      if (loginFormEl) {
        var oldErr = loginFormEl.querySelector(".login-error");
        if (oldErr) oldErr.remove();
        var errDiv = document.createElement("div");
        errDiv.className = "login-error";
        errDiv.style.cssText = "color:#ef5350;margin-top:8px;font-size:13px;";
        errDiv.textContent = "\u274c 江湖名号不能为空";
        loginFormEl.appendChild(errDiv);
      }
      return;
    }
    try {
      var saves = await App.fetchSaves();
      var dup = saves.find(function(s) { return s.display_name === name; });
      if (dup) {
        var loginFormEl2 = document.getElementById("loginForm");
        if (loginFormEl2) {
          var oldErr2 = loginFormEl2.querySelector(".login-error");
          if (oldErr2) oldErr2.remove();
          var errDiv2 = document.createElement("div");
          errDiv2.className = "login-error";
          errDiv2.style.cssText = "color:#ef5350;margin-top:8px;font-size:13px;";
          errDiv2.textContent = "\u274c 已有名号\u300c" + name + "\u300d的存档，请换一个名号";
          loginFormEl2.appendChild(errDiv2);
        }
        return;
      }
    } catch (_e) {}

    if (btn) { btn.disabled = true; btn.textContent = "\u23f3 进入江湖..."; }

    var gender = document.getElementById("inpGender").value;
    var permadeath = document.getElementById("inpPermadeath").checked;
    console.log("[App] startNewGame:", { name: name, gender: gender, permadeath: permadeath });

    var pid = "web_" + Date.now();
    App.startEvolution(pid, name, gender, permadeath);
  };

  App.loadGame = async function() {
    var sel = document.querySelector(".saves-list div.selected");
    if (!sel) { App.addMsg("system", "请先选择一个存档"); return; }
    try {
      var data = await App.loadPlayer(sel._pid);
      App.onGameReady(data, sel._pid, data.display_name);
    } catch (e) {
      App.addMsg("system", "读档失败：" + e.message);
    }
  };

  App.deleteSave = async function() {
    var sel = document.querySelector(".saves-list div.selected");
    if (!sel) { App.addMsg("system", "请先选择一个存档"); return; }
    var pid = sel._pid;
    App.showConfirm(
      "删除存档",
      "确定要删除此存档吗？<br><br>\u26a0\ufe0f <b>此操作不可逆</b>",
      async function() {
        try {
          await App.backendPost("/api/delete-save", { player_id: pid });
          App.addMsg("system", "存档已删除");
          App.showLoadForm();
        } catch (e) {
          App.addMsg("system", "删除失败: " + e.message);
        }
      }
    );
  };

})(window.App);
