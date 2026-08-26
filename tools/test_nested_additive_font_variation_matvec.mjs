import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const base = new URL("../experiments/additive-font-variation-matvec/", import.meta.url);
const manifest = JSON.parse(await fs.readFile(new URL("manifest.json", base), "utf8"));
const selected = new Set(
  (process.env.NESTED_ADDITIVE_SHAPES ?? "32x32,64x64,128x128,256x256,512x512,768x768")
    .split(",").map((label) => label.trim()).filter(Boolean),
);
const shapes = manifest.sizes.filter(({ label }) => selected.has(label));
const rounds = Number(process.env.NESTED_ADDITIVE_ROUNDS ?? 4);
const extension = process.env.NESTED_ADDITIVE_EXTENSION ?? "html";
const layout = process.env.NESTED_ADDITIVE_LAYOUT ?? "nested";
if (!new Set(["nested", "one"]).has(layout)) throw new Error(`invalid layout ${layout}`);
const resultSelector = layout === "one" ? "#one-result" : "#nested-result";
const carrierSelector = layout === "one" ? ".one-carrier" : ".nested-carrier";

function parseSettings(text) {
  return Array.from(
    text.matchAll(/"[A-Z0-9]{4}"\s+(-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)/gi),
    (match) => Number(match[1]),
  );
}

function measureError(actual, expected) {
  const differences = actual.map((value, index) => value - expected[index]);
  return {
    finite: actual.filter(Number.isFinite).length,
    rmse: Math.sqrt(differences.reduce((sum, value) => sum + value * value, 0) / differences.length),
    maxError: Math.max(...differences.map(Math.abs)),
  };
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

try {
  const page = await browser.newPage();
  const trials = [];
  for (let round = 0; round < rounds; round += 1) {
    for (const descriptor of shapes.map((_, index) => shapes[(index + round) % shapes.length])) {
      const reference = JSON.parse(await fs.readFile(
        new URL(`n${descriptor.label}.json`, base), "utf8",
      ));
      const started = performance.now();
      await page.goto(
        `http://127.0.0.1:4178/experiments/additive-font-variation-matvec/n${descriptor.label}-${layout}.${extension}?r=${round}`,
        { waitUntil: "load", timeout: 120000 },
      );
      const initialText = await page.locator(resultSelector).evaluate(
        (element) => getComputedStyle(element).fontVariationSettings,
      );
      const loadMilliseconds = performance.now() - started;
      const mutationStarted = performance.now();
      const mutatedText = await page.evaluate(({ values, carrierSelector, resultSelector }) => {
        const carriers = document.querySelectorAll(carrierSelector);
        values.forEach((value, index) => {
          carriers[index].style.width = `${value * 100}px`;
        });
        return getComputedStyle(document.querySelector(resultSelector)).fontVariationSettings;
      }, { values: reference.inputs[1], carrierSelector, resultSelector });
      trials.push({
        label: descriptor.label,
        round,
        loadMilliseconds,
        mutationMilliseconds: performance.now() - mutationStarted,
        initial: measureError(parseSettings(initialText), reference.expected[0]),
        mutated: measureError(parseSettings(mutatedText), reference.expected[1]),
        domDepth: await page.locator(resultSelector).evaluate((element) => {
          let depth = 0;
          for (let node = element; node; node = node.parentElement) depth += 1;
          return depth;
        }),
      });
    }
  }
  const summary = {};
  for (const descriptor of shapes) {
    const samples = trials.filter(({ label }) => label === descriptor.label);
    const warm = samples.length > 1 ? samples.slice(1) : samples;
    const loads = warm.map(({ loadMilliseconds }) => loadMilliseconds).sort((a, b) => a - b);
    const mutations = warm.map(({ mutationMilliseconds }) => mutationMilliseconds).sort((a, b) => a - b);
    summary[descriptor.label] = {
      ...descriptor,
      domDepth: Math.min(...samples.map(({ domDepth }) => domDepth)),
      warmLoadMedianMilliseconds: loads[Math.floor(loads.length / 2)],
      warmMutationMedianMilliseconds: mutations[Math.floor(mutations.length / 2)],
      rmseMaximum: Math.max(...samples.flatMap(({ initial, mutated }) => [initial.rmse, mutated.rmse])),
      finiteMinimum: Math.min(...samples.flatMap(({ initial, mutated }) => [initial.finite, mutated.finite])),
    };
  }
  const report = { chrome: await browser.version(), rounds, extension, layout, trials, summary };
  await fs.writeFile(
    new URL(`${layout}-browser-results-${extension}.json`, base),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
