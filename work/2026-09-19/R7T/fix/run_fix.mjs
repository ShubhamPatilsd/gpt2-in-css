// R7T fixture runner (NOT a timing run of the demo). One headless Chrome; per arm N trials: fresh JS-off context -> load -> quiescence ->
// warm-up mutation (html.class=go-k) -> traced mutation -> quiescence -> per-pass / per-layout / per-frame anatomy from the trace.
import fs from "node:fs"; import path from "node:path"; import { createRequire } from "node:module"; import { fileURLToPath } from "node:url";
const here = path.dirname(fileURLToPath(import.meta.url)); const require = createRequire(import.meta.url);
const argv = process.argv.slice(2); const opt = (k, d) => { const i = argv.indexOf(k); return i >= 0 && argv[i + 1] != null ? argv[i + 1] : d; };
const TRIALS = Number(opt("--trials", 3)); const SETTLE = Number(opt("--settle-ms", 700)); const OUT = opt("--out", path.join(here, "results", "fix.jsonl"));
const PAGES = opt("--pages", "pages"); const ARMS = opt("--arms", "").split(",").filter(Boolean);
const dependencyRoot = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms)); const mm = (r) => Object.fromEntries(r.metrics.map(({ name, value }) => [name, value]));
const metas = JSON.parse(fs.readFileSync(path.join(here, PAGES, "variants.json"), "utf8")); const arms = ARMS.length ? ARMS : Object.keys(metas);
const CATS = ["blink", "blink.animations", "devtools.timeline", "disabled-by-default-devtools.timeline", "cc"];
async function quiescent(cdp, base, requireChange, settle = SETTLE, max = 60000) {
  const t0 = performance.now(); let last = base ?? mm(await cdp.send("Performance.getMetrics")); const init = last; let lastChange = t0, changed = false;
  for (;;) { await sleep(40); const now = mm(await cdp.send("Performance.getMetrics"));
    if (now.RecalcStyleCount !== last.RecalcStyleCount || now.LayoutCount !== last.LayoutCount) { lastChange = performance.now(); changed = true; } last = now;
    if (performance.now() - lastChange >= settle && (!requireChange || changed)) break; if (performance.now() - t0 > max) break; }
  return { metrics: last, recalcs: last.RecalcStyleCount - init.RecalcStyleCount, layouts: last.LayoutCount - init.LayoutCount, activeMs: Math.max(0, lastChange - t0), timedOut: performance.now() - t0 > max };
}
function anatomy(events, t0us, t1us) {
  const ult = events.filter((e) => e.ph === "X" && e.name === "UpdateLayoutTree"); if (!ult.length) return { error: "no UpdateLayoutTree" };
  const pid = ult[0].pid, tid = ult[0].tid;
  const X = events.filter((e) => e.ph === "X" && e.pid === pid && e.tid === tid && e.ts >= t0us && e.ts <= t1us).sort((a, b) => a.ts - b.ts || (b.dur ?? 0) - (a.dur ?? 0));
  const self = X.map((e) => e.dur ?? 0); const stack = [];
  for (let i = 0; i < X.length; i++) { while (stack.length && X[stack.at(-1)].ts + (X[stack.at(-1)].dur ?? 0) <= X[i].ts) stack.pop(); if (stack.length) self[stack.at(-1)] -= X[i].dur ?? 0; stack.push(i); }
  const r = { passes: [], layouts: [], frames: 0, paintLCself: 0, compInputs: 0, prePaint: 0, animate: 0, ULself: 0, styleMs: 0, layoutMs: 0, busy: 0, svcAnim: 0, shapeN: 0, shapeMs: 0, fontInst: 0 };
  for (let i = 0; i < X.length; i++) { const e = X[i]; const d = (e.dur ?? 0) / 1000; const a = e.args ?? {};
    switch (e.name) {
      case "UpdateLayoutTree": r.passes.push([a.elementCount ?? a.endData?.elementCount ?? -1, +d.toFixed(1)]); r.styleMs += d; break;
      case "Layout": r.layouts.push([a.beginData?.dirtyObjects ?? -1, +d.toFixed(1)]); r.layoutMs += d; break;
      case "ProxyMain::BeginMainFrame": r.frames++; r.busy += d; break;
      case "LocalFrameView::RunPaintLifecyclePhase": r.paintLCself += self[i] / 1000; break;
      case "Blink.CompositingInputs.UpdateTime": r.compInputs += d; break;
      case "Blink.PrePaint.UpdateTime": r.prePaint += d; break;
      case "WebFrameWidgetImpl::BeginMainFrame": r.animate += d; break;
      case "WebFrameWidgetImpl::UpdateLifecycle": r.ULself += self[i] / 1000; break;
      case "AnimationTimeline::serviceAnimations": r.svcAnim++; break;
      case "InlineNode::ShapeTextIncludingFirstLine": r.shapeN++; r.shapeMs += d; break;
      case "FontCache::GetFontPlatformData": r.fontInst++; break;
    } }
  for (const k of ["paintLCself", "compInputs", "prePaint", "animate", "ULself", "styleMs", "layoutMs", "busy", "shapeMs"]) r[k] = +r[k].toFixed(1);
  return r;
}
async function trial(browser, name, meta, t) {
  const ctx = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 800, height: 600 } }); const pg = await ctx.newPage(); const cdp = await ctx.newCDPSession(pg);
  const rec = { arm: name, trial: t };
  try {
    await cdp.send("Performance.enable", { timeDomain: "timeTicks" }); await cdp.send("DOM.enable"); await cdp.send("CSS.enable");
    const tl = performance.now(); await pg.goto(`file://${path.join(here, PAGES, meta.file)}`, { waitUntil: "load", timeout: 300000 }); await quiescent(cdp, null, false, 1200); rec.loadMs = Math.round(performance.now() - tl);
    const { root } = await cdp.send("DOM.getDocument", { depth: 1 }); const htmlId = (root.children ?? []).find((c) => c.localName === "html")?.nodeId ?? root.nodeId;
    const nodes = []; for (const v of meta.verify) { const q = await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: v.selector }); nodes.push({ id: q.nodeId, props: v.props }); }
    const readAll = async () => { const o = {}; for (const n of nodes) { const { computedStyle } = await cdp.send("CSS.getComputedStyleForNode", { nodeId: n.id }); const m = new Map(computedStyle.map((p) => [p.name, p.value])); for (const p of n.props) o[p] = m.get(p) ?? null; } return o; };
    let k = (t * 2 + 1) % 16; let b = mm(await cdp.send("Performance.getMetrics")); await cdp.send("DOM.setAttributeValue", { nodeId: htmlId, name: "class", value: `go-${k}` }); const w = await quiescent(cdp, b, true); rec.warm = { recalcs: w.recalcs, layouts: w.layouts, activeMs: Math.round(w.activeMs) };
    rec.valuesWarm = await readAll();
    k = (t * 2 + 2) % 16; rec.k = k;
    const events = []; const collect = ({ value }) => events.push(...value); cdp.on("Tracing.dataCollected", collect); const done = new Promise((r) => cdp.once("Tracing.tracingComplete", r));
    await cdp.send("Tracing.start", { transferMode: "ReportEvents", traceConfig: { recordMode: "recordContinuously", includedCategories: CATS } }); await sleep(120);
    b = mm(await cdp.send("Performance.getMetrics")); await cdp.send("DOM.setAttributeValue", { nodeId: htmlId, name: "class", value: `go-${k}` }); const q = await quiescent(cdp, b, true); const a = mm(await cdp.send("Performance.getMetrics"));
    await cdp.send("Tracing.end"); await done; cdp.off("Tracing.dataCollected", collect);
    rec.recalcs = q.recalcs; rec.layouts = q.layouts; rec.activeMs = Math.round(q.activeMs); rec.timedOut = q.timedOut; rec.recalcStyleMs = +((a.RecalcStyleDuration - b.RecalcStyleDuration) * 1000).toFixed(1); rec.layoutDurMs = +((a.LayoutDuration - b.LayoutDuration) * 1000).toFixed(1); rec.taskMs = +((a.TaskDuration - b.TaskDuration) * 1000).toFixed(1);
    rec.anat = anatomy(events, b.Timestamp * 1e6, a.Timestamp * 1e6); rec.values = await readAll();
  } catch (e) { rec.error = String(e?.stack ?? e).split("\n").slice(0, 2).join(" | "); } finally { await ctx.close().catch(() => {}); }
  return rec;
}
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true, args: ["--allow-file-access-from-files", "--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows"] });
console.log(`[fix] chrome ${await browser.version()} trials=${TRIALS} arms=${arms.join(",")}`);
fs.mkdirSync(path.dirname(OUT), { recursive: true });
try { for (const name of arms) for (let t = 0; t < TRIALS; t++) { const r = await trial(browser, name, metas[name], t); fs.appendFileSync(OUT, JSON.stringify(r) + "\n");
  if (r.error) { console.log(`${name} t${t}: ERROR ${r.error}`); continue; }
  const A = r.anat; console.log(`${name} t${t}: load ${r.loadMs} | passes ${JSON.stringify(A.passes)} | layouts ${JSON.stringify(A.layouts)} | frames ${A.frames} busy ${A.busy} | style ${A.styleMs} layout ${A.layoutMs} paintLCself ${A.paintLCself} CI ${A.compInputs} prepaint ${A.prePaint} animate ${A.animate} UL ${A.ULself} | shape ${A.shapeN}x ${A.shapeMs}ms inst ${A.fontInst} | RSC ${r.recalcs} LC ${r.layouts} active ${r.activeMs} | ${JSON.stringify(r.values)}`); } }
finally { await browser.close().catch(() => {}); }
