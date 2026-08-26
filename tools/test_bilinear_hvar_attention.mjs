import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const base = new URL("../experiments/bilinear-hvar-attention/", import.meta.url);
const manifest = JSON.parse(await fs.readFile(new URL("manifest.json", base), "utf8"));
const rounds = Number(process.env.BILINEAR_HVAR_ROUNDS ?? 4);
const selectedVariants = (process.env.BILINEAR_HVAR_VARIANTS ?? manifest.variants.join(","))
  .split(",").map((value) => value.trim()).filter(Boolean);

function median(values) {
  const ordered = values.toSorted((a, b) => a - b);
  return ordered[Math.floor(ordered.length / 2)];
}

function summarize(actual, expected) {
  const differences = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(differences.reduce((sum, value) => sum + value * value, 0) / differences.length),
    maxError: Math.max(...differences.map(Math.abs)),
    finite: actual.filter(Number.isFinite).length,
  };
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
let report;
try {
  const page = await browser.newPage({ viewport: { width: 64, height: 64 } });
  const trials = [];
  for (let round = 0; round < rounds; round += 1) {
    for (const item of manifest.cases) {
      const variants = (round % 2 ? selectedVariants.toReversed() : selectedVariants);
      for (const variant of variants) {
        const pageSpec = item.pages[variant];
        if (!pageSpec) throw new Error(`unknown bilinear HVAR variant: ${variant}`);
        const started = performance.now();
        await page.goto(
          `http://127.0.0.1:4178/experiments/bilinear-hvar-attention/${pageSpec.page}?r=${round}`,
          { waitUntil: "load", timeout: 180000 },
        );
        await page.evaluate(() => document.fonts.ready);
        const read = () => page.locator(".score").evaluateAll((elements) =>
          elements.map((element) => element.getBoundingClientRect().width));
        const decode = (widths) => widths.map((width) =>
          (width * item.unitsPerEm / item.fontSize - pageSpec.outputBase) * pageSpec.decodeScale);
        const initial = decode(await read());
        const loadMilliseconds = performance.now() - started;

        const queryStarted = performance.now();
        const queryWidths = await page.locator(".head").evaluateAll((elements, payload) => {
          payload.values.forEach((head, headIndex) => head.forEach((value, index) => {
            elements[headIndex].style.setProperty(`--q${index}`, `${value / payload.valueMax}`);
          }));
          return Array.from(document.querySelectorAll(".score"), (element) =>
            element.getBoundingClientRect().width);
        }, { values: item.q[1], valueMax: item.valueMax });
        const queryMilliseconds = performance.now() - queryStarted;

        const fullStarted = performance.now();
        const fullWidths = await page.locator(".score").evaluateAll((elements, payload) => {
          let cursor = 0;
          payload.values.forEach((head) => head.forEach((token) => {
            token.forEach((value, index) => {
              elements[cursor].style.setProperty(`--k${index}`, `${value / payload.valueMax}`);
            });
            cursor += 1;
          }));
          return elements.map((element) => element.getBoundingClientRect().width);
        }, { values: item.k[1], valueMax: item.valueMax });
        const fullMilliseconds = performance.now() - fullStarted;

        trials.push({
          round,
          shape: `${item.heads}x${item.tokens}`,
          variant,
          loadMilliseconds,
          queryMilliseconds,
          fullMilliseconds,
          elements: await page.locator("*").count(),
          initial: summarize(initial, item.expectedInitial),
          queryOnly: summarize(decode(queryWidths), item.expectedQueryOnly),
          full: summarize(decode(fullWidths), item.expectedFull),
        });
      }
    }
  }

  const summary = {};
  for (const item of manifest.cases) {
    const shape = `${item.heads}x${item.tokens}`;
    summary[shape] = {};
    for (const variant of selectedVariants) {
      const selected = trials.filter((trial) => trial.shape === shape && trial.variant === variant);
      const warm = selected.slice(1);
      summary[shape][variant] = {
        scores: item.heads * item.tokens,
        elements: selected[0].elements,
        bytes: item.pages[variant].bytes,
        warmLoadMedianMilliseconds: median(warm.map((trial) => trial.loadMilliseconds)),
        warmQueryMedianMilliseconds: median(warm.map((trial) => trial.queryMilliseconds)),
        warmFullMedianMilliseconds: median(warm.map((trial) => trial.fullMilliseconds)),
        rmseMaximum: Math.max(...selected.flatMap((trial) =>
          [trial.initial.rmse, trial.queryOnly.rmse, trial.full.rmse])),
        maxErrorMaximum: Math.max(...selected.flatMap((trial) =>
          [trial.initial.maxError, trial.queryOnly.maxError, trial.full.maxError])),
      };
    }
  }
  report = { chrome: await browser.version(), rounds, fonts: manifest.fonts, trials, summary };
} finally {
  await browser.close();
}

const resultSuffix = selectedVariants.length === manifest.variants.length
  ? ""
  : `-${selectedVariants.join("-")}`;
await fs.writeFile(
  new URL(`browser-results${resultSuffix}.json`, base),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report.summary, null, 2));
