import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const experiment = new URL("../experiments/smil-stage-scheduler/", import.meta.url);
const manifest = JSON.parse(await fs.readFile(new URL("manifest.json", experiment), "utf8"));
const base = "http://127.0.0.1:4178/experiments/smil-stage-scheduler";
const rounds = Number(process.env.SMIL_STAGE_ROUNDS ?? 5);
const selectedSizes = new Set(
  (process.env.SMIL_STAGE_SIZES ?? manifest.sizes.join(",")).split(",").map(Number),
);
const selectedModes = new Set(
  (process.env.SMIL_STAGE_MODES ?? manifest.modes.join(",")).split(","),
);

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

async function readMetrics(session) {
  const response = await session.send("Performance.getMetrics");
  return Object.fromEntries(response.metrics.map(({ name, value }) => [name, value]));
}

function metricDelta(after, before, name) {
  return (after[name] ?? 0) - (before[name] ?? 0);
}

async function runFixture(browser, descriptor) {
  const context = await browser.newContext({ viewport: { width: 800, height: 600 } });
  const page = await context.newPage();
  page.setDefaultTimeout(120000);
  const session = await context.newCDPSession(page);
  await session.send("Performance.enable");
  const before = await readMetrics(session);
  const wallStarted = performance.now();
  await page.goto(`${base}/${descriptor.file}`, { waitUntil: "domcontentloaded", timeout: 120000 });
  const domContentLoadedMilliseconds = performance.now() - wallStarted;
  const observation = await page.evaluate(async ({ mode }) => {
    const root = document.querySelector("#root");
    const gate = document.querySelector("#gate");
    const result = document.querySelector("#result");
    const started = performance.now();
    const frames = [];
    let upstreamReady = null;
    let stageReady = null;
    const deadline = (mode === "hidden" || mode === "smil-html-target") ? 350 : 2000;
    while (performance.now() - started < deadline) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
      const elapsed = performance.now() - started;
      const upstream = Number(getComputedStyle(root).getPropertyValue("--upstream"));
      const display = getComputedStyle(gate).display;
      const width = display === "none" ? 0 : result.getBoundingClientRect().width;
      if (upstreamReady === null && Math.abs(upstream - 37) < 0.001) upstreamReady = elapsed;
      if (stageReady === null && display !== "none" && Math.abs(width - 37) < 0.02) {
        stageReady = elapsed;
      }
      if (frames.length < 40) frames.push({ elapsed, upstream, display, width });
      if (mode !== "hidden" && stageReady !== null && elapsed >= 220) break;
    }
    return {
      upstreamReadyMilliseconds: upstreamReady,
      stageReadyMilliseconds: stageReady,
      finalUpstream: Number(getComputedStyle(root).getPropertyValue("--upstream")),
      finalGateDisplay: getComputedStyle(gate).display,
      finalWidth: getComputedStyle(gate).display === "none"
        ? 0 : result.getBoundingClientRect().width,
      frames,
    };
  }, { mode: descriptor.mode });
  const after = await readMetrics(session);
  await context.close();
  return {
    domContentLoadedMilliseconds,
    ...observation,
    layoutCount: metricDelta(after, before, "LayoutCount"),
    layoutDurationMilliseconds: metricDelta(after, before, "LayoutDuration") * 1000,
    recalcStyleCount: metricDelta(after, before, "RecalcStyleCount"),
    recalcStyleDurationMilliseconds: metricDelta(after, before, "RecalcStyleDuration") * 1000,
    taskDurationMilliseconds: metricDelta(after, before, "TaskDuration") * 1000,
  };
}

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH
    ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const report = { chrome: await browser.version(), rounds, results: {} };
try {
  for (const descriptor of manifest.fixtures.filter(
    ({ size, mode }) => selectedSizes.has(size) && selectedModes.has(mode),
  )) {
    const samples = [];
    for (let round = 0; round < rounds; round += 1) {
      samples.push(await runFixture(browser, descriptor));
    }
    const key = `${descriptor.size}-${descriptor.mode}`;
    report.results[key] = {
      ...descriptor,
      medians: Object.fromEntries([
        "domContentLoadedMilliseconds",
        "upstreamReadyMilliseconds",
        "stageReadyMilliseconds",
        "layoutCount",
        "layoutDurationMilliseconds",
        "recalcStyleCount",
        "recalcStyleDurationMilliseconds",
        "taskDurationMilliseconds",
      ].map((name) => [name, median(samples.map((sample) => sample[name]).filter(Number.isFinite))])),
      samples,
    };
  }
} finally {
  await browser.close();
}

for (const result of Object.values(report.results)) {
  for (const sample of result.samples) {
    if (Math.abs(sample.finalUpstream - 37) > 0.001) {
      throw new Error(`upstream did not settle: ${JSON.stringify(result)}`);
    }
    if (result.mode.startsWith("smil") && result.mode !== "smil-html-target" && (
      sample.finalGateDisplay === "none" || Math.abs(sample.finalWidth - 37) > 0.02
    )) {
      throw new Error(`SMIL stage failed to activate or inherit: ${JSON.stringify(result)}`);
    }
    if (result.mode === "hidden" && sample.finalGateDisplay !== "none") {
      throw new Error(`hidden control unexpectedly activated: ${JSON.stringify(result)}`);
    }
    if (result.mode === "smil-html-target" && sample.finalGateDisplay !== "none") {
      throw new Error(`SMIL unexpectedly targeted an HTML element: ${JSON.stringify(result)}`);
    }
  }
  const html = await fs.readFile(new URL(result.file, experiment), "utf8");
  if (html.toLowerCase().includes("<script")) {
    throw new Error(`runtime fixture contains JavaScript: ${result.file}`);
  }
}

const completeSelection = selectedSizes.size === manifest.sizes.length
  && selectedModes.size === manifest.modes.length;
await fs.writeFile(
  new URL(completeSelection ? "browser-results.json" : "browser-results-partial.json", experiment),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
