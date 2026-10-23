"use strict";

// The package is served next to the page on GitHub Pages (montecarlo_pi/), and one folder up
// when the repository itself is served locally (python -m http.server, then open /web/).
const PACKAGE_FILES = ["__init__.py", "estimate.py", "simulation.py"];
const PACKAGE_FOLDERS = ["montecarlo_pi/", "../montecarlo_pi/"];

const Z95 = 1.959963984540054;
const SIGMA1 = Math.sqrt(Math.PI * (4 - Math.PI));
const DECIMALS_BUDGET = 1e10;
const WARM_UP_POINTS = 300_000;
const FRAME_MS = 16;
const BATCH_MS = 45;
const CAPTURE = 4000;
const RESOLUTION = 800;

const $ = (id) => document.getElementById(id);
const fmt = new Intl.NumberFormat("en-US");

const state = {
  python: null,
  bridge: null,
  running: false,
  finished: false,
  hasRun: false,
  batch: 25,
  total: 0,
  history: [],
  runMs: 0,
  target: 0,
  decimals: null,
};

// ---------- Loading Python ----------

async function loadPython() {
  try {
    setLoading("Starting Python…");
    const pyodide = await loadPyodide();
    setLoading("Loading NumPy…");
    await pyodide.loadPackage("numpy");

    setLoading("Loading montecarlo_pi…");
    pyodide.FS.mkdirTree("/home/pyodide/montecarlo_pi");
    const folder = await findPackageFolder();
    for (const file of PACKAGE_FILES) {
      const text = await (await fetch(folder + file)).text();
      pyodide.FS.writeFile(`/home/pyodide/montecarlo_pi/${file}`, text);
    }
    pyodide.FS.writeFile("/home/pyodide/bridge.py", await (await fetch("bridge.py")).text());

    state.python = pyodide;
    state.bridge = pyodide.pyimport("bridge");
    $("loading").hidden = true;
    $("start").disabled = false;
    setStatus("Press Start to throw the first points.");
    updateDecimalsText();
  } catch (error) {
    setLoading("Python could not be loaded. Check the connection and reload the page.");
    document.querySelector(".spinner").hidden = true;
    console.error(error);
  }
}

async function findPackageFolder() {
  for (const folder of PACKAGE_FOLDERS) {
    const response = await fetch(folder + "__init__.py", { method: "HEAD" }).catch(() => null);
    if (response?.ok) return folder;
  }
  throw new Error("montecarlo_pi package not found next to the page");
}

function setLoading(text) {
  $("loading-text").textContent = text;
}

// ---------- Settings ----------

function mode() {
  return document.querySelector('input[name="mode"]:checked').value;
}

/** Reads 1000000, 1,000,000, 1_000_000, 1e6, 2.5M or 1B. */
function parseCount(text) {
  const match = text.trim().replace(/[,_\s]/g, "").match(/^(\d+(?:\.\d+)?(?:e\d+)?)([kmb]?)$/i);
  if (!match) return null;
  const scale = { k: 1e3, m: 1e6, b: 1e9 }[match[2].toLowerCase()] ?? 1;
  const value = Number(match[1]) * scale;
  return Number.isInteger(value) && value >= 1 && value <= 1e12 ? value : null;
}

function parseSeed(text) {
  const t = text.trim();
  return t === "" ? undefined : /^\d{1,19}$/.test(t) ? t : null;
}

function decimals() {
  return Number($("decimals").value);
}

function updateDecimalsText() {
  if (!state.bridge) return;
  const d = decimals();
  $("window-text").textContent = `Stops at the first point where the estimate is in ${state.bridge.window_text(d)}.`;
  $("needed-text").textContent =
    `To be 95% sure of ${d} ${d === 1 ? "decimal" : "decimals"} you would need about ${scientific(state.bridge.points_needed(d))} points.`;
  $("fewer").disabled = d <= 1;
  $("more").disabled = d >= 7;
}

function validate() {
  const countOk = mode() === "decimals" || parseCount($("count").value) !== null;
  const seedOk = parseSeed($("seed").value) !== null;
  $("count-error").hidden = mode() === "decimals" || countOk;
  $("seed-error").hidden = seedOk;
  $("start").disabled = !state.bridge || state.running || !countOk || !seedOk;
}

// ---------- Running ----------

function start() {
  if (!state.running && (state.finished || !state.hasRun)) begin();
  state.running = true;
  state.hasRun = true;
  updateButtons();
  requestAnimationFrame(frame);
}

function begin() {
  const seed = parseSeed($("seed").value);
  const used = state.bridge.start(seed === undefined ? undefined : BigInt(seed));
  $("used-seed").textContent = `seed ${used}`;
  state.decimals = mode() === "decimals" ? decimals() : null;
  state.target = state.decimals === null ? parseCount($("count").value) : DECIMALS_BUDGET;
  state.batch = 25;
  state.total = 0;
  state.history = [];
  state.runMs = 0;
  state.finished = false;
  clearPoints();
  showEstimate(null);
}

function pause() {
  state.running = false;
  updateButtons();
  setStatus("Paused.");
}

function reset() {
  state.running = false;
  state.finished = false;
  state.hasRun = false;
  state.history = [];
  $("used-seed").textContent = "";
  $("progress").value = 0;
  clearPoints();
  showEstimate(null);
  drawChart();
  updateButtons();
  setStatus("Press Start to throw the first points.");
}

function frame() {
  if (!state.running) return;

  const remaining = state.target - state.total;
  const batch = Math.max(1, Math.min(remaining, Math.round(state.batch)));
  const started = performance.now();
  // undefined (not null) becomes None in Python.
  const result = state.bridge.step(batch, CAPTURE, state.decimals ?? undefined);
  const ms = performance.now() - started;
  state.runMs += ms;

  const [inside, total, pi, standardError, matching, matched, xyBytes, insideBytes] = result.toJs();
  result.destroy();
  const before = state.total;
  state.total = Number(total);

  drawPoints(new Float32Array(xyBytes.buffer, xyBytes.byteOffset, xyBytes.byteLength / 4), insideBytes, before);
  record(state.total, pi);
  showEstimate({ inside: Number(inside), total: state.total, pi, standardError, matching });
  drawChart();

  if (matched) return finish(`${state.decimals} ${state.decimals === 1 ? "decimal matches" : "decimals match"} after ${fmt.format(state.total)} points.`);
  if (state.total >= state.target) {
    return finish(state.decimals === null
      ? `Done: ${fmt.format(state.total)} points.`
      : `No match within ${short(DECIMALS_BUDGET)} points. Monte Carlo converges slowly.`);
  }

  setStatus(state.decimals === null
    ? `Throwing points… ${short(state.total)} of ${short(state.target)}`
    : `Looking for ${state.decimals} matching decimals… ${short(state.total)} points so far`);

  // Small, growing batches while the first points land; then batches sized from the measured speed.
  const perMs = batch / Math.max(ms, 0.25);
  if (state.total < WARM_UP_POINTS) {
    state.batch = Math.min(state.batch * 1.12, perMs * FRAME_MS);
    requestAnimationFrame(frame);
  } else {
    state.batch = Math.min(Math.max(perMs * BATCH_MS, state.batch / 2), state.batch * 8);
    setTimeout(() => requestAnimationFrame(frame), 0);
  }
}

function finish(message) {
  state.running = false;
  state.finished = true;
  if (state.decimals === null) $("progress").value = 1;
  updateButtons();
  setStatus(message);
}

function record(total, pi) {
  const last = state.history[state.history.length - 1];
  if (!last || total >= last.total * 1.03) state.history.push({ total, pi });
  else state.history[state.history.length - 1] = { total, pi };
}

function updateButtons() {
  const start = $("start");
  start.textContent = state.running ? "❚❚ Pause" : state.finished ? "▶ Run again" : state.hasRun ? "▶ Resume" : "▶ Start";
  start.classList.toggle("accent", !state.running);
  $("reset").disabled = !state.hasRun;
  $("settings").disabled = state.running || (state.hasRun && !state.finished);
  validate();
  start.disabled = start.disabled && !state.running;
}

// ---------- Drawing the points ----------

const pointsCanvas = $("points");
const pointsContext = pointsCanvas.getContext("2d");
const image = pointsContext.createImageData(RESOLUTION, RESOLUTION);
const pixels = new Uint32Array(image.data.buffer);

function clearPoints() {
  pixels.fill(0);
  pointsContext.putImageData(image, 0, 0);
}

function drawPoints(xy, inside, totalBefore) {
  const insideColor = abgr(cssColor("--inside"));
  const outsideColor = abgr(cssColor("--outside"));
  const radius = totalBefore < 20_000 ? 1 : 0;
  const last = RESOLUTION - 1;

  for (let i = 0; i < inside.length; i++) {
    const cx = Math.floor((xy[2 * i] + 1) / 2 * last);
    const cy = Math.floor((1 - xy[2 * i + 1]) / 2 * last);
    const color = inside[i] ? insideColor : outsideColor;
    for (let y = Math.max(0, cy - radius); y <= Math.min(last, cy + radius); y++) {
      for (let x = Math.max(0, cx - radius); x <= Math.min(last, cx + radius); x++) {
        pixels[y * RESOLUTION + x] = color;
      }
    }
  }
  pointsContext.putImageData(image, 0, 0);
}

function cssColor(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** "#rrggbb" as a little-endian RGBA pixel. */
function abgr(hex) {
  const n = parseInt(hex.slice(1), 16);
  return (0xff << 24) | ((n & 0xff) << 16) | (n & 0xff00) | ((n >> 16) & 0xff);
}

// ---------- The estimate ----------

function showEstimate(e) {
  if (!e) {
    $("correct").textContent = "";
    $("rest").textContent = "?.??????";
    for (const id of ["m-error", "m-interval", "m-speed"]) $(id).textContent = "—";
    for (const id of ["m-total", "m-inside", "m-matching"]) $(id).textContent = "0";
    $("m-elapsed").textContent = "0.0 s";
    return;
  }

  const digits = e.pi.toFixed(10);
  const split = e.pi >= 3 && e.pi < 4 ? 2 + Math.min(e.matching, 10) : 0;
  $("correct").textContent = digits.slice(0, split);
  $("rest").textContent = digits.slice(split);

  const error = e.pi - Math.PI;
  $("m-total").textContent = fmt.format(e.total);
  $("m-inside").textContent = fmt.format(e.inside);
  $("m-matching").textContent = e.matching;
  $("m-error").textContent = (error >= 0 ? "+" : "−") + Math.abs(error).toFixed(6);
  $("m-interval").textContent = "± " + (Z95 * e.standardError).toFixed(6);
  $("m-elapsed").textContent = (state.runMs / 1000).toFixed(1) + " s";
  $("m-speed").textContent = state.runMs > 20 ? rate(e.total / (state.runMs / 1000)) : "—";
  $("progress").value = state.decimals === null
    ? e.total / state.target
    : Math.min(1, Math.log10(e.total) / Math.log10(state.bridge.points_needed(state.decimals)));
}

function setStatus(text) {
  $("status").textContent = text;
}

// ---------- Convergence chart ----------

const chart = $("chart");

function drawChart() {
  const dpr = window.devicePixelRatio || 1;
  const width = chart.clientWidth;
  const height = chart.clientHeight;
  chart.width = Math.round(width * dpr);
  chart.height = Math.round(height * dpr);
  const g = chart.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, width, height);

  const left = 64, top = 8, bottom = 22;
  const w = width - left - 8;
  const h = height - top - bottom;
  const muted = cssColor("--muted");
  const history = state.history;
  const lastTotal = history.length ? history[history.length - 1].total : 1;
  const axisEnd = state.decimals === null ? (state.target || parseCount($("count").value) || 1e6) : state.bridge?.points_needed(state.decimals ?? decimals()) ?? 1e6;
  const maxLog = Math.max(2, Math.ceil(Math.log10(Math.max(axisEnd, lastTotal, 10))));

  let range = 0.02;
  for (const p of history) if (p.total >= 100) range = Math.max(range, Math.abs(p.pi - Math.PI));
  if (history.length) {
    const recent = Math.max(...history.filter((p) => p.total >= lastTotal / 10).map((p) => Math.abs(p.pi - Math.PI)));
    range = Math.min(range, Math.max(Math.max(recent, band(lastTotal)) * 2.2, 1e-5));
  }

  const X = (n) => left + Math.log10(Math.max(1, n)) / maxLog * w;
  const Y = (err) => top + h / 2 - Math.max(-1.05, Math.min(1.05, err / range)) * h / 2;

  g.save();
  g.beginPath();
  g.rect(left, top, w, h);
  g.clip();

  // 95% band of the theory.
  g.fillStyle = cssColor("--band");
  g.beginPath();
  const steps = 120;
  for (let i = 0; i <= steps; i++) {
    const n = 10 ** (1 + (maxLog - 1) * i / steps);
    i === 0 ? g.moveTo(X(n), Y(band(n))) : g.lineTo(X(n), Y(band(n)));
  }
  for (let i = steps; i >= 0; i--) {
    const n = 10 ** (1 + (maxLog - 1) * i / steps);
    g.lineTo(X(n), Y(-band(n)));
  }
  g.fill();

  g.strokeStyle = muted;
  g.setLineDash([4, 3]);
  g.beginPath();
  g.moveTo(left, Y(0));
  g.lineTo(left + w, Y(0));
  g.stroke();
  g.setLineDash([]);

  const accent = cssColor("--accent");
  if (history.length > 1) {
    g.strokeStyle = accent;
    g.lineWidth = 2;
    g.lineJoin = "round";
    g.beginPath();
    history.forEach((p, i) => (i === 0 ? g.moveTo(X(p.total), Y(p.pi - Math.PI)) : g.lineTo(X(p.total), Y(p.pi - Math.PI))));
    g.stroke();
  }
  if (history.length) {
    const p = history[history.length - 1];
    g.fillStyle = accent;
    g.beginPath();
    g.arc(X(p.total), Y(p.pi - Math.PI), 4, 0, 2 * Math.PI);
    g.fill();
  }
  g.restore();

  // Axes and labels.
  g.strokeStyle = cssColor("--stroke");
  g.lineWidth = 1;
  g.beginPath();
  g.moveTo(left, top + h);
  g.lineTo(left + w, top + h);
  g.stroke();

  g.fillStyle = muted;
  g.font = "11px 'Segoe UI', system-ui, sans-serif";
  g.textBaseline = "top";
  for (let p = 1; p <= maxLog; p++) {
    if (p % (maxLog > 8 ? 2 : 1) && p !== maxLog) continue;
    const label = short(10 ** p);
    g.fillText(label, Math.min(X(10 ** p) - g.measureText(label).width / 2, width - g.measureText(label).width), top + h + 5);
  }

  const label = (err) => (err > 0 ? "π + " : "π − ") + (range < 0.001 ? Math.abs(err).toExponential(1) : +Math.abs(err).toFixed(4));
  g.textAlign = "right";
  g.textBaseline = "top";
  g.fillText(label(range), left - 8, top);
  g.textBaseline = "middle";
  g.fillText("π", left - 8, Y(0));
  g.textBaseline = "bottom";
  g.fillText(label(-range), left - 8, top + h);
  g.textAlign = "left";
}

function band(n) {
  return Z95 * SIGMA1 / Math.sqrt(n);
}

// ---------- Number formatting ----------

function short(n) {
  if (n >= 1e9) return +(n / 1e9).toFixed(1) + "B";
  if (n >= 1e6) return +(n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return +(n / 1e3).toFixed(1) + "K";
  return String(n);
}

function rate(perSecond) {
  if (perSecond >= 1e6) return (perSecond / 1e6).toFixed(1) + " M/s";
  if (perSecond >= 1e3) return (perSecond / 1e3).toFixed(1) + " K/s";
  return perSecond.toFixed(0) + " /s";
}

function scientific(n) {
  if (n < 1000) return n.toFixed(0);
  const exponent = Math.floor(Math.log10(n));
  const superscript = String(exponent).replace(/\d/g, (d) => "⁰¹²³⁴⁵⁶⁷⁸⁹"[d]);
  return `${+(n / 10 ** exponent).toFixed(1)} × 10${superscript}`;
}

// ---------- Wiring ----------

$("start").addEventListener("click", () => (state.running ? pause() : start()));
$("reset").addEventListener("click", reset);
document.querySelectorAll('input[name="mode"]').forEach((radio) =>
  radio.addEventListener("change", () => {
    $("points-mode").hidden = mode() !== "points";
    $("decimals-mode").hidden = mode() !== "decimals";
    validate();
    drawChart();
  }));
document.querySelectorAll("[data-count]").forEach((chip) =>
  chip.addEventListener("click", () => {
    $("count").value = fmt.format(Number(chip.dataset.count));
    validate();
    drawChart();
  }));
$("count").addEventListener("input", () => { validate(); drawChart(); });
$("seed").addEventListener("input", validate);
$("fewer").addEventListener("click", () => { $("decimals").value = Math.max(1, decimals() - 1); updateDecimalsText(); drawChart(); });
$("more").addEventListener("click", () => { $("decimals").value = Math.min(7, decimals() + 1); updateDecimalsText(); drawChart(); });
document.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && !$("start").disabled) $("start").click();
});
window.addEventListener("resize", drawChart);
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", drawChart);

clearPoints();
drawChart();
loadPython();
