window.App = window.App || {};

(function(App) {
  "use strict";

  var _evoAbortController = null;

  App.startEvolution = function(pid, name, gender, permadeath) {
    var evoOverlay = document.getElementById("evolutionOverlay");
    var loginOverlay = document.getElementById("loginOverlay");
    if (loginOverlay) loginOverlay.style.display = "none";
    if (evoOverlay) evoOverlay.style.display = "flex";

    var log = document.getElementById("evolutionLog");
    if (log) log.replaceChildren();

    var enterBtn = document.getElementById("evoEnterBtn");
    if (enterBtn) { enterBtn.disabled = true; enterBtn.textContent = "演进中..."; }

    _updateProgress(0, 60);

    App._evoPlayerId = pid;
    App._evoPlayerName = name;
    App._evoDone = false;

    _evoAbortController = new AbortController();
    var controller = _evoAbortController;
    var connectTimeout = setTimeout(function() { controller.abort(); }, 30000);

    fetch(App.API + "/evolution/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        player_id: pid,
        display_name: name,
        gender: gender,
        permadeath: permadeath
      }),
      signal: controller.signal
    }).then(function(res) {
      clearTimeout(connectTimeout);
      if (!res.ok) throw new Error("演进启动失败: " + res.status);
      _readSSEStream(res.body.getReader(), pid, name);
    }).catch(function(err) {
      clearTimeout(connectTimeout);
      console.error("[Evolution] start failed:", err);
      _fallbackCreatePlayer(pid, name, gender, permadeath);
    });
  };

  function _readSSEStream(reader, pid, name) {
    var decoder = new TextDecoder();
    var buffer = "";

    function read() {
      reader.read().then(function(result) {
        if (result.done) {
          if (!App._evoDone) {
            _onEvolutionDone(pid, name, { type: "done" });
          }
          return;
        }
        buffer += decoder.decode(result.value, { stream: true });
        var lines = buffer.split("\n");
        buffer = lines.pop();

        for (var i = 0; i < lines.length; i++) {
          var line = lines[i].trim();
          if (!line.startsWith("data: ")) continue;
          try {
            var event = JSON.parse(line.substring(6));
            _handleEvent(event, pid, name);
          } catch (_e) {}
        }

        read();
      }).catch(function(err) {
        console.error("[Evolution] stream error:", err);
        var statusText = document.getElementById("evoStatusText");
        var enterBtn = document.getElementById("evoEnterBtn");
        if (statusText) statusText.textContent = "连接中断，可直接进入";
        if (enterBtn) { enterBtn.disabled = false; enterBtn.textContent = "踏入江湖 ▶"; }
        App._evoDone = true;
      });
    }

    read();
  }

  function _handleEvent(event, pid, name) {
    var log = document.getElementById("evolutionLog");
    if (!log) return;

    switch (event.type) {
      case "tick":
        _appendLog(log, "evo-tick", event.text);
        if (event.shichen) {
          var shichenLabel = document.getElementById("evoShichenLabel");
          if (shichenLabel) shichenLabel.textContent = event.shichen;
        }
        break;
      case "dialogue":
        _appendLog(log, "evo-dialogue", event.speaker_a + "对" + event.speaker_b + "：「" + event.line + "」");
        break;
      case "event":
        _appendLog(log, "evo-event", "📜 " + event.title + "——" + (event.desc || ""));
        break;
      case "player_action":
        _appendLog(log, "evo-player", "🏔️ " + event.text);
        break;
      case "progress":
        _updateProgress(event.current, event.total);
        break;
      case "done":
        _onEvolutionDone(pid, name, event);
        return;
      case "cancelled":
        _onEvolutionCancelled(pid, name, event);
        return;
    }

    log.scrollTop = log.scrollHeight;
  }

  function _appendLog(log, className, text) {
    var div = document.createElement("div");
    div.className = className;
    div.textContent = text;
    log.appendChild(div);
    while (log.children.length > 500) {
      log.removeChild(log.firstChild);
    }
  }

  function _updateProgress(current, total) {
    var fill = document.getElementById("evoProgressFill");
    var dayLabel = document.getElementById("evoDayLabel");
    if (fill) fill.style.width = (current / total * 100) + "%";
    if (dayLabel) dayLabel.textContent = "第" + Math.floor(current / 12 + 1) + "日";
  }

  function _onEvolutionDone(pid, name, event) {
    var statusText = document.getElementById("evoStatusText");
    var enterBtn = document.getElementById("evoEnterBtn");
    if (statusText) statusText.textContent = "世界演进完成！";
    if (enterBtn) { enterBtn.disabled = false; enterBtn.textContent = "踏入江湖 ▶"; }

    App._evoPlayerId = pid;
    App._evoPlayerName = name;
    App._evoDone = true;
  }

  function _onEvolutionCancelled(pid, name, event) {
    var statusText = document.getElementById("evoStatusText");
    var enterBtn = document.getElementById("evoEnterBtn");
    if (statusText) statusText.textContent = "演进已提前结束";
    if (enterBtn) { enterBtn.disabled = false; enterBtn.textContent = "踏入江湖 ▶"; }

    App._evoPlayerId = pid;
    App._evoPlayerName = name;
    App._evoDone = true;
  }

  App.endEvolution = function() {
    if (!App._evoDone && App._evoPlayerId) {
      App.backendPost("/api/evolution/cancel", { player_id: App._evoPlayerId }).catch(function() {});
    }

    if (_evoAbortController) {
      _evoAbortController.abort();
      _evoAbortController = null;
    }

    var pid = App._evoPlayerId;
    var name = App._evoPlayerName;

    if (!pid) return;

    App.backendGet("/api/evolution/result/" + pid).then(function(data) {
      var evoOverlay = document.getElementById("evolutionOverlay");
      if (evoOverlay) evoOverlay.style.display = "none";
      App._evoPlayerId = null;
      App._evoPlayerName = null;
      App._evoDone = false;
      App.onGameReady(data, pid, name || data.display_name);
    }).catch(function(err) {
      console.error("[Evolution] get result failed:", err);
      App.loadPlayer(pid).then(function(data) {
        var evoOverlay = document.getElementById("evolutionOverlay");
        if (evoOverlay) evoOverlay.style.display = "none";
        App._evoPlayerId = null;
        App._evoPlayerName = null;
        App._evoDone = false;
        App.onGameReady(data, pid, name || data.display_name);
      }).catch(function(e2) {
        console.error("[Evolution] fallback load failed:", e2);
      });
    });
  };

  function _fallbackCreatePlayer(pid, name, gender, permadeath) {
    App.backendPost("/api/hello", {
      player_id: pid,
      display_name: name,
      gender: gender,
      permadeath: permadeath
    }).then(function(data) {
      var evoOverlay = document.getElementById("evolutionOverlay");
      if (evoOverlay) evoOverlay.style.display = "none";
      App._evoPlayerId = null;
      App._evoPlayerName = null;
      App._evoDone = false;
      App.onGameReady(data, pid, name || data.display_name);
    }).catch(function(err) {
      var evoOverlay = document.getElementById("evolutionOverlay");
      if (evoOverlay) evoOverlay.style.display = "none";
      App.addMsg("system", "创建角色失败: " + err.message);
    });
  }

})(window.App);
