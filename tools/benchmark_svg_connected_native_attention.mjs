import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.SVG_NATIVE_ATTENTION_ROUNDS ?? "7", 10);
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/svg-contiguous-qkv-batched-native-convolve/reference.json",
  import.meta.url,
), "utf8"));

const variants = [
  {
    name: "head-local",
    url: "http://127.0.0.1:4178/experiments/svg-multitoken-attention/connected-qkv.html",
    contextResult: "context1-common",
    contextY: 1,
    probabilityResult: null,
  },
  {
    name: "contiguous-native",
    url: "http://127.0.0.1:4178/experiments/svg-contiguous-qkv-batched-native-convolve/index.html",
    contextResult: "context1-common",
    contextY: 255,
    probabilityResult: "prob0-tile",
  },
];

function stats(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return {
    minimum: sorted[0],
    median: sorted[Math.floor(sorted.length / 2)],
    mean: values.reduce((sum, value) => sum + value, 0) / values.length,
    maximum: sorted.at(-1),
  };
}

function errorSummary(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0)
      / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

async function expose(page, resultName, y) {
  await page.locator("filter").evaluate((filter, name) => {
    filter.lastElementChild.innerHTML = `<feMergeNode in="${name}"/>`;
  }, resultName);
  await page.locator("svg").evaluate((svg, viewY) => {
    svg.setAttribute("width", "768");
    svg.setAttribute("height", "1");
    svg.setAttribute("viewBox", `0 ${viewY} 768 1`);
  }, y);
}

async function measureContext(page, variant) {
  const started = performance.now();
  await page.goto(`${variant.url}?run=${performance.now()}`, {
    waitUntil: "load",
    timeout: 180000,
  });
  await expose(page, variant.contextResult, variant.contextY);
  const png = await page.locator("svg").screenshot({ timeout: 180000 });
  const milliseconds = performance.now() - started;
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const actual = Array.from({ length: 768 }, (_, index) => {
    const head = Math.floor(index / reference.headWidth);
    const offset = index % reference.headWidth;
    const code = data[index * info.channels] / 255;
    return (code - reference.surfaceCenter) * 2
      * reference.valueScales[head][offset];
  });
  return {
    milliseconds,
    ...errorSummary(actual, reference.expectedContext[1].flat()),
  };
}

async function measureProbabilities(page, variant) {
  if (variant.probabilityResult === null) return null;
  await page.goto(`${variant.url}?probability=${performance.now()}`, {
    waitUntil: "load",
    timeout: 180000,
  });
  await expose(page, variant.probabilityResult, variant.contextY);
  const png = await page.locator("svg").screenshot({ timeout: 180000 });
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const actual = Array.from({ length: reference.heads }, (_, head) =>
    data[head * reference.headWidth * info.channels] / 255);
  return {
    actual,
    expected: reference.expectedProbabilities,
    maxError: Math.max(...actual.map((value, head) =>
      Math.abs(value - reference.expectedProbabilities[head]))),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const pages = new Map();
  for (const variant of variants) {
    const page = await browser.newPage({ viewport: { width: 800, height: 100 } });
    pages.set(variant.name, page);
    await measureContext(page, variant);
  }
  const samples = Object.fromEntries(variants.map((variant) => [variant.name, []]));
  for (let round = 0; round < rounds; round += 1) {
    const order = round % 2 === 0 ? variants : [...variants].reverse();
    for (const variant of order) {
      samples[variant.name].push(await measureContext(pages.get(variant.name), variant));
    }
  }
  const result = { rounds, variants: {} };
  for (const variant of variants) {
    result.variants[variant.name] = {
      timing: stats(samples[variant.name].map((sample) => sample.milliseconds)),
      rmse: stats(samples[variant.name].map((sample) => sample.rmse)),
      maxError: Math.max(...samples[variant.name].map((sample) => sample.maxError)),
      probabilities: await measureProbabilities(pages.get(variant.name), variant),
    };
  }
  result.contiguousNativeSpeedup =
    result.variants["head-local"].timing.median
    / result.variants["contiguous-native"].timing.median;
  console.log(JSON.stringify(result, null, 2));
  if (result.variants["contiguous-native"].rmse.maximum > 0.03
      || result.variants["contiguous-native"].probabilities.maxError > 0.06) {
    process.exitCode = 1;
  }
} finally {
  await browser.close();
}
