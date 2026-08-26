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

async function decode(png) {
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: info.width * info.height }, (_, index) =>
    (data[index * info.channels] / 255 - reference.surface_center)
      * 2 * reference.output_range_2blocks
  );
}

async function decodeRange(png, range) {
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: info.width * info.height }, (_, index) =>
    (data[index * info.channels] / 255 - reference.surface_center) * 2 * range
  );
}

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    maxError: Math.max(...errors.map(Math.abs)),
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    actualRange: [Math.min(...actual), Math.max(...actual)],
    levels: new Set(actual).size,
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 200 } });
  const start = performance.now();
  await page.goto(`${baseUrl}/chain-2blocks.html?run=${Date.now()}`, { waitUntil: "load" });
  let png = await page.locator("svg").screenshot({ animations: "disabled" });
  const coldMilliseconds = performance.now() - start;
  const original = summarize(await decode(png), reference.expected_2blocks);

  const stageSpecs = [
    ["chain-6.html", "b1_n1", "b1_n1_range"],
    ["chain-7.html", "b1_residual", "b1_residual_range"],
    ["chain-8.html", "b1_n2", "b1_n2_range"],
    ["chain-9.html", "b1_hidden", "b1_hidden_range"],
  ];
  const stages = {};
  for (const [file, vectorKey, rangeKey] of stageSpecs) {
    await page.goto(`${baseUrl}/${file}?stage=${Date.now()}`, { waitUntil: "load" });
    const stagePng = await page.locator("svg").screenshot({ animations: "disabled" });
    stages[file] = summarize(
      await decodeRange(stagePng, reference[rangeKey]), reference[vectorKey],
    );
  }
  await page.goto(`${baseUrl}/chain-2blocks.html?mutation=${Date.now()}`, { waitUntil: "load" });
  await page.locator("svg").screenshot({ animations: "disabled" });

  const timings = [];
  const mutation = {};
  for (let index = 0; index < 12; index += 1) {
    const href = index % 2 ? "x.png" : "x-alt.png";
    const mutationStart = performance.now();
    await page.locator("#chain-ln1 feImage").first().evaluate(
      (element, value) => element.setAttribute("href", value), href,
    );
    png = await page.locator("svg").screenshot({ animations: "disabled" });
    timings.push(performance.now() - mutationStart);
    mutation[href] = summarize(
      await decode(png),
      href === "x.png" ? reference.expected_2blocks : reference.expected_alt_2blocks,
    );
  }
  const sorted = timings.slice(1).sort((a, b) => a - b);
  const result = {
    original,
    stages,
    mutation,
    coldMilliseconds,
    mutationTimings: timings,
    warmMedianMilliseconds: sorted[Math.floor(sorted.length / 2)],
  };
  console.log(JSON.stringify(result, null, 2));
  if (original.maxError > 20 || original.rmse > 2) {
    throw new Error(`two-block accuracy regression: ${JSON.stringify(original)}`);
  }
  for (const accuracy of Object.values(mutation)) {
    if (accuracy.maxError > 20 || accuracy.rmse > 2) {
      throw new Error(`two-block live-input regression: ${JSON.stringify(accuracy)}`);
    }
  }
} finally {
  await browser.close();
}
