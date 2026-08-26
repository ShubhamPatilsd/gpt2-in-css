import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const base = new URL("../experiments/anchor-swar-matvec/", import.meta.url);
const manifest = JSON.parse(await fs.readFile(new URL("manifest.json", base), "utf8"));
const rounds = Number(process.env.ANCHOR_SWAR_ROUNDS ?? 5);
const mutations = Number(process.env.ANCHOR_SWAR_MUTATIONS ?? 5);

function median(values) {
  const ordered = values.toSorted((a, b) => a - b);
  return ordered[Math.floor(ordered.length / 2)];
}

function error(actual, expected) {
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
      const variants = round % 2 ? ["pair", "scalar"] : ["scalar", "pair"];
      for (const variant of variants) {
        const started = performance.now();
        await page.goto(
          `http://127.0.0.1:4178/experiments/anchor-swar-matvec/${item.pages[variant].page}?r=${round}`,
          { waitUntil: "load", timeout: 180000 },
        );
        const initialWidths = await page.locator(".output").evaluateAll(
          (elements) => elements.map((element) => element.getBoundingClientRect().width),
        );
        const loadMilliseconds = performance.now() - started;
        const samples = [];
        for (let mutation = 0; mutation < mutations; mutation += 1) {
          const caseIndex = mutation % 2 === 0 ? 1 : 0;
          const widths = variant === "pair" ? item.pairWidths[caseIndex] : item.inputs[caseIndex];
          const mutationStarted = performance.now();
          const measured = await page.locator(".source").evaluateAll((elements, values) => {
            values.forEach((value, index) => { elements[index].style.width = `${value}px`; });
            return Array.from(document.querySelectorAll(".output"), (element) =>
              element.getBoundingClientRect().width);
          }, widths);
          samples.push({
            caseIndex,
            milliseconds: performance.now() - mutationStarted,
            ...error(measured.map((value) => value - item.outputBase), item.expected[caseIndex]),
          });
        }
        trials.push({
          round,
          shape: `${item.inputWidth}x${item.outputWidth}`,
          variant,
          loadMilliseconds,
          bytes: item.pages[variant].bytes,
          sources: variant === "pair" ? item.pairSources : item.scalarSources,
          terms: variant === "pair" ? item.pairTerms : item.scalarTerms,
          initial: error(
            initialWidths.map((value) => value - item.outputBase),
            item.expected[0],
          ),
          samples,
        });
      }
    }
  }

  const summary = {};
  for (const item of manifest) {
    const shape = `${item.inputWidth}x${item.outputWidth}`;
    summary[shape] = {};
    for (const variant of ["scalar", "pair"]) {
      const selected = trials.filter((trial) => trial.shape === shape && trial.variant === variant);
      const warm = selected.slice(1);
      summary[shape][variant] = {
        bytes: item.pages[variant].bytes,
        sources: variant === "pair" ? item.pairSources : item.scalarSources,
        terms: variant === "pair" ? item.pairTerms : item.scalarTerms,
        warmLoadMedianMilliseconds: median(warm.map((trial) => trial.loadMilliseconds)),
        warmMutationMedianMilliseconds: median(warm.flatMap((trial) =>
          trial.samples.slice(1).map((sample) => sample.milliseconds))),
        rmseMaximum: Math.max(...selected.flatMap((trial) =>
          [trial.initial.rmse, ...trial.samples.map((sample) => sample.rmse)])),
        maxErrorMaximum: Math.max(...selected.flatMap((trial) =>
          [trial.initial.maxError, ...trial.samples.map((sample) => sample.maxError)])),
      };
    }
    summary[shape].mutationSpeedup = summary[shape].scalar.warmMutationMedianMilliseconds /
      summary[shape].pair.warmMutationMedianMilliseconds;
  }
  report = { chrome: await browser.version(), rounds, mutations, trials, summary };
} finally {
  await browser.close();
}

await fs.writeFile(new URL("browser-results.json", base), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report.summary, null, 2));
