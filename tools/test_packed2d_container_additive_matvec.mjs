import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const base = new URL("../experiments/additive-font-variation-matvec/", import.meta.url);
const shape = process.env.PACKED_2D_SHAPE ?? "3072x768";
const rounds = Number(process.env.PACKED_2D_ROUNDS ?? 5);
const mutationsPerLoad = Number(process.env.PACKED_2D_MUTATIONS ?? 5);
const reference = JSON.parse(await fs.readFile(new URL(`n${shape}.json`, base), "utf8"));

function parseSettings(text) {
  return Array.from(
    text.matchAll(/"[A-Z0-9]{4}"\s+(-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)/gi),
    (match) => Number(match[1]),
  );
}

function error(actual, expected) {
  const differences = actual.map((value, index) => value - expected[index]);
  return {
    finite: actual.filter(Number.isFinite).length,
    rmse: Math.sqrt(differences.reduce((sum, value) => sum + value * value, 0) / differences.length),
    maxError: Math.max(...differences.map(Math.abs)),
  };
}

function median(values) {
  const sorted = values.toSorted((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

const variants = [
  {
    name: "width-only-4-values",
    suffix: "packed",
    resultId: "packed-result",
    carrierClass: "packed-carrier",
    widthsKey: "packedWidths",
  },
  {
    name: "width-height-8-values",
    suffix: "packed2d",
    resultId: "packed2d-result",
    carrierClass: "packed2d-carrier",
    widthsKey: "packed2dWidths",
    heightsKey: "packed2dHeights",
  },
];

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

let report;
try {
  const page = await browser.newPage({ viewport: { width: 64, height: 64 } });
  const trials = [];
  for (let round = 0; round < rounds; round += 1) {
    const ordered = variants.map((_, index) => variants[(index + round) % variants.length]);
    for (const variant of ordered) {
      const loadStarted = performance.now();
      await page.goto(
        `http://127.0.0.1:4178/experiments/additive-font-variation-matvec/n${shape}-${variant.suffix}.xhtml?r=${round}`,
        { waitUntil: "load", timeout: 180000 },
      );
      const initialText = await page.locator(`#${variant.resultId}`).evaluate(
        (element) => getComputedStyle(element).fontVariationSettings,
      );
      const loadMilliseconds = performance.now() - loadStarted;

      const mutations = [];
      for (let mutation = 0; mutation < mutationsPerLoad; mutation += 1) {
        const caseIndex = mutation % 2 === 0 ? 1 : 0;
        const mutationStarted = performance.now();
        const mutatedText = await page.evaluate((payload) => {
          const carriers = document.querySelectorAll(`.${payload.carrierClass}`);
          payload.widths.forEach((width, index) => {
            carriers[index].style.width = `${width}px`;
            if (payload.heights) carriers[index].style.height = `${payload.heights[index]}px`;
          });
          return getComputedStyle(document.getElementById(payload.resultId)).fontVariationSettings;
        }, {
          carrierClass: variant.carrierClass,
          resultId: variant.resultId,
          widths: reference[variant.widthsKey][caseIndex],
          heights: variant.heightsKey ? reference[variant.heightsKey][caseIndex] : null,
        });
        mutations.push({
          caseIndex,
          milliseconds: performance.now() - mutationStarted,
          ...error(parseSettings(mutatedText), reference.packedExpected[caseIndex]),
        });
      }
      trials.push({
        round,
        variant: variant.name,
        loadMilliseconds,
        mutations,
        carriers: await page.locator(`.${variant.carrierClass}`).count(),
        domDepth: await page.locator(`#${variant.resultId}`).evaluate((element) => {
          let depth = 0;
          for (let node = element; node; node = node.parentElement) depth += 1;
          return depth;
        }),
        initial: error(parseSettings(initialText), reference.packedExpected[0]),
      });
    }
  }

  const summary = {};
  for (const variant of variants) {
    const samples = trials.filter((trial) => trial.variant === variant.name);
    const warm = samples.slice(1);
    summary[variant.name] = {
      carriers: samples[0].carriers,
      domDepth: samples[0].domDepth,
      warmLoadMedianMilliseconds: median(warm.map((sample) => sample.loadMilliseconds)),
      warmMutationMedianMilliseconds: median(warm.flatMap((sample) =>
        sample.mutations.slice(1).map((mutation) => mutation.milliseconds))),
      rmseMaximum: Math.max(...samples.flatMap((sample) =>
        [sample.initial.rmse, ...sample.mutations.map((mutation) => mutation.rmse)])),
      maxErrorMaximum: Math.max(...samples.flatMap((sample) =>
        [sample.initial.maxError, ...sample.mutations.map((mutation) => mutation.maxError)])),
    };
  }
  report = {
    chrome: await browser.version(),
    shape,
    rounds,
    mutationsPerLoad,
    trials,
    summary,
    mutationSpeedup: summary["width-only-4-values"].warmMutationMedianMilliseconds /
      summary["width-height-8-values"].warmMutationMedianMilliseconds,
  };
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("packed-1d-vs-2d-browser-results.json", base),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
