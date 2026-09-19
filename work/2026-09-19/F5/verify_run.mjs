// F5 correctness run (NOT a timing run): headless Chrome 153 loads the bundle, clicks Run once,
// waits passively for #token-8-captured.done (poll every 5 s), then reads the 8 generated ids from
// the retained --saved-token-N values and the decoded text. Pattern: work/2026-09-19/B0/bench_native.mjs.
import fs from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = process.env.F5_URL;
const out = process.env.F5_OUT;
const capacity = Number(process.env.F5_CAPACITY ?? 8);
const capMs = Number(process.env.F5_CAP_MS ?? 900000);
if (!url || !out) throw new Error("F5_URL and F5_OUT required");
const t0 = performance.now();
const now = () => Math.round(performance.now() - t0);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (event, extra = {}) => console.log(JSON.stringify({ t: now(), event, ...extra }));

const args = ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--force-device-scale-factor=1",
  "--hide-scrollbars", "--disable-background-networking", "--disable-component-update", "--js-flags=--heap-growing-percent=10"];
const browser = await chromium.launch({ executablePath, headless: true, args });
const context = await browser.newContext({ viewport: { width: 900, height: 300 } });
const page = await context.newPage();
const cdp = await context.newCDPSession(page);
await cdp.send("Performance.enable", { timeDomain: "timeTicks" });
await cdp.send("DOM.enable");
await cdp.send("CSS.enable");
log("launched", { version: browser.version(), url });
const metrics = async () => Object.fromEntries((await cdp.send("Performance.getMetrics")).metrics.map((m) => [m.name, m.value]));

await page.goto(url, { waitUntil: "load", timeout: 600000 });
log("load-event");
// pre-run idle: RecalcStyleCount unchanged for 2 s
{ let last = (await metrics()).RecalcStyleCount, since = now(); const lim = now() + 90000; while (now() - since < 2000 && now() < lim) { await sleep(250); const m = await metrics(); if (m.RecalcStyleCount !== last) { last = m.RecalcStyleCount; since = now(); } } }
const { root } = await cdp.send("DOM.getDocument", { depth: 1 });
const q = async (sel) => (await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: sel })).nodeId;
const runNode = await q("#run");
const box = (await cdp.send("DOM.getBoxModel", { nodeId: runNode })).model.content;
const point = { x: (box[0] + box[2]) / 2, y: (box[1] + box[5]) / 2, button: "left", clickCount: 1 };
const m0 = await metrics();
const tRun = now();
await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", ...point });
await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", ...point });
log("run-clicked");
const tokens = [];
let nextToken = 1, stop = "cap";
const deadline = tRun + capMs;
while (now() < deadline) {
  await sleep(5000);
  const done = await q(`#token-${nextToken}-captured.done`);
  if (done) {
    const prev = tokens.length ? tokens[tokens.length - 1].t : tRun;
    tokens.push({ k: nextToken, t: now(), tokenSeconds: (now() - prev) / 1000 });
    log("token-captured", tokens[tokens.length - 1]);
    nextToken++;
    if (nextToken > capacity) { stop = "token-limit"; break; }
  }
  if (await q("#eos-done.done")) { stop = "eos"; break; }
}
await sleep(2000);
const m1 = await metrics();
// readback AFTER the run: style reads are allowed now
const ids = [];
for (let i = 1; i <= capacity; i++) {
  try {
    const nodeId = await q(`.token-slot-${i}`);
    const { computedStyle } = await cdp.send("CSS.getComputedStyleForNode", { nodeId });
    ids.push(Number(computedStyle.find((p) => p.name === `--saved-token-${i}`)?.value));
  } catch (e) { ids.push(null); }
}
let text = null;
try { text = await page.evaluate(() => { const o = document.getElementById("visible-output"); return getComputedStyle(o, "::before").content + " | " + getComputedStyle(o, "::after").content; }); } catch (e) { text = String(e); }
const result = { url, stop, wallSeconds: (now() - tRun) / 1000, tokens, ids, text,
  metricsDelta: { RecalcStyleCount: m1.RecalcStyleCount - m0.RecalcStyleCount, LayoutCount: m1.LayoutCount - m0.LayoutCount,
    RecalcStyleDurationS: m1.RecalcStyleDuration - m0.RecalcStyleDuration, LayoutDurationS: m1.LayoutDuration - m0.LayoutDuration, TaskDurationS: m1.TaskDuration - m0.TaskDuration } };
fs.writeFileSync(out, JSON.stringify(result, null, 1));
log("done", result);
await browser.close();
