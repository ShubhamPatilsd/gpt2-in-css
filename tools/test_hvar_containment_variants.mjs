import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/gpt2-block-css/view-timeline-two-block-full-reference.json", import.meta.url),
  "utf8",
));
const allVariants = [
  ["baseline", "view-timeline-two-block-full-packed4.html"],
  ["stage-layout", "view-timeline-two-block-contain-stage-layout.html"],
  ["scroller-size", "view-timeline-two-block-contain-scroller-size.html"],
  ["combined", "view-timeline-two-block-contain-combined.html"],
  ["stage-style", "view-timeline-two-block-contain-stage-style.html"],
  ["preload-fonts", "view-timeline-two-block-preload-fonts.html"],
  ["unregistered-n2", "view-timeline-two-block-unregistered-n2.html"],
  ["unregistered-layernorm", "view-timeline-two-block-unregistered-layernorm.html"],
  ["unregistered-states", "view-timeline-two-block-unregistered-states.html"],
  ["unregistered-intermediates", "view-timeline-two-block-unregistered-intermediates.html"],
];
const selected = new Set(
  (process.env.CONTAINMENT_VARIANTS ?? allVariants.map(([name]) => name).join(","))
    .split(",").map((name) => name.trim()).filter(Boolean),
);
const variants = allVariants.filter(([name]) => selected.has(name));
if (variants.length === 0) throw new Error("no containment variants selected");
const rounds = Number.parseInt(process.env.CONTAINMENT_ROUNDS ?? "5", 10);
const base = "http://127.0.0.1:4178/experiments/gpt2-block-css";

function errorStats(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    finite: actual.filter(Number.isFinite).length,
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 400 } });
  const trials = [];
  for (let round = 0; round < rounds; round += 1) {
    const order = variants.map((_, index) => variants[(index + round) % variants.length]);
    for (const [name, file] of order) {
      const started = performance.now();
      await page.goto(`${base}/${file}?round=${round}`, { waitUntil: "load", timeout: 120000 });
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      });
      const values = await page.locator("#two-block-full").evaluate((element, width) => {
        const style = getComputedStyle(element);
        return Array.from({ length: width }, (_, index) => Number(
          style.getPropertyValue(`--b1-final-${String(index).padStart(3, "0")}`),
        ));
      }, reference.width);
      trials.push({
        name,
        round,
        milliseconds: performance.now() - started,
        ...errorStats(values, reference.expected_packed),
      });
    }
  }
  const summary = {};
  for (const [name] of variants) {
    const samples = trials.filter((trial) => trial.name === name).slice(1);
    const times = samples.map(({ milliseconds }) => milliseconds).sort((a, b) => a - b);
    summary[name] = {
      medianMilliseconds: times[Math.floor(times.length / 2)],
      minimumMilliseconds: times[0],
      maximumMilliseconds: times.at(-1),
      rmse: samples[0].rmse,
      maxError: samples[0].maxError,
      finite: samples[0].finite,
    };
  }
  const report = { chrome: await browser.version(), rounds, trials, summary };
  await fs.writeFile(
    new URL("../experiments/packed-activation-precision/containment-results.json", import.meta.url),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
