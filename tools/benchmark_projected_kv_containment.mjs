import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number(process.env.PROJECTED_KV_CONTAINMENT_ROUNDS ?? 1);
const context = Number(process.env.PROJECTED_KV_CONTAINMENT_CONTEXT ?? 16);
const stem = `attention-context-${context}-geometry-streaming-flat-projected-kv-score-cached-value-live-current-kv-siblings-projected-full-block0-multitoken-direct.html`;
const url = `http://127.0.0.1:4178/experiments/gpt2-block-css/${stem}`;
const allVariants = [
  { name: "baseline", css: "" },
  { name: "mlp-style", css: ".after-attn{contain:style}" },
  { name: "mlp-layout", css: ".after-attn{contain:layout}" },
  { name: "mlp-layout-style", css: ".after-attn{contain:layout style}" },
  { name: "bridge-layout-style", css: "#attention-result{contain:layout style}" },
  { name: "attention-layout-style", css: "geometry-stream-attention{contain:layout style}" },
  {
    name: "both-layout-style",
    css: "geometry-stream-attention,.after-attn{contain:layout style}",
  },
];
const requestedVariants = new Set(
  (process.env.PROJECTED_KV_CONTAINMENT_VARIANTS ?? allVariants.map(({ name }) => name).join(","))
    .split(","),
);
const variants = allVariants.filter(({ name }) => requestedVariants.has(name));

function median(values) {
  const sorted = values.toSorted((left, right) => left - right);
  return sorted[Math.floor(sorted.length / 2)];
}

async function readVector(page, selector, prefix) {
  return page.locator(selector).evaluate((element, propertyPrefix) => {
    const style = getComputedStyle(element);
    return Array.from({ length: 768 }, (_, index) => Number.parseFloat(
      style.getPropertyValue(`${propertyPrefix}${String(index).padStart(3, "0")}`),
    ));
  }, prefix);
}

const browser = await chromium.launch({ executablePath, headless: true });
const trials = [];
try {
  const warm = await browser.newPage({ viewport: { width: 900, height: 300 } });
  await warm.goto(`${url}?warm=1`, { waitUntil: "load", timeout: 180000 });
  await warm.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  await warm.close();

  for (let round = 0; round < rounds; round += 1) {
    for (const variant of variants) {
      console.error(`starting ${variant.name} round ${round}`);
      const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
      page.setDefaultTimeout(30000);
      await page.goto(`${url}?variant=${variant.name}&round=${round}`, {
        waitUntil: "load",
        timeout: 180000,
      });
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      });
      if (variant.css) {
        await page.addStyleTag({ content: variant.css });
        await page.evaluate(() => new Promise(
          (resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ));
      }
      const before = await readVector(page, "#final", "--out-");
      const started = performance.now();
      await page.locator(`geometry-stream-q-${context}`).evaluate((scope) => {
        const style = getComputedStyle(scope);
        const context = scope.localName.split("-").at(-1);
        const values = Array.from({ length: 768 }, (_, index) => {
          const suffix = String(index).padStart(3, "0");
          return Number(style.getPropertyValue(
            `--geometry-stream-q-${context}-i-${suffix}`,
          ));
        });
        for (let index = 0; index < 768; index += 1) {
          const suffix = String(index).padStart(3, "0");
          const name = `--geometry-stream-q-${context}-i-${suffix}`;
          scope.style.setProperty(name, String(values[index] * 0.8));
        }
      });
      await page.evaluate(() => new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(resolve)))
      ));
      const after = await readVector(page, "#final", "--out-");
      const milliseconds = performance.now() - started;
      const finite = after.filter(Number.isFinite).length;
      const delta = Math.sqrt(after.reduce((sum, value, index) =>
        sum + (value - before[index]) ** 2, 0) / after.length);
      trials.push({
        round,
        name: variant.name,
        css: variant.css,
        milliseconds,
        finite,
        outputDeltaRmse: delta,
        checksum: after.reduce((sum, value) => sum + value, 0),
      });
      console.error(`finished ${variant.name}: ${milliseconds.toFixed(1)} ms`);
      await page.close();
    }
  }
} finally {
  await browser.close();
}

const summary = Object.fromEntries(variants.map(({ name }) => {
  const matching = trials.filter((trial) => trial.name === name);
  return [name, {
    medianMilliseconds: median(matching.map(({ milliseconds }) => milliseconds)),
    finite: Math.min(...matching.map(({ finite }) => finite)),
    outputDeltaRmse: matching[0].outputDeltaRmse,
    checksum: matching[0].checksum,
  }];
}));
const report = {
  chrome: await browser.version(),
  context,
  rounds,
  runtimeJavaScript: false,
  summary,
  trials,
};
await fs.writeFile(
  new URL("../experiments/gpt2-block-css/projected-kv-containment-browser.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(summary, null, 2));
