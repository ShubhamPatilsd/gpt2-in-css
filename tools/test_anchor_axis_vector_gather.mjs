import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const rounds = Number.parseInt(process.env.ANCHOR_AXIS_ROUNDS ?? "7", 10);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/anchor-axis-vector-gather/reference.json", import.meta.url),
  "utf8",
));

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
    finite: actual.filter(Number.isFinite).length,
  };
}

async function readProjection(page) {
  return page.locator(".output").evaluateAll((elements) => elements.map((element) =>
    element.getBoundingClientRect().width * 1000 / 512 - Number(element.dataset.base)));
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
let report;
try {
  const page = await browser.newPage({ viewport: { width: 64, height: 64 } });
  const started = performance.now();
  await page.goto("http://127.0.0.1:4178/experiments/anchor-axis-vector-gather/index.html", {
    waitUntil: "load",
    timeout: 180000,
  });
  await page.evaluate(() => document.fonts.ready);
  const computedFontVariationSettings = await page.locator("#projection").evaluate(
    (element) => getComputedStyle(element).fontVariationSettings,
  );
  const initial = await readProjection(page);
  const loadAndFirstEvaluationMilliseconds = performance.now() - started;
  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    const alternate = round % 2 === 0;
    const state = alternate ? reference.alternateState : reference.initialState;
    const expected = alternate ? reference.alternateExpected : reference.initialExpected;
    const mutationStarted = performance.now();
    await page.locator(".source").evaluateAll((elements, payload) => {
      for (let index = 0; index < elements.length; index += 1) {
        elements[index].style.width = `${payload.base + payload.scale * payload.state[index]}px`;
      }
    }, {
      base: reference.geometryBase,
      scale: reference.geometryScale,
      state,
    });
    const actual = await readProjection(page);
    samples.push({
      alternate,
      milliseconds: performance.now() - mutationStarted,
      ...summarize(actual, expected),
    });
  }
  const timings = samples.map(({ milliseconds }) => milliseconds).sort((a, b) => a - b);
  report = {
    axisExpressionAccepted: computedFontVariationSettings !== "normal",
    computedFontVariationSettings,
    loadAndFirstEvaluationMilliseconds,
    initial: summarize(initial, reference.initialExpected),
    mutationMedianMilliseconds: timings[Math.floor(timings.length / 2)],
    mutationMaximumMilliseconds: timings.at(-1),
    elements: await page.locator("*").count(),
    fontBytes: reference.fontBytes,
    htmlBytes: reference.htmlBytes,
    cssBytes: reference.cssBytes,
    samples,
  };
} finally {
  await browser.close();
}
await fs.writeFile(
  new URL("../experiments/anchor-axis-vector-gather/browser-results.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
