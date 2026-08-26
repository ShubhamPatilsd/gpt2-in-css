import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const outputs = Number.parseInt(process.env.HVAR_DIRECT_OUTPUTS ?? "16", 10);
const inputs = Number.parseInt(process.env.HVAR_DIRECT_INPUTS ?? "3072", 10);
const rounds = Number.parseInt(process.env.HVAR_DIRECT_ROUNDS ?? "5", 10);
const stem = inputs === 3072 ? `n${outputs}` : `n${outputs}-i${inputs}`;
const reference = JSON.parse(await fs.readFile(
  new URL(`../experiments/hvar-raster-direct-projection/${stem}-reference.json`, import.meta.url),
  "utf8",
));

function stats(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
    finite: actual.filter(Number.isFinite).length,
  };
}

async function readVector(page) {
  const box = await page.locator("#bank").boundingBox();
  if (!box) throw new Error("Direct projection bank has no bounding box");
  const png = await page.screenshot({
    animations: "disabled",
    omitBackground: true,
    clip: { x: box.x, y: box.y, width: outputs, height: 1 },
    timeout: 180000,
  });
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: outputs }, (_, index) =>
    (data[index * info.channels] / 255 - reference.surfaceCenter)
      * 2 * reference.outputRanges[index]);
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const page = await browser.newPage({ viewport: { width: Math.max(outputs, 256), height: 500 } });
  const started = performance.now();
  await page.goto(
    `http://127.0.0.1:4178/experiments/hvar-raster-direct-projection/${stem}.html`,
    { waitUntil: "load", timeout: 180000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const initial = await readVector(page);
  const loadAndFirstPaintMilliseconds = performance.now() - started;
  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    const alternate = round % 2 === 0;
    const settings = alternate ? reference.alternateFontSettings : reference.initialFontSettings;
    const expected = alternate ? reference.alternateExpected : reference.initialExpected;
    const mutationStarted = performance.now();
    await page.locator("#bank").evaluate((element, value) => {
      element.style.fontVariationSettings = value;
    }, settings);
    const actual = await readVector(page);
    samples.push({ alternate, milliseconds: performance.now() - mutationStarted, ...stats(actual, expected) });
  }
  const timings = samples.map(({ milliseconds }) => milliseconds).sort((a, b) => a - b);
  report = {
    outputs,
    inputs,
    loadAndFirstPaintMilliseconds,
    initial: stats(initial, reference.initialExpected),
    initialSamples: initial.slice(0, 16).map((actual, index) => ({
      output: reference.selectedOutputs[index],
      actual,
      expected: reference.initialExpected[index],
      range: reference.outputRanges[index],
    })),
    mutationMedianMilliseconds: timings[Math.floor(timings.length / 2)],
    mutationMaximumMilliseconds: timings.at(-1),
    htmlBytes: reference.htmlBytes,
    primitiveCount: await page.locator("filter > *").count(),
    samples,
  };
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL(`../experiments/hvar-raster-direct-projection/${stem}-browser-results.json`, import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
