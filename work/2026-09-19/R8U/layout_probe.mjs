// R8U layout probe (UX check, NOT a timing run): HEADED Chrome, classic scrollbars SHOWN (no --hide-scrollbars), one viewport.
// Screenshots at 0.5/1/2/4/8 s after navigation (until Ready), Ready, after typing R8U_TYPED, then Run (DOM.focus #run + Space) and
// screenshots at R8U_SHOTS seconds after Run; optionally waits for completion (R8U_FULL=1). At every shot: a geometry dump of all UI
// boxes (rects, display) + checks: pairwise overlap of the visible row boxes, right edge inside the viewport, header lines not ellipsised,
// row-1 / row-2 control items vertically aligned. env: R8U_URL R8U_OUT R8U_VIEWPORT=WxH [R8U_TYPED] [R8U_SHOTS=25,70] [R8U_FULL=0] [R8U_CAPACITY=36]
import fs from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require(`${process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"}/playwright`);
const executablePath = process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = process.env.R8U_URL, out = process.env.R8U_OUT;
const [vpW, vpH] = (process.env.R8U_VIEWPORT ?? "1100x700").split("x").map(Number);
const t0 = performance.now(); const now = () => Math.round(performance.now() - t0);
const log = (event, extra = {}) => { const l = JSON.stringify({ t: now(), event, ...extra }); console.log(l); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const args = ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--force-device-scale-factor=1",
  "--disable-background-networking", "--disable-component-update", "--js-flags=--heap-growing-percent=10", `--window-size=${vpW},${vpH + 90}`];
const browser = await chromium.launch({ executablePath, headless: false, args });
const context = await browser.newContext({ viewport: { width: vpW, height: vpH } });
const page = await context.newPage();
const cdp = await context.newCDPSession(page); await cdp.send("DOM.enable");
log("launched", { version: browser.version(), url, viewport: [vpW, vpH], args });
const tNav0 = () => globalThis.__tNav ?? 0;
const geometry = async () => page.evaluate(() => {
  const vis = (e) => { if (!e) return false; for (let n = e; n && n.nodeType === 1; n = n.parentElement) { const cs = getComputedStyle(n); if (cs.display === "none" || cs.visibility === "hidden" || cs.contentVisibility === "hidden" && n !== e) return false; } const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const box = (name, e) => { if (!e) return null; const r = e.getBoundingClientRect(); return { name, vis: vis(e), l: Math.round(r.left), t: Math.round(r.top), r: Math.round(r.right), b: Math.round(r.bottom), sw: e.scrollWidth, cw: e.clientWidth }; };
  const q = (s) => document.querySelector(s);
  const c = q(".controls"); const kids = c ? [...c.children] : [];
  const items = [
    box("title", q(".r8u-title")), ...[...document.querySelectorAll(".r8u-lede>span")].map((e, i) => box("lede" + i, e)), box("notes", q(".r8u-notes")),
    ...kids.map((e, i) => box("ctl" + i + ":" + (e.className || e.tagName.toLowerCase()) + (e.tagName === "LABEL" ? ":" + e.textContent.trim().slice(0, 8) : ""), e)),
    box("tk-editor", q("#tk-editor")), box("tk-tokens", q(".tk-tokens")),
    box("ld", q(".ld")), box("ld-n", q(".ld-n")), box("ld2-track", q(".ld2 .ld-track")), box("pg", q(".pg")),
    box("output", q("#visible-output")), box("footer", q(".tk-aside")), box("fb-warn", q(".fb-warn")),
  ].filter(Boolean);
  const v = items.filter((b) => b.vis);
  const overlaps = [];
  for (let i = 0; i < v.length; i++) for (let j = i + 1; j < v.length; j++) { const a = v[i], b = v[j];
    if (a.l < b.r && b.l < a.r && a.t < b.b && b.t < a.b) overlaps.push(`${a.name} x ${b.name}`); }
  const W = document.documentElement.clientWidth, H = document.documentElement.clientHeight;
  const outside = v.filter((b) => b.r > W || b.l < 0 || b.t < 0).map((b) => `${b.name} r=${b.r} W=${W}`);
  const ellipsis = v.filter((b) => /^(title|lede|notes)/.test(b.name) && b.sw > b.cw).map((b) => b.name);
  const ctl = v.filter((b) => b.name.startsWith("ctl"));
  const rows = {}; for (const b of ctl) { const mid = Math.round((b.t + b.b) / 2); (rows[mid] ??= []).push(b.name); }
  const st = q(".status"); const so = q(".r7b-seed-out");
  return { W, H, overlaps, outside, ellipsis, controlRows: rows, footerBelowViewport: (() => { const f = v.find((b) => b.name === "footer"); return f ? f.t >= H : null; })(),
    status: st ? getComputedStyle(st, "::after").content : null, readout: so ? getComputedStyle(so, "::before").content + getComputedStyle(so, "::after").content : null,
    ldLabel: q(".ld-label") && vis(q(".ld")) ? q(".ld-label").textContent : null, ldn: q(".ld-n") ? getComputedStyle(q(".ld-n"), "::after").content : null,
    pg: q(".pg") && vis(q(".pg")) ? getComputedStyle(q(".pg-tok"), "::after").content + getComputedStyle(q(".pg-lay"), "::after").content : null,
    tk: q(".tk-tokens") ? getComputedStyle(q(".tk-tokens"), "::after").content.slice(0, 200) : null, items };
}).catch((e) => ({ error: String(e).slice(0, 200) }));
const shot = async (tag) => { const ts = now(); await page.screenshot({ path: `${out}/shot-${tag}.png`, timeout: 30000 }).catch((e) => log("screenshot-failed", { tag, error: String(e).slice(0, 100) }));
  const g = await geometry(); log("shot", { tag, file: `shot-${tag}.png`, requestedSinceNavMs: ts - tNav0(), tookMs: now() - ts, ...g }); return g; };
// screencast: compositor frames as they are produced during the load (what the window shows while the main thread parses the sheet)
const frames = []; let castOn = true;
cdp.on("Page.screencastFrame", async (f) => { const t = now(); if (castOn) frames.push({ t, data: f.data }); cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {}); });
await cdp.send("Page.enable"); await cdp.send("Page.startScreencast", { format: "png", everyNthFrame: 1 });
const tNav = now(); globalThis.__tNav = tNav;
const nav = page.goto(url, { waitUntil: "load", timeout: 600000 }).then(() => log("load-event", { sinceNavMs: now() - tNav })).catch((e) => log("goto-error", { error: String(e) }));
let ready = false;
for (const ms of [500, 1000, 2000, 4000, 8000, 16000, 32000]) {
  const w = tNav + ms - now(); if (w > 0) await sleep(w);
  await shot(`load-${ms / 1000}s`);
  if (await page.evaluate(() => !!document.querySelector("#fonts-loaded.done")).catch(() => false)) { ready = true; break; }
}
await nav;
for (let i = 0; i < 90 && !ready; i++) { ready = await page.evaluate(() => !!document.querySelector("#fonts-loaded.done")).catch(() => false); if (!ready) await sleep(1000); }
log("ready", { sinceNavMs: now() - tNav, ready });
castOn = false; await cdp.send("Page.stopScreencast").catch(() => {});
{ // keep the first frame and then the first frame at/after 0.5, 1, 1.5, 2, 3, 4 s after navigation
  const keep = new Map(); for (const ms of [0, 500, 1000, 1500, 2000, 3000, 4000]) { const f = frames.find((x) => x.t - tNav >= ms); if (f && ![...keep.values()].includes(f)) keep.set(ms, f); }
  for (const [ms, f] of keep) { const name = `cast-${String(f.t - tNav).padStart(5, "0")}ms.png`; fs.writeFileSync(`${out}/${name}`, Buffer.from(f.data, "base64")); log("cast-frame", { file: name, sinceNavMs: f.t - tNav, wanted: ms }); }
  log("cast", { frames: frames.length, firstSinceNavMs: frames.length ? frames[0].t - tNav : null });
}
await sleep(800); await shot("ready");
const typed = process.env.R8U_TYPED ?? "";
if (typed) { await page.locator("#tk-editor").fill(process.env.R8U_EDITOR_5LINE !== "1" ? `.tk-root { --draft-prompt: "${typed}"; }` : `.tk-root {\n--draft-prompt:\n"${typed}"\n;\n}`); await sleep(1500); await shot("typed"); }
if (process.env.R8U_OPTIONS_SHOT !== "0") {  // open the native <details> Options disclosure (real click on its summary), screenshot, close it again
  const sum = page.locator(".r8u-opt>summary");
  if (await sum.count()) { await sum.click(); await sleep(600); await shot("options-open"); await sum.click(); await sleep(400); log("options-closed", { open: await page.evaluate(() => document.querySelector(".r8u-opt").open) }); }
}
const shots = (process.env.R8U_SHOTS ?? "25,70").split(",").filter(Boolean).map(Number);
if (shots.length) {
  const { root } = await cdp.send("DOM.getDocument", { depth: 1 });
  const q = async (sel) => (await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: sel })).nodeId;
  const trigger = process.env.R8U_TRIGGER ?? "keyboard";
  const tRun = now();
  if (trigger === "mouse") {  // real mouse click (Input.dispatchMouseEvent via Playwright) on the centre of the Run / continue label
    const lab = page.locator(".controls>label:nth-of-type(2)"); const bb = await lab.boundingBox(); log("run-label-box", bb);
    await page.mouse.click(bb.x + bb.width * 0.6, bb.y + bb.height / 2);
  } else {
    await cdp.send("DOM.focus", { nodeId: await q("#run") });
    const key = { key: " ", code: "Space", windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 32 };
    await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", text: " ", unmodifiedText: " ", ...key }); await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", ...key });
  }
  await sleep(300);
  log("run-triggered", { trigger, checked: (await q("#run:checked")) !== 0, latched: (await q("#run-latched.done")) !== 0 });
  setTimeout(async () => log("run-state-5s", { checked: (await q("#run:checked").catch(() => 0)) !== 0, latched: (await q("#run-latched.done").catch(() => 0)) !== 0 }), 5000);
  for (const s of shots) { const w = tRun + s * 1000 - now(); if (w > 0) await sleep(w); await shot(`run-${s}s`); }
  if (process.env.R8U_FULL === "1") {
    const cap = Number(process.env.R8U_CAPACITY ?? 36);
    for (;;) { await sleep(5000); const d = await page.evaluate(() => !!document.querySelector("[id^=r7b-complete-].done, #eos-done.done")).catch(() => false); if (d || now() - tRun > 3600000) break; }
    await sleep(2000); await shot("complete");
  }
}
await browser.close(); log("closed");
