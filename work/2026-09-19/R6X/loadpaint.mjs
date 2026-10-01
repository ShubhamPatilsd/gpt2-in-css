// R6X copy of R6V/loadpaint.mjs (+ prompt-panel fields) — load-time UX probe (NOT a timing run): navigate to a bundle, take screenshots at fixed times after navigation start
// (0.5 1 2 4 8 16 24 32 48 s or until the fonts-loaded marker), record paint timings + the loading panel's text at each
// step, then click Run and take mid-token screenshots at +6/+12/+18 s (cap 8: token 1 takes ~16-20 s). Screenshots force
// frames; this run's numbers are for the UX check only. env: R6X_URL R6X_OUT [R6X_RUN=1]
import fs from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = process.env.R6X_URL, outDir = process.env.R6X_OUT, doRun = process.env.R6X_RUN === "1";
const t0 = performance.now(); const now = () => Math.round(performance.now() - t0);
const log = (event, extra = {}) => console.log(JSON.stringify({ t: now(), event, ...extra }));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const args = ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--force-device-scale-factor=1",
  "--hide-scrollbars", "--disable-background-networking", "--disable-component-update", "--js-flags=--heap-growing-percent=10"];
const browser = await chromium.launch({ executablePath, headless: true, args });
const [vpW, vpH] = (process.env.R6X_VIEWPORT ?? "900x300").split("x").map(Number);  // R6X v2: e.g. 900x600 to see 2-3 output lines + footer
const context = await browser.newContext({ viewport: { width: vpW, height: vpH } });
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
    status: txt(".status"), editor: (() => { const e = document.getElementById("tk-editor"); return e ? { display: getComputedStyle(e).display, text: e.textContent } : null; })(), tkTokens: txt(".tk-tokens"), ld: txt(".ld-label"), ldn: txt(".ld-n"), pgtok: txt(".pg-tok"), pglay: txt(".pg-lay"), fontsLoaded: !!document.querySelector("#fonts-loaded.done"), paints };
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
  // R6X v2: R6X_TYPED = text typed into the editable <style id="tk-editor"> (Playwright fill = harness-side select-all + insertText; the page stays JS-free),
  // then Run via DOM.focus(#run) + Space (R3K keyboard trigger), screenshots at R6X_SHOTS seconds after Run and when the run completes
  // (#token-<cap>-captured.done or #eos-done.done, polled every 5 s, cap R6X_WAIT_MS), then one more at 900x300 for the short-viewport check.
  const typed = process.env.R6X_TYPED ?? "";
  const cap = Number(process.env.R6X_CAPACITY ?? 32);
  const waitMs = Number(process.env.R6X_WAIT_MS ?? 1500000);
  const shots = (process.env.R6X_SHOTS ?? "10").split(",").filter(Boolean).map(Number).sort((a, b) => a - b);
  if (typed) {
    await page.locator("#tk-editor").fill(`.tk-root { --draft-prompt: "${typed.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"; }`);
    await sleep(1500);
    const info = await panelText(); log("prompt-typed", { typed, tkTokens: info.tkTokens, editor: info.editor });
    await page.screenshot({ path: `${outDir}/shot-typed.png` }).catch(() => {});
  }
  const { root } = await cdp.send("DOM.getDocument", { depth: 1 });
  const q = async (sel) => (await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: sel })).nodeId;
  const runNode = await q("#run");
  await cdp.send("DOM.focus", { nodeId: runNode });
  const key = { key: " ", code: "Space", windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 32 };
  const tRun = now();
  await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", text: " ", unmodifiedText: " ", ...key });
  await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", ...key });
  log("run-keyed");
  const overlap = async () => page.evaluate(() => {
    const r = (sel) => { const e = document.querySelector(sel); if (!e) return null; const b = e.getBoundingClientRect(); return { top: Math.round(b.top), bottom: Math.round(b.bottom), height: Math.round(b.height), scrollH: e.scrollHeight }; };
    const out = r("#visible-output"), foot = r(".tk-aside");
    return { output: out, footer: foot, overlap: out && foot ? out.bottom > foot.top && foot.bottom > out.top : null, text: (getComputedStyle(document.querySelector("#visible-output"), "::after").content || "").length };
  }).catch((e) => ({ error: String(e).slice(0, 120) }));
  for (const s of shots) {
    const wait = tRun + s * 1000 - now(); if (wait > 0) await sleep(wait);
    await page.screenshot({ path: `${outDir}/shot-run-${s}s.png`, timeout: 30000 }).then(() => log("screenshot", { file: `shot-run-${s}s.png`, sinceRunMs: now() - tRun })).catch((e) => log("screenshot-failed", { s, error: String(e).slice(0, 100) }));
    log("state", { tag: `run-${s}s`, ...(await panelText()), geometry: await overlap() });
  }
  // R6X v3: screenshots of the vocabulary-head phase (--held:1 on .core-controller): poll the computed value once per second until
  // R6X_HEAD_SHOTS shots are taken (a UX probe — the computed-style read may force a style recalc; not a timing run).
  const headShotsWanted = Number(process.env.R6X_HEAD_SHOTS ?? 3); let headShots = 0, lastHeld = "0";
  const held = async () => page.evaluate(() => { const c = document.querySelector(".core-controller"); const cs = getComputedStyle(c); return { held: cs.getPropertyValue("--held").trim(), layer: cs.getPropertyValue("--layer").trim(), epoch: getComputedStyle(document.body).getPropertyValue("--epoch").trim(), lay: getComputedStyle(document.querySelector(".pg-lay"), "::after").content }; }).catch((e) => ({ error: String(e).slice(0, 80) }));
  let doneWhy = null;
  while (now() - tRun < waitMs) {
    if (headShots < headShotsWanted) {
      await sleep(1000);
      const h = await held();
      if (h.held === "1" && lastHeld !== "1") {
        headShots++;
        await page.screenshot({ path: `${outDir}/shot-head-${headShots}.png`, timeout: 30000 }).then(() => log("screenshot", { file: `shot-head-${headShots}.png`, sinceRunMs: now() - tRun, ...h })).catch((e) => log("screenshot-failed", { tag: "head", error: String(e).slice(0, 100) }));
        if (headShots === 1) { await sleep(1200); const h2 = await held(); await page.screenshot({ path: `${outDir}/shot-head-1b.png`, timeout: 30000 }).then(() => log("screenshot", { file: "shot-head-1b.png", sinceRunMs: now() - tRun, ...h2 })).catch(() => {}); }
      }
      lastHeld = h.held ?? lastHeld;
      if (headShots >= headShotsWanted) log("head-shots-done", { sinceRunMs: now() - tRun });
      if (now() % 5000 >= 4000) { /* fall through to the completion check below once per ~5 s */ } else continue;
    } else await sleep(5000);
    try { if ((await q(`#token-${cap}-captured.done`)) !== 0) { doneWhy = "token-limit"; break; } if ((await q("#eos-done.done")) !== 0) { doneWhy = "eos"; break; } } catch {}
  }
  log("run-complete", { doneWhy, sinceRunMs: now() - tRun });
  await sleep(2000);
  await page.screenshot({ path: `${outDir}/shot-complete.png`, timeout: 30000 }).catch(() => {});
  log("state", { tag: "complete", ...(await panelText()), geometry: await overlap() });
  await page.setViewportSize({ width: 900, height: 300 }); await sleep(1500);
  await page.screenshot({ path: `${outDir}/shot-complete-900x300.png`, timeout: 30000 }).catch(() => {});
  log("state", { tag: "complete-900x300", geometry: await overlap() });
}
await browser.close();
log("closed");
