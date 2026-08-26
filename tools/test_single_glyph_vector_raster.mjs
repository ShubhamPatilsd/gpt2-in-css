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
const inputs = Number.parseInt(process.env.SINGLE_GLYPH_INPUTS ?? "64", 10);
const outputs = Number.parseInt(process.env.SINGLE_GLYPH_OUTPUTS ?? "64", 10);
const rounds = Number.parseInt(process.env.SINGLE_GLYPH_ROUNDS ?? "7", 10);
const stem = `i${inputs}-o${outputs}`;
const reference = JSON.parse(await fs.readFile(
  new URL(`../experiments/single-glyph-vector-raster/${stem}-reference.json`, import.meta.url),
  "utf8",
));

function mapped(value) {
  return value <= 0.5 ? value * 0.5 : 0.25 + (value - 0.5) * 1.5;
}

function stats(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maximumError: Math.max(...errors.map(Math.abs)),
  };
}

function correlation(left, right) {
  const leftMean = left.reduce((sum, value) => sum + value, 0) / left.length;
  const rightMean = right.reduce((sum, value) => sum + value, 0) / right.length;
  let numerator = 0;
  let leftSquare = 0;
  let rightSquare = 0;
  for (let index = 0; index < left.length; index += 1) {
    const a = left[index] - leftMean;
    const b = right[index] - rightMean;
    numerator += a * b;
    leftSquare += a * a;
    rightSquare += b * b;
  }
  return numerator / Math.sqrt(leftSquare * rightSquare);
}

async function read(page) {
  const png = await page.locator("#surface").screenshot({ omitBackground: true, timeout: 180000 });
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const channel = (x, y) => data[(y * info.width + x) * info.channels] / 255;
  return {
    vector: Array.from({ length: outputs }, (_, y) => channel(0, y)),
    mean: channel(1, 0),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const page = await browser.newPage({ viewport: { width: 20, height: Math.max(outputs, 20) } });
  const loadStarted = performance.now();
  await page.goto(
    `http://127.0.0.1:4178/experiments/single-glyph-vector-raster/${stem}.html`,
    { waitUntil: "load", timeout: 180000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const initial = await read(page);
  const loadAndFirstPaintMilliseconds = performance.now() - loadStarted;
  // Font coordinates grow upward; screen row zero is the last COLR layer.
  const initialExpected = [...reference.initialExpected].reverse().map(mapped);
  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    const alternate = round % 2 === 0;
    const settings = alternate ? reference.alternateSettings : reference.initialSettings;
    const expected = [...(alternate ? reference.alternateExpected : reference.initialExpected)]
      .reverse().map(mapped);
    const started = performance.now();
    await page.locator("#vector").evaluate((element, value) => {
      element.style.fontVariationSettings = value;
    }, settings);
    const actual = await read(page);
    const actualDelta = actual.vector.map((value, index) => value - initial.vector[index]);
    const expectedDelta = expected.map((value, index) => value - initialExpected[index]);
    samples.push({
      round,
      alternate,
      milliseconds: performance.now() - started,
      vector: stats(actual.vector, expected),
      meanActual: actual.mean,
      meanExpected: expected.slice(0, reference.reduceCount).reduce((sum, value) => sum + value, 0)
        / reference.reduceCount,
      meanError: actual.mean - expected.slice(0, reference.reduceCount)
        .reduce((sum, value) => sum + value, 0) / reference.reduceCount,
      changedPixelsFromInitial: actualDelta.filter((value) => value !== 0).length,
      deltaCorrelationWithExpected: alternate ? correlation(actualDelta, expectedDelta) : 1,
    });
  }
  const timings = samples.slice(Math.min(2, samples.length)).map((sample) => sample.milliseconds)
    .sort((a, b) => a - b);
  const cachedReadTimings = [];
  for (let round = 0; round < 5; round += 1) {
    const started = performance.now();
    await read(page);
    cachedReadTimings.push(performance.now() - started);
  }
  cachedReadTimings.sort((a, b) => a - b);
  const cachedReadMedianMilliseconds = cachedReadTimings[Math.floor(cachedReadTimings.length / 2)];
  report = {
    chrome: await browser.version(),
    inputs,
    outputs,
    runtimeContainsJavaScript: false,
    loadAndFirstPaintMilliseconds,
    initial: {
      vector: stats(initial.vector, initialExpected),
      meanActual: initial.mean,
      meanExpected: initialExpected.slice(0, reference.reduceCount)
        .reduce((sum, value) => sum + value, 0) / reference.reduceCount,
    },
    warmMutationMedianMilliseconds: timings[Math.floor(timings.length / 2)],
    warmMutationMinimumMilliseconds: Math.min(...timings),
    warmMutationMaximumMilliseconds: Math.max(...timings),
    cachedRasterReadMedianMilliseconds: cachedReadMedianMilliseconds,
    estimatedMutationAndRepaintMilliseconds:
      timings[Math.floor(timings.length / 2)] - cachedReadMedianMilliseconds,
    fontBytes: reference.fontBytes,
    htmlBytes: reference.htmlBytes,
    paintLayers: reference.paintLayers,
    elements: await page.locator("*").count(),
    samples,
  };
  await page.close();
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL(`../experiments/single-glyph-vector-raster/${stem}-browser-results.json`, import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
