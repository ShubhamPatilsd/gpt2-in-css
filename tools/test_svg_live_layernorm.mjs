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
const directory = process.env.SVG_LIVE_LN_DIRECTORY ?? "svg-live-layernorm";
const rounds = Number.parseInt(process.env.SVG_LIVE_LN_ROUNDS ?? "5", 10);
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
    const liveX = reference.liveX ?? 0;
    const actual = reference.expected.map((_, row) => {
      const scale = reference.qkvInputScales?.[row] ?? reference.outputRange;
      return (data[(row * info.width + liveX) * info.channels] / 255
        - reference.surfaceCenter) * 2 * scale;
    });
    const errors = actual.map((value, row) => value - reference.expected[row]);
    samples.push({
      milliseconds,
      rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0)
        / errors.length),
      maxError: Math.max(...errors.map(Math.abs)),
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
    htmlBytes: Buffer.byteLength(html),
    totalPrimitiveCount: [...html.matchAll(/<fe[A-Za-z]+/g)].length,
    samples,
  }, null, 2));
} finally {
  await browser.close();
}
