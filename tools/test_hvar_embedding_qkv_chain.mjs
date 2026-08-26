import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const variant = process.env.HVAR_EMBEDDING_QKV_VARIANT ?? "b12";
const rounds = Number.parseInt(process.env.HVAR_EMBEDDING_QKV_ROUNDS ?? "12", 10);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/hvar-embedding-qkv-chain/reference.json", import.meta.url),
  "utf8",
));

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function errors(actual, expected) {
  const delta = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(delta.reduce((sum, value) => sum + value * value, 0) / delta.length),
    maximum: Math.max(...delta.map(Math.abs)),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 800, height: 200 },
  });
  const page = await context.newPage();
  const loadStarted = performance.now();
  await page.goto(
    `http://127.0.0.1:4178/experiments/hvar-embedding-qkv-chain/${variant}.html`,
    { waitUntil: "load", timeout: 180000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const loadMilliseconds = performance.now() - loadStarted;

  async function read() {
    const widths = await page.locator(".qkv-metric").evaluateAll((elements) =>
      elements.map((element) => element.getBoundingClientRect().width));
    return widths.map((width, dimension) =>
      reference.base[dimension] +
      (width - reference.qkvBase) * reference.rowScale[dimension]);
  }

  const initial = await read();
  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    const tokenIndex = (round + 1) % reference.tokens.length;
    const started = performance.now();
    await page.locator(`#t${tokenIndex}`).evaluate((element) => {
      element.checked = true;
    });
    const actual = await read();
    samples.push({
      tokenIndex,
      milliseconds: performance.now() - started,
      transportedError: errors(actual, reference.variants[variant].expected[tokenIndex]),
      denseError: errors(actual, reference.dense[tokenIndex]),
    });
  }
  const initialTransportedError = errors(initial, reference.variants[variant].expected[0]);
  const initialDenseError = errors(initial, reference.dense[0]);
  const report = {
    variant,
    bits: reference.variants[variant].bits,
    loadMilliseconds,
    mutationMedianMilliseconds: median(samples.map((sample) => sample.milliseconds)),
    settledMutationMedianMilliseconds: median(
      samples.slice(2).map((sample) => sample.milliseconds),
    ),
    browserTransportRmseMaximum: Math.max(
      initialTransportedError.rmse,
      ...samples.map((sample) => sample.transportedError.rmse),
    ),
    denseRmseMaximum: Math.max(
      initialDenseError.rmse,
      ...samples.map((sample) => sample.denseError.rmse),
    ),
    denseMaximumError: Math.max(
      initialDenseError.maximum,
      ...samples.map((sample) => sample.denseError.maximum),
    ),
    offlineTransportRmseVsDense: reference.variants[variant].transportRmseVsDense,
    elements: await page.locator("*").count(),
    htmlBytes: reference.variants[variant].htmlBytes,
    fontBytes: reference.fontBytes,
    initial: {
      transportedError: initialTransportedError,
      denseError: initialDenseError,
    },
    samples,
  };
  await fs.writeFile(
    new URL(`../experiments/hvar-embedding-qkv-chain/browser-${variant}.json`, import.meta.url),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
