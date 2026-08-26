import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/gpt2-block-css/reference.json", import.meta.url), "utf8"));

const files = ["composed", "composed-direct-cqi"];
const pairCount = Number(process.env.HVAR_BLOCK_BENCHMARK_PAIRS ?? 3);
const order = [];
for (let pair = 0; pair < pairCount; pair += 1) {
  order.push(...(pair % 2 === 0 ? files : [...files].reverse()));
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 400 } });
  const trials = [];
  for (const file of order) {
    const started = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/gpt2-block-css/${file}.html?run=${trials.length}`,
      { waitUntil: "load", timeout: 120000 },
    );
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const values = await page.evaluate(() => {
      const style = getComputedStyle(document.querySelector("#final"));
      return Array.from({ length: 768 }, (_, index) =>
        Number(style.getPropertyValue(`--out-${String(index).padStart(3, "0")}`)));
    });
    const errors = values.map(
      (value, index) => value - reference.composed_quantized_output[index]);
    trials.push({
      file,
      milliseconds: performance.now() - started,
      finite: values.filter(Number.isFinite).length,
      rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
      maxError: Math.max(...errors.map(Math.abs)),
    });
  }
  const summary = {};
  for (const file of files) {
    const samples = trials.filter((trial) => trial.file === file).slice(1);
    const times = samples.map((trial) => trial.milliseconds).sort((a, b) => a - b);
    summary[file] = {
      samples: samples.length,
      medianMilliseconds: times[Math.floor(times.length / 2)],
      rmse: samples[0]?.rmse,
      maxError: samples[0]?.maxError,
    };
  }
  console.log(JSON.stringify({ trials, summary }, null, 2));
} finally {
  await browser.close();
}
