// R2F load diagnostic (correctness/diagnosis only): open each URL with waitUntil "commit" and poll readyState, fonts, metrics.
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");
const urls = process.env.R2F_URLS.split(","); const secs = Number(process.env.R2F_SECS ?? 90);
const t0 = performance.now(); const now = () => Math.round(performance.now() - t0);
const log = (e, x = {}) => console.log(JSON.stringify({ t: now(), e, ...x }));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const race = (p, ms) => Promise.race([p, sleep(ms).then(() => "TIMEOUT")]);
const args = ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--force-device-scale-factor=1", "--hide-scrollbars", "--js-flags=--heap-growing-percent=10"];
const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true, args });
for (const url of urls) {
  const context = await browser.newContext({ viewport: { width: 900, height: 300 } });
  const page = await context.newPage(); const cdp = await context.newCDPSession(page);
  await cdp.send("Performance.enable", { timeDomain: "timeTicks" });
  log("goto", { url });
  const t1 = now();
  page.goto(url, { waitUntil: "commit", timeout: 60000 }).then(() => log("committed", { url, ms: now() - t1 })).catch((e) => log("goto-error", { error: String(e).slice(0, 200) }));
  page.on("load", () => log("load-event", { url, ms: now() - t1 }));
  page.on("crash", () => log("CRASH", { url }));
  const end = now() + secs * 1000; let last = null;
  while (now() < end) {
    await sleep(5000);
    const m = await race(cdp.send("Performance.getMetrics").then(({ metrics }) => Object.fromEntries(metrics.map((x) => [x.name, +x.value.toFixed(2)]))), 4000);
    const st = await race(page.evaluate(() => ({ rs: document.readyState, fonts: document.fonts.status, loaded: !!document.querySelector("#fonts-loaded.done"), n: document.getElementsByTagName("*").length })), 4000);
    const row = m === "TIMEOUT" ? { metrics: "TIMEOUT", st } : { st, Recalc: m.RecalcStyleCount, RecalcS: m.RecalcStyleDuration, Layout: m.LayoutCount, LayoutS: m.LayoutDuration, Task: m.TaskDuration, Nodes: m.Nodes, JSHeap: m.JSHeapUsedSize };
    log("poll", row);
    if (st !== "TIMEOUT" && st.rs === "complete" && st.loaded && last && last.Recalc === row.Recalc) break;
    last = row;
  }
  await context.close();
}
await browser.close(); log("closed");
