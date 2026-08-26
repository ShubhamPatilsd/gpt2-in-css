import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

const stats = (values, expected, channels) => {
  const errors = values.map((value, index) => value - expected[index]);
  const byChannel = channels.map((name, channel) => {
    const selected = errors.filter((_, index) => index % channels.length === channel);
    return {
      channel: name,
      rmse: Math.sqrt(selected.reduce((sum, error) => sum + error * error, 0) / selected.length),
      maxError: Math.max(...selected.map(Math.abs)),
    };
  });
  return {
    finite: values.filter(Number.isFinite).length,
    rmse: Math.sqrt(errors.reduce((sum, error) => sum + error * error, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
    byChannel,
  };
};

try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 400 } });
  const browserMessages = [];
  page.on("console", (message) => browserMessages.push({
    type: message.type(), text: message.text(),
  }));
  const results = {};
  const fixtureNames = (process.env.ROW_AXIS_TEST_FIXTURES ??
    "small,scale,trigger,outputs768-i16shift,outputs768-i32shift," +
    "outputs768-i64shift,outputs768-i64,outputs768-i128,outputs768-i256")
    .split(",").map((name) => name.trim()).filter(Boolean);
  const navigationRounds = Number(process.env.ROW_AXIS_NAV_ROUNDS ?? 10);
  const mutationBatchesCount = Number(process.env.ROW_AXIS_MUTATION_BATCHES ?? 8);
  const mutationIterations = Number(process.env.ROW_AXIS_MUTATION_ITERATIONS ?? 100);
  const fontFormat = process.env.ROW_AXIS_FONT_FORMAT ?? "ttf";
  if (!["ttf", "woff", "woff2"].includes(fontFormat)) {
    throw new Error(`unknown font format: ${fontFormat}`);
  }
  for (const name of fixtureNames) {
    const reference = JSON.parse(await fs.readFile(
      new URL(`../experiments/row-axis-multimetric/${name}.json`, import.meta.url), "utf8"));
    const trials = [];
    for (let trial = 0; trial < navigationRounds; trial += 1) {
      const started = performance.now();
      const pageName = fontFormat === "ttf" ? name : `${name}-${fontFormat}`;
      await page.goto(`http://127.0.0.1:4178/experiments/row-axis-multimetric/${pageName}.html?t=${trial}`, {
        waitUntil: "load", timeout: 120000,
      });
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      });
      const values = await page.evaluate((count) => {
        const style = getComputedStyle(document.querySelector("#result"));
        return Array.from({ length: count }, (_, index) =>
          Number(style.getPropertyValue(`--o${String(index).padStart(3, "0")}`)));
      }, reference.expected.length);
      trials.push({ milliseconds: performance.now() - started, values });
    }
    const warm = trials.slice(1).map((trial) => trial.milliseconds).sort((a, b) => a - b);
    const mutationBatches = await page.evaluate(({
      weights, inputs, outputs, batchesCount, iterations,
    }) => {
      const root = document.querySelector(".root");
      const result = document.querySelector("#result");
      const batches = [];
      let latest = [];
      for (let batch = 0; batch < batchesCount; batch += 1) {
        const started = performance.now();
        for (let iteration = 0; iteration < iterations; iteration += 1) {
          const value = iteration % 2 === 0 ? -1 : 1;
          root.style.setProperty("--x000", value);
          const style = getComputedStyle(result);
          latest = Array.from({ length: outputs }, (_, index) =>
            Number(style.getPropertyValue(`--o${String(index).padStart(3, "0")}`)));
        }
        batches.push(performance.now() - started);
      }
      const finalInputs = [...inputs];
      finalInputs[0] = 1;
      const expected = weights.flatMap((group) => group.map((row) =>
        row.reduce((sum, weight, index) => sum + weight * finalInputs[index], 0)));
      return { batches, latest, expected };
    }, {
      weights: reference.weights,
      inputs: reference.inputs,
      outputs: reference.expected.length,
      batchesCount: mutationBatchesCount,
      iterations: mutationIterations,
    });
    const sortedBatches = [...mutationBatches.batches].sort((a, b) => a - b);
    const fontFaces = await page.evaluate(() => Array.from(document.fonts).map((face) => ({
      family: face.family, status: face.status,
    })));
    results[name] = {
      fontFormat,
      outputs: reference.expected.length,
      accuracy: stats(trials.at(-1).values, reference.expected, reference.channels),
      warmNavigationMilliseconds: {
        median: warm[Math.floor((warm.length - 1) / 2)], min: warm[0], max: warm.at(-1),
      },
      mutationAccuracy: stats(
        mutationBatches.latest, mutationBatches.expected, reference.channels),
      mutationMilliseconds: {
        batchIterations: mutationIterations,
        medianBatch: sortedBatches[Math.floor((sortedBatches.length - 1) / 2)],
        medianPerUpdate: sortedBatches[Math.floor((sortedBatches.length - 1) / 2)] /
          mutationIterations,
      },
      fontFaces,
      browserMessages: browserMessages.splice(0),
    };
  }
  const htmls = await Promise.all(fixtureNames.map((name) => {
    const pageName = fontFormat === "ttf" ? name : `${name}-${fontFormat}`;
    return fs.readFile(
      new URL(`../experiments/row-axis-multimetric/${pageName}.html`, import.meta.url),
      "utf8",
    );
  }));
  const report = {
    noJavaScript: htmls.every((html) => !html.toLowerCase().includes("<script")),
    results,
  };
  if (process.env.ROW_AXIS_RESULT_OUTPUT) {
    await fs.writeFile(
      new URL(`../experiments/row-axis-multimetric/${process.env.ROW_AXIS_RESULT_OUTPUT}`, import.meta.url),
      `${JSON.stringify(report, null, 2)}\n`,
    );
  }
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
