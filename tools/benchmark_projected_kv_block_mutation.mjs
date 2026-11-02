import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const contexts = (process.env.PROJECTED_KV_BLOCK_MUTATION_CONTEXTS ?? "16,32")
  .split(",").map(Number);
const rounds = Number(process.env.PROJECTED_KV_BLOCK_MUTATION_ROUNDS ?? 7);
const isolatedTail = process.env.PROJECTED_KV_BLOCK_MUTATION_ISOLATED_TAIL === "1";
const projectionTransport = process.env.PROJECTED_KV_BLOCK_MUTATION_PROJECTION ?? "packet12";
if (!["packet6", "packet8", "packet12"].includes(projectionTransport)) {
  throw new Error(`unknown projection transport: ${projectionTransport}`);
}
const scoreBackend = process.env.PROJECTED_KV_BLOCK_MUTATION_SCORE_BACKEND ?? "feature-kv";
const scoreStem = {
  "css-kv": "css-kv-score",
  "feature-kv": "projected-kv-score",
  "bilinear-kv": "bilinear-kv-score",
  "bilinear-sum-kv": "bilinear-sum-kv-score",
}[scoreBackend];
if (!scoreStem) throw new Error(`unknown score backend: ${scoreBackend}`);
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);

function median(values) {
  const sorted = values.toSorted((left, right) => left - right);
  return sorted[Math.floor(sorted.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
const trials = [];
try {
  for (const context of contexts) {
    const stem = `attention-context-${context}-geometry-streaming-flat-${scoreStem}-cached-value-live-current-kv-siblings-projection-${projectionTransport}-full-block0-multitoken-direct${isolatedTail ? "-isolated" : ""}`;
    const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
    await page.goto(
      `http://127.0.0.1:4178/experiments/gpt2-block-css/${stem}.html`,
      { waitUntil: "load", timeout: 180000 },
    );
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const hostSelector = isolatedTail ? "#attention-isolated" : `geometry-stream-q-${context}`;
    const property = isolatedTail ? "--r1-000" : `--geometry-stream-q-${context}-i-000`;
    const base = await page.locator(hostSelector).evaluate(
      (element, name) => Number.parseFloat(getComputedStyle(element).getPropertyValue(name)),
      property,
    );
    for (let round = 0; round < rounds; round += 1) {
      const delta = round % 2 ? -0.01 : 0.01;
      const started = performance.now();
      await page.locator(hostSelector).evaluate(
        (element, [name, value]) => element.style.setProperty(name, `${value}`),
        [property, base + delta],
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
const report = { contexts, rounds, scoreBackend, projectionTransport, isolatedTail, runtimeJavaScript: false, summary, trials };
await fs.writeFile(
  new URL(`projected-kv-block-mutation-${scoreBackend}-${projectionTransport}${isolatedTail ? "-isolated-tail" : ""}.json`, directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(summary, null, 2));
