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
const referencePath = process.env.SVG_CHAIN_REFERENCE ?? new URL(
  "../experiments/svg-filter-full-block/reference.json", import.meta.url,
);
const outputPath = process.env.SVG_CHAIN_OUTPUT ?? "/tmp/svg-filter-bucketed-final.json";
const reference = JSON.parse(await fs.readFile(referencePath, "utf8"));

async function decode(png, scales) {
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: info.width * info.height }, (_, index) =>
    (data[index * info.channels] / 255 - reference.surface_center) * 2 * scales[index]
  );
}

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    maxError: Math.max(...errors.map(Math.abs)),
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    relativeRmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0)
      / expected.reduce((sum, value) => sum + value * value, 0)),
    levels: new Set(actual.map((value) => value.toFixed(8))).size,
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 200 } });
  const start = performance.now();
  await page.goto(`${baseUrl}/bucket-chain-12blocks.html?run=${Date.now()}`, {
    waitUntil: "load", timeout: 180000,
  });
  let png = await page.locator("svg").screenshot({ animations: "disabled", timeout: 180000 });
  const stateOriginal = await decode(png, reference.bucket_12blocks_scales);
  const coldMilliseconds = performance.now() - start;
  await page.locator('feImage[href^="bucket-x"]').first().evaluate(
    (element) => element.setAttribute("href", "bucket-x-alt.png"),
  );
  let warmStart = performance.now();
  png = await page.locator("svg").screenshot({ animations: "disabled", timeout: 180000 });
  const stateAlternate = await decode(png, reference.bucket_12blocks_scales);
  const alternateMilliseconds = performance.now() - warmStart;

  await page.goto(`${baseUrl}/bucket-chain-12blocks-final-ln.html?final=${Date.now()}`, {
    waitUntil: "load", timeout: 180000,
  });
  warmStart = performance.now();
  png = await page.locator("svg").screenshot({ animations: "disabled", timeout: 180000 });
  const finalOriginal = await decode(png, reference.bucket_final_ln_scales);
  await page.locator('feImage[href^="bucket-x"]').first().evaluate(
    (element) => element.setAttribute("href", "bucket-x-alt.png"),
  );
  png = await page.locator("svg").screenshot({ animations: "disabled", timeout: 180000 });
  const finalAlternate = await decode(png, reference.bucket_final_ln_scales);
  const finalWarmMilliseconds = performance.now() - warmStart;
  await fs.writeFile(outputPath, JSON.stringify({
    stateOriginal, stateAlternate, finalOriginal, finalAlternate,
  }));
  console.log(JSON.stringify({
    state: {
      original: summarize(stateOriginal, reference.bucket_12blocks_expected),
      alternate: summarize(stateAlternate, reference.bucket_12blocks_expected_alt),
    },
    final: {
      original: summarize(finalOriginal, reference.bucket_final_ln_expected),
      alternate: summarize(finalAlternate, reference.bucket_final_ln_expected_alt),
    },
    coldMilliseconds,
    alternateMilliseconds,
    finalWarmMilliseconds,
  }, null, 2));
} finally {
  await browser.close();
}
