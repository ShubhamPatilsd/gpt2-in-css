import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const sharp = require(`${root}/sharp`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/svg-magnitude-plane-dot/reference.json", import.meta.url), "utf8"));
const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 20, height: 128 } });
  const started = performance.now();
  await page.goto("http://127.0.0.1:4178/experiments/svg-magnitude-plane-dot/index.html", {
    waitUntil: "load",
  });
  const png = await page.locator("svg").screenshot();
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const columns = Array.from({ length: 6 }, (_, column) =>
    Array.from({ length: 64 }, (_, index) =>
      (data[(index * info.width + column) * info.channels] / 255 - 128 / 255)
      * 2 * reference.output_bound));
  const summarize = (actual) => {
    const errors = actual.map((value, index) => value - reference.expected[index]);
    return {
      rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
      maxError: Math.max(...errors.map(Math.abs)),
    };
  };
  console.log(JSON.stringify({
    baseline: summarize(columns[0]),
    centeredMagnitudePlanes: summarize(columns[1]),
    sharedScaleMagnitudePlanes: summarize(columns[2]),
    independentScaleMagnitudePlanes: summarize(columns[3]),
    directKernel: summarize(columns[4]),
    directKernel4x: summarize(columns[5]),
    encodedRanges: columns.map((column) => ({
      min: Math.min(...column),
      max: Math.max(...column),
    })),
    directSamples: columns[4].slice(0, 8).map((value, index) => ({
      value, expected: reference.expected[index],
    })),
    milliseconds: performance.now() - started,
  }, null, 2));
} finally {
  await browser.close();
}
