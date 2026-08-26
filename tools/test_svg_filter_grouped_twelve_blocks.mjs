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

async function raw(png) {
  return sharp(png).raw().toBuffer({ resolveWithObject: true });
}

async function decodeGrouped(png) {
  const { data, info } = await raw(png);
  return Array.from({ length: info.width * info.height }, (_, index) => {
    const isOutlier = outliers.has(index);
    const range = isOutlier
      ? reference.grouped_12blocks_outlier_range
      : reference.grouped_12blocks_normal_range;
    return (data[index * info.channels + (isOutlier ? 1 : 0)] / 255
      - reference.surface_center) * 2 * range;
  });
}

async function decodeFinal(png) {
  const { data, info } = await raw(png);
  return Array.from({ length: info.width * info.height }, (_, index) =>
    (data[index * info.channels] / 255 - reference.surface_center)
      * 2 * reference.grouped_final_ln_range
  );
}

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  const normal = errors.filter((_, index) => !outliers.has(index));
  return {
    maxError: Math.max(...errors.map(Math.abs)),
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    normalRmse: Math.sqrt(normal.reduce((sum, value) => sum + value * value, 0) / normal.length),
    levels: new Set(actual).size,
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 200 } });
  const coldStart = performance.now();
  await page.goto(`${baseUrl}/grouped-chain-12blocks.html?run=${Date.now()}`, {
    waitUntil: "load", timeout: 120000,
  });
  let png = await page.locator("svg").screenshot({ animations: "disabled", timeout: 120000 });
  const coldMilliseconds = performance.now() - coldStart;
  const stateOriginal = await decodeGrouped(png);
  const state = {
    original: summarize(stateOriginal, reference.grouped_12blocks_expected),
  };
  await page.locator('feImage[href^="grouped-x"]').first().evaluate(
    (element) => element.setAttribute("href", "grouped-x-alt.png"),
  );
  let start = performance.now();
  png = await page.locator("svg").screenshot({ animations: "disabled", timeout: 120000 });
  const alternateMilliseconds = performance.now() - start;
  const stateAlternate = await decodeGrouped(png);
  state.alternate = summarize(stateAlternate, reference.grouped_12blocks_expected_alt);

  await page.goto(`${baseUrl}/grouped-chain-12blocks-final-ln.html?final=${Date.now()}`, {
    waitUntil: "load", timeout: 120000,
  });
  start = performance.now();
  let finalPng = await page.locator("svg").screenshot({ animations: "disabled", timeout: 120000 });
  const finalOriginal = await decodeFinal(finalPng);
  const final = {
    original: summarize(finalOriginal, reference.grouped_final_ln_expected),
  };
  await page.locator('feImage[href^="grouped-x"]').first().evaluate(
    (element) => element.setAttribute("href", "grouped-x-alt.png"),
  );
  finalPng = await page.locator("svg").screenshot({ animations: "disabled", timeout: 120000 });
  const finalAlternate = await decodeFinal(finalPng);
  final.alternate = summarize(
    finalAlternate, reference.grouped_final_ln_expected_alt,
  );
  await fs.writeFile(
    "/tmp/svg-filter-grouped-final-ln.json",
    JSON.stringify({
      stateOriginal,
      stateAlternate,
      original: finalOriginal,
      alternate: finalAlternate,
    }),
  );
  console.log(JSON.stringify({
    state,
    final,
    coldMilliseconds,
    alternateMilliseconds,
    finalWarmMilliseconds: performance.now() - start,
  }, null, 2));
} finally {
  await browser.close();
}
