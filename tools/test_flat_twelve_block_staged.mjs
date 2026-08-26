import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number(process.env.FLAT_12BLOCK_STAGED_ROUNDS ?? 3);
const experiment = new URL("../experiments/gpt2-flat-12block-chain/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", experiment), "utf8"));

function error(actual, expected) {
  const delta = actual.map((value, index) => value - expected[index]);
  return {
    finite: actual.filter(Number.isFinite).length,
    rmse: Math.sqrt(delta.reduce((sum, value) => sum + value * value, 0) / delta.length),
    maximum: Math.max(...delta.map(Math.abs)),
  };
}

function median(values) {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.floor(sorted.length / 2)];
}

async function waitFrames(page, count = 4) {
  await page.evaluate((frames) => new Promise((resolve) => {
    const next = (remaining) => {
      if (remaining <= 0) resolve();
      else requestAnimationFrame(() => next(remaining - 1));
    };
    next(frames);
  }), count);
}

async function readVector(page, selector, prefix) {
  return page.locator(selector).evaluate((element, propertyPrefix) => {
    const style = getComputedStyle(element);
    return Array.from({ length: 768 }, (_, index) => Number(
      style.getPropertyValue(`${propertyPrefix}${String(index).padStart(3, "0")}`),
    ));
  }, prefix);
}

async function setVector(page, selector, prefix, values) {
  const declarations = values.map((value, index) =>
    `${prefix}${String(index).padStart(3, "0")}:${value}`
  ).join(";");
  await page.locator(selector).evaluate((element, cssText) => {
    element.style.cssText = cssText;
  }, declarations);
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const pages = [];
  const loadTimes = [];
  for (let layer = 0; layer < 12; layer += 1) {
    const page = await browser.newPage({ viewport: { width: 900, height: 240 } });
    const url = layer === 0
      ? "http://127.0.0.1:4178/experiments/gpt2-block-css/view-timeline-block-hybrid.html"
      : `http://127.0.0.1:4178/experiments/gpt2-flat-12block-chain/layer${String(layer).padStart(2, "0")}/standalone.html`;
    const started = performance.now();
    await page.goto(`${url}?load=${Date.now()}`, { waitUntil: "load", timeout: 300000 });
    await page.evaluate(() => document.fonts.ready);
    await waitFrames(page);
    loadTimes.push(performance.now() - started);
    pages.push(page);
    console.error(`loaded block ${layer}: ${loadTimes.at(-1).toFixed(1)}ms`);
  }

  const samples = [];
  for (let round = 0; round < rounds + 1; round += 1) {
    const alternate = round % 2 === 0;
    let vector = alternate ? reference.alternateInput : reference.input;
    const layers = [];
    const totalStarted = performance.now();
    for (let layer = 0; layer < 12; layer += 1) {
      const page = pages[layer];
      const inputSelector = layer === 0 ? ".norm1" : "body > div";
      const inputPrefix = layer === 0 ? "--x-" : "--out-";
      const outputSelector = layer === 0 ? "#final" : `#block${layer}-full`;
      const outputPrefix = layer === 0 ? "--out-" : `--b${layer}-final-`;
      const started = performance.now();
      await setVector(page, inputSelector, inputPrefix, vector);
      await waitFrames(page);
      vector = await readVector(page, outputSelector, outputPrefix);
      layers.push({
        layer,
        milliseconds: performance.now() - started,
        error: error(
          vector,
          (alternate ? reference.alternateTrace : reference.baselineTrace)[layer + 1],
        ),
      });
    }
    samples.push({
      round,
      alternate,
      milliseconds: performance.now() - totalStarted,
      finalError: layers.at(-1).error,
      finalVector: vector,
      layers,
    });
    console.error(
      `r${round}: ${samples.at(-1).milliseconds.toFixed(1)}ms ` +
      `rmse=${samples.at(-1).finalError.rmse.toFixed(6)}`,
    );
  }
  const measured = samples.slice(1);
  const report = {
    chrome: await browser.version(),
    context: 1,
    blocks: 12,
    connected: false,
    externalVectorTransfers: 11,
    loadMilliseconds: loadTimes.reduce((sum, value) => sum + value, 0),
    loadTimes,
    warmMedianMilliseconds: median(measured.map(({ milliseconds }) => milliseconds)),
    warmMinimumMilliseconds: Math.min(...measured.map(({ milliseconds }) => milliseconds)),
    warmMaximumMilliseconds: Math.max(...measured.map(({ milliseconds }) => milliseconds)),
    samples,
  };
  await fs.writeFile(
    new URL("staged-browser-results.json", experiment),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
