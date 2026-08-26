import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const root = new URL("../experiments/avar2-hvar-mlp-scaling/", import.meta.url);
const manifest = JSON.parse(await fs.readFile(new URL("manifest.json", root), "utf8"));
// HVAR stores each basis delta as an integer font unit. Across hundreds of
// active basis terms, the intended piecewise output can therefore differ by
// slightly more than one unit even when Chrome evaluates the font correctly.
const representationTolerance = 2;

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 1000, height: 120 },
  });
  const results = [];
  for (const reference of manifest) {
    const page = await context.newPage();
    const loadStarted = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/avar2-hvar-mlp-scaling/n${reference.size}/index.html`,
      { waitUntil: "load" },
    );
    await page.evaluate(() => document.fonts.ready);
    const loadMilliseconds = performance.now() - loadStarted;
    const samples = [];
    for (let round = 0; round < 9; round += 1) {
      const mode = (round + 1) % 2;
      const started = performance.now();
      await page.locator(`#case-${mode}`).evaluate((element) => {
        element.checked = true;
      });
      const widths = await page.locator(".output").evaluateAll((elements) =>
        elements.map((element) => element.getBoundingClientRect().width));
      const milliseconds = performance.now() - started;
      const expected = reference.representedWidths[mode];
      const maximumError = Math.max(...widths.map((value, index) =>
        Math.abs(value - expected[index])));
      samples.push({ round, mode, milliseconds, maximumError });
    }
    const measured = samples.slice(2);
    const result = {
      size: reference.size,
      loadMilliseconds,
      mutationMedianMilliseconds: median(measured.map(({ milliseconds }) => milliseconds)),
      mutationMinimumMilliseconds: Math.min(...measured.map(({ milliseconds }) => milliseconds)),
      mutationMaximumMilliseconds: Math.max(...measured.map(({ milliseconds }) => milliseconds)),
      maximumRepresentationError: Math.max(...samples.map(({ maximumError }) => maximumError)),
      representationTolerance,
      correct: samples.every(
        ({ maximumError }) => maximumError <= representationTolerance
      ),
      fontBytes: reference.fontBytes,
      htmlBytes: reference.htmlBytes,
      avarDeltaValues: reference.avarDeltaValues,
      hvarDeltaValues: reference.hvarDeltaValues,
      elements: await page.locator("*").count(),
      samples,
    };
    results.push(result);
    await page.close();
  }
  const report = {
    chrome: await browser.version(),
    runtimeContainsJavaScript: false,
    results,
  };
  await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
  if (!results.every(({ correct }) => correct)) process.exitCode = 1;
  await context.close();
} finally {
  await browser.close();
}
