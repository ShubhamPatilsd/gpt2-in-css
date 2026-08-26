import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = process.env.SVG_CHAIN_URL ??
  "http://127.0.0.1:4178/experiments/svg-filter-full-block";
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/svg-filter-full-block/reference.json", import.meta.url,
), "utf8"));
const outliers = new Set(reference.grouped_outlier_dims);

async function decode(png, blockCount = 2) {
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: info.width * info.height }, (_, index) => {
    const channel = outliers.has(index) ? 1 : 0;
    const range = outliers.has(index)
      ? reference[`grouped_${blockCount}block${blockCount === 1 ? "" : "s"}_outlier_range`]
      : reference[`grouped_${blockCount}block${blockCount === 1 ? "" : "s"}_normal_range`];
    return (data[index * info.channels + channel] / 255 - reference.surface_center)
      * 2 * range;
  });
}

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  const normalErrors = errors.filter((_, index) => !outliers.has(index));
  const largest = errors.reduce(
    (best, value, index) => Math.abs(value) > Math.abs(errors[best]) ? index : best, 0,
  );
  return {
    maxError: Math.max(...errors.map(Math.abs)),
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    normalRmse: Math.sqrt(
      normalErrors.reduce((sum, value) => sum + value * value, 0) / normalErrors.length,
    ),
    outlierErrors: [...outliers].map((index) => ({ index, error: errors[index] })),
    normalLevels: new Set(actual.filter((_, index) => !outliers.has(index))).size,
    largest: { index: largest, actual: actual[largest], expected: expected[largest] },
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 200 } });
  await page.goto(`${baseUrl}/grouped-chain-1block.html?stage=${Date.now()}`, { waitUntil: "load" });
  let onePng = await page.locator("svg").screenshot({ animations: "disabled" });
  const oneBlock = {
    original: summarize(await decode(onePng, 1), reference.grouped_1block_expected),
  };
  await page.locator('feImage[href^="grouped-x"]').first().evaluate(
    (element) => element.setAttribute("href", "grouped-x-alt.png"),
  );
  onePng = await page.locator("svg").screenshot({ animations: "disabled" });
  oneBlock.alternate = summarize(
    await decode(onePng, 1), reference.grouped_1block_expected_alt,
  );
  const start = performance.now();
  await page.goto(`${baseUrl}/grouped-chain-2blocks.html?run=${Date.now()}`, { waitUntil: "load" });
  let png = await page.locator("svg").screenshot({ animations: "disabled" });
  const coldMilliseconds = performance.now() - start;
  const original = summarize(await decode(png), reference.grouped_2blocks_expected);
  const timings = [];
  const results = {};
  for (const href of ["grouped-x-alt.png", "grouped-x.png", "grouped-x-alt.png", "grouped-x.png"]) {
    const mutationStart = performance.now();
    await page.locator('feImage[href^="grouped-x"]').first().evaluate(
      (element, value) => element.setAttribute("href", value), href,
    );
    png = await page.locator("svg").screenshot({ animations: "disabled" });
    timings.push(performance.now() - mutationStart);
    results[href] = summarize(
      await decode(png),
      href === "grouped-x.png"
        ? reference.grouped_2blocks_expected
        : reference.grouped_2blocks_expected_alt,
    );
  }
  const sorted = timings.slice(1).sort((a, b) => a - b);
  const report = {
    oneBlock,
    original,
    mutation: results,
    coldMilliseconds,
    mutationTimings: timings,
    warmMedianMilliseconds: sorted[Math.floor(sorted.length / 2)],
  };
  console.log(JSON.stringify(report, null, 2));
  if (original.rmse > 1 || Object.values(results).some((result) => result.rmse > 1)) {
    throw new Error("two-scale connected blocks missed the accuracy gate");
  }
} finally {
  await browser.close();
}
