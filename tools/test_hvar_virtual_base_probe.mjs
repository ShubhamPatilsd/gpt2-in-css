#!/usr/bin/env node
/* Verify whether Chrome sums all HVAR regions before range clamping. */

import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot =
  process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath =
  process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const output = path.join(root, "experiments", "hvar-virtual-base");
const reference = JSON.parse(fs.readFileSync(path.join(output, "reference.json"), "utf8"));

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 600 } });
  await page.goto(pathToFileURL(path.join(output, "index.html")).href, {
    waitUntil: "load",
    timeout: 120_000,
  });
  await page.evaluate(() => document.fonts.ready);
  const raw = await page.evaluate(() =>
    [...document.querySelectorAll("[data-case]")].map((group) => {
      const width = (selector) => {
        const text = group.querySelector(selector);
        return text.getStartPositionOfChar(1).x - text.getStartPositionOfChar(0).x;
      };
      return {
        name: group.getAttribute("data-case"),
        base: width(".base"),
        biasFirst: width(".bias-first"),
        negativeFirst: width(".negative-first"),
      };
    }),
  );
  const toUnits = (pixels) => Math.round((pixels / reference.scale) * 1000) / 1000;
  const measured = raw.map((item) => {
    const expected = reference.cases.find((candidate) => candidate.name === item.name);
    const observed = {
      base: toUnits(item.base),
      biasFirst: toUnits(item.biasFirst),
      negativeFirst: toUnits(item.negativeFirst),
    };
    return {
      ...expected,
      observed,
      biasFirstError: observed.biasFirst - expected.expected,
      negativeFirstError: observed.negativeFirst - expected.expected,
    };
  });
  const exact = measured.every(
    (item) =>
      Math.abs(item.biasFirstError) <= 2 &&
      Math.abs(item.negativeFirstError) <= 2 &&
      Math.abs(item.observed.base - item.base) <= 2,
  );
  const report = {
    chrome: await browser.version(),
    generatedAt: new Date().toISOString(),
    conclusion: exact ? "virtual-base-survives" : "virtual-base-fails",
    toleranceDesignUnits: 2,
    measured,
  };
  fs.writeFileSync(
    path.join(output, "browser-results.json"),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  for (const item of measured) {
    process.stdout.write(
      `${item.name.padEnd(16)} expected=${item.expected.toFixed(1)} ` +
        `bias-first=${item.observed.biasFirst.toFixed(1)} ` +
        `negative-first=${item.observed.negativeFirst.toFixed(1)}\n`,
    );
  }
  process.stdout.write(`conclusion: ${report.conclusion}\n`);
  await page.close();
} finally {
  await browser.close();
}
