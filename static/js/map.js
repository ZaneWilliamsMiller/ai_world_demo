// ═══════════════════════════════════════════════════════
//  map.js — Canvas 视口地图渲染 + 摄像机跟随 + 小地图
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  App._isMoving = false;

  // ═══════════════════════════════════════════
  //  常量 & 颜色 - 全新美观配色
  // ═══════════════════════════════════════════
  var TILE = 28;                          // 主视口瓦片像素 - 更大更舒适
  var MINI_TILE = 2;                     // 小地图瓦片像素 - 缩小
  var MINI_PAD = 8;                      // 小地图内边距
  var MINI_BORDER = 2;                   // 小地图边框宽

  // 游戏风格配色 - 肉鸽风格
  var TERRAIN = {
    "#": { fill: "#2a2a4a", border: "#4a4a8a", label: "城墙" },
    ".": { fill: "#3a3a2a", border: "#4a4a3a", label: "平地" },
    ",": { fill: "#3a4a2a", border: "#4a5a3a", label: "草地" },
    "~": { fill: "#2a4a6a", border: "#3a5a7a", label: "险水" },
    "=": { fill: "#3a5a7a", border: "#4a6a8a", label: "河道" },
    "F": { fill: "#2a4a3a", border: "#3a5a4a", label: "密林" },
    "m": { fill: "#5a4a3a", border: "#6a5a4a", label: "山岭" },
    "/": { fill: "#4a3a2a", border: "#5a4a3a", label: "山道" },
    ";": { fill: "#5a3a2a", border: "#6a4a3a", label: "泥沼" },
    "T": { fill: "#6a5a3a", border: "#8a7a4a", label: "客栈" },
    "Y": { fill: "#4a5a6a", border: "#5a6a7a", label: "塔楼" },
    "I": { fill: "#5a3a5a", border: "#6a4a6a", label: "废墟" },
    "M": { fill: "#5a5a3a", border: "#6a6a4a", label: "集市" },
    "B": { fill: "#5a3a3a", border: "#6a4a4a", label: "桥梁" },
    "@": { fill: "#4a2a3a", border: "#5a3a4a", label: "危险" },
    "!": { fill: "#6a2a2a", border: "#8a3a3a", label: "深渊" },
    "^": { fill: "#4a4a5a", border: "#6a6a7a", label: "悬崖" },
    "&": { fill: "#2a3a3a", border: "#3a4a4a", label: "伏击点" },
    " ": { fill: "#0a0a12", label: "虚空" },
  };

  function terrainColor(ch) {
    return (TERRAIN[ch] || TERRAIN[" "]).fill;
  }

  // ═══════════════════════════════════════════
  //  摄像机状态 - 优化平滑度
  // ═══════════════════════════════════════════
  var cam = { x: 0, y: 0, targetX: 0, targetY: 0, lerp: 0.25 };
  var mapState = { rows: [], cols: 0, id: "" };

  // 玩家屏幕位置（带插值）- 解决玩家标记与地形割裂问题
  var playerScreen = { x: -9999, y: -9999, initialized: false };

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
  var _pathSet = {};
  var _animPath = [];
  var _animIdx = 0;
  var _animTimer = null;

  // ─── 悬停瓦片 ───
  var _hoverX = -1, _hoverY = -1;

  // ═══════════════════════════════════════════
  //  初始化 - 优化小地图位置和样式
  // ═══════════════════════════════════════════
  function initCanvas() {
    var container = document.getElementById("mapContainer");
    if (!container) return;

    if (mainCanvas && mainCanvas.parentNode === container) {
      resizeCanvas();
      return;
    }

    container.innerHTML = "";

    // 主画布
    mainCanvas = document.createElement("canvas");
    mainCanvas.id = "mapCanvas";
    mainCanvas.style.display = "block";
    mainCanvas.style.cursor = "crosshair";
    mainCanvas.style.width = "100%";
    mainCanvas.style.height = "100%";
    container.appendChild(mainCanvas);
    
    // 获取 context
    mainCtx = mainCanvas.getContext("2d");

    // 小地图画布（左上角）
    miniCanvas = document.createElement("canvas");
    miniCanvas.id = "miniMap";
    miniCanvas.style.cssText =
      "position:absolute;left:12px;top:12px;border:" + MINI_BORDER +
      "px solid rgba(80,100,140,0.9);border-radius:8px;cursor:pointer;z-index:5;" +
      "box-shadow: 0 6px 20px rgba(0,0,0,0.45);";
    container.appendChild(miniCanvas);
    
    // 获取小地图 context
    miniCtx = miniCanvas.getContext("2d");

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
    viewCols = Math.ceil(viewW / TILE) + 2;
    viewRows = Math.ceil(viewH / TILE) + 2;

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
    // 玩家居中，同时确保不超出地图边界
    var halfCols = viewCols / 2;
    var halfRows = viewRows / 2;
    
    var idealX = px - halfCols;
    var idealY = py - halfRows;
    
    var maxX = Math.max(0, mapState.cols - viewCols);
    var maxY = Math.max(0, mapState.rows.length - viewRows);
    
    cam.targetX = Math.max(0, Math.min(idealX, maxX));
    cam.targetY = Math.max(0, Math.min(idealY, maxY));
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
  //  主视口渲染 - 全新美观渲染
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

    // 绘制瓦片 - 新视觉效果
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
        var tileInfo = TERRAIN[ch] || TERRAIN[" "];

        // 绘制瓦片 - 添加细微的视觉效果
        ctx.fillStyle = tileInfo.fill;
        ctx.fillRect(sx, sy, TILE, TILE);

        // 添加深浅变化，让地图有层次感
        if (ch !== " ") {
          var shade = ((mx + my) % 2 === 0) ? 0.03 : -0.02;
          ctx.fillStyle = "rgba(0,0,0," + (shade > 0 ? shade : 0) + ")";
          if (shade < 0) ctx.fillStyle = "rgba(255,255,255," + (-shade) + ")";
          ctx.fillRect(sx, sy, TILE, TILE);
        }

        // 悬停高亮
        if (mx === _hoverX && my === _hoverY) {
          ctx.strokeStyle = "rgba(80,180,255,0.8)";
          ctx.lineWidth = 3;
          ctx.strokeRect(sx + 2, sy + 2, TILE - 4, TILE - 4);
        }
      }
    }

    // 绘制路径（在瓦片后，人物前）
    for (var row = 0; row <= viewRows; row++) {
      var my = startRow + row;
      if (my < 0 || my >= mapState.rows.length) continue;
      for (var col = 0; col <= viewCols; col++) {
        var mx = startCol + col;
        if (mx < 0 || mx >= mapState.cols) continue;
        var sx = col * TILE - subX;
        var sy = row * TILE - subY;
        
        if (isPathTile(mx, my)) {
          ctx.strokeStyle = "rgba(80,180,255,0.45)";
          ctx.setLineDash([5, 4]);
          ctx.lineWidth = 2;
          ctx.strokeRect(sx + 3, sy + 3, TILE - 6, TILE - 6);
          ctx.setLineDash([]);
        }
      }
    }

    // 绘制 NPC 标记 - 更美观的效果
    for (var npcKey in _npcCoords) {
      var parts = npcKey.split(",");
      var nx = parseInt(parts[0], 10);
      var ny = parseInt(parts[1], 10);
      
      if (nx >= startCol && nx <= startCol + viewCols && 
          ny >= startRow && ny <= startRow + viewRows) {
        var sx = (nx - cam.x) * TILE;
        var sy = (ny - cam.y) * TILE;
        
        // NPC 光晕 - 更柔和
        var gradient = ctx.createRadialGradient(
          sx + TILE/2, sy + TILE/2, 0,
          sx + TILE/2, sy + TILE/2, TILE * 0.8
        );
        gradient.addColorStop(0, "rgba(255,140,100,0.4)");
        gradient.addColorStop(1, "rgba(255,140,100,0)");
        ctx.fillStyle = gradient;
        ctx.fillRect(sx - TILE/3, sy - TILE/3, TILE * 1.7, TILE * 1.7);
        
        // NPC 投影 - 增加深度感
        ctx.fillStyle = "rgba(0,0,0,0.25)";
        ctx.beginPath();
        ctx.arc(sx + TILE/2 + 2, sy + TILE/2 + 2, 6, 0, Math.PI * 2);
        ctx.fill();
        
        // NPC 点 - 更精致
        ctx.fillStyle = "#ff8c64";
        ctx.beginPath();
        ctx.arc(sx + TILE/2, sy + TILE/2, 6, 0, Math.PI * 2);
        ctx.fill();
        
        // NPC 边框
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    }

    // ─── 地点标签 - 更美观 ───
    ctx.font = "12px 'PingFang SC','Microsoft YaHei',sans-serif";
    ctx.textAlign = "center";
    for (var i = 0; i < _locationLabels.length; i++) {
      var loc = _locationLabels[i];
      var lx = (loc.x - cam.x) * TILE + TILE / 2;
      var ly = (loc.y - cam.y) * TILE - 10;
      if (lx < -80 || lx > viewW + 80 || ly < -30 || ly > viewH + 30) continue;
      
      // 标签背景 - 更美观
      ctx.fillStyle = "rgba(15,15,30,0.75)";
      var tw = ctx.measureText(loc.name).width;
      ctx.beginPath();
      ctx.roundRect(lx - tw/2 - 12, ly - 18, tw + 24, 28, 6);
      ctx.fill();
      
      // 标签边框
      ctx.strokeStyle = "rgba(100,180,255,0.4)";
      ctx.lineWidth = 1;
      ctx.stroke();
      
      // 标签文字
      ctx.fillStyle = "#f0f0ff";
      ctx.fillText(loc.name, lx, ly + 2);
    }

    // ─── 玩家标记 - 使用插值同步摄像机 ───
    // 目标屏幕位置
    var targetPlayerSX = (px - cam.x) * TILE + TILE / 2;
    var targetPlayerSY = (py - cam.y) * TILE + TILE / 2;

    // 首次渲染时直接跳到目标位置，避免从 (0,0) 滑入的视觉跳跃
    if (!playerScreen.initialized) {
      playerScreen.x = targetPlayerSX;
      playerScreen.y = targetPlayerSY;
      playerScreen.initialized = true;
    } else {
      // 平滑插值（与摄像机相同的速度），解决玩家飘在地形上的问题
      playerScreen.x += (targetPlayerSX - playerScreen.x) * cam.lerp;
      playerScreen.y += (targetPlayerSY - playerScreen.y) * cam.lerp;
    }

    var playerScreenX = playerScreen.x;
    var playerScreenY = playerScreen.y;

    // 玩家投影 - 增加深度感
    ctx.fillStyle = "rgba(0,0,0,0.3)";
    ctx.beginPath();
    ctx.arc(playerScreenX + 2, playerScreenY + 2, 7, 0, Math.PI * 2);
    ctx.fill();

    // 外圈大光晕
    var glowR = TILE * 1.1;
    var grd = ctx.createRadialGradient(
      playerScreenX, playerScreenY, 2,
      playerScreenX, playerScreenY, glowR
    );
    grd.addColorStop(0, "rgba(80,180,255,0.7)");
    grd.addColorStop(0.4, "rgba(80,180,255,0.35)");
    grd.addColorStop(1, "rgba(80,180,255,0)");
    ctx.fillStyle = grd;
    ctx.beginPath();
    ctx.arc(playerScreenX, playerScreenY, glowR, 0, Math.PI * 2);
    ctx.fill();

    // 玩家主体 - 更精致
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(playerScreenX, playerScreenY, 7, 0, Math.PI * 2);
    ctx.fill();
    
    // 玩家外边框
    ctx.strokeStyle = "#50b4ff";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(playerScreenX, playerScreenY, 9, 0, Math.PI * 2);
    ctx.stroke();

    // 方向箭头（最近一次移动方向）
    if (App._lastDir) {
      ctx.strokeStyle = "rgba(80,180,255,0.9)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(playerScreenX, playerScreenY);
      ctx.lineTo(playerScreenX + App._lastDir.x * 14, playerScreenY + App._lastDir.y * 14);
      ctx.stroke();
    }

    // ─── 动画路径高亮 ───
    if (_animPath.length > 0 && _animIdx < _animPath.length) {
      var step = _animPath[_animIdx];
      var asx = (step[0] - cam.x) * TILE + TILE / 2;
      var asy = (step[1] - cam.y) * TILE + TILE / 2;
      ctx.strokeStyle = "rgba(255,220,80,0.8)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(asx, asy, TILE * 0.38, 0, Math.PI * 2);
      ctx.stroke();
    }

    // ─── 坐标显示 - 更简洁 ───
    ctx.font = "13px 'Courier New',monospace";
    ctx.fillStyle = "rgba(160,160,190,0.8)";
    ctx.textAlign = "left";
    ctx.fillText("(" + px + ", " + py + ")", 16, viewH - 16);
  }

  // ═══════════════════════════════════════════
  //  小地图渲染 - 优化视觉
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
    ctx.fillStyle = "#ff8c64";
    for (var key in _npcCoords) {
      var parts = key.split(",");
      var nx = parseInt(parts[0], 10);
      var ny = parseInt(parts[1], 10);
      ctx.beginPath();
      ctx.arc(nx * MINI_TILE + MINI_TILE/2, ny * MINI_TILE + MINI_TILE/2, 
              MINI_TILE * 0.45, 0, Math.PI * 2);
      ctx.fill();
    }

    // 视口矩形
    ctx.strokeStyle = "rgba(80,180,255,0.95)";
    ctx.lineWidth = 2;
    ctx.strokeRect(
      cam.x * MINI_TILE, 
      cam.y * MINI_TILE,
      viewCols * MINI_TILE, 
      viewRows * MINI_TILE
    );

    // 玩家点
    var px = App._playerX || 0;
    var py = App._playerY || 0;
    ctx.fillStyle = "#50b4ff";
    ctx.beginPath();
    ctx.arc(px * MINI_TILE + MINI_TILE/2, py * MINI_TILE + MINI_TILE/2, 
            MINI_TILE * 0.7, 0, Math.PI * 2);
    ctx.fill();
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

    // 首先尝试移动到该格子
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
    App.moveTo(tileX, tileY);
  }

  // ═══════════════════════════════════════════
  //  路径辅助
  // ═══════════════════════════════════════════
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

    var isNewMap = mapState.id !== App.currentMapId;
    mapState.rows = rows;
    mapState.cols = cols;
    mapState.id = App.currentMapId;

    App._playerX = p.px;
    App._playerY = p.py;

    document.getElementById("mapTitle").textContent =
      "🗺️ " + (mapInfo.name || App.currentMapId);

    initCanvas();
    buildNpcIndex();
    buildLocationLabels();
    resizeCanvas();

    updateCameraTarget(p.px, p.py);
    if (isNewMap) {
      cam.x = cam.targetX;
      cam.y = cam.targetY;
    }

    startRender();
  };

  // ─── 步行动画
  App.moveTo = async function(tx, ty) {
    if (App._isMoving) return;
    App._isMoving = true;
    
    // 移动期间清除悬停高亮，防止高亮残留造成视觉干扰
    _hoverX = -1;
    _hoverY = -1;
    
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

      for (var i = 0; i < path.length; i++) {
        var step = path[i];
        var oldX = App._playerX, oldY = App._playerY;
        App._playerX = step[0];
        App._playerY = step[1];

        var dx = step[0] - oldX;
        var dy = step[1] - oldY;
        if (dx !== 0 || dy !== 0) {
          App._lastDir = { x: dx, y: dy };
        }

        _animIdx = i;
        updateCameraTarget(step[0], step[1]);

        await new Promise(function(r) { setTimeout(r, 50); });
      }

      clearPath();
      App.updateUI(data);

    } catch (e) {
      var errorMsg = e.message;
      if (errorMsg.includes("/api/move ")) {
        errorMsg = errorMsg.replace("/api/move ", "");
      }
      
      var isLockError = errorMsg.includes("🚫") || errorMsg.includes("⚠️");
      
      if (isLockError) {
        App.addMsg("system-error", errorMsg, true);
        if (App.updatePlayerMarker) App.updatePlayerMarker(App._playerX, App._playerY, "locked");
      } else {
        App.addMsg("system", errorMsg);
      }
    }

    App._isMoving = false;
  };

  // ─── 键盘控制
  document.addEventListener("keydown", function(e) {
    if (!App._playerX || App._isMoving) return;
    if (document.activeElement && (document.activeElement.tagName === "INPUT" || 
        document.activeElement.tagName === "SELECT")) return;

    var dx = 0, dy = 0;
    switch (e.key) {
      case "w": case "W": case "ArrowUp":    dy = -1; break;
      case "s": case "S": case "ArrowDown":  dy = 1; break;
      case "a": case "A": case "ArrowLeft":  dx = -1; break;
      case "d": case "D": case "ArrowRight": dx = 1; break;
      default: return;
    }
    e.preventDefault();
    App.moveTo(App._playerX + dx, App._playerY + dy);
  });



})(window.App);
