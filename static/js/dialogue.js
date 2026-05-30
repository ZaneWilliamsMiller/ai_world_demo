window.App = window.App || {};

(function(App) {
  "use strict";

  App.doTalk = async function(autoMsg) {
    if (App.isStreaming) return;

    var input = document.getElementById("msgInput");
    var msg = autoMsg || (input ? input.value.trim() : "");
    if (!msg || !App.selectedNpcId || !App.playerId) return;

    if (msg.length > 2000) {
      App.addMsg("system", "消息过长，请控制在2000字以内");
      return;
    }

    if (input && !autoMsg) input.value = "";
    App.addMsg("player", msg);

    App.isStreaming = true;
    var btn = document.getElementById("talkBtn");
    var cancelBtn = document.getElementById("cancelStreamBtn");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "等待中...";
      btn.classList.add("streaming");
    }
    if (cancelBtn) cancelBtn.classList.add("visible");

    var npcName = App.npcsHere.find(function(n) { return n.id === App.selectedNpcId; });
    npcName = npcName ? npcName.name : "NPC";

    var reader = null;
    var textEl = null;
    var visibleText = "";
    var _streamTimeout = null;

    function _resetStreamState() {
      App.isStreaming = false;
      if (btn) {
        btn.disabled = false;
        btn.textContent = "发送";
        btn.classList.remove("streaming");
      }
      if (cancelBtn) cancelBtn.classList.remove("visible");
      if (_streamTimeout) clearTimeout(_streamTimeout);
      if (textEl) textEl.textContent = visibleText;
      App.scrollToBottom();
    }

    try {
      reader = await App.talkStream(App.selectedNpcId, msg);

      var msgDiv = App.addMsg("npc", {speaker: npcName, text: "..."}, false);
      textEl = msgDiv.querySelector(".msg-text");

      var decoder = new TextDecoder();
      var buf = "";
      var receivedDone = false;
      var _rafPending = false;

      _streamTimeout = setTimeout(function() {
        visibleText += "\n[对话超时，回复可能不完整]";
        _resetStreamState();
        reader && reader.cancel && reader.cancel().catch(function(){});
      }, 120000);

      while (true) {
        var chunk = await reader.read();
        if (chunk.done) break;
        buf += decoder.decode(chunk.value, { stream: true });
        var lines = buf.split("\n");
        buf = lines.pop();
        for (var i = 0; i < lines.length; i++) {
          var line = lines[i];
          if (line.indexOf("data: ") !== 0) continue;
          try {
            var d = JSON.parse(line.slice(6).trim());
            if (d.chunk) {
              visibleText += d.chunk;
              if (!_rafPending) {
                _rafPending = true;
                requestAnimationFrame(function() {
                  textEl.textContent = visibleText;
                  App.scrollToBottom();
                  _rafPending = false;
                });
              }
            }
            if (d.error) {
              visibleText += "\n[错误] " + d.error;
              textEl.textContent = visibleText;
              if (d.fatal) break;
            }
            if (d.done) {
              receivedDone = true;
              if (d.player) {
                var stateData = { player: d.player };
                if (d.npcs_here) stateData.npcs_here = d.npcs_here;
                App.updateUI(stateData);
              }
              if (!d.player) {
                App.fetchState().then(function(data) { if (data) App.updateUI(data); }).catch(function() {});
              }
              break;
            }
          } catch (_e) { /* 忽略解析错误 */ }
        }
      }

      if (buf.trim()) {
        var lastLine = buf.trim();
        if (lastLine.indexOf("data: ") === 0) {
          try {
            var lastD = JSON.parse(lastLine.slice(6).trim());
            if (lastD.chunk) {
              visibleText += lastD.chunk;
              textEl.textContent = visibleText;
              App.scrollToBottom();
            }
          } catch (_e) { /* 忽略 */ }
        }
      }

      if (!receivedDone) {
        visibleText += "\n[连接中断，回复可能不完整]";
        textEl.textContent = visibleText;
        App.fetchState().then(function(data) { if (data) App.updateUI(data); }).catch(function() {});
      }
    } catch (e) {
      var errorMsg = e.message || "对话中断，请重试";
      var lastMsg = document.querySelector(".msg:last-child");
      var msgTextEl = lastMsg ? lastMsg.querySelector(".msg-text") : null;
      if (lastMsg && lastMsg.classList.contains("npc") && msgTextEl && msgTextEl.textContent === "...") {
        lastMsg.remove();
      }
      App.addMsg("system", errorMsg);
    } finally {
      if (reader) try { reader.releaseLock(); } catch (_e) { /* already released */ }
      App._streamAbortController = null;
    }

    _resetStreamState();
  };

})(window.App);
