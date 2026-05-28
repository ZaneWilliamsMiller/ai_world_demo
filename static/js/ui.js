window.App = window.App || {};

(function(App) {
  "use strict";

  const HtmlUtils = {
    escape(text) {
      if (!text) return '';
      const str = String(text);
      const div = document.createElement('div');
      div.textContent = str;
      return div.innerHTML.replace(/'/g, '&#39;');
    },

    setSafeHtml(element, html) {
      if (element) {
        element.innerHTML = this.escape(html);
      }
    },

    setTrustedHtml(element, html) {
      if (element) {
        element.innerHTML = html;
      }
    },

    sanitize(text) {
      if (!text) return '';
      return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/&lt;b&gt;/g, '<b>').replace(/&lt;\/b&gt;/g, '</b>')
        .replace(/&lt;i&gt;/g, '<i>').replace(/&lt;\/i&gt;/g, '</i>')
        .replace(/&lt;u&gt;/g, '<u>').replace(/&lt;\/u&gt;/g, '</u>')
        .replace(/&lt;br\s*\/?&gt;/g, '<br>')
        .replace(/&lt;strong&gt;/g, '<strong>').replace(/&lt;\/strong&gt;/g, '</strong>')
        .replace(/&lt;em&gt;/g, '<em>').replace(/&lt;\/em&gt;/g, '</em>');
    }
  };

  App.HtmlUtils = HtmlUtils;

  App.updateUI = function(data) {
    const p = data.player || {};
    App.currentMapId = p.map_id;
    App.npcCatalog  = data.npc_catalog || App.npcCatalog || [];
    App._playerX = p.px;
    App._playerY = p.py;
    App._mapLocations = data.map_locations || App._mapLocations || {};

    updateTopbar(p);
    App.renderMap(p);
    renderRightPanel(p, data);
    renderNpcBar(data);
    renderPortals(p);
    renderAtmosphere(p, data);
    renderBounty(data);
  };

  function updateTopbar(p) {
    const badge = p.world_is_night
        ? '<span class="badge night">' + HtmlUtils.escape(p.world_shichen) + '\u00b7\u591c</span>'
        : '<span class="badge day">'   + HtmlUtils.escape(p.world_shichen) + '</span>';
    const topbarInfo = document.getElementById("topbarInfo");
    HtmlUtils.setSafeHtml(topbarInfo,
      HtmlUtils.escape(p.map_id || "") + " " + badge + " " + HtmlUtils.escape(p.weather || ""));
  }

  function renderRightPanel(p, data) {
    document.getElementById("statTime").textContent =
      p.world_shichen || "--";
    document.getElementById("statWeather").textContent =
      p.weather || "--";
    const dayEl = document.getElementById("statDay");
    if (dayEl) dayEl.textContent = p.world_day || 1;

    const v = p.vigor || 0, vm = p.vigor_max || 100;
    document.getElementById("statVigor").textContent = v + "/" + vm;
    document.getElementById("barVigor").style.width =
      (v / vm * 100).toFixed(0) + "%";

    const s = p.spirit || 0, sm = p.spirit_max || 100;
    document.getElementById("statSpirit").textContent = s + "/" + sm;
    document.getElementById("barSpirit").style.width =
      (s / sm * 100).toFixed(0) + "%";

    document.getElementById("statCoins").textContent =
      p.coins || 0;

    const inv = p.inventory || {};
    let html = "";
    Object.keys(inv).forEach(function(k) {
      html += "<span class='inv-item' data-item=\"" + HtmlUtils.escape(k) + "\">" + HtmlUtils.escape(k) + "\u00d7" + HtmlUtils.escape(inv[k]) + "</span>";
    });
    const statInv = document.getElementById("statInv");
    if (html) {
      statInv.innerHTML = html;
    } else {
      statInv.innerHTML = "<span style='color:#555;'>\u8eab\u65e0\u957f\u7269</span>";
    }
    statInv.querySelectorAll(".inv-item").forEach(function(el) {
      el.addEventListener("click", function() {
        var name = el.getAttribute("data-item");
        if (name) App.doUseItem(name);
      });
    });
  }

  function renderNpcBar(data) {
    App.npcsHere = data.npcs_here || [];

    var ul = document.getElementById("npcList");
    if (!App.npcsHere || App.npcsHere.length === 0) {
      ul.innerHTML = '<div style="color:var(--text-muted);padding:8px;font-size:12px;">附近无人，试试移动到其他地点</div>';
    } else {
      ul.innerHTML = "";
      App.npcsHere.forEach(function(n) {
        const li = document.createElement("li");
        li.innerHTML = '<span class="npc-dot"></span>' + HtmlUtils.escape(n.name);
        li.onclick = function() {
          App.selectedNpcId = n.id;
          renderNpcBar(data);
          setNpcSelect(n.id);
          document.getElementById("msgInput").focus();
        };
        if (n.id === App.selectedNpcId) li.classList.add("selected");
        ul.appendChild(li);
      });
    }

    const sel = document.getElementById("npcSelect");
    const oldVal = sel.value;
    sel.innerHTML = "";
    App.npcsHere.forEach(function(n) {
      const opt = document.createElement("option");
      opt.value = n.id;
      opt.textContent = n.name;
      sel.appendChild(opt);
    });
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

  function renderAtmosphere(p, data) {
    var atmoEl = document.getElementById("statAtmosphere");
    var dangerEl = document.getElementById("statDanger");

    if (atmoEl) {
      var atmo = data.atmosphere || p.atmosphere;
      if (atmo) {
        atmoEl.textContent = atmo;
        atmoEl.classList.add("visible");
      } else {
        atmoEl.classList.remove("visible");
      }
    }

    if (dangerEl) {
      var ds = data.danger_sense || p.danger_sense;
      if (ds && ds.alert) {
        dangerEl.textContent = "\u26a0\ufe0f " + ds.alert;
        dangerEl.classList.add("visible");
      } else {
        dangerEl.classList.remove("visible");
      }
    }
  }

  function renderBounty(data) {
    var p = data.player || {};
    var bounties = p.bounties || data.bounties;
    var listEl = document.getElementById("bountyList");
    if (!listEl) return;

    if (!bounties || bounties.length === 0) {
      listEl.innerHTML = '<div style="color:var(--text-muted);padding:8px;font-size:11px;">暂无悬赏，点击刷新查看</div>';
      return;
    }

    var html = "";
    bounties.forEach(function(b) {
      var isActive = b.status === "active" || b.accepted;
      var cls = isActive ? "bounty-item active" : "bounty-item";
      html += '<div class="' + cls + '" data-bounty-id="' + HtmlUtils.escape(b.id || "") + '">';
      html += '<div class="bounty-title">' + HtmlUtils.escape(b.title || b.name || "悬赏") + '</div>';
      if (b.description) {
        html += '<div class="bounty-desc">' + HtmlUtils.escape(b.description).substring(0, 80) + '</div>';
      }
      if (b.reward) {
        html += '<div class="bounty-reward">\u5956\u52b1: ' + HtmlUtils.escape(String(b.reward)) + '</div>';
      }
      if (isActive) {
        html += '<div style="color:var(--accent-green);font-size:10px;margin-top:2px;">\u2713 \u5df2\u63a5\u53d7</div>';
      }
      html += '</div>';
    });
    listEl.innerHTML = html;

    listEl.querySelectorAll(".bounty-item:not(.active)").forEach(function(el) {
      el.addEventListener("click", function() {
        var bid = el.getAttribute("data-bounty-id");
        if (bid) App.doBountyAccept(bid);
      });
    });
  }

  App.addMsg = function(type, text, isImportant) {
    const area = document.getElementById("dialogueArea");
    const div  = document.createElement("div");
    div.className = "msg " + type;

    if (isImportant) {
      div.classList.add("important");
    }

    if (type === "npc" && text) {
      div.innerHTML = '<div class="speaker">' + HtmlUtils.escape(text.speaker || "")
        + '</div><div class="msg-text">' + HtmlUtils.sanitize(text.text || text) + '</div>';
    } else if (type === "system-error") {
      div.innerHTML = HtmlUtils.escape(text).replace(/\n/g, "<br>");
    } else {
      div.textContent = text;
    }

    area.appendChild(div);

    while (area.children.length > 200) {
      area.removeChild(area.firstChild);
    }

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

  App.scrollToBottom = scrollToBottom;

  function renderPortals(p) {
    const mapInfo = App.mapsData[App.currentMapId];
    const div = document.getElementById("portalList");
    if (!mapInfo || !mapInfo.portals || mapInfo.portals.length === 0) {
      div.innerHTML = '<span style="color:#555;">\u6b64\u5730\u56fe\u65e0\u754c\u95e8</span>';
      return;
    }
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
