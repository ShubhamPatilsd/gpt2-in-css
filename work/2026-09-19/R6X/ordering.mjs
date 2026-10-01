// R6X v5 ordering probe (diagnosis, not a timing run): HEADED, user-like input. Load → Ready → optional browser zoom (Meta+= × N) → click into
// the editor, move the caret between the quotes, type with real keystrokes (80 ms) → MOUSE click on the Run checkbox → record ~40 animation
// frames of: --prompt-armed (.tk-root), .tk-high-3 ids/present/count, --prompt-live, #run-latched.done, .embedding-receipt --embed-ready/--embed-stamp,
// .feedback-select --token, body --epoch → then wait for R6X_TOKENS captures and dump winners (--feedback-i), display tokens and the readout.
// env: R6X_URL R6X_OUT R6X_TYPED [R6X_ZOOM_STEPS=0] [R6X_TOKENS=5] [R6X_VIEWPORT=1100x700] [R6X_CAP_MS=600000]
import fs from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = process.env.R6X_URL, outDir = process.env.R6X_OUT, typed = process.env.R6X_TYPED ?? "Shubham was";
const zoomSteps = Number(process.env.R6X_ZOOM_STEPS ?? 0), wantTokens = Number(process.env.R6X_TOKENS ?? 5), capMs = Number(process.env.R6X_CAP_MS ?? 600000);
const [vpW, vpH] = (process.env.R6X_VIEWPORT ?? "1100x700").split("x").map(Number);
const t0 = performance.now(); const now = () => Math.round(performance.now() - t0);
const log = (event, extra = {}) => console.log(JSON.stringify({ t: now(), event, ...extra }));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch({ executablePath, headless: false, args: ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--force-device-scale-factor=1", `--window-size=${vpW},${vpH + 90}`, "--js-flags=--heap-growing-percent=10"] });
const context = await browser.newContext({ viewport: { width: vpW, height: vpH } });
const page = await context.newPage();
const cdp = await context.newCDPSession(page); await cdp.send("DOM.enable");
log("launched", { version: browser.version(), url, typed, zoomSteps });
await page.goto(url, { waitUntil: "load", timeout: 600000 }); log("loaded");
for (let i = 0; i < 90 && !(await page.evaluate(() => !!document.querySelector("#fonts-loaded.done"))); i++) await sleep(1000);
log("ready", { sinceStart: now() });
const state = () => page.evaluate(() => {
  const g = (sel, props, pseudo) => { const e = document.querySelector(sel); if (!e) return null; const cs = getComputedStyle(e, pseudo); const o = {}; for (const p of props) o[p] = p === "content" ? cs.content.slice(0, 200) : cs.getPropertyValue(p).trim(); return o; };
  return { armedRoot: g(".tk-root", ["--prompt-armed", "--prompt-live"]), high3: g(".tk-high-3", ["--prompt-count", "--prompt-token-id-0", "--prompt-token-id-1", "--prompt-token-id-2", "--prompt-token-id-3", "--pt-present-0", "--pt-id-0", "--prompt-armed"]),
    runChecked: document.getElementById("run").checked, runLatched: !!document.querySelector("#run-latched.done"), fontsLoaded: !!document.querySelector("#fonts-loaded.done"),
    receipt: g(".embedding-receipt", ["--embed-ready", "--embed-stamp", "--epoch"]), select: g(".feedback-select", ["--token", "--prompt-count"]), epoch: getComputedStyle(document.body).getPropertyValue("--epoch").trim(),
    output: g("#visible-output", ["--prompt-count", "--display-prompt", "--draft-echo", "--display-token-1", "--display-token-2", "--display-token-3", "--display-token-4", "--display-token-5"]), before: g("#visible-output", ["content"], "::before"), tkTokens: g(".tk-tokens", ["content"], "::after"), editor: document.getElementById("tk-editor").textContent, zoom: window.devicePixelRatio, innerW: window.innerWidth };
});
if (zoomSteps > 0) { for (let i = 0; i < zoomSteps; i++) { await page.keyboard.press("Meta+Equal"); await sleep(400); } log("zoomed", { steps: zoomSteps, ...(await state()) }); await sleep(1500); }
await page.screenshot({ path: `${outDir}/shot-ready.png` }).catch(() => {});
// type like a user: click into the editor, caret to the end, back 4 chars (before `"; }`), type with delay
await page.locator("#tk-editor").click(); await page.keyboard.press("End"); for (let i = 0; i < 4; i++) await page.keyboard.press("ArrowLeft");
await page.keyboard.type(typed, { delay: 80 }); await sleep(1500);
log("typed", await state()); await page.screenshot({ path: `${outDir}/shot-typed.png` }).catch(() => {});
// frame recorder (rAF) started just before the mouse click on the checkbox
const framesP = page.evaluate(() => new Promise((resolve) => {
  const out = []; let n = 0; const t0 = performance.now();
  const rd = (sel, p, pseudo) => { const e = document.querySelector(sel); return e ? getComputedStyle(e, pseudo).getPropertyValue(p).trim() : null; };
  const tick = () => { out.push({ f: n++, ms: Math.round(performance.now() - t0), armed: rd(".tk-root", "--prompt-armed"), live: rd(".tk-root", "--prompt-live"), count: rd(".tk-high-3", "--prompt-count"), id0: rd(".tk-high-3", "--prompt-token-id-0"), id3: rd(".tk-high-3", "--prompt-token-id-3"), latched: !!document.querySelector("#run-latched.done"), ready: rd(".embedding-receipt", "--embed-ready"), stamp: rd(".embedding-receipt", "--embed-stamp"), token: rd(".feedback-select", "--token"), epoch: rd("body", "--epoch"), selCount: rd(".feedback-select", "--prompt-count") }); if (n < 45) requestAnimationFrame(tick); else resolve(out); };
  requestAnimationFrame(tick); }));
await sleep(50);
const tClick = now();
await page.locator("#run").click();  // MOUSE click on the checkbox (user-like)
log("run-clicked", { sinceStart: tClick });
const frames = await framesP;
for (const f of frames) log("frame", f);
fs.writeFileSync(`${outDir}/frames.json`, JSON.stringify(frames));
log("after-click", await state());
const { root } = await cdp.send("DOM.getDocument", { depth: 1 });
const q = async (sel) => (await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: sel })).nodeId;
let next = 1; const tRun = now();
while (next <= wantTokens && now() - tRun < capMs) { await sleep(1000); if ((await q(`#token-${next}-captured.done`)) !== 0) { log("token-captured", { k: next, sinceRun: now() - tRun, ...(await state()) }); next++; } }
const fb = await page.evaluate((n) => { const vo = document.getElementById("visible-output"); const cs = getComputedStyle(vo); const o = { feedback: [], display: [] }; for (let i = 1; i <= n; i++) { o.feedback.push(cs.getPropertyValue("--feedback-" + i).trim()); o.display.push(cs.getPropertyValue("--display-token-" + i).trim()); } return o; }, wantTokens);
log("winners", { ...fb, ...(await state()) });
await page.screenshot({ path: `${outDir}/shot-after-${wantTokens}.png` }).catch(() => {});
await browser.close(); log("closed");
