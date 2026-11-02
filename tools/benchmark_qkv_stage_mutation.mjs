import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const contexts = (process.env.QKV_STAGE_CONTEXTS ?? "16,32").split(",").map(Number);
const rounds = Number(process.env.QKV_STAGE_ROUNDS ?? 9);
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);

function median(values) {
  const sorted = values.toSorted((left, right) => left - right);
  return sorted[Math.floor(sorted.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
const trials = [];
try {
  for (const context of contexts) {
    const stem = `attention-context-${context}-geometry-streaming-flat-projected-kv-score-cached-value-live-current-kv-siblings-projection-packet12`;
    const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
    await page.goto(
      `http://127.0.0.1:4178/experiments/gpt2-block-css/${stem}.html`,
      { waitUntil: "load", timeout: 180000 },
    );
    await page.evaluate(async (tokenCount) => {
      await document.fonts.ready;
      const host = document.querySelector(`geometry-stream-q-${tokenCount}`);
      host.querySelector("geometry-stream-attention").remove();
      const probe = document.createElement("output");
      probe.id = "qkv-probe";
      host.append(probe);
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    }, context);
    const inputProperty = `--geometry-stream-q-${context}-i-000`;
    const base = await page.locator(`geometry-stream-q-${context}`).evaluate(
      (element, property) => Number.parseFloat(getComputedStyle(element).getPropertyValue(property)),
      inputProperty,
    );
    for (let round = 0; round < rounds; round += 1) {
      const delta = round % 2 ? -0.01 : 0.01;
      const started = performance.now();
      await page.locator(`geometry-stream-q-${context}`).evaluate(
        (element, [property, value]) => element.style.setProperty(property, `${value}`),
        [inputProperty, base + delta],
      );
      const values = await page.locator("#qkv-probe").evaluate(async (element) => {
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const styles = getComputedStyle(element);
        return [
          ...Array.from({ length: 768 }, (_, index) =>
            Number.parseFloat(styles.getPropertyValue(`--q-${String(index).padStart(3, "0")}`))),
          ...Array.from({ length: 768 }, (_, index) =>
            Number.parseFloat(styles.getPropertyValue(`--current-k-${String(index).padStart(3, "0")}`))),
          ...Array.from({ length: 768 }, (_, index) =>
            Number.parseFloat(styles.getPropertyValue(`--current-v-${String(index).padStart(3, "0")}`))),
        ];
      });
      trials.push({
        context,
        round,
        milliseconds: performance.now() - started,
        finite: values.every(Number.isFinite),
      });
    }
    await page.close();
  }
} finally {
  await browser.close();
}

const summary = Object.fromEntries(contexts.map((context) => {
  const selected = trials.filter((trial) => trial.context === context);
  return [context, {
    medianMilliseconds: median(selected.map((trial) => trial.milliseconds)),
    maximumMilliseconds: Math.max(...selected.map((trial) => trial.milliseconds)),
    finite: selected.every((trial) => trial.finite),
  }];
}));
const report = { contexts, rounds, runtimeJavaScript: false, summary, trials };
await fs.writeFile(
  new URL("qkv-stage-mutation.json", directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(summary, null, 2));
