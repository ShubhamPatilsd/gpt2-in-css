// R2C correctness run (NOT a timing run): headless Chrome, passive wait for #token-8-captured.done, then ONE
// readback of the 8 ids + the verification vectors (final residual, final hidden, retained KV banks).
// Adapted from work/2026-09-19/B0/trace_native.mjs (same launch args), tracing removed.
import fs from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = process.env.R2C_URL;
const outDir = process.env.R2C_OUT;
const capMs = Number(process.env.R2C_CAP_MS ?? 900000);
const capacity = Number(process.env.R2C_CAPACITY ?? 8);
const blocks = 12, heads = 12;
const manifest = JSON.parse(fs.readFileSync(`${outDir}/manifest.json`, "utf8"));
const packedBanks = !!manifest.f4PackedBanks, packedHead = !!manifest.f4PackedHead;
const t0 = performance.now();
const now = () => Math.round(performance.now() - t0);
const log = (event, extra = {}) => console.log(JSON.stringify({ t: now(), event, ...extra }));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const args = ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--force-device-scale-factor=1",
  "--hide-scrollbars", "--disable-background-networking", "--disable-component-update", "--js-flags=--heap-growing-percent=10"];
const browser = await chromium.launch({ executablePath, headless: true, args });
log("launched", { version: browser.version(), url });
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
log("pre-run-idle");
const { root } = await cdp.send("DOM.getDocument", { depth: 1 });
const q = async (sel) => (await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: sel })).nodeId;
const runNode = await q("#run");
const box = (await cdp.send("DOM.getBoxModel", { nodeId: runNode })).model.content;
const point = { x: (box[0] + box[2]) / 2, y: (box[1] + box[5]) / 2, button: "left", clickCount: 1 };
const tRun = now();
await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", ...point });
await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", ...point });
log("run-clicked");
let stopReason = "cap"; const tokenTimes = {}; let nextToken = 1;
while (now() - tRun < capMs) {
  await sleep(5000);
  try {
    // only DOM selector matches (no style/geometry) during generation
    while (nextToken <= capacity && (await q(`#token-${nextToken}-captured.done`))) { tokenTimes[nextToken] = now() - tRun; log("token-captured", { token: nextToken, sinceRunMs: tokenTimes[nextToken] }); nextToken++; }
    if (nextToken > capacity) { stopReason = "token-limit"; break; }
    if (await q("#eos-done.done")) { stopReason = "eos"; break; }
  } catch (e) { log("poll-error", { error: String(e) }); }
}
log("wait-ended", { stopReason, sinceRunMs: now() - tRun });
await sleep(2000);
const m = await metrics();
log("metrics-after", { RecalcStyleCount: m.RecalcStyleCount, RecalcStyleDuration: m.RecalcStyleDuration, LayoutCount: m.LayoutCount, LayoutDuration: m.LayoutDuration, Nodes: m.Nodes });
// ---- ONE readback ----
const result = await page.evaluate(({ capacity, blocks, heads, packedBanks, packedHead }) => {
  const num = (s) => { s = s.trim(); if (s.startsWith("calc(")) { const mm = s.match(/^calc\(\s*([-+\d.eE]+)\s*\/\s*([-+\d.eE]+)\s*\)$/); return mm ? Number(mm[1]) / Number(mm[2]) : NaN; } return Number(s); };
  const cs = (el) => getComputedStyle(el);
  const tokens = []; const slotProps = {};
  for (let i = 1; i <= capacity; i++) { const el = document.querySelector(`.token-slot-${i}`); const v = el ? cs(el).getPropertyValue(`--saved-token-${i}`).trim() : null; slotProps[i] = v; tokens.push(Number(v)); }
  const tokensText = document.getElementById("tokens")?.textContent ?? null;
  const core = document.getElementById("core-result"); const finalResidual = []; if (core) { const c = cs(core); for (let i = 0; i < 768; i++) finalResidual.push(num(c.getPropertyValue(`--x-${String(i).padStart(3, "0")}`))); }
  const bank = document.querySelector(".head-input-bank"); const finalHidden = []; let headSample = null;
  if (bank) { const c = cs(bank);
    if (packedHead) { for (let i = 0; i < 768; i++) finalHidden.push(num(c.getPropertyValue(`--final-h-${String(i).padStart(3, "0")}`))); headSample = c.getPropertyValue("--head-fvs").slice(0, 120); }
    else { for (let i = 0; i < 768; i++) finalHidden.push(num(c.getPropertyValue(`--h${i}`))); } }
  const caches = []; const rawSample = {};
  for (let L = 0; L < blocks; L++) { const el = document.querySelector(`.fvs-bank-${L}`); if (!el) continue; const c = cs(el);
    for (let s = 0; s < capacity; s++) { const values = new Array(1536).fill(NaN); let ok = true;
      if (packedBanks) {
        for (const [kind, off, tagRe] of [["k", 0, /"K([0-9A-F]{3})"\s*(calc\([^)]*\)|[-+\d.eE]+)/g], ["v", 768, /"V([0-9A-F]{3})"\s*(calc\([^)]*\)|[-+\d.eE]+)/g]]) {
          const list = c.getPropertyValue(`--fc-${kind}-${s}`); const scales = []; for (let h = 0; h < heads; h++) scales.push(num(c.getPropertyValue(`--fc-${kind}s-${s}-${h}`)));
          if (L === 0 && s === 0) rawSample[kind] = { list: list.slice(0, 160), scales: scales.slice(0, 3) };
          let mm, n = 0; while ((mm = tagRe.exec(list))) { const idx = parseInt(mm[1], 16); values[off + idx] = num(mm[2]) * scales[idx >> 6]; n++; }
          if (n !== 768) ok = false; } }
      else {
        for (let h = 0; h < heads; h++) { for (const [kind, off] of [["k", 0], ["v", 768]]) {
          const list = c.getPropertyValue(`--fc-${kind}-${s}-${h}`); const scale = num(c.getPropertyValue(`--fc-${kind}s-${s}-${h}`));
          if (L === 0 && s === 0 && h === 0) rawSample[kind] = { list: list.slice(0, 160), scale };
          const re = /"K(\d{3})"\s*(calc\([^)]*\)|[-+\d.eE]+)/g; let mm, n = 0;
          while ((mm = re.exec(list))) { values[off + h * 64 + Number(mm[1])] = num(mm[2]) * scale; n++; }
          if (n !== 64) ok = false; } } }
      caches.push({ layer: L, slot: s, position: s, values, complete: ok }); } }
  const body = cs(document.body); const bodyProps = {}; for (const k of ["--epoch", "--winner", "--head-output-epoch", "--token"]) bodyProps[k] = body.getPropertyValue(k);
  return { tokens, slotProps, tokensText, finalResidual, finalHidden, headSample, caches, rawSample, bodyProps };
}, { capacity, blocks, heads, packedBanks, packedHead });
const doneMarkers = {}; for (let i = 1; i <= capacity; i++) doneMarkers[i] = (await q(`#token-${i}-captured.done`)) !== 0;
log("final", { packedBanks, packedHead, headSample: result.headSample, tokens: result.tokens, tokensText: result.tokensText, bodyProps: result.bodyProps, doneMarkers, rawSample: result.rawSample, cachesComplete: result.caches.filter((c) => c.complete).length, tokenTimes });
fs.writeFileSync(`${outDir}/verification-vectors.json`, JSON.stringify({ tokens: result.tokens, prompt: 15496, finalResidual: result.finalResidual, finalHidden: result.finalHidden, caches: result.caches.map(({ layer, slot, position, values }) => ({ layer, slot, position, values })), cacheReadbackScope: "all retained native cache slots (R2C correctness run)" }));
fs.writeFileSync(`${outDir}/pipeline-results.json`, JSON.stringify({ complete: stopReason === "token-limit" && result.tokens.every((t) => Number.isFinite(t) && t > 0), stopReason, tokenTimesMs: tokenTimes, harness: "work/2026-09-19/R2C/correctness_run.mjs (correctness only, not a timing run)", browserArguments: args, browser: browser.version(), artifactSha256: {}, metricsAfter: m }, null, 2));
await page.screenshot({ path: `${outDir}/screenshot.png` }).catch(() => {});
await browser.close();
log("closed");
