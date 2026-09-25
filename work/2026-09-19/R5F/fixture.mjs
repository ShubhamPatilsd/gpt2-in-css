// R5F copy of the R5M memory fixture harness (results to R5F/fx-results): ONE fresh headless Chrome (same launch args as the bench harness, heap flag ON by default),
// navigate to a page (no JS in the page), wait for load + lifecycle settle, sample renderer RSS (ps) until stable, then optional
// CDP-driven generations (DOM.setAttributeValue class=gN on <html>), then HeapProfiler.collectGarbage, then
// Memory.simulatePressureNotification(critical) — RSS after each. Output: one JSON per page to R5M/fx-results/<label>.json.
// Passive apart from the attribute writes and Performance.getMetrics/ps reads. Usage:
//   node fixture.mjs <label> <url> [gens] [settleMs]     (env: R5M_HEAP=0 to drop --js-flags=--heap-growing-percent=10)
import fs from "node:fs";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const [label, url, gensArg, settleArg] = process.argv.slice(2);
if (!label || !url) throw new Error("usage: fixture.mjs <label> <url> [gens] [settleMs]");
const gens = Number(gensArg ?? 0);
const settleMs = Number(settleArg ?? 4000);
const outDir = new URL("./fx-results/", import.meta.url).pathname; fs.mkdirSync(outDir, { recursive: true });
const args = ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--force-device-scale-factor=1", "--hide-scrollbars",
  "--disable-background-networking", "--disable-component-update"];
if (process.env.R5M_HEAP !== "0") args.push("--js-flags=--heap-growing-percent=10");
const t0 = performance.now(); const now = () => Math.round(performance.now() - t0);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch({ executablePath, headless: true, args });
const bcdp = await browser.newBrowserCDPSession();
const context = await browser.newContext({ viewport: { width: 900, height: 300 } });
const page = await context.newPage();
const cdp = await context.newCDPSession(page);
await cdp.send("Performance.enable", { timeDomain: "timeTicks" });
await cdp.send("DOM.enable"); await cdp.send("HeapProfiler.enable");
async function rendererPids() { const { processInfo } = await bcdp.send("SystemInfo.getProcessInfo"); return processInfo.filter((p) => p.type === "renderer").map((p) => p.id); }
function rssOf(pids) { if (!pids.length) return 0; const out = execSync(`ps -o pid=,rss= -p ${pids.join(",")}`).toString(); let m = 0; for (const l of out.split("\n")) { const x = l.trim().split(/\s+/); if (x.length === 2) m = Math.max(m, Math.round(Number(x[1]) / 1024)); } return m; }
async function rss() { return rssOf(await rendererPids()); }
async function metrics() { const { metrics } = await cdp.send("Performance.getMetrics"); const o = {}; for (const m of metrics) o[m.name] = m.value; return o; }
// wait until RSS and RecalcStyleCount are unchanged for settleMs (poll 1 s), cap 300 s
async function settle(tag) {
  let last = null, stableSince = now(), start = now(), samples = [];
  while (now() - start < 300000) {
    const m = await metrics(); const r = await rss(); const key = `${m.RecalcStyleCount}/${m.LayoutCount}/${Math.round(r / 20)}`;
    samples.push({ t: now(), rssMB: r, recalcs: m.RecalcStyleCount, layouts: m.LayoutCount });
    if (key !== last) { last = key; stableSince = now(); } else if (now() - stableSince >= settleMs) break;
    await sleep(1000);
  }
  const m = await metrics(); const r = await rss();
  const row = { tag, t: now(), rssMB: r, recalcs: m.RecalcStyleCount, layouts: m.LayoutCount, styleMs: Math.round(m.RecalcStyleDuration * 1000), layoutMs: Math.round(m.LayoutDuration * 1000), nodes: m.Nodes, layoutObjects: m.LayoutObjects, jsHeapMB: Math.round(m.JSHeapUsedSize / 1e6), taskMs: Math.round(m.TaskDuration * 1000) };
  console.log(JSON.stringify(row)); return { row, samples };
}
const result = { label, url, args, gens, settleMs, steps: [] };
const { row: r0 } = await settle("blank"); result.steps.push(r0);
const tNav = now();
await page.goto(url, { waitUntil: "load", timeout: 600000 });
result.loadMs = now() - tNav;
const { row: r1, samples } = await settle("loaded"); result.steps.push(r1); result.loadSamples = samples;
const { root } = await cdp.send("DOM.getDocument", { depth: 1 });
const html = root.children?.find((c) => c.nodeName === "HTML") ?? root.children?.[0];
for (let g = 1; g <= gens; g++) {
  await cdp.send("DOM.setAttributeValue", { nodeId: html.nodeId, name: "class", value: `g${g}` });
  const { row } = await settle(`gen${g}`); result.steps.push(row);
}
await cdp.send("HeapProfiler.collectGarbage"); await sleep(1500);
result.steps.push((await settle("afterGC")).row);
try { await cdp.send("Memory.simulatePressureNotification", { level: "critical" }); await sleep(2500); result.steps.push((await settle("afterPressure")).row); }
catch (e) { result.pressureError = String(e); }
result.rendererCount = (await rendererPids()).length;
fs.writeFileSync(`${outDir}${label}.json`, JSON.stringify(result, null, 1));
await browser.close();
console.log(`DONE ${label} load=${result.loadMs}ms ` + result.steps.map((s) => `${s.tag}:${s.rssMB}MB`).join(" "));
