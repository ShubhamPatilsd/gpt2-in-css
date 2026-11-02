import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number(process.env.ATTENTION_SCORE_ROUNDS ?? 5);
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);
const variants = [
  {
    name: "css",
    page: "view-timeline-attention-2token.html",
    reference: "view-timeline-attention-2token-reference.json",
  },
  {
    name: "bilinear",
    page: "view-timeline-attention-2token-bilinear.html",
    reference: "view-timeline-attention-2token-bilinear-reference.json",
  },
  {
    name: "qkv-container",
    page: "view-timeline-attention-2token-qkv-container.html",
    reference: "view-timeline-attention-2token-qkv-container-reference.json",
  },
];
for (const variant of variants) {
  const reference = JSON.parse(await fs.readFile(
    new URL(variant.reference, directory), "utf8",
  ));
  variant.expected = reference.residual;
  variant.expectedScores = reference.scores[1].flatMap((head) => head.slice(0, 2));
}

function median(values) {
  const ordered = values.toSorted((a, b) => a - b);
  return ordered[Math.floor(ordered.length / 2)];
}

function summarize(actual, expected) {
  const errors = actual.flatMap((row, token) =>
    row.map((value, index) => value - expected[token][index]));
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
  const trials = [];
  for (let round = 0; round < rounds; round += 1) {
    const order = round % 2 ? variants.toReversed() : variants;
    for (const variant of order) {
      const started = performance.now();
      await page.goto(
        `http://127.0.0.1:4178/experiments/gpt2-block-css/${variant.page}?round=${round}`,
        { waitUntil: "load", timeout: 180000 },
      );
      const observed = await page.locator("#attention-result").evaluate((element) => {
        const styles = getComputedStyle(element);
        return {
          values: Array.from({ length: 2 }, (_, token) =>
            Array.from({ length: 768 }, (_, index) => Number.parseFloat(
            styles.getPropertyValue(`--r1-${token}-${String(index).padStart(3, "0")}`),
          ))),
          scores: Array.from({ length: 12 }, (_, head) =>
            Array.from({ length: 2 }, (_, source) => Number.parseFloat(
              styles.getPropertyValue(`--score-${head}-${source}`),
            ))).flat(),
        };
      });
      const milliseconds = performance.now() - started;
      if (observed.values.some((row) => row.some((value) => !Number.isFinite(value))) ||
          observed.scores.some((value) => !Number.isFinite(value))) {
        throw new Error(`${variant.name} returned a non-finite value`);
      }
      const residualError = summarize(observed.values, variant.expected);
      const scoreError = summarize([observed.scores], [variant.expectedScores]);
      trials.push({
        round,
        variant: variant.name,
        milliseconds,
        residual: residualError,
        scores: scoreError,
      });
    }
  }
  const summary = {};
  for (const variant of variants) {
    const selected = trials.filter((trial) => trial.variant === variant.name);
    const warm = selected.slice(1);
    summary[variant.name] = {
      warmMedianMilliseconds: median(warm.map((trial) => trial.milliseconds)),
      residualRmseMaximum: Math.max(...selected.map((trial) => trial.residual.rmse)),
      residualMaxErrorMaximum: Math.max(...selected.map((trial) => trial.residual.maxError)),
      scoreRmseMaximum: Math.max(...selected.map((trial) => trial.scores.rmse)),
      scoreMaxErrorMaximum: Math.max(...selected.map((trial) => trial.scores.maxError)),
    };
  }
  summary.bilinear.speedup = summary.css.warmMedianMilliseconds /
    summary.bilinear.warmMedianMilliseconds;
  summary["qkv-container"].speedup = summary.css.warmMedianMilliseconds /
    summary["qkv-container"].warmMedianMilliseconds;
  report = { chrome: await browser.version(), rounds, trials, summary };
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("view-timeline-attention-2token-score-backends-browser.json", directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report.summary, null, 2));
