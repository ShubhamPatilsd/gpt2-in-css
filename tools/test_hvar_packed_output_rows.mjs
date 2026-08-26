#!/usr/bin/env node
/* External correctness/timing harness for the HTML/CSS-only row-packing probe. */

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
const output = path.join(root, "experiments", "hvar-packed-output-rows");
const reference = JSON.parse(
  fs.readFileSync(path.join(output, "reference.json"), "utf8"),
);
const rounds = Number(process.env.HVAR_PACKED_ROUNDS ?? 30);
const warmups = Number(process.env.HVAR_PACKED_WARMUPS ?? 6);

function summary(errors) {
  const absolute = errors.map(Math.abs);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    mae: absolute.reduce((sum, value) => sum + value, 0) / absolute.length,
    maxAbs: Math.max(...absolute),
  };
}

function timingSummary(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const at = (fraction) => sorted[Math.floor((sorted.length - 1) * fraction)];
  return { medianMs: at(0.5), p10Ms: at(0.1), p90Ms: at(0.9) };
}

async function readOutputs(page, lanes) {
  return page.evaluate((laneCount) => {
    const values = [];
    for (const decoded of document.querySelectorAll(".decoded")) {
      const style = getComputedStyle(decoded);
      for (let lane = 0; lane < laneCount; lane += 1) {
        values.push(Number(style.getPropertyValue(`--o${lane}`)));
      }
    }
    return values;
  }, lanes);
}

async function inspectVariant(browser, variant, lanes, encoding) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  const started = performance.now();
  await page.goto(pathToFileURL(path.join(output, `${variant}.html`)).href, {
    waitUntil: "load",
    timeout: 120_000,
  });
  await page.evaluate(() => document.fonts.ready);
  const readyMs = performance.now() - started;
  const actualCases = [];
  for (let caseIndex = 0; caseIndex < reference.tokenIds.length; caseIndex += 1) {
    await page.evaluate((index) => {
      document.body.className = index === 0 ? "" : `case${index}`;
      void document.querySelector("#bank").scrollWidth;
    }, caseIndex);
    actualCases.push(await readOutputs(page, lanes));
  }

  const errors = [];
  const laneErrors = Array.from({ length: lanes }, () => []);
  const implementationErrors = [];
  let wrongDigitCount = 0;
  for (let caseIndex = 0; caseIndex < actualCases.length; caseIndex += 1) {
    for (let outputIndex = 0; outputIndex < reference.reference[caseIndex].length; outputIndex += 1) {
      const error = actualCases[caseIndex][outputIndex] - reference.reference[caseIndex][outputIndex];
      errors.push(error);
      laneErrors[outputIndex % lanes].push(error);
      if (encoding) {
        implementationErrors.push(
          actualCases[caseIndex][outputIndex] - encoding.offlineDecoded[caseIndex][outputIndex],
        );
        const expectedDigit = Math.round(
          encoding.radix / 2 - 0.5 +
            reference.reference[caseIndex][outputIndex] * encoding.scale,
        );
        const actualDigit = Math.round(
          encoding.radix / 2 - 0.5 +
            actualCases[caseIndex][outputIndex] * encoding.scale,
        );
        if (actualDigit !== expectedDigit) wrongDigitCount += 1;
      }
    }
  }

  const timing = await page.evaluate(
    async ({ count, discarded }) => {
      const values = [];
      let checksum = 0;
      for (let index = 0; index < count + discarded; index += 1) {
        const tick = performance.now();
        document.body.className = index % 2 === 0 ? "" : "case1";
        const bank = document.querySelector("#bank");
        checksum += bank.scrollWidth + bank.scrollHeight;
        const elapsed = performance.now() - tick;
        if (index >= discarded) values.push(elapsed);
        await new Promise(requestAnimationFrame);
      }
      return { values, checksum };
    },
    { count: rounds, discarded: warmups },
  );

  const counts = await page.evaluate(() => ({
    packets: document.querySelectorAll(".packet").length,
    elements: document.querySelectorAll("*").length,
    loadedFonts: [...document.fonts].filter((font) => font.status === "loaded").length,
  }));
  await page.close();
  return {
    variant,
    lanes,
    readyMs,
    ...counts,
    ...timingSummary(timing.values),
    modelError: summary(errors),
    laneErrors: laneErrors.map(summary),
    browserVsOffline: encoding ? summary(implementationErrors) : null,
    wrongDigitRate: encoding ? wrongDigitCount / errors.length : null,
    checksum: timing.checksum,
  };
}

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--disable-background-timer-throttling"],
});

try {
  const variants = [
    ["control", 1, null],
    ["packed2", 2, reference.encodings.find((item) => item.lanes === 2)],
    ["packed4", 4, reference.encodings.find((item) => item.lanes === 4)],
  ];
  const results = [];
  for (const [name, lanes, encoding] of variants) {
    const result = await inspectVariant(browser, name, lanes, encoding);
    results.push(result);
    process.stdout.write(
      `${name.padEnd(8)} ${result.medianMs.toFixed(1)} ms median; ` +
        `RMSE ${result.modelError.rmse.toFixed(3)}; ` +
        `lane RMSE ${result.laneErrors.map((item) => item.rmse.toFixed(3)).join(", ")}\n`,
    );
  }
  const report = {
    chrome: await browser.version(),
    rounds,
    warmups,
    generatedAt: new Date().toISOString(),
    results,
  };
  fs.writeFileSync(
    path.join(output, "browser-results.json"),
    `${JSON.stringify(report, null, 2)}\n`,
  );
} finally {
  await browser.close();
}
