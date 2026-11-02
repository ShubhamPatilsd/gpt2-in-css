import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${root}/playwright`);
const file = process.env.VIEW_TIMELINE_PROFILE_FILE ?? "view-timeline-block.html";
const scopeSelector = process.env.VIEW_TIMELINE_PROFILE_SCOPE ?? ".block-scope";
const inputPrefix = process.env.VIEW_TIMELINE_PROFILE_INPUT_PREFIX ?? "x";
const outputId = process.env.VIEW_TIMELINE_PROFILE_OUTPUT_ID ?? "final";
const outputPrefix = process.env.VIEW_TIMELINE_PROFILE_OUTPUT_PREFIX ?? "out";
const frames = Number(process.env.VIEW_TIMELINE_PROFILE_FRAMES ?? 3);
const mutationScale = Number(process.env.VIEW_TIMELINE_PROFILE_SCALE ?? 0.8);
const resultName = process.env.VIEW_TIMELINE_PROFILE_RESULT ??
  "view-timeline-block-mutation-trace.json";
const extraCss = process.env.VIEW_TIMELINE_PROFILE_EXTRA_CSS ?? "";

function aggregate(events) {
  const byName = new Map();
  for (const event of events) {
    if (event.ph !== "X" || !(event.dur > 0)) continue;
    const value = byName.get(event.name) ?? {
      microseconds: 0,
      count: 0,
      maximum: 0,
    };
    value.microseconds += event.dur;
    value.count += 1;
    value.maximum = Math.max(value.maximum, event.dur);
    byName.set(event.name, value);
  }
  return [...byName.entries()]
    .map(([name, value]) => ({
      name,
      milliseconds: value.microseconds / 1000,
      count: value.count,
      maximumMilliseconds: value.maximum / 1000,
    }))
    .sort((a, b) => b.milliseconds - a.milliseconds)
    .slice(0, 60);
}

function metricMap(result) {
  return Object.fromEntries(result.metrics.map(({ name, value }) => [name, value]));
}

function phaseTimeline(events) {
  const names = new Set([
    "UpdateLayoutTree",
    "Layout",
    "InlineNode::ShapeTextIncludingFirstLine",
    "AnimationTimeline::serviceAnimations",
    "PrePaint",
  ]);
  const selected = events.filter((event) =>
    event.ph === "X" && event.dur > 0 && names.has(event.name),
  );
  let origin = Infinity;
  for (const event of selected) origin = Math.min(origin, event.ts);
  const detailed = selected
    .filter((event) => event.name !== "InlineNode::ShapeTextIncludingFirstLine" &&
      event.name !== "AnimationTimeline::serviceAnimations")
    .map((event) => ({
      name: event.name,
      startMilliseconds: (event.ts - origin) / 1000,
      milliseconds: event.dur / 1000,
      args: event.args,
    }));
  for (const repeatedName of [
    "InlineNode::ShapeTextIncludingFirstLine",
    "AnimationTimeline::serviceAnimations",
  ]) {
    const buckets = new Map();
    for (const event of selected.filter(({ name }) => name === repeatedName)) {
      const bucket = Math.floor((event.ts - origin) / 100000) * 100;
      const value = buckets.get(bucket) ?? { count: 0, milliseconds: 0 };
      value.count += 1;
      value.milliseconds += event.dur / 1000;
      buckets.set(bucket, value);
    }
    detailed.push(...[...buckets.entries()].map(([startMilliseconds, value]) => ({
      name: `${repeatedName} (100ms bucket)`,
      startMilliseconds,
      ...value,
    })));
  }
  return detailed.sort((a, b) => a.startMilliseconds - b.startMilliseconds);
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

try {
  const page = await browser.newPage();
  await page.goto(
    `http://127.0.0.1:4178/experiments/gpt2-block-css/${file}`,
    { waitUntil: "load", timeout: 120000 },
  );
  if (extraCss) await page.addStyleTag({ content: extraCss });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });

  const session = await page.context().newCDPSession(page);
  await session.send("Performance.enable");
  const before = metricMap(await session.send("Performance.getMetrics"));
  const events = [];
  session.on("Tracing.dataCollected", ({ value }) => events.push(...value));
  let traceComplete;
  const completed = new Promise((resolve) => { traceComplete = resolve; });
  session.on("Tracing.tracingComplete", traceComplete);
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

  const result = await page.evaluate(async (options) => {
    const scope = document.querySelector(options.scopeSelector);
    const style = getComputedStyle(scope);
    const input = Array.from({ length: 768 }, (_, index) =>
      Number(style.getPropertyValue(
        `--${options.inputPrefix}-${String(index).padStart(3, "0")}`,
      )),
    );
    const started = performance.now();
    input.forEach((value, index) => {
      scope.style.setProperty(
        `--${options.inputPrefix}-${String(index).padStart(3, "0")}`,
        String(value * options.mutationScale),
      );
    });
    for (let frame = 0; frame < options.frames; frame += 1) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
    }
    const final = getComputedStyle(document.getElementById(options.outputId));
    const output = Array.from({ length: 768 }, (_, index) =>
      Number(final.getPropertyValue(
        `--${options.outputPrefix}-${String(index).padStart(3, "0")}`,
      )),
    );
    return {
      milliseconds: performance.now() - started,
      checksum: output.reduce((sum, value) => sum + value, 0),
    };
  }, {
    scopeSelector,
    inputPrefix,
    outputId,
    outputPrefix,
    frames,
    extraCss: extraCss || null,
    mutationScale,
  });

  await session.send("Tracing.end");
  await completed;
  const after = metricMap(await session.send("Performance.getMetrics"));
  const metricNames = [
    "LayoutCount",
    "RecalcStyleCount",
    "LayoutDuration",
    "RecalcStyleDuration",
    "ScriptDuration",
    "TaskDuration",
    "JSHeapUsedSize",
  ];
  const metrics = Object.fromEntries(metricNames.map((name) => [
    name,
    (after[name] ?? 0) - (before[name] ?? 0),
  ]));
  const report = {
    chrome: await browser.version(),
    file,
    frames,
    ...result,
    traceEvents: events.length,
    metrics,
    topCompleteEvents: aggregate(events),
    phaseTimeline: phaseTimeline(events),
  };
  await fs.writeFile(
    new URL(`../experiments/gpt2-block-css/${resultName}`, import.meta.url),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(JSON.stringify(report, null, 2));
  await session.detach();
} finally {
  await browser.close();
}
