import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/font-multimetric-probe/reference.json", import.meta.url), "utf8"));

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
  const trials = [];
  for (let trial = 0; trial < 12; trial += 1) {
    const started = performance.now();
    await page.goto(`http://127.0.0.1:4178/experiments/font-multimetric-probe/index.html?trial=${trial}`, {
      waitUntil: "load",
      timeout: 120000,
    });
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const values = await page.evaluate((count) => {
      const style = getComputedStyle(document.querySelector("#result"));
      return Array.from({ length: count }, (_, index) =>
        Number(style.getPropertyValue(`--o${index}`)));
    }, reference.channels.length);
    trials.push({ milliseconds: performance.now() - started, values });
  }
  const errors = trials.at(-1).values.map((value, index) => value - reference.expected[index]);
  const warm = trials.slice(2).map((trial) => trial.milliseconds).sort((a, b) => a - b);
  const recomputes = await page.evaluate(({ inputs, weights, channels }) => {
    const producer = document.querySelector(".producer");
    const result = document.querySelector("#result");
    const axis = (index) => `X${String(index).padStart(3, "0")}`;
    const samples = [];
    const batches = [];
    for (let batch = 0; batch < 10; batch += 1) {
      const batchStarted = performance.now();
      for (let iteration = 0; iteration < 200; iteration += 1) {
        const next = [...inputs];
        next[0] = iteration % 2 === 0 ? -1 : 1;
        const settings = next.map((value, index) => `"${axis(index)}" ${value}`).join(",");
        const started = performance.now();
        producer.style.fontVariationSettings = settings;
        const style = getComputedStyle(result);
        const values = channels.map((_, index) => Number(style.getPropertyValue(`--o${index}`)));
        const milliseconds = performance.now() - started;
        const expected = weights.map((row) => row.reduce((sum, weight, index) => sum + weight * next[index], 0));
        samples.push({ milliseconds, values, expected });
      }
      batches.push(performance.now() - batchStarted);
    }
    return { samples, batches };
  }, { inputs: reference.inputs, weights: reference.weights, channels: reference.channels });
  const recomputeTimes = recomputes.samples.slice(2).map((sample) => sample.milliseconds).sort((a, b) => a - b);
  const batchTimes = [...recomputes.batches].sort((a, b) => a - b);
  const recomputeErrors = recomputes.samples.flatMap((sample) =>
    sample.values.slice(0, 5).map((value, index) => value - sample.expected[index]));
  const vvarGeometry = await page.evaluate(({ base, fontSize, unitsPerEm, inputs }) => {
    const axis = (index) => `X${String(index).padStart(3, "0")}`;
    document.querySelector(".producer").style.fontVariationSettings = inputs
      .map((value, index) => `"${axis(index)}" ${value}`).join(",");
    const scale = fontSize / unitsPerEm;
    return {
      zeroDelta: document.querySelector("#vzero").getBoundingClientRect().height / scale - base,
      waterDelta: document.querySelector("#vwater").getBoundingClientRect().height / scale - base,
    };
  }, { base: reference.base, fontSize: reference.font_size, unitsPerEm: reference.units_per_em,
    inputs: reference.inputs });
  const orientationAttempts = await page.evaluate(() => {
    const read = (selector) => {
      const style = getComputedStyle(document.querySelector(selector));
      return [Number(style.getPropertyValue("--o5")), Number(style.getPropertyValue("--o6"))];
    };
    return { mixed: read("#result"), upright: read("#upright-result") };
  });
  const varying = reference.channels.map((channel, index) => ({
    channel,
    expected: reference.expected[index],
    actual: trials.at(-1).values[index],
    error: errors[index],
  }));
  const successfulErrors = errors.slice(0, 5);
  console.log(JSON.stringify({
    noJavaScript: !(await fs.readFile(new URL("../experiments/font-multimetric-probe/index.html", import.meta.url), "utf8")).toLowerCase().includes("<script"),
    channels: varying,
    successfulChannelRmse: Math.sqrt(successfulErrors.reduce((sum, error) => sum + error * error, 0) / successfulErrors.length),
    successfulChannelMaxError: Math.max(...successfulErrors.map(Math.abs)),
    warmMilliseconds: {
      samples: warm.length,
      min: warm[0],
      median: warm[Math.floor((warm.length - 1) / 2)],
      max: warm.at(-1),
    },
    forcedRecomputeMilliseconds: {
      samples: recomputeTimes.length,
      min: recomputeTimes[0],
      median: recomputeTimes[Math.floor((recomputeTimes.length - 1) / 2)],
      max: recomputeTimes.at(-1),
      medianBatchOf200: batchTimes[Math.floor((batchTimes.length - 1) / 2)],
      medianBatchPerUpdate: batchTimes[Math.floor((batchTimes.length - 1) / 2)] / 200,
    },
    forcedRecomputeFirstFiveMaxError: Math.max(...recomputeErrors.map(Math.abs)),
    vvarGeometry,
    orientationAttempts,
  }, null, 2));
} finally {
  await browser.close();
}
