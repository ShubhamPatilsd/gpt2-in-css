import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.TWO_BLOCK_SELECTIVE_ROUNDS ?? "3", 10);
const blockFrames = Number.parseInt(process.env.TWO_BLOCK_SELECTIVE_BLOCK_FRAMES ?? "7", 10);
const settlePasses = Number.parseInt(process.env.TWO_BLOCK_SELECTIVE_SETTLE_PASSES ?? "5", 10);
const staged = process.env.TWO_BLOCK_SELECTIVE_STAGED !== "0";
const internalStaging = process.env.TWO_BLOCK_SELECTIVE_INTERNAL_STAGING === "1";
const stem = "view-timeline-two-block-with-selective-gpt2-output-head" +
  (internalStaging ? "-internally-staged" : "");
const referenceUrl = new URL(`../experiments/gpt2-block-css/${stem}-reference.json`, import.meta.url);
const reference = JSON.parse(await fs.readFile(referenceUrl, "utf8"));

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function vectorError(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maximum: Math.max(...errors.map(Math.abs)),
  };
}

async function waitFrames(page, count) {
  // The document has JavaScript disabled. Keep time control in the external
  // harness, then force a lifecycle update with a geometry read.
  await page.waitForTimeout(Math.ceil(count * 16.7));
  await page.locator("body").evaluate((element) => element.getBoundingClientRect().width);
}

async function settleHead(page) {
  if (internalStaging) {
    const settle = async (...selectors) => {
      for (let pass = 0; pass < 2; pass += 1) {
        for (const selector of selectors) {
          await page.locator(selector).evaluate((element) => {
            const style = getComputedStyle(element);
            return [element.getBoundingClientRect().width, style.length];
          });
        }
      }
    };
    await settle("#result");
    await page.locator("#fine-stage-run").evaluate((element) => { element.checked = true; });
    await page.evaluate(() => document.fonts.ready);
    await settle("#fine-stage", "#fine-result");
    await page.locator("#near-stage-run").evaluate((element) => { element.checked = true; });
    await settle("#near-result");
    await page.locator("#dither-stage-run").evaluate((element) => { element.checked = true; });
    await settle("#dither-stage", "#refined-result");
    return;
  }
  await page.locator("#fine-stage").evaluate((element) =>
    element.getBoundingClientRect().width);
  await page.evaluate(() => document.fonts.ready);
  for (let pass = 0; pass < settlePasses; pass += 1) {
    await page.locator("#result").evaluate((element) => {
      const style = getComputedStyle(element);
      return [style.getPropertyValue("--group"), element.getBoundingClientRect().width];
    });
    await page.locator("#fine-stage").evaluate((element) =>
      element.getBoundingClientRect().width);
  }
}

async function readOutput(page) {
  return page.evaluate(() => {
    const coarse = getComputedStyle(document.querySelector("#result"));
    const near = getComputedStyle(document.querySelector("#near-result"));
    const refined = getComputedStyle(document.querySelector("#refined-result"));
    return {
      coarseWinner: Number(coarse.getPropertyValue("--winner")),
      coarseGroup: Number(coarse.getPropertyValue("--group")),
      nearLow: Number(near.getPropertyValue("--near-low")),
      nearHigh: Number(near.getPropertyValue("--near-high")),
      refinedWinner: Number(refined.getPropertyValue("--refined-winner")),
    };
  });
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 900, height: 240 },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(240000);
  const loadStarted = performance.now();
  await page.goto(
    `http://127.0.0.1:4178/experiments/gpt2-block-css/${stem}.html`,
    { waitUntil: "load", timeout: 240000 },
  );
  await waitFrames(page, blockFrames);
  const blockOnlyLoadMilliseconds = performance.now() - loadStarted;

  const actualHidden = await page.locator("#two-block-full").evaluate((element, width) => {
    const style = getComputedStyle(element);
    return Array.from({ length: width }, (_value, index) =>
      Number(style.getPropertyValue(`--h${index}`)));
  }, reference.width);
  const originalInput = await page.locator(".norm1").evaluate((element) => Number(
    getComputedStyle(element).getPropertyValue("--x-000"),
  ));

  const coldHeadStarted = performance.now();
  await page.locator("#selective-head-run").evaluate((element) => { element.checked = true; });
  await settleHead(page);
  const initial = await readOutput(page);
  const coldHeadMilliseconds = performance.now() - coldHeadStarted;

  const samples = [];
  for (let round = 0; round < rounds + 2; round += 1) {
    const perturbed = round % 2 === 0;
    if (staged) {
      await page.locator("#selective-head-run").evaluate((element) => { element.checked = false; });
      if (internalStaging) {
        for (const selector of ["#dither-stage-run", "#near-stage-run", "#fine-stage-run"]) {
          await page.locator(selector).evaluate((element) => { element.checked = false; });
        }
      }
      await waitFrames(page, 1);
    }
    const totalStarted = performance.now();
    const blockStarted = performance.now();
    await page.locator(".norm1").evaluate((element, values) => {
      if (values.perturbed) element.style.setProperty("--x-000", values.input + 0.125);
      else element.style.removeProperty("--x-000");
    }, { perturbed, input: originalInput });
    await waitFrames(page, blockFrames);
    const blockMilliseconds = performance.now() - blockStarted;

    const headStarted = performance.now();
    if (staged) {
      await page.locator("#selective-head-run").evaluate((element) => { element.checked = true; });
    }
    await settleHead(page);
    const output = await readOutput(page);
    const headMilliseconds = performance.now() - headStarted;
    samples.push({
      round,
      perturbed,
      blockMilliseconds,
      headMilliseconds,
      totalMilliseconds: performance.now() - totalStarted,
      output,
      resetCorrect: perturbed ? null : output.refinedWinner === reference.denseWinner,
    });
  }
  const measured = samples.slice(2);
  const resetSamples = measured.filter(({ perturbed }) => !perturbed);
  const report = {
    chrome: await browser.version(),
    rounds,
    staged,
    internalStaging,
    blockFrames,
    settlePasses,
    blockOnlyLoadMilliseconds,
    coldHeadMilliseconds,
    initial,
    expectedDenseWinner: reference.denseWinner,
    initialDenseCorrect: initial.refinedWinner === reference.denseWinner,
    hiddenError: vectorError(actualHidden, reference.finalHidden),
    blockMedianMilliseconds: median(measured.map(({ blockMilliseconds }) => blockMilliseconds)),
    headMedianMilliseconds: median(measured.map(({ headMilliseconds }) => headMilliseconds)),
    endToEndMedianMilliseconds: median(measured.map(({ totalMilliseconds }) => totalMilliseconds)),
    endToEndMinimumMilliseconds: Math.min(...measured.map(({ totalMilliseconds }) => totalMilliseconds)),
    endToEndMaximumMilliseconds: Math.max(...measured.map(({ totalMilliseconds }) => totalMilliseconds)),
    resetCorrect: resetSamples.length > 0 && resetSamples.every(({ resetCorrect }) => resetCorrect),
    elements: await page.locator("*").count(),
    runtimeContainsJavaScript: await page.locator("script").count() > 0,
    samples,
  };
  await fs.writeFile(
    new URL(
      `../experiments/gpt2-block-css/${stem}-${staged ? "staged" : "connected"}-browser.json`,
      import.meta.url,
    ),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
