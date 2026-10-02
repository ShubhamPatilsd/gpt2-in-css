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

// R7B copy of R6X/bench_native.mjs: + B0_SEED / B0_TEMP (Playwright selectOption on #r7b-seed / #r7b-temp before Run, computed --seed/--temp on body read back pre-Run), B0_STOP_TOKEN (last expected #token-k-captured; the wait ends there or on #r7b-complete-*.done), post-run readback of the head bank's --noise-col/--seed/--temp/--r7b-n and the seed readout.
// R6X copy of R6P/bench_native.mjs (+ B0_SHOTS mid-run screenshots) = R4M/bench_native.mjs + B0_TYPED_PROMPT (harness-side typing into the editable <style>; the page stays JS-free).
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
const stopToken = Number(process.env.B0_STOP_TOKEN || capacity); // R7B: the stop rule ends the run at epoch 31+max(N,1) < capacity
const t0 = performance.now();
const now = () => Math.round((performance.now() - t0) * 10) / 10;
const timeline = [];
const log = (event, extra = {}) => { const row = { t: now(), event, ...extra }; timeline.push(row); console.log(JSON.stringify(row)); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const args = [
  "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
  "--force-device-scale-factor=1",
  "--disable-background-networking", "--disable-component-update",
];
if (heapFlag) args.push("--js-flags=--heap-growing-percent=10"); // same as the validated runs (browserArguments in pipeline-results.json)
// R6X v3: B0_HEADED=1 opens a real window (user-like session), B0_VIEWPORT=WxH (default 900x300)
const headed = process.env.B0_HEADED === "1";
// R7H: --hide-scrollbars only unless R7H_SHOW_SCROLLBARS=1 (the user's Chrome has no such flag; classic scrollbars shrink scrollports)
if (process.env.R7H_SHOW_SCROLLBARS !== "1" && process.env.B0_SHOW_SCROLLBARS !== "1") args.push("--hide-scrollbars");  // R7X: either name (R6X v6 harness uses B0_SHOW_SCROLLBARS)
const [vpW, vpH] = (process.env.B0_VIEWPORT ?? "900x300").split("x").map(Number);
if (headed) args.push(`--window-size=${vpW},${vpH + 90}`);
const browser = await chromium.launch({ executablePath, headless: !headed, args });
const browserCdp = await browser.newBrowserCDPSession();
async function procInfo() { const { processInfo } = await browserCdp.send("SystemInfo.getProcessInfo"); return processInfo; }
const browserPid = (await procInfo()).find((p) => p.type === "browser")?.id;
log("launched", { browserPid, version: browser.version(), url, args, heapFlag, invalidation, bufferKb, capMs });
const context = await browser.newContext({ viewport: { width: vpW, height: vpH } });
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
if (process.env.B0_READY_SHOT === "1") { try { await page.screenshot({ path: `${outDir}/${label}-ready.png` }); log("screenshot", { file: `${label}-ready.png`, sinceNav: now() - tNav0 }); } catch (e) { log("screenshot-failed", { tag: "ready", error: String(e).slice(0, 100) }); } }
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
// R6P (2026-09-30): B0_TYPED_PROMPT = text to type into the editable <style id="tk-editor"> BEFORE focusing/pressing Run (Playwright
// locator.fill on the contenteditable element = harness-side select-all + Input.insertText; no page script). The tokenizer fonts turn
// the text into ids live (pre-Run); B0_TYPED_IDS (JSON array) is asserted against the live --pt-id-k on .tk-high-k, --draft-prompt on
// .tk-root is read back. Typing happens BEFORE DOM.focus(#run) so the Space key goes to the checkbox, not into the editor.
const typedPrompt = process.env.B0_TYPED_PROMPT ? process.env.B0_TYPED_PROMPT : null;
const typedIds = process.env.B0_TYPED_IDS ? JSON.parse(process.env.B0_TYPED_IDS) : null;
let typedState = null;
if (typedPrompt !== null) {
  const rule = `.tk-root { --draft-prompt: "${typedPrompt.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"; }`;
  const tType0 = now();
  await page.locator("#tk-editor").fill(rule);
  await sleep(1500);
  typedState = await page.evaluate((slots) => {
    const root = document.querySelector(".tk-root"); const o = { editorText: document.getElementById("tk-editor").textContent,
      draftPrompt: getComputedStyle(root).getPropertyValue("--draft-prompt"), ids: [], present: [], armed: [] };
    for (let k = 0; k < slots; k++) { const el = document.querySelector(`.tk-high-${k}`); const cs = getComputedStyle(el);
      o.ids.push(Number(cs.getPropertyValue("--pt-id-" + k))); o.present.push(Number(cs.getPropertyValue("--pt-present-" + k)));
      o.armed.push(Number(cs.getPropertyValue("--prompt-token-id-" + k))); }
    const last = document.querySelector(`.tk-high-${slots - 1}`); o.promptCount = Number(getComputedStyle(last).getPropertyValue("--prompt-count"));
    const vo = document.getElementById("visible-output"); o.visibleBefore = getComputedStyle(vo, "::before").content.slice(0, 300);
    const tk = document.querySelector(".tk-tokens"); o.tokensReadout = getComputedStyle(tk, "::after").content.slice(0, 300);
    return o; }, Number(process.env.B0_PROMPT_SLOTS ?? 4));
  log("prompt-typed", { typedPrompt, typedIds, typeMs: now() - tType0, ...typedState, sinceNav: now() - tNav0 });
  if (typedIds) {
    const live = typedState.ids.filter((v) => v >= 0);
    if (JSON.stringify(live) !== JSON.stringify(typedIds)) throw new Error(`typed prompt ids ${JSON.stringify(live)} != expected ${JSON.stringify(typedIds)} (draft ${typedState.draftPrompt})`);
    if (typedState.promptCount !== 0 || typedState.armed.some((v) => v !== -1)) throw new Error(`model-facing prompt values leaked before Run: count ${typedState.promptCount} ids ${JSON.stringify(typedState.armed)}`);
  }
}
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
// R4M (coordinator 2026-09-21): B0_PROMPT_TOKEN = value of the prompt <select> option to pick BEFORE Run (harness-side Playwright
// selectOption; the page stays JS-free). The bundle ships options 15496,464,40,32,1212,2061 (browser_gpt2_runtime.py:498-500);
// body:has(option[value=T]:checked){--prompt-token:T} makes the choice effective, .feedback-reader freezes it on Run. Verified by reading
// the select's value back (one harness read, pre-run) and by the `--prompt-token` computed value on body.
const promptToken = process.env.B0_PROMPT_TOKEN ? Number(process.env.B0_PROMPT_TOKEN) : null;
let promptSelect = null;
if (promptToken !== null) {
  const picked = await page.selectOption("select", String(promptToken));
  await sleep(500);
  promptSelect = await page.evaluate(() => {
    const s = document.querySelector("select");
    return { value: s.value, selectedText: s.options[s.selectedIndex]?.textContent, options: [...s.options].map((o) => o.value),
             bodyPromptToken: getComputedStyle(document.body).getPropertyValue("--prompt-token").trim() };
  });
  log("prompt-selected", { promptToken, picked, ...promptSelect, sinceNav: now() - tNav0 });
  if (promptSelect.value !== String(promptToken) || promptSelect.bodyPromptToken !== String(promptToken)) {
    throw new Error(`B0_PROMPT_TOKEN=${promptToken} did not take effect: select.value=${promptSelect.value} --prompt-token=${promptSelect.bodyPromptToken}`);
  }
}
// R7B: sampling controls (harness-side selectOption; the page stays JS-free). B0_SEED = 1..64 (0/empty = auto clock), B0_TEMP = 0 | 0.7 | 1.
const seedPick = process.env.B0_SEED ? String(Number(process.env.B0_SEED)) : null;
const tempPick = process.env.B0_TEMP ? String(Number(process.env.B0_TEMP)) : null;
let samplingState = null;
if (seedPick !== null || tempPick !== null) {
  if (seedPick !== null) await page.selectOption("#r7b-seed", seedPick);
  if (tempPick !== null) await page.selectOption("#r7b-temp", tempPick);
  await sleep(500);
  samplingState = await page.evaluate(() => {
    const cs = getComputedStyle(document.body); const out = document.querySelector(".r7b-seed-out");
    const seedSel = document.getElementById("r7b-seed"), tempSel = document.getElementById("r7b-temp");
    return { seedSelect: seedSel && seedSel.value, tempSelect: tempSel && tempSel.value, bodySeed: cs.getPropertyValue("--seed").trim(), bodySeedOverride: cs.getPropertyValue("--seed-override").trim(),
             bodyTemp: cs.getPropertyValue("--temp").trim(), bodyClock: cs.getPropertyValue("--clock").trim(), playState: cs.animationPlayState,
             readout: out ? (getComputedStyle(out, "::before").content + " " + getComputedStyle(out, "::after").content) : null };
  });
  log("sampling-selected", { seedPick, tempPick, ...samplingState, sinceNav: now() - tNav0 });
  if (seedPick !== null && samplingState.bodySeed !== seedPick) throw new Error(`B0_SEED=${seedPick} did not take effect: --seed=${samplingState.bodySeed}`);
  if (tempPick !== null && Number(samplingState.bodyTemp) !== Number(tempPick)) throw new Error(`B0_TEMP=${tempPick} did not take effect: --temp=${samplingState.bodyTemp}`);
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
// R6X (2026-09-30): B0_SHOTS = comma-separated seconds after Run at which to save a screenshot (`<label>-run-<s>s.png`) of the page
// (progress bar mid-token). Screenshot only — no style/geometry reads — so the passive protocol is otherwise unchanged; a screenshot
// forces one frame, which may add one RecalcStyle/Layout to that token's counters.
const shotTimes = (process.env.B0_SHOTS ?? "").split(",").filter(Boolean).map(Number).sort((a, b) => a - b);
while (now() < deadline) {
  await sleep(250);
  if (shotTimes.length && now() - tRun >= shotTimes[0] * 1000) {
    const s = shotTimes.shift();
    try { await page.screenshot({ path: `${outDir}/${label}-run-${s}s.png`, timeout: 30000 }); log("screenshot", { file: `${label}-run-${s}s.png`, sinceRun: now() - tRun, tokensSoFar: nextToken - 1 }); } catch (e) { log("screenshot-failed", { s, error: String(e).slice(0, 120) }); }
    if (process.env.B0_SHOT_DUMP === "1") {  // R6X v5 diagnosis: display state at each shot (forces a style read; diagnosis runs only)
      const d = await page.evaluate((cap) => { const vo = document.getElementById("visible-output"); const cs = getComputedStyle(vo); const o = { promptCount: cs.getPropertyValue("--prompt-count").trim(), displayPrompt: cs.getPropertyValue("--display-prompt").trim(), draftEcho: cs.getPropertyValue("--draft-echo").trim(), before: getComputedStyle(vo, "::before").content.slice(0, 300), innerText: vo.innerText, promptTokenIds: [], displayTokens: [], feedback: [] };
        for (let k = 0; k < 4; k++) o.promptTokenIds.push(cs.getPropertyValue("--prompt-token-id-" + k).trim());
        for (let i = 1; i <= Math.min(cap, 8); i++) { o.displayTokens.push(cs.getPropertyValue("--display-token-" + i).trim()); o.feedback.push(cs.getPropertyValue("--feedback-" + i).trim()); }
        const tk = document.querySelector(".tk-tokens"); o.tkTokens = tk ? getComputedStyle(tk, "::after").content.slice(0, 300) : null; const tkc = tk ? getComputedStyle(tk) : null; o.tkIds = tkc ? [0,1,2,3].map((k) => tkc.getPropertyValue("--tkd-" + k).trim()) : null;
        const hi = document.querySelector(".tk-high-3"); if (hi) { const h = getComputedStyle(hi); o.tkHigh3 = { promptCount: h.getPropertyValue("--prompt-count").trim(), ids: [0,1,2,3].map((k) => h.getPropertyValue("--prompt-token-id-" + k).trim()), present: [0,1,2,3].map((k) => h.getPropertyValue("--pt-present-" + k).trim()) }; }
        const fs = document.querySelector(".feedback-select"); o.token = fs ? getComputedStyle(fs).getPropertyValue("--token").trim() : null; o.epoch = getComputedStyle(document.body).getPropertyValue("--epoch").trim();
        return o; }, capacity).catch((e) => ({ error: String(e).slice(0, 160) }));
      log("shot-dump", { s, ...d });
    }
  }
  if (nextToken === 1 && now() - tRun >= Number(process.env.R7H_HELD_S ?? 120) * 1000 && !globalThis.__heldChecked) {  // R7H diagnostic read
    globalThis.__heldChecked = true;
    const g = await page.evaluate(() => { const ts = document.querySelector(".token-state"); return ts ? getComputedStyle(ts).getPropertyValue("--fb-ok").trim() : "n/a"; }).catch((e) => String(e));
    log("guard-check", { sinceRun: now() - tRun, fbOk: g });
    if (g === "0") { stopReason = "guard-held"; log("completion-marker", { t: now(), sinceRun: now() - tRun, stopReason }); break; }
  }
  if (nextToken <= stopToken && now() - lastCheck >= 1000) {
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
        if (nextToken > stopToken) { stopReason = nextToken > capacity ? "token-limit" : "stop-rule"; log("completion-marker", { t: now(), sinceRun: now() - tRun, stopReason }); break; }
      }
    } catch (e) { completionChecks.push({ t: now(), error: String(e) }); }
  }
  if (now() - lastEos >= 5000) {
    lastEos = now();
    try { const eos = await q("#eos-done.done"); if (eos) { stopReason = "eos"; log("completion-marker", { t: now(), sinceRun: now() - tRun, stopReason }); break; } } catch {}
    try { const done = await q("[id^=r7b-complete-].done"); if (done && nextToken > stopToken) { stopReason = "r7b-complete"; log("completion-marker", { t: now(), sinceRun: now() - tRun, stopReason }); break; } } catch {}
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
try {  // R7H: id-guard state + the scrollport the view-timeline decode actually saw
  finalState.guard = await page.evaluate((cap) => {
    const o = {}; const ts = document.querySelector(".token-state"); const fr = document.querySelector(".feedback-reader"); const w = document.querySelector(".fb-warn"); const sc = document.querySelector(".feedback-scroller");
    if (ts) { const cs = getComputedStyle(ts); o.tokenState = { fbOk: cs.getPropertyValue("--fb-ok").trim(), fbCalP: cs.getPropertyValue("--fb-cal-p").trim(), agree: [] }; for (let i = 1; i <= cap; i++) o.tokenState.agree.push(cs.getPropertyValue(`--fb-agree-${i}`).trim()); }
    if (fr) { const cs = getComputedStyle(fr); o.feedbackReader = { fbOk: cs.getPropertyValue("--fb-ok").trim(), fbCalP: cs.getPropertyValue("--fb-cal-p").trim(), feedback: [] }; for (let i = 1; i <= cap; i++) o.feedbackReader.feedback.push(cs.getPropertyValue(`--feedback-${i}`).trim()); }
    o.warn = w ? { display: getComputedStyle(w).display, text: getComputedStyle(w, "::after").content.slice(0, 120) } : null;
    if (sc) { const cs = getComputedStyle(sc); o.scroller = { clientWidth: sc.clientWidth, offsetWidth: sc.offsetWidth, clientHeight: sc.clientHeight, scrollLeft: sc.scrollLeft, scrollbarWidth: cs.scrollbarWidth, overflow: cs.overflow }; }
    o.status = (() => { const st = document.querySelector(".status"); return st ? getComputedStyle(st, "::after").content.slice(0, 120) : null; })();
    return o; }, capacity).catch((e) => ({ error: String(e).slice(0, 200) }));
  log("guard-state", finalState.guard);
} catch (e) { finalState.guardError = String(e); }
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
  if (typedPrompt !== null) finalState.typed = await page.evaluate((slots) => {
    const last = document.querySelector(`.tk-high-${slots - 1}`); const cs = getComputedStyle(last); const o = { promptCount: Number(cs.getPropertyValue("--prompt-count")), armedIds: [] };
    for (let k = 0; k < slots; k++) o.armedIds.push(Number(getComputedStyle(document.querySelector(`.tk-high-${k}`)).getPropertyValue("--prompt-token-id-" + k)));
    const vo = document.getElementById("visible-output"); o.visibleBefore = getComputedStyle(vo, "::before").content.slice(0, 400); o.visibleAfter = getComputedStyle(vo, "::after").content.slice(0, 1200);
    o.feedbackSelectToken = getComputedStyle(document.querySelector(".feedback-select")).getPropertyValue("--token");
    return o; }, Number(process.env.B0_PROMPT_SLOTS ?? 4));
  else finalState.visible = await page.evaluate(() => { const vo = document.getElementById("visible-output"); return vo ? { before: getComputedStyle(vo, "::before").content.slice(0, 400), after: getComputedStyle(vo, "::after").content.slice(0, 1200) } : null; });
  // R6X v3 (user report "Complete but no text"): computed styles of the output element and every input of its counters; lock state of the body children
  finalState.display = await page.evaluate((cap) => {
    const vo = document.getElementById("visible-output"); const cs = getComputedStyle(vo); const r = vo.getBoundingClientRect();
    const o = { display: cs.display, visibility: cs.visibility, contentVisibility: cs.contentVisibility, opacity: cs.opacity, color: cs.color, fontFamily: cs.fontFamily, fontSize: cs.fontSize,
      top: cs.top, bottom: cs.bottom, height: cs.height, overflow: cs.overflow, rect: { top: Math.round(r.top), height: Math.round(r.height), width: Math.round(r.width) }, scrollHeight: vo.scrollHeight, clientHeight: vo.clientHeight,
      before: getComputedStyle(vo, "::before").content.slice(0, 500), after: getComputedStyle(vo, "::after").content.slice(0, 200),
      displayPrompt: cs.getPropertyValue("--display-prompt"), draftEcho: cs.getPropertyValue("--draft-echo"), promptCount: cs.getPropertyValue("--prompt-count"), frozenPrompt: cs.getPropertyValue("--frozen-prompt"),
      displayTokens: {}, promptTokenIds: {}, bodyChildren: [] };
    for (let i = 1; i <= cap; i++) o.displayTokens[i] = cs.getPropertyValue("--display-token-" + i).trim();
    for (let k = 0; k < 4; k++) o.promptTokenIds[k] = cs.getPropertyValue("--prompt-token-id-" + k).trim();
    const root = document.querySelector(".tk-root"); if (root) { const rs = getComputedStyle(root); o.tkRoot = { display: rs.display, contentVisibility: rs.contentVisibility, draftPrompt: rs.getPropertyValue("--draft-prompt") }; }
    const ed = document.getElementById("tk-editor"); if (ed) o.editor = { text: ed.textContent, display: getComputedStyle(ed).display, sheetRules: ed.sheet ? ed.sheet.cssRules.length : null, ruleText: ed.sheet && ed.sheet.cssRules[0] ? ed.sheet.cssRules[0].cssText.slice(0, 200) : null };
    for (const c of document.body.children) o.bodyChildren.push({ tag: c.tagName, cls: c.className && c.className.baseVal === undefined ? String(c.className).slice(0, 40) : (c.id || c.tagName), cv: getComputedStyle(c).contentVisibility });
    const st = document.querySelector(".status"); o.status = st ? getComputedStyle(st, "::after").content : null;
    const tk = document.querySelector(".tk-tokens"); o.tkTokens = tk ? getComputedStyle(tk, "::after").content.slice(0, 300) : null;
    return o; }, capacity).catch((e) => ({ error: String(e).slice(0, 200) }));
  log("display-dump", finalState.display);
} catch (e) { finalState.typedError = String(e); }
try {  // R7B: sampling state after the run (bank-side values, readout, status text, stop relay)
  finalState.r7b = await page.evaluate(() => {
    const bank = document.querySelector(".head-input-bank"); const bs = bank ? getComputedStyle(bank) : null; const o = {};
    if (bs) { for (const k of ["--noise-col", "--seed", "--temp", "--r7b-n", "--epoch", "--head-input-epoch"]) o[k] = bs.getPropertyValue(k).trim(); o.headFvsTail = bs.getPropertyValue("--head-fvs").trim().slice(-60); }
    const cs = getComputedStyle(document.body); o.bodySeed = cs.getPropertyValue("--seed").trim(); o.bodyTemp = cs.getPropertyValue("--temp").trim(); o.bodyPlayState = cs.animationPlayState;
    const out = document.querySelector(".r7b-seed-out"); o.readout = out ? (getComputedStyle(out, "::before").content + " " + getComputedStyle(out, "::after").content) : null;
    const st = document.querySelector(".status"); o.status = st ? getComputedStyle(st, "::after").content : null;
    const pg = document.querySelector(".pg"); o.pgDisplay = pg ? getComputedStyle(pg).display : null; const pt = document.querySelector(".pg-tok"); o.pgTok = pt ? getComputedStyle(pt, "::after").content : null;
    o.complete = [...document.querySelectorAll("[id^=r7b-complete-]")].map((g) => g.id + ":" + g.getAttribute("class"));
    return o; }).catch((e) => ({ error: String(e).slice(0, 200) }));
  log("r7b-state", finalState.r7b);
} catch (e) { finalState.r7bError = String(e); }
try {
  finalState.doneMarkers = {};
  for (let i = 1; i <= capacity; i++) finalState.doneMarkers[`token-${i}-captured`] = (await q(`#token-${i}-captured.done`)) !== 0;
  finalState.doneMarkers.eos = (await q("#eos-done.done")) !== 0;
  finalState.doneMarkers.runLatched = (await q("#run-latched.done")) !== 0;
} catch (e) { finalState.doneMarkersError = String(e); }
log("final-state", finalState);
try { await page.screenshot({ path: `${outDir}/${label}-final.png` }); } catch (e) { log("screenshot-failed", { error: String(e) }); }
// R8U: after the final readback, the Complete page at more viewport sizes (display only; the run is over)
for (const vp of (process.env.R8U_FINAL_VIEWPORTS ?? "").split(",").filter(Boolean)) {
  const [w, h] = vp.split("x").map(Number);
  try { await page.setViewportSize({ width: w, height: h }); await sleep(2500); await page.screenshot({ path: `${outDir}/${label}-final-${vp}.png`, timeout: 60000 }); log("screenshot", { file: `${label}-final-${vp}.png` }); } catch (e) { log("screenshot-failed", { vp, error: String(e).slice(0, 120) }); }
}
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
const result = { label, url, version: browser.version(), node: process.version, executablePath, args, heapFlag, trigger, mouseOff, promptToken, promptSelect, typedPrompt, typedIds, typedState, seedPick, tempPick, samplingState, stopToken, tokenEvents, categories, bufferKb, capMs, capacity, tNav0, tLoad, tIdle, tRun, tEndWait, stopReason, navInfo, mBeforeNav, mAfterLoad, mIdle, mBeforeRun, mAfterGen, mFinal, metricSamples, rssSamples, bufferUsage, completionChecks, finalState, timeline, tracePath, traceBytes, dataLossOccurred: done?.dataLossOccurred };
await fsp.writeFile(`${outDir}/${label}.json`, JSON.stringify(result, null, 1));
log("saved", { file: `${outDir}/${label}.json` });
await browser.close();
