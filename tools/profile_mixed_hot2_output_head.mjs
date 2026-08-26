import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const server = process.env.MIXED_HOT2_SERVER ?? "http://127.0.0.1:4189";
const directories = (process.env.MIXED_HOT2_PROFILE_DIRECTORIES
  ?? "gpt2-mixed-hot2-blockflow-group-max-shard256,gpt2-mixed-hot2-blockflow-group-max")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);
const targetFixture = Math.max(0, Number(process.env.MIXED_HOT2_PROFILE_FIXTURE ?? 1));
const warmFixture = Math.max(0, Number(process.env.MIXED_HOT2_PROFILE_WARM_FIXTURE ?? 0));
const output = process.env.MIXED_HOT2_PROFILE_OUTPUT
  ?? "experiments/gpt2-mixed-hot2-blockflow-group-max-shard256/output-head-trace-comparison.json";

function fixtureStyle(fixtures, fixture) {
  const hidden = fixtures.hiddenVectors[fixture];
  const properties = hidden.map((value, dimension) => `--h${dimension}:${value}`);
  properties.push(`--score-offset:${-fixtures.scoreFloors[fixture] * 256 * 4}px`);
  properties.push(`--query-norm:${Math.sqrt(
    hidden.reduce((sum, value) => sum + value * value, 0),
  )}`);
  return properties.join(";");
}

function metricMap(metrics) {
  return Object.fromEntries(metrics.map(({ name, value }) => [name, value]));
}

function metricDelta(before, after) {
  const result = {};
  for (const [name, value] of Object.entries(after)) {
    if (typeof before[name] === "number") result[name] = value - before[name];
  }
  return result;
}

function aggregate(events) {
  const byName = new Map();
  for (const event of events) {
    if (event.ph !== "X" || !(event.dur > 0)) continue;
    const current = byName.get(event.name) ?? {
      microseconds: 0,
      count: 0,
      maximumMicroseconds: 0,
    };
    current.microseconds += event.dur;
    current.count += 1;
    current.maximumMicroseconds = Math.max(current.maximumMicroseconds, event.dur);
    byName.set(event.name, current);
  }
  return [...byName.entries()]
    .map(([name, value]) => ({
      name,
      milliseconds: value.microseconds / 1000,
      count: value.count,
      maximumMilliseconds: value.maximumMicroseconds / 1000,
    }))
    .sort((left, right) => right.milliseconds - left.milliseconds);
}

async function loadReference(directory) {
  return JSON.parse(await fs.readFile(
    new URL(`../experiments/${directory}/reference.json`, import.meta.url),
    "utf8",
  ));
}

async function setInput(page, fixtures, fixture) {
  await page.evaluate((style) => {
    for (const element of [document.querySelector(".cascade"), document.querySelector("#model")]) {
      element.style.cssText = style;
    }
  }, fixtureStyle(fixtures, fixture));
}

async function settle(page, stages) {
  return page.evaluate((stageCount) => {
    const reads = [];
    const force = (label, selector, kind = "width", property = "") => {
      const element = document.querySelector(selector);
      const started = performance.now();
      let value;
      if (kind === "style") value = getComputedStyle(element).getPropertyValue(property);
      else value = element.getBoundingClientRect().width;
      reads.push({ label, selector, milliseconds: performance.now() - started, value });
      return value;
    };
    performance.mark("mixed-hot2-settle-start");
    for (let pass = 0; pass < 3; pass += 1) {
      force(`pass-${pass}-result`, "#result");
      for (let stage = 0; stage < stageCount; stage += 1) {
        const wrapper = document.querySelector(`#mixed-stage-${stage}`);
        const wrapperStarted = performance.now();
        const wrapperDisplay = getComputedStyle(wrapper).display;
        reads.push({
          label: `pass-${pass}-stage-${stage}-wrapper`,
          selector: `#mixed-stage-${stage}`,
          milliseconds: performance.now() - wrapperStarted,
          value: wrapperDisplay,
        });
        if (wrapperDisplay === "none") break;
        const dynamic = document.querySelector(`#dynamic-fine-stage-${stage}`);
        if (getComputedStyle(dynamic).display !== "none") {
          force(`pass-${pass}-stage-${stage}-dynamic`, `#dynamic-fine-stage-${stage}`);
        }
        force(`pass-${pass}-stage-${stage}-choice`, `#mixed-choice-source-${stage}`);
        force(
          `pass-${pass}-stage-${stage}-fine`,
          stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
        );
        force(`pass-${pass}-stage-${stage}-remaining`, `#remaining-result-${stage + 1}`);
        const done = Number(force(
          `pass-${pass}-stage-${stage}-done`,
          `#remaining-result-${stage + 1}`,
          "style",
          `--done-${stage}`,
        ));
        if (done === 1) break;
      }
    }
    performance.mark("mixed-hot2-settle-end");
    performance.measure(
      "mixed-hot2-settle",
      "mixed-hot2-settle-start",
      "mixed-hot2-settle-end",
    );
    return {
      reads,
      settleMilliseconds: performance.getEntriesByName("mixed-hot2-settle").at(-1).duration,
    };
  }, stages);
}

async function profile(browser, directory) {
  const reference = await loadReference(directory);
  const fixtures = reference.certifiedFixtures;
  if (!fixtures.hiddenVectors[targetFixture] || !fixtures.hiddenVectors[warmFixture]) {
    throw new Error(`Fixture index is out of range for ${directory}`);
  }
  const context = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const page = await context.newPage();
  page.setDefaultTimeout(900_000);
  const loadStarted = performance.now();
  await page.goto(`${server}/experiments/${directory}/index.html`, {
    waitUntil: "load",
    timeout: 900_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  const loadMilliseconds = performance.now() - loadStarted;
  await setInput(page, fixtures, warmFixture);
  await settle(page, reference.stages);

  const session = await context.newCDPSession(page);
  await session.send("Performance.enable");
  const before = metricMap((await session.send("Performance.getMetrics")).metrics);
  const events = [];
  session.on("Tracing.dataCollected", ({ value }) => events.push(...value));
  const traceComplete = new Promise((resolve) => session.on("Tracing.tracingComplete", resolve));
  await session.send("Tracing.start", {
    transferMode: "ReportEvents",
    categories: [
      "devtools.timeline",
      "blink",
      "blink.animations",
      "blink.user_timing",
      "disabled-by-default-devtools.timeline",
      "disabled-by-default-devtools.timeline.frame",
    ].join(","),
  });
  const wallStarted = performance.now();
  await setInput(page, fixtures, targetFixture);
  const settleResult = await settle(page, reference.stages);
  const wallMilliseconds = performance.now() - wallStarted;
  await session.send("Tracing.end");
  await traceComplete;
  const after = metricMap((await session.send("Performance.getMetrics")).metrics);
  await session.detach();
  await context.close();

  const completeEvents = aggregate(events);
  return {
    directory,
    backend: reference.backend,
    topologyStrategy: reference.topologyStrategy,
    loadMilliseconds,
    wallMilliseconds,
    settleMilliseconds: settleResult.settleMilliseconds,
    reads: settleResult.reads,
    performanceMetricDelta: metricDelta(before, after),
    traceEventCount: events.length,
    topCompleteEvents: completeEvents.slice(0, 60),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const results = [];
  for (const directory of directories) {
    const result = await profile(browser, directory);
    results.push(result);
    console.log(JSON.stringify({
      directory,
      loadMilliseconds: result.loadMilliseconds,
      wallMilliseconds: result.wallMilliseconds,
      topCompleteEvents: result.topCompleteEvents.slice(0, 12),
    }, null, 2));
  }
  report = {
    chromeVersion: await browser.version(),
    targetFixture,
    warmFixture,
    results,
  };
} finally {
  await browser.close();
}

await fs.writeFile(new URL(`../${output}`, import.meta.url), `${JSON.stringify(report, null, 2)}\n`);
