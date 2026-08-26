import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const base = new URL("../experiments/anchor-swar-attention/", import.meta.url);
const manifest = JSON.parse(await fs.readFile(new URL("manifest.json", base), "utf8"));
const rounds = Number(process.env.SWAR_ATTENTION_ROUNDS ?? 4);
const selectedVariants = (process.env.SWAR_ATTENTION_VARIANTS ?? "scalar,pair")
  .split(",").map((value) => value.trim()).filter(Boolean);
if (selectedVariants.some((variant) => !new Set(["scalar", "pair"]).has(variant))) {
  throw new Error("SWAR_ATTENTION_VARIANTS must contain scalar and/or pair");
}

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
    for (const item of manifest) {
      const variants = (round % 2 ? ["pair", "scalar"] : ["scalar", "pair"])
        .filter((variant) => selectedVariants.includes(variant));
      for (const variant of variants) {
        const started = performance.now();
        await page.goto(
          `http://127.0.0.1:4178/experiments/anchor-swar-attention/${item.pages[variant].page}?r=${round}`,
          { waitUntil: "load", timeout: 180000 },
        );
        const read = () => page.locator(".output").evaluateAll((elements) =>
          elements.map((element) => element.getBoundingClientRect().width));
        const initial = (await read()).map((width) => width - item.outputBase);
        const loadMilliseconds = performance.now() - started;
        const qValues = variant === "pair" ? item.pairedQ : item.q;
        const kValues = variant === "pair" ? item.pairedK : item.k;
        const sourceBase = variant === "pair" ? item.pairBase : item.scalarBase;

        const queryStarted = performance.now();
        const queryOnly = await page.locator(".q").evaluateAll((elements, payload) => {
          payload.values.forEach((head, headIndex) => head.forEach((value, index) => {
            elements[headIndex * head.length + index].style.width = `${payload.base + value}px`;
          }));
          return Array.from(document.querySelectorAll(".output"), (element) =>
            element.getBoundingClientRect().width);
        }, { values: qValues[1], base: sourceBase });
        const queryMilliseconds = performance.now() - queryStarted;

        const fullStarted = performance.now();
        const full = await page.locator(".k").evaluateAll((elements, payload) => {
          let cursor = 0;
          payload.values.forEach((head) => head.forEach((token) => token.forEach((value) => {
            elements[cursor].style.width = `${payload.base + value}px`;
            cursor += 1;
          })));
          return Array.from(document.querySelectorAll(".output"), (element) =>
            element.getBoundingClientRect().width);
        }, { values: kValues[1], base: sourceBase });
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
          queryOnly: summarize(
            queryOnly.map((width) => width - item.outputBase), item.expectedQueryOnly,
          ),
          full: summarize(full.map((width) => width - item.outputBase), item.expectedFull),
        });
      }
    }
  }

  const summary = {};
  for (const item of manifest) {
    const shape = `${item.heads}x${item.tokens}`;
    summary[shape] = {};
    for (const variant of selectedVariants) {
      const selected = trials.filter((trial) => trial.shape === shape && trial.variant === variant);
      const warm = selected.slice(1);
      summary[shape][variant] = {
        sources: variant === "pair" ? item.pairSources : item.scalarSources,
        terms: variant === "pair" ? item.pairTerms : item.scalarTerms,
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
    if (summary[shape].scalar && summary[shape].pair) {
      summary[shape].querySpeedup = summary[shape].scalar.warmQueryMedianMilliseconds /
        summary[shape].pair.warmQueryMedianMilliseconds;
      summary[shape].fullSpeedup = summary[shape].scalar.warmFullMedianMilliseconds /
        summary[shape].pair.warmFullMedianMilliseconds;
    }
  }
  report = { chrome: await browser.version(), rounds, trials, summary };
} finally {
  await browser.close();
}

const resultSuffix = selectedVariants.length === 2 ? "" : `-${selectedVariants[0]}`;
await fs.writeFile(
  new URL(`browser-results${resultSuffix}.json`, base),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report.summary, null, 2));
