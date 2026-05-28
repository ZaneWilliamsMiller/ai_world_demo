// ═══════════════════════════════════════════════════════
//  ui.js — UI 渲染：HUD、NPC 列表、消息、界门
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  // ═══════════════════════════════════════════
  //  HTML 安全工具 - 防止 XSS 攻击
  //  安全说明：所有用户输入和不可信内容必须经过转义后再插入 DOM
  // ═══════════════════════════════════════════
  const HtmlUtils = {
    // 转义特殊 HTML 字符，防止 XSS 注入
    escape(text) {
      if (!text) return '';
      const str = String(text);
      const div = document.createElement('div');
      div.textContent = str;
      return div.innerHTML;
    },

    // 安全设置元素的 innerHTML（自动转义）
    setSafeHtml(element, html) {
      if (element) {
        element.innerHTML = this.escape(html);
      }
    },

    // 设置原始 HTML（仅用于可信内容，如后端已处理的富文本）
    // 注意：调用此方法前必须确保内容来源可信且已消毒
    // 设置原始 HTML（仅用于可信内容）
    setTrustedHtml(element, html) {
      if (element) {
        element.innerHTML = html;
      }
    },

    // HTML 白名单过滤：只允许 <b> <i> <u> <br> <strong> <em> 标签，其余转义
    sanitize(text) {
      if (!text) return '';
      return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        // 恢复安全标签
        .replace(/&lt;b&gt;/g, '<b>').replace(/&lt;\/b&gt;/g, '</b>')
        .replace(/&lt;i&gt;/g, '<i>').replace(/&lt;\/i&gt;/g, '</i>')
        .replace(/&lt;u&gt;/g, '<u>').replace(/&lt;\/u&gt;/g, '</u>')
        .replace(/&lt;br\s*\/?&gt;/g, '<br>')
        .replace(/&lt;strong&gt;/g, '<strong>').replace(/&lt;\/strong&gt;/g, '</strong>')
        .replace(/&lt;em&gt;/g, '<em>').replace(/&lt;\/em&gt;/g, '</em>');
    }
  };

  // 暴露给其他模块使用
  App.HtmlUtils = HtmlUtils;

  // ═══════════════════════════════════════════
  //  全量 UI 更新（由 API 层或对话流程调用）
  // ═══════════════════════════════════════════

  App.updateUI = function(data) {
    const p = data.player || {};
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
    const badge = p.world_is_night
        ? '<span class="badge night">' + HtmlUtils.escape(p.world_shichen) + '\u00b7\u591c</span>'
        : '<span class="badge day">'   + HtmlUtils.escape(p.world_shichen) + '</span>';
    const topbarInfo = document.getElementById("topbarInfo");
    HtmlUtils.setSafeHtml(topbarInfo,
      HtmlUtils.escape(p.map_id || "") + " " + badge + " " + HtmlUtils.escape(p.weather || ""));
  }

  // ── 右栏：状态面板 ──
  function renderRightPanel(p, data) {
    // 时辰 · 天气 · 天数
    document.getElementById("statTime").textContent =
      p.world_shichen || "--";
    document.getElementById("statWeather").textContent =
      p.weather || "--";
    const dayEl = document.getElementById("statDay");
    if (dayEl) dayEl.textContent = p.world_day || 1;

    // 体力
    const v = p.vigor || 0, vm = p.vigor_max || 100;
    document.getElementById("statVigor").textContent = v + "/" + vm;
    document.getElementById("barVigor").style.width =
      (v / vm * 100).toFixed(0) + "%";

    // 心气
    const s = p.spirit || 0, sm = p.spirit_max || 100;
    document.getElementById("statSpirit").textContent = s + "/" + sm;
    document.getElementById("barSpirit").style.width =
      (s / sm * 100).toFixed(0) + "%";

    // 钱银
    document.getElementById("statCoins").textContent =
      p.coins || 0;

    // 背包 - 物品名称需要转义以防止 XSS
    const inv = p.inventory || {};
    let html = "";
    Object.keys(inv).forEach(function(k) {
      html += "<span>" + HtmlUtils.escape(k) + "\u00d7" + HtmlUtils.escape(inv[k]) + "</span>";
    });
    const statInv = document.getElementById("statInv");
    HtmlUtils.setSafeHtml(statInv,
      html || "<span style='color:#555;'>\u8eab\u65e0\u957f\u7269</span>");
  }

  // ── 此地图 NPC 列表 ──
  function renderNpcBar(data) {
    App.npcsHere = data.npcs_here || [];

    // 侧栏列表 - NPC 名称需要转义
    const ul = document.getElementById("npcList");
    ul.innerHTML = "";
    App.npcsHere.forEach(function(n) {
      const li = document.createElement("li");
      // NPC 名称来自后端数据，为安全起见进行转义
      li.innerHTML = '<span class="npc-dot"></span>' + HtmlUtils.escape(n.name);
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
    const sel = document.getElementById("npcSelect");
    const oldVal = sel.value;
    sel.innerHTML = "";
    App.npcsHere.forEach(function(n) {
      const opt = document.createElement("option");
      opt.value = n.id;
      opt.textContent = n.name;  // 使用 textContent 自动转义
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
    const sel = document.getElementById("npcSelect");
    sel.value = id;
  }

  // ═══════════════════════════════════════════
  //  消息区域
  // ═══════════════════════════════════════════

  /** 添加一条消息到对话区，返回 DOM 元素 */
  App.addMsg = function(type, text, isImportant) {
    const area = document.getElementById("dialogueArea");
    const div  = document.createElement("div");
    div.className = "msg " + type;

    if (isImportant) {
      div.classList.add("important");
    }

    if (type === "npc" && text) {
      // NPC 对话：speaker 必须转义，text 经白名单过滤（b/i/u/br/strong/em）
      div.innerHTML = '<div class="speaker">' + HtmlUtils.escape(text.speaker || "")
        + '</div><div class="msg-text">' + HtmlUtils.sanitize(text.text || text) + '</div>';
    } else if (type === "system-error") {
      // 错误消息：只转换换行符，其他内容转义
      div.innerHTML = HtmlUtils.escape(text).replace(/\n/g, "<br>");
    } else {
      // 其他类型使用 textContent 自动转义
      div.textContent = text;
    }

    area.appendChild(div);

    if (isImportant) {
      div.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      scrollToBottom();
    }

    return div;
  };

  function scrollToBottom() {
    const area = document.getElementById("dialogueArea");
    area.scrollTop = area.scrollHeight;
  }

  /** 外部也可调用 */
  App.scrollToBottom = scrollToBottom;

  // ═══════════════════════════════════════════
  //  界门（地图切换入口）
  // ═══════════════════════════════════════════

  function renderPortals(p) {
    const mapInfo = App.mapsData[App.currentMapId];
    const div = document.getElementById("portalList");
    if (!mapInfo || !mapInfo.portals || mapInfo.portals.length === 0) {
      div.innerHTML = '<span style="color:#555;">\u6b64\u5730\u56fe\u65e0\u754c\u95e8</span>';
      return;
    }
    // 界门信息来自后端数据，坐标经 parseInt 确保数值安全
    div.innerHTML = mapInfo.portals.map(function(pt) {
      const target = App.mapsData[pt.target_map_id];
      const targetName = target ? target.name : pt.target_map_id;
      const sx = parseInt(pt.to_x, 10);
      const sy = parseInt(pt.to_y, 10);
      return '<div class="portal-entry" onclick="App.moveTo('
        + sx + ',' + sy + ')">\u2197 \u5f80\u3010'
        + HtmlUtils.escape(targetName)
        + '\u3011(' + sx + ',' + sy + ')</div>';
    }).join("");
  }

})(window.App);
