// ═══════════════════════════════════════════════════════
//  main.js — 应用入口
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  let _statePollTimer = null;

  // ═══════════════════════════════════════════
  //  DOM 元素缓存 - 避免重复查询，提升性能
  // ═══════════════════════════════════════════
  const DOM = {
    configOverlay: null,
    configPanel: null,
    loginForm: null,
    loadForm: null,
    loginOverlay: null,
    topbar: null,
    mainUI: null,
    introMsg: null,
    confirmOverlay: null,
    confirmTitle: null,
    confirmMessage: null,
    confirmOk: null,
    confirmCancel: null,
    savesList: null,
    npcSelect: null,
    msgInput: null,

    init() {
      this.configOverlay = document.getElementById("configOverlay");
      this.configPanel = document.getElementById("configPanel");
      this.loginForm = document.getElementById("loginForm");
      this.loadForm = document.getElementById("loadForm");
      this.loginOverlay = document.getElementById("loginOverlay");
      this.topbar = document.getElementById("topbar");
      this.mainUI = document.getElementById("mainUI");
      this.introMsg = document.getElementById("introMsg");
      this.confirmOverlay = document.getElementById("confirmOverlay");
      this.confirmTitle = document.getElementById("confirmTitle");
      this.confirmMessage = document.getElementById("confirmMessage");
      this.confirmOk = document.getElementById("confirmOk");
      this.confirmCancel = document.getElementById("confirmCancel");
      this.savesList = document.getElementById("savesList");
      this.npcSelect = document.getElementById("npcSelect");
      this.msgInput = document.getElementById("msgInput");
    }
  };

  // 暴露 DOM 缓存供其他模块使用
  App.DOM = DOM;

  const HtmlUtils = App.HtmlUtils;

  App.toggleConfigPanel = function() {
    const overlay = DOM.configOverlay || document.getElementById("configOverlay");
    const panel = DOM.configPanel || document.getElementById("configPanel");
    if (!overlay || !panel) return;
    if (panel.style.display === "none" || panel.style.display === "") {
      panel.style.display = "block";
      overlay.style.display = "flex";
      App.fillConfigValues();
    } else {
      panel.style.display = "none";
      overlay.style.display = "none";
    }
  };

  App.fillConfigValues = function() {
    const backendUrl = document.getElementById("cfgBackendUrl");
    if (backendUrl) backendUrl.value = App.BACKEND_URL;
  };

  App.applyConfig = function() {
    const backendUrl = document.getElementById("cfgBackendUrl");
    if (backendUrl) App.BACKEND_URL = backendUrl.value.trim();
    App.saveConfig();
    App.toggleConfigPanel();
  };

  App.showLoadForm = async function() {
    const loginForm = DOM.loginForm || document.getElementById("loginForm");
    const loadForm = DOM.loadForm || document.getElementById("loadForm");
    if (loginForm) loginForm.style.display = "none";
    if (loadForm) loadForm.style.display = "block";

    try {
      const saves = await App.fetchSaves();
      const list = DOM.savesList || document.getElementById("savesList");
      list.innerHTML = "";
      if (saves.length === 0) {
        const emptyDiv = document.createElement("div");
        emptyDiv.textContent = "暂无存档";
        emptyDiv.style.cssText = "color:#888;padding:12px;text-align:center;";
        list.appendChild(emptyDiv);
      }
      saves.forEach(function(s) {
        const div = document.createElement("div");
        // 使用 textContent 设置文本，自动防止 XSS
        div.textContent = s.display_name + "  (" + s.map_id + ", 第" + s.world_day + "日)" + (s.dead ? " [亡]" : "");
        div.onclick = function() {
          const all = list.querySelectorAll("div");
          for (let i = 0; i < all.length; i++) { all[i].classList.remove("selected"); }
          div.classList.add("selected");
          div._pid = s.player_id;
        };
        list.appendChild(div);
      });
    } catch (_e) {
      const savesList = DOM.savesList || document.getElementById("savesList");
      // 错误消息使用安全方式显示
      HtmlUtils.setTrustedHtml(savesList, '<div style="color:#ef5350;">加载存档列表失败</div>');
    }
  };

  App.showLoginForm = function() {
    const loadForm = DOM.loadForm || document.getElementById("loadForm");
    const loginForm = DOM.loginForm || document.getElementById("loginForm");
    if (loadForm) loadForm.style.display = "none";
    if (loginForm) loginForm.style.display = "block";
  };

  App.startNewGame = async function() {
    const btn = document.querySelector('#loginForm button[onclick*="startNewGame"]');
    if (btn) { btn.disabled = true; btn.textContent = "⏳ 进入江湖..."; }

    const name   = document.getElementById("inpName").value.trim() || "江湖客";
    const gender = document.getElementById("inpGender").value;
    const permadeath = document.getElementById("inpPermadeath").checked;
    console.log("[App] startNewGame:", { name: name, gender: gender, permadeath: permadeath });

    try {
      console.log("[App] calling createPlayer...");
      const result = await App.createPlayer(name, gender, permadeath);
      console.log("[App] createPlayer OK:", result);
      App.onGameReady(result.data, result.pid, result.data.display_name);
    } catch (e) {
      console.error("[App] createPlayer FAILED:", e);
      // 用页面内提示代替 alert（避免被浏览器拦截）
      const errDiv = document.createElement("div");
      errDiv.className = "login-error";
      errDiv.style.cssText = "color:#ef5350;margin-top:8px;font-size:13px;";
      errDiv.textContent = "❌ 创建角色失败：" + e.message;
      const loginFormEl = DOM.loginForm || document.getElementById("loginForm");
      if (loginFormEl) {
        var oldErr = loginFormEl.querySelector(".login-error");
        if (oldErr) oldErr.remove();
        loginFormEl.appendChild(errDiv);
      }
      if (btn) { btn.disabled = false; btn.textContent = "踏入江湖"; }
    }
  };

  App.loadGame = async function() {
    const sel = document.querySelector(".saves-list div.selected");
    if (!sel) { App.addMsg("system", "请先选择一个存档"); return; }
    try {
      const data = await App.loadPlayer(sel._pid);
      App.onGameReady(data, sel._pid, data.display_name);
    } catch (e) {
      App.addMsg("system", "读档失败：" + e.message);
    }
  };

  App.onGameReady = function(data, pid, name) {
    App.playerId    = pid;
    App.displayName = name || "江湖客";
    App.mapsData    = data.maps || {};
    App.selectedNpcId = null;

    const loginOverlay = DOM.loginOverlay || document.getElementById("loginOverlay");
    const topbar = DOM.topbar || document.getElementById("topbar");
    const mainUI = DOM.mainUI || document.getElementById("mainUI");
    if (loginOverlay) loginOverlay.style.display = "none";
    if (topbar) topbar.style.display = "flex";
    if (mainUI) mainUI.style.display = "flex";

    const introMsg = DOM.introMsg || document.getElementById("introMsg");
    if (introMsg) {
      introMsg.textContent = "";
      var b = document.createElement("b");
      b.textContent = "欢迎，" + App.displayName + "！";
      introMsg.appendChild(b);
      introMsg.appendChild(document.createElement("br"));
      var introLines = (data.intro || "江湖路远，珍重。").split("\n");
      introLines.forEach(function(line, i) {
        if (i > 0) introMsg.appendChild(document.createElement("br"));
        introMsg.appendChild(document.createTextNode(line));
      });
    }

    App.updateUI(data);
  };

  App.doLogout = function() {
    App.showConfirm(
      "退出游戏",
      "确定要退出游戏吗？<br><br>⚠️ <b>未存档的进度将丢失</b>",
      function() {
        if (_statePollTimer) { clearInterval(_statePollTimer); _statePollTimer = null; }
        App.playerId = null;
        App.isStreaming = false;
        App.selectedNpcId = null;
        const mainUI = DOM.mainUI || document.getElementById("mainUI");
        const topbar = DOM.topbar || document.getElementById("topbar");
        const loginOverlay = DOM.loginOverlay || document.getElementById("loginOverlay");
        if (mainUI) mainUI.style.display = "none";
        if (topbar) topbar.style.display = "none";
        if (loginOverlay) loginOverlay.style.display = "flex";
      }
    );
  };

  App.doSaveFlow = async function() {
    if (!App.playerId) return;
    try {
      const data = await App.doSave();
      App.addMsg("system", data.ok ? "存档成功" : "存档失败");
    } catch (e) {
      App.addMsg("system", "存档失败: " + e.message);
    }
  };

  App.doUseItem = async function(itemName) {
    if (!App.playerId) return;
    try {
      const data = await App.useItem(itemName);
      if (data) {
        App.addMsg("system", data.note || data.message || "使用了 " + itemName);
        if (data.player) App.updateUI(data);
      }
    } catch (e) {
      App.addMsg("system", "使用失败: " + e.message);
    }
  };

  App.doRest = async function() {
    if (!App.playerId) return;
    try {
      App.addMsg("system", "正在休息...");
      const data = await App.rest();
      if (data) {
        App.addMsg("system", data.note || data.message || "休息完毕");
        if (data.player) App.updateUI(data);
      }
    } catch (e) {
      App.addMsg("system", "休息失败: " + e.message);
    }
  };

  App.doWait = async function() {
    if (!App.playerId) return;
    try {
      const data = await App.wait();
      if (data) {
        App.addMsg("system", data.note || "时光流逝……");
        if (data.player) App.updateUI(data);
      }
    } catch (e) {
      App.addMsg("system", "等待失败: " + e.message);
    }
  };

  App.doFinale = async function() {
    if (!App.playerId) return;
    App.showConfirm(
      "终局收束",
      "确定要结束这段江湖旅程吗？<br><br>⚠️ <b>此操作不可逆</b>",
      async function() {
        try {
          const data = await App.finale();
          if (data) {
            if (data.epilogue) {
              App.addMsg("system", "【" + (data.ending_label || "江湖路尽") + "】");
              App.addMsg("npc", {speaker: "终局叙事", text: data.epilogue}, true);
            } else {
              App.addMsg("system", data.ending_label || "江湖路尽");
            }
            if (data.player) App.updateUI(data);
          }
        } catch (e) {
          App.addMsg("system", "终局失败: " + e.message);
        }
      }
    );
  };

  App.doBountyRefresh = async function() {
    if (!App.playerId) return;
    try {
      const data = await App.bountyRefresh();
      if (data) {
        App.addMsg("system", data.board_text || "悬赏榜已刷新");
        App.updateUI(data);
      }
    } catch (e) {
      App.addMsg("system", "刷新悬赏失败: " + e.message);
    }
  };

  App.doBountyAccept = async function(bountyId) {
    if (!App.playerId) return;
    try {
      const data = await App.bountyAccept(bountyId);
      App.addMsg("system", data.message || (data.ok ? "已接受悬赏" : "无法接受"));
      if (data.ok) App.doBountyRefresh();
    } catch (e) {
      App.addMsg("system", "接受悬赏失败: " + e.message);
    }
  };

  App.doBountyComplete = async function() {
    if (!App.playerId) return;
    try {
      const data = await App.bountyComplete();
      if (data.ok) {
        App.addMsg("system", "悬赏完成！" + (data.reward ? " 获得奖励: " + data.reward : ""));
        App.doBountyRefresh();
      } else {
        App.addMsg("system", data.message || "无法完成悬赏");
      }
    } catch (e) {
      App.addMsg("system", "完成悬赏失败: " + e.message);
    }
  };

  App.doBountyAbandon = async function() {
    if (!App.playerId) return;
    App.showConfirm(
      "放弃悬赏",
      "确定要放弃当前悬赏吗？",
      async function() {
        try {
          const data = await App.bountyAbandon();
          App.addMsg("system", data.message || (data.ok ? "已放弃悬赏" : "无法放弃"));
          if (data.ok) App.doBountyRefresh();
        } catch (e) {
          App.addMsg("system", "放弃悬赏失败: " + e.message);
        }
      }
    );
  };

  App.deleteSave = async function() {
    var sel = document.querySelector(".saves-list div.selected");
    if (!sel) { App.addMsg("system", "请先选择一个存档"); return; }
    var pid = sel._pid;
    App.showConfirm(
      "删除存档",
      "确定要删除此存档吗？<br><br>⚠️ <b>此操作不可逆</b>",
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

  // showConfirm: message 参数必须为调用方硬编码的可信 HTML（不可传入用户输入）
  var _confirmActive = false;

  App.showConfirm = function(title, message, onConfirm) {
    if (_confirmActive) return;
    _confirmActive = true;

    const overlay = DOM.confirmOverlay || document.getElementById("confirmOverlay");
    const titleEl = DOM.confirmTitle || document.getElementById("confirmTitle");
    const msgEl = DOM.confirmMessage || document.getElementById("confirmMessage");
    const okBtn = DOM.confirmOk || document.getElementById("confirmOk");
    const cancelBtn = DOM.confirmCancel || document.getElementById("confirmCancel");

    titleEl.textContent = title;
    HtmlUtils.setTrustedHtml(msgEl, message);

    overlay.classList.add("show");

    var _onOverlayClick, _onKeydown;

    function cleanup() {
      _confirmActive = false;
      overlay.classList.remove("show");
      okBtn.removeEventListener("click", handleOk);
      cancelBtn.removeEventListener("click", handleCancel);
      if (_onOverlayClick) overlay.removeEventListener("click", _onOverlayClick);
      if (_onKeydown) document.removeEventListener("keydown", _onKeydown);
    }

    function handleOk(e) {
      e.preventDefault();
      e.stopPropagation();
      cleanup();
      if (typeof onConfirm === "function") {
        try {
          var result = onConfirm();
          if (result && typeof result.catch === "function") {
            result.catch(function(err) { console.error("onConfirm error:", err); });
          }
        } catch (err) {
          console.error("onConfirm error:", err);
        }
      }
    }

    function handleCancel(e) {
      e.preventDefault();
      e.stopPropagation();
      cleanup();
    }

    okBtn.addEventListener("click", handleOk);
    cancelBtn.addEventListener("click", handleCancel);

    _onOverlayClick = function(e) {
      if (e.target === overlay) { cleanup(); }
    };
    overlay.addEventListener("click", _onOverlayClick);

    _onKeydown = function(e) {
      if (e.key === "Escape") { cleanup(); }
    };
    document.addEventListener("keydown", _onKeydown);
  };

  App.shutdownAll = function() {
    App.showConfirm(
      "关闭服务",
      "确定要关闭服务吗？<br><br>" +
      "⚠️ <b>这将停止后端服务</b><br><br>" +
      "💡 所有未保存的进度将丢失",
      async function() {
        try {
          const overlay = DOM.loginOverlay || document.getElementById("loginOverlay");
          if (overlay) {
              HtmlUtils.setTrustedHtml(overlay,
                '<div class="shutdown-screen">' +
                '<div class="shutdown-icon">⏳</div>' +
                '<h2>正在关闭服务...</h2>' +
                '<p class="shutdown-step pending" id="shutdownStep1">⏳ 正在发送关闭指令...</p>' +
                '<p class="shutdown-step pending" id="shutdownStep2" style="display:none;">⏳ 验证服务已停止...</p>' +
                '</div>');
              overlay.style.display = 'flex';
            }

          let step1 = document.getElementById("shutdownStep1");
          let step2 = document.getElementById("shutdownStep2");

          let backendSuccess = false;
          let lastError = null;

          const maxRetries = 3;
          for (let attempt = 1; attempt <= maxRetries; attempt++) {
            if (step1) {
              step1.textContent = "⏳ 正在发送关闭指令 (第" + attempt + "/" + maxRetries + "次)...";
            }

            try {
              const controller = new AbortController();
              const timeoutId = setTimeout(function() { controller.abort(); }, 15000);

              const resp = await fetch("/api/shutdown", {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "X-Shutdown-Secret": App.SHUTDOWN_SECRET || ""
                },
                signal: controller.signal
              });

              clearTimeout(timeoutId);
              await resp.json();
              backendSuccess = true;
              lastError = null;

              if (step1) {
                step1.textContent = "✓ 服务已接收关闭指令 (第" + attempt + "次尝试成功)";
                step1.classList.remove("pending");
                step1.classList.add("done");
              }
              break;

            } catch (e) {
              lastError = e;

              const isNetworkError = e.message === 'Failed to fetch' ||
                                     e.name === 'TypeError';

              if (isNetworkError) {
                backendSuccess = true;
                lastError = null;

                if (step1) {
                  step1.textContent = "✓ 服务已接收关闭指令 (网络断开确认)";
                  step1.classList.remove("pending");
                  step1.classList.add("done");
                }
                break;
              }

              backendSuccess = false;

              if (attempt < maxRetries) {
                if (step1) {
                  step1.textContent = "⚠️ 第" + attempt + "次失败，2秒后重试...";
                  step1.classList.remove("pending");
                  step1.classList.add("error");
                }
                await new Promise(function(r) { setTimeout(r, 2000); });

                if (step1) {
                  step1.classList.remove("error");
                  step1.classList.add("pending");
                }
              } else {
                if (step1) {
                  step1.textContent = "✗ 无法连接服务 (" + maxRetries + "次尝试均失败)";
                  step1.classList.add("error");
                }
              }
            }
          }

          if (backendSuccess && step2) {
            step2.style.display = "block";
            step2.textContent = "⏳ 验证服务已停止...";

            let serverStopped = false;
            for (let i = 0; i < 15; i++) {
              await new Promise(function(r) { setTimeout(r, 500); });

              try {
                await fetch("/api/health", { cache: 'no-store' });
              } catch (_err) {
                serverStopped = true;
                break;
              }
            }

            if (serverStopped) {
              step2.textContent = "✓ 服务已确认停止";
              step2.classList.remove("pending");
              step2.classList.add("done");
            } else {
              step2.textContent = "⚠️ 服务可能仍在运行（超时未停止）";
              step2.classList.remove("pending");
              step2.classList.add("error");
            }
          }

          await new Promise(function(r) { setTimeout(r, 600); });

          if (overlay) {
            const resultIcon = backendSuccess ? "✅" : "🔶";
            const resultTitle = backendSuccess ? "服务已关闭" : "服务关闭未完全成功";

            let statusHtml = "";
            if (backendSuccess) {
              statusHtml = "✅ 服务已停止<br>";
            } else {
              statusHtml = "❌ 服务未能自动关闭<br>";
              if (lastError) {
                statusHtml += "   错误: " + HtmlUtils.escape(lastError.message.substring(0, 80)) + "<br>";
              }
              statusHtml += "   请手动关闭终端窗口<br>";
            }

            HtmlUtils.setTrustedHtml(overlay,
              '<div class="shutdown-screen">' +
              '<div class="shutdown-icon">' + resultIcon + '</div>' +
              '<h2>' + resultTitle + '</h2>' +
              '<p style="font-size:16px;line-height:1.8;">' +
              statusHtml +
              '<br><span style="color:#a0a0b0;">' +
              '此页面即将失效<br>' +
              '可重新运行 <code>python start.py</code> 启动服务</span></p>' +
              '</div>');
          }

        } catch (e) {
          console.error("Shutdown error:", e);
          App.addMsg("system", "关闭过程中出现错误: " + e.message + " — 请手动关闭终端窗口。");
        }
      }
    );
  };

  App.setLoading = function(active, text) {
    var overlay = document.getElementById("loadingOverlay");
    if (!overlay) return;
    if (active) {
      overlay.style.display = "flex";
      var label = overlay.querySelector(".loading-text");
      if (label) label.textContent = text || "加载中...";
    } else {
      overlay.style.display = "none";
    }
  };

  let _pollErrorCount = 0;
  var _pageVisible = true;

  document.addEventListener("visibilitychange", function() {
    _pageVisible = !document.hidden;
    if (_pageVisible && App.playerId) {
      App.fetchState().then(function(data) { if (data) App.updateUI(data); }).catch(function() {});
    }
  });

  _statePollTimer = setInterval(function() {
    if (!_pageVisible) return;
    if (App.playerId && !App.isStreaming) {
      App.fetchState().then(function(data) {
        if (data) {
          _pollErrorCount = 0;
          App.updateUI(data);
        }
      }).catch(function(err) {
        _pollErrorCount++;
        if (err.message && err.message.includes('404')) {
          App.doLogout();
        } else if (_pollErrorCount >= 3) {
          App.addMsg("system", "⚠️ 与服务器连接中断，正在尝试重连...");
        }
      });
    }
  }, 30000);

  document.addEventListener("DOMContentLoaded", function() {
    DOM.init();

    fetch("/api/health", { cache: "no-store" })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        try {
          var cfg = JSON.parse(localStorage.getItem("lp_config") || "{}");
          if (cfg.shutdownSecret) {
            App.SHUTDOWN_SECRET = cfg.shutdownSecret;
          } else if (data.shutdown_configured === "true" && !App.SHUTDOWN_SECRET) {
            App.SHUTDOWN_SECRET = "dev";
          }
        } catch(_e) {}
      })
      .catch(function() {});

    const sel = DOM.npcSelect;
    if (sel) {
      sel.addEventListener("change", function() {
        App.selectedNpcId = sel.value;
      });
    }

    var bountyRefreshBtn = document.getElementById("bountyRefreshBtn");
    if (bountyRefreshBtn) bountyRefreshBtn.addEventListener("click", function() { App.doBountyRefresh(); });
    var bountyCompleteBtn = document.getElementById("bountyCompleteBtn");
    if (bountyCompleteBtn) bountyCompleteBtn.addEventListener("click", function() { App.doBountyComplete(); });
    var bountyAbandonBtn = document.getElementById("bountyAbandonBtn");
    if (bountyAbandonBtn) bountyAbandonBtn.addEventListener("click", function() { App.doBountyAbandon(); });

    var cancelStreamBtn = document.getElementById("cancelStreamBtn");
    if (cancelStreamBtn) {
      cancelStreamBtn.addEventListener("click", function() {
        App.cancelTalkStream();
      });
    }
  });

})(window.App);
