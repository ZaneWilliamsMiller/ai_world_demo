// ═══════════════════════════════════════════════════════
//  main.js — 应用入口（配置、操作、关闭、离线、DOM 初始化）
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  let _statePollTimer = null;

  const HtmlUtils = App.HtmlUtils;

  App.toggleConfigPanel = function() {
    const overlay = document.getElementById("configOverlay");
    const panel = document.getElementById("configPanel");
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

  App.onGameReady = function(data, pid, name) {
    App.playerId    = pid;
    App.displayName = name || "江湖客";
    App.mapsData    = data.maps || {};
    App.selectedNpcId = null;

    const loginOverlay = document.getElementById("loginOverlay");
    const topbar = document.getElementById("topbar");
    const mainUI = document.getElementById("mainUI");
    if (loginOverlay) loginOverlay.style.display = "none";
    if (topbar) topbar.style.display = "flex";
    if (mainUI) mainUI.style.display = "flex";

    const introMsg = document.getElementById("introMsg");
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

    if (_statePollTimer) { clearInterval(_statePollTimer); _statePollTimer = null; }
    _statePollTimer = setInterval(function() {
      if (!_pageVisible) return;
      if (App.playerId && !App.isStreaming) {
        App.fetchState().then(function(d) {
          if (d) { _pollErrorCount = 0; App.updateUI(d); }
        }).catch(function(err) {
          _pollErrorCount++;
          if (err.message && err.message.includes('404')) {
            App.doLogout();
          } else if (_pollErrorCount >= 3) {
            fetch("/api/health", { cache: "no-store" })
              .then(function() { _pollErrorCount = 0; })
              .catch(function() { App.addMsg("system", "\u26a0\ufe0f \u4e0e\u670d\u52a1\u5668\u8fde\u63a5\u4e2d\u65ad\uff0c\u8bf7\u68c0\u67e5\u540e\u7aef\u670d\u52a1\u662f\u5426\u8fd0\u884c"); });
          }
        });
      }
    }, 30000);
  };

  App.doLogout = function() {
    App.showConfirm(
      "退出游戏",
      "确定要退出游戏吗？<br><br>\u26a0\ufe0f <b>未存档的进度将丢失</b>",
      function() {
        if (_statePollTimer) { clearInterval(_statePollTimer); _statePollTimer = null; }
        App.cancelTalkStream();
        if (App._actLoopAbortController) { App._actLoopAbortController.abort(); App._actLoopAbortController = null; }
        App.playerId = null;
        App.isStreaming = false;
        App.selectedNpcId = null;
        App.mapsData = {};
        App.currentMapId = null;
        const mainUI = document.getElementById("mainUI");
        const topbar = document.getElementById("topbar");
        const loginOverlay = document.getElementById("loginOverlay");
        if (mainUI) mainUI.style.display = "none";
        if (topbar) topbar.style.display = "none";
        if (loginOverlay) loginOverlay.style.display = "flex";
        var startBtn = document.querySelector('#loginForm button[onclick*="startNewGame"]');
        if (startBtn) { startBtn.disabled = false; startBtn.textContent = "踏入江湖"; }
        var loginForm = document.getElementById("loginForm");
        var loadForm = document.getElementById("loadForm");
        if (loginForm) loginForm.style.display = "block";
        if (loadForm) loadForm.style.display = "none";
        if (loginForm) {
          var oldErr = loginForm.querySelector(".login-error");
          if (oldErr) oldErr.remove();
        }
        var dialogueArea = document.getElementById("dialogueArea");
        if (dialogueArea) dialogueArea.innerHTML = "";
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
      "确定要结束这段江湖旅程吗？<br><br>\u26a0\ufe0f <b>此操作不可逆</b>",
      async function() {
        try {
          const data = await App.finale();
          if (data) {
            if (data.epilogue) {
              App.addMsg("system", "\u3010" + (data.ending_label || "江湖路尽") + "\u3011");
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
        var rewardText = data.reward ? (typeof data.reward === "string" ? data.reward : JSON.stringify(data.reward)) : "";
        App.addMsg("system", "悬赏完成！" + (rewardText ? " 获得奖励: " + rewardText : ""));
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

  App.shutdownAll = function() {
    App.showConfirm(
      "关闭服务",
      "确定要关闭服务吗？<br><br>" +
      "\u26a0\ufe0f <b>这将停止后端服务</b><br><br>" +
      "\ud83d\udca1 所有未保存的进度将丢失",
      async function() {
        try {
          const overlay = document.getElementById("loginOverlay");
          if (overlay) {
              HtmlUtils.setTrustedHtml(overlay,
                '<div class="shutdown-screen">' +
                '<div class="shutdown-icon">\u23f3</div>' +
                '<h2>正在关闭服务...</h2>' +
                '<p class="shutdown-step pending" id="shutdownStep1">\u23f3 正在发送关闭指令...</p>' +
                '<p class="shutdown-step pending" id="shutdownStep2" style="display:none;">\u23f3 验证服务已停止...</p>' +
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
              step1.textContent = "\u23f3 正在发送关闭指令 (第" + attempt + "/" + maxRetries + "次)...";
            }

            try {
              const controller = new AbortController();
              const timeoutId = setTimeout(function() { controller.abort(); }, 15000);

              const resp = await fetch(App.API + "/admin/shutdown", {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "X-Shutdown-Secret": App.SHUTDOWN_SECRET || ""
                },
                signal: controller.signal
              });

              clearTimeout(timeoutId);
              if (!resp.ok) {
                var errBody = await resp.json().catch(function() { return {}; });
                throw new Error(errBody.detail || "HTTP " + resp.status);
              }
              await resp.json();
              backendSuccess = true;
              lastError = null;

              if (step1) {
                step1.textContent = "\u2713 服务已接收关闭指令 (第" + attempt + "次尝试成功)";
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
                  step1.textContent = "\u2713 服务已接收关闭指令 (网络断开确认)";
                  step1.classList.remove("pending");
                  step1.classList.add("done");
                }
                break;
              }

              backendSuccess = false;

              if (attempt < maxRetries) {
                if (step1) {
                  step1.textContent = "\u26a0\ufe0f 第" + attempt + "次失败，2秒后重试...";
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
                  step1.textContent = "\u2717 无法连接服务 (" + maxRetries + "次尝试均失败)";
                  step1.classList.add("error");
                }
              }
            }
          }

          if (backendSuccess && step2) {
            step2.style.display = "block";
            step2.textContent = "\u23f3 验证服务已停止...";

            let serverStopped = false;
            for (let i = 0; i < 15; i++) {
              await new Promise(function(r) { setTimeout(r, 500); });

              try {
                await fetch(App.API + "/health", { cache: 'no-store' });
              } catch (_err) {
                serverStopped = true;
                break;
              }
            }

            if (serverStopped) {
              step2.textContent = "\u2713 服务已确认停止";
              step2.classList.remove("pending");
              step2.classList.add("done");
            } else {
              step2.textContent = "\u26a0\ufe0f 服务可能仍在运行（超时未停止）";
              step2.classList.remove("pending");
              step2.classList.add("error");
            }
          }

          await new Promise(function(r) { setTimeout(r, 600); });

          if (overlay) {
            const resultIcon = backendSuccess ? "\u2705" : "\ud83d\udf36";
            const resultTitle = backendSuccess ? "服务已关闭" : "服务关闭未完全成功";

            let statusHtml = "";
            if (backendSuccess) {
              statusHtml = "\u2705 服务已停止<br>";
            } else {
              statusHtml = "\u274c 服务未能自动关闭<br>";
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

  App.openAdminPanel = function() {
    window.open('/admin.html', '_blank');
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

  App._showOfflineScreen = function() {
    var existing = document.getElementById("offlineOverlay");
    if (existing) return;
    var overlay = document.createElement("div");
    overlay.id = "offlineOverlay";
    overlay.style.cssText = "position:fixed;inset:0;background:rgba(10,10,18,0.97);z-index:99998;display:flex;align-items:center;justify-content:center;flex-direction:column;";
    var box = document.createElement("div");
    box.className = "login-box";
    var icon = document.createElement("div");
    icon.style.cssText = "text-align:center;font-size:48px;margin-bottom:16px;";
    icon.textContent = "\u26a0\ufe0f";
    box.appendChild(icon);
    var title = document.createElement("h3");
    title.style.cssText = "text-align:center;color:#ef5350;";
    title.textContent = "\u670d\u52a1\u672a\u8fd0\u884c";
    box.appendChild(title);
    var desc = document.createElement("p");
    desc.style.cssText = "text-align:center;color:#a0a0b0;margin-top:12px;";
    desc.textContent = "\u540e\u7aef\u670d\u52a1\u5f53\u524d\u4e0d\u53ef\u7528\uff0c\u8bf7\u8fd0\u884c python start.py \u542f\u52a8\u670d\u52a1\u540e\u5237\u65b0\u9875\u9762";
    box.appendChild(desc);
    var btn = document.createElement("button");
    btn.style.cssText = "margin-top:16px;width:100%;";
    btn.textContent = "\ud83d\udd04 \u5237\u65b0\u91cd\u8bd5";
    btn.onclick = function() { window.location.reload(); };
    box.appendChild(btn);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
  };

  let _pollErrorCount = 0;
  var _pageVisible = true;

  document.addEventListener("visibilitychange", function() {
    _pageVisible = !document.hidden;
    if (_pageVisible && App.playerId) {
      App.fetchState().then(function(data) { if (data) App.updateUI(data); }).catch(function() {});
    }
  });

  document.addEventListener("DOMContentLoaded", function() {
    window.addEventListener("pageshow", function(event) {
      if (event.persisted) {
        var co = document.getElementById("connectingOverlay");
        if (co) co.style.display = "flex";
        fetch("/api/health", { cache: "no-store" })
          .then(function() {
            if (co) co.style.display = "none";
          })
          .catch(function() {
            if (co) co.style.display = "none";
            App._showOfflineScreen();
          });
      }
    });

    window.addEventListener("offline", function() {
      App._showOfflineScreen();
    });

    fetch("/api/health", { cache: "no-store" })
      .then(function(r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function(data) {
        var co = document.getElementById("connectingOverlay");
        if (co) co.style.display = "none";
        try {
          var cfg = JSON.parse(localStorage.getItem("lp_config") || "{}");
          if (cfg.shutdownSecret) {
            App.SHUTDOWN_SECRET = cfg.shutdownSecret;
          }
        } catch(_e) {}
      })
      .catch(function() {
        var co = document.getElementById("connectingOverlay");
        if (co) co.style.display = "none";
        App._showOfflineScreen();
      });

    var sel = document.getElementById("npcSelect");
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

    var bountyExpandBtn = document.getElementById("bountyExpandBtn");
    var bountyOverlay = document.getElementById("bountyOverlay");
    var bountyOverlayClose = document.getElementById("bountyOverlayClose");
    if (bountyExpandBtn && bountyOverlay) {
      bountyExpandBtn.addEventListener("click", function() {
        var isVisible = bountyOverlay.classList.contains("visible");
        if (isVisible) {
          bountyOverlay.classList.remove("visible");
          bountyExpandBtn.textContent = "展开";
        } else {
          bountyOverlay.classList.add("visible");
          bountyExpandBtn.textContent = "收起";
        }
      });
    }
    if (bountyOverlayClose && bountyOverlay) {
      bountyOverlayClose.addEventListener("click", function() {
        bountyOverlay.classList.remove("visible");
        if (bountyExpandBtn) bountyExpandBtn.textContent = "展开";
      });
    }

    var cancelStreamBtn = document.getElementById("cancelStreamBtn");
    if (cancelStreamBtn) {
      cancelStreamBtn.addEventListener("click", function() {
        App.cancelTalkStream();
      });
    }

    var watchNpcBtn = document.createElement("button");
    watchNpcBtn.id = "watchNpcBtn";
    watchNpcBtn.textContent = "\u89c2\u5bdf\u884c\u52a8";
    watchNpcBtn.addEventListener("click", function() {
      if (App.selectedNpcId) {
        App.watchNpcAct(App.selectedNpcId);
      } else {
        App.addMsg("system", "\u8bf7\u5148\u9009\u62e9\u4e00\u4e2aNPC");
      }
    });
    var inputBar = document.querySelector(".input-bar");
    if (inputBar) inputBar.appendChild(watchNpcBtn);
  });

})(window.App);
