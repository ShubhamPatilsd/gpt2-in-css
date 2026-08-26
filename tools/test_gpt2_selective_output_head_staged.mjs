import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.GPT2_STAGED_HEAD_ROUNDS ?? "5", 10);
const settlePasses = Number.parseInt(process.env.GPT2_STAGED_HEAD_SETTLE_PASSES ?? "2", 10);
const sourceName = process.env.GPT2_STAGED_HEAD_SOURCE ??
  "gpt2-hvar-grid-output-head-cascade-near-dither7";
const directory = process.env.GPT2_STAGED_HEAD_DIR ?? `${sourceName}-staged`;
const sourceRoot = new URL(`../experiments/${sourceName}/`, import.meta.url);
const outputRoot = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", sourceRoot), "utf8"));

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

async function flush(page, selector) {
  return page.locator(selector).evaluate((element) => {
    const style = getComputedStyle(element);
    return [element.getBoundingClientRect().width, style.length];
  });
}

async function settle(page, ...selectors) {
  for (let pass = 0; pass < settlePasses; pass += 1) {
    for (const selector of selectors) await flush(page, selector);
  }
}

async function setGate(page, id, checked) {
  await page.locator(id).evaluate((element, value) => { element.checked = value; }, checked);
}

async function read(page) {
  return page.evaluate(() => {
    const coarse = getComputedStyle(document.querySelector("#result"));
    const fine = getComputedStyle(document.querySelector("#fine-result"));
    const near = getComputedStyle(document.querySelector("#near-result"));
    const refined = getComputedStyle(document.querySelector("#refined-result"));
    return {
      coarseWinner: Number(coarse.getPropertyValue("--winner")),
      coarseGroup: Number(coarse.getPropertyValue("--group")),
      fineWinner: Number(fine.getPropertyValue("--refined-winner")),
      nearLow: Number(near.getPropertyValue("--near-low")),
      nearHigh: Number(near.getPropertyValue("--near-high")),
      refinedWinner: Number(refined.getPropertyValue("--refined-winner")),
    };
  });
}

async function runStages(page) {
  const coarseStarted = performance.now();
  await settle(page, "#result");
  const coarseMilliseconds = performance.now() - coarseStarted;

  const fineStarted = performance.now();
  await setGate(page, "#fine-stage-run", true);
  await page.evaluate(() => document.fonts.ready);
  await settle(page, "#fine-stage", "#fine-result");
  const fineMilliseconds = performance.now() - fineStarted;

  const nearStarted = performance.now();
  await setGate(page, "#near-stage-run", true);
  await settle(page, "#near-result");
  const nearMilliseconds = performance.now() - nearStarted;

  const ditherStarted = performance.now();
  await setGate(page, "#dither-stage-run", true);
  await settle(page, "#dither-stage", "#refined-result");
  const ditherMilliseconds = performance.now() - ditherStarted;
  return {
    coarseMilliseconds,
    fineMilliseconds,
    nearMilliseconds,
    ditherMilliseconds,
    milliseconds: coarseMilliseconds + fineMilliseconds + nearMilliseconds + ditherMilliseconds,
    output: await read(page),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 800, height: 200 },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(240000);
  const coldStarted = performance.now();
  await page.goto(`http://127.0.0.1:4178/experiments/${directory}/index.html`, {
    waitUntil: "load", timeout: 240000,
  });
  await page.evaluate(() => document.fonts.ready);
  const cold = await runStages(page);
  const coldMilliseconds = performance.now() - coldStarted;

  const samples = [];
  for (let round = 0; round < rounds + 2; round += 1) {
    await setGate(page, "#dither-stage-run", false);
    await setGate(page, "#near-stage-run", false);
    await setGate(page, "#fine-stage-run", false);
    await settle(page, "#dither-stage", "#near-result", "#fine-stage", "body");
    const query = (round + 1) % 2;
    await page.locator(`#q${query}`).evaluate((element) => { element.checked = true; });
    const sample = await runStages(page);
    samples.push({
      round,
      query,
      ...sample,
      expected: reference.refinedWinners[query],
      dense: reference.denseWinners[query],
    });
  }
  const measured = samples.slice(2);
  const report = {
    chrome: await browser.version(),
    rounds,
    settlePasses,
    coldMilliseconds,
    cold,
    correct: cold.output.refinedWinner === reference.refinedWinners[0] &&
      samples.every(({ output, expected }) => output.refinedWinner === expected),
    denseCorrect: cold.output.refinedWinner === reference.denseWinners[0] &&
      samples.every(({ output, dense }) => output.refinedWinner === dense),
    medianMilliseconds: median(measured.map(({ milliseconds }) => milliseconds)),
    coarseMedianMilliseconds: median(measured.map(({ coarseMilliseconds }) => coarseMilliseconds)),
    fineMedianMilliseconds: median(measured.map(({ fineMilliseconds }) => fineMilliseconds)),
    nearMedianMilliseconds: median(measured.map(({ nearMilliseconds }) => nearMilliseconds)),
    ditherMedianMilliseconds: median(measured.map(({ ditherMilliseconds }) => ditherMilliseconds)),
    minimumMilliseconds: Math.min(...measured.map(({ milliseconds }) => milliseconds)),
    maximumMilliseconds: Math.max(...measured.map(({ milliseconds }) => milliseconds)),
    elements: await page.locator("*").count(),
    samples,
  };
  await fs.writeFile(new URL("browser-results.json", outputRoot), `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
