import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const mode = process.env.GRID_VECTOR_MODE ?? "grid";
const rounds = Number.parseInt(process.env.GRID_VECTOR_ROUNDS ?? "7", 10);
if (!["grid", "direct"].includes(mode)) throw new Error("mode must be grid or direct");

const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/grid-subgrid-vector/reference.json", import.meta.url),
  "utf8",
));

function settingText(values) {
  return values.map((value, index) =>
    `"X${String(index).padStart(3, "0")}" ${value}`).join(",");
}

function gelu(value) {
  return 0.5 * value * (1 + Math.tanh(
    Math.sqrt(2 / Math.PI) * (value + 0.044715 * value ** 3),
  ));
}

function stats(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    finite: actual.filter(Number.isFinite).length,
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

const mutationCases = reference.mutationCases.slice(0, rounds);

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 240 } });
  const url = mode === "grid"
    ? "http://127.0.0.1:4178/experiments/grid-subgrid-vector/index.html"
    : "http://127.0.0.1:4178/experiments/matrix-scaling/256/variable-font.html";
  const loadStarted = performance.now();
  await page.goto(url, { waitUntil: "load", timeout: 180000 });
  await page.evaluate(() => document.fonts.ready);
  const loadMilliseconds = performance.now() - loadStarted;

  const read = mode === "grid"
    ? () => page.locator(".consumer").evaluateAll((elements) => elements.map((element) => {
      const style = getComputedStyle(element);
      return [Number(style.getPropertyValue("--v")), Number(style.getPropertyValue("--g"))];
    }))
    : () => page.locator("#vf-result").evaluate((element, size) => {
      const style = getComputedStyle(element);
      return Array.from({ length: size }, (_, index) => [
        Number(style.getPropertyValue(`--vf-y-${String(index).padStart(3, "0")}`)),
        0,
      ]);
    }, reference.size);

  const initialPairs = await read();
  const initial = initialPairs.map(([value]) => value);
  const initialGelu = initialPairs.map(([, value]) => value);
  const samples = [];
  for (const testCase of mutationCases) {
    const started = performance.now();
    if (mode === "grid") {
      await page.locator("#bank").evaluate(
        (element, settings) => { element.style.fontVariationSettings = settings; },
        settingText(testCase.input),
      );
    } else {
      await page.evaluate((settings) => {
        for (const sheet of document.styleSheets) {
          for (const rule of sheet.cssRules) {
            if (rule.selectorText === ".metric") {
              rule.style.fontVariationSettings = settings;
              return;
            }
          }
        }
      }, settingText(testCase.input));
    }
    const pairs = await read();
    const actual = pairs.map(([value]) => value);
    const actualGelu = pairs.map(([, value]) => value);
    samples.push({
      milliseconds: performance.now() - started,
      values: stats(actual, testCase.expected),
      gelu: mode === "grid"
        ? stats(actualGelu, testCase.expected.map(gelu))
        : null,
    });
  }
  const times = samples.map(({ milliseconds }) => milliseconds).sort((a, b) => a - b);
  console.log(JSON.stringify({
    mode,
    loadMilliseconds,
    initial: stats(initial, reference.expected),
    initialGelu: mode === "grid" ? stats(initialGelu, reference.expected.map(gelu)) : null,
    mutationMedianMilliseconds: times[Math.floor(times.length / 2)],
    mutationMaximumMilliseconds: times.at(-1),
    samples,
    elements: await page.locator("*").count(),
  }, null, 2));
} finally {
  await browser.close();
}
