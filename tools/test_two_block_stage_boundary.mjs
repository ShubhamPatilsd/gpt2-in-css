import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.TWO_BLOCK_BOUNDARY_ROUNDS ?? "7", 10);
const frames = Number.parseInt(process.env.TWO_BLOCK_BOUNDARY_FRAMES ?? "4", 10);
const stem = "view-timeline-two-block-full-exact-b0-global-projection-" +
  "fc-easing-gelu-s513-projection-easing-s257-global-projection";
const stagedStem = `${stem}-manual-stage-boundary`;
const root = new URL("../experiments/gpt2-block-css/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL(`${stem}-reference.json`, root), "utf8"));

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

async function waitFrames(page, count = frames) {
  await page.waitForTimeout(Math.ceil(count * 16.7));
  await page.locator("body").evaluate((element) => element.getBoundingClientRect().width);
}

async function readOutput(page) {
  return page.locator("#two-block-full").evaluate((element, width) => {
    const style = getComputedStyle(element);
    return Array.from({ length: width }, (_value, index) => Number(
      style.getPropertyValue(`--b1-final-${String(index).padStart(3, "0")}`),
    ));
  }, reference.width);
}

async function mutate(page, originalInput, perturbed) {
  await page.locator(".norm1").evaluate((element, values) => {
    if (values.perturbed) element.style.setProperty("--x-000", values.original + 0.125);
    else element.style.removeProperty("--x-000");
  }, { original: originalInput, perturbed });
}

async function benchmarkBaseline(context) {
  const page = await context.newPage();
  page.setDefaultTimeout(180000);
  const loadStarted = performance.now();
  await page.goto(`http://127.0.0.1:4178/experiments/gpt2-block-css/${stem}.html`, {
    waitUntil: "load", timeout: 180000,
  });
  await page.evaluate(() => document.fonts.ready);
  await waitFrames(page);
  const originalInput = await page.locator(".norm1").evaluate((element) => Number(
    getComputedStyle(element).getPropertyValue("--x-000"),
  ));
  const initial = await readOutput(page);
  const samples = [];
  for (let round = 0; round < rounds + 2; round += 1) {
    const perturbed = round % 2 === 0;
    const started = performance.now();
    await mutate(page, originalInput, perturbed);
    await waitFrames(page);
    const output = await readOutput(page);
    samples.push({
      round,
      perturbed,
      milliseconds: performance.now() - started,
      resetError: perturbed ? null : error(output, reference.expected),
    });
  }
  const measured = samples.slice(2);
  const result = {
    loadMilliseconds: performance.now() - loadStarted,
    initialError: error(initial, reference.expected),
    medianMilliseconds: median(measured.map(({ milliseconds }) => milliseconds)),
    minimumMilliseconds: Math.min(...measured.map(({ milliseconds }) => milliseconds)),
    maximumMilliseconds: Math.max(...measured.map(({ milliseconds }) => milliseconds)),
    samples,
  };
  await page.close();
  return result;
}

async function benchmarkStaged(context) {
  const page = await context.newPage();
  page.setDefaultTimeout(180000);
  const loadStarted = performance.now();
  await page.goto(`http://127.0.0.1:4178/experiments/gpt2-block-css/${stagedStem}.html`, {
    waitUntil: "load", timeout: 180000,
  });
  await waitFrames(page);
  const originalInput = await page.locator(".norm1").evaluate((element) => Number(
    getComputedStyle(element).getPropertyValue("--x-000"),
  ));
  const coldBlock0Milliseconds = performance.now() - loadStarted;
  const coldBlock1Started = performance.now();
  await page.locator("#b1-stage-run").evaluate((element) => { element.checked = true; });
  await page.evaluate(() => document.fonts.ready);
  await waitFrames(page);
  const initial = await readOutput(page);
  const coldBlock1Milliseconds = performance.now() - coldBlock1Started;

  const samples = [];
  for (let round = 0; round < rounds + 2; round += 1) {
    const perturbed = round % 2 === 0;
    await page.locator("#b1-stage-run").evaluate((element) => { element.checked = false; });
    await waitFrames(page, 1);
    const block0Started = performance.now();
    await mutate(page, originalInput, perturbed);
    await waitFrames(page);
    await page.locator(".proj-result-5").evaluate((element) => {
      const style = getComputedStyle(element);
      return [style.getPropertyValue("--op0"), element.getBoundingClientRect().width];
    });
    const block0Milliseconds = performance.now() - block0Started;

    const block1Started = performance.now();
    await page.locator("#b1-stage-run").evaluate((element) => { element.checked = true; });
    await waitFrames(page);
    const output = await readOutput(page);
    const block1Milliseconds = performance.now() - block1Started;
    samples.push({
      round,
      perturbed,
      block0Milliseconds,
      block1Milliseconds,
      milliseconds: block0Milliseconds + block1Milliseconds,
      resetError: perturbed ? null : error(output, reference.expected),
    });
  }
  const measured = samples.slice(2);
  const result = {
    coldBlock0Milliseconds,
    coldBlock1Milliseconds,
    initialError: error(initial, reference.expected),
    block0MedianMilliseconds: median(measured.map(({ block0Milliseconds }) => block0Milliseconds)),
    block1MedianMilliseconds: median(measured.map(({ block1Milliseconds }) => block1Milliseconds)),
    medianMilliseconds: median(measured.map(({ milliseconds }) => milliseconds)),
    minimumMilliseconds: Math.min(...measured.map(({ milliseconds }) => milliseconds)),
    maximumMilliseconds: Math.max(...measured.map(({ milliseconds }) => milliseconds)),
    samples,
  };
  await page.close();
  return result;
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 900, height: 240 },
  });
  const baseline = await benchmarkBaseline(context);
  const staged = await benchmarkStaged(context);
  const report = {
    chrome: await browser.version(),
    rounds,
    frames,
    baseline,
    staged,
    stagedSpeedup: baseline.medianMilliseconds / staged.medianMilliseconds,
    stagedDeltaMilliseconds: staged.medianMilliseconds - baseline.medianMilliseconds,
  };
  await fs.writeFile(new URL("two-block-manual-stage-boundary-browser.json", root),
    `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
