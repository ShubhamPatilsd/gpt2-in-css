// R6V load-time UX probe (NOT a timing run): navigate to a bundle, take screenshots at fixed times after navigation start
// (0.5 1 2 4 8 16 24 32 48 s or until the fonts-loaded marker), record paint timings + the loading panel's text at each
// step, then click Run and take mid-token screenshots at +6/+12/+18 s (cap 8: token 1 takes ~16-20 s). Screenshots force
// frames; this run's numbers are for the UX check only. env: R6V_URL R6V_OUT [R6V_RUN=1]
import fs from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = process.env.R6V_URL, outDir = process.env.R6V_OUT, doRun = process.env.R6V_RUN === "1";
const t0 = performance.now(); const now = () => Math.round(performance.now() - t0);
const log = (event, extra = {}) => console.log(JSON.stringify({ t: now(), event, ...extra }));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const args = ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--force-device-scale-factor=1",
  "--hide-scrollbars", "--disable-background-networking", "--disable-component-update", "--js-flags=--heap-growing-percent=10"];
const browser = await chromium.launch({ executablePath, headless: true, args });
const context = await browser.newContext({ viewport: { width: 900, height: 300 } });
const page = await context.newPage();
const cdp = await context.newCDPSession(page);
await cdp.send("DOM.enable");
log("launched", { version: browser.version(), url });
const tNav = now();
const nav = page.goto(url, { waitUntil: "load", timeout: 600000 }).then(() => log("load-event", { sinceNavMs: now() - tNav })).catch((e) => log("goto-error", { error: String(e) }));
const steps = [500, 1000, 2000, 4000, 8000, 12000, 16000, 24000, 32000, 40000, 48000, 60000];
const panelText = async () => page.evaluate(() => {
  const txt = (sel) => { const el = document.querySelector(sel); if (!el) return null; const cs = getComputedStyle(el, "::after"); return { display: getComputedStyle(el).display, after: cs.content }; };
  const paints = performance.getEntriesByType("paint").map((p) => ({ name: p.name, t: Math.round(p.startTime) }));
  return { readyState: document.readyState, elements: document.getElementsByTagName("*").length, fonts: document.fonts ? document.fonts.size : null,
    status: txt(".status"), ld: txt(".ld-label"), ldn: txt(".ld-n"), pgtok: txt(".pg-tok"), pglay: txt(".pg-lay"), fontsLoaded: !!document.querySelector("#fonts-loaded.done"), paints };
}).catch((e) => ({ error: String(e).slice(0, 120) }));
let fontsDone = false;
for (const ms of steps) {
  const wait = tNav + ms - now(); if (wait > 0) await sleep(wait);
  const tag = `load-${ms / 1000}s`;
  await page.screenshot({ path: `${outDir}/shot-${tag}.png`, timeout: 20000 }).then(() => log("screenshot", { file: `shot-${tag}.png`, sinceNavMs: now() - tNav })).catch((e) => log("screenshot-failed", { tag, error: String(e).slice(0, 100) }));
  const info = await panelText(); log("state", { tag, sinceNavMs: now() - tNav, ...info });
  if (info.fontsLoaded) { fontsDone = true; break; }
}
await nav;
if (!fontsDone) { for (let i = 0; i < 60 && !(await page.evaluate(() => !!document.querySelector("#fonts-loaded.done")).catch(() => false)); i++) await sleep(2000); }
log("fonts-loaded", { sinceNavMs: now() - tNav, ...(await panelText()) });
await page.screenshot({ path: `${outDir}/shot-ready.png` }).catch(() => {});
if (doRun) {
  const { root } = await cdp.send("DOM.getDocument", { depth: 1 });
  const q = async (sel) => (await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: sel })).nodeId;
  const runNode = await q("#run");
  const box = (await cdp.send("DOM.getBoxModel", { nodeId: runNode })).model.content;
  const point = { x: (box[0] + box[2]) / 2, y: (box[1] + box[5]) / 2, button: "left", clickCount: 1 };
  const tRun = now();
  await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", ...point });
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", ...point });
  log("run-clicked");
  for (const ms of [3000, 6000, 9000, 12000, 15000, 18000, 24000, 30000, 36000]) {
    const wait = tRun + ms - now(); if (wait > 0) await sleep(wait);
    const tag = `run-${ms / 1000}s`;
    await page.screenshot({ path: `${outDir}/shot-${tag}.png`, timeout: 30000 }).then(() => log("screenshot", { file: `shot-${tag}.png`, sinceRunMs: now() - tRun })).catch((e) => log("screenshot-failed", { tag, error: String(e).slice(0, 100) }));
    const info = await panelText(); const tok1 = (await q("#token-1-captured.done")) !== 0; const tok2 = (await q("#token-2-captured.done")) !== 0;
    log("state", { tag, sinceRunMs: now() - tRun, pgtok: info.pgtok, pglay: info.pglay, status: info.status, tok1, tok2 });
    if (tok2) break;
  }
}
await browser.close();
log("closed");
