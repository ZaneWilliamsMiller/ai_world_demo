// ═══════════════════════════════════════════════════════
//  map.js — Canvas 视口地图渲染 + 摄像机跟随 + 小地图
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  App._isMoving = false;
  App._playerMarkerState = "normal";

  // ═══════════════════════════════════════════
  //  常量 & 颜色 - 全新美观配色
  // ═══════════════════════════════════════════
  var TILE = 28;                          // 主视口瓦片像素 - 更大更舒适
  var MINI_TILE = 2;                     // 小地图瓦片像素 - 缩小
  var _MINI_PAD = 8;                      // 小地图内边距
  var MINI_BORDER = 2;                   // 小地图边框宽

  // 游戏风格配色 - 肉鸽风格
  var TERRAIN = {
    "#": { fill: "#2e2845", border: "#5a50a0", label: "城墙", deco: "brick" },
    ".": { fill: "#4a4230", border: "#5e5640", label: "平地" },
    ",": { fill: "#2a5030", border: "#3a7040", label: "草地", deco: "grass" },
    "~": { fill: "#153a5e", border: "#2060a0", label: "险水", deco: "wave" },
    "=": { fill: "#1e4e6e", border: "#2a6ea0", label: "河道", deco: "wave" },
    "F": { fill: "#1a3e1e", border: "#2a5e2a", label: "密林", deco: "tree" },
    "m": { fill: "#5a4030", border: "#806050", label: "山岭", deco: "rock" },
    "/": { fill: "#4a4035", border: "#6a6055", label: "山道" },
    ";": { fill: "#3a3520", border: "#5a5540", label: "泥沼", deco: "swamp" },
    "T": { fill: "#6a5020", border: "#c09030", label: "客栈", deco: "inn" },
    "Y": { fill: "#3a4a70", border: "#5a6aa0", label: "塔楼", deco: "tower" },
    "I": { fill: "#4a3545", border: "#6a5565", label: "废墟", deco: "ruin" },
    "M": { fill: "#6a5a20", border: "#b0a030", label: "集市", deco: "market" },
    "B": { fill: "#6a3535", border: "#a05555", label: "桥梁", deco: "bridge" },
    "@": { fill: "#5a1a2a", border: "#902a3a", label: "危险", deco: "danger" },
    "!": { fill: "#3a0a0a", border: "#701a1a", label: "深渊", deco: "abyss" },
    "^": { fill: "#4a4a58", border: "#6a6a80", label: "悬崖", deco: "cliff" },
    "&": { fill: "#1a3a3a", border: "#2a5a5a", label: "伏击点" },
    " ": { fill: "#06060c", label: "虚空" },
  };

  function terrainColor(ch) {
    return (TERRAIN[ch] || TERRAIN[" "]).fill;
  }

  function _drawDeco(ctx, sx, sy, deco, fill, border) {
    var cx = sx + TILE / 2;
    var cy = sy + TILE / 2;
    ctx.save();
    switch (deco) {
      case "brick":
        ctx.strokeStyle = "rgba(120,110,180,0.35)";
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.moveTo(sx + 3, cy); ctx.lineTo(sx + TILE - 3, cy);
        ctx.moveTo(cx, sy + 3); ctx.lineTo(cx, cy);
        ctx.moveTo(sx + TILE * 0.25, cy); ctx.lineTo(sx + TILE * 0.25, sy + TILE - 3);
        ctx.moveTo(sx + TILE * 0.75, cy); ctx.lineTo(sx + TILE * 0.75, sy + TILE - 3);
        ctx.stroke();
        break;
      case "grass":
        ctx.strokeStyle = "rgba(80,160,80,0.45)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(cx - 4, sy + TILE - 4); ctx.lineTo(cx - 2, sy + TILE - 10);
        ctx.moveTo(cx, sy + TILE - 3); ctx.lineTo(cx + 1, sy + TILE - 11);
        ctx.moveTo(cx + 4, sy + TILE - 4); ctx.lineTo(cx + 3, sy + TILE - 9);
        ctx.stroke();
        break;
      case "wave":
        ctx.strokeStyle = "rgba(100,180,240,0.35)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(sx + 3, cy - 3);
        ctx.quadraticCurveTo(sx + TILE * 0.3, cy - 7, sx + TILE * 0.5, cy - 3);
        ctx.quadraticCurveTo(sx + TILE * 0.7, cy + 1, sx + TILE - 3, cy - 3);
        ctx.moveTo(sx + 5, cy + 4);
        ctx.quadraticCurveTo(sx + TILE * 0.3, cy, sx + TILE * 0.5, cy + 4);
        ctx.quadraticCurveTo(sx + TILE * 0.7, cy + 8, sx + TILE - 5, cy + 4);
        ctx.stroke();
        break;
      case "tree":
        ctx.fillStyle = "rgba(40,100,40,0.5)";
        ctx.beginPath();
        ctx.moveTo(cx, sy + 4); ctx.lineTo(cx - 6, cy + 2); ctx.lineTo(cx + 6, cy + 2);
        ctx.closePath(); ctx.fill();
        ctx.beginPath();
        ctx.moveTo(cx, sy + 8); ctx.lineTo(cx - 5, cy + 6); ctx.lineTo(cx + 5, cy + 6);
        ctx.closePath(); ctx.fill();
        ctx.fillStyle = "rgba(80,50,30,0.5)";
        ctx.fillRect(cx - 1, cy + 4, 2, TILE - cy + sy - 6);
        break;
      case "rock":
        ctx.strokeStyle = "rgba(140,120,100,0.4)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(cx - 5, sy + TILE - 5); ctx.lineTo(cx - 3, cy - 2);
        ctx.lineTo(cx + 2, sy + 5); ctx.lineTo(cx + 6, cy + 1);
        ctx.lineTo(cx + 4, sy + TILE - 5);
        ctx.stroke();
        break;
      case "swamp":
        ctx.fillStyle = "rgba(80,70,30,0.4)";
        ctx.beginPath();
        ctx.arc(cx - 3, cy, 2, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath();
        ctx.arc(cx + 4, cy + 3, 1.5, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath();
        ctx.arc(cx, cy - 4, 1, 0, Math.PI * 2); ctx.fill();
        break;
      case "inn":
        ctx.fillStyle = "rgba(220,170,50,0.6)";
        ctx.beginPath();
        ctx.moveTo(cx, sy + 3); ctx.lineTo(sx + 4, sy + 10); ctx.lineTo(sx + TILE - 4, sy + 10);
        ctx.closePath(); ctx.fill();
        ctx.fillStyle = "rgba(180,130,40,0.5)";
        ctx.fillRect(cx - 4, sy + 10, 8, TILE - 14);
        ctx.fillStyle = "rgba(255,200,80,0.7)";
        ctx.fillRect(cx - 1, sy + 12, 2, 3);
        break;
      case "tower":
        ctx.fillStyle = "rgba(90,110,170,0.5)";
        ctx.fillRect(cx - 3, sy + 6, 6, TILE - 10);
        ctx.fillStyle = "rgba(110,130,190,0.6)";
        ctx.beginPath();
        ctx.moveTo(cx, sy + 2); ctx.lineTo(cx - 5, sy + 8); ctx.lineTo(cx + 5, sy + 8);
        ctx.closePath(); ctx.fill();
        ctx.fillStyle = "rgba(200,200,240,0.5)";
        ctx.fillRect(cx - 1, sy + 10, 2, 2);
        break;
      case "ruin":
        ctx.strokeStyle = "rgba(120,90,110,0.5)";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(sx + 5, sy + TILE - 5); ctx.lineTo(sx + 5, cy);
        ctx.moveTo(sx + TILE - 5, sy + TILE - 5); ctx.lineTo(sx + TILE - 5, cy + 3);
        ctx.moveTo(sx + 4, cy); ctx.lineTo(sx + TILE - 4, cy + 3);
        ctx.stroke();
        ctx.fillStyle = "rgba(100,70,90,0.3)";
        ctx.fillRect(sx + 6, cy + 1, 4, 3);
        break;
      case "market":
        ctx.fillStyle = "rgba(200,170,40,0.5)";
        ctx.beginPath();
        ctx.moveTo(sx + 3, cy + 2); ctx.lineTo(cx, sy + 4); ctx.lineTo(sx + TILE - 3, cy + 2);
        ctx.lineTo(sx + TILE - 3, sy + TILE - 4); ctx.lineTo(sx + 3, sy + TILE - 4);
        ctx.closePath(); ctx.fill();
        ctx.fillStyle = "rgba(240,200,60,0.6)";
        ctx.fillRect(cx - 1, cy + 2, 2, TILE / 2 - 4);
        break;
      case "bridge":
        ctx.strokeStyle = "rgba(180,80,80,0.5)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(sx + 3, cy); ctx.lineTo(sx + TILE - 3, cy);
        ctx.moveTo(sx + 3, cy + 4); ctx.lineTo(sx + TILE - 3, cy + 4);
        ctx.stroke();
        ctx.strokeStyle = "rgba(160,70,70,0.4)";
        ctx.lineWidth = 1;
        for (var bi = 0; bi < 3; bi++) {
          var bx = sx + 5 + bi * 7;
          ctx.beginPath(); ctx.moveTo(bx, cy - 2); ctx.lineTo(bx, cy + 6); ctx.stroke();
        }
        break;
      case "danger":
        ctx.fillStyle = "rgba(200,40,60,0.3)";
        ctx.beginPath();
        ctx.moveTo(cx, sy + 4); ctx.lineTo(cx + 5, sy + TILE - 5); ctx.lineTo(cx - 5, sy + TILE - 5);
        ctx.closePath(); ctx.fill();
        ctx.fillStyle = "rgba(255,80,80,0.6)";
        ctx.fillRect(cx - 1, cy + 2, 2, 4);
        ctx.fillRect(cx - 0.5, cy, 1, 2);
        break;
      case "abyss":
        var ag = ctx.createRadialGradient(cx, cy, 0, cx, cy, TILE / 2);
        ag.addColorStop(0, "rgba(0,0,0,0.5)");
        ag.addColorStop(0.6, "rgba(60,10,10,0.3)");
        ag.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = ag;
        ctx.fillRect(sx, sy, TILE, TILE);
        break;
      case "cliff":
        ctx.strokeStyle = "rgba(100,100,130,0.4)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(sx + 3, sy + 4); ctx.lineTo(sx + TILE - 3, sy + TILE - 4);
        ctx.moveTo(sx + TILE - 3, sy + 4); ctx.lineTo(sx + 3, sy + TILE - 4);
        ctx.stroke();
        break;
    }
    ctx.restore();
  }

  if (typeof CanvasRenderingContext2D !== "undefined" && !CanvasRenderingContext2D.prototype.roundRect) {
    CanvasRenderingContext2D.prototype.roundRect = function(x, y, w, h, r) {
      if (typeof r === "number") r = [r, r, r, r];
      var tl = r[0] || 0, tr = r[1] || r[0] || 0, br = r[2] || r[0] || 0, bl = r[3] || r[0] || 0;
      this.moveTo(x + tl, y);
      this.lineTo(x + w - tr, y);
      this.quadraticCurveTo(x + w, y, x + w, y + tr);
      this.lineTo(x + w, y + h - br);
      this.quadraticCurveTo(x + w, y + h, x + w - br, y + h);
      this.lineTo(x + bl, y + h);
      this.quadraticCurveTo(x, y + h, x, y + h - bl);
      this.lineTo(x, y + tl);
      this.quadraticCurveTo(x, y, x + tl, y);
      this.closePath();
      return this;
    };
  }

  // ═══════════════════════════════════════════
  //  摄像机状态 - 优化平滑度
  // ═══════════════════════════════════════════
  var cam = { x: 0, y: 0, targetX: 0, targetY: 0, lerp: 0.5, snap: false };
  var mapState = { rows: [], cols: 0, id: "" };

  // ═══════════════════════════════════════════
  //  Canvas 引用
  // ═══════════════════════════════════════════
  var mainCanvas, mainCtx;
  var miniCanvas, miniCtx;
  var viewW, viewH;
  var viewCols, viewRows;

  // ─── 地点标签 ───
  var _locationLabels = [];

  // ─── NPC 坐标索引 ───
  var _npcCoords = {};

  // ─── 路径动画 ───
  var _pathSet = {};
  var _animPath = [];
  var _animIdx = 0;

  // ─── 悬停瓦片 ───
  var _hoverX = -1, _hoverY = -1;
  var _mouseScreenX = -1, _mouseScreenY = -1;
  var _pendingMove = null;

  var _dirty = true;
  var _rafId = null;
  var _resizeBound = false;
  var _keyHandler = null;

  var _npcGradientCache = {};
  var _npcGradientCacheKey = "";

  function getNpcGradient(ctx, colorKey, innerColor, outerColor) {
    var cacheKey = viewW + "x" + viewH;
    if (_npcGradientCacheKey !== cacheKey) {
      _npcGradientCache = {};
      _npcGradientCacheKey = cacheKey;
    }
    if (_npcGradientCache[colorKey]) {
      return _npcGradientCache[colorKey];
    }
    var g = ctx.createRadialGradient(
      TILE / 2, TILE / 2, 0,
      TILE / 2, TILE / 2, TILE * 0.8
    );
    g.addColorStop(0, innerColor);
    g.addColorStop(1, outerColor);
    _npcGradientCache[colorKey] = g;
    return g;
  }

  function markDirty() {
    _dirty = true;
    if (!_rafId) {
      _rafId = requestAnimationFrame(renderLoop);
    }
  }

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
      "box-shadow: 0 6px 20px rgba(0,0,0,0.45);background:rgba(10,10,20,0.7);";
    container.appendChild(miniCanvas);
    
    // 获取小地图 context
    miniCtx = miniCanvas.getContext("2d");

    resizeCanvas();
    if (!_resizeBound) {
      window.addEventListener("resize", resizeCanvas);
      _resizeBound = true;
    }

    // 鼠标事件
    mainCanvas.addEventListener("click", onMapClick);
    mainCanvas.addEventListener("mousemove", onMapHover);
    mainCanvas.addEventListener("mouseleave", function() { _hoverX = _hoverY = -1; _mouseScreenX = _mouseScreenY = -1; markDirty(); });
    miniCanvas.addEventListener("click", onMiniClick);
  }

  function resizeCanvas() {
    var container = document.getElementById("mapContainer");
    if (!container || !mainCanvas) return;
    var dpr = window.devicePixelRatio || 1;
    viewW = container.clientWidth;
    viewH = container.clientHeight;
    mainCanvas.width = Math.round(viewW * dpr);
    mainCanvas.height = Math.round(viewH * dpr);
    mainCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    viewCols = Math.ceil(viewW / TILE) + 2;
    viewRows = Math.ceil(viewH / TILE) + 2;

    var miniW = mapState.cols * MINI_TILE;
    var miniH = mapState.rows.length * MINI_TILE;
    miniCanvas.width = miniW;
    miniCanvas.height = miniH;
    markDirty();
  }

  // ═══════════════════════════════════════════
  //  摄像机逻辑
  // ═══════════════════════════════════════════
  function updateCameraTarget(px, py) {
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
    if (cam.snap) {
      cam.x = cam.targetX;
      cam.y = cam.targetY;
      cam.snap = false;
    } else {
      var dx = cam.targetX - cam.x;
      var dy = cam.targetY - cam.y;
      var dist = Math.sqrt(dx * dx + dy * dy);
      var factor;
      if (App._isMoving) {
        factor = dist > 2 ? 0.85 : dist > 0.5 ? 0.7 : 0.6;
      } else {
        factor = dist > 3 ? 0.8 : dist > 1.5 ? 0.6 : cam.lerp;
      }
      cam.x += dx * factor;
      cam.y += dy * factor;
      if (Math.abs(cam.x - cam.targetX) < 0.005) cam.x = cam.targetX;
      if (Math.abs(cam.y - cam.targetY) < 0.005) cam.y = cam.targetY;
    }
  }

  // ═══════════════════════════════════════════
  //  渲染主循环
  // ═══════════════════════════════════════════
  function renderLoop() {
    lerpCamera();
    updateHoverFromScreen();
    renderMain();
    renderMini();

    var camMoving = Math.abs(cam.x - cam.targetX) > 0.01 || Math.abs(cam.y - cam.targetY) > 0.01;
    var keepRunning = camMoving || _dirty || App._isMoving;

    if (keepRunning) {
      _dirty = false;
      _rafId = requestAnimationFrame(renderLoop);
    } else {
      _rafId = null;
    }
  }

  function _stopRender() {
    if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null; }
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

        ctx.fillStyle = tileInfo.fill;
        ctx.fillRect(sx, sy, TILE, TILE);

        if (ch !== " ") {
          var shade = ((mx + my) % 2 === 0) ? 0.03 : -0.02;
          ctx.fillStyle = "rgba(0,0,0," + (shade > 0 ? shade : 0) + ")";
          if (shade < 0) ctx.fillStyle = "rgba(255,255,255," + (-shade) + ")";
          ctx.fillRect(sx, sy, TILE, TILE);

          if (tileInfo.border) {
            ctx.strokeStyle = tileInfo.border;
            ctx.lineWidth = 0.5;
            ctx.strokeRect(sx + 0.5, sy + 0.5, TILE - 1, TILE - 1);
          }
        }

        if (tileInfo.deco) {
          _drawDeco(ctx, sx, sy, tileInfo.deco, tileInfo.fill, tileInfo.border);
        }

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
      var npcData = _npcCoords[npcKey];
      
      if (nx >= startCol && nx <= startCol + viewCols && 
          ny >= startRow && ny <= startRow + viewRows) {
        var sx = (nx - cam.x) * TILE;
        var sy = (ny - cam.y) * TILE;
        
        ctx.save();
        ctx.translate(sx, sy);

        var gradient = getNpcGradient(ctx, "npc_glow", "rgba(255,140,100,0.4)", "rgba(255,140,100,0)");
        ctx.fillStyle = gradient;
        ctx.fillRect(-TILE/3, -TILE/3, TILE * 1.7, TILE * 1.7);
        
        ctx.fillStyle = "rgba(0,0,0,0.25)";
        ctx.beginPath();
        ctx.arc(TILE/2 + 2, TILE/2 + 2, 8, 0, Math.PI * 2);
        ctx.fill();
        
        ctx.fillStyle = "#e87040";
        ctx.beginPath();
        ctx.arc(TILE/2, TILE/2, 8, 0, Math.PI * 2);
        ctx.fill();
        
        ctx.strokeStyle = "#ffd0a0";
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.fillStyle = "#fff";
        ctx.font = "bold 10px 'PingFang SC','Microsoft YaHei',sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        var npcChar = (npcData && npcData.name) ? npcData.name[0] : "人";
        ctx.fillText(npcChar, TILE/2, TILE/2 + 1);

        ctx.restore();
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

    // ─── 玩家标记 - 直接计算位置 ───
    var playerScreenX = (px - cam.x) * TILE + TILE / 2;
    var playerScreenY = (py - cam.y) * TILE + TILE / 2;

    // 玩家主体 - 更精致
    var playerFill = App._playerMarkerState === "locked" ? "#ff4444" : "#ffffff";
    var playerStroke = App._playerMarkerState === "locked" ? "#cc0000" : "#50b4ff";
    var glowColor = App._playerMarkerState === "locked" ? "rgba(255,60,60," : "rgba(80,180,255,";

    ctx.fillStyle = "rgba(0,0,0,0.3)";
    ctx.beginPath();
    ctx.arc(playerScreenX + 2, playerScreenY + 2, 8, 0, Math.PI * 2);
    ctx.fill();

    var glowR = TILE * 1.1;
    var grd = ctx.createRadialGradient(
      playerScreenX, playerScreenY, 2,
      playerScreenX, playerScreenY, glowR
    );
    grd.addColorStop(0, glowColor + "0.7)");
    grd.addColorStop(0.4, glowColor + "0.35)");
    grd.addColorStop(1, glowColor + "0)");
    ctx.fillStyle = grd;
    ctx.beginPath();
    ctx.arc(playerScreenX, playerScreenY, glowR, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = playerFill;
    ctx.beginPath();
    ctx.arc(playerScreenX, playerScreenY, 8, 0, Math.PI * 2);
    ctx.fill();
    
    ctx.strokeStyle = playerStroke;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(playerScreenX, playerScreenY, 10, 0, Math.PI * 2);
    ctx.stroke();

    ctx.fillStyle = playerStroke;
    ctx.font = "bold 11px 'PingFang SC','Microsoft YaHei',sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("侠", playerScreenX, playerScreenY + 1);

    // ─── 动画路径高亮 ───
    for (var pi = 0; pi < _animPath.length && _animIdx < _animPath.length; pi++) {
      if (pi !== _animIdx) continue;
      var step = _animPath[pi];
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
    ctx.fillText("(" + px + ", " + py + ")", viewW - 80, viewH - 16);
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

    if (App._isMoving) {
      _pendingMove = { x: tileX, y: tileY };
      return;
    }
    App.moveTo(tileX, tileY);
  }

  function onMapHover(e) {
    var rect = mainCanvas.getBoundingClientRect();
    _mouseScreenX = e.clientX - rect.left;
    _mouseScreenY = e.clientY - rect.top;
    updateHoverFromScreen();
  }

  function updateHoverFromScreen() {
    if (_mouseScreenX < 0 || _mouseScreenY < 0) return;
    var newX = Math.floor((_mouseScreenX / TILE) + cam.x);
    var newY = Math.floor((_mouseScreenY / TILE) + cam.y);
    if (newX !== _hoverX || newY !== _hoverY) {
      _hoverX = newX;
      _hoverY = newY;
      markDirty();
    }
  }

  function onMiniClick(e) {
    var rect = miniCanvas.getBoundingClientRect();
    var scaleX = miniCanvas.width / rect.width;
    var scaleY = miniCanvas.height / rect.height;
    var mx = (e.clientX - rect.left) * scaleX;
    var my = (e.clientY - rect.top) * scaleY;
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
    markDirty();
  }

  function clearPath() {
    _pathSet = {};
    _animPath = [];
    _animIdx = 0;
    markDirty();
  }

  // ═══════════════════════════════════════════
  //  构建地点标签
  // ═══════════════════════════════════════════
  function buildLocationLabels() {
    _locationLabels = [];
    var _locs = (App.mapsData && App.mapsData[App.currentMapId])
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

    var mapTitle = document.getElementById("mapTitle");
    if (mapTitle) mapTitle.textContent = "🗺️ " + (mapInfo.name || App.currentMapId);

    initCanvas();
    buildNpcIndex();
    buildLocationLabels();
    resizeCanvas();

    updateCameraTarget(p.px, p.py);
    if (isNewMap) {
      cam.snap = true;
    }
    markDirty();
  };

  // ─── 步行动画
  App.moveTo = async function(tx, ty) {
    if (App._isMoving) return;
    App._isMoving = true;

    clearPath();

    try {
      var data = await App.doMove(tx, ty);
      var path = data.path || [];

      if (path.length === 0) {
        App.addMsg("system", "此路不通");
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
        markDirty();

        await new Promise(function(r) { setTimeout(r, 50); });
      }

      clearPath();
      App.updateUI(data);

      if (data.forced_encounter && data.forced_encounter.npc_id) {
        var fe = data.forced_encounter;
        var trapType = (data.trap_state && data.trap_state.type) || "npc";
        var npcInfo = (data.npcs_here || []).find(function(n) { return n.id === fe.npc_id; });
        var npcName = npcInfo ? npcInfo.name : (fe.blurb || "对方");
        if (trapType === "environment") {
          App.addMsg("system", "🚫 身陷险境 — " + (fe.blurb || "环境凶险"), true);
        } else {
          App.addMsg("system", "🚫 身陷险局 — " + npcName + "挡住了去路！", true);
        }
        App.selectedNpcId = fe.npc_id;
        var selEl = document.getElementById("npcSelect");
        if (selEl) selEl.value = fe.npc_id;
        var autoMsg = fe.user_line || "[际遇] 狭路相逢，请开口说话。";
        setTimeout(function() {
          App.doTalk(autoMsg);
        }, 600);
      }

    } catch (e) {
      var errorMsg = e.message;
      if (errorMsg.includes("/api/move ")) {
        errorMsg = errorMsg.replace("/api/move ", "");
      }
      
      var isLockError = errorMsg.includes("🚫") || errorMsg.includes("⚠️");
      
      if (isLockError) {
        App.addMsg("system-error", errorMsg, true);
        if (App.selectedNpcId && !App.isStreaming) {
          setTimeout(function() {
            App.doTalk("[系统指令] 我要离开这里，请让我过去。");
          }, 800);
        }
      } else {
        App.addMsg("system", errorMsg);
      }
    } finally {
      App._isMoving = false;
      if (_pendingMove) {
        var next = _pendingMove;
        _pendingMove = null;
        App.moveTo(next.x, next.y);
      }
    }
  };

  // ─── 键盘控制
  _keyHandler = function(e) {
    if (!App._playerX || App._isMoving) return;
    if (document.activeElement && (document.activeElement.tagName === "INPUT" || 
        document.activeElement.tagName === "SELECT" ||
        document.activeElement.tagName === "TEXTAREA")) return;

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
  };
  document.addEventListener("keydown", _keyHandler);

  App.updatePlayerMarker = function(x, y, state) {
    App._playerMarkerState = state || "normal";
    markDirty();
  };

})(window.App);
