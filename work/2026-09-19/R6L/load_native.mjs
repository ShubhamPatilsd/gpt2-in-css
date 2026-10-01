// R6L load-phase harness (2026-09-30), derived from R4M/bench_native.mjs (same node + playwright + Chrome).
// Loads the bundle ONCE, never clicks Run. Records: load event, first paint (Performance paint entries),
// Ready (= #fonts-loaded.done, polled every 250 ms via CDP DOM.querySelector — DOM-only match), pre-run idle,
// Performance.getMetrics every 250 ms (a blocked reply == a blocked main thread), resource timing of css/fonts,
// renderer RSS at 1 Hz, and optionally a light trace of the load phase only.
import fs from "node:fs"; import fsp from "node:fs/promises"; import { execSync } from "node:child_process";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require(`${process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"}/playwright`);
const executablePath = process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = process.env.B0_URL, label = process.env.B0_LABEL ?? "load", outDir = process.env.B0_OUT;
if (!url || !outDir) throw new Error("B0_URL and B0_OUT required");
const doTrace = process.env.B0_TRACE === "1", heapFlag = process.env.B0_HEAP !== "0";
const readyCapMs = Number(process.env.B0_READY_CAP_MS ?? 240000), headless = process.env.B0_HEADED !== "1";
const t0 = performance.now(); const now = () => Math.round((performance.now() - t0) * 10) / 10;
const timeline = []; const log = (event, extra = {}) => { const row = { t: now(), event, ...extra }; timeline.push(row); console.log(JSON.stringify(row)); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const args = ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--force-device-scale-factor=1", "--hide-scrollbars", "--disable-background-networking", "--disable-component-update"];
if (heapFlag) args.push("--js-flags=--heap-growing-percent=10");
const browser = await chromium.launch({ executablePath, headless, args });
const browserCdp = await browser.newBrowserCDPSession();
async function procInfo() { const { processInfo } = await browserCdp.send("SystemInfo.getProcessInfo"); return processInfo; }
log("launched", { version: browser.version(), url, headless, heapFlag, doTrace });
const context = await browser.newContext({ viewport: { width: 1000, height: 400 } });
const page = await context.newPage();
const cdp = await context.newCDPSession(page);
await cdp.send("Performance.enable", { timeDomain: "timeTicks" }); await cdp.send("DOM.enable");
let procCache = []; const rssSamples = []; let phase = "launch";
const rssTimer = setInterval(async () => { try { procCache = await procInfo(); const pids = procCache.map((p) => p.id).filter(Boolean); if (!pids.length) return;
  const out = execSync(`ps -o pid=,rss= -p ${pids.join(",")}`).toString(); const rss = new Map(); for (const line of out.split("\n")) { const m = line.match(/^\s*(\d+)\s+(\d+)/); if (m) rss.set(Number(m[1]), Math.round(Number(m[2]) / 1024)); }
  const r = procCache.filter((p) => p.type === "renderer").map((p) => rss.get(p.id) ?? 0); rssSamples.push({ t: now(), phase, rendererMaxMB: Math.max(0, ...r), renderers: r.length }); } catch {} }, 1000);
const metricSamples = []; let sampling = true;
async function metrics() { const tReq = now(); const { metrics } = await cdp.send("Performance.getMetrics"); const o = { tReq, tResp: now(), phase }; for (const m of metrics) o[m.name] = m.value; return o; }
(async () => { while (sampling) { try { metricSamples.push(await metrics()); } catch { break; } await sleep(250); } })();
const categories = ["blink", "blink.style", "blink.resource", "blink.user_timing", "devtools.timeline", "disabled-by-default-devtools.timeline", "loading", "v8.gc", "fonts", "blink.fonts"];
let tracingDone = null; const tracingP = new Promise((r) => browserCdp.on("Tracing.tracingComplete", (e) => { tracingDone = e; r(e); }));
if (doTrace) await browserCdp.send("Tracing.start", { transferMode: "ReturnAsStream", streamFormat: "json", streamCompression: "gzip", traceConfig: { recordMode: "recordContinuously", traceBufferSizeInKb: 800000, includedCategories: categories } });
// ---- load ----
phase = "load"; const tNav0 = now(); log("goto");
await page.goto(url, { waitUntil: "load", timeout: 900000 });
const tLoad = now(); log("load-event", { loadMs: tLoad - tNav0 });
const mAfterLoad = await metrics();
// Ready = #fonts-loaded.done (the witness barrier's SVG <set>); polled via a DOM-only selector match.
phase = "ready-wait"; let tReady = null; let ready = false;
{ const { root } = await cdp.send("DOM.getDocument", { depth: 0 }); const lim = tNav0 + readyCapMs;
  while (now() < lim) { const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: "#fonts-loaded.done" }); if (nodeId) { ready = true; tReady = now(); break; } await sleep(250); } }
log("ready", { ready, readyMs: ready ? tReady - tNav0 : null });
const mReady = await metrics();
// pre-run idle: RecalcStyleCount stable 2 s (max 60 s)
phase = "idle-wait"; { let last = mReady.RecalcStyleCount, since = now(); const lim = now() + 60000; while (now() - since < 2000 && now() < lim) { await sleep(250); const m = await metrics(); if (m.RecalcStyleCount !== last) { last = m.RecalcStyleCount; since = now(); } } }
const tIdle = now(); const mIdle = await metrics(); log("idle", { idleMs: tIdle - tNav0 });
// one-time reads (nothing is generating): navigation/resource/paint timing
const navInfo = await page.evaluate(() => { const res = performance.getEntriesByType("resource"); const nav = performance.getEntriesByType("navigation")[0]?.toJSON();
  const css = res.filter((r) => /runtime\.css/.test(r.name)).map((r) => ({ startTime: r.startTime, responseEnd: r.responseEnd, decodedBodySize: r.decodedBodySize, encodedBodySize: r.encodedBodySize, transferSize: r.transferSize }))[0];
  const fonts = res.filter((r) => !/runtime\.css/.test(r.name)); const fe = fonts.map((r) => r.responseEnd), fs0 = fonts.map((r) => r.startTime);
  return { nav: nav && { responseEnd: nav.responseEnd, domInteractive: nav.domInteractive, domContentLoadedEventStart: nav.domContentLoadedEventStart, domComplete: nav.domComplete, loadEventStart: nav.loadEventStart, transferSize: nav.transferSize, nextHopProtocol: nav.nextHopProtocol },
    resources: res.length, css, fonts: fonts.length, fontsFirstStart: fonts.length ? Math.min(...fs0) : null, fontsLastEnd: fonts.length ? Math.max(...fe) : null, fontBytes: fonts.reduce((s, r) => s + (r.encodedBodySize || 0), 0),
    paint: performance.getEntriesByType("paint").map((p) => ({ name: p.name, startTime: p.startTime })), fontsStatus: document.fonts.status, fontsSize: document.fonts.size, elements: document.getElementsByTagName("*").length,
    status: (document.querySelector(".status") && getComputedStyle(document.querySelector(".status"), "::after").content) || null }; });
log("nav-info", navInfo);
phase = "done"; sampling = false; clearInterval(rssTimer);
let tracePath = null, traceBytes = 0;
if (doTrace) { await browserCdp.send("Tracing.end"); const done = await tracingP; tracePath = `${outDir}/${label}-trace.json.gz`; const fh = await fsp.open(tracePath, "w");
  for (;;) { const { data, base64Encoded, eof } = await browserCdp.send("IO.read", { handle: done.stream, size: 4 * 1024 * 1024 }); const buf = Buffer.from(data, base64Encoded ? "base64" : "utf8"); if (buf.length) { await fh.write(buf); traceBytes += buf.length; } if (eof) break; }
  await fh.close(); await browserCdp.send("IO.close", { handle: done.stream }); log("trace-saved", { tracePath, traceBytes, dataLossOccurred: done.dataLossOccurred }); }
const result = { label, url, version: browser.version(), headless, heapFlag, tNav0, tLoad, tReady, tIdle, loadS: (tLoad - tNav0) / 1000, readyS: tReady ? (tReady - tNav0) / 1000 : null, idleS: (tIdle - tNav0) / 1000,
  firstPaintS: navInfo.paint.find((p) => p.name === "first-paint")?.startTime / 1000 ?? null, navInfo, mAfterLoad, mReady, mIdle, metricSamples, rssSamples, rssPeakMB: Math.max(0, ...rssSamples.map((s) => s.rendererMaxMB)), timeline, tracePath, traceBytes };
fs.writeFileSync(`${outDir}/${label}.json`, JSON.stringify(result));
log("summary", { loadS: result.loadS, firstPaintS: result.firstPaintS, readyS: result.readyS, idleS: result.idleS, rssPeakMB: result.rssPeakMB, cssResponseEndS: navInfo.css?.responseEnd / 1000, fontsLastEndS: navInfo.fontsLastEnd / 1000, RecalcStyle: mIdle.RecalcStyleCount, RecalcStyleS: mIdle.RecalcStyleDuration, Layout: mIdle.LayoutCount, LayoutS: mIdle.LayoutDuration, TaskS: mIdle.TaskDuration });
const closeP = browser.close(); await Promise.race([closeP, sleep(60000).then(() => { log("close-timeout"); process.exit(3); })]);
process.exit(0);
