import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const directory = process.env.MULTIFACE_BANK_DIRECTORY ?? "multiface-metric-bank";
const rounds = Number.parseInt(process.env.MULTIFACE_BANK_ROUNDS ?? "8", 10);
const pageName = process.env.MULTIFACE_BANK_PAGE ?? "index.html";
const mutationMode = process.env.MULTIFACE_BANK_MUTATION ?? "toggle";
if (!["toggle", "unique"].includes(mutationMode)) {
  throw new Error("MULTIFACE_BANK_MUTATION must be toggle or unique");
}
const reference = JSON.parse(await fs.readFile(
  new URL(`../experiments/${directory}/reference.json`, import.meta.url),
  "utf8",
));

function settingText(values) {
  return values.map((value, index) =>
    `"X${String(index).padStart(3, "0")}" ${value}`).join(",");
}

function axisValues(values) {
  return reference.shifted ? values.map((value) => (value + 1) / 2) : values;
}

function errorStats(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    finite: actual.filter(Number.isFinite).length,
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

function matrixVector(weights, values) {
  return weights.map((row) => row.reduce(
    (sum, weight, index) => sum + weight * values[index],
    0,
  ));
}

const cases = Array.from({ length: rounds }, (_, round) => {
  if (mutationMode === "toggle") {
    const alternate = round % 2 === 0;
    return {
      values: alternate ? reference.alternateInputs : reference.inputs,
      expected: alternate ? reference.alternateExpected : reference.expected,
    };
  }
  const values = reference.inputs.map((value, index) => Math.max(-1, Math.min(
    1,
    value + (((index * 17 + (round + 1) * 13) % 9) - 4) / 64,
  )));
  return { values, expected: matrixVector(reference.weights, values) };
});

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
  const url = `http://127.0.0.1:4178/experiments/${directory}/${pageName}`;
  const started = performance.now();
  await page.goto(url, { waitUntil: "load", timeout: 180000 });
  await page.evaluate(() => document.fonts.ready);
  const loadMilliseconds = performance.now() - started;
  const structure = await page.locator("#result").evaluate((element) => {
    const classes = [];
    for (let current = element.parentElement; current; current = current.parentElement) {
      classes.push(current.className);
    }
    const style = getComputedStyle(element);
    return {
      ancestorCount: classes.length,
      nearestClasses: classes.slice(0, 8),
      furthestClasses: classes.slice(-8),
      stage0Output0: style.getPropertyValue("--s0-o0"),
      stage1Output0: style.getPropertyValue("--s1-o0"),
      finalOutput0: style.getPropertyValue("--o0"),
      shardElements: document.querySelectorAll(".shard").length,
    };
  });
  const read = () => page.locator("#result").evaluate((element, count) => {
    const style = getComputedStyle(element);
    return Array.from({ length: count }, (_, index) =>
      Number(style.getPropertyValue(`--o${index}`)));
  }, reference.outputWidth);
  const initial = await read();
  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    const { values, expected } = cases[round];
    const mutationStarted = performance.now();
    const encoded = axisValues(values);
    const settingsByShard = Array.from({ length: reference.shardCount ?? 1 }, (_, shard) =>
      settingText(encoded.slice(shard * reference.inputWidth, (shard + 1) * reference.inputWidth)));
    await page.locator("#bank").evaluate(
      (bank, next) => {
        const elements = bank.querySelectorAll(".shard");
        if (elements.length === 0) {
          bank.style.fontVariationSettings = next[0];
          return;
        }
        elements.forEach((element, index) => {
          element.style.fontVariationSettings = next[index];
        });
      },
      settingsByShard,
    );
    const actual = await read();
    samples.push({
      milliseconds: performance.now() - mutationStarted,
      ...errorStats(actual, expected),
    });
  }
  const times = samples.map((sample) => sample.milliseconds).sort((a, b) => a - b);
  console.log(JSON.stringify({
    directory,
    mutationMode,
    loadMilliseconds,
    structure,
    initial: errorStats(initial, reference.expected),
    mutationMedianMilliseconds: times[Math.floor(times.length / 2)],
    mutationMaximumMilliseconds: times.at(-1),
    samples,
  }, null, 2));
} finally {
  await browser.close();
}
