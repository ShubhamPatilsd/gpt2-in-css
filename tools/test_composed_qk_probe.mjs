import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number(process.env.COMPOSED_QK_ROUNDS ?? 5);
const variants = (process.env.COMPOSED_QK_VARIANTS ?? "direct,shifted").split(",");
const directory = new URL("../experiments/composed-qk-probe/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", directory), "utf8"));

function median(values) {
  const ordered = values.toSorted((a, b) => a - b);
  return ordered[Math.floor(ordered.length / 2)];
}

function error(actual) {
  const values = actual.map((value, index) => value - reference.expected[index]);
  return {
    rmse: Math.sqrt(values.reduce((sum, value) => sum + value * value, 0) / values.length),
    maxError: Math.max(...values.map(Math.abs)),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
const trials = [];
try {
  for (const variant of variants) {
    for (let round = 0; round < rounds; round += 1) {
      const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
      const started = performance.now();
      await page.goto(
        `http://127.0.0.1:4178/experiments/composed-qk-probe/${variant}.html?round=${round}`,
        { waitUntil: "load", timeout: 180000 },
      );
      await page.evaluate(() => document.fonts.ready);
      const fontStatuses = await page.evaluate(() =>
        [...document.fonts].map((font) => ({ family: font.family, status: font.status })));
      if (fontStatuses.some((font) => font.status !== "loaded")) {
        throw new Error(`${variant} font load failed: ${JSON.stringify(fontStatuses)}`);
      }
      let actual;
      if (variant === "direct") {
        actual = await page.locator(".direct-score").evaluateAll((elements, config) =>
          elements.map((element) =>
            (element.getBoundingClientRect().width - config.base) / config.scale), {
          base: reference.directBase,
          scale: reference.directScale,
        });
      } else {
        const fonts = variant.startsWith("shifted")
          ? reference.shiftedFonts : reference.composedFonts;
        const widths = await page.locator(".glyph").evaluateAll((elements) =>
          elements.map((element) => element.getBoundingClientRect().width));
        actual = Array.from({ length: reference.context }, (_, source) => {
          let score = 0;
          for (let shard = 0; shard < fonts.length; shard += 1) {
            const width = widths[source * fonts.length + shard];
            score += (width - (fonts[shard].baseAdvance ?? reference.baseAdvance)) /
              fonts[shard].scale;
          }
          return score / Math.sqrt(64);
        });
      }
      if (actual.some((value) => !Number.isFinite(value))) {
        throw new Error(`${variant} produced non-finite scores`);
      }
      trials.push({ variant, round, milliseconds: performance.now() - started, ...error(actual) });
      await page.close();
    }
  }
} finally {
  await browser.close();
}
const summary = {};
for (const variant of variants) {
  const selected = trials.filter((trial) => trial.variant === variant);
  summary[variant] = {
    warmMedianMilliseconds: median(selected.slice(1).map((trial) => trial.milliseconds)),
    rmseMaximum: Math.max(...selected.map((trial) => trial.rmse)),
    maxErrorMaximum: Math.max(...selected.map((trial) => trial.maxError)),
  };
}
if (summary.direct) {
  for (const variant of variants.filter((item) => item !== "direct")) {
    summary[variant].speedup = summary.direct.warmMedianMilliseconds /
      summary[variant].warmMedianMilliseconds;
  }
}
const report = { chrome: await browser.version(), rounds, trials, summary };
await fs.writeFile(new URL("browser.json", directory), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(summary, null, 2));
