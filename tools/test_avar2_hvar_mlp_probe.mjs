import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const root = new URL("../experiments/avar2-hvar-mlp/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 900, height: 120 },
  });
  const page = await context.newPage();
  await page.goto("http://127.0.0.1:4178/experiments/avar2-hvar-mlp/index.html");
  await page.evaluate(() => document.fonts.ready);
  const cases = [];
  for (let index = 0; index < reference.inputs.length; index += 1) {
    await page.locator(`#case-${index}`).evaluate((element) => {
      element.checked = true;
    });
    const widths = await page.locator(".probe").evaluateAll((elements) =>
      elements.map((element) => element.getBoundingClientRect().width));
    const represented = reference.representedWidths[index];
    const exact = reference.exactOutputs[index].map((value) => value + reference.baseAdvance);
    cases.push({
      index,
      input: reference.inputs[index],
      widths,
      represented,
      exact,
      representationErrors: widths.map((value, output) => value - represented[output]),
      modelErrors: widths.map((value, output) => value - exact[output]),
    });
  }
  const representationMaximumError = Math.max(...cases.flatMap(({ representationErrors }) =>
    representationErrors.map(Math.abs)));
  const modelMaximumError = Math.max(...cases.flatMap(({ modelErrors }) =>
    modelErrors.map(Math.abs)));
  const report = {
    chrome: await browser.version(),
    runtimeContainsJavaScript: await page.locator("script").count() > 0,
    correct: representationMaximumError <= 1,
    representationMaximumError,
    modelMaximumError,
    approximationMaximum: reference.approximationMaximum,
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
