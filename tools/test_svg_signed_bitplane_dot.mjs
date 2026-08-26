import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/svg-signed-bitplane-dot/reference.json", import.meta.url),
));

function stats(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
    distinctValues: new Set(actual.map((value) => value.toFixed(8))).size,
  };
}

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 20, height: 100 } });
  const started = performance.now();
  await page.goto("http://127.0.0.1:4178/experiments/svg-signed-bitplane-dot/index.html", {
    waitUntil: "load",
    timeout: 30000,
  });
  const png = await page.locator("svg").screenshot();
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const columns = Array.from({ length: 4 }, (_, x) =>
    Array.from({ length: 64 }, (_, y) =>
      (data[(y * info.width + x) * info.channels] / 255 - 128 / 255)
      * 2 * reference.outputBound,
    ),
  );
  console.log(JSON.stringify({
    ordinaryProduct: stats(columns[0], reference.expected),
    signedSixBitPlanes: stats(columns[1], reference.expected),
    packedTwosComplementPlanes: stats(columns[2], reference.expected),
    packedSignedMagnitudePlanes: stats(columns[3], reference.expected),
    inputQuantizationRmse: reference.inputRmse,
    weightQuantizationRmse: reference.weightRmse,
    packedWeightQuantizationRmse: reference.packedWeightRmse,
    filterPrimitives: reference.filterPrimitives,
    htmlBytes: reference.htmlBytes,
    milliseconds: performance.now() - started,
  }, null, 2));
} finally {
  await browser.close();
}
