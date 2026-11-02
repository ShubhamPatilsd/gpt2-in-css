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
const rounds = Number.parseInt(process.env.SVG_RESIDUAL_BENCH_ROUNDS ?? "9", 10);
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/svg-multitoken-attention/reference.json", import.meta.url,
), "utf8"));
const allVariants = [
  {
    name: "head-local",
    url: "http://127.0.0.1:4178/experiments/svg-multitoken-attention/connected-attention-residual.html",
  },
  {
    name: "rgb-staged",
    url: "http://127.0.0.1:4178/experiments/svg-multitoken-attention-rgb-tile/connected-attention-residual-staged.html",
  },
  {
    name: "mixed-direct",
    url: "http://127.0.0.1:4178/experiments/svg-staged-mixed-projection/index.html",
  },
  {
    name: "mixed-rgb",
    url: "http://127.0.0.1:4178/experiments/svg-staged-mixed-projection-rgb/index.html",
  },
  {
    name: "mixed-centered-qkv",
    url: "http://127.0.0.1:4178/experiments/svg-staged-mixed-projection-centered/index.html",
  },
];
const benchSet = process.env.SVG_RESIDUAL_BENCH_SET;
const variants = benchSet === "mixed"
  ? allVariants.slice(1)
  : benchSet === "rgb"
    ? allVariants.filter((variant) => variant.name === "mixed-rgb")
    : benchSet === "centered"
      ? allVariants.filter((variant) =>
        variant.name === "mixed-direct" || variant.name === "mixed-centered-qkv")
      : benchSet === "centered-only"
        ? allVariants.filter((variant) => variant.name === "mixed-centered-qkv")
        : benchSet === "direct-only"
          ? allVariants.filter((variant) => variant.name === "mixed-direct")
    : allVariants;

function stats(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return {
    minimum: sorted[0],
    median: sorted[Math.floor(sorted.length / 2)],
    mean: values.reduce((sum, value) => sum + value, 0) / values.length,
    maximum: sorted.at(-1),
  };
}

async function measure(page, variant) {
  const started = performance.now();
  await page.goto(`${variant.url}?run=${performance.now()}`, {
    waitUntil: "load",
    timeout: 180000,
  });
  const png = await page.locator("svg").screenshot({ timeout: 180000 });
  const milliseconds = performance.now() - started;
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const actual = Array.from({ length: reference.width }, (_, index) =>
    (data[index * info.channels] / 255 - reference.surface_center)
      * 2 * reference.residual_scales[index]);
  const errors = actual.map((value, index) =>
    value - reference.expected_residual[1][index]);
  return {
    milliseconds,
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0)
      / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const pages = new Map();
  for (const variant of variants) {
    const page = await browser.newPage({ viewport: { width: 64, height: 800 } });
    pages.set(variant.name, page);
    await measure(page, variant);
  }
  const samples = Object.fromEntries(variants.map((variant) => [variant.name, []]));
  for (let round = 0; round < rounds; round += 1) {
    const order = round % 2 === 0 ? variants : [...variants].reverse();
    for (const variant of order) {
      samples[variant.name].push(await measure(pages.get(variant.name), variant));
    }
  }
  const result = { rounds, variants: {} };
  for (const variant of variants) {
    result.variants[variant.name] = {
      timing: stats(samples[variant.name].map((sample) => sample.milliseconds)),
      rmse: stats(samples[variant.name].map((sample) => sample.rmse)),
      maxError: Math.max(...samples[variant.name].map((sample) => sample.maxError)),
    };
    result.variants[variant.name].valid =
      result.variants[variant.name].rmse.maximum < 0.1;
  }
  if (result.variants["head-local"]) {
    result.speedupComparable = result.variants["head-local"].valid
      && result.variants["rgb-staged"].valid;
    result.rgbStagedSpeedup = result.speedupComparable
      ? result.variants["head-local"].timing.median
        / result.variants["rgb-staged"].timing.median
      : null;
  }
  if (result.variants["rgb-staged"] && result.variants["mixed-direct"]) {
    result.mixedDirectSpeedup =
      result.variants["rgb-staged"].timing.median
      / result.variants["mixed-direct"].timing.median;
  }
  if (result.variants["mixed-rgb"] && result.variants["mixed-direct"]) {
    result.mixedRgbSpeedupVsSeparate =
      result.variants["mixed-direct"].timing.median
      / result.variants["mixed-rgb"].timing.median;
    result.mixedRgbSpeedupVsOriginalProjection =
      result.variants["rgb-staged"].timing.median
      / result.variants["mixed-rgb"].timing.median;
  }
  if (result.variants["mixed-centered-qkv"] && result.variants["mixed-direct"]) {
    result.centeredQkvSpeedupVsSplitSign =
      result.variants["mixed-direct"].timing.median
      / result.variants["mixed-centered-qkv"].timing.median;
  }
  if (process.env.SVG_RESIDUAL_BENCH_RAW === "1") {
    result.samples = samples;
  }
  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
