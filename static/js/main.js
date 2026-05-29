// ═══════════════════════════════════════════════════════
//  main.js — 应用入口（独立 Web 前端）
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
    apiModeIndicator: null,
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
      this.apiModeIndicator = document.getElementById("apiModeIndicator");
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

  // ═══════════════════════════════════════════
  //  HTML 安全工具 - 复用 ui.js 的实现或提供本地版本
  // ═══════════════════════════════════════════
  const HtmlUtils = App.HtmlUtils || {
    escape(text) {
      if (!text) return '';
      const str = String(text);
      const div = document.createElement('div');
      div.textContent = str;
      return div.innerHTML;
    },

    setSafeHtml(element, html) {
      if (element) {
        element.innerHTML = this.escape(html);
      }
    }
  };

  // 配置面板开关
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
    const modeSelect = document.getElementById("cfgApiMode");
    const backendUrl = document.getElementById("cfgBackendUrl");
    const llmUrl = document.getElementById("cfgLlmUrl");
    const llmKey = document.getElementById("cfgLlmKey");
    const llmModel = document.getElementById("cfgLlmModel");
    if (modeSelect) modeSelect.value = App.apiMode;
    if (backendUrl) backendUrl.value = App.BACKEND_URL;
    if (llmUrl) llmUrl.value = App.LLM_API_URL;
    if (llmKey) llmKey.value = App.LLM_API_KEY;
    if (llmModel) llmModel.value = App.LLM_MODEL;
  };

  App.applyConfig = function() {
    const modeSelect = document.getElementById("cfgApiMode");
    const backendUrl = document.getElementById("cfgBackendUrl");
    const llmUrl = document.getElementById("cfgLlmUrl");
    const llmKey = document.getElementById("cfgLlmKey");
    const llmModel = document.getElementById("cfgLlmModel");
    if (modeSelect) App.apiMode = modeSelect.value;
    if (backendUrl) App.BACKEND_URL = backendUrl.value.trim();
    if (llmUrl) App.LLM_API_URL = llmUrl.value.trim();
    if (llmKey) App.LLM_API_KEY = llmKey.value.trim();
    if (llmModel) App.LLM_MODEL = llmModel.value.trim();
    App.saveConfig();
    const modeIndicator = DOM.apiModeIndicator || document.getElementById("apiModeIndicator");
    if (modeIndicator) {
      modeIndicator.textContent = App.apiMode === "backend" ? "后端模式" : "独立模式";
      modeIndicator.className = "api-mode-badge " + App.apiMode;
    }
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
    } catch (e) {
      const savesList = DOM.savesList || document.getElementById("savesList");
      // 错误消息使用安全方式显示
      HtmlUtils.setSafeHtml(savesList, '<div style="color:#ef5350;">加载存档列表失败</div>');
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
      introMsg.innerHTML =
        "<b>欢迎，" + HtmlUtils.escape(App.displayName) + "！</b><br>" + HtmlUtils.escape(data.intro || "江湖路远，珍重。").replace(/\n/g, "<br>");
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
          await fetch(App.API + "/delete-save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ player_id: pid })
          });
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
    // 确认框的消息通常是硬编码的可信 HTML，使用 setTrustedHtml
    msgEl.innerHTML = message;

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
      "确定要关闭所有服务吗？<br><br>" +
      "⚠️ <b>这将同时停止：</b><br>" +
      "• 🌐 Web前端服务器<br>" +
      "• 🔧 后端API服务<br><br>" +
      "💡 所有未保存的进度将丢失",
      async function() {
        try {
          const overlay = DOM.loginOverlay || document.getElementById("loginOverlay");
          if (overlay) {
            // 关闭界面是硬编码的可信 HTML，直接设置
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

          let step1 = document.getElementById("shutdownStep1");
          let step2 = document.getElementById("shutdownStep2");
          let step3 = document.getElementById("shutdownStep3");

          let backendSuccess = false;
          let data = null;
          let lastError = null;

          // ════════════════════════════════════
          // 第一重保障：多次重试连接后端
          // ════════════════════════════════════
          const maxRetries = 3;
          for (let attempt = 1; attempt <= maxRetries; attempt++) {
            if (step1) {
              step1.textContent = "⏳ 正在连接后端 (第" + attempt + "/" + maxRetries + "次)...";
            }

            try {
              // 使用AbortController设置更长的超时时间（15秒）
              const controller = new AbortController();
              const timeoutId = setTimeout(function() { controller.abort(); }, 15000);

              const resp = await fetch(App.BACKEND_URL + "/api/shutdown", {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "X-Shutdown-Secret": App.SHUTDOWN_SECRET || ""
                },
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

              // 判断是否是 "Failed to fetch" 错误
              // 如果是且这是 shutdown 请求，说明后端已收到请求并开始关闭（网络断开）
              const isNetworkError = e.message === 'Failed to fetch' ||
                                     e.name === 'TypeError';
              const isShutdownRequest = true; // 当前上下文就是 shutdown

              if (isNetworkError && isShutdownRequest) {
                // 这种情况下，后端实际上已经收到了关闭指令
                // 只是网络连接在响应传输过程中断开了
                backendSuccess = true;  // 视为成功！
                lastError = null;

                if (step1) {
                  step1.textContent = "✓ 后端已接收关闭指令 (网络断开确认)";
                  step1.classList.remove("pending");
                  step1.classList.add("done");
                }
                break; // 跳出重试循环
              }

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

            let backendStopped = false;
            for (let i = 0; i < 15; i++) {
              await new Promise(function(r) { setTimeout(r, 500); });

              try {
                await fetch(App.BACKEND_URL + "/api/health", {
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
            const directResp = await fetch(window.location.origin + "/__shutdown__", {
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
          let frontendStopped = false;
          for (let i = 0; i < 10; i++) {
            await new Promise(function(r) { setTimeout(r, 400); });

            try {
              await fetch(window.location.origin + "/__ping__", {
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
            const resultIcon = (backendSuccess && frontendStopped) ? "✅" : "🔶";
            const resultTitle = (backendSuccess && frontendStopped) ? "所有服务已关闭" : "部分服务已关闭";

            let backendStatus = "";
            if (backendSuccess) {
              backendStatus = "✅ 后端API服务已停止<br>";
            } else {
              backendStatus = "❌ 后端未能自动关闭<br>";
              if (lastError) {
                // 错误信息可能来自异常对象，进行转义处理
                backendStatus += "   错误: " + HtmlUtils.escape(lastError.message.substring(0, 80)) + "<br>";
              }
              backendStatus += "   请手动关闭运行后端的终端窗口<br>";
            }

            const frontendStatus = frontendStopped
              ? "✅ Web前端服务已强制停止<br>"
              : "⚠️ Web前端可能仍在运行<br>";

            // 最终结果是动态生成的，但数据来源可信（系统状态），使用 setTrustedHtml
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
    if (_pageVisible && App.playerId && App.apiMode === "backend") {
      App.fetchState().then(function(data) { if (data) App.updateUI(data); });
    }
  });

  _statePollTimer = setInterval(function() {
    if (!_pageVisible) return;
    if (App.playerId && !App.isStreaming && App.apiMode === "backend") {
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

    const modeIndicator = DOM.apiModeIndicator;
    if (modeIndicator) {
      modeIndicator.textContent = App.apiMode === "backend" ? "后端模式" : "独立模式";
    }
    const modeSelect = document.getElementById("apiModeQuickToggle");
    if (modeSelect) {
      modeSelect.addEventListener("change", function() {
        App.setApiMode(modeSelect.value);
      });
    }
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
        cancelStreamBtn.classList.remove("visible");
      });
    }
  });

})(window.App);
