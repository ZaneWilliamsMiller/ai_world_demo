window.App = window.App || {};

(function(App) {
  "use strict";

  var HtmlUtils = App.HtmlUtils;

  App.updateUI = function(data) {
    var p = data.player || {};
    App.currentMapId = p.map_id;
    App.npcCatalog  = data.npc_catalog || App.npcCatalog || [];
    App._mapLocations = data.map_locations || App._mapLocations || {};

    updateTopbar(p);
    App.renderMap(p);
    renderRightPanel(p, data);
    renderNpcBar(data);
    renderPortals(p);
    renderAtmosphere(p, data);
    renderBounty(data);

    if (p.move_locked) {
      App.updatePlayerMarker(p.px, p.py, "locked");
    } else {
      App.updatePlayerMarker(p.px, p.py, "normal");
    }
  };

  function updateTopbar(p) {
    var topbarInfo = document.getElementById("topbarInfo");
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

  function renderRightPanel(p, _data) {
    var statTime = document.getElementById("statTime");
    if (statTime) statTime.textContent = p.world_shichen || "--";
    var statWeather = document.getElementById("statWeather");
    if (statWeather) statWeather.textContent = p.weather || "--";
    var dayEl = document.getElementById("statDay");
    if (dayEl) dayEl.textContent = p.world_day || 1;

    var v = p.vigor || 0, vm = Math.max(p.vigor_max || 100, 1);
    var statVigor = document.getElementById("statVigor");
    if (statVigor) statVigor.textContent = v + "/" + vm;
    var barVigor = document.getElementById("barVigor");
    if (barVigor) barVigor.style.width = (v / vm * 100).toFixed(0) + "%";

    var s = p.spirit || 0, sm = Math.max(p.spirit_max || 100, 1);
    var statSpirit = document.getElementById("statSpirit");
    if (statSpirit) statSpirit.textContent = s + "/" + sm;
    var barSpirit = document.getElementById("barSpirit");
    if (barSpirit) barSpirit.style.width = (s / sm * 100).toFixed(0) + "%";

    var statCoins = document.getElementById("statCoins");
    if (statCoins) statCoins.textContent = p.coins || 0;

    var inv = p.inventory || {};
    var statInv = document.getElementById("statInv");
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
    var npcs = data.npcs_here;
    if (npcs !== undefined) {
      App.npcsHere = npcs;
    }

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
        var li = document.createElement("li");
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

    var sel = document.getElementById("npcSelect");
    if (!sel) return;
    sel.innerHTML = "";
    App.npcsHere.forEach(function(n) {
      var opt = document.createElement("option");
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
    var sel = document.getElementById("npcSelect");
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

  function _formatReward(reward) {
    if (!reward) return "";
    if (typeof reward === "string") return reward;
    var parts = [];
    if (reward.coins) parts.push(reward.coins + "文");
    if (reward.rep && typeof reward.rep === "object") {
      var facNames = {"yamen": "衙门", "biaoju": "镖局", "caobang": "漕帮", "jianghu": "江湖"};
      for (var k in reward.rep) {
        parts.push((facNames[k] || k) + "声望+" + reward.rep[k]);
      }
    }
    if (reward.favor && typeof reward.favor === "object") {
      for (var f in reward.favor) {
        var val = reward.favor[f];
        parts.push((val > 0 ? "好感+" : "好感") + val);
      }
    }
    if (reward.items_gain && Array.isArray(reward.items_gain)) {
      reward.items_gain.forEach(function(it) { parts.push(it); });
    }
    return parts.join("，") || "无";
  }

  function _renderBountyOverlay(data) {
    var p = data.player || {};
    var bounties = p.bounties || [];
    var activeBounty = p.active_bounty;
    var contentEl = document.getElementById("bountyOverlayContent");
    if (!contentEl) return;
    contentEl.innerHTML = "";

    if (activeBounty) {
      var activeDiv = document.createElement("div");
      activeDiv.className = "bounty-overlay-item active";
      var activeTitle = document.createElement("div");
      activeTitle.className = "bounty-title";
      activeTitle.textContent = (activeBounty.title || "进行中") + " ✓";
      activeDiv.appendChild(activeTitle);
      if (activeBounty.desc) {
        var activeDesc = document.createElement("div");
        activeDesc.className = "bounty-desc";
        activeDesc.textContent = activeBounty.desc;
        activeDiv.appendChild(activeDesc);
      }
      var activeReward = document.createElement("div");
      activeReward.className = "bounty-reward";
      activeReward.textContent = "奖励: " + _formatReward(activeBounty.reward);
      activeDiv.appendChild(activeReward);
      var activeLabel = document.createElement("div");
      activeLabel.style.cssText = "color:var(--accent-green);font-size:11px;margin-top:4px;";
      activeLabel.textContent = "✓ 已接受 — 进行中";
      activeDiv.appendChild(activeLabel);
      contentEl.appendChild(activeDiv);
    }

    if (!bounties || bounties.length === 0) {
      var emptyDiv = document.createElement("div");
      emptyDiv.style.cssText = "color:var(--text-muted);padding:12px;font-size:12px;";
      emptyDiv.textContent = "暂无悬赏，点击刷新查看";
      contentEl.appendChild(emptyDiv);
      return;
    }

    bounties.forEach(function(b) {
      var isAccepted = b.status === "active" || b.accepted ||
        (activeBounty && activeBounty.id === b.id);
      var item = document.createElement("div");
      item.className = isAccepted ? "bounty-overlay-item active" : "bounty-overlay-item";

      var title = document.createElement("div");
      title.className = "bounty-title";
      title.textContent = b.title || b.name || "悬赏";
      item.appendChild(title);

      if (b.desc) {
        var desc = document.createElement("div");
        desc.className = "bounty-desc";
        desc.textContent = b.desc;
        item.appendChild(desc);
      }
      var rewardEl = document.createElement("div");
      rewardEl.className = "bounty-reward";
      rewardEl.textContent = "奖励: " + _formatReward(b.reward);
      item.appendChild(rewardEl);

      if (b.requires) {
        var reqDiv = document.createElement("div");
        reqDiv.style.cssText = "color:var(--text-muted);font-size:10px;margin-bottom:4px;";
        var reqParts = [];
        if (b.requires.talk_to_npc) reqParts.push("与NPC交谈");
        if (b.requires.ask_about) reqParts.push("打听消息");
        if (b.requires.move_to) reqParts.push("前往地点");
        if (b.requires.with_npc) reqParts.push("护送NPC");
        if (b.requires.have_item) reqParts.push("获取物品");
        if (reqParts.length) reqDiv.textContent = "条件: " + reqParts.join("、");
        item.appendChild(reqDiv);
      }

      if (isAccepted) {
        var label = document.createElement("div");
        label.style.cssText = "color:var(--accent-green);font-size:11px;margin-top:4px;";
        label.textContent = "✓ 已接受";
        item.appendChild(label);
      } else {
        var acceptBtn = document.createElement("button");
        acceptBtn.className = "bounty-accept-btn";
        acceptBtn.textContent = "接取悬赏";
        acceptBtn.addEventListener("click", function(ev) {
          ev.stopPropagation();
          var bid = b.id;
          if (!bid) return;
          var rewardText = _formatReward(b.reward);
          App.showConfirm(
            "接取悬赏",
            (b.title || "悬赏") + "<br><br>" +
            (b.desc ? b.desc + "<br><br>" : "") +
            "奖励: " + rewardText + "<br><br>确定要接取此悬赏吗？",
            function() { App.doBountyAccept(bid); }
          );
        });
        item.appendChild(acceptBtn);
      }

      contentEl.appendChild(item);
    });
  }

  function renderBounty(data) {
    var p = data.player || {};
    var bounties = p.bounties || data.bounties;
    var activeBounty = p.active_bounty;
    var listEl = document.getElementById("bountyList");
    var summaryText = document.getElementById("bountySummaryText");
    if (!listEl) return;
    listEl.innerHTML = "";

    _renderBountyOverlay(data);

    if (summaryText) {
      if (activeBounty) {
        summaryText.textContent = "悬赏: " + (activeBounty.title || "进行中") + " ✓";
      } else if (bounties && bounties.length > 0) {
        summaryText.textContent = "悬赏: " + bounties.length + "项可接";
      } else {
        summaryText.textContent = "悬赏: 暂无";
      }
    }

    if (activeBounty) {
      var activeDiv = document.createElement("div");
      activeDiv.className = "bounty-item active";
      var activeTitle = document.createElement("div");
      activeTitle.className = "bounty-title";
      activeTitle.textContent = (activeBounty.title || "进行中") + " ✓";
      activeDiv.appendChild(activeTitle);
      if (activeBounty.desc) {
        var activeDesc = document.createElement("div");
        activeDesc.className = "bounty-desc";
        activeDesc.textContent = activeBounty.desc;
        activeDiv.appendChild(activeDesc);
      }
      var activeReward = document.createElement("div");
      activeReward.className = "bounty-reward";
      activeReward.textContent = "奖励: " + _formatReward(activeBounty.reward);
      activeDiv.appendChild(activeReward);
      listEl.appendChild(activeDiv);
    }

    if (!bounties || bounties.length === 0) {
      var emptyDiv = document.createElement("div");
      emptyDiv.style.cssText = "color:var(--text-muted);padding:8px;font-size:11px;";
      emptyDiv.textContent = "暂无悬赏，点击刷新查看";
      listEl.appendChild(emptyDiv);
      return;
    }

    bounties.forEach(function(b) {
      var isAccepted = b.status === "active" || b.accepted ||
        (activeBounty && activeBounty.id === b.id);
      var item = document.createElement("div");
      item.className = isAccepted ? "bounty-item active" : "bounty-item";
      item.setAttribute("data-bounty-id", b.id || "");

      var header = document.createElement("div");
      header.className = "bounty-item-header";
      var title = document.createElement("div");
      title.className = "bounty-title";
      title.textContent = b.title || b.name || "悬赏";
      header.appendChild(title);
      if (!isAccepted) {
        var toggleBtn = document.createElement("span");
        toggleBtn.className = "bounty-toggle";
        toggleBtn.textContent = "展开";
        header.appendChild(toggleBtn);
      }
      item.appendChild(header);

      var detail = document.createElement("div");
      detail.className = "bounty-detail";
      detail.style.display = "none";

      if (b.desc) {
        var desc = document.createElement("div");
        desc.className = "bounty-desc";
        desc.textContent = b.desc;
        detail.appendChild(desc);
      }
      var rewardEl = document.createElement("div");
      rewardEl.className = "bounty-reward";
      rewardEl.textContent = "奖励: " + _formatReward(b.reward);
      detail.appendChild(rewardEl);

      if (isAccepted) {
        var activeLabel = document.createElement("div");
        activeLabel.style.cssText = "color:var(--accent-green);font-size:10px;margin-top:2px;";
        activeLabel.textContent = "✓ 已接受";
        detail.appendChild(activeLabel);
      }

      item.appendChild(detail);

      if (!isAccepted) {
        var toggleBtnEl = header.querySelector(".bounty-toggle");
        if (toggleBtnEl) {
          toggleBtnEl.addEventListener("click", function(ev) {
            ev.stopPropagation();
            var isOpen = detail.style.display !== "none";
            detail.style.display = isOpen ? "none" : "block";
            toggleBtnEl.textContent = isOpen ? "展开" : "收起";
          });
        }
        item.addEventListener("click", function() {
          var bid = b.id;
          if (!bid) return;
          var rewardText = _formatReward(b.reward);
          App.showConfirm(
            "接取悬赏",
            (b.title || "悬赏") + "<br><br>" +
            (b.desc ? b.desc + "<br><br>" : "") +
            "奖励: " + rewardText + "<br><br>确定要接取此悬赏吗？",
            function() { App.doBountyAccept(bid); }
          );
        });
      }

      listEl.appendChild(item);
    });
  }

  App.addMsg = function(type, text, isImportant) {
    var area = document.getElementById("dialogueArea");
    if (!area) return null;
    var div = document.createElement("div");
    div.className = "msg " + type;

    if (isImportant) {
      div.classList.add("important");
    }

    if ((type === "npc" || type === "npc_interact") && text) {
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
    var area = document.getElementById("dialogueArea");
    if (area) area.scrollTop = area.scrollHeight;
  }

  App.scrollToBottom = scrollToBottom;

  function renderPortals(_p) {
    var mapInfo = App.mapsData[App.currentMapId];
    var div = document.getElementById("portalList");
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
      var target = App.mapsData[pt.target_map_id];
      var targetName = target ? target.name : pt.target_map_id;
      var sx = parseInt(pt.to_x, 10);
      var sy = parseInt(pt.to_y, 10);
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
