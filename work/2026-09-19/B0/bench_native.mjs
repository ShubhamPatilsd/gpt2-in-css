// P2 audit: PASSIVE Chromium trace of the validated no-JS GPT-2 bundle (demo-font-vector-twelve).
// Same node + playwright + Chrome as the repo's tools/*.mjs. Nothing in the repo is modified.
// Passive = after the single Run click there are NO forced style/geometry reads (no getBoundingClientRect,
// getComputedStyle, DOM.getBoxModel, CSS.getComputedStyleForNode) until the run is over. Only:
//   Performance.getMetrics (1 Hz; a pure counter read; blocked while the main thread is busy),
//   DOM.querySelector on a completion marker every 5 s (DOM-only selector match, no style),
//   ps RSS at 1 Hz, Tracing.bufferUsage events.
import fs from "node:fs";
import fsp from "node:fs/promises";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

// B0 bench copy of audit/2026-09-18/P2-scratch/trace_native.mjs. Changes: env-driven outDir / heap flag /
// trace categories, and passive per-token boundary detection (DOM.querySelector on #token-N-captured.done at 1 Hz).
const url = process.env.B0_URL;
const label = process.env.B0_LABEL ?? "run";
const outDir = process.env.B0_OUT;
if (!url || !outDir) throw new Error("B0_URL and B0_OUT are required");
const capMs = Number(process.env.B0_CAP_MS ?? 600000); // hard cap measured from navigation start
const invalidation = process.env.B0_INVALIDATION === "1"; // light trace by default
const heapFlag = process.env.B0_HEAP !== "0"; // "1" = Codex's --js-flags=--heap-growing-percent=10
const bufferKb = Number(process.env.B0_BUFFER_KB ?? 1500000);
const capacity = Number(process.env.B0_CAPACITY ?? 8);
const t0 = performance.now();
const now = () => Math.round((performance.now() - t0) * 10) / 10;
const timeline = [];
const log = (event, extra = {}) => { const row = { t: now(), event, ...extra }; timeline.push(row); console.log(JSON.stringify(row)); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const args = [
  "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
  "--force-device-scale-factor=1", "--hide-scrollbars",
  "--disable-background-networking", "--disable-component-update",
];
if (heapFlag) args.push("--js-flags=--heap-growing-percent=10"); // same as the validated runs (browserArguments in pipeline-results.json)
const browser = await chromium.launch({ executablePath, headless: true, args });
const browserCdp = await browser.newBrowserCDPSession();
async function procInfo() { const { processInfo } = await browserCdp.send("SystemInfo.getProcessInfo"); return processInfo; }
const browserPid = (await procInfo()).find((p) => p.type === "browser")?.id;
log("launched", { browserPid, version: browser.version(), url, args, heapFlag, invalidation, bufferKb, capMs });
const context = await browser.newContext({ viewport: { width: 900, height: 300 } });
const page = await context.newPage();
const cdp = await context.newCDPSession(page);
await cdp.send("Performance.enable", { timeDomain: "timeTicks" });
await cdp.send("DOM.enable");

// ---- samplers -------------------------------------------------------------
let procCache = [];
async function refreshProcs() { try { procCache = await procInfo(); } catch {} }
function procRss() {
  const pids = procCache.map((p) => p.id).filter(Boolean);
  if (!pids.length) return [];
  const out = execSync(`ps -o pid=,rss= -p ${pids.join(",")}`).toString();
  const rss = new Map();
  for (const line of out.split("\n")) { const m = line.match(/^\s*(\d+)\s+(\d+)/); if (m) rss.set(Number(m[1]), Math.round(Number(m[2]) / 1024)); }
  return procCache.map((p) => ({ pid: p.id, type: p.type, rssMB: rss.get(p.id) ?? 0 }));
}
const rssSamples = [];
let phase = "launch";
const rssTimer = setInterval(async () => {
  try {
    await refreshProcs();
    const procs = procRss();
    const renderers = procs.filter((p) => p.type === "renderer");
    rssSamples.push({ t: now(), phase, browserMB: procs.filter((p) => p.type === "browser").reduce((s, p) => s + p.rssMB, 0), rendererMaxMB: Math.max(0, ...renderers.map((p) => p.rssMB)), rendererSumMB: renderers.reduce((s, p) => s + p.rssMB, 0), gpuMB: procs.filter((p) => p.type === "GPU").reduce((s, p) => s + p.rssMB, 0), utilityMB: procs.filter((p) => p.type === "utility").reduce((s, p) => s + p.rssMB, 0), renderers: renderers.length });
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
(async () => { while (sampling) { try { metricSamples.push(await metrics()); } catch (e) { break; } await sleep(1000); } })();

// ---- tracing (raw CDP, streamed + gzip-compressed by Chrome, never held in memory) -----------
const categories = ["blink", "blink.style", "blink.animations", "blink.user_timing", "devtools.timeline", "disabled-by-default-devtools.timeline", "cc", "loading", "v8.gc"];
if (invalidation) categories.push("disabled-by-default-devtools.timeline.invalidationTracking");
for (const c of (process.env.B0_DROP_CATS ?? "").split(",").filter(Boolean)) { const i = categories.indexOf(c); if (i >= 0) categories.splice(i, 1); }
const bufferUsage = [];
browserCdp.on("Tracing.bufferUsage", (e) => { bufferUsage.push({ t: now(), phase, ...e }); });
let tracingComplete = null;
const tracingCompleteP = new Promise((r) => { browserCdp.on("Tracing.tracingComplete", (e) => { tracingComplete = e; r(e); }); });
const doTrace = process.env.B0_TRACE === "1";
if (doTrace) await browserCdp.send("Tracing.start", {
  transferMode: "ReturnAsStream", streamFormat: "json", streamCompression: "gzip", bufferUsageReportingInterval: 5000,
  traceConfig: { recordMode: process.env.B0_RECORD_MODE ?? "recordContinuously", traceBufferSizeInKb: bufferKb, includedCategories: categories },
});
log(doTrace ? "tracing-started" : "tracing-disabled", { categories });

// ---- load -----------------------------------------------------------------
phase = "load";
const tNav0 = now();
const mBeforeNav = await metrics();
log("goto", { mBeforeNav: { Timestamp: mBeforeNav.Timestamp } });
await page.goto(url, { waitUntil: "load", timeout: 600000 });
const tLoad = now();
log("load-event", { loadMs: tLoad - tNav0 });
// One-time harness reads BEFORE Run (allowed: nothing is generating yet). navigation/resource timing only.
const navInfo = await page.evaluate(() => ({
  nav: performance.getEntriesByType("navigation")[0]?.toJSON(),
  resources: performance.getEntriesByType("resource").length,
  resourceBytes: performance.getEntriesByType("resource").reduce((s, r) => s + (r.decodedBodySize || 0), 0),
  resourceEncodedBytes: performance.getEntriesByType("resource").reduce((s, r) => s + (r.encodedBodySize || 0), 0),
  lastResourceEnd: Math.max(0, ...performance.getEntriesByType("resource").map((r) => r.responseEnd)),
  cssResource: performance.getEntriesByType("resource").filter((r) => /runtime\.css/.test(r.name)).map((r) => ({ startTime: r.startTime, responseEnd: r.responseEnd, decodedBodySize: r.decodedBodySize, encodedBodySize: r.encodedBodySize }))[0],
  fontResources: performance.getEntriesByType("resource").filter((r) => !/runtime\.css/.test(r.name)).length,
  paint: performance.getEntriesByType("paint").map((p) => ({ name: p.name, startTime: p.startTime })),
  fontsStatus: document.fonts.status, fontsSize: document.fonts.size,
  elements: document.getElementsByTagName("*").length,
  scripts: document.querySelectorAll("script").length,
}));
log("nav-info", navInfo);
const mAfterLoad = await metrics();
log("metrics-after-load", { RecalcStyleCount: mAfterLoad.RecalcStyleCount, RecalcStyleDuration: mAfterLoad.RecalcStyleDuration, LayoutCount: mAfterLoad.LayoutCount, LayoutDuration: mAfterLoad.LayoutDuration, Nodes: mAfterLoad.Nodes, LayoutObjects: mAfterLoad.LayoutObjects, TaskDuration: mAfterLoad.TaskDuration, Timestamp: mAfterLoad.Timestamp });
// wait for pre-run idle: RecalcStyleCount unchanged for 2 s (max 90 s)
phase = "pre-run-idle";
{ let last = mAfterLoad.RecalcStyleCount, stableSince = now(); const lim = now() + 90000; while (now() - stableSince < 2000 && now() < lim) { await sleep(250); const m = await metrics(); if (m.RecalcStyleCount !== last) { last = m.RecalcStyleCount; stableSince = now(); } } }
const tIdle = now();
const mIdle = await metrics();
log("pre-run-idle", { sinceNav: tIdle - tNav0, RecalcStyleCount: mIdle.RecalcStyleCount, RecalcStyleDuration: mIdle.RecalcStyleDuration, LayoutCount: mIdle.LayoutCount, LayoutDuration: mIdle.LayoutDuration, Nodes: mIdle.Nodes, LayoutObjects: mIdle.LayoutObjects, Timestamp: mIdle.Timestamp });

// ---- Run (the single external write) ---------------------------------------------------------
phase = "generate";
const { root } = await cdp.send("DOM.getDocument", { depth: 1 });
const rootId = root.nodeId;
const q = async (sel) => (await cdp.send("DOM.querySelector", { nodeId: rootId, selector: sel })).nodeId;
const runNode = await q("#run");
// R3K (2026-09-20, from R3F.md §2.3): B0_TRIGGER selects how Run (<input type=checkbox id=run>) is toggled.
//   "click" (default, unchanged behaviour) = mouse click on #run + the mouseoff park below (B1 item 2).
//   "keyboard" = DOM.focus(#run) + Space keyDown/keyUp; NO mouse event is ever dispatched, so Blink's mouse position stays
//   unknown (MouseEventManager::IsMousePositionUnknown) and the post-layout hover update — a forced 0-element style pass +
//   hit test in EVERY frame, ≈14 ms × 44 frames ≈ 0.6 s/token even with the pointer parked at (-50,-50) — is skipped.
const trigger = process.env.B0_TRIGGER ?? "click";
if (trigger !== "click" && trigger !== "keyboard") throw new Error(`B0_TRIGGER must be "click" or "keyboard", got "${trigger}"`);
let point = null;
if (trigger === "click") {
  // One geometry read of the checkbox to click it (same as Codex's runner). This is before generation.
  const box = (await cdp.send("DOM.getBoxModel", { nodeId: runNode })).model.content;
  point = { x: (box[0] + box[2]) / 2, y: (box[1] + box[5]) / 2, button: "left", clickCount: 1 };
} else {
  // Pre-run, one-time: focus the checkbox (Element::Focus does its own focusability style/layout check; nothing is generating yet).
  await cdp.send("DOM.focus", { nodeId: runNode });
  log("run-focused", { sinceNav: now() - tNav0 });
}
const mBeforeRun = await metrics();
await page.evaluate(() => performance.mark("P2-run"));
const tRun = now();
let mouseOff = { mode: trigger === "keyboard" ? "none (keyboard trigger, no mouse event dispatched)" : (process.env.B0_MOUSEOFF ?? "off"), point: null };
if (trigger === "keyboard") {
  // Checkbox activation in Blink: Space keydown sets :active, Space keyup dispatches the simulated click (toggle + change).
  const key = { key: " ", code: "Space", windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 32 };
  await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", text: " ", unmodifiedText: " ", ...key });
  await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", ...key });
  log("run-keyed", { sinceNav: tRun - tNav0, trigger, Timestamp: mBeforeRun.Timestamp, RecalcStyleCount: mBeforeRun.RecalcStyleCount });
} else {
  await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", ...point });
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", ...point });
  log("run-clicked", { sinceNav: tRun - tNav0, point, trigger, Timestamp: mBeforeRun.Timestamp, RecalcStyleCount: mBeforeRun.RecalcStyleCount });
  // mouseoff (R2A §1, coordinator 2026-09-19 02:4x): with the pointer left on INPUT#run, Blink's after-layout hover update
  // hit-tests the whole document in 61 of 85 frames (≈16.7 ms each ≈ 1 s/token of harness artifact). Park the pointer
  // outside any content. Default "off" = off-viewport (-50,-50): the hit test rejects at the root. "corner" = blank body
  // area at the bottom-right of the 900x300 viewport (890,290). "0" = legacy behaviour (pointer stays on #run).
  const mouseOffMode = mouseOff.mode;
  if (mouseOffMode !== "0") {
    const corner = { x: 890, y: 290 };
    const target = mouseOffMode === "corner" ? corner : { x: -50, y: -50 };
    try {
      await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", ...target, button: "none" });
      mouseOff.point = target;
    } catch (e) {
      log("mouseoff-fallback", { error: String(e), target });
      await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", ...corner, button: "none" });
      mouseOff = { mode: "corner-fallback", point: corner };
    }
    log("mouse-parked", { sinceNav: now() - tNav0, ...mouseOff });
  }
}

// ---- passive wait -------------------------------------------------------------------------
const completionChecks = [];
const tokenEvents = []; // passive: first positive DOM.querySelector(#token-k-captured.done) reply, polled at 1 Hz for the NEXT k only
let stopReason = "cap";
const deadline = tNav0 + capMs;
let lastCheck = 0, lastEos = 0, nextToken = 1;
while (now() < deadline) {
  await sleep(250);
  if (nextToken <= capacity && now() - lastCheck >= 1000) {
    lastCheck = now();
    try {
      const tReq = now();
      const done = await q(`#token-${nextToken}-captured.done`);
      const tResp = now();
      completionChecks.push({ t: tResp, tReq, k: nextToken, done });
      if (done) {
        const prev = tokenEvents.length ? tokenEvents[tokenEvents.length - 1].tResp : tRun;
        tokenEvents.push({ k: nextToken, tReq, tResp, sinceRun: tResp - tRun, tokenSeconds: (tResp - prev) / 1000, replyLatencyMs: tResp - tReq });
        log("token-captured", tokenEvents[tokenEvents.length - 1]);
        nextToken++;
        if (nextToken > capacity) { stopReason = "token-limit"; log("completion-marker", { t: now(), sinceRun: now() - tRun, stopReason }); break; }
      }
    } catch (e) { completionChecks.push({ t: now(), error: String(e) }); }
  }
  if (now() - lastEos >= 5000) {
    lastEos = now();
    try { const eos = await q("#eos-done.done"); if (eos) { stopReason = "eos"; log("completion-marker", { t: now(), sinceRun: now() - tRun, stopReason }); break; } } catch {}
  }
}
const tEndWait = now();
log("wait-ended", { sinceRun: tEndWait - tRun, stopReason, checks: completionChecks.length });
await sleep(2000);
const mAfterGen = await metrics();
log("metrics-after-generate", { RecalcStyleCount: mAfterGen.RecalcStyleCount, RecalcStyleDuration: mAfterGen.RecalcStyleDuration, LayoutCount: mAfterGen.LayoutCount, LayoutDuration: mAfterGen.LayoutDuration, TaskDuration: mAfterGen.TaskDuration, Nodes: mAfterGen.Nodes, LayoutObjects: mAfterGen.LayoutObjects, Timestamp: mAfterGen.Timestamp });
await page.evaluate(() => performance.mark("P2-end"));

// ---- ONE final readback (after the measurement window) ---------------------------------------
phase = "readback";
let finalState = {};
try {
  const cap = await q("#capture-epoch-observer");
  const capBox = (await cdp.send("DOM.getBoxModel", { nodeId: cap })).model.content;
  finalState.captureObserver = { headEpoch: Math.round(capBox[2] - capBox[0]), winner: Math.round(capBox[5] - capBox[1]) };
} catch (e) { finalState.captureObserverError = String(e); }
try {
  const head = await q("#head-epoch-observer");
  const hb = (await cdp.send("DOM.getBoxModel", { nodeId: head })).model.content;
  finalState.headObserver = { headOutputEpoch: Math.round(hb[2] - hb[0]), winner: Math.round(hb[5] - hb[1]) };
} catch (e) { finalState.headObserverError = String(e); }
try {
  const tokensText = await page.evaluate(() => { const o = document.getElementById("tokens"); const cs = getComputedStyle(o, "::after"); return { text: o.textContent, after: cs.content.slice(0, 500), before: getComputedStyle(o, "::before").content.slice(0, 500) }; });
  finalState.tokens = tokensText;
} catch (e) { finalState.tokensError = String(e); }
try {
  const saved = await page.evaluate((cap) => { const cs = getComputedStyle(document.body); const o = {}; for (const k of ["--epoch", "--winner", "--head-output-epoch", "--token", "--layer", "--pass", "--native-pass"]) o[k] = cs.getPropertyValue(k); for (let i = 1; i <= cap; i++) o[`--saved-token-${i}`] = cs.getPropertyValue(`--saved-token-${i}`); return o; }, capacity);
  finalState.bodyProps = saved;
} catch (e) { finalState.bodyPropsError = String(e); }
try {
  finalState.slotProps = await page.evaluate((cap) => { const o = {}; for (let i = 1; i <= cap; i++) { const el = document.querySelector(`.token-slot-${i}`); o[`--saved-token-${i}`] = el ? getComputedStyle(el).getPropertyValue(`--saved-token-${i}`) : null; } const ts = document.querySelector(".token-state"); if (ts) { const cs = getComputedStyle(ts); o.tokenState = {}; for (const k of ["--epoch", "--winner", "--head-output-epoch"]) o.tokenState[k] = cs.getPropertyValue(k); } return o; }, capacity);
} catch (e) { finalState.slotPropsError = String(e); }
try {
  finalState.doneMarkers = {};
  for (let i = 1; i <= capacity; i++) finalState.doneMarkers[`token-${i}-captured`] = (await q(`#token-${i}-captured.done`)) !== 0;
  finalState.doneMarkers.eos = (await q("#eos-done.done")) !== 0;
  finalState.doneMarkers.runLatched = (await q("#run-latched.done")) !== 0;
} catch (e) { finalState.doneMarkersError = String(e); }
log("final-state", finalState);
try { await page.screenshot({ path: `${outDir}/${label}-final.png` }); } catch (e) { log("screenshot-failed", { error: String(e) }); }
const mFinal = await metrics();

// ---- stop tracing, stream to disk (already gzip) --------------------------------------------------
phase = "finish";
sampling = false; clearInterval(rssTimer);
if (doTrace) await browserCdp.send("Tracing.end");
const done = doTrace ? await Promise.race([tracingCompleteP, sleep(600000).then(() => null)]) : null;
let tracePath = null, traceBytes = 0;
if (done && done.stream) {
  tracePath = `${outDir}/${label}-trace.json.gz`;
  const fh = await fsp.open(tracePath, "w");
  for (;;) {
    const r = await browserCdp.send("IO.read", { handle: done.stream, size: 4 << 20 });
    const buf = r.base64Encoded ? Buffer.from(r.data, "base64") : Buffer.from(r.data, "utf8");
    if (buf.length) { await fh.write(buf); traceBytes += buf.length; }
    if (r.eof) break;
  }
  await fh.close();
  await browserCdp.send("IO.close", { handle: done.stream });
  log("trace-saved", { tracePath, gzipBytes: traceBytes, dataLossOccurred: done.dataLossOccurred });
} else if (doTrace) { log("trace-missing", { done }); }
const result = { label, url, version: browser.version(), node: process.version, executablePath, args, heapFlag, trigger, mouseOff, tokenEvents, categories, bufferKb, capMs, capacity, tNav0, tLoad, tIdle, tRun, tEndWait, stopReason, navInfo, mBeforeNav, mAfterLoad, mIdle, mBeforeRun, mAfterGen, mFinal, metricSamples, rssSamples, bufferUsage, completionChecks, finalState, timeline, tracePath, traceBytes, dataLossOccurred: done?.dataLossOccurred };
await fsp.writeFile(`${outDir}/${label}.json`, JSON.stringify(result, null, 1));
log("saved", { file: `${outDir}/${label}.json` });
await browser.close();
