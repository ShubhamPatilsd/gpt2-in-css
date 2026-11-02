import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const origin = process.env.HVAR_ORIGIN ?? "http://127.0.0.1:4178";
const directory = process.env.HVAR_TRACE_DIRECTORY ??
  "avar2-gelu-linear-hvar-full-mlp-g13";
const file = process.env.HVAR_TRACE_FILE ??
  "connected-two-block-shadow-staged.html";
const outputSelector = process.env.HVAR_TRACE_OUTPUT_SELECTOR ?? ".b1-output-767";
const url = `${origin}/experiments/${directory}/${file}`;
const outputDirectory = new URL(
  "../experiments/hvar-two-block-toggle-trace/",
  import.meta.url,
);
const resultFile = process.env.HVAR_TRACE_RESULT ?? "trace-summary.json";

function percentile(values, fraction) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor((sorted.length - 1) * fraction)];
}

function metricsMap(result) {
  return Object.fromEntries(result.metrics.map(({ name, value }) => [name, value]));
}

function metricDelta(before, after) {
  const names = [
    "LayoutCount",
    "RecalcStyleCount",
    "LayoutDuration",
    "RecalcStyleDuration",
    "ScriptDuration",
    "TaskDuration",
    "Nodes",
    "LayoutObjects",
  ];
  return Object.fromEntries(names.map((name) => {
    const delta = (after[name] ?? 0) - (before[name] ?? 0);
    return name.endsWith("Duration")
      ? [`${name}Milliseconds`, delta * 1000]
      : [name, delta];
  }));
}

function mainThread(events) {
  const rendererNames = new Set(
    events
      .filter((event) => event.ph === "M" && event.name === "thread_name" &&
        event.args?.name === "CrRendererMain")
      .map((event) => `${event.pid}:${event.tid}`),
  );
  if (rendererNames.size) return rendererNames.values().next().value;
  const totals = new Map();
  for (const event of events) {
    if (event.ph !== "X" || event.name !== "UpdateLayoutTree") continue;
    const key = `${event.pid}:${event.tid}`;
    totals.set(key, (totals.get(key) ?? 0) + (event.dur ?? 0));
  }
  return [...totals.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
}

function aggregateTrace(events, startMicroseconds, endMicroseconds) {
  const thread = mainThread(events);
  const complete = events
    .filter((event) => event.ph === "X" && event.dur > 0 &&
      `${event.pid}:${event.tid}` === thread &&
      event.ts < endMicroseconds && event.ts + event.dur > startMicroseconds)
    .map((event) => {
      const start = Math.max(event.ts, startMicroseconds);
      const end = Math.min(event.ts + event.dur, endMicroseconds);
      return { ...event, ts: start, dur: end - start };
    })
    .sort((a, b) => a.ts - b.ts || b.dur - a.dur);

  const nodes = complete.map((event) => ({ event, children: [] }));
  const stack = [];
  for (const node of nodes) {
    const start = node.event.ts;
    const end = start + node.event.dur;
    while (stack.length && start >= stack.at(-1).event.ts + stack.at(-1).event.dur) {
      stack.pop();
    }
    const parent = stack.at(-1);
    if (parent && end <= parent.event.ts + parent.event.dur) parent.children.push(node);
    stack.push(node);
  }

  const byName = new Map();
  for (const node of nodes) {
    const childDuration = node.children.reduce((sum, child) => sum + child.event.dur, 0);
    const self = Math.max(0, node.event.dur - childDuration);
    const value = byName.get(node.event.name) ?? {
      count: 0,
      inclusiveMicroseconds: 0,
      selfMicroseconds: 0,
      maximumMicroseconds: 0,
    };
    value.count += 1;
    value.inclusiveMicroseconds += node.event.dur;
    value.selfMicroseconds += self;
    value.maximumMicroseconds = Math.max(value.maximumMicroseconds, node.event.dur);
    byName.set(node.event.name, value);
  }
  const rows = [...byName.entries()].map(([name, value]) => ({
    name,
    count: value.count,
    inclusiveMilliseconds: value.inclusiveMicroseconds / 1000,
    selfMilliseconds: value.selfMicroseconds / 1000,
    maximumMilliseconds: value.maximumMicroseconds / 1000,
  }));

  const patterns = {
    fontShaping: /ShapeText|HarfBuzz|Shaper|ShapeResult|Glyph|Font/i,
    style: /Style|Selector|RuleSet|MatchRequest|UpdateLayoutTree/i,
    layout: /Layout|Fragment|LineBox|InlineNode|OutOfFlow/i,
    anchor: /Anchor|PositionTry|Positioned/i,
    shadowSlot: /Shadow|HTMLSlot|SlotAssignment|FlatTree|Distribution|AssignedNodes/i,
  };
  const categories = Object.fromEntries(Object.entries(patterns).map(([category, pattern]) => {
    const matching = rows.filter(({ name }) => pattern.test(name));
    return [category, {
      eventNames: matching.length,
      eventCount: matching.reduce((sum, row) => sum + row.count, 0),
      inclusiveMilliseconds: matching.reduce((sum, row) => sum + row.inclusiveMilliseconds, 0),
      selfMilliseconds: matching.reduce((sum, row) => sum + row.selfMilliseconds, 0),
      topEvents: matching.sort((a, b) => b.selfMilliseconds - a.selfMilliseconds).slice(0, 15),
    }];
  }));

  return {
    rendererMainThread: thread,
    completeEventCount: complete.length,
    categories,
    topSelfEvents: [...rows].sort((a, b) => b.selfMilliseconds - a.selfMilliseconds).slice(0, 40),
    topInclusiveEvents: [...rows].sort((a, b) => b.inclusiveMilliseconds - a.inclusiveMilliseconds).slice(0, 40),
  };
}

function markerTimestamp(events, label) {
  const matches = events.filter((event) =>
    event.name === label ||
    event.args?.data?.name === label ||
    event.args?.data?.message === label ||
    event.args?.name === label,
  );
  return {
    timestamp: matches[0]?.ts,
    matches: matches.slice(0, 5).map((event) => ({
      name: event.name,
      phase: event.ph,
      timestamp: event.ts,
      args: event.args,
    })),
  };
}

async function toggle(page, mode, marker = null) {
  return page.evaluate(({ caseId, marker, outputSelector }) => {
    const deepQuery = (root, selector) => {
      const direct = root.querySelector(selector);
      if (direct) return direct;
      for (const element of root.querySelectorAll("*")) {
        if (!element.shadowRoot) continue;
        const nested = deepQuery(element.shadowRoot, selector);
        if (nested) return nested;
      }
      return null;
    };
    if (marker) {
      performance.mark(`${marker}-start`);
      console.timeStamp(`${marker}-start`);
    }
    const started = performance.now();
    document.querySelector(`#case-${caseId}`).checked = true;
    const output = deepQuery(document, outputSelector);
    if (!output) throw new Error(`missing output ${outputSelector}`);
    const width = output.getBoundingClientRect().width;
    if (marker) {
      console.timeStamp(`${marker}-end`);
      performance.mark(`${marker}-end`);
    }
    return { milliseconds: performance.now() - started, width };
  }, { caseId: mode, marker, outputSelector });
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 1000, height: 120 },
  });
  const page = await context.newPage();
  await page.goto(url, { waitUntil: "load", timeout: 120_000 });
  await page.evaluate(async (outputSelector) => {
    const deepQuery = (root, selector) => {
      const direct = root.querySelector(selector);
      if (direct) return direct;
      for (const element of root.querySelectorAll("*")) {
        if (!element.shadowRoot) continue;
        const nested = deepQuery(element.shadowRoot, selector);
        if (nested) return nested;
      }
      return null;
    };
    await document.fonts.ready;
    const output = deepQuery(document, outputSelector);
    if (!output) throw new Error(`missing output ${outputSelector}`);
    output.getBoundingClientRect();
  }, outputSelector);

  const structure = await page.evaluate(() => {
    const roots = [document];
    const all = [];
    const shadowHosts = [];
    for (let index = 0; index < roots.length; index += 1) {
      const root = roots[index];
      for (const element of root.querySelectorAll("*")) {
        all.push(element);
        if (!element.shadowRoot) continue;
        shadowHosts.push(element);
        roots.push(element.shadowRoot);
      }
    }
    return {
      documentElements: document.querySelectorAll("*").length,
      totalElements: all.length,
      shadowRoots: shadowHosts.length,
      shadowElements: all.length - document.querySelectorAll("*").length,
      slots: all.filter((element) => element.localName === "slot").length,
    };
  });
  const source = await fs.readFile(
    new URL(`../experiments/${directory}/${file}`, import.meta.url),
    "utf8",
  );
  Object.assign(structure, {
    sourceBytes: Buffer.byteLength(source),
    declarativeShadowRoots: (source.match(/shadowrootmode=/g) ?? []).length,
    anchorNameDeclarations: (source.match(/anchor-name:/g) ?? []).length,
    anchorFunctionUses: (source.match(/anchor\(/g) ?? []).length,
    slotElementsInSource: (source.match(/<slot/g) ?? []).length,
  });

  // Prime every case so that tracing measures recomputation, not font loading.
  for (let mode = 0; mode < 4; mode += 1) await toggle(page, mode);

  const wallRounds = Number(process.env.HVAR_TRACE_WALL_ROUNDS ?? 12);
  const wallSamples = [];
  for (let round = 0; round < wallRounds; round += 1) {
    const mode = (round + 1) % 4;
    wallSamples.push({ round, mode, ...await toggle(page, mode) });
  }

  const session = await context.newCDPSession(page);
  await session.send("Performance.enable");
  const traceRounds = Number(process.env.HVAR_TRACE_ROUNDS ?? 3);
  const traces = [];
  for (let round = 0; round < traceRounds; round += 1) {
    const events = [];
    const collect = ({ value }) => events.push(...value);
    session.on("Tracing.dataCollected", collect);
    const complete = new Promise((resolve) => session.once("Tracing.tracingComplete", resolve));
    await session.send("Tracing.start", {
      transferMode: "ReportEvents",
      categories: [
        "devtools.timeline",
        "blink",
        "blink.style",
        "blink.layout",
        "blink.user_timing",
        "disabled-by-default-devtools.timeline",
        "disabled-by-default-devtools.timeline.frame",
        "disabled-by-default-blink.debug",
        "disabled-by-default-blink.debug.layout",
        "disabled-by-default-fonts",
      ].join(","),
    });
    const before = metricsMap(await session.send("Performance.getMetrics"));
    const mode = (wallRounds + round + 1) % 4;
    const marker = `hvar-toggle-${round}`;
    const result = await toggle(page, mode, marker);
    const after = metricsMap(await session.send("Performance.getMetrics"));
    await session.send("Tracing.end");
    await complete;
    session.off("Tracing.dataCollected", collect);
    const startMarker = markerTimestamp(events, `${marker}-start`);
    const endMarker = markerTimestamp(events, `${marker}-end`);
    const traceStart = startMarker.timestamp ?? before.Timestamp * 1_000_000;
    const traceEnd = endMarker.timestamp ?? after.Timestamp * 1_000_000;
    traces.push({
      round,
      mode,
      ...result,
      traceEvents: events.length,
      performanceMetrics: metricDelta(before, after),
      traceWindowMicroseconds: {
        start: traceStart,
        end: traceEnd,
        startMarkerMatches: startMarker.matches,
        endMarkerMatches: endMarker.matches,
      },
      trace: aggregateTrace(
        events,
        traceStart,
        traceEnd,
      ),
    });
  }

  const measuredWall = wallSamples.slice(4).map(({ milliseconds }) => milliseconds);
  const report = {
    chrome: await browser.version(),
    url,
    outputSelector,
    runtimeContainsJavaScript: false,
    structure,
    wallTiming: {
      rounds: wallRounds,
      discardedWarmupRounds: 4,
      minimumMilliseconds: Math.min(...measuredWall),
      medianMilliseconds: percentile(measuredWall, 0.5),
      p90Milliseconds: percentile(measuredWall, 0.9),
      maximumMilliseconds: Math.max(...measuredWall),
      samples: wallSamples,
    },
    traceRounds,
    traces,
  };
  await fs.mkdir(outputDirectory, { recursive: true });
  await fs.writeFile(
    new URL(resultFile, outputDirectory),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  await session.detach();
  await context.close();
} finally {
  await browser.close();
}
