#!/usr/bin/env node
/* Capture exact-CSS-GELU two-block vector boundaries from the real browser graph. */

import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const origin = process.env.HVAR_ORIGIN ?? "http://127.0.0.1:4178";
const sourceUrl = `${origin}/experiments/avar2-gelu-linear-hvar-full-mlp-g13/connected-two-block-exact-css-gelu-layoutless.html`;
const output = new URL(
  "../experiments/exact-gelu-vector-oracle/captured-boundaries.json",
  import.meta.url,
);

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 1000, height: 120 },
  });
  const page = await context.newPage();
  await page.goto(sourceUrl, { waitUntil: "load", timeout: 180_000 });
  await page.evaluate(() => document.fonts.ready);
  const cases = [];
  for (let mode = 0; mode < 4; mode += 1) {
    const values = await page.evaluate((caseIndex) => {
      function deepElements(selector) {
        const found = [];
        const visit = (root) => {
          found.push(...root.querySelectorAll(selector));
          for (const element of root.querySelectorAll("*")) {
            if (element.shadowRoot) visit(element.shadowRoot);
          }
        };
        visit(document);
        return found;
      }
      document.querySelector(`#case-${caseIndex}`).checked = true;
      const outputs = deepElements(".serial-output");
      const terminal = outputs.at(-1);
      terminal.getBoundingClientRect();
      const map = terminal.computedStyleMap();
      const typedNumbers = (prefix, count, digits) => Array.from(
        { length: count },
        (_, index) => map.get(`--${prefix}${String(index).padStart(digits, "0")}`).value,
      );
      const parsedNumbers = (prefix, count, digits) => Array.from(
        { length: count },
        (_, index) => CSSNumericValue.parse(
          getComputedStyle(terminal).getPropertyValue(
            `--${prefix}${String(index).padStart(digits, "0")}`,
          ),
        ).to("number").value,
      );
      return {
        mode: caseIndex,
        states: typedNumbers("state-", 768, 3),
        normalizedPreactivations: typedNumbers("serial-z-", 3072, 4),
        geluValues: typedNumbers("b1-g-", 3072, 4),
        residuals: parsedNumbers("b1-r1-", 768, 3),
        outputWidths: outputs.map((element) => element.getBoundingClientRect().width),
      };
    }, mode);
    cases.push(values);
    console.error(`captured exact-GELU case ${mode + 1}/4`);
  }
  const report = {
    chrome: await browser.version(),
    sourceUrl,
    runtimeContainsJavaScript: false,
    cases,
  };
  await fs.mkdir(new URL(".", output), { recursive: true });
  await fs.writeFile(output, `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify({
    chrome: report.chrome,
    cases: cases.length,
    stateValues: cases[0].states.length,
    preactivationValues: cases[0].normalizedPreactivations.length,
    geluValues: cases[0].geluValues.length,
    residualValues: cases[0].residuals.length,
    outputValues: cases[0].outputWidths.length,
  }, null, 2));
  await context.close();
} finally {
  await browser.close();
}
