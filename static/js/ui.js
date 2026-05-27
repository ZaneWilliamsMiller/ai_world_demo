// ═══════════════════════════════════════════════════════
//  ui.js — UI 渲染：HUD、NPC 列表、消息、界门
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  // ═══════════════════════════════════════════
  //  全量 UI 更新（由 API 层或对话流程调用）
  // ═══════════════════════════════════════════

  App.updateUI = function(data) {
    var p = data.player || {};
    App.currentMapId = p.map_id;
    App.npcCatalog  = data.npc_catalog || App.npcCatalog || [];
    App._playerX = p.px;
    App._playerY = p.py;
    // 传递地点坐标（用于地图标签）
    App._mapLocations = data.map_locations || App._mapLocations || {};

    updateTopbar(p);
    App.renderMap(p);
    renderRightPanel(p, data);
    renderNpcBar(data);
    renderPortals(p);
  };

  // ── 顶栏 ──
  function updateTopbar(p) {
    var badge = p.world_is_night
      ? '<span class="badge night">' + p.world_shichen + '\u00b7\u591c</span>'
      : '<span class="badge day">'   + p.world_shichen + '</span>';
    document.getElementById("topbarInfo").innerHTML =
      (p.map_id || "") + " " + badge + " " + (p.weather || "");
  }

  // ── 右栏：状态面板 ──
  function renderRightPanel(p, data) {
    // 时辰 · 天气 · 天数
    document.getElementById("statTime").textContent =
      p.world_shichen || "--";
    document.getElementById("statWeather").textContent =
      p.weather || "--";
    var dayEl = document.getElementById("statDay");
    if (dayEl) dayEl.textContent = p.world_day || 1;

    // 体力
    var v = p.vigor || 0, vm = p.vigor_max || 100;
    document.getElementById("statVigor").textContent = v + "/" + vm;
    document.getElementById("barVigor").style.width =
      (v / vm * 100).toFixed(0) + "%";

    // 心气
    var s = p.spirit || 0, sm = p.spirit_max || 100;
    document.getElementById("statSpirit").textContent = s + "/" + sm;
    document.getElementById("barSpirit").style.width =
      (s / sm * 100).toFixed(0) + "%";

    // 钱银
    document.getElementById("statCoins").textContent =
      p.coins || 0;

    // 背包
    var inv = p.inventory || {};
    var html = "";
    Object.keys(inv).forEach(function(k) {
      html += "<span>" + k + "\u00d7" + inv[k] + "</span>";
    });
    document.getElementById("statInv").innerHTML =
      html || "<span style='color:#555;'>\u8eab\u65e0\u957f\u7269</span>";
  }

  // ── 此地图 NPC 列表 ──
  function renderNpcBar(data) {
    App.npcsHere = data.npcs_here || [];

    // 侧栏列表
    var ul = document.getElementById("npcList");
    ul.innerHTML = "";
    App.npcsHere.forEach(function(n) {
      var li = document.createElement("li");
      li.innerHTML = '<span class="npc-dot"></span>' + n.name;
      li.onclick = function() {
        App.selectedNpcId = n.id;
        renderNpcBar(data);  // 重新渲染侧栏 + 下拉
        setNpcSelect(n.id);
        document.getElementById("msgInput").focus();
      };
      if (n.id === App.selectedNpcId) li.classList.add("selected");
      ul.appendChild(li);
    });

    // 对话下拉
    var sel = document.getElementById("npcSelect");
    var oldVal = sel.value;
    sel.innerHTML = "";
    App.npcsHere.forEach(function(n) {
      var opt = document.createElement("option");
      opt.value = n.id;
      opt.textContent = n.name;
      sel.appendChild(opt);
    });
    // 恢复选中
    if (App.selectedNpcId &&
        App.npcsHere.some(function(n) { return n.id === App.selectedNpcId; })) {
      sel.value = App.selectedNpcId;
    } else if (App.npcsHere.length > 0) {
      sel.value = App.npcsHere[0].id;
      App.selectedNpcId = App.npcsHere[0].id;
    }
  }

  function setNpcSelect(id) {
    var sel = document.getElementById("npcSelect");
    sel.value = id;
  }

  // ═══════════════════════════════════════════
  //  消息区域
  // ═══════════════════════════════════════════

  /** 添加一条消息到对话区，返回 DOM 元素 */
  App.addMsg = function(type, text, speaker) {
    var area = document.getElementById("dialogueArea");
    var div  = document.createElement("div");
    div.className = "msg " + type;
    if (type === "npc" && speaker) {
      div.innerHTML = '<div class="speaker">' + speaker
        + '</div><div class="msg-text">' + text + '</div>';
    } else {
      div.textContent = text;
    }
    area.appendChild(div);
    scrollToBottom();
    return div;
  };

  function scrollToBottom() {
    var area = document.getElementById("dialogueArea");
    area.scrollTop = area.scrollHeight;
  }

  /** 外部也可调用 */
  App.scrollToBottom = scrollToBottom;

  // ═══════════════════════════════════════════
  //  界门（地图切换入口）
  // ═══════════════════════════════════════════

  function renderPortals(p) {
    var mapInfo = App.mapsData[App.currentMapId];
    var div = document.getElementById("portalList");
    if (!mapInfo || !mapInfo.portals || mapInfo.portals.length === 0) {
      div.innerHTML = '<span style="color:#555;">\u6b64\u5730\u56fe\u65e0\u754c\u95e8</span>';
      return;
    }
    div.innerHTML = mapInfo.portals.map(function(pt) {
      var target = App.mapsData[pt.target_map_id];
      return '<div class="portal-entry" onclick="App.moveTo('
        + pt.to_x + ',' + pt.to_y + ')">\u2197 \u5f80\u3010'
        + (target ? target.name : pt.target_map_id)
        + '\u3011(' + pt.to_x + ',' + pt.to_y + ')</div>';
    }).join("");
  }

})(window.App);
