// R2F correctness run (NOT a timing run): headless Chrome, click #run, passively poll #token-N-captured.done,
// record Performance.getMetrics at every token capture (RecalcStyleCount / LayoutCount deltas per token),
// optional light trace (R2F_TRACE=1: frames + UpdateLayoutTree + Layout counts per token window), then ONE
// readback of ids + verification vectors in the layout of F4/correctness_run.mjs (verify_browser_gpt2_runtime.py).
import fs from "node:fs";
import zlib from "node:zlib";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = process.env.R2F_URL, outDir = process.env.R2F_OUT;
const capMs = Number(process.env.R2F_CAP_MS ?? 900000);
const manifest = JSON.parse(fs.readFileSync(`${outDir}/manifest.json`, "utf8"));
const capacity = Number(process.env.R2F_CAPACITY ?? manifest.capacity ?? 8);
const blocks = manifest.blocks, heads = 12;
const TRACE = process.env.R2F_TRACE === "1";
const t0 = performance.now(); const now = () => Math.round(performance.now() - t0);
const log = (event, extra = {}) => console.log(JSON.stringify({ t: now(), event, ...extra }));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const args = ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--force-device-scale-factor=1",
  "--hide-scrollbars", "--disable-background-networking", "--disable-component-update", "--js-flags=--heap-growing-percent=10"];
const browser = await chromium.launch({ executablePath, headless: true, args });
log("launched", { version: browser.version(), url, blocks, capacity, trace: TRACE });
const context = await browser.newContext({ viewport: { width: 900, height: 300 } });
const page = await context.newPage();
const cdp = await context.newCDPSession(page);
await cdp.send("Performance.enable", { timeDomain: "timeTicks" });
await cdp.send("DOM.enable");
const metrics = async () => { const { metrics } = await cdp.send("Performance.getMetrics"); const o = {}; for (const m of metrics) o[m.name] = m.value; return o; };
await page.goto(url, { waitUntil: "load", timeout: 600000 });
log("loaded", { elements: await page.evaluate(() => document.getElementsByTagName("*").length), fonts: await page.evaluate(() => document.fonts.size) });
{ let m = await metrics(), last = m.RecalcStyleCount, stableSince = now(); const lim = now() + 90000;
  while (now() - stableSince < 2000 && now() < lim) { await sleep(250); m = await metrics(); if (m.RecalcStyleCount !== last) { last = m.RecalcStyleCount; stableSince = now(); } } }
const m0 = await metrics();
log("pre-run-idle", { RecalcStyleCount: m0.RecalcStyleCount, LayoutCount: m0.LayoutCount, Nodes: m0.Nodes });
let events = [];
if (TRACE) {
  cdp.on("Tracing.dataCollected", ({ value }) => events.push(...value));
  await cdp.send("Tracing.start", { transferMode: "ReportEvents", traceConfig: { recordMode: "recordContinuously", includedCategories: ["blink", "blink.style", "devtools.timeline", "disabled-by-default-devtools.timeline", "cc"] } });
  await sleep(200);
}
const { root } = await cdp.send("DOM.getDocument", { depth: 1 }); // one getDocument per session
const q = async (sel) => (await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: sel })).nodeId;
const runNode = await q("#run");
const box = (await cdp.send("DOM.getBoxModel", { nodeId: runNode })).model.content;
const point = { x: (box[0] + box[2]) / 2, y: (box[1] + box[5]) / 2, button: "left", clickCount: 1 };
const tRun = now();
await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", ...point });
await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", ...point });
log("run-clicked");
let stopReason = "cap"; const tokenTimes = {}; const tokenMetrics = {}; let nextToken = 1; let prev = m0;
const pollMs = Number(process.env.R2F_POLL_MS ?? 5000);
while (now() - tRun < capMs) {
  await sleep(pollMs);
  try {
    while (nextToken <= capacity && (await q(`#token-${nextToken}-captured.done`))) {
      tokenTimes[nextToken] = now() - tRun;
      const m = await metrics();
      tokenMetrics[nextToken] = { ts: m.Timestamp, RecalcStyleCount: m.RecalcStyleCount, LayoutCount: m.LayoutCount, dRecalc: m.RecalcStyleCount - prev.RecalcStyleCount, dLayout: m.LayoutCount - prev.LayoutCount, dRecalcS: +(m.RecalcStyleDuration - prev.RecalcStyleDuration).toFixed(2), dLayoutS: +(m.LayoutDuration - prev.LayoutDuration).toFixed(2) };
      prev = m;
      log("token-captured", { token: nextToken, sinceRunMs: tokenTimes[nextToken], ...tokenMetrics[nextToken] });
      nextToken++;
    }
    if (nextToken > capacity) { stopReason = "token-limit"; break; }
    if (await q("#eos-done.done")) { stopReason = "eos"; break; }
  } catch (e) { log("poll-error", { error: String(e) }); }
}
log("wait-ended", { stopReason, sinceRunMs: now() - tRun });
await sleep(2000);
const m = await metrics();
log("metrics-after", { RecalcStyleCount: m.RecalcStyleCount, RecalcStyleDuration: m.RecalcStyleDuration, LayoutCount: m.LayoutCount, LayoutDuration: m.LayoutDuration, Nodes: m.Nodes, dRecalcSinceIdle: m.RecalcStyleCount - m0.RecalcStyleCount, dLayoutSinceIdle: m.LayoutCount - m0.LayoutCount });
let traceSummary = null;
if (TRACE) {
  const complete = new Promise((res) => cdp.once("Tracing.tracingComplete", res));
  await cdp.send("Tracing.end"); await complete;
  const { summarizeTrace } = await import("/Users/shubhampatil/Documents/programming/gpt2-css/audit/2026-09-18/M1-microbench/parse_trace.mjs");
  traceSummary = {};
  let startUs = m0.Timestamp * 1e6;
  for (let tkn = 1; tkn <= capacity; tkn++) {
    const tm = tokenMetrics[tkn]; if (!tm) break;
    const endUs = tm.ts * 1e6;
    const s = summarizeTrace(events, { windowStartUs: startUs, windowEndUs: endUs });
    traceSummary[tkn] = { ult: s.updateLayoutTree.count, ultMs: +(s.updateLayoutTree.totalUs / 1000).toFixed(0), layout: s.layout.count, layoutMs: +(s.layout.totalUs / 1000).toFixed(0), frames: s.frames, busyMs: +(s.topLevelBusyUs / 1000).toFixed(0), ultElementsTop: (s.updateLayoutTree.elementCounts ?? []).slice(0, 12) };
    startUs = endUs;
  }
  log("trace-per-token", traceSummary);
  fs.writeFileSync(`${outDir}/trace.json.gz`, zlib.gzipSync(JSON.stringify({ traceEvents: events })));
  events = [];
}
// ---- ONE readback (same shape as F4/correctness_run.mjs, unpacked banks) ----
const result = await page.evaluate(({ capacity, blocks, heads }) => {
  const num = (s) => { s = s.trim(); if (s.startsWith("calc(")) { const mm = s.match(/^calc\(\s*([-+\d.eE]+)\s*\/\s*([-+\d.eE]+)\s*\)$/); return mm ? Number(mm[1]) / Number(mm[2]) : NaN; } return Number(s); };
  const cs = (el) => getComputedStyle(el);
  const tokens = [];
  for (let i = 1; i <= capacity; i++) { const el = document.querySelector(`.token-slot-${i}`); tokens.push(Number(el ? cs(el).getPropertyValue(`--saved-token-${i}`).trim() : NaN)); }
  const tokensText = document.getElementById("tokens")?.textContent ?? null;
  const core = document.getElementById("core-result"); const finalResidual = []; if (core) { const c = cs(core); for (let i = 0; i < 768; i++) finalResidual.push(num(c.getPropertyValue(`--x-${String(i).padStart(3, "0")}`))); }
  const bank = document.querySelector(".head-input-bank"); const finalHidden = []; if (bank) { const c = cs(bank); for (let i = 0; i < 768; i++) finalHidden.push(num(c.getPropertyValue(`--h${i}`))); }
  const caches = [];
  for (let L = 0; L < blocks; L++) { const el = document.querySelector(`.fvs-bank-${L}`); if (!el) continue; const c = cs(el);
    for (let s = 0; s < capacity; s++) { const values = new Array(1536).fill(NaN); let ok = true;
      for (let h = 0; h < heads; h++) { for (const [kind, off] of [["k", 0], ["v", 768]]) {
        const list = c.getPropertyValue(`--fc-${kind}-${s}-${h}`); const scale = num(c.getPropertyValue(`--fc-${kind}s-${s}-${h}`));
        const re = /"K(\d{3})"\s*(calc\([^)]*\)|[-+\d.eE]+)/g; let mm, n = 0;
        while ((mm = re.exec(list))) { values[off + h * 64 + Number(mm[1])] = num(mm[2]) * scale; n++; }
        if (n !== 64) ok = false; } }
      caches.push({ layer: L, slot: s, position: s, values, complete: ok }); } }
  // F3 chain diagnostics: a few chain-bottom values
  const diag = {};
  const fb = document.getElementById("f3b"); if (fb) { const c = cs(fb); diag.out0 = c.getPropertyValue("--out-000"); diag.out767 = c.getPropertyValue("--out-767"); diag.pr0 = c.getPropertyValue("--f3pr0"); diag.pr11 = c.getPropertyValue("--f3pr11"); }
  const fr0 = document.getElementById("f3r0"); if (fr0) { const c = cs(fr0); diag.hidden0 = c.getPropertyValue("--hidden-000"); diag.hidden255 = c.getPropertyValue("--hidden-255"); diag.rangeProj0 = c.getPropertyValue("--range-proj"); diag.fcWidth = document.getElementById("f3c0-0")?.getBoundingClientRect().width; }
  return { tokens, tokensText, finalResidual, finalHidden, caches, diag };
}, { capacity, blocks, heads });
const doneMarkers = {}; for (let i = 1; i <= capacity; i++) doneMarkers[i] = (await q(`#token-${i}-captured.done`)) !== 0;
log("final", { tokens: result.tokens, tokensText: result.tokensText, doneMarkers, cachesComplete: result.caches.filter((c) => c.complete).length, tokenTimes, diag: result.diag });
fs.writeFileSync(`${outDir}/verification-vectors.json`, JSON.stringify({ tokens: result.tokens, prompt: 15496, finalResidual: result.finalResidual, finalHidden: result.finalHidden, caches: result.caches.map(({ layer, slot, position, values }) => ({ layer, slot, position, values })), cacheReadbackScope: "all retained native cache slots (R2F correctness run)" }));
fs.writeFileSync(`${outDir}/pipeline-results.json`, JSON.stringify({ complete: stopReason === "token-limit" && result.tokens.every((t) => Number.isFinite(t) && t > 0), stopReason, tokenTimesMs: tokenTimes, tokenMetrics, traceSummary, metricsIdle: { RecalcStyleCount: m0.RecalcStyleCount, LayoutCount: m0.LayoutCount }, metricsAfter: m, harness: "work/2026-09-19/R2F/run_bundle.mjs (correctness only, not a timing run)", browserArguments: args, browser: browser.version(), artifactSha256: {} }, null, 2));
await browser.close();
log("closed");
