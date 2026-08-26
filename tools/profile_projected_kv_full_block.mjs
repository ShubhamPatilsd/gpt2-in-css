import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const context = Number(process.env.PROJECTED_KV_PROFILE_CONTEXT ?? 16);
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);
const stem = `attention-context-${context}-geometry-streaming-flat-projected-kv-score-cached-value-live-current-kv-siblings-projected`;
const variants = [
  {
    name: "attention",
    file: `${stem}.html`,
    selector: "#attention-result",
    property: "--r1-000",
  },
  {
    name: "mlp-isolated-multitoken",
    file: `${stem}-full-block0-multitoken-isolated.html`,
    selector: "#final",
    property: "--out-000",
  },
  {
    name: "connected-multitoken",
    file: `${stem}-full-block0-multitoken.html`,
    selector: "#final",
    property: "--out-000",
  },
];

function metricMap(result) {
  return Object.fromEntries(result.metrics.map(({ name, value }) => [name, value]));
}

function aggregate(events) {
  const values = new Map();
  for (const event of events) {
    if (event.ph !== "X" || !(event.dur > 0)) continue;
    const current = values.get(event.name) ?? {
      microseconds: 0,
      count: 0,
      maximum: 0,
    };
    current.microseconds += event.dur;
    current.count += 1;
    current.maximum = Math.max(current.maximum, event.dur);
    values.set(event.name, current);
  }
  return [...values.entries()].map(([name, value]) => ({
    name,
    milliseconds: value.microseconds / 1000,
    count: value.count,
    maximumMilliseconds: value.maximum / 1000,
  })).sort((left, right) => right.milliseconds - left.milliseconds);
}

const browser = await chromium.launch({ executablePath, headless: true });
const profiles = [];
try {
  const warm = await browser.newPage({ viewport: { width: 900, height: 300 } });
  for (const variant of variants) {
    await warm.goto(
      `http://127.0.0.1:4178/experiments/gpt2-block-css/${variant.file}?warm=1`,
      { waitUntil: "load", timeout: 180000 },
    );
    await warm.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
  }
  await warm.close();

  for (const variant of variants) {
    const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
    const session = await page.context().newCDPSession(page);
    await session.send("Performance.enable");
    const before = metricMap(await session.send("Performance.getMetrics"));
    const events = [];
    session.on("Tracing.dataCollected", ({ value }) => events.push(...value));
    let finishTrace;
    const traceComplete = new Promise((resolve) => { finishTrace = resolve; });
    session.on("Tracing.tracingComplete", finishTrace);
    await session.send("Tracing.start", {
      transferMode: "ReportEvents",
      categories: [
        "devtools.timeline",
        "blink",
        "blink.animations",
        "disabled-by-default-devtools.timeline",
        "disabled-by-default-devtools.timeline.frame",
      ].join(","),
    });
    const started = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/gpt2-block-css/${variant.file}?profile=1`,
      { waitUntil: "load", timeout: 180000 },
    );
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const output = await page.locator(variant.selector).evaluate(
      (element, property) => Number.parseFloat(
        getComputedStyle(element).getPropertyValue(property),
      ),
      variant.property,
    );
    const milliseconds = performance.now() - started;
    await session.send("Tracing.end");
    await traceComplete;
    const after = metricMap(await session.send("Performance.getMetrics"));
    const allEvents = aggregate(events);
    const keyNames = new Set([
      "UpdateLayoutTree",
      "Layout",
      "InlineNode::ShapeTextIncludingFirstLine",
      "AnimationTimeline::serviceAnimations",
      "PrePaint",
      "ParseAuthorStyleSheet",
    ]);
    profiles.push({
      ...variant,
      milliseconds,
      output,
      metrics: Object.fromEntries([
        "LayoutCount",
        "RecalcStyleCount",
        "LayoutDuration",
        "RecalcStyleDuration",
        "TaskDuration",
        "ScriptDuration",
        "JSHeapUsedSize",
        "Nodes",
      ].map((name) => [name, (after[name] ?? 0) - (before[name] ?? 0)])),
      keyEvents: allEvents.filter(({ name }) => keyNames.has(name)),
      topEvents: allEvents.slice(0, 30),
    });
    await session.detach();
    await page.close();
  }
} finally {
  await browser.close();
}

const byName = Object.fromEntries(profiles.map((profile) => [profile.name, profile]));
const separate = byName.attention.milliseconds + byName["mlp-isolated-multitoken"].milliseconds;
const connected = byName["connected-multitoken"].milliseconds;
const report = {
  chrome: await browser.version(),
  context,
  profiles,
  separateMilliseconds: separate,
  connectedMilliseconds: connected,
  connectedPremiumMilliseconds: connected - separate,
  connectedOverSeparateRatio: connected / separate,
};
await fs.writeFile(
  new URL(`projected-kv-full-block0-profile-${context}.json`, directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
