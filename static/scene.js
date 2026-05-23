/**
 * 程序化「伪远景」画面：随片区变色、星空、残骸剪影、飘尘与对话闪光。
 * 无需外部图片资源，纯 Canvas 2D。
 */

function hashSeed(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mulberry32(seed) {
  return function () {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** @typedef {{ top: string; bot: string; haze: string; wreck: string; accent: string; grid: number; ring?: boolean }} Pal */

/** @type {Record<string, Pal>} */
const PALETTES = {
  camp: {
    top: "#12081a",
    bot: "#2a1208",
    haze: "rgba(255,140,60,0.18)",
    wreck: "#1a0c18",
    accent: "rgba(255,180,90,0.35)",
    grid: 0.06,
  },
  salt: {
    top: "#050c18",
    bot: "#0a2030",
    haze: "rgba(180,230,255,0.2)",
    wreck: "#0c1828",
    accent: "rgba(120,220,255,0.25)",
    grid: 0.1,
  },
  hollow: {
    top: "#100818",
    bot: "#180828",
    haze: "rgba(255,80,200,0.12)",
    wreck: "#120a1a",
    accent: "rgba(200,120,255,0.3)",
    grid: 0.12,
    ring: true,
  },
  spire: {
    top: "#020814",
    bot: "#081028",
    haze: "rgba(80,160,255,0.15)",
    wreck: "#060a14",
    accent: "rgba(60,200,255,0.22)",
    grid: 0.14,
  },
  glass: {
    top: "#0a1018",
    bot: "#101820",
    haze: "rgba(220,235,255,0.18)",
    wreck: "#0c1218",
    accent: "rgba(255,255,255,0.2)",
    grid: 0.18,
  },
  well: {
    top: "#080510",
    bot: "#1a0a22",
    haze: "rgba(255,210,120,0.08)",
    wreck: "#0a0612",
    accent: "rgba(255,200,100,0.18)",
    grid: 0.05,
  },
};

/**
 * @param {HTMLElement} viewport
 * @param {HTMLCanvasElement} canvas
 */
export function mountScene(viewport, canvas) {
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return {
      setZone() {},
      pulse() {},
      destroy() {},
    };
  }

  let zoneId = "camp";
  /** @type {{x:number,y:number,r:number,tw:number}[]} */
  let stars = [];
  /** @type {{x:number,y:number,vx:number,vy:number,a:number}[]} */
  let dust = [];
  let flash = 0;
  let rafId = 0;
  const t0 = performance.now();

  function regenDecor() {
    const rng = mulberry32(hashSeed(zoneId + "v3"));
    stars = Array.from({ length: 96 }, () => ({
      x: rng(),
      y: rng() * 0.58,
      r: 0.35 + rng() * 1.6,
      tw: rng() * Math.PI * 2,
    }));
    dust = Array.from({ length: 48 }, () => ({
      x: rng(),
      y: 0.55 + rng() * 0.45,
      vx: (rng() - 0.5) * 0.35,
      vy: (rng() - 0.5) * 0.12,
      a: 0.08 + rng() * 0.22,
    }));
  }

  regenDecor();

  function drawSky(w, h, pal, t) {
    const g = ctx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, pal.top);
    g.addColorStop(0.55, pal.bot);
    g.addColorStop(1, "#020308");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);

    if (pal.haze) {
      const rg = ctx.createRadialGradient(w * 0.5, h * 0.2, 0, w * 0.5, h * 0.35, w * 0.65);
      rg.addColorStop(0, pal.haze);
      rg.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = rg;
      ctx.fillRect(0, 0, w, h);
    }

    for (const s of stars) {
      const tw = 0.55 + 0.45 * Math.sin(t * 1.2 + s.tw);
      ctx.fillStyle = `rgba(230,245,255,${0.15 + tw * 0.55})`;
      ctx.beginPath();
      ctx.arc(s.x * w, s.y * h, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function drawWreck(w, h, t, pal) {
    const base = h * 0.58;
    ctx.fillStyle = pal.wreck;
    ctx.beginPath();
    ctx.moveTo(-10, h + 10);
    const step = w / 28;
    for (let i = 0; i <= 28; i++) {
      const x = i * step;
      const n =
        Math.sin(i * 0.45 + t * 0.15) * 18 +
        Math.sin(i * 1.1 + hashSeed(zoneId) * 0.001) * 12 +
        Math.cos(i * 0.25 + t * 0.08) * 8;
      ctx.lineTo(x, base + n);
    }
    ctx.lineTo(w + 10, h + 10);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = `rgba(120,200,255,${0.08 + pal.grid})`;
    ctx.lineWidth = 1;
    for (let y = base + 20; y < h; y += 14) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y + 6);
      ctx.stroke();
    }

    if (pal.ring) {
      ctx.strokeStyle = pal.accent;
      ctx.globalAlpha = 0.22;
      ctx.beginPath();
      ctx.ellipse(w * 0.72, h * 0.42, w * 0.14, h * 0.05, -0.35, 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    ctx.strokeStyle = pal.accent;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(w * 0.08, base - 40);
    ctx.lineTo(w * 0.12, base - 120);
    ctx.lineTo(w * 0.22, base - 90);
    ctx.lineTo(w * 0.28, base - 140);
    ctx.stroke();
  }

  function drawDust(w, h, t) {
    for (const p of dust) {
      p.x += p.vx * 0.0018;
      p.y += p.vy * 0.0018;
      if (p.x < -0.05) p.x = 1.05;
      if (p.x > 1.05) p.x = -0.05;
      if (p.y < 0.5) p.y = 0.95;
      if (p.y > 1) p.y = 0.52;
      ctx.fillStyle = `rgba(200,220,255,${p.a * (0.7 + 0.3 * Math.sin(t + p.x * 10))})`;
      ctx.fillRect(p.x * w, p.y * h, 1.4, 1.4);
    }
  }

  function drawFlash(w, h) {
    if (flash <= 0) return;
    ctx.fillStyle = `rgba(200, 255, 255, ${flash * 0.22})`;
    ctx.fillRect(0, 0, w, h);
  }

  function frame(now) {
    const t = (now - t0) / 1000;
    flash = Math.max(0, flash - 0.045);

    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = viewport.clientWidth | 0;
    const h = viewport.clientHeight | 0;
    if (w > 8 && h > 8) {
      canvas.width = (w * dpr) | 0;
      canvas.height = (h * dpr) | 0;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const pal = PALETTES[zoneId] || PALETTES.camp;
      drawSky(w, h, pal, t);
      drawWreck(w, h, t, pal);
      drawDust(w, h, t);
      drawFlash(w, h);
    }
    rafId = requestAnimationFrame(frame);
  }

  rafId = requestAnimationFrame(frame);

  const ro = new ResizeObserver(() => {});
  ro.observe(viewport);

  return {
    /** @param {string} id */
    setZone(id) {
      const next = id && PALETTES[id] ? id : "camp";
      if (next !== zoneId) {
        zoneId = next;
        regenDecor();
      }
    },
    pulse() {
      flash = 1;
    },
    destroy() {
      cancelAnimationFrame(rafId);
      ro.disconnect();
    },
  };
}
