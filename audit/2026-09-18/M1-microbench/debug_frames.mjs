import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const url = `file://${process.cwd()}/pages/mb2-a-var-N0-b0.html`;
async function rsc(cdp) { const { metrics } = await cdp.send("Performance.getMetrics"); return metrics.find((m) => m.name === "RecalcStyleCount").value; }
async function trial(label, args, prep, jsEnabled = false) {
  const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true, args });
  const ctx = await browser.newContext({ javaScriptEnabled: jsEnabled, viewport: { width: 800, height: 600 } });
  const page = await ctx.newPage(); const cdp = await ctx.newCDPSession(page);
  await cdp.send("Performance.enable", process.env.TD ? { timeDomain: "timeTicks" } : {}); await cdp.send("DOM.enable");
  await page.goto(url, { waitUntil: "load" }); await sleep(600);
  if (prep) await prep(page, cdp);
  const { root } = await cdp.send("DOM.getDocument", { depth: 1 });
  const html = root.children.find((c) => c.localName === "html");
  const r0 = await rsc(cdp); const t0 = performance.now();
  await cdp.send("DOM.setAttributeValue", { nodeId: html.nodeId, name: "class", value: "go-3" });
  let r1 = r0, t1 = null;
  while (performance.now() - t0 < 2500) { await sleep(25); r1 = await rsc(cdp); if (r1 !== r0) { t1 = performance.now() - t0; break; } }
  let vis = null; try { vis = jsEnabled ? await page.evaluate(() => [document.visibilityState, document.hasFocus()]) : null; } catch {}
  console.log(`${label}: RSC ${r0} -> ${r1} ${t1 ? `after ${t1.toFixed(0)} ms` : "NO RECALC in 2.5 s"} ${vis ? JSON.stringify(vis) : ""}`);
  await browser.close();
}
await trial("flag --disable-backgrounding-occluded-windows", ["--disable-backgrounding-occluded-windows"]);
await trial("all three run.mjs flags", ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows"]);
