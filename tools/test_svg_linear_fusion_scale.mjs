import fs from "node:fs/promises";
import { performance } from "node:perf_hooks";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = process.env.SVG_LINEAR_FUSION_URL ??
  "http://127.0.0.1:4178/experiments/svg-linear-fusion-scale";
const referenceUrl = new URL(
  "../experiments/svg-linear-fusion-scale/reference.json", import.meta.url,
);
const resultsUrl = new URL(
  "../experiments/svg-linear-fusion-scale/results.json", import.meta.url,
);
const reference = JSON.parse(await fs.readFile(referenceUrl, "utf8"));

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
const page = await browser.newPage({ viewport: { width: 3200, height: 100 } });
const results = [];
try {
  for (const [name, fixture] of Object.entries(reference.cases)) {
    const timings = [];
    let png;
    for (let run = 0; run < 3; run += 1) {
      const started = performance.now();
      await page.goto(`${baseUrl}/${name}.html?run=${run}`, {
        waitUntil: "load",
        timeout: 120000,
      });
      png = await page.locator("svg").screenshot({ animations: "disabled" });
      timings.push(performance.now() - started);
    }
    const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
    const red = (x, y) => data[(y * info.width + x) * info.channels] / 255 * 2 - 1;
    const chain = Array.from({ length: fixture.width }, (_, x) => red(x, 0));
    const bounded = Array.from({ length: fixture.width }, (_, x) => red(x, 1));
    const fused = Array.from({ length: fixture.width }, (_, x) => red(x, 2));
    const chainSummary = summarize(chain, fixture.expected);
    const boundedSummary = summarize(bounded, fixture.expected);
    const fusedSummary = summarize(fused, fixture.expected);
    results.push({
      name,
      width: fixture.width,
      stages: fixture.stages,
      chainPrimitives: fixture.chain_primitives,
      boundedPrimitives: fixture.bounded_primitives,
      fusedPrimitives: fixture.fused_primitives,
      chain: chainSummary,
      bounded: boundedSummary,
      fused: fusedSummary,
      rmseRatio: chainSummary.rmse / Math.max(fusedSummary.rmse, Number.EPSILON),
      boundedRmseRatio: boundedSummary.rmse / Math.max(fusedSummary.rmse, Number.EPSILON),
      medianNavigationAndCaptureMs: median(timings),
    });
  }
} finally {
  await browser.close();
}

const report = { results };
await fs.writeFile(resultsUrl, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
