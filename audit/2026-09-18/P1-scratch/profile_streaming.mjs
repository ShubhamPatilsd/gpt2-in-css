// P1 audit: profile tinystories streaming-packed8 generation in Chrome via Playwright + CDP.
// Uses the same node + playwright + Chrome the repo's tools/*.mjs harnesses use. No repo files are modified.
import fs from "node:fs/promises";
import zlib from "node:zlib";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const url = process.env.P1_URL;
const label = process.env.P1_LABEL ?? "run";
const trace = process.env.P1_TRACE === "1";
const headless = process.env.P1_HEADFUL !== "1";
const outDir = "/Users/shubhampatil/Documents/programming/gpt2-css/audit/2026-09-18/P1-scratch";
const genTimeoutMs = Number(process.env.P1_GEN_TIMEOUT_MS ?? 120000);
const expectedGates = Number(process.env.P1_EXPECTED_GATES ?? 16); // handoffs 1..15 gate stages 2..16; handoff 16 = completion-marker
const prePlayProbes = process.env.P1_PRE_PROBES !== "0";
const postProbes = process.env.P1_POST_PROBES !== "0";
const t0 = performance.now();
const now = () => Math.round((performance.now() - t0) * 10) / 10;
const timeline = [];
const log = (event, extra = {}) => { const row = { t: now(), event, ...extra }; timeline.push(row); console.log(JSON.stringify(row)); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch({ executablePath, headless, args: ["--disable-background-timer-throttling", "--disable-renderer-backgrounding"] });
const browserCdp = await browser.newBrowserCDPSession();
async function procInfo() { const { processInfo } = await browserCdp.send("SystemInfo.getProcessInfo"); return processInfo; }
const browserPid = (await procInfo()).find((p) => p.type === "browser")?.id;
const version = browser.version();
log("launched", { browserPid, version, headless, url, trace });
const context = await browser.newContext({ viewport: { width: 1000, height: 800 } });
const page = await context.newPage();
const cdp = await context.newCDPSession(page);
await cdp.send("Performance.enable", { timeDomain: "timeTicks" });
const noAnim = process.env.P1_NO_ANIM === "1";
if (!noAnim) await cdp.send("Animation.enable");
const animEvents = [];
cdp.on("Animation.animationCreated", (e) => animEvents.push({ t: now(), kind: "created", id: e.id }));
cdp.on("Animation.animationStarted", (e) => {
  const a = e.animation;
  animEvents.push({ t: now(), kind: "started", id: a.id, name: a.name, type: a.type, playState: a.playState, startTime: a.startTime, node: a.source?.backendNodeId, keyframes: a.source?.keyframesRule?.name });
});

// ---- samplers -------------------------------------------------------------
let procCache = [];
async function refreshProcs() { try { procCache = await procInfo(); } catch {} }
function rendererProcs() {
  const pids = procCache.map((p) => p.id).filter(Boolean);
  if (!pids.length) return [];
  const out = execSync(`ps -o pid=,rss= -p ${pids.join(",")}`).toString();
  const rss = new Map();
  for (const line of out.split("\n")) { const m = line.match(/^\s*(\d+)\s+(\d+)/); if (m) rss.set(Number(m[1]), Math.round(Number(m[2]) / 1024)); }
  return procCache.map((p) => ({ pid: p.id, type: p.type, rssMB: rss.get(p.id) ?? 0 }));
}
function browserRssMB() {
  try { return Math.round(Number(execSync(`ps -o rss= -p ${browserPid}`).toString().trim()) / 1024); } catch { return null; }
}
const rssSamples = [];
let phase = "launch";
const rssTimer = setInterval(async () => {
  try {
    await refreshProcs();
    const procs = rendererProcs();
    const renderers = procs.filter((p) => p.type === "renderer");
    rssSamples.push({ t: now(), phase, browserMB: browserRssMB(), rendererMaxMB: Math.max(0, ...renderers.map((p) => p.rssMB)), rendererSumMB: renderers.reduce((s, p) => s + p.rssMB, 0), gpuMB: procs.filter((p) => p.type === "GPU").reduce((s, p) => s + p.rssMB, 0), renderers: renderers.length });
  } catch (e) { rssSamples.push({ t: now(), phase, error: String(e) }); }
}, 1000);

async function metrics() {
  const tReq = now();
  const { metrics } = await cdp.send("Performance.getMetrics");
  const o = { tReq, tResp: now(), phase };
  for (const m of metrics) o[m.name] = m.value;
  return o;
}
const metricSamples = [];
let sampling = true;
(async () => { while (sampling) { try { metricSamples.push(await metrics()); } catch (e) { break; } await sleep(200); } })();

// ---- tracing --------------------------------------------------------------
const categories = ["blink", "blink.animations", "blink.user_timing", "blink_style", "blink.style", "devtools.timeline", "disabled-by-default-devtools.timeline", "disabled-by-default-devtools.timeline.frame", "v8", "disabled-by-default-v8.gc", "cc", "loading", "disabled-by-default-blink.debug"];
if (trace) { await browser.startTracing(page, { categories, screenshots: false }); log("tracing-started", { categories }); }

// ---- load -----------------------------------------------------------------
phase = "load";
const tNav0 = now();
log("goto");
await page.goto(url, { waitUntil: "load", timeout: 900000 });
const tLoad = now();
log("load-event", { loadMs: tLoad - tNav0 });
const navInfo = await page.evaluate(() => ({
  nav: performance.getEntriesByType("navigation")[0]?.toJSON(),
  resources: performance.getEntriesByType("resource").map((r) => ({ name: r.name.replace(location.origin, ""), startTime: r.startTime, responseEnd: r.responseEnd, duration: r.duration, encodedBodySize: r.encodedBodySize, decodedBodySize: r.decodedBodySize, transferSize: r.transferSize })),
  paint: performance.getEntriesByType("paint").map((p) => ({ name: p.name, startTime: p.startTime })),
  styleSheets: Array.from(document.styleSheets).map((s) => { let n = null; try { n = s.cssRules.length; } catch {} return { href: s.href && s.href.replace(location.origin, ""), rules: n }; }),
  scripts: document.querySelectorAll("script").length,
}));
log("nav-info", navInfo);
await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
const tFirstFrame = now();
log("two-raf-after-load", { sinceNav: tFirstFrame - tNav0 });
const mAfterLoad = await metrics();
log("metrics-after-load", mAfterLoad);
// wait for paused idle: RecalcStyleCount unchanged for 1.5 s
phase = "paused-idle";
{ let last = mAfterLoad.RecalcStyleCount, stableSince = now(); while (now() - stableSince < 1500) { await sleep(250); const m = await metrics(); if (m.RecalcStyleCount !== last) { last = m.RecalcStyleCount; stableSince = now(); } } }
const tPausedIdle = now();
const stage1 = await page.evaluate(() => { const m = document.querySelector('.model[data-step="1"]'); const o = m.querySelector(":scope > .token-output"); return { winner: getComputedStyle(m).getPropertyValue("--winner-id"), piece: getComputedStyle(o, "::after").content, paused: document.getElementById("pause-generation")?.checked ?? null, h1: (() => { const h = document.querySelector(".handoff[data-after-token=\"1\"]"); if (!h) return null; const cs = getComputedStyle(h); return { gateOpen: cs.getPropertyValue("--gate-open"), cv: cs.contentVisibility, anim: cs.animationName }; })() }; });
log("paused-idle", { sinceNav: tPausedIdle - tNav0, stage1, animEventsSoFar: animEvents.length });
const mPausedIdle = await metrics();

// ---- probes ---------------------------------------------------------------
const probeResults = [];
async function probe(name, fn, repeat = 2) {
  for (let i = 0; i < repeat; i++) {
    const before = await metrics();
    const inPage = await page.evaluate(fn, i);
    const after = await metrics();
    const row = { name, iteration: i, inPageMs: inPage.ms, inPageValue: inPage.value, dRecalcStyleMs: Math.round((after.RecalcStyleDuration - before.RecalcStyleDuration) * 1e4) / 10, dRecalcCount: after.RecalcStyleCount - before.RecalcStyleCount, dLayoutMs: Math.round((after.LayoutDuration - before.LayoutDuration) * 1e4) / 10, dLayoutCount: after.LayoutCount - before.LayoutCount, dScriptMs: Math.round((after.ScriptDuration - before.ScriptDuration) * 1e4) / 10 };
    probeResults.push(row); log("probe", row);
    await sleep(300);
  }
}
const probeSet = (stepForModel) => [
  ["noop-body-attr", (i) => { const b = document.body; const s = performance.now(); b.setAttribute("data-p1", "x" + i); const v = getComputedStyle(b).color; return { ms: performance.now() - s, value: v }; }],
  ["body-inline-color", (i) => { const b = document.body; const s = performance.now(); b.style.color = `rgb(${10 + i},20,30)`; const v = getComputedStyle(b).color; return { ms: performance.now() - s, value: v }; }],
  [`stage${stepForModel}-token-output-unrelated-custom-prop`, (i, step = stepForModel) => { const o = document.querySelector(`.model[data-step="${step}"] > .token-output`); const s = performance.now(); o.style.setProperty("--p1-probe", String(i + 1)); const v = getComputedStyle(o).getPropertyValue("--p1-probe"); return { ms: performance.now() - s, value: v }; }],
  [`stage${stepForModel}-model-unrelated-custom-prop`, (i, step = stepForModel) => { const m = document.querySelector(`.model[data-step="${step}"]`); const s = performance.now(); m.style.setProperty("--p1-probe", String(i + 1)); const v = getComputedStyle(m).getPropertyValue("--p1-probe"); return { ms: performance.now() - s, value: v }; }],
  [`stage${stepForModel}-model-winner-override`, (i, step = stepForModel) => { const m = document.querySelector(`.model[data-step="${step}"]`); const o = m.querySelector(":scope > .token-output"); const s = performance.now(); m.style.setProperty("--winner-id", String(612 + i)); const v = getComputedStyle(o, "::after").content; return { ms: performance.now() - s, value: v }; }],
  [`stage${stepForModel}-model-winner-restore`, (i, step = stepForModel) => { const m = document.querySelector(`.model[data-step="${step}"]`); const o = m.querySelector(":scope > .token-output"); const s = performance.now(); m.style.removeProperty("--winner-id"); const v = getComputedStyle(o, "::after").content; return { ms: performance.now() - s, value: v }; }],
];
// NOTE: probe fns receive (i) only; step is baked via closure default param evaluated in page -> pass step explicitly instead
async function runProbeSet(step, includeBodyCustomProp) {
  for (const [name, fn] of probeSet(step)) {
    if (process.env.P1_SKIP_BODY_COLOR === "1" && name === "body-inline-color") continue;
    if (process.env.P1_SAMPLE_BODY === "1" && name === "body-inline-color" && phase === "probes-after") {
      await refreshProcs(); const r = rendererProcs().filter((p) => p.type === "renderer").sort((a, b) => b.rssMB - a.rssMB)[0];
      if (r) { const { spawn } = await import("node:child_process"); const file = `${outDir}/${label}-renderer-sample.txt`; const child = spawn("sample", [String(r.pid), "10", "1", "-file", file], { stdio: "ignore", detached: true }); child.unref(); log("native-sample-started", { pid: r.pid, file }); await sleep(300); }
    }
    const wrapped = new Function("i", `return (${fn.toString()})(i, ${step});`);
    await probe(name, wrapped, name.includes("restore") ? 1 : 2);
  }
  if (includeBodyCustomProp) await probe("body-inline-inherited-custom-prop", (i) => { const b = document.body; const s = performance.now(); b.style.setProperty("--p1-probe-body", String(i + 1)); const v = getComputedStyle(b).getPropertyValue("--p1-probe-body"); return { ms: performance.now() - s, value: v }; }, 2);
}
if (prePlayProbes) { phase = "probes-paused"; log("probes-paused-start"); await runProbeSet(1, true); log("probes-paused-end"); }

// ---- play -----------------------------------------------------------------
phase = "generate";
const mBeforePlay = await metrics();
await page.evaluate(() => performance.mark("P1-play"));
const animBeforePlay = animEvents.length;
const tPlay = now();
const noPlay = process.env.P1_NO_PLAY === "1";
if (!noPlay) { await page.click(".pause-control"); log("play-clicked"); } else { log("no-play-mode (page has no pause control; all stages resolved during load)"); }
let gates = [];
const deadline = tPlay + genTimeoutMs;
let tLastRecalcChange = null;
if (noPlay) {
  gates = [];
} else if (noAnim) {
  // no Animation domain: detect completion as RecalcStyleCount stable for 2.5 s; the getMetrics reply is blocked while a recalc runs, so tResp ~= end of the last recalc
  let last = mBeforePlay.RecalcStyleCount; tLastRecalcChange = now();
  while (now() < deadline) { const m = await metrics(); if (m.RecalcStyleCount !== last) { last = m.RecalcStyleCount; tLastRecalcChange = m.tResp; gates.push({ t: m.tResp, kind: "recalc-count-change", count: m.RecalcStyleCount, recalcMs: m.RecalcStyleDuration * 1000 }); } if (now() - tLastRecalcChange > 2500) break; await sleep(100); }
} else {
  while (now() < deadline) {
    gates = animEvents.filter((e) => e.kind === "started" && e.t >= tPlay);
    if (gates.length >= expectedGates) break;
    await sleep(50);
  }
}
const tLastGate = gates.length ? gates[gates.length - 1].t : null;
log("gates-observed", { count: gates.length, expected: expectedGates, tLastGateSincePlay: tLastGate && tLastGate - tPlay, timedOut: gates.length < expectedGates });
// wait for the frame after the last stage's style/paint
await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
const tDone = noPlay ? tPlay : (noAnim ? tLastRecalcChange : now());
await page.evaluate(() => performance.mark("P1-done"));
const mAfterGen = await metrics();
const finalState = await page.evaluate(() => Array.from(document.querySelectorAll(".model")).map((m) => { const o = m.querySelector(":scope > .token-output"); const h = m.querySelector(":scope > .handoff"); return { step: m.dataset.step, winner: getComputedStyle(m).getPropertyValue("--winner-id"), piece: getComputedStyle(o, "::after").content, gateOpen: h && getComputedStyle(h).getPropertyValue("--gate-open"), cv: h && getComputedStyle(h).contentVisibility }; }));
log("generation-done", { sincePlayMs: tDone - tPlay, gates: gates.length, finalState });
await page.screenshot({ path: `${outDir}/${label}-final.png` });
// idle check: 3 s with nothing happening
phase = "idle-after";
const mIdle0 = await metrics(); await sleep(3000); const mIdle1 = await metrics();
log("idle-after-3s", { dRecalcCount: mIdle1.RecalcStyleCount - mIdle0.RecalcStyleCount, dRecalcMs: (mIdle1.RecalcStyleDuration - mIdle0.RecalcStyleDuration) * 1000, dLayoutCount: mIdle1.LayoutCount - mIdle0.LayoutCount });
if (postProbes) { phase = "probes-after"; log("probes-after-start"); await runProbeSet(16, process.env.P1_POST_BODY_CUSTOM === "1"); log("probes-after-end"); }

// ---- finish ---------------------------------------------------------------
phase = "finish";
let tracePath = null;
if (trace) { const buf = await browser.stopTracing(); tracePath = `${outDir}/${label}-trace.json.gz`; await fs.writeFile(tracePath, zlib.gzipSync(buf)); log("trace-saved", { bytes: buf.length, tracePath }); }
sampling = false; clearInterval(rssTimer);
const result = { label, url, version, headless, node: process.version, executablePath, tNav0, tLoad, tFirstFrame, tPausedIdle, tPlay, tLastGate, tDone, generationMs: tDone - tPlay, gates, animEvents, mAfterLoad, mPausedIdle, mBeforePlay, mAfterGen, probeResults, metricSamples, rssSamples, timeline, navInfo, finalState, tracePath };
await fs.writeFile(`${outDir}/${label}.json`, JSON.stringify(result, null, 1));
log("saved", { file: `${outDir}/${label}.json` });
await browser.close();
