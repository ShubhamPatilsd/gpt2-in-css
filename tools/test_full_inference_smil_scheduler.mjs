import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const root = new URL("../experiments/gpt2-block-css/", import.meta.url);
const manifest = JSON.parse(await fs.readFile(
  new URL("full-inference-smil-manifest.json", root), "utf8",
));
const reference = JSON.parse(await fs.readFile(
  new URL(`${manifest.sourceStem}-reference.json`, root), "utf8",
));
const base = "http://127.0.0.1:4178/experiments/gpt2-block-css";
const rounds = Number(process.env.FULL_INFERENCE_SMIL_ROUNDS ?? 1);
const selected = new Set(
  (process.env.FULL_INFERENCE_SMIL_MODES
    ?? manifest.fixtures.map(({ name }) => name).join(",")).split(","),
);

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

async function getMetrics(session) {
  const result = await session.send("Performance.getMetrics");
  return Object.fromEntries(result.metrics.map(({ name, value }) => [name, value]));
}

async function settleHead(page) {
  await page.locator("#fine-stage").evaluate((element) => element.getBoundingClientRect().width);
  await page.evaluate(() => document.fonts.ready);
  for (let pass = 0; pass < 5; pass += 1) {
    await page.locator("#result").evaluate((element) => {
      const style = getComputedStyle(element);
      return [style.getPropertyValue("--group"), element.getBoundingClientRect().width];
    });
    await page.locator("#fine-stage").evaluate((element) => element.getBoundingClientRect().width);
  }
}

async function run(browser, fixture) {
  const context = await browser.newContext({ viewport: { width: 900, height: 240 } });
  const page = await context.newPage();
  page.setDefaultTimeout(240000);
  const session = await context.newCDPSession(page);
  await session.send("Performance.enable");
  const before = await getMetrics(session);
  const started = performance.now();
  await page.goto(`${base}/${fixture.stem}.html`, { waitUntil: "load", timeout: 240000 });
  const loadMilliseconds = performance.now() - started;
  if (fixture.headDelaySeconds !== null) {
    await page.waitForFunction(() => (
      document.querySelector("#head-smil-signal").className.animVal === "ready"
    ), null, { timeout: 240000 });
  }
  const headGateMilliseconds = performance.now() - started;
  await settleHead(page);
  const output = await page.evaluate(() => {
    const coarse = getComputedStyle(document.querySelector("#result"));
    const refined = getComputedStyle(document.querySelector("#refined-result"));
    return {
      coarseWinner: Number(coarse.getPropertyValue("--winner")),
      refinedWinner: Number(refined.getPropertyValue("--refined-winner")),
    };
  });
  const readyMilliseconds = performance.now() - started;
  const after = await getMetrics(session);
  const result = {
    loadMilliseconds,
    headGateMilliseconds,
    readyMilliseconds,
    output,
    correct: output.refinedWinner === reference.denseWinner,
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
const report = { chrome: await browser.version(), rounds, expected: reference.denseWinner, results: {} };
try {
  for (const fixture of manifest.fixtures.filter(({ name }) => selected.has(name))) {
    const samples = [];
    for (let round = 0; round < rounds; round += 1) samples.push(await run(browser, fixture));
    report.results[fixture.name] = {
      ...fixture,
      medians: Object.fromEntries([
        "loadMilliseconds", "headGateMilliseconds", "readyMilliseconds", "layoutCount",
        "layoutDurationMilliseconds", "recalcStyleCount",
        "recalcStyleDurationMilliseconds", "taskDurationMilliseconds",
      ].map((key) => [key, median(samples.map((sample) => sample[key]))])),
      allCorrect: samples.every(({ correct }) => correct),
      samples,
    };
  }
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("full-inference-smil-results.json", root),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
