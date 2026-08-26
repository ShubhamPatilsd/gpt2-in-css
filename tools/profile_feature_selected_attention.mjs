import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);
const variants = [
  {
    name: "metric-per-key-coordinate",
    file: "attention-context-16-geometry-streaming-flat-siblings-projected.html",
  },
  {
    name: "feature-selected-qk",
    file: "attention-context-16-geometry-streaming-flat-feature-score-siblings-projected.html",
  },
  {
    name: "feature-selected-qk-mixed-v",
    file: "attention-context-16-geometry-streaming-flat-feature-score-mixed-value-siblings-projected.html",
  },
  {
    name: "projected-kv-cache",
    file: "attention-context-16-geometry-streaming-flat-projected-kv-score-cached-value-siblings-projected.html",
  },
  {
    name: "projected-kv-cache-live",
    file: "attention-context-16-geometry-streaming-flat-projected-kv-score-cached-value-nested-cache-siblings-projected.html",
  },
];

function metricMap(result) {
  return Object.fromEntries(result.metrics.map(({ name, value }) => [name, value]));
}

function aggregate(events) {
  const values = new Map();
  for (const event of events) {
    if (event.ph !== "X" || !(event.dur > 0)) continue;
    const current = values.get(event.name) ?? { microseconds: 0, count: 0 };
    current.microseconds += event.dur;
    current.count += 1;
    values.set(event.name, current);
  }
  return [...values.entries()].map(([name, value]) => ({
    name,
    milliseconds: value.microseconds / 1000,
    count: value.count,
  })).sort((left, right) => right.milliseconds - left.milliseconds);
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
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
    let resolveTrace;
    const traceComplete = new Promise((resolve) => { resolveTrace = resolve; });
    session.on("Tracing.tracingComplete", resolveTrace);
    await session.send("Tracing.start", {
      transferMode: "ReportEvents",
      categories: "devtools.timeline,blink,blink.animations,disabled-by-default-devtools.timeline",
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
    const output = await page.locator("#attention-result").evaluate((element) =>
      Number.parseFloat(getComputedStyle(element).getPropertyValue("--r1-000"))
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
      topEvents: allEvents.slice(0, 25),
    });
    await session.detach();
    await page.close();
  }
} finally {
  await browser.close();
}

const oldProfile = profiles[0];
const newProfile = profiles[1];
const mixedProfile = profiles[2];
const projectedKvProfile = profiles[3];
const projectedKvLiveProfile = profiles[4];
const report = {
  chrome: await browser.version(),
  profiles,
  speedup: oldProfile.milliseconds / newProfile.milliseconds,
  savedMilliseconds: oldProfile.milliseconds - newProfile.milliseconds,
  mixedValueSpeedup: oldProfile.milliseconds / mixedProfile.milliseconds,
  mixedValueSavedMilliseconds: oldProfile.milliseconds - mixedProfile.milliseconds,
  projectedKvSpeedup: oldProfile.milliseconds / projectedKvProfile.milliseconds,
  projectedKvSavedMilliseconds: oldProfile.milliseconds - projectedKvProfile.milliseconds,
  projectedKvLiveSpeedup: oldProfile.milliseconds / projectedKvLiveProfile.milliseconds,
};
await fs.writeFile(
  new URL("feature-selected-attention-profile-16.json", directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
