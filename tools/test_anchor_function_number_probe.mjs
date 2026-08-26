#!/usr/bin/env node

import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const origin = process.env.HVAR_ORIGIN ?? "http://127.0.0.1:4178";

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(
    `${origin}/experiments/anchor-function-number-probe.html`,
    { waitUntil: "load" },
  );
  const result = await page.evaluate(() => {
    const consumer = getComputedStyle(document.querySelector("#consumer"));
    const direct = getComputedStyle(document.querySelector("#direct-length"));
    return {
      a0: consumer.getPropertyValue("--a0").trim(),
      a1: consumer.getPropertyValue("--a1").trim(),
      consumerWidth: consumer.width,
      directLengthWidth: direct.width,
      fontVariationSettings: consumer.fontVariationSettings,
    };
  });
  const report = {
    chrome: await browser.version(),
    runtimeContainsJavaScript: false,
    expectedNumbers: [37, 53],
    ...result,
    reusableNumberSucceeded: result.a0 === "37" && result.a1 === "53",
  };
  await fs.writeFile(
    new URL("../experiments/anchor-function-number-probe-results.json", import.meta.url),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
