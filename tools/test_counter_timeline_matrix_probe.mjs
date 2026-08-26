import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const experiment = new URL("../experiments/counter-matrix/", import.meta.url);
const manifest = JSON.parse(await fs.readFile(new URL("manifest.json", experiment), "utf8"));
const base = "http://127.0.0.1:4178/experiments/counter-matrix";
const rounds = Number(process.env.COUNTER_TIMELINE_ROUNDS ?? 9);
const selectedSizes = new Set(
  (process.env.COUNTER_TIMELINE_SIZES ?? manifest.sizes.map(({ size }) => size).join(","))
    .split(",").map(Number),
);

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function errors(actual, expected) {
  const differences = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(differences.reduce((sum, value) => sum + value * value, 0) / differences.length),
    maxError: Math.max(...differences.map(Math.abs)),
  };
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const report = { chrome: await browser.version(), rounds, results: {} };
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 400 } });
  for (const descriptor of manifest.sizes.filter(({ size }) => selectedSizes.has(size))) {
    const reference = JSON.parse(await fs.readFile(
      new URL(`n${descriptor.size}.json`, experiment), "utf8",
    ));
    await page.goto(`${base}/n${descriptor.size}-timeline.html`, {
      waitUntil: "load",
      timeout: 120000,
    });
    await page.evaluate(() => document.fonts.ready);
    const correctness = [];
    for (let caseIndex = 0; caseIndex < 2; caseIndex += 1) {
      const widths = await page.evaluate(async (index) => {
        document.querySelector(`#case-${index}`).checked = true;
        await new Promise((resolve) => requestAnimationFrame(
          () => requestAnimationFrame(resolve),
        ));
        return [...document.querySelectorAll(".result")].map(
          (element) => element.getBoundingClientRect().width,
        );
      }, caseIndex);
      correctness.push(errors(widths, reference.expectedWidths[caseIndex]));
    }
    const timing = await page.evaluate(async ({ count }) => {
      const radios = [...document.querySelectorAll('input[name="case"]')];
      const outputs = [...document.querySelectorAll(".result")];
      const samples = [];
      let checksum = 0;
      for (let round = 0; round < count + 8; round += 1) {
        const started = performance.now();
        radios[round % 2].checked = true;
        await new Promise((resolve) => requestAnimationFrame(
          () => requestAnimationFrame(resolve),
        ));
        for (const output of outputs) checksum += output.getBoundingClientRect().width;
        const elapsed = performance.now() - started;
        if (round >= 8) samples.push(elapsed);
      }
      return { samples, checksum, elements: document.querySelectorAll("*").length };
    }, { count: rounds });
    report.results[descriptor.size] = {
      ...descriptor,
      correctness,
      medianMilliseconds: median(timing.samples),
      samplesMilliseconds: timing.samples,
      checksum: timing.checksum,
      elements: timing.elements,
    };
  }
} finally {
  await browser.close();
}

for (const result of Object.values(report.results)) {
  if (Math.max(...result.correctness.map(({ maxError }) => maxError)) > 0.03) {
    throw new Error(`timeline counter matrix mismatch: ${JSON.stringify(result)}`);
  }
}
for (const descriptor of manifest.sizes.filter(({ size }) => selectedSizes.has(size))) {
  const html = await fs.readFile(
    new URL(`n${descriptor.size}-timeline.html`, experiment),
    "utf8",
  );
  if (html.toLowerCase().includes("<script")) {
    throw new Error(`runtime fixture contains JavaScript: n${descriptor.size}-timeline.html`);
  }
}

await fs.writeFile(
  new URL("timeline-browser-results.json", experiment),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
