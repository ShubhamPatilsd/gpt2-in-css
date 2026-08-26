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
const rootUrl = process.env.HVAR_RASTER_QKV_URL ??
  "http://127.0.0.1:4178/experiments/hvar-raster-qkv-attention";
const rounds = Number.parseInt(process.env.HVAR_RASTER_QKV_ROUNDS ?? "5", 10);
const connectedFile = process.env.HVAR_RASTER_QKV_CONNECTED_FILE ?? "connected.html";
const qkvFile = process.env.HVAR_RASTER_QKV_FILE ?? "qkv-debug.html";
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/hvar-raster-qkv-attention/reference.json", import.meta.url,
), "utf8"));

function stats(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return {
    minimum: sorted[0],
    median: sorted[Math.floor(sorted.length / 2)],
    mean: values.reduce((sum, value) => sum + value, 0) / values.length,
    maximum: sorted.at(-1),
  };
}

function errors(actual, expected) {
  const delta = actual.flatMap((row, rowIndex) =>
    row.map((value, index) => value - expected[rowIndex][index]));
  return {
    rmse: Math.sqrt(delta.reduce((sum, value) => sum + value * value, 0) / delta.length),
    maxError: Math.max(...delta.map(Math.abs)),
  };
}

async function screenshot(page, file, selector, clip) {
  const started = performance.now();
  await page.goto(`${rootUrl}/${file}?run=${performance.now()}`, {
    waitUntil: "load", timeout: 180000,
  });
  await page.evaluate(() => document.fonts.ready);
  const locator = page.locator(selector);
  const png = clip
    ? await locator.screenshot({ clip, timeout: 180000 })
    : await locator.screenshot({ timeout: 180000 });
  return { png, milliseconds: performance.now() - started };
}

async function qkvSample(page) {
  const started = performance.now();
  await page.goto(`${rootUrl}/${qkvFile}?run=${performance.now()}`, {
    waitUntil: "load", timeout: 180000,
  });
  await page.evaluate(() => document.fonts.ready);
  const png = await page.screenshot({
    clip: { x: 0, y: 0, width: 64, height: 72 }, timeout: 180000,
  });
  const milliseconds = performance.now() - started;
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const actual = Array.from({ length: 2 }, (_, token) => {
    const values = [];
    for (let part = 0; part < 3; part += 1) {
      for (let head = 0; head < reference.heads; head += 1) {
        const row = token * 36 + part * reference.heads + head;
        for (let offset = 0; offset < reference.headWidth; offset += 1) {
          const index = part * reference.width + head * reference.headWidth + offset;
          const encoded = data[(row * info.width + offset) * info.channels] / 255;
          values[index] = (encoded - reference.surfaceCenter) * 2 * reference.qkvScales[index];
        }
      }
    }
    return values;
  });
  return { milliseconds, dimensions: [info.width, info.height], ...errors(actual, reference.expectedQkv) };
}

async function connectedSample(page) {
  const { png, milliseconds } = await screenshot(
    page, connectedFile, "#attention-output", { x: 0, y: 0, width: 768, height: 3 },
  );
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const actual = Array.from({ length: 2 }, (_, token) =>
    Array.from({ length: reference.width }, (_, index) => {
      const encoded = data[(token * info.width + index) * info.channels] / 255;
      return (encoded - reference.surfaceCenter) * 2 * reference.valueScales[index];
    }));
  const probabilities = Array.from({ length: reference.heads }, (_, head) =>
    data[(2 * info.width + head) * info.channels] / 255);
  return {
    milliseconds,
    dimensions: [info.width, info.height],
    ...errors(actual, reference.expectedContext),
    probabilityMaxError: Math.max(...probabilities.map((value, head) =>
      Math.abs(value - reference.expectedProbabilities[head]))),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const qkvPage = await browser.newPage({ viewport: { width: 1000, height: 200 } });
  const connectedPage = await browser.newPage({ viewport: { width: 1000, height: 200 } });
  await qkvSample(qkvPage);
  await connectedSample(connectedPage);
  const qkv = [];
  const connected = [];
  for (let round = 0; round < rounds; round += 1) {
    if (round % 2 === 0) {
      qkv.push(await qkvSample(qkvPage));
      connected.push(await connectedSample(connectedPage));
    } else {
      connected.push(await connectedSample(connectedPage));
      qkv.push(await qkvSample(qkvPage));
    }
  }
  const result = {
    rounds,
    qkv: {
      timing: stats(qkv.map((sample) => sample.milliseconds)),
      rmse: stats(qkv.map((sample) => sample.rmse)),
      maxError: Math.max(...qkv.map((sample) => sample.maxError)),
      dimensions: qkv[0].dimensions,
    },
    connected: {
      timing: stats(connected.map((sample) => sample.milliseconds)),
      rmse: stats(connected.map((sample) => sample.rmse)),
      maxError: Math.max(...connected.map((sample) => sample.maxError)),
      probabilityMaxError: Math.max(...connected.map((sample) => sample.probabilityMaxError)),
      dimensions: connected[0].dimensions,
    },
  };
  if (process.env.HVAR_RASTER_QKV_RESULT) {
    await fs.writeFile(process.env.HVAR_RASTER_QKV_RESULT, `${JSON.stringify(result, null, 2)}\n`);
  }
  console.log(JSON.stringify(result, null, 2));
  const invalidConnected = result.connected.rmse.median > 0.08
    || result.connected.probabilityMaxError > 0.1;
  if (result.qkv.rmse.median > 0.06
      || (invalidConnected && process.env.HVAR_RASTER_QKV_ALLOW_INVALID_CONNECTED !== "1")) {
    process.exitCode = 1;
  }
} finally {
  await browser.close();
}
