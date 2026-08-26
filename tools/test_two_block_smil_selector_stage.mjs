import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const root = new URL("../experiments/gpt2-block-css/", import.meta.url);
const manifest = JSON.parse(await fs.readFile(
  new URL("two-block-smil-selector-manifest.json", root), "utf8",
));
const reference = JSON.parse(await fs.readFile(
  new URL(`${manifest.sourceStem}-reference.json`, root), "utf8",
));
const base = "http://127.0.0.1:4178/experiments/gpt2-block-css";
const rounds = Number(process.env.TWO_BLOCK_SMIL_SELECTOR_ROUNDS ?? 1);
const names = new Set(
  (process.env.TWO_BLOCK_SMIL_SELECTOR_MODES
    ?? ["control", ...manifest.fixtures.map(({ name }) => name)].join(","))
    .split(","),
);

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function error(actual, expected) {
  const delta = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(delta.reduce((sum, value) => sum + value * value, 0) / delta.length),
    maximum: Math.max(...delta.map(Math.abs)),
  };
}

async function getMetrics(session) {
  const result = await session.send("Performance.getMetrics");
  return Object.fromEntries(result.metrics.map(({ name, value }) => [name, value]));
}

async function run(browser, fixture) {
  const context = await browser.newContext({ viewport: { width: 800, height: 600 } });
  const page = await context.newPage();
  page.setDefaultTimeout(180000);
  const session = await context.newCDPSession(page);
  await session.send("Performance.enable");
  const before = await getMetrics(session);
  const started = performance.now();
  await page.goto(`${base}/${fixture.stem}.html`, { waitUntil: "load", timeout: 180000 });
  const loadMilliseconds = performance.now() - started;
  await page.evaluate(() => document.fonts.ready);
  if (fixture.name !== "control") {
    await page.waitForFunction(() => {
      const style = getComputedStyle(document.querySelector(".b1-norm"));
      return style.display !== "none" && style.contentVisibility !== "hidden";
    }, null, { timeout: 180000 });
  }
  const gateMilliseconds = performance.now() - started;
  await page.evaluate(async () => {
    for (let index = 0; index < 8; index += 1) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
      document.querySelector("#two-block-full").getBoundingClientRect();
    }
  });
  const actual = await page.locator("#two-block-full").evaluate((element, width) => {
    const style = getComputedStyle(element);
    return Array.from({ length: width }, (_value, index) => Number(
      style.getPropertyValue(`--b1-final-${String(index).padStart(3, "0")}`),
    ));
  }, reference.width);
  const readyMilliseconds = performance.now() - started;
  const after = await getMetrics(session);
  const signal = fixture.name === "control" ? null : await page.evaluate(() => ({
    base: document.querySelector("#b1-smil-signal").className.baseVal,
    animated: document.querySelector("#b1-smil-signal").className.animVal,
  }));
  const result = {
    loadMilliseconds,
    gateMilliseconds,
    readyMilliseconds,
    signal,
    error: error(actual, reference.expected),
    layoutCount: (after.LayoutCount ?? 0) - (before.LayoutCount ?? 0),
    layoutDurationMilliseconds: ((after.LayoutDuration ?? 0) - (before.LayoutDuration ?? 0)) * 1000,
    recalcStyleCount: (after.RecalcStyleCount ?? 0) - (before.RecalcStyleCount ?? 0),
    recalcStyleDurationMilliseconds:
      ((after.RecalcStyleDuration ?? 0) - (before.RecalcStyleDuration ?? 0)) * 1000,
    taskDurationMilliseconds: ((after.TaskDuration ?? 0) - (before.TaskDuration ?? 0)) * 1000,
  };
  await context.close();
  return result;
}

const fixtures = [
  { name: "control", stem: manifest.sourceStem, gate: "none", delaySeconds: null },
  ...manifest.fixtures,
].filter(({ name }) => names.has(name));
const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH
    ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const report = { chrome: await browser.version(), rounds, results: {} };
try {
  for (const fixture of fixtures) {
    const samples = [];
    for (let round = 0; round < rounds; round += 1) samples.push(await run(browser, fixture));
    report.results[fixture.name] = {
      ...fixture,
      medians: Object.fromEntries([
        "loadMilliseconds", "gateMilliseconds", "readyMilliseconds", "layoutCount",
        "layoutDurationMilliseconds", "recalcStyleCount",
        "recalcStyleDurationMilliseconds", "taskDurationMilliseconds",
      ].map((key) => [key, median(samples.map((sample) => sample[key]))])),
      medianMaximumError: median(samples.map(({ error: value }) => value.maximum)),
      samples,
    };
  }
} finally {
  await browser.close();
}

for (const result of Object.values(report.results)) {
  if (result.name !== "control") {
    for (const sample of result.samples) {
      if (sample.signal.animated !== "ready" || sample.signal.base !== "") {
        throw new Error(`SMIL class signal did not animate: ${JSON.stringify(result)}`);
      }
    }
  }
}

await fs.writeFile(
  new URL(
    fixtures.length === manifest.fixtures.length + 1
      ? "two-block-smil-selector-results.json"
      : "two-block-smil-selector-results-partial.json",
    root,
  ),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
