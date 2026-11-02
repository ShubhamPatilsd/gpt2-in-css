import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const dimensionsList = (process.env.BILINEAR_HVAR_DIMENSIONS ?? "8,32,64")
  .split(",").map(Number);
const directory = new URL("../experiments/bilinear-hvar-dot/", import.meta.url);

const browser = await chromium.launch({ executablePath, headless: true });
const results = [];
try {
  for (const dimensions of dimensionsList) {
    const reference = JSON.parse(await fs.readFile(
      new URL(`dot-${dimensions}-reference.json`, directory), "utf8",
    ));
    const page = await browser.newPage({ viewport: { width: 800, height: 300 } });
    const started = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/bilinear-hvar-dot/dot-${dimensions}.html`,
      { waitUntil: "load", timeout: 180000 },
    );
    await page.evaluate(() => document.fonts.ready);
    const widths = await page.locator(".dot").evaluateAll((elements) =>
      elements.map((element) => element.getBoundingClientRect().width)
    );
    const actual = widths.map((width) =>
      (width - reference.baseWidthPixels) / reference.dotScalePixels
    );
    const errors = actual.map((value, index) => value - reference.cases[index].expected);
    results.push({
      dimensions,
      axes: reference.axes,
      milliseconds: performance.now() - started,
      fontBytes: reference.fontBytes,
      expected: reference.cases.map((item) => item.expected),
      actual,
      rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
      maxError: Math.max(...errors.map(Math.abs)),
    });
    await page.close();
  }
} finally {
  await browser.close();
}
const report = { results };
await fs.writeFile(
  new URL("browser-results.json", directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
