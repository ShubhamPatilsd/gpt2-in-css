import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const root = new URL("../experiments/avar2-hvar-composition/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 900, height: 120 },
  });
  const page = await context.newPage();
  const started = performance.now();
  await page.goto(
    "http://127.0.0.1:4178/experiments/avar2-hvar-composition/index.html",
    { waitUntil: "load" },
  );
  await page.evaluate(() => document.fonts.ready);

  const cases = [];
  for (let index = 0; index < reference.inputs.length; index += 1) {
    const before = performance.now();
    await page.locator(`#case-${index}`).evaluate((element) => {
      element.checked = true;
    });
    const widths = await page.locator(".probe").evaluateAll((elements) =>
      elements.map((element) => element.getBoundingClientRect().width));
    const expected = reference.expectedWidths[index];
    const errors = widths.map((value, output) => value - expected[output]);
    cases.push({
      index,
      input: reference.inputs[index],
      expectedMapped: reference.expectedMapped[index],
      expectedWidths: expected,
      widths,
      errors,
      milliseconds: performance.now() - before,
    });
  }
  const maximumError = Math.max(
    ...cases.flatMap(({ errors }) => errors.map(Math.abs)),
  );
  const report = {
    chrome: await browser.version(),
    loadMilliseconds: performance.now() - started,
    runtimeContainsJavaScript: await page.locator("script").count() > 0,
    avar2Applied: cases.some(({ widths }) =>
      widths.some((width) => Math.abs(width - reference.baseAdvance) > 1)),
    correct: maximumError <= 0.25,
    maximumError,
    elements: await page.locator("*").count(),
    cases,
  };
  await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
  if (!report.correct) process.exitCode = 1;
  await context.close();
} finally {
  await browser.close();
}
