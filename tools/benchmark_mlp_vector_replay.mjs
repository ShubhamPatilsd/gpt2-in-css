import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const contexts = (process.env.MLP_VECTOR_REPLAY_CONTEXTS ?? "16,32").split(",").map(Number);
const rounds = Number(process.env.MLP_VECTOR_REPLAY_ROUNDS ?? 7);
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);

function median(values) {
  const sorted = values.toSorted((left, right) => left - right);
  return sorted[Math.floor(sorted.length / 2)];
}

async function readVector(page, selector, prefix) {
  return page.locator(selector).evaluate((element, propertyPrefix) => {
    const styles = getComputedStyle(element);
    return Array.from({ length: 768 }, (_, index) => Number.parseFloat(
      styles.getPropertyValue(`${propertyPrefix}${String(index).padStart(3, "0")}`),
    ));
  }, prefix);
}

const browser = await chromium.launch({ executablePath, headless: true });
const trials = [];
try {
  for (const context of contexts) {
    const attentionStem = `attention-context-${context}-geometry-streaming-flat-css-kv-score-cached-value-live-current-kv-siblings-projection-packet12`;
    const attentionPage = await browser.newPage({ viewport: { width: 900, height: 300 } });
    await attentionPage.goto(
      `http://127.0.0.1:4178/experiments/gpt2-block-css/${attentionStem}.html`,
      { waitUntil: "load", timeout: 180000 },
    );
    await attentionPage.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const baseline = await readVector(attentionPage, "#attention-result", "--r1-");
    const hostSelector = `geometry-stream-q-${context}`;
    const property = `--geometry-stream-q-${context}-i-000`;
    const inputBase = await attentionPage.locator(hostSelector).evaluate(
      (element, name) => Number.parseFloat(getComputedStyle(element).getPropertyValue(name)),
      property,
    );
    await attentionPage.locator(hostSelector).evaluate(
      (element, [name, value]) => element.style.setProperty(name, `${value}`),
      [property, inputBase + 0.01],
    );
    await attentionPage.evaluate(() =>
      new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    );
    const mutated = await readVector(attentionPage, "#attention-result", "--r1-");
    await attentionPage.close();

    const changedCoordinates = baseline.filter((value, index) => value !== mutated[index]).length;
    const isolatedStem = `${attentionStem}-full-block0-multitoken-direct-isolated`;
    const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
    await page.goto(
      `http://127.0.0.1:4178/experiments/gpt2-block-css/${isolatedStem}.html`,
      { waitUntil: "load", timeout: 180000 },
    );
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const encode = (values) => values.map((value, index) =>
      `--r1-${String(index).padStart(3, "0")}:${value}`
    ).join(";");
    const states = [encode(baseline), encode(mutated)];
    for (let round = 0; round < rounds; round += 1) {
      const started = performance.now();
      await page.locator("#attention-isolated").evaluate(
        (element, declarations) => element.style.cssText = declarations,
        states[round % 2],
      );
      const output = await page.locator("#final").evaluate(async (element) => {
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const styles = getComputedStyle(element);
        return Array.from({ length: 768 }, (_, index) => Number.parseFloat(
          styles.getPropertyValue(`--out-${String(index).padStart(3, "0")}`),
        ));
      });
      trials.push({
        context,
        round,
        changedCoordinates,
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
    changedCoordinates: selected[0].changedCoordinates,
    medianMilliseconds: median(selected.map((trial) => trial.milliseconds)),
    maximumMilliseconds: Math.max(...selected.map((trial) => trial.milliseconds)),
    finite: selected.every((trial) => trial.finite),
  }];
}));
const report = { contexts, rounds, runtimeJavaScript: false, summary, trials };
await fs.writeFile(
  new URL("mlp-vector-replay.json", directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(summary, null, 2));
