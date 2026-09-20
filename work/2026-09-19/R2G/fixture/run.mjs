#!/usr/bin/env node
// run.mjs -- M1 micro-benchmark harness.
//
// One fresh headless Chromium per page variant, N trials each.  Per trial:
// fresh context (JS disabled) -> navigate file:// page -> wait for load and
// lifecycle quiescence -> W untraced warm-up mutations -> CDP Tracing.start ->
// ONE mutation via CDP DOM.setAttributeValue (no JS in the page) -> wait until
// RecalcStyleCount/LayoutCount stop changing for --settle-ms -> Tracing.end ->
// parse trace + Performance.getMetrics deltas -> one JSON line.
//
// Usage (see README.md):
//   caffeinate -dims node run.mjs [--trials 5] [--warmup 1] [--filter 'mb3-'] \
//       [--trigger class|inline] [--shuffle] [--settle-ms 500] [--force] [--allow-battery]
//
// Never launches Chromium if another headless Chrome/Chromium is running
// (concurrent runs contaminate timings) unless --force is given.

import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";
import zlib from "node:zlib";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { summarizeTrace, median } from "./parse_trace.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

// ---------------------------------------------------------------- args ----
const argv = process.argv.slice(2);
const flag = (k) => argv.includes(k);
const opt = (k, d) => { const i = argv.indexOf(k); return i >= 0 && argv[i + 1] != null ? argv[i + 1] : d; };

const TRIALS = Number(opt("--trials", 5));
const WARMUP = Number(opt("--warmup", 1));
const FILTER = opt("--filter", null) ? new RegExp(opt("--filter")) : null;
const TRIGGER = opt("--trigger", "class");              // class | inline
const SETTLE_MS = Number(opt("--settle-ms", 500));
const POLL_MS = Number(opt("--poll-ms", 50));
const MAX_WAIT_MS = Number(opt("--max-wait-ms", 180_000));
const FORCE_AFTER_MS = Number(opt("--force-after-ms", 3000)); // if no recalc observed, force a lifecycle
const LOAD_TIMEOUT_MS = Number(opt("--load-timeout-ms", 600_000));
const OUT_DIR = path.resolve(here, opt("--out", "results"));
const TRACE_DIR = path.resolve(here, opt("--traces", "traces"));
const SAVE_ALL_TRACES = flag("--save-all-traces");
const VERIFY = !flag("--no-verify");
const SHUFFLE = flag("--shuffle");
const DRY_RUN = flag("--dry-run");
const VERBOSE = flag("--verbose");
const vlog = (...a) => { if (VERBOSE) console.log(`      [${(performance.now() / 1000).toFixed(2)}s]`, ...a); };

const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
// Repo convention is `chromium.launch({ executablePath, headless: true })` with no extra args
// (tools/profile_hvar_two_block_toggle_trace.mjs).  We add only anti-throttling flags.
const LAUNCH_ARGS = [
  "--disable-background-timer-throttling",
  "--disable-renderer-backgrounding",
  "--disable-backgrounding-occluded-windows",
  ...(opt("--extra-args", "") ? opt("--extra-args").split(" ") : []),
];
const TRACE_CATEGORIES = [
  "blink", "blink.style", "blink.animations", "devtools.timeline",
  "disabled-by-default-devtools.timeline",
  "disabled-by-default-devtools.timeline.invalidationTracking",
  "cc", "loading",
  ...(opt("--extra-categories", "") ? opt("--extra-categories").split(",") : []),
];
const METRIC_NAMES = [
  "RecalcStyleCount", "RecalcStyleDuration", "LayoutCount", "LayoutDuration",
  "TaskDuration", "TaskOtherDuration", "ThreadTime", "ProcessTime",
  "JSHeapUsedSize", "JSHeapTotalSize", "Nodes", "LayoutObjects", "DevToolsCommandDuration",
];

// ------------------------------------------------------------ preflight ----
function sh(cmd, args) {
  try { return execFileSync(cmd, args, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim(); }
  catch { return ""; }
}

function preflight() {
  const batt = sh("/usr/bin/pmset", ["-g", "batt"]);
  const onAC = /AC Power/.test(batt);
  const therm = sh("/usr/bin/pmset", ["-g", "therm"]);
  const caffeinated = sh("/usr/bin/pgrep", ["-x", "caffeinate"]) !== "";
  const otherChrome = sh("/bin/sh", ["-c",
    "ps -axo pid=,command= | grep -E 'Chrom(e|ium).*(--headless|--remote-debugging|--type=renderer)' | grep -v grep | head -20"]);
  const env = {
    startedAt: new Date().toISOString(),
    node: process.version,
    chrome: sh("/usr/bin/defaults", ["read", `${executablePath.replace(/\/Contents\/MacOS\/.*$/, "")}/Contents/Info.plist`, "CFBundleShortVersionString"]),
    executablePath,
    launchArgs: LAUNCH_ARGS,
    traceCategories: TRACE_CATEGORIES,
    cpu: sh("/usr/sbin/sysctl", ["-n", "machdep.cpu.brand_string"]),
    memoryBytes: Number(sh("/usr/sbin/sysctl", ["-n", "hw.memsize"])),
    power: { onAC, caffeinated, pmsetBatt: batt.split("\n").slice(0, 2).join(" | "), therm: therm.replace(/\s+/g, " ") },
    gitHead: sh("/usr/bin/git", ["-C", here, "rev-parse", "HEAD"]),
    otherChromeProcesses: otherChrome ? otherChrome.split("\n") : [],
    options: { TRIALS, WARMUP, TRIGGER, SETTLE_MS, POLL_MS, MAX_WAIT_MS, FORCE_AFTER_MS, filter: FILTER?.source ?? null, SHUFFLE, VERIFY },
  };
  const problems = [];
  if (!onAC && !flag("--allow-battery")) problems.push("not on AC power (S7: battery/sleep confounds). Plug in or pass --allow-battery");
  if (!caffeinated) console.warn("[preflight] WARNING: caffeinate not running; run as `caffeinate -dims node run.mjs ...` (S7 found display-off/sleep confounds)");
  if (otherChrome && !flag("--force")) problems.push(`other Chromium processes are running (concurrent runs contaminate timings):\n${otherChrome}\n  pass --force to ignore`);
  if (!fs.existsSync(executablePath)) problems.push(`Chrome not found at ${executablePath} (set CHROME_PATH)`);
  if (!fs.existsSync(`${dependencyRoot}/playwright`)) problems.push(`playwright not found under ${dependencyRoot} (set CODEX_NODE_MODULES)`);
  if (problems.length) {
    console.error("[preflight] refusing to run:\n - " + problems.join("\n - "));
    process.exit(1);
  }
  return env;
}

// -------------------------------------------------------------- helpers ----
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function metricsMap(result) {
  return Object.fromEntries(result.metrics.map(({ name, value }) => [name, value]));
}

function metricDelta(before, after) {
  const out = {};
  for (const name of METRIC_NAMES) {
    const d = (after[name] ?? 0) - (before[name] ?? 0);
    out[name.endsWith("Duration") || name === "ThreadTime" || name === "ProcessTime" ? `${name}Ms` : name] =
      name.endsWith("Duration") || name === "ThreadTime" || name === "ProcessTime" ? d * 1000 : d;
  }
  out.wallMs = ((after.Timestamp ?? 0) - (before.Timestamp ?? 0)) * 1000;
  return out;
}

/** Renderer RSS via a browser-level CDP session (SystemInfo.getProcessInfo -> pids) + ps. */
async function rendererRss(browser) {
  try {
    const bcdp = browser.__m1Session ?? (browser.__m1Session = await browser.newBrowserCDPSession());
    const { processInfo } = await bcdp.send("SystemInfo.getProcessInfo");
    const renderers = processInfo.filter((p) => p.type === "renderer");
    if (!renderers.length) return { rendererCount: 0 };
    const ps = sh("/bin/ps", ["-o", "pid=,rss=", "-p", renderers.map((p) => p.id).join(",")]);
    const rss = ps.split("\n").filter(Boolean).map((l) => Number(l.trim().split(/\s+/)[1]) / 1024);
    return {
      rendererCount: renderers.length,
      maxRendererRssMB: rss.length ? Math.max(...rss) : null,
      totalRendererRssMB: rss.reduce((a, b) => a + b, 0),
      rendererCpuTimeS: renderers.map((p) => p.cpuTime),
    };
  } catch (err) {
    return { error: String(err.message ?? err) };
  }
}

/** Poll Performance.getMetrics until RecalcStyleCount and LayoutCount are unchanged for settleMs. */
async function waitQuiescent(cdp, { settleMs = SETTLE_MS, pollMs = POLL_MS, maxMs = MAX_WAIT_MS, requireChange = false, forceAfterMs = FORCE_AFTER_MS, forceFn = null, baseline = null } = {}) {
  // `baseline` MUST be sampled before the mutation: the lifecycle update for a CDP attribute
  // change completes before the next DevTools command is serviced, so a sample taken after
  // the mutation already includes the recalc (bug found 2026-09-18 21:58Z, first run aborted).
  const t0 = performance.now();
  let last = baseline ?? metricsMap(await cdp.send("Performance.getMetrics"));
  const initial = last;
  let lastChange = t0;
  let changed = false;
  let forced = false;
  let polls = 0;
  for (;;) {
    await sleep(pollMs);
    polls += 1;
    const now = metricsMap(await cdp.send("Performance.getMetrics"));
    if (polls <= 3 || polls % 40 === 0) vlog("poll", polls, "RSC", now.RecalcStyleCount, "LC", now.LayoutCount, "keys", Object.keys(now).length);
    if (now.RecalcStyleCount !== last.RecalcStyleCount || now.LayoutCount !== last.LayoutCount) {
      lastChange = performance.now();
      changed = true;
    }
    last = now;
    const idle = performance.now() - lastChange;
    if (idle >= settleMs && (!requireChange || changed)) break;
    if (requireChange && !changed && !forced && forceFn && performance.now() - t0 > forceAfterMs) {
      forced = true;
      await forceFn();
    }
    if (performance.now() - t0 > maxMs) break;
  }
  return {
    waitedMs: performance.now() - t0,
    activeMs: Math.max(0, lastChange - t0),      // time from start until the last observed counter change
    recalcs: (last.RecalcStyleCount ?? 0) - (initial.RecalcStyleCount ?? 0),
    layouts: (last.LayoutCount ?? 0) - (initial.LayoutCount ?? 0),
    changed, forced, polls,
    timedOut: performance.now() - t0 > maxMs,
    metrics: last,
  };
}

async function nodeIds(cdp, targetSelector) {
  const { root } = await cdp.send("DOM.getDocument", { depth: 1 });
  const htmlNode = root.children?.find((c) => c.localName === "html") ?? root.children?.[0];
  const htmlId = htmlNode.nodeId;
  let targetId = htmlId;
  if (targetSelector !== "html") {
    const r = await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: targetSelector });
    if (!r.nodeId) throw new Error(`mutation target ${targetSelector} not found`);
    targetId = r.nodeId;
  }
  return { docId: root.nodeId, htmlId, targetId };
}

/** Apply the mutation under test via CDP (no JS in the page). */
async function mutate(cdp, ids, page, trialIndex, mutationIndex) {
  if (TRIGGER === "attr") {
    // R2G: explicit per-trial attribute writes from the manifest (selector, attribute name, value)
    const list = page.mutations ?? [];
    if (!list.length) throw new Error(`page ${page.id} has no mutations for --trigger attr`);
    const m = list[(trialIndex * (WARMUP + 1) + mutationIndex) % list.length];
    const r = await cdp.send("DOM.querySelector", { nodeId: ids.docId, selector: m.selector });
    if (!r.nodeId) throw new Error(`mutation target ${m.selector} not found`);
    await cdp.send("DOM.setAttributeValue", { nodeId: r.nodeId, name: m.name, value: m.value });
    return { trigger: "attr", ...m };
  }
  if (TRIGGER === "inline") {
    const [lo, hi] = page.in_range;
    const value = lo + Math.random() * (hi - lo);
    await cdp.send("DOM.setAttributeValue", { nodeId: ids.targetId, name: "style", value: `--in:${value.toFixed(6)}` });
    return { trigger: "inline", value };
  }
  const k = (trialIndex * (WARMUP + 1) + mutationIndex) % page.go_values.length;
  await cdp.send("DOM.setAttributeValue", { nodeId: ids.htmlId, name: "class", value: `go-${k}` });
  return { trigger: "class", value: page.go_values[k], goIndex: k };
}

async function readComputed(cdp, docId, selector, property) {
  if (!VERIFY || !selector || !property) return null;
  try {
    const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: docId, selector });
    if (!nodeId) return null;
    const { computedStyle } = await cdp.send("CSS.getComputedStyleForNode", { nodeId });
    return computedStyle.find((p) => p.name === property)?.value ?? null;
  } catch (err) {
    return `error: ${err.message}`;
  }
}

async function startTracing(cdp) {
  const events = [];
  const collect = ({ value }) => events.push(...value);
  cdp.on("Tracing.dataCollected", collect);
  const complete = new Promise((resolve) => cdp.once("Tracing.tracingComplete", resolve));
  await cdp.send("Tracing.start", {
    transferMode: "ReportEvents",
    traceConfig: { recordMode: "recordContinuously", includedCategories: TRACE_CATEGORIES },
  });
  return {
    events,
    async stop() {
      await cdp.send("Tracing.end");
      await complete;
      cdp.off("Tracing.dataCollected", collect);
      return events;
    },
  };
}

// ------------------------------------------------------------- one trial ----
async function runTrial(browser, page, trialIndex, saveTrace) {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 800, height: 600 } });
  const pw = await context.newPage();
  const cdp = await context.newCDPSession(pw);
  const record = { variant: page.id, family: page.family, params: page.params, bytes: page.bytes, trial: trialIndex, warmups: WARMUP, trigger: TRIGGER };
  try {
    await cdp.send("Performance.enable", { timeDomain: "timeTicks" });
    await cdp.send("DOM.enable");
    if (VERIFY) await cdp.send("CSS.enable");

    const url = `file://${path.resolve(here, "pages", page.file)}`;
    const tLoad = performance.now();
    vlog("goto", url);
    await pw.goto(url, { waitUntil: "load", timeout: LOAD_TIMEOUT_MS });
    vlog("loaded");
    const loadSettle = await waitQuiescent(cdp, { settleMs: Math.max(SETTLE_MS, 500) });
    record.load = { loadMs: performance.now() - tLoad, settle: { waitedMs: loadSettle.waitedMs, recalcs: loadSettle.recalcs, layouts: loadSettle.layouts } };
    record.metricsAfterLoad = Object.fromEntries(Object.entries(loadSettle.metrics).filter(([k]) => METRIC_NAMES.includes(k)));
    vlog("load settle", JSON.stringify({ waited: loadSettle.waitedMs, recalcs: loadSettle.recalcs, layouts: loadSettle.layouts, RSC: loadSettle.metrics.RecalcStyleCount }));
    record.rssAfterLoad = await rendererRss(browser);
    vlog("rss", JSON.stringify(record.rssAfterLoad));

    const ids = await nodeIds(cdp, page.target);
    const force = async () => { try { const r = await cdp.send("DOM.getBoxModel", { nodeId: ids.targetId }); vlog("forced getBoxModel ok", !!r.model); } catch (err) { vlog("forced getBoxModel FAILED", err.message); } };

    // untraced warm-ups (same trigger, different values)
    record.warmup = [];
    for (let w = 0; w < WARMUP; w += 1) {
      const base = metricsMap(await cdp.send("Performance.getMetrics"));
      const m = await mutate(cdp, ids, page, trialIndex, w);
      vlog("warmup mutated", JSON.stringify(m));
      const q = await waitQuiescent(cdp, { requireChange: true, forceFn: force, baseline: base });
      vlog("warmup settled", JSON.stringify({ waited: q.waitedMs, recalcs: q.recalcs, layouts: q.layouts, forced: q.forced, changed: q.changed }));
      record.warmup.push({ ...m, activeMs: q.activeMs, recalcs: q.recalcs, layouts: q.layouts, forced: q.forced });
    }

    const verifyBefore = await readComputed(cdp, ids.docId, page.verify_selector, page.verify_property);

    // ---- traced mutation ----
    const tracing = await startTracing(cdp);
    await sleep(150); // let tracing settle so the mutation is not at the buffer edge
    const before = metricsMap(await cdp.send("Performance.getMetrics"));
    const tMut = performance.now();
    const mutation = await mutate(cdp, ids, page, trialIndex, WARMUP);
    vlog("traced mutation", JSON.stringify(mutation));
    const q = await waitQuiescent(cdp, { requireChange: true, forceFn: force, baseline: before });
    const after = metricsMap(await cdp.send("Performance.getMetrics"));
    vlog("settled", JSON.stringify({ waited: q.waitedMs, recalcs: q.recalcs, layouts: q.layouts, forced: q.forced }));
    const events = await tracing.stop();
    vlog("trace events", events.length);

    record.mutation = mutation;
    record.harness = { mutateToQuiescentMs: performance.now() - tMut, activeMs: q.activeMs, recalcs: q.recalcs, layouts: q.layouts, forced: q.forced, timedOut: q.timedOut, polls: q.polls };
    record.metricsDelta = metricDelta(before, after);
    record.trace = summarizeTrace(events, { windowStartUs: before.Timestamp * 1e6, windowEndUs: after.Timestamp * 1e6 });
    record.traceEventCount = events.length;
    record.rssAfterMutation = await rendererRss(browser);
    // F5: quiet idle window after settle -> per-frame animation/transition servicing cost with NO mutation
    {
      const IDLE_MS = Number(opt("--idle-ms", 3000));
      const i0 = metricsMap(await cdp.send("Performance.getMetrics"));
      const w0 = performance.now();
      await sleep(IDLE_MS);
      const i1 = metricsMap(await cdp.send("Performance.getMetrics"));
      const wall = performance.now() - w0;
      record.idle = { wallMs: wall, taskMs: (i1.TaskDuration - i0.TaskDuration) * 1000, threadMs: (i1.ThreadTime - i0.ThreadTime) * 1000,
        recalcs: i1.RecalcStyleCount - i0.RecalcStyleCount, recalcMs: (i1.RecalcStyleDuration - i0.RecalcStyleDuration) * 1000,
        layouts: i1.LayoutCount - i0.LayoutCount, busyPct: 100 * (i1.TaskDuration - i0.TaskDuration) * 1000 / wall };
    }

    const verifyAfter = await readComputed(cdp, ids.docId, page.verify_selector, page.verify_property);
    record.verify = { selector: page.verify_selector, property: page.verify_property, before: verifyBefore, after: verifyAfter, changed: verifyBefore != null && verifyAfter != null && verifyBefore !== verifyAfter };

    if (saveTrace) {
      await fsp.mkdir(TRACE_DIR, { recursive: true });
      const file = path.join(TRACE_DIR, `${page.id}${SAVE_ALL_TRACES ? `-t${trialIndex}` : ""}.trace.json.gz`);
      await fsp.writeFile(file, zlib.gzipSync(JSON.stringify({ traceEvents: events, metadata: { variant: page.id, trial: trialIndex, windowStartUs: before.Timestamp * 1e6, windowEndUs: after.Timestamp * 1e6 } })));
      record.traceFile = path.relative(here, file);
    }
  } catch (err) {
    record.error = String(err?.stack ?? err);
  } finally {
    await context.close().catch(() => {});
  }
  return record;
}

// ------------------------------------------------------------- summary ----
function trialRow(r) {
  const t = r.trace ?? {};
  return {
    ultCount: t.updateLayoutTree?.count, ultMs: (t.updateLayoutTree?.totalUs ?? NaN) / 1000,
    ultElements: (t.updateLayoutTree?.elementCounts ?? []).reduce((a, b) => a + (b ?? 0), 0),
    layoutCount: t.layout?.count, layoutMs: (t.layout?.totalUs ?? NaN) / 1000,
    prePaintMs: (t.prePaint?.totalUs ?? NaN) / 1000, paintMs: (t.paint?.totalUs ?? NaN) / 1000,
    animMs: (t.animation?.bucket?.selfUs ?? NaN) / 1000,
    busyMs: (t.topLevelBusyUs ?? NaN) / 1000,
    activeMs: r.harness?.activeMs,
    recalcStyleCount: r.metricsDelta?.RecalcStyleCount, recalcStyleMs: r.metricsDelta?.RecalcStyleDurationMs,
    layoutCountMetric: r.metricsDelta?.LayoutCount, layoutMsMetric: r.metricsDelta?.LayoutDurationMs,
    threadTimeMs: r.metricsDelta?.ThreadTimeMs,
    invalidations: t.invalidation?.styleRecalc?.count,
    verified: r.verify?.changed,
    forced: r.harness?.forced,
    idleTaskMsPerS: r.idle ? r.idle.taskMs / (r.idle.wallMs / 1000) : NaN,
    idleRecalcs: r.idle?.recalcs,
    rssMB: r.rssAfterMutation?.maxRendererRssMB,
  };
}

function fmt(v, d = 1) { return Number.isFinite(v) ? v.toFixed(d) : "-"; }

function summarize(allRecords, env) {
  const byVariant = new Map();
  for (const r of allRecords) {
    if (!byVariant.has(r.variant)) byVariant.set(r.variant, []);
    byVariant.get(r.variant).push(r);
  }
  const lines = [
    `# M1 micro-benchmark summary`,
    ``,
    `Run started ${env.startedAt}; Chrome ${env.chrome}; node ${env.node}; ${env.cpu}; AC=${env.power.onAC}; caffeinate=${env.power.caffeinated}; therm: ${env.power.therm}`,
    `trials=${TRIALS} warmup=${WARMUP} trigger=${TRIGGER} settle=${SETTLE_MS}ms. Values are medians over trials [min–max] of the traced mutation only.`,
    `Columns: ULT = UpdateLayoutTree events (count / total ms / elements restyled), Layout (count / ms), PrePaint+Paint ms, Anim = self ms of animation-named events, Busy = top-level main-thread ms in window, Active = ms from mutation until counters stopped changing, RSC/RSD = Performance.getMetrics RecalcStyleCount / RecalcStyleDuration deltas, MB/s = page bytes / ULT ms.`,
    ``,
    `| variant | bytes | ULT n | ULT ms | ULT elems | Layout n | Layout ms | PrePaint+Paint ms | Anim ms | Busy ms | Active ms | RSC | RSD ms | MB/s | idle task ms/s | RSS MB | verified | err |`,
    `|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|`,
  ];
  const json = [];
  for (const [variant, recs] of byVariant) {
    const ok = recs.filter((r) => !r.error);
    const rows = ok.map(trialRow);
    const col = (k) => rows.map((x) => x[k]);
    const m = (k) => median(col(k));
    const rng = (k) => { const v = col(k).filter(Number.isFinite); return v.length ? `${fmt(Math.min(...v))}–${fmt(Math.max(...v))}` : "-"; };
    const bytes = recs[0].bytes;
    const mbps = bytes / 1e6 / (m("ultMs") / 1000);
    const errs = recs.filter((r) => r.error).length;
    lines.push(`| ${variant} | ${(bytes / 1e6).toFixed(2)} | ${fmt(m("ultCount"), 0)} | ${fmt(m("ultMs"))} [${rng("ultMs")}] | ${fmt(m("ultElements"), 0)} | ${fmt(m("layoutCount"), 0)} | ${fmt(m("layoutMs"))} | ${fmt(m("prePaintMs") + m("paintMs"))} | ${fmt(m("animMs"))} | ${fmt(m("busyMs"))} [${rng("busyMs")}] | ${fmt(m("activeMs"))} | ${fmt(m("recalcStyleCount"), 0)} | ${fmt(m("recalcStyleMs"))} | ${fmt(mbps)} | ${fmt(m("idleTaskMsPerS"))} | ${fmt(m("rssMB"), 0)} | ${ok.filter((r) => r.verify?.changed).length}/${ok.length} | ${errs || ""} |`);
    json.push({ variant, family: recs[0].family, params: recs[0].params, bytes, trials: ok.length, errors: errs,
      median: Object.fromEntries(Object.keys(rows[0] ?? {}).map((k) => [k, m(k)])),
      min: Object.fromEntries(Object.keys(rows[0] ?? {}).map((k) => [k, Math.min(...col(k).filter(Number.isFinite))])),
      max: Object.fromEntries(Object.keys(rows[0] ?? {}).map((k) => [k, Math.max(...col(k).filter(Number.isFinite))])),
      invalidationReasons: ok[0]?.trace?.invalidation ?? null,
      topSelf: ok[0]?.trace?.topSelf?.slice(0, 12) ?? null });
  }
  return { md: lines.join("\n") + "\n", json };
}

// ---------------------------------------------------------------- main ----
async function main() {
  const env = preflight();
  const manifest = JSON.parse(await fsp.readFile(path.join(here, "pages", "manifest.json"), "utf8"));
  let pages = manifest.pages.filter((p) => !FILTER || FILTER.test(p.id));
  if (SHUFFLE) pages = pages.map((p) => [Math.random(), p]).sort((a, b) => a[0] - b[0]).map(([, p]) => p);
  if (!pages.length) { console.error("no pages match the filter"); process.exit(1); }
  console.log(`[run] ${pages.length} variants x ${TRIALS} trials (warmup ${WARMUP}, trigger ${TRIGGER}); est. ${(pages.length * TRIALS * 6 / 60).toFixed(0)}+ min`);
  if (DRY_RUN) { console.log(pages.map((p) => `${p.id}  ${(p.bytes / 1e6).toFixed(2)} MB  target=${p.target}`).join("\n")); return; }

  await fsp.mkdir(OUT_DIR, { recursive: true });
  const stamp = env.startedAt.replace(/[:.]/g, "-");
  await fsp.writeFile(path.join(OUT_DIR, `run-${stamp}.env.json`), JSON.stringify({ ...env, manifestSeed: manifest.seed, variants: pages.map((p) => p.id) }, null, 1));

  const { chromium } = require(`${dependencyRoot}/playwright`);
  const all = [];
  for (const [i, page] of pages.entries()) {
    const therm = sh("/usr/bin/pmset", ["-g", "therm"]).replace(/\s+/g, " ");
    console.log(`[${i + 1}/${pages.length}] ${page.id} (${(page.bytes / 1e6).toFixed(2)} MB) ${therm}`);
    const browser = await chromium.launch({ executablePath, headless: true, args: LAUNCH_ARGS });
    const version = await browser.version();
    const out = fs.createWriteStream(path.join(OUT_DIR, `${page.id}.jsonl`), { flags: "a" });
    try {
      for (let t = 0; t < TRIALS; t += 1) {
        const rec = await runTrial(browser, page, t, t === 0 || SAVE_ALL_TRACES);
        rec.chrome = version;
        rec.startedAt = env.startedAt;
        rec.therm = therm;
        out.write(JSON.stringify(rec) + "\n");
        all.push(rec);
        const row = trialRow(rec);
        console.log(rec.error
          ? `   trial ${t}: ERROR ${rec.error.split("\n")[0]}`
          : `   trial ${t}: ULT ${row.ultCount}x ${fmt(row.ultMs)} ms (${row.ultElements} elems) | Layout ${row.layoutCount}x ${fmt(row.layoutMs)} ms | busy ${fmt(row.busyMs)} ms | active ${fmt(row.activeMs)} ms | RSC ${row.recalcStyleCount} RSD ${fmt(row.recalcStyleMs)} ms | verified=${row.verified}${row.forced ? " FORCED" : ""}`);
      }
    } finally {
      out.end();
      await browser.close().catch(() => {});
    }
    // incremental summary after every variant so partial runs are usable
    const { md, json } = summarize(all, env);
    await fsp.writeFile(path.join(OUT_DIR, "summary.md"), md);
    await fsp.writeFile(path.join(OUT_DIR, "summary.json"), JSON.stringify(json, null, 1));
  }
  console.log(`[run] done. ${path.join(OUT_DIR, "summary.md")}`);
}

main().catch((err) => { console.error(err); process.exit(1); });
