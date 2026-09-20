// R2E pause-and-hold fixture runner (NOT a timing run of the demo). One fresh headless Chrome; per page N trials; per trial a fixed
// sequence of states set via CDP DOM.setAttributeValue on <html class> and <div#track style="--in:v"> (no JS in the page).
// After every step: wait until RecalcStyleCount/LayoutCount are stable for --settle-ms, read the consumer's --o-* computed values
// (hold/value check), then an idle window of --idle-ms in which the .tick animation forces a frame per vsync: per-frame main-thread
// cost = TaskDuration delta / RecalcStyleCount delta. Steps marked traced record a light trace of the mutation (event counts by name).
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
const PAGES = opt("--pages", "1024,0").split(",").map(Number);
const TRIALS = Number(opt("--trials", 2));
const SETTLE = Number(opt("--settle-ms", 400));
const IDLE = Number(opt("--idle-ms", 2000));
const OUT = path.resolve(here, opt("--out", "results"));
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

// steps: [name, htmlClass, inValue, expectFn(i, prevExpected) -> expected value or null(=hold), traced]
// expected --o-i while live = i + in; while held = previous expected; after an un-paused detach = base (-1) or unknown.
const STEPS = [
  ["live0", "", 0, (i) => i, false],
  ["live7", "", 7, (i) => i + 7, true],                 // ordinary input change while live (baseline for the cycle cost)
  ["paused", "paused", 7, (i) => i + 7, false],         // paused-attached: hold current value
  ["paused-in13", "paused", 13, (i) => i + 7, false],   // input changes while paused: must NOT leak (hold)
  ["pd-none", "pd-none", 13, (i) => i + 7, false],      // (1a) hold across view-timeline-name removal?
  ["resume21", "", 21, (i) => i + 21, true],            // (3) cycle cost: re-attach timelines + un-pause, new value
  ["paused2", "paused", 21, (i) => i + 21, false],
  ["pd-display", "pd-display", 21, (i) => i + 21, false], // (1b) hold across display:none of the subjects?
  ["resume33", "", 33, (i) => i + 33, true],
  ["paused3", "paused", 33, (i) => i + 33, false],
  ["pd-cv", "pd-cv", 33, (i) => i + 33, false],         // (1c) hold across content-visibility:hidden?
  ["resume45", "", 45, (i) => i + 45, true],
  ["d-none", "d-none", 45, null, false],                // control: detach WITHOUT pause -> value?
  ["resume57", "", 57, (i) => i + 57, true],
  ["d-display", "d-display", 57, null, false],          // control: display:none WITHOUT pause -> value?
  ["resume69", "", 69, (i) => i + 69, true],
];

async function waitQuiescent(cdp, baseline) {
  let last = baseline, lastChange = performance.now(); const t0 = lastChange;
  for (;;) {
    await sleep(50);
    const now = mm(await cdp.send("Performance.getMetrics"));
    if (now.RecalcStyleCount !== last.RecalcStyleCount || now.LayoutCount !== last.LayoutCount) lastChange = performance.now();
    last = now;
    if (performance.now() - lastChange >= SETTLE || performance.now() - t0 > 30000) return { m: last, activeMs: lastChange - t0, waitedMs: performance.now() - t0 };
  }
}
function summarizeTrace(events, t0us, t1us) {
  const names = {}; let ult = 0, ultElems = 0, layout = 0, tasks = 0; const sched = {};
  for (const e of events) {
    if (e.ph !== "X" && e.ph !== "I" && e.ph !== "i") continue;
    if (e.ts < t0us || e.ts > t1us) continue;
    names[e.name] = (names[e.name] ?? 0) + 1;
    if (e.name === "UpdateLayoutTree") { ult += (e.dur ?? 0); ultElems += e.args?.elementCount ?? 0; }
    if (e.name === "Layout") layout += (e.dur ?? 0);
    if (e.name === "ThreadControllerImpl::RunTask" || e.name === "RunTask") tasks += (e.dur ?? 0);
    if (/ScheduleAnimation/.test(e.name)) { const f = e.args?.data?.function_name ?? e.args?.function_name ?? "?"; sched[f] = (sched[f] ?? 0) + 1; }
  }
  const top = Object.entries(names).sort((a, b) => b[1] - a[1]).slice(0, 25);
  return { ultMs: ult / 1000, ultElems, layoutMs: layout / 1000, taskMs: tasks / 1000, scheduleAnimation: sched, top };
}
async function readValues(cdp, docId, n) {
  const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: docId, selector: "#consumer" });
  const { computedStyle } = await cdp.send("CSS.getComputedStyleForNode", { nodeId });
  const vals = new Array(n).fill(null);
  for (const p of computedStyle) { const m = /^--o-(\d+)$/.exec(p.name); if (m) vals[Number(m[1])] = Number(p.value); }
  return vals;
}

async function trial(browser, n, t) {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 800, height: 600 } });
  const pw = await context.newPage(); const cdp = await context.newCDPSession(pw);
  await cdp.send("Performance.enable", { timeDomain: "timeTicks" }); await cdp.send("DOM.enable"); await cdp.send("CSS.enable");
  const url = `file://${path.join(here, "pages", `hold-${n}.html`)}`;
  const tl = performance.now();
  await pw.goto(url, { waitUntil: "load", timeout: 600000 });
  const q0 = await waitQuiescent(cdp, mm(await cdp.send("Performance.getMetrics")));
  const { root } = await cdp.send("DOM.getDocument", { depth: 1 });
  const htmlId = (root.children.find((c) => c.localName === "html") ?? root.children[0]).nodeId;
  const trackId = (await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: "#track" })).nodeId;
  const rec = { n, trial: t, loadMs: performance.now() - tl, loadRecalcs: q0.m.RecalcStyleCount, steps: [] };
  let prevExpected = null;
  for (const [name, cls, inv, expectFn, traced] of STEPS) {
    const tracing = traced ? await startTrace(cdp) : null;
    if (traced) await sleep(150);
    const before = mm(await cdp.send("Performance.getMetrics"));
    const tm = performance.now();
    await cdp.send("DOM.setAttributeValue", { nodeId: htmlId, name: "class", value: cls });
    await cdp.send("DOM.setAttributeValue", { nodeId: trackId, name: "style", value: `--in:${inv}` });
    const q = await waitQuiescent(cdp, before);
    const after = q.m;
    const step = { name, cls, in: inv, mutateMs: (after.TaskDuration - before.TaskDuration) * 1000, recalcs: after.RecalcStyleCount - before.RecalcStyleCount,
      layouts: after.LayoutCount - before.LayoutCount, recalcMs: (after.RecalcStyleDuration - before.RecalcStyleDuration) * 1000, activeMs: q.activeMs };
    if (traced) { const ev = await tracing.stop(); step.trace = summarizeTrace(ev, before.Timestamp * 1e6, after.Timestamp * 1e6); step.traceEvents = ev.length;
      if (t === 0) fs.writeFileSync(path.join(OUT, `trace-${n}-${name}.json.gz`), zlib.gzipSync(JSON.stringify({ traceEvents: ev }))); }
    if (n > 0) {
      const vals = await readValues(cdp, root.nodeId, n);
      const expected = expectFn ? Array.from({ length: n }, (_, i) => expectFn(i)) : null;
      const ok = expected ? vals.filter((v, i) => v === expected[i]).length : null;
      const heldPrev = prevExpected ? vals.filter((v, i) => v === prevExpected[i]).length : null;
      step.values = { sample: [vals[0], vals[n >> 1], vals[n - 1]], expectedSample: expected ? [expected[0], expected[n >> 1], expected[n - 1]] : null, matchExpected: ok, matchPrevious: heldPrev, distinct: [...new Set(vals)].length };
      if (expected) prevExpected = expected;
    }
    // idle window: per-frame cost with the tick animation forcing frames
    const i0 = mm(await cdp.send("Performance.getMetrics")); const w0 = performance.now(); await sleep(IDLE); const i1 = mm(await cdp.send("Performance.getMetrics"));
    const frames = i1.RecalcStyleCount - i0.RecalcStyleCount; const task = (i1.TaskDuration - i0.TaskDuration) * 1000;
    step.idle = { wallMs: performance.now() - w0, frames, taskMs: task, msPerFrame: frames ? task / frames : null, recalcMsPerFrame: frames ? (i1.RecalcStyleDuration - i0.RecalcStyleDuration) * 1000 / frames : null, layouts: i1.LayoutCount - i0.LayoutCount };
    rec.steps.push(step);
    log({ n, t, step: name, mutateMs: +step.mutateMs.toFixed(1), recalcs: step.recalcs, layouts: step.layouts, values: step.values?.sample, match: step.values?.matchExpected, prev: step.values?.matchPrevious, idleMsPerFrame: step.idle.msPerFrame && +step.idle.msPerFrame.toFixed(3), frames, sched: step.trace?.scheduleAnimation });
  }
  await context.close();
  return rec;
}
async function startTrace(cdp) {
  const events = []; const collect = ({ value }) => events.push(...value);
  cdp.on("Tracing.dataCollected", collect); const done = new Promise((r) => cdp.once("Tracing.tracingComplete", r));
  await cdp.send("Tracing.start", { transferMode: "ReportEvents", traceConfig: { recordMode: "recordContinuously", includedCategories: ["blink", "blink.animations", "devtools.timeline", "disabled-by-default-devtools.timeline"] } });
  return { async stop() { await cdp.send("Tracing.end"); await done; cdp.off("Tracing.dataCollected", collect); return events; } };
}
const browser = await chromium.launch({ executablePath, headless: true, args: ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows"] });
log({ launched: await browser.version(), pages: PAGES, trials: TRIALS, batt: batt.split("\n")[0] });
const out = fs.createWriteStream(path.join(OUT, "hold.jsonl"), { flags: "a" });
for (const n of PAGES) for (let t = 0; t < TRIALS; t++) { const r = await trial(browser, n, t); out.write(JSON.stringify(r) + "\n"); }
out.end(); await browser.close(); log({ done: true });
