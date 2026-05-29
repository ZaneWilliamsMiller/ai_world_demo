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

    _ALLOWED_TAGS: new Set(['b', 'i', 'u', 'strong', 'em', 'br']),

    sanitize(text) {
      if (!text) return '';
      var escaped = String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      escaped = escaped.replace(/&lt;(\/?)(b|i|u|strong|em|br)\s*\/?&gt;/gi, function(match, slash, tag) {
        tag = tag.toLowerCase();
        if (HtmlUtils._ALLOWED_TAGS.has(tag)) {
          if (tag === 'br') return '<br>';
          return '<' + slash + tag + '>';
        }
        return match;
      });
      return escaped;
    },
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
    const topbarInfo = document.getElementById("topbarInfo");
    if (!topbarInfo) return;
    topbarInfo.textContent = "";

    var mapSpan = document.createElement("span");
    mapSpan.textContent = (p.map_id || "") + " ";
    topbarInfo.appendChild(mapSpan);

    var badge = document.createElement("span");
    badge.className = p.world_is_night ? "badge night" : "badge day";
    badge.textContent = p.world_shichen || "";
    if (p.world_is_night) badge.textContent += "\u00b7\u591c";
    topbarInfo.appendChild(badge);

    var weatherSpan = document.createElement("span");
    weatherSpan.textContent = " " + (p.weather || "");
    topbarInfo.appendChild(weatherSpan);
  }

  function renderRightPanel(p, data) {
    var statTime = document.getElementById("statTime");
    if (statTime) statTime.textContent = p.world_shichen || "--";
    var statWeather = document.getElementById("statWeather");
    if (statWeather) statWeather.textContent = p.weather || "--";
    const dayEl = document.getElementById("statDay");
    if (dayEl) dayEl.textContent = p.world_day || 1;

    const v = p.vigor || 0, vm = Math.max(p.vigor_max || 100, 1);
    var statVigor = document.getElementById("statVigor");
    if (statVigor) statVigor.textContent = v + "/" + vm;
    var barVigor = document.getElementById("barVigor");
    if (barVigor) barVigor.style.width = (v / vm * 100).toFixed(0) + "%";

    const s = p.spirit || 0, sm = Math.max(p.spirit_max || 100, 1);
    var statSpirit = document.getElementById("statSpirit");
    if (statSpirit) statSpirit.textContent = s + "/" + sm;
    var barSpirit = document.getElementById("barSpirit");
    if (barSpirit) barSpirit.style.width = (s / sm * 100).toFixed(0) + "%";

    var statCoins = document.getElementById("statCoins");
    if (statCoins) statCoins.textContent = p.coins || 0;

    const inv = p.inventory || {};
    const statInv = document.getElementById("statInv");
    if (!statInv) return;
    statInv.innerHTML = "";

    var keys = Object.keys(inv);
    if (keys.length === 0) {
      var emptySpan = document.createElement("span");
      emptySpan.style.color = "#555";
      emptySpan.textContent = "\u8eab\u65e0\u957f\u7269";
      statInv.appendChild(emptySpan);
    } else {
      keys.forEach(function(k) {
        var span = document.createElement("span");
        span.className = "inv-item";
        span.setAttribute("data-item", k);
        span.textContent = k + "\u00d7" + inv[k];
        span.addEventListener("click", function() {
          App.doUseItem(k);
        });
        statInv.appendChild(span);
      });
    }
  }

  function renderNpcBar(data) {
    App.npcsHere = data.npcs_here || [];

    var ul = document.getElementById("npcList");
    if (!ul) return;
    ul.innerHTML = "";

    if (!App.npcsHere || App.npcsHere.length === 0) {
      var emptyDiv = document.createElement("div");
      emptyDiv.style.cssText = "color:var(--text-muted);padding:8px;font-size:12px;";
      emptyDiv.textContent = "附近无人，试试移动到其他地点";
      ul.appendChild(emptyDiv);
    } else {
      App.npcsHere.forEach(function(n) {
        const li = document.createElement("li");
        var dot = document.createElement("span");
        dot.className = "npc-dot";
        li.appendChild(dot);
        li.appendChild(document.createTextNode(n.name));
        li.onclick = function() {
          App.selectedNpcId = n.id;
          renderNpcBar(data);
          setNpcSelect(n.id);
          var msgInput = document.getElementById("msgInput");
          if (msgInput) msgInput.focus();
        };
        if (n.id === App.selectedNpcId) li.classList.add("selected");
        ul.appendChild(li);
      });
    }

    const sel = document.getElementById("npcSelect");
    if (!sel) return;
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
    if (sel) sel.value = id;
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
    listEl.innerHTML = "";

    if (!bounties || bounties.length === 0) {
      var emptyDiv = document.createElement("div");
      emptyDiv.style.cssText = "color:var(--text-muted);padding:8px;font-size:11px;";
      emptyDiv.textContent = "暂无悬赏，点击刷新查看";
      listEl.appendChild(emptyDiv);
      return;
    }

    bounties.forEach(function(b) {
      var isActive = b.status === "active" || b.accepted;
      var item = document.createElement("div");
      item.className = isActive ? "bounty-item active" : "bounty-item";
      item.setAttribute("data-bounty-id", b.id || "");

      var title = document.createElement("div");
      title.className = "bounty-title";
      title.textContent = b.title || b.name || "悬赏";
      item.appendChild(title);

      if (b.desc) {
        var desc = document.createElement("div");
        desc.className = "bounty-desc";
        desc.textContent = (b.desc || "").substring(0, 80);
        item.appendChild(desc);
      }
      if (b.reward) {
        var reward = document.createElement("div");
        reward.className = "bounty-reward";
        reward.textContent = "\u5956\u52b1: " + b.reward;
        item.appendChild(reward);
      }
      if (isActive) {
        var activeLabel = document.createElement("div");
        activeLabel.style.cssText = "color:var(--accent-green);font-size:10px;margin-top:2px;";
        activeLabel.textContent = "\u2713 \u5df2\u63a5\u53d7";
        item.appendChild(activeLabel);
      }

      if (!isActive) {
        item.addEventListener("click", function() {
          var bid = b.id;
          if (bid) App.doBountyAccept(bid);
        });
      }

      listEl.appendChild(item);
    });
  }

  App.addMsg = function(type, text, isImportant) {
    const area = document.getElementById("dialogueArea");
    if (!area) return null;
    const div  = document.createElement("div");
    div.className = "msg " + type;

    if (isImportant) {
      div.classList.add("important");
    }

    if (type === "npc" && text) {
      var speakerDiv = document.createElement("div");
      speakerDiv.className = "speaker";
      speakerDiv.textContent = text.speaker || "";
      div.appendChild(speakerDiv);

      var textDiv = document.createElement("div");
      textDiv.className = "msg-text";
      HtmlUtils.setTrustedHtml(textDiv, HtmlUtils.sanitize(text.text || text));
      div.appendChild(textDiv);
    } else if (type === "system-error") {
      var lines = (text || "").split("\n");
      lines.forEach(function(line, i) {
        if (i > 0) div.appendChild(document.createElement("br"));
        div.appendChild(document.createTextNode(line));
      });
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
    if (area) area.scrollTop = area.scrollHeight;
  }

  App.scrollToBottom = scrollToBottom;

  function renderPortals(p) {
    const mapInfo = App.mapsData[App.currentMapId];
    const div = document.getElementById("portalList");
    if (!div) return;
    div.innerHTML = "";

    if (!mapInfo || !mapInfo.portals || mapInfo.portals.length === 0) {
      var emptySpan = document.createElement("span");
      emptySpan.style.color = "#555";
      emptySpan.textContent = "\u6b64\u5730\u56fe\u65e0\u754c\u95e8";
      div.appendChild(emptySpan);
      return;
    }

    mapInfo.portals.forEach(function(pt) {
      const target = App.mapsData[pt.target_map_id];
      const targetName = target ? target.name : pt.target_map_id;
      const sx = parseInt(pt.to_x, 10);
      const sy = parseInt(pt.to_y, 10);
      if (isNaN(sx) || isNaN(sy)) return;

      var entry = document.createElement("div");
      entry.className = "portal-entry";
      entry.textContent = "\u2197 \u5f80\u3010" + targetName + "\u3011(" + sx + "," + sy + ")";
      entry.addEventListener("click", function() {
        App.moveTo(sx, sy);
      });
      div.appendChild(entry);
    });
  }

})(window.App);
