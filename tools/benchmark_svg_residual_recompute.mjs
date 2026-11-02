import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.SVG_RECOMPUTE_ROUNDS ?? "12", 10);
const referencePath = process.env.SVG_RECOMPUTE_REFERENCE
  ? new URL(process.env.SVG_RECOMPUTE_REFERENCE, `file://${process.cwd()}/`)
  : new URL(
    "../experiments/svg-multitoken-attention/reference.json",
    import.meta.url,
  );
const reference = JSON.parse(await fs.readFile(referencePath, "utf8"));

const variants = process.env.SVG_RECOMPUTE_VARIANTS
  ? process.env.SVG_RECOMPUTE_VARIANTS.split(",").map((entry) => {
    const separator = entry.indexOf(":");
    if (separator < 1 || separator === entry.length - 1) {
      throw new Error("SVG_RECOMPUTE_VARIANTS entries must be name:url");
    }
    return { name: entry.slice(0, separator), url: entry.slice(separator + 1) };
  })
  : [
    {
      name: "split-sign-qkv",
      url: "http://127.0.0.1:4178/experiments/svg-staged-mixed-projection/index.html",
    },
    {
      name: "centered-dot-qkv",
      url: "http://127.0.0.1:4178/experiments/svg-staged-mixed-projection-centered/index.html",
    },
  ];
if (process.env.SVG_RECOMPUTE_ORDER === "centered-first") {
  variants.reverse();
}

function stats(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return {
    minimum: sorted[0],
    median: sorted[Math.floor(sorted.length / 2)],
    mean: values.reduce((sum, value) => sum + value, 0) / values.length,
    maximum: sorted.at(-1),
  };
}

async function decode(png) {
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const center = reference.surface_center ?? reference.surfaceCenter;
  const scales = reference.residual_scales ?? reference.residualScales;
  const expectedValue = reference.expected_residual ?? reference.expectedResidual;
  const expected = Array.isArray(expectedValue[0]) ? expectedValue[1] : expectedValue;
  const actual = Array.from({ length: reference.width }, (_, index) =>
    (data[index * info.channels] / 255 - center) * 2 * scales[index]);
  const errors = actual.map((value, index) =>
    value - expected[index]);
  const result = {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0)
      / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
  if (reference.nextLnExpected) {
    const mean = actual.reduce((sum, value) => sum + value, 0) / actual.length;
    const variance = actual.reduce(
      (sum, value) => sum + (value - mean) ** 2,
      0,
    ) / actual.length;
    const normalized = actual.map((value, index) =>
      (value - mean) / Math.sqrt(variance + 1e-5) * reference.nextLnGamma[index]
        + reference.nextLnBeta[index]);
    const normalizedErrors = normalized.map(
      (value, index) => value - reference.nextLnExpected[index],
    );
    result.nextLnRmse = Math.sqrt(normalizedErrors.reduce(
      (sum, value) => sum + value * value,
      0,
    ) / normalizedErrors.length);
    result.nextLnMaxError = Math.max(...normalizedErrors.map(Math.abs));
  }
  return result;
}

const result = { rounds, variants: {} };
for (const variant of variants) {
  const browser = await chromium.launch({ executablePath, headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 64, height: 800 } });
    await page.goto(variant.url, { waitUntil: "load", timeout: 180000 });
    await page.locator("svg").screenshot({ timeout: 180000 });
    const inputImage = page.locator("filter").first().locator("feImage").first();
    const originalHref = await inputImage.getAttribute("href");
    if (!originalHref) throw new Error(`No input image in ${variant.name}`);
    const baseHref = originalHref.split("?")[0];
    const samples = [];
    for (let round = 0; round < rounds; round += 1) {
      const started = performance.now();
      await inputImage.evaluate((image, payload) => {
        image.setAttribute("href", `${payload.baseHref}?recompute=${payload.round}`);
      }, { baseHref, round });
      const png = await page.locator("svg").screenshot({ timeout: 180000 });
      samples.push({ milliseconds: performance.now() - started, ...await decode(png) });
    }
    result.variants[variant.name] = {
      timing: stats(samples.map((sample) => sample.milliseconds)),
      rmse: stats(samples.map((sample) => sample.rmse)),
      maxError: Math.max(...samples.map((sample) => sample.maxError)),
      ...(samples[0].nextLnRmse === undefined ? {} : {
        nextLnRmse: stats(samples.map((sample) => sample.nextLnRmse)),
        nextLnMaxError: Math.max(...samples.map((sample) => sample.nextLnMaxError)),
      }),
      samples,
    };
  } finally {
    await browser.close();
  }
}

const baseline = result.variants["split-sign-qkv"];
const candidate = result.variants["centered-dot-qkv"];
if (baseline && candidate) {
  result.centeredDotSpeedup = baseline.timing.median / candidate.timing.median;
}
console.log(JSON.stringify(result, null, 2));
