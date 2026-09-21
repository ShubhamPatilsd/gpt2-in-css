// R4T fixture runner (NOT a timing run of the demo). One headless Chrome; per variant page N trials (fresh context each, JS disabled):
// load -> settle -> read sample --o-* values -> idle metrics window (Performance.getMetrics deltas: TaskDuration / RecalcStyle / Layout) ->
// light trace window parsed in-process into per-frame anatomy (ProxyMain::BeginMainFrame frames on the renderer main thread: dur,
// animate step = WebFrameWidgetImpl::BeginMainFrame, serviceScriptedAnimations incl/self, AnimationTimeline::serviceAnimations count/ms,
// WebFrameWidgetImpl::UpdateLifecycle self, UpdateLayoutTree n/ms, Layout n/ms, RunPaintLifecyclePhase incl/self, PrePaint, CompositingInputs).
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const argv = process.argv.slice(2);
const opt = (k, d) => { const i = argv.indexOf(k); return i >= 0 && argv[i + 1] != null ? argv[i + 1] : d; };
const VARIANTS = opt("--variants", "").split(",").filter(Boolean);
const TRIALS = Number(opt("--trials", 3));
const SETTLE = Number(opt("--settle-ms", 1500));
const IDLE = Number(opt("--idle-ms", 2000));
const TRACE = Number(opt("--trace-ms", 1500));
const SAVE = opt("--save-traces", "").split(",").filter(Boolean);
const OUT = path.resolve(here, opt("--out", "results"));
const TAG = opt("--tag", "run");
fs.mkdirSync(OUT, { recursive: true });
const dependencyRoot = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const executablePath = process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sh = (c, a) => { try { return execFileSync(c, a, { encoding: "utf8" }).trim(); } catch { return ""; } };
const batt = sh("/usr/bin/pmset", ["-g", "batt"]);
if (!/AC Power/.test(batt) && !argv.includes("--allow-battery")) { console.error("not on AC power:", batt.split("\n")[0]); process.exit(2); }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const mm = (r) => Object.fromEntries(r.metrics.map(({ name, value }) => [name, value]));
const log = (...a) => console.log(JSON.stringify({ t: Math.round(performance.now()), ...Object.assign({}, ...a) }));
const metas = JSON.parse(fs.readFileSync(path.join(here, "pages", "variants.json"), "utf8"));
const variants = VARIANTS.length ? VARIANTS : Object.keys(metas);
const median = (xs) => { const s = [...xs].sort((a, b) => a - b); return s.length ? (s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : null; };

async function startTrace(cdp) {
  const events = []; const collect = ({ value }) => { for (const e of value) events.push(e); };
  cdp.on("Tracing.dataCollected", collect); const done = new Promise((r) => cdp.once("Tracing.tracingComplete", r));
  await cdp.send("Tracing.start", { transferMode: "ReportEvents", traceConfig: { recordMode: "recordContinuously", includedCategories: ["blink", "blink.animations", "devtools.timeline", "disabled-by-default-devtools.timeline"] } });
  return { async stop() { await cdp.send("Tracing.end"); await done; cdp.off("Tracing.dataCollected", collect); return events; } };
}

// per-frame anatomy from the in-memory event list
function anatomy(events, t0us, t1us) {
  const bmfAll = events.filter((e) => e.ph === "X" && e.name === "WebFrameWidgetImpl::BeginMainFrame");
  if (!bmfAll.length) return { frames: 0 };
  const pid = bmfAll[0].pid, tid = bmfAll[0].tid;
  const X = events.filter((e) => e.ph === "X" && e.pid === pid && e.tid === tid && e.ts >= t0us - 200000 && e.ts <= t1us + 200000);
  X.sort((a, b) => a.ts - b.ts || (b.dur ?? 0) - (a.dur ?? 0));
  const svcITs = events.filter((e) => (e.ph === "I" || e.ph === "i") && e.name === "AnimationTimeline::serviceAnimations" && e.pid === pid && e.tid === tid).map((e) => e.ts).sort((a, b) => a - b);
  const lowerBound = (arr, v) => { let lo = 0, hi = arr.length; while (lo < hi) { const m = (lo + hi) >> 1; if (arr[m] < v) lo = m + 1; else hi = m; } return lo; };
  const n = X.length; const self = new Float64Array(n); const parent = new Int32Array(n).fill(-1); const depth = new Int32Array(n);
  const stack = [];
  for (let i = 0; i < n; i++) {
    const e = X[i]; const d = e.dur ?? 0; self[i] = d;
    while (stack.length && X[stack[stack.length - 1]].ts + (X[stack[stack.length - 1]].dur ?? 0) <= e.ts) stack.pop();
    depth[i] = stack.length;
    if (stack.length) { const p = stack[stack.length - 1]; self[p] -= d; parent[i] = p; }
    stack.push(i);
  }
  // a frame = top-level RunTask that contains a WebFrameWidgetImpl::BeginMainFrame (cc's ProxyMain::BeginMainFrame is not in the light categories)
  const isFrame = new Uint8Array(n);
  for (let i = 0; i < n; i++) if (X[i].name === "WebFrameWidgetImpl::BeginMainFrame") { let p = i; while (parent[p] >= 0) p = parent[p]; isFrame[p] = 1; }
  // window: full frames whose start and end lie inside [t0, t1]
  const frames = [];
  for (let i = 0; i < n; i++) {
    const e = X[i]; if (!isFrame[i]) continue;
    const a = e.ts, b = e.ts + (e.dur ?? 0); if (a < t0us || b > t1us) continue;
    const f = { dur: (e.dur ?? 0) / 1000, animate: 0, ssaIncl: 0, ssaSelf: 0, svcN: 0, svcMs: 0, ulSelf: 0, ulIncl: 0, ultN: 0, ultMs: 0, ultSelf: 0, usSelf: 0, layoutN: 0, layoutMs: 0, paintLC: 0, paintLCSelf: 0, prePaint: 0, compInputs: 0, usalN: 0, usalMs: 0, elems: [], sched: 0 };
    for (let j = i + 1; j < n && X[j].ts < b; j++) {
      const nm = X[j].name, d = (X[j].dur ?? 0) / 1000, s = self[j] / 1000;
      switch (nm) {
        case "WebFrameWidgetImpl::BeginMainFrame": f.animate += d; break;
        case "PageAnimator::serviceScriptedAnimations": f.ssaIncl += d; f.ssaSelf += s; break;
        case "AnimationTimeline::serviceAnimations": f.svcN++; f.svcMs += d; break;
        case "WebFrameWidgetImpl::UpdateLifecycle": f.ulSelf += s; f.ulIncl += d; break;
        case "UpdateLayoutTree": f.ultN++; f.ultMs += d; f.ultSelf += s; { const a_ = X[j].args || {}; const ec = a_.elementCount ?? a_.endData?.elementCount; if (ec != null) f.elems.push(ec); } break;
        case "Document::updateStyle": f.usSelf += s; break;
        case "Layout": f.layoutN++; f.layoutMs += d; break;
        case "LocalFrameView::RunPaintLifecyclePhase": f.paintLC += d; f.paintLCSelf += s; break;
        case "PrePaint": f.prePaint += d; break;
        case "Blink.CompositingInputs.UpdateTime": f.compInputs += d; break;
        case "LocalFrameView::UpdateStyleAndLayout": f.usalN++; f.usalMs += d; break;
        case "LocalFrameView::ScheduleAnimation": f.sched++; break;
      }
    }
    f.svcI = lowerBound(svcITs, b) - lowerBound(svcITs, a); f.svcN += f.svcI;
    frames.push(f);
  }
  // main-thread busy in the window (top-level events), and busy outside frames
  let busy = 0, frameBusy = 0;
  for (let i = 0; i < n; i++) if (depth[i] === 0 && X[i].ts >= t0us && X[i].ts + (X[i].dur ?? 0) <= t1us) busy += (X[i].dur ?? 0) / 1000;
  for (const f of frames) frameBusy += f.dur;
  // instant serviceAnimations (some Chrome versions emit them as I events)
  let svcI = 0; for (const e of events) if ((e.ph === "I" || e.ph === "i") && e.name === "AnimationTimeline::serviceAnimations" && e.ts >= t0us && e.ts <= t1us) svcI++;
  const keys = ["dur", "svcI", "animate", "ssaIncl", "ssaSelf", "svcN", "svcMs", "ulSelf", "ulIncl", "ultN", "ultMs", "ultSelf", "usSelf", "layoutN", "layoutMs", "paintLC", "paintLCSelf", "prePaint", "compInputs", "usalN", "usalMs", "sched"];
  const med = {}, mean = {};
  for (const k of keys) { const xs = frames.map((f) => f[k]); med[k] = median(xs); mean[k] = xs.reduce((a, b) => a + b, 0) / (xs.length || 1); }
  const elemHist = {}; for (const f of frames) { const k = f.elems.join(" "); elemHist[k] = (elemHist[k] ?? 0) + 1; }
  // top self-time names inside frames (untraced attribution)
  const selfBy = {};
  for (let i = 0; i < n; i++) if (X[i].ts >= t0us && X[i].ts <= t1us) selfBy[X[i].name] = (selfBy[X[i].name] ?? 0) + self[i] / 1000;
  const topSelf = Object.entries(selfBy).sort((a, b) => b[1] - a[1]).slice(0, 14).map(([k, v]) => [k, +(v / (frames.length || 1)).toFixed(3)]);
  return { frames: frames.length, windowMs: (t1us - t0us) / 1000, busyMs: busy, frameBusyMs: frameBusy, busyPerFrame: frames.length ? busy / frames.length : null, med, mean, elemHist, svcInstant: svcI, topSelfPerFrame: topSelf, events: events.length };
}

async function readValues(cdp, docId, meta) {
  const n = meta.n, cons = meta.consumers; if (!n) return null;
  const want = [0, n >> 1, n - 1]; const out = {};
  for (const i of want) {
    const c = i % cons;
    const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: docId, selector: `#c${c}` });
    const { computedStyle } = await cdp.send("CSS.getComputedStyleForNode", { nodeId });
    const p = computedStyle.find((x) => x.name === `--o-${i}`); out[i] = p ? Number(p.value) : null;
  }
  return { sample: want.map((i) => out[i]), expected: want.map((i) => i), ok: want.filter((i) => Math.abs(out[i] - i) < 0.01).length };
}

async function trial(browser, name, t) {
  const meta = metas[name];
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 800, height: 600 } });
  const pw = await context.newPage(); const cdp = await context.newCDPSession(pw);
  await cdp.send("Performance.enable", { timeDomain: "timeTicks" }); await cdp.send("DOM.enable"); await cdp.send("CSS.enable");
  const url = `file://${path.join(here, "pages", `${name}.html`)}`;
  const tl = performance.now();
  await pw.goto(url, { waitUntil: "load", timeout: 300000 });
  const loadMs = performance.now() - tl;
  await sleep(SETTLE);
  const { root } = await cdp.send("DOM.getDocument", { depth: 1 });
  const values = await readValues(cdp, root.nodeId, meta);
  // idle metrics window
  const i0 = mm(await cdp.send("Performance.getMetrics")); const w0 = performance.now(); await sleep(IDLE); const i1 = mm(await cdp.send("Performance.getMetrics"));
  const idle = { wallMs: performance.now() - w0, recalcs: i1.RecalcStyleCount - i0.RecalcStyleCount, layouts: i1.LayoutCount - i0.LayoutCount, taskMs: (i1.TaskDuration - i0.TaskDuration) * 1000, recalcMs: (i1.RecalcStyleDuration - i0.RecalcStyleDuration) * 1000, layoutMs: (i1.LayoutDuration - i0.LayoutDuration) * 1000, nodes: i1.Nodes, jsHeap: i1.JSHeapUsedSize };
  // trace window
  const tr = await startTrace(cdp); await sleep(200);
  const m0 = mm(await cdp.send("Performance.getMetrics")); await sleep(TRACE); const m1 = mm(await cdp.send("Performance.getMetrics"));
  await sleep(100); const ev = await tr.stop();
  const an = anatomy(ev, m0.Timestamp * 1e6, m1.Timestamp * 1e6);
  an.metricTaskMs = (m1.TaskDuration - m0.TaskDuration) * 1000; an.metricRecalcs = m1.RecalcStyleCount - m0.RecalcStyleCount; an.metricLayouts = m1.LayoutCount - m0.LayoutCount;
  if (t === 0 && SAVE.includes(name)) fs.writeFileSync(path.join(OUT, `trace-${name}.json.gz`), zlib.gzipSync(JSON.stringify({ traceEvents: ev })));
  const rss = Number(sh("/bin/sh", ["-c", `ps -o rss= -p $(pgrep -f '^/Applications/.*Google Chrome .*--type=renderer' | head -1) 2>/dev/null`])) || null;
  await context.close();
  const rec = { tag: TAG, name, trial: t, meta, loadMs, values, idle, anatomy: an, rssKb: rss, when: new Date().toISOString() };
  log({ name, t, loadMs: +loadMs.toFixed(0), values: values?.sample, ok: values?.ok, idleMsPerFrame: idle.recalcs ? +(idle.taskMs / (an.frames ? an.frames / (TRACE / 1000) * (IDLE / 1000) : idle.recalcs)).toFixed(3) : null,
    frames: an.frames, busyPerFrame: an.busyPerFrame && +an.busyPerFrame.toFixed(3), frameDur: an.med?.dur && +an.med.dur.toFixed(3), animate: an.med?.animate && +an.med.animate.toFixed(3), ssaSelf: an.med?.ssaSelf && +an.med.ssaSelf.toFixed(3), svcN: an.med?.svcN, svcMs: an.med?.svcMs && +an.med.svcMs.toFixed(3), ulSelf: an.med?.ulSelf && +an.med.ulSelf.toFixed(3), ult: an.med?.ultMs && +an.med.ultMs.toFixed(3), layout: an.med?.layoutMs && +an.med.layoutMs.toFixed(3), paintLC: an.med?.paintLC && +an.med.paintLC.toFixed(3), elems: an.elemHist, events: an.events });
  return rec;
}
const browser = await chromium.launch({ executablePath, headless: true, args: ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows"] });
log({ launched: await browser.version(), variants, trials: TRIALS, batt: batt.split("\n")[0] });
const out = fs.createWriteStream(path.join(OUT, `${TAG}.jsonl`), { flags: "a" });
for (let t = 0; t < TRIALS; t++) for (const name of variants) { try { const r = await trial(browser, name, t); out.write(JSON.stringify(r) + "\n"); } catch (e) { log({ name, t, error: String(e).slice(0, 300) }); } }
out.end(); await browser.close(); log({ done: true });
