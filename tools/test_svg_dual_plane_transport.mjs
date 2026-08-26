import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = process.env.SVG_DUAL_PLANE_URL ??
  "http://127.0.0.1:4178/experiments/svg-dual-plane-transport/index.html";
const referencePath = new URL(
  "../experiments/svg-dual-plane-transport/reference.json", import.meta.url,
);
const resultsPath = new URL(
  "../experiments/svg-dual-plane-transport/results.json", import.meta.url,
);
const reference = JSON.parse(await fs.readFile(referencePath, "utf8"));

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
    distinct: new Set(actual.map((value) => value.toFixed(9))).size,
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 512, height: 200 } });
  await page.goto(`${url}?run=${Date.now()}`, { waitUntil: "load", timeout: 120000 });
  const png = await page.locator("svg").screenshot({ animations: "disabled" });
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const channel = (x, y, c) => data[(y * info.width + x) * info.channels + c];
  const results = [];
  reference.checkpoints.forEach((checkpoint, index) => {
    const singleRow = index * 2;
    const dualRow = singleRow + 1;
    const single = Array.from({ length: reference.width }, (_, x) =>
      (channel(x, singleRow, 0) / 255 - reference.center) * 2 * reference.coarse_range
    );
    const dual = Array.from({ length: reference.width }, (_, x) =>
      (channel(x, dualRow, 0) / 255 - reference.center) * 2 * reference.coarse_range
      + (channel(x, dualRow, 1) / 255 - reference.center) * 2 * reference.fine_range
    );
    results.push({
      checkpoint,
      single: summarize(single, reference.exact[String(checkpoint)]),
      dual: summarize(dual, reference.exact[String(checkpoint)]),
    });
  });
  const radixRow = reference.checkpoints.length * 2;
  let radixErrors = 0;
  const radixMismatches = [];
  for (let x = 0; x < reference.width; x += 1) {
    const total = reference.radix_left[x] + reference.radix_right[x];
    const actualLow = channel(x, radixRow, 0);
    const actualCarry = channel(x, radixRow, 1);
    const expectedLow = (total % 16) * reference.radix_step;
    const expectedCarry = Math.floor(total / 16) * reference.radix_step;
    if (actualLow !== expectedLow || actualCarry !== expectedCarry) {
      radixErrors += 1;
      if (radixMismatches.length < 12) {
        radixMismatches.push({
          x,
          left: reference.radix_left[x],
          right: reference.radix_right[x],
          total,
          expected: [expectedLow, expectedCarry],
          actual: [actualLow, actualCarry],
        });
      }
    }
  }
  const report = {
    results,
    radixErrors,
    radixMismatches,
    exactRadixDotLowerBounds: reference.exact_radix_dot_lower_bounds,
  };
  await fs.writeFile(resultsPath, `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
