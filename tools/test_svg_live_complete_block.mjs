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
const directory = process.env.SVG_LIVE_BLOCK_DIRECTORY ?? "svg-live-complete-block";
const rounds = Number.parseInt(process.env.SVG_LIVE_BLOCK_ROUNDS ?? "5", 10);
const reference = JSON.parse(await fs.readFile(
  new URL(`../experiments/${directory}/reference.json`, import.meta.url),
  "utf8",
));

function stats(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return {
    minimum: sorted[0],
    median: sorted[Math.floor(sorted.length / 2)],
    mean: values.reduce((sum, value) => sum + value, 0) / values.length,
    maximum: sorted.at(-1),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 16, height: 768 } });
  await page.goto(
    `http://127.0.0.1:4178/experiments/${directory}/index.html`,
    { waitUntil: "load", timeout: 180000 },
  );
  await page.locator("svg").screenshot({ timeout: 180000 });
  const input = page.locator("feImage").first();
  const baseHref = (await input.getAttribute("href")).split("?")[0];
  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    const started = performance.now();
    await input.evaluate((image, payload) => {
      image.setAttribute("href", `${payload.baseHref}?recompute=${payload.round}`);
    }, { baseHref, round });
    const png = await page.locator("svg").screenshot({ timeout: 180000 });
    const milliseconds = performance.now() - started;
    const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
    const actual = reference.expected.map((_, row) =>
      (data[row * info.channels] / 255 - reference.surfaceCenter)
        * 2 * reference.finalScales[row]);
    const errors = actual.map((value, row) => value - reference.expected[row]);
    const mean = actual.reduce((sum, value) => sum + value, 0) / actual.length;
    const variance = actual.reduce(
      (sum, value) => sum + (value - mean) ** 2,
      0,
    ) / actual.length;
    const nextLnActual = actual.map((value, row) =>
      (value - mean) / Math.sqrt(variance + 1e-5) * reference.nextLnGamma[row]
        + reference.nextLnBeta[row]);
    const nextLnErrors = nextLnActual.map(
      (value, row) => value - reference.nextLnExpected[row],
    );
    samples.push({
      milliseconds,
      rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0)
        / errors.length),
      maxError: Math.max(...errors.map(Math.abs)),
      nextLnRmse: Math.sqrt(nextLnErrors.reduce(
        (sum, value) => sum + value * value,
        0,
      ) / nextLnErrors.length),
      nextLnMaxError: Math.max(...nextLnErrors.map(Math.abs)),
      clippedChannels: reference.expected.filter((_, row) => {
        const channel = data[row * info.channels];
        return channel === 0 || channel === 255;
      }).length,
    });
  }
  const html = await fs.readFile(
    new URL(`../experiments/${directory}/index.html`, import.meta.url),
    "utf8",
  );
  console.log(JSON.stringify({
    directory,
    rounds,
    timing: stats(samples.map((sample) => sample.milliseconds)),
    rmse: stats(samples.map((sample) => sample.rmse)),
    maxError: Math.max(...samples.map((sample) => sample.maxError)),
    nextLnRmse: stats(samples.map((sample) => sample.nextLnRmse)),
    nextLnMaxError: Math.max(...samples.map((sample) => sample.nextLnMaxError)),
    clippedChannels: samples[0].clippedChannels,
    htmlBytes: Buffer.byteLength(html),
    totalPrimitiveCount: [...html.matchAll(/<fe[A-Za-z]+/g)].length,
    samples,
  }, null, 2));
} finally {
  await browser.close();
}
