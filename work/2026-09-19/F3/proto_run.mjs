#!/usr/bin/env node
// proto_run.mjs -- F3 prototype harness (M1 run.mjs pattern, trimmed).
// usage: node proto_run.mjs [--trials 3] [--warmup 1] [--no-trace] pages/<id>.json ...
// Per trial: fresh context (JS off) -> goto file:// -> quiescence -> W warm-up mutations ->
// read verify props -> Tracing.start -> ONE CDP class mutation on <html> -> quiescence ->
// Tracing.end -> read verify props -> compare with expected exact values.
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { createRequire } from "node:module";
import { summarizeTrace } from "/Users/shubhampatil/Documents/programming/gpt2-css/audit/2026-09-18/M1-microbench/parse_trace.mjs";

const require = createRequire(import.meta.url);
const argv = process.argv.slice(2);
const flag = (k) => argv.includes(k);
const opt = (k, d) => { const i = argv.indexOf(k); return i >= 0 && argv[i + 1] != null ? argv[i + 1] : d; };
const TRIALS = Number(opt("--trials", 3));
const WARMUP = Number(opt("--warmup", 1));
const TRACE = !flag("--no-trace");
const SETTLE_MS = Number(opt("--settle-ms", 500));
const SAVE_TRACE = opt("--save-trace", null);
const OUT = opt("--out", null);
const MAX_WAIT_MS = Number(opt("--max-wait-ms", 300000));
const EXTRA_ARGS = opt("--extra-args", "") ? opt("--extra-args").split(" ") : [];
const files = argv.filter((a) => a.endsWith(".json"));
const dependencyRoot = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const executablePath = process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const LAUNCH_ARGS = ["--allow-file-access-from-files", "--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows", ...EXTRA_ARGS];
const TRACE_CATEGORIES = ["blink", "blink.style", "blink.animations", "devtools.timeline", "disabled-by-default-devtools.timeline", "disabled-by-default-devtools.timeline.invalidationTracking", "cc", "loading"];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const metricsMap = (r) => Object.fromEntries(r.metrics.map(({ name, value }) => [name, value]));

async function waitQuiescent(cdp, { baseline = null, requireChange = false, settleMs = SETTLE_MS } = {}) {
  const t0 = performance.now();
  let last = baseline ?? metricsMap(await cdp.send("Performance.getMetrics"));
  const initial = last;
  let lastChange = t0, changed = false;
  for (;;) {
    await sleep(50);
    const now = metricsMap(await cdp.send("Performance.getMetrics"));
    if (now.RecalcStyleCount !== last.RecalcStyleCount || now.LayoutCount !== last.LayoutCount) { lastChange = performance.now(); changed = true; }
    last = now;
    if (performance.now() - lastChange >= settleMs && (!requireChange || changed)) break;
    if (performance.now() - t0 > MAX_WAIT_MS) break;
  }
  return { waitedMs: performance.now() - t0, activeMs: Math.max(0, lastChange - t0), recalcs: last.RecalcStyleCount - initial.RecalcStyleCount, layouts: last.LayoutCount - initial.LayoutCount, changed, metrics: last, timedOut: performance.now() - t0 > MAX_WAIT_MS };
}

async function findNodes(cdp, selectors) {
  // ONE DOM.getDocument per trial: every getDocument call invalidates previously issued nodeIds.
  const { root } = await cdp.send("DOM.getDocument", { depth: 1 });
  const ids = [];
  for (const selector of selectors) {
    const r = await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector }).catch(() => ({ nodeId: 0 }));
    if (r.nodeId) { ids.push(r.nodeId); continue; }
    // pierce shadow roots without serialising the whole (very deep) tree
    const { searchId, resultCount } = await cdp.send("DOM.performSearch", { query: selector, includeUserAgentShadowDOM: false });
    if (!resultCount) throw new Error(`node ${selector} not found`);
    const { nodeIds } = await cdp.send("DOM.getSearchResults", { searchId, fromIndex: 0, toIndex: 1 });
    await cdp.send("DOM.discardSearchResults", { searchId }).catch(() => {});
    ids.push(nodeIds[0]);
  }
  return { root, ids };
}

async function readProps(cdp, nodeId, names) {
  const { computedStyle } = await cdp.send("CSS.getComputedStyleForNode", { nodeId });
  const m = new Map(computedStyle.map((p) => [p.name, p.value]));
  return names.map((n) => m.get(n) ?? null);
}

function compare(vals, expected, tol = 1e-6) {
  let exact = 0, close = 0, maxAbs = 0, se = 0, nan = 0; const bad = [];
  for (let i = 0; i < expected.length; i += 1) {
    const v = Number(vals[i]);
    if (!Number.isFinite(v)) { nan += 1; if (bad.length < 20) bad.push({ i, got: vals[i], want: expected[i] }); continue; }
    const d = Math.abs(v - expected[i]);
    maxAbs = Math.max(maxAbs, d); se += d * d;
    if (v === expected[i]) exact += 1;
    else if (d < tol * Math.max(1, Math.abs(expected[i]))) close += 1;
    else if (bad.length < 20) bad.push({ i, got: vals[i], want: expected[i] });
  }
  return { exact, close, total: expected.length, bad, maxAbs, rmse: Math.sqrt(se / Math.max(1, expected.length)), nan };
}

async function runTrial(browser, meta, dir, t) {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 800, height: 600 } });
  const pw = await context.newPage();
  const cdp = await context.newCDPSession(pw);
  const rec = { id: meta.id, trial: t };
  try {
    await cdp.send("Performance.enable", { timeDomain: "timeTicks" });
    await cdp.send("DOM.enable");
    await cdp.send("CSS.enable");
    const tLoad = performance.now();
    await pw.goto(`file://${path.resolve(dir, meta.file)}`, { waitUntil: "load", timeout: 600000 });
    const ls = await waitQuiescent(cdp);
    rec.loadMs = performance.now() - tLoad;
    rec.loadRecalcs = ls.recalcs; rec.loadLayouts = ls.layouts;
    const verify = meta.verify ?? [{ selector: meta.verify_selector, props: meta.verify_props }];
    const { root, ids } = await findNodes(cdp, verify.map((v) => v.selector));
    const nodes = verify.map((v, i) => ({ nodeId: ids[i], props: v.props }));
    const htmlId = (root.children ?? []).find((c) => c.localName === "html")?.nodeId ?? root.nodeId;
    const expect = (k) => meta.expected ? meta.expected[k] : meta.widths.map((w) => w + meta.step * k);
    const readAll = async () => { const out = []; for (const n of nodes) out.push(...(await readProps(cdp, n.nodeId, n.props))); return out; };
    let k = 0;
    for (let w = 0; w < WARMUP; w += 1) {
      k = (t * (WARMUP + 1) + w) % 16;
      const base = metricsMap(await cdp.send("Performance.getMetrics"));
      await cdp.send("DOM.setAttributeValue", { nodeId: htmlId, name: "class", value: `go-${k}` });
      await waitQuiescent(cdp, { baseline: base, requireChange: true });
    }
    const before = await readAll();
    rec.beforeCheck = compare(before, expect(k), meta.tolerance);
    // traced mutation
    k = (t * (WARMUP + 1) + WARMUP) % 16;
    let events = [], tracer = null;
    if (TRACE) {
      const collect = ({ value }) => events.push(...value);
      cdp.on("Tracing.dataCollected", collect);
      const complete = new Promise((res) => cdp.once("Tracing.tracingComplete", res));
      await cdp.send("Tracing.start", { transferMode: "ReportEvents", traceConfig: { recordMode: "recordContinuously", includedCategories: TRACE_CATEGORIES } });
      tracer = { stop: async () => { await cdp.send("Tracing.end"); await complete; cdp.off("Tracing.dataCollected", collect); } };
      await sleep(150);
    }
    const bm = metricsMap(await cdp.send("Performance.getMetrics"));
    const tMut = performance.now();
    await cdp.send("DOM.setAttributeValue", { nodeId: htmlId, name: "class", value: `go-${k}` });
    const q = await waitQuiescent(cdp, { baseline: bm, requireChange: true });
    const am = metricsMap(await cdp.send("Performance.getMetrics"));
    rec.activeMs = q.activeMs; rec.recalcs = q.recalcs; rec.layouts = q.layouts; rec.timedOut = q.timedOut;
    rec.recalcStyleMs = (am.RecalcStyleDuration - bm.RecalcStyleDuration) * 1000;
    rec.layoutMs = (am.LayoutDuration - bm.LayoutDuration) * 1000;
    rec.taskMs = (am.TaskDuration - bm.TaskDuration) * 1000;
    rec.wallMs = (am.Timestamp - bm.Timestamp) * 1000;
    if (tracer) {
      await tracer.stop();
      const s = summarizeTrace(events, { windowStartUs: bm.Timestamp * 1e6, windowEndUs: am.Timestamp * 1e6 });
      rec.ult = s.updateLayoutTree.count; rec.ultMs = s.updateLayoutTree.totalUs / 1000; rec.ultElements = s.updateLayoutTree.elementCounts;
      rec.layoutN = s.layout.count; rec.layoutTraceMs = s.layout.totalUs / 1000; rec.layoutDirty = s.layout.dirtyObjects;
      rec.frames = s.frames; rec.busyMs = s.topLevelBusyUs / 1000;
      rec.prePaintMs = s.prePaint.totalUs / 1000; rec.paintMs = s.paint.totalUs / 1000;
      rec.invalidation = { styleRecalc: s.invalidation.styleRecalc, layout: s.invalidation.layoutInvalidation.byReason };
      rec.topSelf = s.topSelf.slice(0, 15).map((x) => [x.name, +(x.selfUs / 1000).toFixed(2), x.count]);
      rec.animation = s.animation.bucket;
      if (SAVE_TRACE && t === 0) fs.writeFileSync(path.join(SAVE_TRACE, `${meta.id}.trace.json.gz`), zlib.gzipSync(JSON.stringify({ traceEvents: events })));
    }
    const after = await readAll();
    rec.afterCheck = compare(after, expect(k), meta.tolerance);
    rec.k = k;
    rec.sampleAfter = after.slice(0, 4);
    const ps = require("node:child_process").execFileSync("/bin/sh", ["-c", "ps -axo rss=,command= | grep -E 'Chrome.*--type=renderer' | grep -v grep | sort -rn | head -1"], { encoding: "utf8" });
    rec.rendererRssMB = Number(ps.trim().split(/\s+/)[0]) / 1024;
  } catch (err) {
    rec.error = String(err?.stack ?? err).split("\n").slice(0, 3).join(" | ");
  } finally {
    await context.close().catch(() => {});
  }
  return rec;
}

async function main() {
  if (!files.length) { console.error("no page json given"); process.exit(2); }
  const { chromium } = require(`${dependencyRoot}/playwright`);
  const browser = await chromium.launch({ executablePath, headless: true, args: LAUNCH_ARGS });
  console.log(`[proto] chrome ${await browser.version()} trials=${TRIALS} warmup=${WARMUP} trace=${TRACE}`);
  const all = [];
  try {
    for (const f of files) {
      const meta = JSON.parse(fs.readFileSync(f, "utf8"));
      const dir = path.dirname(path.resolve(f));
      for (let t = 0; t < TRIALS; t += 1) {
        const r = await runTrial(browser, meta, dir, t);
        all.push(r);
        if (r.error) { console.log(`${meta.id} t${t}: ERROR ${r.error}`); continue; }
        console.log(`${meta.id} t${t}: load ${r.loadMs.toFixed(0)}ms | ULT ${r.ult ?? "-"}x ${r.ultMs?.toFixed(2) ?? "-"}ms elems=${JSON.stringify(r.ultElements ?? [])} | Layout ${r.layoutN ?? r.layouts}x ${(r.layoutTraceMs ?? r.layoutMs).toFixed(2)}ms | frames BMF=${r.frames?.beginMainThreadFrame ?? "-"} commit=${r.frames?.commit ?? "-"} | busy ${r.busyMs?.toFixed(1) ?? "-"} active ${r.activeMs.toFixed(0)} wall ${r.wallMs.toFixed(0)} | RSC ${r.recalcs} LC ${r.layouts} | k=${r.k} exact ${r.afterCheck.exact}/${r.afterCheck.total} (+${r.afterCheck.close} close) maxAbs ${r.afterCheck.maxAbs.toExponential(2)} rmse ${r.afterCheck.rmse.toExponential(2)} nan ${r.afterCheck.nan} | before exact ${r.beforeCheck.exact} close ${r.beforeCheck.close} maxAbs ${r.beforeCheck.maxAbs.toExponential(2)} | rss ${r.rendererRssMB?.toFixed(0)}MB${r.timedOut ? " TIMEOUT" : ""}`);
        if (r.afterCheck.bad.length) console.log(`   bad: ${JSON.stringify(r.afterCheck.bad)}`);
      }
    }
  } finally {
    await browser.close().catch(() => {});
  }
  if (OUT) fs.writeFileSync(OUT, all.map((r) => JSON.stringify(r)).join("\n") + "\n");
}
main().catch((e) => { console.error(e); process.exit(1); });
