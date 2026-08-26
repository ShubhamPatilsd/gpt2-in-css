import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.GPT2_CASCADE_ROUNDS ?? "3", 10);
const settlePasses = Number.parseInt(process.env.GPT2_CASCADE_SETTLE_PASSES ?? "2", 10);
const cascadeDirectory = process.env.GPT2_CASCADE_DIR ??
  "gpt2-hvar-grid-output-head-cascade";
const root = new URL(`../experiments/${cascadeDirectory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

async function settleCascade(page, count) {
  // Force the newly selected fine group to request its font faces before
  // waiting. This is effectively free for monolithic fonts and captures the
  // one-time group load for the lazy subfont variant.
  await page.locator("#fine-stage").evaluate((element) =>
    element.getBoundingClientRect().width);
  await page.evaluate(() => document.fonts.ready);
  for (let pass = 0; pass < count; pass += 1) {
    await page.locator("#result").evaluate((element) => {
      const style = getComputedStyle(element);
      return [style.getPropertyValue("--group"), element.getBoundingClientRect().width];
    });
    await page.locator("#fine-stage").evaluate((element) =>
      element.getBoundingClientRect().width);
  }
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 800, height: 200 },
  });
  const page = await context.newPage();
  const started = performance.now();
  await page.goto(
    `http://127.0.0.1:4178/experiments/${cascadeDirectory}/index.html`,
    { waitUntil: "load", timeout: 240000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const loadMilliseconds = performance.now() - started;
  const read = () => page.evaluate(() => {
    const coarse = getComputedStyle(document.querySelector("#result"));
    const finalElement = document.querySelector("#refined-result") ??
      document.querySelector("#fine-result");
    const fine = getComputedStyle(finalElement);
    const nearElement = document.querySelector("#near-result");
    const near = nearElement ? getComputedStyle(nearElement) : null;
    return {
      coarseWinner: Number(coarse.getPropertyValue("--winner")),
      coarseGroup: Number(coarse.getPropertyValue("--group")),
      refinedWinner: Number(fine.getPropertyValue("--refined-winner")),
      fineLocal: Number(fine.getPropertyValue("--fine-local")),
      fineWidth: finalElement.getBoundingClientRect().width,
      nearHigh: near ? Number(near.getPropertyValue("--near-high")) : null,
      nearLow: near ? Number(near.getPropertyValue("--near-low")) : null,
    };
  });
  const initial = await read();
  const samples = [];
  for (let round = 0; round < rounds + 2; round += 1) {
    const query = (round + 1) % 2;
    const before = performance.now();
    await page.locator(`#q${query}`).evaluate((element) => { element.checked = true; });
    await settleCascade(page, settlePasses);
    const output = await read();
    samples.push({
      round,
      query,
      milliseconds: performance.now() - before,
      output,
      expected: reference.refinedWinners[query],
      dense: reference.denseWinners[query],
    });
  }
  const validation = [];
  for (let fixture = 0; fixture < reference.validation.hiddenVectors.length; fixture += 1) {
    const before = performance.now();
    await page.evaluate((values) => {
      for (const selector of ["#model", "#fine-stage"]) {
        const element = document.querySelector(selector);
        values.hidden.forEach((value, dimension) => {
          element.style.setProperty(`--h${dimension}`, String(value));
        });
        element.style.setProperty(
          "--score-offset",
          `${-values.floor * 256 * 4}px`,
        );
      }
    }, {
      hidden: reference.validation.hiddenVectors[fixture],
      floor: reference.validation.scoreFloors[fixture],
    });
    await settleCascade(page, settlePasses);
    const output = await read();
    validation.push({
      fixture,
      inputToken: reference.validation.tokenIds[fixture],
      milliseconds: performance.now() - before,
      output,
      expected: reference.validation.refinedWinners[fixture],
      dense: reference.validation.denseWinners[fixture],
    });
  }
  const measured = samples.slice(2);
  const report = {
    chrome: await browser.version(),
    cascadeDirectory,
    rounds,
    settlePasses,
    loadMilliseconds,
    initial,
    initialCorrect: initial.refinedWinner === reference.refinedWinners[0],
    initialDenseCorrect: initial.refinedWinner === reference.denseWinners[0],
    settledMutationMedianMilliseconds: median(
      measured.map(({ milliseconds }) => milliseconds),
    ),
    settledMutationMinimumMilliseconds: Math.min(
      ...measured.map(({ milliseconds }) => milliseconds),
    ),
    settledMutationMaximumMilliseconds: Math.max(
      ...measured.map(({ milliseconds }) => milliseconds),
    ),
    correct: samples.every(({ output, expected }) => output.refinedWinner === expected) &&
      validation.every(({ output, expected }) => output.refinedWinner === expected),
    denseCorrect: samples.every(({ output, dense }) => output.refinedWinner === dense) &&
      validation.every(({ output, dense }) => output.refinedWinner === dense),
    validationMutationMedianMilliseconds: median(
      validation.map(({ milliseconds }) => milliseconds),
    ),
    elements: await page.locator("*").count(),
    totalRuntimeBytes: reference.totalRuntimeBytes,
    samples,
    validation,
  };
  await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
