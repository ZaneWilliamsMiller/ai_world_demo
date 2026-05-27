// ═══════════════════════════════════════════════════════
//  map.js — Canvas 视口地图渲染 + 摄像机跟随 + 小地图
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  App._isMoving = false;

  // ═══════════════════════════════════════════
  //  常量 & 颜色
  // ═══════════════════════════════════════════
  var TILE = 20;                          // 主视口瓦片像素
  var MINI_TILE = 2;                     // 小地图瓦片像素
  var MINI_PAD = 8;                      // 小地图内边距
  var MINI_BORDER = 3;                   // 小地图边框宽

  // 地形字符 → 主色 + 可选辅助色
  var TERRAIN = {
    "#": { fill: "#261f1a", label: "城墙" },
    ".": { fill: "#3d3a36", label: "平地" },
    "~": { fill: "#1a4d80", label: "深水" },
    "=": { fill: "#595040", label: "河道" },
    "F": { fill: "#1a5c26", label: "密林" },
    "m": { fill: "#4d4026", label: "丘陵" },
    ";": { fill: "#807319", label: "花田" },
    "/": { fill: "#595040", label: "坡地" },
    "T": { fill: "#996619", label: "建筑" },
    "Y": { fill: "#1a8099", label: "塔楼" },
    "I": { fill: "#66264d", label: "牌坊" },
    "M": { fill: "#998019", label: "集市" },
    "B": { fill: "#803333", label: "军营" },
    "C": { fill: "#8c4d8c", label: "关卡" },
    "G": { fill: "#3d6633", label: "祠庙" },
    "f": { fill: "#194d80", label: "渔场" },
    "w": { fill: "#334d66", label: "码头" },
    "s": { fill: "#3d6666", label: "船坞" },
    "E": { fill: "#664d33", label: "府衙" },
    "*": { fill: "#806600", label: "宝藏" },
    " ": { fill: "#0a0a12", label: "虚空" },
  };

  function terrainColor(ch) {
    return (TERRAIN[ch] || TERRAIN[" "]).fill;
  }

  // ═══════════════════════════════════════════
  //  摄像机状态
  // ═══════════════════════════════════════════
  var cam = { x: 0, y: 0, targetX: 0, targetY: 0, lerp: 0.12 };
  var mapState = { rows: [], cols: 0, id: "" };

  // ═══════════════════════════════════════════
  //  Canvas 引用
  // ═══════════════════════════════════════════
  var mainCanvas, mainCtx;
  var miniCanvas, miniCtx;
  var viewW, viewH;             // 主视口像素尺寸
  var viewCols, viewRows;       // 主视口可见瓦片数
  var rafId = null;

  // ─── 地点标签 ───
  var _locationLabels = [];

  // ─── NPC 坐标索引 ───
  var _npcCoords = {};

  // ─── 路径动画 ───
  var _animPath = [];
  var _animIdx = 0;
  var _animTimer = null;

  // ─── 悬停瓦片 ───
  var _hoverX = -1, _hoverY = -1;

  // ═══════════════════════════════════════════
  //  初始化
  // ═══════════════════════════════════════════
  function initCanvas() {
    var container = document.getElementById("mapContainer");
    if (!container) return;

    container.innerHTML = "";

    // 主画布
    mainCanvas = document.createElement("canvas");
    mainCanvas.id = "mapCanvas";
    mainCanvas.style.display = "block";
    mainCanvas.style.cursor = "crosshair";
    container.appendChild(mainCanvas);

    // 小地图画布（叠加在主画布右上角）
    miniCanvas = document.createElement("canvas");
    miniCanvas.id = "miniMap";
    miniCanvas.style.cssText =
      "position:absolute;right:12px;bottom:12px;border:" + MINI_BORDER +
      "px solid rgba(42,58,90,0.8);border-radius:4px;cursor:pointer;z-index:5;";
    container.appendChild(miniCanvas);

    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    // 鼠标事件
    mainCanvas.addEventListener("click", onMapClick);
    mainCanvas.addEventListener("mousemove", onMapHover);
    mainCanvas.addEventListener("mouseleave", function() { _hoverX = _hoverY = -1; });
    miniCanvas.addEventListener("click", onMiniClick);
  }

  function resizeCanvas() {
    var container = document.getElementById("mapContainer");
    if (!container || !mainCanvas) return;
    viewW = container.clientWidth;
    viewH = container.clientHeight;
    mainCanvas.width = viewW;
    mainCanvas.height = viewH;
    viewCols = Math.ceil(viewW / TILE) + 1;
    viewRows = Math.ceil(viewH / TILE) + 1;

    // 小地图尺寸
    var miniW = mapState.cols * MINI_TILE;
    var miniH = mapState.rows.length * MINI_TILE;
    miniCanvas.width = miniW;
    miniCanvas.height = miniH;
  }

  // ═══════════════════════════════════════════
  //  摄像机逻辑
  // ═══════════════════════════════════════════
  function updateCameraTarget(px, py) {
    // 玩家居中 → clamp 到地图边缘
    var halfCols = viewCols / 2;
    var halfRows = viewRows / 2;
    cam.targetX = Math.max(0, Math.min(px - halfCols, mapState.cols - viewCols));
    cam.targetY = Math.max(0, Math.min(py - halfRows, mapState.rows.length - viewRows));
  }

  function lerpCamera() {
    cam.x += (cam.targetX - cam.x) * cam.lerp;
    cam.y += (cam.targetY - cam.y) * cam.lerp;
  }

  // ═══════════════════════════════════════════
  //  渲染主循环
  // ═══════════════════════════════════════════
  function renderLoop() {
    lerpCamera();
    renderMain();
    renderMini();
    rafId = requestAnimationFrame(renderLoop);
  }

  function startRender() {
    if (rafId) return;
    rafId = requestAnimationFrame(renderLoop);
  }

  function stopRender() {
    if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
  }

  // ═══════════════════════════════════════════
  //  主视口渲染
  // ═══════════════════════════════════════════
  function renderMain() {
    if (!mainCtx) return;
    var ctx = mainCtx;
    ctx.clearRect(0, 0, viewW, viewH);

    var startCol = Math.floor(cam.x);
    var startRow = Math.floor(cam.y);
    var subX = (cam.x - startCol) * TILE;
    var subY = (cam.y - startRow) * TILE;

    var px = App._playerX || 0;
    var py = App._playerY || 0;

    // 绘制瓦片
    for (var row = 0; row <= viewRows; row++) {
      var my = startRow + row;
      if (my < 0 || my >= mapState.rows.length) continue;
      var rowData = mapState.rows[my] || "";
      for (var col = 0; col <= viewCols; col++) {
        var mx = startCol + col;
        if (mx < 0 || mx >= mapState.cols) continue;
        var ch = mx < rowData.length ? rowData[mx] : " ";
        var sx = col * TILE - subX;
        var sy = row * TILE - subY;

        ctx.fillStyle = terrainColor(ch);
        ctx.fillRect(sx, sy, TILE + 1, TILE + 1);

        // NPC 标记
        var npcKey = mx + "," + my;
        if (_npcCoords[npcKey]) {
          ctx.fillStyle = "rgba(255,112,67,0.35)";
          ctx.fillRect(sx, sy, TILE, TILE);
          // 右下角小点
          ctx.fillStyle = "#ff7043";
          ctx.beginPath();
          ctx.arc(sx + TILE - 4, sy + TILE - 4, 2.5, 0, Math.PI * 2);
          ctx.fill();
        }

        // 路径标记
        if (isPathTile(mx, my)) {
          ctx.strokeStyle = "rgba(79,195,247,0.3)";
          ctx.setLineDash([2, 2]);
          ctx.lineWidth = 1;
          ctx.strokeRect(sx + 1, sy + 1, TILE - 2, TILE - 2);
          ctx.setLineDash([]);
        }

        // 悬停高亮
        if (mx === _hoverX && my === _hoverY) {
          ctx.strokeStyle = "rgba(79,195,247,0.6)";
          ctx.lineWidth = 1.5;
          ctx.strokeRect(sx + 0.5, sy + 0.5, TILE - 1, TILE - 1);
        }
      }
    }

    // ── 地点标签 ──
    ctx.font = "10px 'PingFang SC','Microsoft YaHei',sans-serif";
    ctx.textAlign = "center";
    for (var i = 0; i < _locationLabels.length; i++) {
      var loc = _locationLabels[i];
      var lx = (loc.x - cam.x) * TILE + TILE / 2;
      var ly = (loc.y - cam.y) * TILE - 6;
      if (lx < -40 || lx > viewW + 40 || ly < -10 || ly > viewH + 10) continue;
      ctx.fillStyle = "rgba(0,0,0,0.6)";
      var tw = ctx.measureText(loc.name).width;
      ctx.fillRect(lx - tw / 2 - 3, ly - 9, tw + 6, 13);
      ctx.fillStyle = "rgba(224,224,224,0.9)";
      ctx.fillText(loc.name, lx, ly);
    }

    // ── 玩家标记 ──
    var playerScreenX = (px - cam.x) * TILE + TILE / 2;
    var playerScreenY = (py - cam.y) * TILE + TILE / 2;

    // 外圈光晕
    var glowR = TILE * 0.7;
    var grd = ctx.createRadialGradient(
      playerScreenX, playerScreenY, 2,
      playerScreenX, playerScreenY, glowR);
    grd.addColorStop(0, "rgba(79,195,247,0.9)");
    grd.addColorStop(0.4, "rgba(79,195,247,0.4)");
    grd.addColorStop(1, "rgba(79,195,247,0)");
    ctx.fillStyle = grd;
    ctx.beginPath();
    ctx.arc(playerScreenX, playerScreenY, glowR, 0, Math.PI * 2);
    ctx.fill();

    // 内核
    ctx.fillStyle = "#e0f7fa";
    ctx.beginPath();
    ctx.arc(playerScreenX, playerScreenY, 3.5, 0, Math.PI * 2);
    ctx.fill();

    // 方向箭头（最近一次移动方向）
    if (App._lastDir) {
      ctx.strokeStyle = "rgba(79,195,247,0.8)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(playerScreenX, playerScreenY);
      ctx.lineTo(playerScreenX + App._lastDir.x * 8, playerScreenY + App._lastDir.y * 8);
      ctx.stroke();
    }

    // ── 动画路径高亮 ──
    if (_animPath.length > 0 && _animIdx < _animPath.length) {
      var step = _animPath[_animIdx];
      var asx = (step[0] - cam.x) * TILE + TILE / 2;
      var asy = (step[1] - cam.y) * TILE + TILE / 2;
      ctx.strokeStyle = "rgba(255,215,0,0.6)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(asx, asy, TILE * 0.4, 0, Math.PI * 2);
      ctx.stroke();
    }

    // ── 坐标显示 ──
    ctx.font = "11px 'Courier New',monospace";
    ctx.fillStyle = "rgba(136,136,170,0.7)";
    ctx.textAlign = "left";
    ctx.fillText("(" + px + ", " + py + ")", 8, viewH - 8);
  }

  // ═══════════════════════════════════════════
  //  小地图渲染
  // ═══════════════════════════════════════════
  function renderMini() {
    if (!miniCtx) return;
    var ctx = miniCtx;
    var cols = mapState.cols;
    var rows = mapState.rows.length;
    if (cols === 0 || rows === 0) return;

    ctx.clearRect(0, 0, miniCanvas.width, miniCanvas.height);

    // 绘制地形
    for (var y = 0; y < rows; y++) {
      var rowData = mapState.rows[y] || "";
      for (var x = 0; x < cols; x++) {
        var ch = x < rowData.length ? rowData[x] : " ";
        ctx.fillStyle = terrainColor(ch);
        ctx.fillRect(x * MINI_TILE, y * MINI_TILE, MINI_TILE, MINI_TILE);
      }
    }

    // NPC 点
    ctx.fillStyle = "#ff7043";
    for (var key in _npcCoords) {
      var parts = key.split(",");
      var nx = parseInt(parts[0], 10);
      var ny = parseInt(parts[1], 10);
      ctx.fillRect(nx * MINI_TILE, ny * MINI_TILE, MINI_TILE, MINI_TILE);
    }

    // 视口矩形
    ctx.strokeStyle = "rgba(79,195,247,0.8)";
    ctx.lineWidth = 1;
    ctx.strokeRect(cam.x * MINI_TILE, cam.y * MINI_TILE,
                  viewCols * MINI_TILE, viewRows * MINI_TILE);

    // 玩家点
    var px = App._playerX || 0;
    var py = App._playerY || 0;
    ctx.fillStyle = "#4fc3f7";
    ctx.fillRect(px * MINI_TILE - 1, py * MINI_TILE - 1, MINI_TILE + 2, MINI_TILE + 2);
  }

  // ═══════════════════════════════════════════
  //  鼠标交互
  // ═══════════════════════════════════════════
  function onMapClick(e) {
    var rect = mainCanvas.getBoundingClientRect();
    var mx = e.clientX - rect.left;
    var my = e.clientY - rect.top;
    var tileX = Math.floor((mx / TILE) + cam.x);
    var tileY = Math.floor((my / TILE) + cam.y);
    if (tileX < 0 || tileX >= mapState.cols || tileY < 0 || tileY >= mapState.rows.length) return;

    // NPC 点击检测
    var npcKey = tileX + "," + tileY;
    if (_npcCoords[npcKey]) {
      var npc = _npcCoords[npcKey];
      App.selectedNpcId = npc.id;
      var sel = document.getElementById("npcSelect");
      if (sel) {
        for (var i = 0; i < sel.options.length; i++) {
          if (sel.options[i].value === npc.id) {
            sel.selectedIndex = i;
            break;
          }
        }
      }
      document.getElementById("msgInput").focus();
      return;
    }

    App.moveTo(tileX, tileY);
  }

  function onMapHover(e) {
    var rect = mainCanvas.getBoundingClientRect();
    var mx = e.clientX - rect.left;
    var my = e.clientY - rect.top;
    _hoverX = Math.floor((mx / TILE) + cam.x);
    _hoverY = Math.floor((my / TILE) + cam.y);
  }

  function onMiniClick(e) {
    var rect = miniCanvas.getBoundingClientRect();
    var mx = e.clientX - rect.left;
    var my = e.clientY - rect.top;
    var tileX = Math.floor(mx / MINI_TILE);
    var tileY = Math.floor(my / MINI_TILE);
    // 点击小地图移动
    App.moveTo(tileX, tileY);
  }

  // ═══════════════════════════════════════════
  //  路径辅助
  // ═══════════════════════════════════════════
  var _pathSet = {};

  function isPathTile(x, y) {
    return _pathSet[x + "," + y] === true;
  }

  function setPath(path) {
    _pathSet = {};
    for (var i = 0; i < path.length; i++) {
      _pathSet[path[i][0] + "," + path[i][1]] = true;
    }
  }

  function clearPath() {
    _pathSet = {};
    _animPath = [];
    _animIdx = 0;
    if (_animTimer) { clearInterval(_animTimer); _animTimer = null; }
  }

  // ═══════════════════════════════════════════
  //  构建地点标签
  // ═══════════════════════════════════════════
  function buildLocationLabels() {
    _locationLabels = [];
    var locs = (App.mapsData && App.mapsData[App.currentMapId])
      ? (App.mapsData[App.currentMapId]._locations || {})
      : {};
    // 从 MAP_LOCATIONS 端口获取
    // 这些数据需要从后端传来，暂时从现有数据结构中尝试
    if (App._mapLocations) {
      var ml = App._mapLocations[App.currentMapId] || {};
      for (var name in ml) {
        var pos = ml[name];
        _locationLabels.push({ name: name, x: pos[0], y: pos[1] });
      }
    }
  }

  // ═══════════════════════════════════════════
  //  构建 NPC 索引
  // ═══════════════════════════════════════════
  function buildNpcIndex() {
    _npcCoords = {};
    (App.npcCatalog || []).forEach(function(n) {
      if (n.map === App.currentMapId && n.x !== undefined && n.y !== undefined) {
        _npcCoords[n.x + "," + n.y] = n;
      }
    });
  }

  // ═══════════════════════════════════════════
  //  公开 API
  // ═══════════════════════════════════════════
  App.renderMap = function(p) {
    var mapInfo = App.mapsData[App.currentMapId];
    if (!mapInfo) return;

    var rows = mapInfo.rows;
    var cols = rows[0] ? rows[0].length : 0;
    if (cols === 0) return;

    // 更新地图状态
    mapState.rows = rows;
    mapState.cols = cols;
    mapState.id = App.currentMapId;

    App._playerX = p.px;
    App._playerY = p.py;

    // 更新标题
    document.getElementById("mapTitle").textContent =
      "🗺️ " + (mapInfo.name || App.currentMapId);

    // 初始化 Canvas
    initCanvas();
    buildNpcIndex();
    buildLocationLabels();
    resizeCanvas();

    // 初始摄像机位置（瞬移到玩家位置）
    updateCameraTarget(p.px, p.py);
    cam.x = cam.targetX;
    cam.y = cam.targetY;

    startRender();
  };

  // ── 步行动画 ──
  App.moveTo = async function(tx, ty) {
    if (App._isMoving) return;
    App._isMoving = true;
    clearPath();

    try {
      var data = await App.doMove(tx, ty);
      var path = data.path || [];

      if (path.length === 0) {
        App.addMsg("system", "此路不通");
        App._isMoving = false;
        return;
      }

      setPath(path);

      // 逐步移动动画
      for (var i = 0; i < path.length; i++) {
        var step = path[i];
        var oldX = App._playerX, oldY = App._playerY;
        App._playerX = step[0];
        App._playerY = step[1];

        // 移动方向
        var dx = step[0] - oldX;
        var dy = step[1] - oldY;
        if (dx !== 0 || dy !== 0) {
          App._lastDir = { x: dx, y: dy };
        }

        _animIdx = i;
        updateCameraTarget(step[0], step[1]);

        // 等待摄像机接近目标
        await new Promise(function(r) { setTimeout(r, 60); });
      }

      clearPath();
      App.updateUI(data);

    } catch (e) {
      App.addMsg("system", "移动失败: " + e.message);
    }

    App._isMoving = false;
  };

  // ── 键盘控制 ──
  document.addEventListener("keydown", function(e) {
    if (!App._playerX || App._isMoving) return;
    if (document.activeElement && document.activeElement.tagName === "INPUT") return;
    if (document.activeElement && document.activeElement.tagName === "SELECT") return;

    var dx = 0, dy = 0;
    switch (e.key) {
      case "w": case "W": case "ArrowUp":    dy = -1; break;
      case "s": case "S": case "ArrowDown":  dy = 1;  break;
      case "a": case "A": case "ArrowLeft":  dx = -1; break;
      case "d": case "D": case "ArrowRight": dx = 1;  break;
      default: return;
    }
    e.preventDefault();
    App.moveTo(App._playerX + dx, App._playerY + dy);
  });

  // ── 鼠标滚轮缩放（可选） ──
  var _zoom = 1.0;
  // 保留，后续可扩展

})(window.App);
