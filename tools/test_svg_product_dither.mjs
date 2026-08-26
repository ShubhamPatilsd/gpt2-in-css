import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const sharp = require(`${root}/sharp`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/svg-product-dither/reference.json", import.meta.url), "utf8"));

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 20, height: 100 } });
  const started = performance.now();
  await page.goto("http://127.0.0.1:4178/experiments/svg-product-dither/index.html", {
    waitUntil: "load", timeout: 120000,
  });
  const png = await page.locator("svg").screenshot({ timeout: 120000 });
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const summarize = (column) => {
    const values = Array.from({ length: reference.width }, (_, row) =>
      (data[(row * info.width + column) * info.channels] / 255 - reference.center)
      * 2 * reference.output_bound
    );
    const errors = values.map((value, index) => value - reference.expected[index]);
    return {
      rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
      maxError: Math.max(...errors.map(Math.abs)),
      distinctValues: new Set(values.map((value) => value.toFixed(12))).size,
    };
  };
  const baseline = summarize(0);
  const dithered = summarize(1);
  console.log(JSON.stringify({
    baseline,
    dithered,
    improvement: baseline.rmse / dithered.rmse,
    milliseconds: performance.now() - started,
  }, null, 2));
} finally {
  await browser.close();
}
