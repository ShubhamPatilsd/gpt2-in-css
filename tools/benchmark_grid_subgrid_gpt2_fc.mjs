import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const mode = process.env.GRID_GPT2_FC_MODE ?? "grid";
const rounds = Number.parseInt(process.env.GRID_GPT2_FC_ROUNDS ?? "7", 10);
if (!["grid", "timeline"].includes(mode)) throw new Error("mode must be grid or timeline");

const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/grid-subgrid-gpt2-fc/reference.json", import.meta.url),
  "utf8",
));

function settings(values, activationRange) {
  return values.map((value, index) => {
    const shard = Math.floor(index / 256);
    const local = index % 256;
    return `"${String.fromCharCode(65 + shard)}${String(local).padStart(3, "0")}" ${value / activationRange}`;
  }).join(",");
}

function stats(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    finite: actual.filter(Number.isFinite).length,
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

function median(values) {
  const ordered = [...values].sort((a, b) => a - b);
  return ordered[Math.floor(ordered.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 240 } });
  const url = mode === "grid"
    ? "http://127.0.0.1:4178/experiments/grid-subgrid-gpt2-fc/index.html"
    : "http://127.0.0.1:4178/experiments/gpt2-block-css/view-timeline-fc.html";
  const loadStarted = performance.now();
  await page.goto(url, { waitUntil: "load", timeout: 180000 });
  await page.evaluate(() => document.fonts.ready);
  const loadMilliseconds = performance.now() - loadStarted;

  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    const testCase = reference.cases[(round + 1) % reference.cases.length];
    const started = performance.now();
    let actual;
    if (mode === "grid") {
      await page.locator("#bank").evaluate(
        (element, value) => { element.style.fontVariationSettings = value; },
        settings(testCase.input, reference.activationRange),
      );
      actual = await page.locator(".consumer").evaluateAll((elements) =>
        elements.map((element) => Number(getComputedStyle(element).getPropertyValue("--hidden"))),
      );
    } else {
      actual = await page.evaluate(async ({ input, outputCount }) => {
        const scope = document.querySelector(".scope");
        input.forEach((value, index) => {
          scope.style.setProperty(`--n2-${String(index).padStart(3, "0")}`, String(value));
        });
        await new Promise((resolve) => requestAnimationFrame(resolve));
        await new Promise((resolve) => requestAnimationFrame(resolve));
        const style = getComputedStyle(document.getElementById("fc-result"));
        return Array.from({ length: outputCount }, (_, index) =>
          Number(style.getPropertyValue(`--hidden-${String(index).padStart(3, "0")}`)),
        );
      }, { input: testCase.input, outputCount: reference.outputs });
    }
    samples.push({
      milliseconds: performance.now() - started,
      error: stats(actual, testCase.hidden),
    });
  }
  const warm = samples.slice(1);
  const diagnostics = mode === "grid" ? await page.locator(".consumer").first().evaluate((element) => {
    const style = getComputedStyle(element);
    const cellStyle = getComputedStyle(element.parentElement);
    const metric = document.querySelector(".metric");
    const metricStyle = getComputedStyle(metric);
    return {
      cellWidth: cellStyle.width,
      metricWidth: metricStyle.width,
      metricInlineWidth: metric.style.width,
      pre: style.getPropertyValue("--pre"),
      t: style.getPropertyValue("--t"),
      hidden: style.getPropertyValue("--hidden"),
      width: style.width,
      gridColumns: getComputedStyle(document.getElementById("bank")).gridTemplateColumns.slice(0, 240),
    };
  }) : null;
  console.log(JSON.stringify({
    mode,
    chrome: await browser.version(),
    loadMilliseconds,
    mutationMedianMilliseconds: median(warm.map((sample) => sample.milliseconds)),
    mutationMinimumMilliseconds: Math.min(...warm.map((sample) => sample.milliseconds)),
    mutationMaximumMilliseconds: Math.max(...warm.map((sample) => sample.milliseconds)),
    medianRmse: median(warm.map((sample) => sample.error.rmse)),
    maximumError: Math.max(...warm.map((sample) => sample.error.maxError)),
    elements: await page.locator("*").count(),
    diagnostics,
    samples,
  }, null, 2));
} finally {
  await browser.close();
}
