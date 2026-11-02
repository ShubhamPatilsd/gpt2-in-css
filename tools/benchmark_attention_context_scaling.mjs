import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number(process.env.ATTENTION_CONTEXT_ROUNDS ?? 5);
const contexts = (process.env.ATTENTION_CONTEXTS ?? "1,2,4,8")
  .split(",").map(Number);
const transports = (process.env.ATTENTION_CONTEXT_TRANSPORTS ?? "container,timeline,streaming,streaming-key-anchor").split(",");
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);

const variants = [];
for (const transport of transports) {
  for (const context of contexts) {
    const stem = `attention-context-${context}-qkv-${transport}`;
    const reference = JSON.parse(await fs.readFile(
      new URL(`${stem}-reference.json`, directory), "utf8",
    ));
    variants.push({ context, transport, stem, reference });
  }
}

function median(values) {
  const ordered = values.toSorted((a, b) => a - b);
  return ordered[Math.floor(ordered.length / 2)];
}

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const trials = [];
  for (const variant of variants) {
    for (let round = 0; round < rounds; round += 1) {
      const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
      const started = performance.now();
      await page.goto(
        `http://127.0.0.1:4178/experiments/gpt2-block-css/${variant.stem}.html?round=${round}`,
        { waitUntil: "load", timeout: 180000 },
      );
      const actual = await page.locator("#attention-result").evaluate((element) => {
        const styles = getComputedStyle(element);
        return Array.from({ length: 768 }, (_, index) => Number.parseFloat(
          styles.getPropertyValue(`--r1-${String(index).padStart(3, "0")}`),
        ));
      });
      const milliseconds = performance.now() - started;
      if (actual.some((value) => !Number.isFinite(value))) {
        throw new Error(`${variant.transport}/${variant.context} returned a non-finite result`);
      }
      trials.push({
        context: variant.context,
        transport: variant.transport,
        round,
        milliseconds,
        ...summarize(actual, variant.reference.residual),
      });
      await page.close();
    }
  }
  const summary = {};
  for (const variant of variants) {
    const selected = trials.filter((trial) =>
      trial.context === variant.context && trial.transport === variant.transport);
    const warm = selected.slice(1);
    summary[variant.transport] ??= {};
    summary[variant.transport][variant.context] = {
      warmMedianMilliseconds: median(warm.map((trial) => trial.milliseconds)),
      rmseMaximum: Math.max(...selected.map((trial) => trial.rmse)),
      maxErrorMaximum: Math.max(...selected.map((trial) => trial.maxError)),
      qkvPackingRmse: variant.reference.qkvPackingRmse,
      qkvClippedFraction: variant.reference.qkvClippedFraction,
      sourceBytes: variant.reference.htmlBytes + variant.reference.cssBytes +
        variant.reference.stageCssBytes + variant.reference.fontBytes,
    };
  }
  for (const transport of transports) {
    for (const context of contexts.slice(1)) {
      if (summary[transport][context / 2]) {
        summary[transport][context].incrementalMilliseconds =
          summary[transport][context].warmMedianMilliseconds -
          summary[transport][context / 2].warmMedianMilliseconds;
      }
    }
  }
  if (summary.container && summary.timeline) {
    for (const context of contexts) {
      summary.container[context].speedupVsTimeline =
        summary.timeline[context].warmMedianMilliseconds /
        summary.container[context].warmMedianMilliseconds;
    }
  }
  if (summary.streaming && summary.container) {
    for (const context of contexts) {
      summary.streaming[context].speedupVsAccumulatedContainer =
        summary.container[context].warmMedianMilliseconds /
        summary.streaming[context].warmMedianMilliseconds;
    }
  }
  if (summary["streaming-key-anchor"] && summary.streaming) {
    for (const context of contexts) {
      summary["streaming-key-anchor"][context].speedupVsStreaming =
        summary.streaming[context].warmMedianMilliseconds /
        summary["streaming-key-anchor"][context].warmMedianMilliseconds;
    }
  }
  report = {
    chrome: await browser.version(),
    rounds,
    rangeCalibration: variants[0].reference.rangeCalibration,
    trials,
    summary,
  };
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL(process.env.ATTENTION_CONTEXT_REPORT ?? "attention-context-scaling-browser.json", directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report.summary, null, 2));
