import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = process.env.SVG_BATCHED_ATTENTION_URL ??
  "http://127.0.0.1:4178/experiments/svg-multitoken-attention-batched";
const baselineUrl = process.env.SVG_BASELINE_ATTENTION_URL ??
  "http://127.0.0.1:4178/experiments/svg-multitoken-attention";
const baselineFile = process.env.SVG_BASELINE_ATTENTION_FILE ?? "index.html";
const scoreDebugUrl = process.env.SVG_SCORE_DEBUG_URL ?? baseUrl;
const referencePath = process.env.SVG_BATCHED_ATTENTION_REFERENCE ?? new URL(
  "../experiments/svg-multitoken-attention-batched/reference.json", import.meta.url,
);
const outputPath = process.env.SVG_BATCHED_ATTENTION_OUTPUT;
const trialCount = Number(process.env.SVG_ATTENTION_TRIALS ?? 9);
if (!Number.isInteger(trialCount) || trialCount < 2) {
  throw new Error("SVG_ATTENTION_TRIALS must be an integer of at least 2");
}
const reference = JSON.parse(await fs.readFile(referencePath, "utf8"));

function summary(actual, expected) {
  const errors = actual.flatMap((tokens, token) =>
    tokens.flatMap((head, h) => head.map((value, offset) =>
      value - expected[token][h][offset])));
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 256, height: 144 } });
  await page.goto(`${scoreDebugUrl}/score-debug.html?debug=${Date.now()}`, {
    waitUntil: "load", timeout: 180000,
  });
  const debugPng = await page.locator("svg").screenshot({ timeout: 180000 });
  const debugRaw = await sharp(debugPng).raw().toBuffer({ resolveWithObject: true });
  const debugDifferences = Array.from({ length: reference.heads }, (_, head) =>
    (debugRaw.data[head * debugRaw.info.channels] / 255 - reference.surfaceCenter)
      * 2 * reference.differenceRange);
  const runs = [];
  for (let trial = 0; trial < trialCount; trial += 1) {
    const started = performance.now();
    await page.goto(`${baseUrl}/index.html?trial=${trial}-${Date.now()}`, {
      waitUntil: "load", timeout: 180000,
    });
    const png = await page.locator("svg").screenshot({ timeout: 180000 });
    const milliseconds = performance.now() - started;
    const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
    const contexts = Array.from({ length: 2 }, (_, token) =>
      Array.from({ length: reference.heads }, (_, head) =>
        Array.from({ length: reference.headWidth }, (_, offset) => {
          const row = token * reference.heads + head;
          const x = head * reference.contextStride + offset;
          const code = data[(token * info.width + x) * info.channels] / 255;
          return (code - reference.surfaceCenter) * 2 * reference.valueScales[head][offset];
        })));
    const probabilities = Array.from({ length: reference.heads }, (_, head) =>
      data[(2 * info.width + head * reference.contextStride)
        * info.channels] / 255);
    runs.push({
      trial,
      milliseconds,
      ...summary(contexts, reference.expectedContext),
      probabilityMaxError: Math.max(...probabilities.map((value, head) =>
        Math.abs(value - reference.expectedProbabilities[head]))),
      probabilities,
    });
  }
  const baselineRuns = [];
  for (let trial = 0; trial < trialCount; trial += 1) {
    const started = performance.now();
    await page.goto(`${baselineUrl}/${baselineFile}?trial=${trial}-${Date.now()}`, {
      waitUntil: "load", timeout: 180000,
    });
    const png = await page.locator("svg").screenshot({ timeout: 180000 });
    const milliseconds = performance.now() - started;
    const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
    const contexts = Array.from({ length: 2 }, (_, token) =>
      Array.from({ length: reference.heads }, (_, head) =>
        Array.from({ length: reference.headWidth }, (_, offset) => {
          const index = head * reference.headWidth + offset;
          const code = data[(token * info.width + index) * info.channels] / 255;
          return (code - reference.surfaceCenter) * 2 * reference.valueScales[head][offset];
        })));
    const probabilities = Array.from({ length: reference.heads }, (_, head) =>
      data[(2 * info.width + head) * info.channels] / 255);
    baselineRuns.push({
      trial,
      milliseconds,
      ...summary(contexts, reference.expectedContext),
      probabilityMaxError: Math.max(...probabilities.map((value, head) =>
        Math.abs(value - reference.expectedProbabilities[head]))),
    });
  }
  const packedWarmMean = runs.slice(1).reduce(
    (sum, run) => sum + run.milliseconds, 0,
  ) / (trialCount - 1);
  const baselineWarmMean = baselineRuns.slice(1).reduce(
    (sum, run) => sum + run.milliseconds, 0,
  ) / (trialCount - 1);
  const payload = {
    scoreDebug: {
      actual: debugDifferences,
      expected: reference.expectedDifferences,
      maxError: Math.max(...debugDifferences.map((value, head) =>
        Math.abs(value - reference.expectedDifferences[head]))),
    },
    runs,
    warm: {
      meanMilliseconds: packedWarmMean,
      maxRmse: Math.max(...runs.slice(1).map((run) => run.rmse)),
      maxError: Math.max(...runs.slice(1).map((run) => run.maxError)),
      probabilityMaxError: Math.max(...runs.slice(1).map((run) => run.probabilityMaxError)),
    },
    baselineRuns,
    baselineWarm: {
      meanMilliseconds: baselineWarmMean,
      maxRmse: Math.max(...baselineRuns.slice(1).map((run) => run.rmse)),
      maxError: Math.max(...baselineRuns.slice(1).map((run) => run.maxError)),
      probabilityMaxError: Math.max(...baselineRuns.slice(1).map(
        (run) => run.probabilityMaxError,
      )),
    },
    speedup: baselineWarmMean / packedWarmMean,
  };
  if (outputPath) await fs.writeFile(outputPath, JSON.stringify(payload, null, 2) + "\n");
  console.log(JSON.stringify(payload, null, 2));
  if (payload.warm.maxRmse > 0.03 || payload.warm.probabilityMaxError > 0.06
    || payload.baselineWarm.maxRmse > 0.03) {
    process.exitCode = 1;
  }
} finally {
  await browser.close();
}
