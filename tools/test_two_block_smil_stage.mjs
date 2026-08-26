import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const root = new URL("../experiments/gpt2-block-css/", import.meta.url);
const manifest = JSON.parse(await fs.readFile(
  new URL("two-block-smil-stage-manifest.json", root), "utf8",
));
const reference = JSON.parse(await fs.readFile(
  new URL(`${manifest.sourceStem}-reference.json`, root), "utf8",
));
const base = "http://127.0.0.1:4178/experiments/gpt2-block-css";
const rounds = Number(process.env.TWO_BLOCK_SMIL_ROUNDS ?? 1);
const selectedModes = new Set(
  (process.env.TWO_BLOCK_SMIL_MODES ?? manifest.fixtures.map(({ name }) => name).join(","))
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

async function metrics(session) {
  const result = await session.send("Performance.getMetrics");
  return Object.fromEntries(result.metrics.map(({ name, value }) => [name, value]));
}

async function run(browser, fixture) {
  const context = await browser.newContext({ viewport: { width: 800, height: 600 } });
  const page = await context.newPage();
  page.setDefaultTimeout(180000);
  const session = await context.newCDPSession(page);
  await session.send("Performance.enable");
  const before = await metrics(session);
  const started = performance.now();
  await page.goto(`${base}/${fixture.stem}.html`, { waitUntil: "load", timeout: 180000 });
  const loadMilliseconds = performance.now() - started;
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(
    () => getComputedStyle(document.querySelector("#b1-smil-gate")).display !== "none",
    null,
    { timeout: 180000 },
  );
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
  const after = await metrics(session);
  const result = {
    loadMilliseconds,
    gateMilliseconds,
    readyMilliseconds,
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

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH
    ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const report = { chrome: await browser.version(), rounds, results: {} };
try {
  for (const fixture of manifest.fixtures.filter(({ name }) => selectedModes.has(name))) {
    const samples = [];
    for (let round = 0; round < rounds; round += 1) samples.push(await run(browser, fixture));
    report.results[fixture.name] = {
      ...fixture,
      medianReadyMilliseconds: median(samples.map(({ readyMilliseconds }) => readyMilliseconds)),
      medianMaximumError: median(samples.map(({ error: value }) => value.maximum)),
      samples,
    };
  }
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("two-block-smil-stage-results.json", root),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
