// ═══════════════════════════════════════════════════════
//  map.js — 地图渲染 + 寻路动画 + 人物模型
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  App._isMoving = false;

  // ─── 地形字符 → emoji ───
  function terrainChar(ch) {
    var map = {
      "#": "\u2b1b", ".": "\u00b7", "~": "\u303c", "=": "\uff1d",
      "F": "\ud83c\udf32", "m": "\u25b2", ";": "\u2726", "/": "\u2571",
      "T": "\ud83c\udfe0", "Y": "\ud83d\udcee", "I": "\ud83c\udfda",
      "M": "\ud83c\udfea", "B": "\u2694", "C": "\ud83c\udfef",
      "G": "\u26e9", "f": "\ud83d\udc1f", "w": "\ud83d\udea2",
      "s": "\u26f5", "E": "\ud83c\udfdb", "*": "\ud83d\udcb0"
    };
    return map[ch] || (ch === " " ? "&nbsp;" : ch);
  }

  // ─── 辅助：按坐标找格子 ───
  function cellAt(x, y) {
    return document.querySelector(
      ".map-cell[data-x='" + x + "'][data-y='" + y + "']");
  }

  // ─── 人物浮标定位 ───
  function placeMarker(x, y) {
    var m = document.querySelector(".player-marker");
    if (!m) return;
    m.style.left = (x * 16) + "px";
    m.style.top  = (y * 16) + "px";
  }

  function ensureMarker() {
    var c = document.getElementById("mapContainer");
    if (!c) return;
    if (!c.querySelector(".player-marker")) {
      var m = document.createElement("div");
      m.className = "player-marker";
      c.appendChild(m);
    }
  }

  // ═══════════════════════════════════════════════════
  //  渲染地图网格
  // ═══════════════════════════════════════════════════
  App.renderMap = function(p) {
    var mapInfo = App.mapsData[App.currentMapId];
    if (!mapInfo) return;

    var rows   = mapInfo.rows;
    var cols   = rows[0] ? rows[0].length : 72;
    var px     = p.px, py = p.py;

    // 更新标题
    document.getElementById("mapTitle").textContent =
      "\ud83d\uddfa\ufe0f " + (mapInfo.name || App.currentMapId);

    var container = document.getElementById("mapContainer");
    container.innerHTML = "";

    var grid = document.createElement("div");
    grid.className = "map-grid";
    grid.style.gridTemplateColumns = "repeat(" + cols + ", 16px)";

    // NPC 坐标集合（从目录中筛选当前地图上的所有 NPC）
    var npcCoords = {};
    (App.npcCatalog || []).forEach(function(n) {
      if (n.map === App.currentMapId && n.x !== undefined && n.y !== undefined)
        npcCoords[n.x + "," + n.y] = n;
    });

    for (var y = 0; y < rows.length; y++) {
      var row = rows[y] || "";
      for (var x = 0; x < cols; x++) {
        var ch   = x < row.length ? row[x] : " ";
        var cell = document.createElement("div");
        cell.className    = "map-cell";
        cell.dataset.x   = x;
        cell.dataset.y   = y;
        cell.innerHTML   = terrainChar(ch);
        cell.title       = "(" + x + "," + y + ") " + ch;
        if (x === px && y === py) cell.classList.add("player-pos");

        // NPC 指示器
        var npcHere = npcCoords[x + "," + y];
        if (npcHere) {
          cell.classList.add("has-npc");
          cell.title = "(" + x + "," + y + ") | " + npcHere.name;
        }

        cell.onclick = (function(tx, ty) {
          return function() { App.moveTo(tx, ty); };
        })(x, y);

        grid.appendChild(cell);
      }
    }
    container.appendChild(grid);

    // 浮动人物标记
    ensureMarker();
    placeMarker(px, py);
  };

  // ═══════════════════════════════════════════════════
  //  动画移动
  // ═══════════════════════════════════════════════════
  App.moveTo = async function(tx, ty) {
    if (App._isMoving) return;
    App._isMoving = true;

    // 清除旧路径
    clearPath();

    try {
      var data = await App.doMove(tx, ty);
      var path = data.path || [];

      if (path.length === 0) {
        App.addMsg("system", "\u6b64\u8def\u4e0d\u901a");
        App._isMoving = false;
        return;
      }

      // 显示路径虚线
      showPath(path);

      // 步行动画
      await animatePath(path);

      // 清除路径
      clearPath();

      // 全量刷新 UI
      App.updateUI(data);
    } catch (e) {
      App.addMsg("system", "\u79fb\u52a8\u5931\u8d25: " + e.message);
    }

    App._isMoving = false;
  };

  // ── 步行动画 ──
  function animatePath(path) {
    return new Promise(function(resolve) {
      var marker = document.querySelector(".player-marker");
      var i = 0;

      // 清除静态 player-pos 标记
      var oldPos = document.querySelectorAll(".map-cell.player-pos");
      for (var j = 0; j < oldPos.length; j++) {
        oldPos[j].classList.remove("player-pos");
      }

      var timer = setInterval(function() {
        if (i >= path.length) {
          clearInterval(timer);

          // 最终定位 + 到达闪烁
          var last = path[path.length - 1];
          placeMarker(last[0], last[1]);

          var dest = cellAt(last[0], last[1]);
          if (dest) {
            dest.classList.add("player-pos", "step-arrive");
            setTimeout(function() {
              if (dest) dest.classList.remove("step-arrive");
            }, 400);
          }

          resolve();
          return;
        }

        var s = path[i];
        placeMarker(s[0], s[1]);

        // 走过格子短暂高亮
        var c = cellAt(s[0], s[1]);
        if (c) {
          c.classList.add("step-active");
          setTimeout(function() {
            if (c) c.classList.remove("step-active");
          }, 120);
        }

        i++;
      }, 80);
    });
  }

  // ── 路径虚线 ──
  function showPath(path) {
    for (var i = 0; i < path.length; i++) {
      var c = cellAt(path[i][0], path[i][1]);
      if (c) c.classList.add("path-waypoint");
    }
  }

  function clearPath() {
    var wp = document.querySelectorAll(".map-cell.path-waypoint");
    for (var j = 0; j < wp.length; j++) {
      wp[j].classList.remove("path-waypoint");
    }
  }

})(window.App);