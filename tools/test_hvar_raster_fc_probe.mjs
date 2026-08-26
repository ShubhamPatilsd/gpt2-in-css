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
const rounds = Number.parseInt(process.env.HVAR_RASTER_FC_ROUNDS ?? "7", 10);

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

async function readVector(page) {
  const box = await page.locator("#bank").boundingBox();
  if (!box) throw new Error("FC bank has no bounding box");
  const buffer = await page.screenshot({
    animations: "disabled",
    omitBackground: true,
    clip: { x: box.x, y: box.y, width: 1, height: reference.outputWidth },
    timeout: 180000,
  });
  const { data, info } = await sharp(buffer).raw().toBuffer({ resolveWithObject: true });
  const span = reference.hiddenMax - reference.hiddenMin;
  return Array.from({ length: reference.outputWidth }, (_, y) =>
    reference.hiddenMin + (data[y * info.channels] / 255) * span);
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const page = await browser.newPage({ viewport: { width: 300, height: reference.outputWidth } });
  const started = performance.now();
  await page.goto(
    "http://127.0.0.1:4178/experiments/hvar-raster-fc/index.html",
    { waitUntil: "load", timeout: 180000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const initial = await readVector(page);
  const loadAndFirstPaintMilliseconds = performance.now() - started;
  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    const alternate = round % 2 === 0;
    const settings = alternate
      ? reference.alternateFontSettings
      : reference.initialFontSettings;
    const expected = alternate
      ? reference.alternateHidden
      : reference.initialHidden;
    const mutationStarted = performance.now();
    await page.locator("#bank").evaluate((element, value) => {
      element.style.fontVariationSettings = value;
    }, settings);
    const actual = await readVector(page);
    samples.push({
      alternate,
      milliseconds: performance.now() - mutationStarted,
      ...stats(actual, expected),
    });
  }
  const timings = samples.map(({ milliseconds }) => milliseconds).sort((a, b) => a - b);
  report = {
    rounds,
    loadAndFirstPaintMilliseconds,
    initial: stats(initial, reference.initialHidden),
    mutationMedianMilliseconds: timings[Math.floor(timings.length / 2)],
    mutationMaximumMilliseconds: timings.at(-1),
    samples,
    elements: await page.locator("*").count(),
  };
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("../experiments/hvar-raster-fc/browser-results.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
