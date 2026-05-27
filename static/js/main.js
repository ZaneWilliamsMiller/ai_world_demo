// ═══════════════════════════════════════════════════════
//  main.js — 应用入口（独立 Web 前端）
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  // 配置面板开关
  App.toggleConfigPanel = function() {
    var overlay = document.getElementById("configOverlay");
    var panel = document.getElementById("configPanel");
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
    var modeSelect = document.getElementById("cfgApiMode");
    var backendUrl = document.getElementById("cfgBackendUrl");
    var llmUrl = document.getElementById("cfgLlmUrl");
    var llmKey = document.getElementById("cfgLlmKey");
    var llmModel = document.getElementById("cfgLlmModel");
    if (modeSelect) modeSelect.value = App.apiMode;
    if (backendUrl) backendUrl.value = App.BACKEND_URL;
    if (llmUrl) llmUrl.value = App.LLM_API_URL;
    if (llmKey) llmKey.value = App.LLM_API_KEY;
    if (llmModel) llmModel.value = App.LLM_MODEL;
  };

  App.applyConfig = function() {
    var modeSelect = document.getElementById("cfgApiMode");
    var backendUrl = document.getElementById("cfgBackendUrl");
    var llmUrl = document.getElementById("cfgLlmUrl");
    var llmKey = document.getElementById("cfgLlmKey");
    var llmModel = document.getElementById("cfgLlmModel");
    if (modeSelect) App.apiMode = modeSelect.value;
    if (backendUrl) App.BACKEND_URL = backendUrl.value.trim();
    if (llmUrl) App.LLM_API_URL = llmUrl.value.trim();
    if (llmKey) App.LLM_API_KEY = llmKey.value.trim();
    if (llmModel) App.LLM_MODEL = llmModel.value.trim();
    App.saveConfig();
    var modeIndicator = document.getElementById("apiModeIndicator");
    if (modeIndicator) {
      modeIndicator.textContent = App.apiMode === "backend" ? "后端模式" : "独立模式";
      modeIndicator.className = "api-mode-badge " + App.apiMode;
    }
    App.toggleConfigPanel();
  };

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

    var name   = document.getElementById("inpName").value.trim() || "江湖客";
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
    App.showConfirm(
      "退出游戏",
      "确定要退出游戏吗？<br><br>⚠️ <b>未存档的进度将丢失</b>",
      function() {
        App.playerId = null;
        document.getElementById("mainUI").style.display = "none";
        document.getElementById("topbar").style.display = "none";
        document.getElementById("loginOverlay").style.display = "flex";
      }
    );
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

  App.showConfirm = function(title, message, onConfirm) {
    var overlay = document.getElementById("confirmOverlay");
    var titleEl = document.getElementById("confirmTitle");
    var msgEl = document.getElementById("confirmMessage");
    var okBtn = document.getElementById("confirmOk");
    var cancelBtn = document.getElementById("confirmCancel");

    titleEl.textContent = title;
    msgEl.innerHTML = message;

    overlay.classList.add("show");

    function cleanup() {
      overlay.classList.remove("show");
      okBtn.removeEventListener("click", handleOk);
      cancelBtn.removeEventListener("click", handleCancel);
    }

    function handleOk(e) {
      e.preventDefault();
      e.stopPropagation();
      cleanup();
      if (typeof onConfirm === "function") {
        onConfirm();
      }
    }

    function handleCancel(e) {
      e.preventDefault();
      e.stopPropagation();
      cleanup();
    }

    okBtn.addEventListener("click", handleOk);
    cancelBtn.addEventListener("click", handleCancel);

    overlay.addEventListener("click", function onOverlayClick(e) {
      if (e.target === overlay) {
        cleanup();
        overlay.removeEventListener("click", onOverlayClick);
      }
    });

    document.addEventListener("keydown", function onEsc(e) {
      if (e.key === "Escape") {
        cleanup();
        document.removeEventListener("keydown", onEsc);
      }
    });
  };

  App.shutdownAll = function() {
    App.showConfirm(
      "关闭服务",
      "确定要关闭所有服务吗？<br><br>" +
      "⚠️ <b>这将同时停止：</b><br>" +
      "• 🌐 Web前端服务器 (端口 8766)<br>" +
      "• 🔧 后端API服务 (端口 8765)<br><br>" +
      "💡 所有未保存的进度将丢失",
      async function() {
        try {
          var overlay = document.getElementById("loginOverlay");
          if (overlay) {
            overlay.innerHTML =
              '<div class="shutdown-screen">' +
              '<div class="shutdown-icon">⏳</div>' +
              '<h2>正在关闭所有服务...</h2>' +
              '<p class="shutdown-step pending" id="shutdownStep1">⏳ 正在连接后端 (第1/3次)...</p>' +
              '<p class="shutdown-step pending" id="shutdownStep2" style="display:none;">⏳ 验证后端已停止...</p>' +
              '<p class="shutdown-step pending" id="shutdownStep3" style="display:none;">⏳ 关闭前端服务器...</p>' +
              '</div>';
            overlay.style.display = 'flex';
          }

          var step1 = document.getElementById("shutdownStep1");
          var step2 = document.getElementById("shutdownStep2");
          var step3 = document.getElementById("shutdownStep3");

          var backendSuccess = false;
          var data = null;
          var lastError = null;

          // ════════════════════════════════════
          // 第一重保障：多次重试连接后端
          // ════════════════════════════════════
          var maxRetries = 3;
          for (var attempt = 1; attempt <= maxRetries; attempt++) {
            if (step1) {
              step1.textContent = "⏳ 正在连接后端 (第" + attempt + "/" + maxRetries + "次)...";
            }

            try {
              // 使用AbortController设置更长的超时时间（10秒）
              var controller = new AbortController();
              var timeoutId = setTimeout(function() { controller.abort(); }, 10000);

              var resp = await fetch(App.BACKEND_URL + "/api/shutdown", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                signal: controller.signal
              });

              clearTimeout(timeoutId);
              data = await resp.json();
              backendSuccess = true;
              lastError = null;

              if (step1) {
                step1.textContent = "✓ 后端已接收关闭指令 (第" + attempt + "次尝试成功)";
                step1.classList.remove("pending");
                step1.classList.add("done");
              }
              break; // 成功，跳出循环

            } catch (e) {
              lastError = e;
              backendSuccess = false;

              if (attempt < maxRetries) {
                // 还有重试机会，等待后重试
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
                // 所有重试都失败了
                if (step1) {
                  step1.textContent = "✗ 无法连接后端 (" + maxRetries + "次尝试均失败)";
                  step1.classList.add("error");
                }
              }
            }
          }

          // ════════════════════════════════════
          // 第二重保障：验证后端确实停止
          // ════════════════════════════════════
          if (backendSuccess && step2) {
            step2.style.display = "block";
            step2.textContent = "⏳ 验证后端已停止...";

            var backendStopped = false;
            for (var i = 0; i < 15; i++) {
              await new Promise(function(r) { setTimeout(r, 500); });

              try {
                var checkBackendResp = await fetch(App.BACKEND_URL + "/api/health", {
                  mode: 'no-cors',
                  cache: 'no-store'
                });
              } catch (err) {
                backendStopped = true;
                break;
              }
            }

            if (backendStopped) {
              step2.textContent = "✓ 后端服务已确认停止";
              step2.classList.remove("pending");
              step2.classList.add("done");
            } else {
              step2.textContent = "⚠️ 后端可能仍在运行（超时未停止）";
              step2.classList.remove("pending");
              step2.classList.add("error");
            }
          }

          await new Promise(function(r) { setTimeout(r, 500); });

          // ════════════════════════════════════
          // 第三重：关闭前端服务器
          // ════════════════════════════════════
          if (step3) {
            step3.style.display = "block";
            step3.textContent = "⏳ 关闭前端服务器...";
          }

          try {
            var directResp = await fetch(window.location.origin + "/__shutdown__", {
              method: "GET"
            });

            if (step3) {
              step3.textContent = "✓ 前端已接收关闭指令";
              step3.classList.remove("pending");
              step3.classList.add("done");
            }
          } catch (err) {
            if (step3) {
              step3.textContent = "⚠️ 前端关闭指令发送异常";
              step3.classList.remove("pending");
              step3.classList.add("error");
            }
          }

          // 等待前端实际停止
          var frontendStopped = false;
          for (var i = 0; i < 10; i++) {
            await new Promise(function(r) { setTimeout(r, 400); });

            try {
              var checkFrontendResp = await fetch(window.location.origin + "/__ping__", {
                mode: 'no-cors',
                cache: 'no-store'
              });
            } catch (err) {
              frontendStopped = true;
              break;
            }
          }

          // ════════════════════════════════════
          // 显示最终结果
          // ════════════════════════════════════
          await new Promise(function(r) { setTimeout(r, 600); });

          if (overlay) {
            var resultIcon = (backendSuccess && frontendStopped) ? "✅" : "🔶";
            var resultTitle = (backendSuccess && frontendStopped) ? "所有服务已关闭" : "部分服务已关闭";

            var backendStatus = "";
            if (backendSuccess) {
              backendStatus = "✅ 后端API服务已停止<br>";
            } else {
              backendStatus = "❌ 后端未能自动关闭<br>";
              if (lastError) {
                backendStatus += "   错误: " + lastError.message.substring(0, 80) + "<br>";
              }
              backendStatus += "   请手动关闭运行后端的终端窗口<br>";
            }

            var frontendStatus = frontendStopped
              ? "✅ Web前端服务已强制停止<br>"
              : "⚠️ Web前端可能仍在运行<br>";

            overlay.innerHTML =
              '<div class="shutdown-screen">' +
              '<div class="shutdown-icon">' + resultIcon + '</div>' +
              '<h2>' + resultTitle + '</h2>' +
              '<p style="font-size:16px;line-height:1.8;">' +
              backendStatus +
              frontendStatus +
              '<br><span style="color:#a0a0b0;">' +
              (frontendStopped ? '此页面即将失效<br>' : '') +
              '可重新运行 <code>python start.py</code> 启动服务</span></p>' +
              '</div>';
          }

        } catch (e) {
          console.error("Shutdown error:", e);
          alert("关闭过程中出现错误: " + e.message + "\n\n请手动关闭终端窗口。");
        }
      }
    );
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
    var modeSelect = document.getElementById("apiModeQuickToggle");
    if (modeSelect) {
      modeSelect.addEventListener("change", function() {
        App.setApiMode(modeSelect.value);
      });
    }
    var sel = document.getElementById("npcSelect");
    if (sel) {
      sel.addEventListener("change", function() {
        App.selectedNpcId = sel.value;
      });
    }
  });

})(window.App);
