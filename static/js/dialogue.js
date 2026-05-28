// ═══════════════════════════════════════════════════════
//  dialogue.js — NPC 对话流程
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  /**
   * 发起流式对话。从 state 读取 selectedNpcId & msgInput，
   * 通过 SSE 逐字渲染，完成后自动拉取最新状态。
   */
  App.doTalk = async function() {
    if (App.isStreaming) return;

    var input = document.getElementById("msgInput");
    var msg   = input.value.trim();
    if (!msg || !App.selectedNpcId || !App.playerId) return;

    if (msg.length > 2000) {
      App.addMsg("system", "消息过长，请控制在2000字以内");
      return;
    }

    input.value = "";
    App.addMsg("player", msg);

    App.isStreaming = true;
    var btn = document.getElementById("talkBtn");
    if (btn) btn.disabled = true;

    var npcName = App.npcsHere.find(function(n) { return n.id === App.selectedNpcId; });
    npcName = npcName ? npcName.name : "NPC";

    try {
      var reader = await App.talkStream(App.selectedNpcId, msg);
      
      var msgDiv = App.addMsg("npc", {speaker: npcName, text: "..."}, false);
      var textEl = msgDiv.querySelector(".msg-text");
      var visibleText = "";
      
      var decoder = new TextDecoder();
      var buf = "";
      var receivedDone = false;

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
              textEl.textContent = visibleText;
              App.scrollToBottom();
            }
            if (d.error) {
              visibleText += "\n[错误] " + d.error;
              textEl.textContent = visibleText;
              if (d.fatal) break;
            }
            if (d.done) {
              receivedDone = true;
              if (d.player) {
                var stateData = d.player;
                if (d.npcs_here) stateData = { player: d.player, npcs_here: d.npcs_here };
                App.updateUI(stateData);
              }
              if (!d.player) {
                App.fetchState().then(function(data) { if (data) App.updateUI(data); });
              }
              break;
            }
          } catch (e) { /* 忽略解析错误 */ }
        }
      }

      // 处理流结束后的残留数据
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
          } catch (e) { /* 忽略 */ }
        }
      }

      reader.releaseLock();

      if (!receivedDone) {
        visibleText += "\n[连接中断，回复可能不完整]";
        textEl.textContent = visibleText;
        App.fetchState().then(function(data) { if (data) App.updateUI(data); });
      }
    } catch (e) {
      // 游戏内情境提示（如身陷险局）作为系统消息显示
      var errorMsg = e.message || "对话中断，请重试";
      // 移除之前创建的空NPC消息
      var lastMsg = document.querySelector(".msg:last-child");
      if (lastMsg && lastMsg.classList.contains("npc") && lastMsg.textContent === "...") {
        lastMsg.remove();
      }
      App.addMsg("system", errorMsg);
    }

    App.isStreaming = false;
    if (btn) btn.disabled = false;
    App.scrollToBottom();
  };

})(window.App);