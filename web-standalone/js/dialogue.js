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

    input.value = "";
    App.addMsg("player", msg);

    App.isStreaming = true;
    var btn = document.getElementById("talkBtn");
    if (btn) btn.disabled = true;

    var npcName = App.npcsHere.find(function(n) { return n.id === App.selectedNpcId; });
    npcName = npcName ? npcName.name : "NPC";

    var msgDiv = App.addMsg("npc", "...", npcName);
    var textEl = msgDiv.querySelector(".msg-text");
    var visibleText = "";

    try {
      var reader = await App.talkStream(App.selectedNpcId, msg);
      var decoder = new TextDecoder();
      var buf = "";

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
            var d = JSON.parse(line.slice(6));
            if (d.chunk) {
              visibleText += d.chunk;
              textEl.textContent = visibleText;
              App.scrollToBottom();
            }
            if (d.done) {
              if (d.player) App.fetchState().then(App.updateUI);
              break;
            }
          } catch (e) { /* 忽略解析错误 */ }
        }
      }
    } catch (e) {
      textEl.textContent = "\u3010\u5bf9\u8bdd\u4e2d\u65ad\uff0c\u8bf7\u91cd\u8bd5\u3011";
    }

    App.isStreaming = false;
    if (btn) btn.disabled = false;
    App.scrollToBottom();
  };

})(window.App);