import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/direct-css-block/reference.json", import.meta.url,
), "utf8"));
const rounds = Number(process.env.DIRECT_CSS_MATRIX_ROUNDS ?? 7);

function median(values) {
  const ordered = values.toSorted((a, b) => a - b);
  return ordered[Math.floor(ordered.length / 2)];
}

function error(actual, expected) {
  const differences = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(differences.reduce((sum, value) => sum + value * value, 0) / differences.length),
    maxError: Math.max(...differences.map(Math.abs)),
  };
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
let report;
try {
  const page = await browser.newPage({ viewport: { width: 64, height: 64 } });
  const started = performance.now();
  await page.goto(
    "http://127.0.0.1:4178/experiments/direct-css-block/matrix.html",
    { waitUntil: "load", timeout: 180000 },
  );
  const initial = await page.locator(".sink").evaluateAll((elements) =>
    elements.map((element) => element.getBoundingClientRect().width - 1000));
  const loadMilliseconds = performance.now() - started;
  const initialError = error(initial, reference.matrix_expected);
  const model = page.locator(".model");
  const original = await model.evaluate((element) => Number.parseFloat(
    getComputedStyle(element).getPropertyValue("--i0"),
  ));
  const trials = [];
  let previous = initial;
  for (let round = 0; round < rounds; round += 1) {
    const value = original + (round % 2 ? 0 : 0.125);
    const mutationStarted = performance.now();
    const actual = await model.evaluate((element, next) => {
      element.style.setProperty("--i0", `${next}`);
      return Array.from(element.querySelectorAll(".sink"), (sink) =>
        sink.getBoundingClientRect().width - 1000);
    }, value);
    trials.push({
      round,
      milliseconds: performance.now() - mutationStarted,
      changed: actual.filter((entry, index) => entry !== previous[index]).length,
      finite: actual.filter(Number.isFinite).length,
    });
    previous = actual;
  }
  report = {
    chrome: await browser.version(),
    matrix: "768x768",
    terms: reference.matrix_terms,
    cssBytes: reference.matrix_css_bytes,
    loadMilliseconds,
    initialError,
    trials,
    warmMedianMilliseconds: median(trials.slice(1).map((trial) => trial.milliseconds)),
  };
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("../experiments/direct-css-block/matrix-mutation-browser.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
