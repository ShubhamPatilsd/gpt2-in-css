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
  (process.env.SHADOW_ADDITIVE_SHAPES ?? "768x768,3072x768")
    .split(",").map((label) => label.trim()).filter(Boolean),
);
const shapes = manifest.sizes.filter(({ label }) => selected.has(label));
const rounds = Number(process.env.SHADOW_ADDITIVE_ROUNDS ?? 3);

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
        `http://127.0.0.1:4178/experiments/additive-font-variation-matvec/n${descriptor.label}-shadow.html?r=${round}`,
        { waitUntil: "load", timeout: 120000 },
      );
      await page.waitForFunction(() => {
        let current = document.getElementById("shadow-root-base")?.shadowRoot;
        if (!current) return false;
        while (current) {
          const link = current.querySelector('link[rel="stylesheet"]');
          if (!link?.sheet) return false;
          const host = current.querySelector(".chunk-host");
          if (!host) return Boolean(current.getElementById("shadow-result"));
          current = host.shadowRoot;
        }
        return false;
      });
      await page.evaluate(() => new Promise(
        (resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ));
      const initial = await page.evaluate(() => {
        let current = document.getElementById("shadow-root-base").shadowRoot;
        let chunks = 1;
        const boundaries = [];
        while (current.querySelector(".chunk-host")) {
          const host = current.querySelector(".chunk-host");
          const next = host.shadowRoot;
          boundaries.push({
            inputs: Array.from(current.querySelectorAll(".one-carrier")).slice(0, 3)
              .map((element) => ({
                index: element.dataset.index,
                width: getComputedStyle(element).width,
                delay: getComputedStyle(element).animationDelay,
                name: getComputedStyle(element).animationName,
              })),
            host: getComputedStyle(host).fontVariationSettings.slice(0, 180),
            child: getComputedStyle(next.querySelector(".one-carrier"))
              .fontVariationSettings.slice(0, 180),
          });
          current = next;
          chunks += 1;
        }
        const result = current.getElementById("shadow-result");
        return {
          chunks,
          boundaries,
          settings: getComputedStyle(result).fontVariationSettings,
        };
      });
      const loadMilliseconds = performance.now() - started;
      const mutationStarted = performance.now();
      const mutatedText = await page.evaluate((values) => {
        let current = document.getElementById("shadow-root-base").shadowRoot;
        while (current) {
          for (const carrier of current.querySelectorAll(".one-carrier")) {
            const index = Number(carrier.dataset.index);
            carrier.style.width = `${values[index] * 100}px`;
          }
          const host = current.querySelector(".chunk-host");
          if (!host) {
            return getComputedStyle(current.getElementById("shadow-result")).fontVariationSettings;
          }
          current = host.shadowRoot;
        }
        throw new Error("missing shadow result");
      }, reference.inputs[1]);
      trials.push({
        label: descriptor.label,
        round,
        chunks: initial.chunks,
        boundaries: initial.boundaries,
        loadMilliseconds,
        mutationMilliseconds: performance.now() - mutationStarted,
        initial: error(parseSettings(initial.settings), reference.expected[0]),
        mutated: error(parseSettings(mutatedText), reference.expected[1]),
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
      chunks: samples[0].chunks,
      warmLoadMedianMilliseconds: loads[Math.floor(loads.length / 2)],
      warmMutationMedianMilliseconds: mutations[Math.floor(mutations.length / 2)],
      rmseMaximum: Math.max(...samples.flatMap(({ initial, mutated }) => [initial.rmse, mutated.rmse])),
      maxErrorMaximum: Math.max(...samples.flatMap(({ initial, mutated }) => [initial.maxError, mutated.maxError])),
    };
  }
  const report = { chrome: await browser.version(), rounds, trials, summary };
  await fs.writeFile(new URL("shadow-browser-results.json", base), JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
