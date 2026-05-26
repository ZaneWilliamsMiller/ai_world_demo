// ═══════════════════════════════════════════════════════
//  map.js — 地图渲染
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  /** 地形字符 → emoji/符号 */
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

  /** 渲染地图 grid */
  App.renderMap = function(p) {
    var mapInfo = App.mapsData[App.currentMapId];
    if (!mapInfo) return;

    var rows   = mapInfo.rows;
    var cols   = rows[0] ? rows[0].length : 72;
    var px     = p.px;
    var py     = p.py;

    document.getElementById("mapTitle").textContent =
      "\ud83d\uddfa\ufe0f " + (mapInfo.name || App.currentMapId);

    var container = document.getElementById("mapContainer");
    container.innerHTML = "";

    var grid = document.createElement("div");
    grid.className = "map-grid";
    grid.style.gridTemplateColumns = "repeat(" + cols + ", 16px)";

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
        if (x === px && y === py) cell.classList.add("player");
        cell.onclick = (function(tx, ty) {
          return function() { App.doMove(tx, ty).then(App.updateUI); };
        })(x, y);
        grid.appendChild(cell);
      }
    }
    container.appendChild(grid);
  };

})(window.App);