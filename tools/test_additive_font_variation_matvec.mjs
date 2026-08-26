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
  (process.env.ADDITIVE_MATVEC_SHAPES ?? manifest.sizes.map(({ label }) => label).join(","))
    .split(",").map((label) => label.trim()).filter(Boolean),
);
const sizes = manifest.sizes.filter(({ label }) => selected.has(label));
const rounds = Number(process.env.ADDITIVE_MATVEC_ROUNDS ?? 4);

function parseSettings(text) {
  const values = [];
  for (const match of text.matchAll(/"[A-Z0-9]{4}"\s+(-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)/gi)) {
    values.push(Number(match[1]));
  }
  return values;
}

function error(actual, expected) {
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
    for (const descriptor of sizes.map((_, index) => sizes[(index + round) % sizes.length])) {
      const reference = JSON.parse(await fs.readFile(
        new URL(`n${descriptor.label}.json`, base), "utf8",
      ));
      const loadStarted = performance.now();
      await page.goto(
        `http://127.0.0.1:4178/experiments/additive-font-variation-matvec/n${descriptor.label}.html?r=${round}`,
        { waitUntil: "load", timeout: 120000 },
      );
      const initial = parseSettings(await page.locator("#result").evaluate(
        (element) => getComputedStyle(element).fontVariationSettings,
      ));
      const loadMilliseconds = performance.now() - loadStarted;
      const mutations = [];
      for (let caseIndex = 1; caseIndex < reference.inputs.length; caseIndex += 1) {
        const started = performance.now();
        const actual = await page.locator("#result").evaluate((element, values) => {
          values.forEach((value, index) => element.style.setProperty(`--x${index}`, value));
          return getComputedStyle(element).fontVariationSettings;
        }, reference.inputs[caseIndex]);
        mutations.push({
          milliseconds: performance.now() - started,
          ...error(parseSettings(actual), reference.expected[caseIndex]),
        });
      }
      trials.push({
        label: descriptor.label,
        round,
        loadMilliseconds,
        initial: error(initial, reference.expected[0]),
        mutations,
      });
    }
  }
  const summary = {};
  for (const descriptor of sizes) {
    const samples = trials.filter(({ label }) => label === descriptor.label);
    const warm = samples.length > 1 ? samples.slice(1) : samples;
    const loads = warm.map(({ loadMilliseconds }) => loadMilliseconds).sort((a, b) => a - b);
    const mutations = warm.flatMap((trial) => trial.mutations.map(({ milliseconds }) => milliseconds))
      .sort((a, b) => a - b);
    const errors = warm.flatMap((trial) => [trial.initial, ...trial.mutations]);
    summary[descriptor.label] = {
      ...descriptor,
      warmLoadMedianMilliseconds: loads[Math.floor(loads.length / 2)],
      warmMutationMedianMilliseconds: mutations[Math.floor(mutations.length / 2)],
      rmseMaximum: Math.max(...errors.map(({ rmse }) => rmse)),
      maxErrorMaximum: Math.max(...errors.map(({ maxError }) => maxError)),
      finiteMinimum: Math.min(...errors.map(({ finite }) => finite), descriptor.outputSize),
    };
  }
  const report = { chrome: await browser.version(), rounds, trials, summary };
  await fs.writeFile(new URL("browser-results.json", base), JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
