import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/feature-selected-qk-all-heads/reference.json", import.meta.url),
  "utf8",
));
const rounds = Number(process.env.FEATURE_QK_ALL_HEADS_ROUNDS ?? 5);

function median(values) {
  const ordered = values.toSorted((left, right) => left - right);
  return ordered[Math.floor(ordered.length / 2)];
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
const trials = [];
let lastHeadErrors = [];
try {
  for (let round = 0; round < rounds; round += 1) {
    const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
    const started = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/feature-selected-qk-all-heads/index.html?round=${round}`,
      { waitUntil: "load", timeout: 180000 },
    );
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const headWidths = await page.locator(".head").evaluateAll((heads) =>
      heads.map((head) => [...head.querySelectorAll(".score")]
        .map((score) => score.getBoundingClientRect().width))
    );
    lastHeadErrors = headWidths.map((widths, head) => {
      const headReference = reference.headsReference[head];
      const baseUnits = headReference.base * reference.baseGlyphs;
      const actual = widths.map((width) => (
        (width * 1000 / reference.fontSize - baseUnits) / headReference.dotScale
        + (headReference.biasFoldedIntoGlyphAdvance ? 0 : headReference.biasCorrection)
      ) / Math.sqrt(reference.headWidth));
      return {
        head,
        ...errors(actual, headReference.expectedScores),
        versusEightBitQuery: errors(actual, headReference.baselineScores),
        queryBinningScoreRmse: headReference.queryBinningScoreRmse,
      };
    });
    trials.push({
      round,
      milliseconds: performance.now() - started,
      maximumHeadRmse: Math.max(...lastHeadErrors.map(({ rmse }) => rmse)),
      maximumHeadError: Math.max(...lastHeadErrors.map(({ maxError }) => maxError)),
    });
    await page.close();
  }
} finally {
  await browser.close();
}

const report = {
  chrome: await browser.version(),
  rounds,
  context: reference.context,
  heads: reference.heads,
  queryBits: reference.queryBits,
  featureChunkSize: reference.featureChunkSize,
  runtimeJavaScript: false,
  warmMedianMilliseconds: median(trials.slice(1).map(({ milliseconds }) => milliseconds)),
  totalFontBytes: reference.totalFontBytes,
  htmlBytes: reference.htmlBytes,
  headErrors: lastHeadErrors,
  trials,
};
await fs.writeFile(
  new URL("../experiments/feature-selected-qk-all-heads/browser.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
