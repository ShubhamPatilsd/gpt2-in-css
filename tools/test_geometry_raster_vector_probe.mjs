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
const rounds = Number.parseInt(process.env.GEOMETRY_RASTER_ROUNDS ?? "7", 10);

const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/geometry-raster-vector/reference.json", import.meta.url),
  "utf8",
));

function stats(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
    nonzero: actual.filter((value) => value > 0).length,
    minimum: Math.min(...actual),
    maximum: Math.max(...actual),
    firstEight: actual.slice(0, 8),
  };
}

async function readStrip(page, count) {
  const box = await page.locator("#bank").boundingBox();
  if (!box) throw new Error("vector bank has no bounding box");
  const buffer = await page.screenshot({
    animations: "disabled",
    omitBackground: true,
    clip: { x: box.x, y: box.y, width: 1, height: count },
    timeout: 180000,
  });
  const { data, info } = await sharp(buffer).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: count }, (_, y) => data[y * info.channels] / 255);
}

const browser = await chromium.launch({ executablePath, headless: true });
const results = [];
try {
  for (const count of reference.counts) {
    const page = await browser.newPage({ viewport: { width: 300, height: count } });
    const started = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/geometry-raster-vector/n${count}.html`,
      { waitUntil: "load", timeout: 180000 },
    );
    const initial = await readStrip(page, count);
    const loadAndFirstPaintMilliseconds = performance.now() - started;
    const source = reference.pages[String(count)].values;
    const samples = [];
    for (let round = 0; round < rounds; round += 1) {
      const gain = round % 2 === 0 ? 0.8 : 1;
      const expected = source.map((value) => value * gain);
      const mutationStarted = performance.now();
      await page.locator("html").evaluate((element, value) => {
        element.style.setProperty("--gain", String(value));
      }, gain);
      const actual = await readStrip(page, count);
      samples.push({
        gain,
        milliseconds: performance.now() - mutationStarted,
        ...stats(actual, expected),
      });
    }
    const timings = samples.map(({ milliseconds }) => milliseconds).sort((a, b) => a - b);
    results.push({
      count,
      loadAndFirstPaintMilliseconds,
      initial: stats(initial, source),
      mutationMedianMilliseconds: timings[Math.floor(timings.length / 2)],
      mutationMaximumMilliseconds: timings.at(-1),
      samples,
      elements: await page.locator("*").count(),
    });
    await page.close();
  }
} finally {
  await browser.close();
}

const report = { rounds, results };
await fs.writeFile(
  new URL("../experiments/geometry-raster-vector/browser-results.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
