import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const contexts = (process.env.PROJECTED_KV_FULL_BLOCK_CONTEXTS ?? "16,32")
  .split(",").map(Number);
const rounds = Number(process.env.PROJECTED_KV_FULL_BLOCK_ROUNDS ?? 3);
const safeOutput = process.env.PROJECTED_KV_FULL_BLOCK_SAFE === "1";
const variant = process.env.PROJECTED_KV_FULL_BLOCK_VARIANT ??
  (safeOutput ? "safe" : "default");
const projectionTransport = process.env.PROJECTED_KV_FULL_BLOCK_PROJECTION ?? "timeline";
const scoreBackend = process.env.PROJECTED_KV_FULL_BLOCK_SCORE_BACKEND ?? "feature-kv";
if (!["timeline", "packet6", "packet8", "packet12"].includes(projectionTransport)) {
  throw new Error(`Unknown PROJECTED_KV_FULL_BLOCK_PROJECTION: ${projectionTransport}`);
}
if (!["default", "safe", "multitoken", "multitoken-direct"].includes(variant)) {
  throw new Error(`Unknown PROJECTED_KV_FULL_BLOCK_VARIANT: ${variant}`);
}
if (!["css-kv", "feature-kv", "bilinear-kv", "bilinear-sum-kv"].includes(scoreBackend)) {
  throw new Error(`Unknown PROJECTED_KV_FULL_BLOCK_SCORE_BACKEND: ${scoreBackend}`);
}
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);

function error(actual, expected) {
  const differences = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(differences.reduce((sum, value) => sum + value * value, 0) / differences.length),
    maxError: Math.max(...differences.map(Math.abs)),
  };
}

function median(values) {
  const sorted = values.toSorted((left, right) => left - right);
  return sorted[Math.floor(sorted.length / 2)];
}

async function readVector(page, selector, prefix) {
  return page.locator(selector).evaluate((element, propertyPrefix) => {
    const styles = getComputedStyle(element);
    return Array.from({ length: 768 }, (_, index) => Number.parseFloat(
      styles.getPropertyValue(`${propertyPrefix}${String(index).padStart(3, "0")}`),
    ));
  }, prefix);
}

const browser = await chromium.launch({ executablePath, headless: true });
const trials = [];
try {
  for (const context of contexts) {
    const projectionSuffix = projectionTransport === "timeline" ?
      "projected" : `projection-${projectionTransport}`;
    const scoreStem = scoreBackend === "css-kv" ? "css-kv-score" :
      scoreBackend === "feature-kv" ? "projected-kv-score" :
      scoreBackend === "bilinear-kv" ? "bilinear-kv-score" : "bilinear-sum-kv-score";
    const stem = `attention-context-${context}-geometry-streaming-flat-${scoreStem}-cached-value-live-current-kv-siblings-${projectionSuffix}-full-block0`;
    const pageStem = variant === "default" ? stem : `${stem}-${variant}`;
    const reference = JSON.parse(await fs.readFile(
      new URL(`${stem}-reference.json`, directory), "utf8",
    ));
    for (let round = 0; round < rounds; round += 1) {
      for (const isolated of [true, false]) {
        const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
        const file = isolated ? `${pageStem}-isolated.html` : `${pageStem}.html`;
        const started = performance.now();
        await page.goto(
          `http://127.0.0.1:4178/experiments/gpt2-block-css/${file}?round=${round}`,
          { waitUntil: "load", timeout: 180000 },
        );
        await page.evaluate(async () => {
          await document.fonts.ready;
          await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        });
        const output = await readVector(page, "#final", "--out-");
        const normalized = await readVector(page, ".after-attn", "--n2-");
        const attention = await readVector(
          page,
          isolated ? "#attention-isolated" : "#attention-result",
          variant === "multitoken-direct" ? "--r1-" : "--attention-r1-",
        );
        if (![...output, ...attention, ...normalized].every(Number.isFinite)) {
          const finiteCounts = Object.fromEntries([
            ["output", output],
            ["attention", attention],
            ["normalized", normalized],
          ].map(([name, values]) => [name, values.filter(Number.isFinite).length]));
          throw new Error(
            `${context} ${isolated ? "isolated" : "connected"} is non-finite: ` +
            JSON.stringify(finiteCounts),
          );
        }
        trials.push({
          context,
          isolated,
          round,
          milliseconds: performance.now() - started,
          output,
          modelError: error(output, reference.fullPrecisionPackedWeightReference),
          packedModelError: error(output, reference.packedReference),
          attentionError: error(attention, reference.attentionResidual),
          normalizedError: error(normalized, reference.normalized),
        });
        await page.close();
      }
    }
  }
} finally {
  await browser.close();
}

const summary = {};
for (const context of contexts) {
  const isolated = trials.filter((trial) => trial.context === context && trial.isolated);
  const connected = trials.filter((trial) => trial.context === context && !trial.isolated);
  const modelReference = JSON.parse(await fs.readFile(
    new URL(`attention-context-${context}-geometry-streaming-flat-${scoreBackend === "css-kv" ? "css-kv-score" : scoreBackend === "feature-kv" ? "projected-kv-score" : scoreBackend === "bilinear-kv" ? "bilinear-kv-score" : "bilinear-sum-kv-score"}-cached-value-live-current-kv-siblings-${projectionTransport === "timeline" ? "projected" : `projection-${projectionTransport}`}-full-block0-reference.json`, directory),
    "utf8",
  )).fullPrecisionPackedWeightReference;
  const worstModelErrors = isolated[0].output.map((value, index) => ({
    index,
    value,
    reference: modelReference[index],
    absoluteError: Math.abs(value - modelReference[index]),
  })).toSorted((left, right) => right.absoluteError - left.absoluteError).slice(0, 8);
  summary[context] = {
    isolatedWarmMedianMilliseconds: median(isolated.slice(1).map(({ milliseconds }) => milliseconds)),
    connectedWarmMedianMilliseconds: median(connected.slice(1).map(({ milliseconds }) => milliseconds)),
    connectedAttentionRmse: connected[0].attentionError.rmse,
    isolatedNormalizedRmse: isolated[0].normalizedError.rmse,
    connectedNormalizedRmse: connected[0].normalizedError.rmse,
    isolatedModelRmse: isolated[0].modelError.rmse,
    connectedModelRmse: connected[0].modelError.rmse,
    isolatedPackedModelRmse: isolated[0].packedModelError.rmse,
    connectedPackedModelRmse: connected[0].packedModelError.rmse,
    connectedVsIsolatedRmse: error(connected[0].output, isolated[0].output).rmse,
    connectedVsIsolatedMaxError: error(connected[0].output, isolated[0].output).maxError,
    isolatedOutputFirst5: isolated[0].output.slice(0, 5),
    modelReferenceFirst5: modelReference.slice(0, 5),
    worstModelErrors,
  };
}
const report = {
  chrome: await browser.version(),
  contexts,
  rounds,
  runtimeJavaScript: false,
  safeOutput,
  variant,
  projectionTransport,
  scoreBackend,
  summary,
  trials: trials.map(({ output, ...trial }) => trial),
};
await fs.writeFile(
  new URL(
    `projected-kv-full-block0-browser-${scoreBackend}-${projectionTransport}-${variant}.json`,
    directory,
  ),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(summary, null, 2));
