import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/gpt2-hvar-chain/reference.json", import.meta.url), "utf8"));

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 400 } });
  const trials = [];
  const pairCount = Number(process.env.HVAR_BENCHMARK_PAIRS ?? 10);
  const files = [];
  for (let pair = 0; pair < pairCount; pair += 1) {
    files.push(...(pair % 2 === 0
      ? ["index", "direct-cqi"]
      : ["direct-cqi", "index"]));
  }
  for (const file of files) {
    const started = performance.now();
    await page.goto(`http://127.0.0.1:4178/experiments/gpt2-hvar-chain/${file}.html?run=${trials.length}`, {
      waitUntil: "load", timeout: 120000,
    });
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const values = await page.evaluate((width) => {
      const outputs = [];
      const blockSize = width / 4;
      for (let block = 0; block < 4; block += 1) {
        const style = getComputedStyle(document.querySelector(`#final-${block}`));
        for (let index = block * blockSize; index < (block + 1) * blockSize; index += 1) {
          outputs.push(Number(style.getPropertyValue(`--l2-y-${String(index).padStart(3, "0")}`)));
        }
      }
      return outputs;
    }, reference.width);
    const elapsed = performance.now() - started;
    const errors = values.map((value, index) => value - reference.quantized_output[index]);
    trials.push({
      file,
      milliseconds: elapsed,
      finite: values.filter(Number.isFinite).length,
      rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
      maxError: Math.max(...errors.map(Math.abs)),
    });
  }
  const warm = {};
  for (const file of ["index", "direct-cqi"]) {
    const values = trials.filter((trial) => trial.file === file).slice(1)
      .map((trial) => trial.milliseconds).sort((a, b) => a - b);
    const quantile = (fraction) => values[Math.floor((values.length - 1) * fraction)];
    warm[file] = {
      samples: values.length,
      min: values[0],
      p25: quantile(0.25),
      median: quantile(0.5),
      p75: quantile(0.75),
      max: values.at(-1),
    };
  }
  console.log(JSON.stringify({ trials, warm }, null, 2));
} finally {
  await browser.close();
}
