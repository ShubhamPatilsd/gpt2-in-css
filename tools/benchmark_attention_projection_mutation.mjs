import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const contexts = (process.env.ATTENTION_PROJECTION_CONTEXTS ?? "16,32")
  .split(",").map(Number);
const rounds = Number(process.env.ATTENTION_PROJECTION_ROUNDS ?? 9);
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
    const base = await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      const attention = document.querySelector("geometry-stream-attention");
      const projection = attention.querySelector(":scope > .geometry-projection");
      const styles = getComputedStyle(projection);
      const contextValues = Array.from({ length: 768 }, (_, index) =>
        styles.getPropertyValue(`--context-${String(index).padStart(3, "0")}`).trim()
      );
      contextValues.forEach((value, index) => {
        projection.style.setProperty(`--context-${String(index).padStart(3, "0")}`, value);
      });
      const slot = document.createElement("slot");
      attention.shadowRoot.replaceChildren(slot);
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      return Number.parseFloat(contextValues[0]);
    });
    for (let round = 0; round < rounds; round += 1) {
      const delta = round % 2 ? -0.01 : 0.01;
      const started = performance.now();
      await page.locator("geometry-stream-attention > .geometry-projection").evaluate(
        (element, value) => element.style.setProperty("--context-000", `${value}`),
        base + delta,
      );
      const output = await page.locator("#attention-result").evaluate(async (element) => {
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const styles = getComputedStyle(element);
        return Array.from({ length: 768 }, (_, index) => Number.parseFloat(
          styles.getPropertyValue(`--r1-${String(index).padStart(3, "0")}`),
        ));
      });
      trials.push({
        context,
        round,
        milliseconds: performance.now() - started,
        finite: output.every(Number.isFinite),
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
  new URL("attention-projection-mutation.json", directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(summary, null, 2));
