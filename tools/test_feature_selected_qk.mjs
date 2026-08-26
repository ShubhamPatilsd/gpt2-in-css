import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/feature-selected-qk/reference.json", import.meta.url),
  "utf8",
));
const rounds = Number(process.env.FEATURE_QK_ROUNDS ?? 7);
const pageName = process.env.FEATURE_QK_PAGE ?? "index.html";

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
let lastActual = [];
try {
  for (let round = 0; round < rounds; round += 1) {
    const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
    const started = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/feature-selected-qk/${pageName}?round=${round}`,
      { waitUntil: "load", timeout: 180000 },
    );
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const widths = await page.locator(".score").evaluateAll((elements) =>
      elements.map((element) => element.getBoundingClientRect().width)
    );
    const computed = await page.locator(".score").first().evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        featureSettings: style.fontFeatureSettings,
        variationSettingsActive: style.fontVariationSettings !== "normal",
        variationSettingsLength: style.fontVariationSettings.length,
        width: element.getBoundingClientRect().width,
        childWidths: [...element.children].map((child) => {
          const glyphs = Array.from(child.textContent).length;
          const glyphWidths = [];
          for (let glyph = 0; glyph < glyphs; glyph += 1) {
            const range = document.createRange();
            range.setStart(child.firstChild, glyph * 2);
            range.setEnd(child.firstChild, (glyph + 1) * 2);
            glyphWidths.push(range.getBoundingClientRect().width);
          }
          return { glyphs, width: child.getBoundingClientRect().width, glyphWidths };
        }),
      };
    });
    const baseUnits = reference.base * reference.baseGlyphs;
    const actual = widths.map((width) =>
      ((width * 1000 / 512 - baseUnits) / reference.dotScale
        + (reference.biasFoldedIntoGlyphAdvance ? 0 : reference.biasCorrection)) / 8
    );
    const actualFirstChunkDots = computed.childWidths.map(({ glyphs, width }) =>
      (width * 1000 / 512 - reference.base * glyphs) / reference.dotScale
    );
    const expectedFirstChunkDots = [];
    for (let start = 0; start < 64; start += reference.featureChunkSize) {
      expectedFirstChunkDots.push(reference.expectedFirstCoordinateFullDots
        .slice(start, start + reference.featureChunkSize)
        .reduce((sum, value) => sum + value, 0));
    }
    const actualFirstCoordinateFullDots = [];
    for (const child of computed.childWidths) {
      const coordinates = child.glyphs / 3;
      for (let coordinate = 0; coordinate < coordinates; coordinate += 1) {
        let dot = 0;
        for (let shard = 0; shard < 3; shard += 1) {
          const width = child.glyphWidths[shard * coordinates + coordinate];
          dot += (width * 1000 / 512 - reference.base) / reference.dotScale;
        }
        actualFirstCoordinateFullDots.push(dot);
      }
    }
    const coordinateMismatches = actualFirstCoordinateFullDots.flatMap((actualValue, coordinate) => {
      const expectedValue = reference.expectedFirstCoordinateFullDots[coordinate];
      const error = actualValue - expectedValue;
      return Math.abs(error) > 0.02 ? [{ coordinate, actualValue, expectedValue, error }] : [];
    });
    lastActual = actual;
    trials.push({
      round,
      milliseconds: performance.now() - started,
      ...errors(actual, reference.expectedScores),
      actualFirstChunkDots,
      expectedFirstChunkDots,
      coordinateMismatches,
      computed,
    });
    await page.close();
  }
} finally {
  await browser.close();
}

const report = {
  chrome: await browser.version(),
  rounds,
  pageName,
  runtimeJavaScript: false,
  warmMedianMilliseconds: median(trials.slice(1).map(({ milliseconds }) => milliseconds)),
  rmseMaximum: Math.max(...trials.map(({ rmse }) => rmse)),
  maxErrorMaximum: Math.max(...trials.map(({ maxError }) => maxError)),
  queryBinningScoreRmse: reference.queryBinningScoreRmse,
  totalFontBytes: reference.fontBytes.reduce((sum, value) => sum + value, 0),
  actualScores: lastActual,
  expectedScores: reference.expectedScores,
  trials,
};
await fs.writeFile(
  new URL("../experiments/feature-selected-qk/browser.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
