import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const sharp = require(`${root}/sharp`);
const outputs = Number.parseInt(process.env.GVAR_VECTOR_OUTPUTS ?? "256", 10);
const rounds = Number.parseInt(process.env.GVAR_VECTOR_ROUNDS ?? "7", 10);
const stem = `n${outputs}`;
const reference = JSON.parse(await fs.readFile(
  new URL(`../experiments/gvar-vector-glyph/${stem}-reference.json`, import.meta.url), "utf8"));

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
    finite: actual.filter(Number.isFinite).length,
  };
}

async function readVector(page) {
  const png = await page.locator("#surface").screenshot({ omitBackground: true, timeout: 180000 });
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: outputs }, (_, y) =>
    data[(y * info.width + reference.barWidth - 1) * info.channels] / 255
      * 2 * reference.base - reference.base);
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
let report;
try {
  const page = await browser.newPage({ viewport: { width: 300, height: outputs } });
  const started = performance.now();
  await page.goto(`http://127.0.0.1:4178/experiments/gvar-vector-glyph/${stem}.html`, {
    waitUntil: "load", timeout: 180000,
  });
  await page.evaluate(() => document.fonts.ready);
  const initial = await readVector(page);
  const loadAndFirstPaintMilliseconds = performance.now() - started;
  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    const alternate = round % 2 === 0;
    const value = alternate ? reference.alternateSettings : reference.initialSettings;
    const expected = alternate ? reference.alternateExpected : reference.initialExpected;
    const mutationStarted = performance.now();
    await page.locator("#bank").evaluate((element, settings) => {
      element.style.fontVariationSettings = settings;
    }, value);
    const actual = await readVector(page);
    samples.push({ alternate, milliseconds: performance.now() - mutationStarted, ...summarize(actual, expected) });
  }
  const timings = samples.map(({ milliseconds }) => milliseconds).sort((a, b) => a - b);
  report = {
    outputs,
    loadAndFirstPaintMilliseconds,
    initial: summarize(initial, reference.initialExpected),
    initialSamples: initial.slice(0, 12).map((actual, index) => ({
      index,
      actual,
      expected: reference.initialExpected[index],
    })),
    mutationMedianMilliseconds: timings[Math.floor(timings.length / 2)],
    mutationMaximumMilliseconds: timings.at(-1),
    fontBytes: reference.fontBytes,
    htmlBytes: reference.htmlBytes,
    elements: await page.locator("*").count(),
    samples,
  };
} finally {
  await browser.close();
}
await fs.writeFile(
  new URL(`../experiments/gvar-vector-glyph/${stem}-browser-results.json`, import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
