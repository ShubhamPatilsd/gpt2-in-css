import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const sharp = require(`${root}/sharp`);
const rounds = Number.parseInt(process.env.GVAR_VECTOR_FC_ROUNDS ?? "8", 10);
const debugResult = process.env.GVAR_VECTOR_FC_DEBUG_RESULT;
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/gvar-vector-fc/reference.json", import.meta.url), "utf8"));

function stats(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  const largest = errors
    .map((error, index) => ({ index, error, actual: actual[index], expected: expected[index] }))
    .sort((a, b) => Math.abs(b.error) - Math.abs(a.error))
    .slice(0, 8);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
    finite: actual.filter(Number.isFinite).length,
    largest,
  };
}

async function readHidden(page) {
  const png = await page.screenshot({
    omitBackground: true,
    clip: { x: 0, y: 0, width: 1, height: reference.outputs },
    timeout: 180000,
  });
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const span = reference.hiddenMax - reference.hiddenMin;
  return Array.from({ length: reference.outputs }, (_, y) =>
    reference.hiddenMin + data[y * info.channels] / 255 * span);
}

async function readCodes(page) {
  const png = await page.screenshot({
    omitBackground: true,
    clip: { x: 0, y: 0, width: 1, height: reference.outputs },
    timeout: 180000,
  });
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: reference.outputs }, (_, y) => data[y * info.channels] / 255);
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
let report;
try {
  const page = await browser.newPage({ viewport: { width: 800, height: reference.outputs } });
  const started = performance.now();
  await page.goto("http://127.0.0.1:4178/experiments/gvar-vector-fc/index.html", {
    waitUntil: "load", timeout: 180000,
  });
  await page.evaluate(() => document.fonts.ready);
  if (debugResult) {
    await page.locator("#fc").evaluate((filter, result) => {
      const primitive = document.createElementNS("http://www.w3.org/2000/svg", "feOffset");
      primitive.setAttribute("in", result);
      primitive.setAttribute("x", "0");
      primitive.setAttribute("y", "0");
      primitive.setAttribute("width", "1");
      primitive.setAttribute("height", "3072");
      filter.append(primitive);
    }, debugResult);
    const codes = await readCodes(page);
    await fs.writeFile(
      new URL(`../experiments/gvar-vector-fc/debug-${debugResult}.json`, import.meta.url),
      `${JSON.stringify(codes)}\n`,
    );
    console.log(JSON.stringify({ debugResult, samples: [1612, 578, 293, 10].map((index) => ({ index, code: codes[index] })) }, null, 2));
    await browser.close();
    process.exit(0);
  }
  const initial = await readHidden(page);
  const loadAndFirstPaintMilliseconds = performance.now() - started;
  const samples = [];
  for (const [index, testCase] of reference.cases.slice(0, rounds).entries()) {
    const mutationStarted = performance.now();
    await page.locator("#bank").evaluate((element, value) => {
      element.style.fontVariationSettings = value;
    }, testCase.fontSettings);
    const actual = await readHidden(page);
    samples.push({
      index,
      calibration: testCase.calibration,
      milliseconds: performance.now() - mutationStarted,
      ...stats(actual, testCase.expectedHidden),
    });
  }
  const timings = samples.map(({ milliseconds }) => milliseconds).sort((a, b) => a - b);
  const aggregate = (group) => ({
    cases: group.length,
    meanRmse: group.reduce((sum, value) => sum + value.rmse, 0) / group.length,
    worstMaxError: Math.max(...group.map((value) => value.maxError)),
  });
  report = {
    loadAndFirstPaintMilliseconds,
    initial: stats(initial, reference.cases[0].expectedHidden),
    mutationMedianMilliseconds: timings[Math.floor(timings.length / 2)],
    mutationMaximumMilliseconds: timings.at(-1),
    calibration: aggregate(samples.filter((value) => value.calibration)),
    heldOut: aggregate(samples.filter((value) => !value.calibration)),
    fontBytes: reference.fontBytes,
    htmlBytes: reference.htmlBytes,
    elements: await page.locator("*").count(),
    samples,
  };
} finally {
  await browser.close();
}
await fs.writeFile(
  new URL("../experiments/gvar-vector-fc/browser-results.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
