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
const rounds = Number.parseInt(process.env.HVAR_RASTER_CHANNEL_ROUNDS ?? "8", 10);

const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/hvar-raster-fc/reference.json", import.meta.url),
  "utf8",
));

function stats(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    finite: actual.filter(Number.isFinite).length,
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
    checksum: actual.reduce((sum, value) => sum + value, 0),
  };
}

async function readCodes(page) {
  const box = await page.locator("#bank").boundingBox();
  if (!box) throw new Error("FC bank has no bounding box");
  const buffer = await page.screenshot({
    animations: "disabled",
    omitBackground: true,
    clip: { x: box.x, y: box.y, width: 1, height: reference.outputWidth },
    timeout: 180000,
  });
  const { data, info } = await sharp(buffer).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: reference.outputWidth }, (_, y) => data[y * info.channels] / 255);
}

function decode(codes) {
  return codes.map((code, index) =>
    reference.perChannelHiddenMin[index]
      + code * (reference.perChannelHiddenMax[index] - reference.perChannelHiddenMin[index]));
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const page = await browser.newPage({ viewport: { width: 300, height: reference.outputWidth } });
  const started = performance.now();
  await page.goto(
    "http://127.0.0.1:4178/experiments/hvar-raster-fc/per-channel.html",
    { waitUntil: "load", timeout: 180000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const initial = decode(await readCodes(page));
  const loadAndFirstPaintMilliseconds = performance.now() - started;
  const samples = [];
  const cases = reference.cases.slice(0, rounds);
  for (let index = 0; index < cases.length; index += 1) {
    const testCase = cases[index];
    const mutationStarted = performance.now();
    await page.locator("#bank").evaluate((element, value) => {
      element.style.fontVariationSettings = value;
    }, testCase.fontSettings);
    const actual = decode(await readCodes(page));
    const widths = await page.locator(".bar").evaluateAll((elements) =>
      [0, 1, 745, 1024, 2048, 3071].map((index) => getComputedStyle(elements[index]).width));
    samples.push({
      index,
      calibration: testCase.calibration,
      milliseconds: performance.now() - mutationStarted,
      ...stats(actual, testCase.expectedHidden),
      widths,
    });
  }
  const timings = samples.map(({ milliseconds }) => milliseconds).sort((a, b) => a - b);
  const calibration = samples.filter((sample) => sample.calibration);
  const heldOut = samples.filter((sample) => !sample.calibration);
  const aggregate = (group) => ({
    cases: group.length,
    meanRmse: group.reduce((sum, sample) => sum + sample.rmse, 0) / group.length,
    worstMaxError: Math.max(...group.map((sample) => sample.maxError)),
  });
  report = {
    rounds: cases.length,
    loadAndFirstPaintMilliseconds,
    initial: stats(initial, reference.cases[0].expectedHidden),
    mutationMedianMilliseconds: timings[Math.floor(timings.length / 2)],
    mutationMaximumMilliseconds: timings.at(-1),
    calibration: aggregate(calibration),
    heldOut: aggregate(heldOut),
    samples,
    elements: await page.locator("*").count(),
  };
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("../experiments/hvar-raster-fc/per-channel-browser-results.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
