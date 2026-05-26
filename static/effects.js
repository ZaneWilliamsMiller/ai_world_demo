/**
 * Effects Module - Weather and ambient effects on the map viewport.
 * Adds rain, fog, night shading, and animated ambient layers to the map.
 */
import { store } from "../store.js";
import { el } from "./ui/utils.js";

let _overlay = null;
let _active = false;
let _animFrame = null;
let _particles = [];
let _canvas = null;
let _ctx = null;

const RAIN_PARTICLE_COUNT = 80;

export function initEffects() {
  const host = el("mapHost");
  if (!host) return;

  if (!_overlay) {
    _overlay = document.createElement("div");
    _overlay.className = "weather-overlay";
    host.appendChild(_overlay);
  }

  if (!_canvas) {
    _canvas = document.createElement("canvas");
    _canvas.style.cssText = "position:absolute;inset:0;pointer-events:none;border-radius:12px;z-index:1;";
    _canvas.width = 600;
    _canvas.height = 400;
    host.appendChild(_canvas);
    _ctx = _canvas.getContext("2d");
  }

  // Listen for state changes to update weather
  store.subscribe((state) => {
    if (!_active) return;
    updateWeatherClass(state.player?.weather, state.player?.world_is_night);
  });

  requestAnimationFrame(animationLoop);
  _active = true;
}

export function destroyEffects() {
  _active = false;
  if (_animFrame) cancelAnimationFrame(_animFrame);
  if (_overlay) { _overlay.remove(); _overlay = null; }
  if (_canvas) { _canvas.remove(); _canvas = null; _ctx = null; }
}

function updateWeatherClass(weather, isNight) {
  if (!_overlay) return;
  const host = el("mapHost");
  if (!host) return;

  host.classList.remove("weather-rain", "weather-fog", "weather-night");
  _particles = [];

  if (!weather) return;
  const w = weather.toLowerCase();

  if (w.includes("雨")) {
    host.classList.add("weather-rain");
    initRain();
  } else if (w.includes("雾") || w.includes("霾") || w.includes("烟")) {
    host.classList.add("weather-fog");
  } else if (w.includes("沙")) {
    // Light sandstorm: fewer sparse dust particles
    initDust();
    host.style.setProperty("--weather-tint", "rgba(180,140,100,0.08)");
  }

  if (isNight) {
    host.classList.add("weather-night");
  } else {
    host.style.removeProperty("--weather-tint");
  }
}

function initRain() {
  _particles = [];
  if (!_canvas) return;
  for (let i = 0; i < RAIN_PARTICLE_COUNT; i++) {
    _particles.push({
      x: Math.random() * _canvas.width,
      y: Math.random() * _canvas.height,
      speed: 3 + Math.random() * 7,
      len: 4 + Math.random() * 8,
      opacity: 0.15 + Math.random() * 0.3,
    });
  }
}

function initDust() {
  _particles = [];
  if (!_canvas) return;
  for (let i = 0; i < 25; i++) {
    _particles.push({
      x: Math.random() * _canvas.width,
      y: Math.random() * _canvas.height,
      vx: 0.5 + Math.random() * 1.5,
      vy: -0.3 + Math.random() * 0.6,
      r: 1 + Math.random() * 2,
      opacity: 0.12 + Math.random() * 0.18,
    });
  }
}

function animationLoop() {
  if (!_active) return;
  updateCanvasSize();
  drawParticles();
  _animFrame = requestAnimationFrame(animationLoop);
}

function updateCanvasSize() {
  if (!_canvas) return;
  const host = el("mapHost");
  if (!host) return;
  const w = host.clientWidth || 600;
  const h = host.clientHeight || 400;
  if (_canvas.width !== w || _canvas.height !== h) {
    _canvas.width = w;
    _canvas.height = h;
    // Rebuild particles on resize
    if (_particles.length) {
      initRain();
    }
  }
}

function drawParticles() {
  if (!_ctx || !_canvas || !_particles.length) return;
  const w = _canvas.width;
  const h = _canvas.height;

  _ctx.clearRect(0, 0, w, h);

  for (const p of _particles) {
    // Rain particles
    if (p.speed !== undefined) {
      _ctx.beginPath();
      _ctx.moveTo(p.x, p.y);
      _ctx.lineTo(p.x + 1, p.y + p.len);
      _ctx.strokeStyle = `rgba(160,200,230,${p.opacity})`;
      _ctx.lineWidth = 1;
      _ctx.stroke();

      p.y += p.speed;
      if (p.y > h) {
        p.y = -p.len;
        p.x = Math.random() * w;
      }
    } else {
      // Dust particles
      _ctx.beginPath();
      _ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      _ctx.fillStyle = `rgba(180,140,100,${p.opacity})`;
      _ctx.fill();

      p.x += p.vx;
      p.y += p.vy;
      if (p.x > w + 5) p.x = -5;
      if (p.x < -5) p.x = w + 5;
      if (p.y > h + 5) p.y = -5;
      if (p.y < -5) p.y = h + 5;
    }
  }
}