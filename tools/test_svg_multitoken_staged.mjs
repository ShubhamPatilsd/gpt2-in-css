import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = process.env.SVG_MULTITOKEN_URL ??
  "http://127.0.0.1:4178/experiments/svg-multitoken-attention";
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/svg-multitoken-attention/reference.json", import.meta.url,
), "utf8"));

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    maxError: Math.max(...errors.map(Math.abs)),
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0)
      / errors.length),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 100, height: 800 } });
  async function evaluate(file, expected, scales, resultName) {
    const started = performance.now();
    await page.goto(`${baseUrl}/${file}?run=${Date.now()}`, {
      waitUntil: "load", timeout: 180000,
    });
    const actual = [];
    for (let chunk = 0; chunk < 12; chunk += 1) {
      await page.locator("filter").last().evaluate((filter, name) => {
        filter.lastElementChild.innerHTML = `<feMergeNode in="${name}"/>`;
      }, resultName(chunk));
      await page.locator("svg").evaluate((svg, y) => {
        svg.setAttribute("width", "1");
        svg.setAttribute("height", "64");
        svg.setAttribute("viewBox", `63 ${y} 1 64`);
      }, chunk * 64);
      const png = await page.locator("svg").screenshot({ timeout: 180000 });
      const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
      for (let offset = 0; offset < 64; offset += 1) {
        const index = chunk * 64 + offset;
        actual[index] = (data[offset * info.channels] / 255
          - reference.surface_center) * 2 * scales[index];
      }
    }
    return {
      ...summarize(actual, expected),
      milliseconds: performance.now() - started,
    };
  }
  const projection = await evaluate(
    "attention-projection-staged.html",
    reference.expected_projected[1],
    reference.projected_scales,
    (chunk) => `p1-cproj-${chunk}-common`,
  );
  const residual = await evaluate(
    "connected-attention-residual-staged.html",
    reference.expected_residual[1],
    reference.residual_scales,
    (chunk) => `p1-residual-c${chunk}-common`,
  );
  console.log(JSON.stringify({ projection, residual }, null, 2));
  if (![projection, residual].every((entry) =>
    Number.isFinite(entry.rmse) && entry.rmse < 0.05)) process.exitCode = 1;
} finally {
  await browser.close();
}
