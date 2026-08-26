import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const stem = "view-timeline-two-block-with-selective-gpt2-output-head-" +
  "internally-staged-event-scheduled";
const root = new URL("../experiments/gpt2-block-css/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL(`${stem}-reference.json`, root), "utf8"));
const url = `http://127.0.0.1:4178/experiments/gpt2-block-css/${stem}.html`;
const rounds = Number(process.env.FULL_INFERENCE_EVENT_ROUNDS ?? 1);
const signalTimeout = Number(process.env.FULL_INFERENCE_EVENT_SIGNAL_TIMEOUT ?? 240000);

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

async function getMetrics(session) {
  const result = await session.send("Performance.getMetrics");
  return Object.fromEntries(result.metrics.map(({ name, value }) => [name, value]));
}

async function run(browser) {
  const context = await browser.newContext({ viewport: { width: 900, height: 240 } });
  const page = await context.newPage();
  page.setDefaultTimeout(240000);
  const session = await context.newCDPSession(page);
  await session.send("Performance.enable");
  const before = await getMetrics(session);
  const started = performance.now();
  await page.goto(url, { waitUntil: "load", timeout: 240000 });
  const loadMilliseconds = performance.now() - started;
  const milestones = {};
  for (const [name, id] of [
    ["b1", "b1-smil-signal"],
    ["head", "head-smil-signal"],
    ["fine", "fine-smil-signal"],
    ["near", "near-smil-signal"],
    ["dither", "dither-smil-signal"],
  ]) {
    try {
      await page.waitForFunction((signalId) => (
        document.querySelector(`#${signalId}`).className.animVal === "ready"
      ), id, { timeout: signalTimeout });
    } catch (error) {
      const state = await page.evaluate(() => Object.fromEntries([
        "b1-smil-signal", "head-smil-signal", "fine-smil-signal",
        "near-smil-signal", "dither-smil-signal",
      ].map((signalId) => {
        const element = document.querySelector(`#${signalId}`);
        return [signalId, element?.className?.animVal ?? null];
      })));
      throw new Error(`timed out waiting for ${name}: ${JSON.stringify(state)}`, { cause: error });
    }
    milestones[`${name}Milliseconds`] = performance.now() - started;
    console.error(`reached ${name} at ${milestones[`${name}Milliseconds`].toFixed(1)}ms`);
  }
  await page.evaluate(() => document.fonts.ready);
  for (let pass = 0; pass < 6; pass += 1) {
    await page.locator("#result").evaluate((element) => element.getBoundingClientRect().width);
    await page.locator("#fine-result").evaluate((element) => element.getBoundingClientRect().width);
    await page.locator("#near-result").evaluate((element) => element.getBoundingClientRect().width);
    await page.locator("#refined-result").evaluate((element) => element.getBoundingClientRect().width);
  }
  const output = await page.evaluate(() => ({
    coarseWinner: Number(getComputedStyle(document.querySelector("#result"))
      .getPropertyValue("--winner")),
    nearLow: Number(getComputedStyle(document.querySelector("#near-result"))
      .getPropertyValue("--near-low")),
    nearHigh: Number(getComputedStyle(document.querySelector("#near-result"))
      .getPropertyValue("--near-high")),
    refinedWinner: Number(getComputedStyle(document.querySelector("#refined-result"))
      .getPropertyValue("--refined-winner")),
  }));
  const readyMilliseconds = performance.now() - started;
  const after = await getMetrics(session);
  const result = {
    loadMilliseconds,
    ...milestones,
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
const chrome = await browser.version();
const samples = [];
try {
  for (let round = 0; round < rounds; round += 1) samples.push(await run(browser));
} finally {
  await browser.close();
}
const numericKeys = [
  "loadMilliseconds", "b1Milliseconds", "headMilliseconds", "fineMilliseconds",
  "nearMilliseconds", "ditherMilliseconds", "readyMilliseconds", "layoutCount",
  "layoutDurationMilliseconds", "recalcStyleCount", "recalcStyleDurationMilliseconds",
  "taskDurationMilliseconds",
];
const report = {
  chrome,
  rounds,
  expected: reference.denseWinner,
  allCorrect: samples.every(({ correct }) => correct),
  medians: Object.fromEntries(numericKeys.map(
    (key) => [key, median(samples.map((sample) => sample[key]))],
  )),
  samples,
};
await fs.writeFile(
  new URL("full-inference-event-scheduler-results.json", root),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
