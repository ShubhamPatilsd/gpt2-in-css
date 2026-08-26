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
const baseUrl = process.env.SVG_LN_FUSION_URL ??
  "http://127.0.0.1:4178/experiments/svg-layernorm-matrix-fusion-bucketed";
const referenceUrl = new URL(
  "../experiments/svg-layernorm-matrix-fusion-bucketed/reference.json", import.meta.url,
);
const resultsUrl = new URL(
  "../experiments/svg-layernorm-matrix-fusion-bucketed/results.json", import.meta.url,
);
const reference = JSON.parse(await fs.readFile(referenceUrl, "utf8"));
const center = 128 / 255;

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
const page = await browser.newPage({ viewport: { width: 32, height: 800 } });
const report = {};
try {
  for (const mode of ["materialized", "fused", "materialized-alt", "fused-alt", "reduced"]) {
    const timings = [];
    let png;
    for (let run = 0; run < 7; run += 1) {
      const started = performance.now();
      await page.goto(`${baseUrl}/${mode}.html?run=${run}`, {
        waitUntil: "load",
        timeout: 120000,
      });
      png = await page.locator("svg").screenshot({ animations: "disabled" });
      timings.push(performance.now() - started);
    }
    const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
    const scales = mode === "reduced"
      ? reference.reduced_scales
      : mode.startsWith("fused")
        ? reference.fused_output_scales
        : reference.baseline_output_scales;
    const actual = Array.from({ length: 768 }, (_, y) =>
      (data[(y * info.width) * info.channels] / 255 - center) *
      2 * scales[y]
    );
    const expected = mode === "reduced"
      ? reference.reduced
      : mode.endsWith("-alt") ? reference.expected_alt : reference.expected;
    const fused = mode.startsWith("fused");
    report[mode] = {
      ...summarize(actual, expected),
      actualMin: Math.min(...actual),
      actualMax: Math.max(...actual),
      expectedMin: Math.min(...expected),
      expectedMax: Math.max(...expected),
      firstValues: actual.slice(0, 8),
      firstExpected: expected.slice(0, 8),
      medianWarmNavigationAndCaptureMs: median(timings.slice(2)),
      timingsMs: timings,
      primitives: mode === "reduced" ? null
        : fused ? reference.fused_primitives : reference.baseline_primitives,
      htmlBytes: reference.pages[mode],
    };
  }
} finally {
  await browser.close();
}

report.algebraicMaxError = reference.algebraic_max_error;
await fs.writeFile(resultsUrl, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
