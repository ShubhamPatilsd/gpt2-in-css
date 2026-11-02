#!/usr/bin/env node
/* Attribute the exact-CSS-GELU two-block graph with exact vector oracles. */

import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const origin = process.env.HVAR_ORIGIN ?? "http://127.0.0.1:4178";
const rounds = Number(process.env.EXACT_GELU_ORACLE_ROUNDS ?? 6);
const oracleRoot = new URL("../experiments/exact-gelu-vector-oracle/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", oracleRoot), "utf8"));

const variants = [
  {
    name: "baseline-exact-gelu-two-blocks",
    directory: "avar2-gelu-linear-hvar-full-mlp-g13",
    pageFile: "connected-two-block-exact-css-gelu-layoutless.html",
    realStages: ["block0", "block0-state-transport", "block1-attention", "block1-fc", "block1-preactivation-transport", "block1-gelu", "block1-projection"],
  },
  {
    name: "oracle-block0-handoff",
    directory: "exact-gelu-vector-oracle",
    pageFile: "oracle-block0-handoff.html",
    realStages: ["block1-attention", "block1-fc", "block1-preactivation-transport", "block1-gelu", "block1-projection"],
  },
  {
    name: "oracle-b1-fc-preactivation",
    directory: "exact-gelu-vector-oracle",
    pageFile: "oracle-b1-fc-preactivation.html",
    realStages: ["block0", "block0-state-transport", "block1-attention", "block1-gelu", "block1-projection"],
  },
  {
    name: "oracle-block0-and-b1-fc",
    directory: "exact-gelu-vector-oracle",
    pageFile: "oracle-block0-and-b1-fc.html",
    realStages: ["block1-attention", "block1-gelu", "block1-projection"],
  },
  {
    name: "oracle-b1-gelu-and-projection",
    directory: "exact-gelu-vector-oracle",
    pageFile: "oracle-b1-gelu-and-projection.html",
    realStages: ["block1-gelu", "block1-projection"],
  },
  {
    name: "oracle-b1-pure-projection",
    directory: "exact-gelu-vector-oracle",
    pageFile: "oracle-b1-pure-projection.html",
    realStages: ["block1-projection"],
  },
];

function percentile(values, fraction) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor((sorted.length - 1) * fraction)];
}

async function preparePage(context, variant) {
  const page = await context.newPage();
  await page.goto(
    `${origin}/experiments/${variant.directory}/${variant.pageFile}`,
    { waitUntil: "load", timeout: 180_000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const initial = await page.evaluate(() => {
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
    const outputs = deepElements(".serial-output");
    if (outputs.length !== 768) throw new Error(`expected 768 outputs, got ${outputs.length}`);
    outputs.at(-1).getBoundingClientRect();
    return {
      elements: deepElements("*").length,
      outputs: outputs.length,
      runtimeScripts: document.scripts.length,
    };
  });
  return { page, initial };
}

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--disable-background-timer-throttling"],
});
try {
  const context = await browser.newContext({ viewport: { width: 1000, height: 120 } });

  for (const variant of variants) {
    const { page } = await preparePage(context, variant);
    await page.close();
    variant.samples = [];
  }

  for (let round = 0; round < rounds; round += 1) {
    const mode = 1 + (round % 3);
    const order = variants.map((_, offset) => variants[(round + offset) % variants.length]);
    for (const variant of order) {
      const { page, initial } = await preparePage(context, variant);
      const sample = await page.evaluate((caseIndex) => {
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
        const outputs = deepElements(".serial-output");
        const started = performance.now();
        document.querySelector(`#case-${caseIndex}`).checked = true;
        const widths = outputs.map((element) => element.getBoundingClientRect().width);
        return {
          milliseconds: performance.now() - started,
          checksum: widths.reduce((sum, value) => sum + value, 0),
        };
      }, mode);
      variant.samples.push({ round, mode, ...initial, ...sample });
      await page.close();
    }
    console.error(`fresh exact-GELU oracle round ${round + 1}/${rounds}`);
  }

  for (const variant of variants) {
    const { page, initial } = await preparePage(context, variant);
    variant.elements = initial.elements;
    variant.runtimeScripts = initial.runtimeScripts;
    variant.validation = [];
    for (let mode = 0; mode < reference.tokenIds.length; mode += 1) {
      const widths = await page.evaluate((caseIndex) => {
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
        return deepElements(".serial-output")
          .map((element) => element.getBoundingClientRect().width);
      }, mode);
      const expected = reference.expectedOutputWidths[mode];
      const errors = widths.map((width, index) => Math.abs(width - expected[index]));
      variant.validation.push({
        mode,
        outputs: widths.length,
        maximumWidthError: Math.max(...errors),
        outputRmse: Math.sqrt(errors.reduce((sum, error) => sum + error ** 2, 0) /
          errors.length) / reference.block1OutputScale,
      });
    }
    await page.close();
  }

  const summaries = variants.map((variant) => {
    const times = variant.samples.map(({ milliseconds }) => milliseconds);
    return {
      name: variant.name,
      pageFile: variant.pageFile,
      realStages: variant.realStages,
      elements: variant.elements,
      runtimeScripts: variant.runtimeScripts,
      minimumMilliseconds: Math.min(...times),
      medianMilliseconds: percentile(times, 0.5),
      p90Milliseconds: percentile(times, 0.9),
      maximumMilliseconds: Math.max(...times),
      maximumWidthError: Math.max(...variant.validation.map(({ maximumWidthError }) => maximumWidthError)),
      maximumOutputRmse: Math.max(...variant.validation.map(({ outputRmse }) => outputRmse)),
      samples: variant.samples,
      validation: variant.validation,
    };
  });
  const byName = Object.fromEntries(summaries.map((entry) => [entry.name, entry]));
  const baseline = byName["baseline-exact-gelu-two-blocks"].medianMilliseconds;
  const handoff = byName["oracle-block0-handoff"].medianMilliseconds;
  const fcFree = byName["oracle-b1-fc-preactivation"].medianMilliseconds;
  const both = byName["oracle-block0-and-b1-fc"].medianMilliseconds;
  const geluProjection = byName["oracle-b1-gelu-and-projection"].medianMilliseconds;
  const pureProjection = byName["oracle-b1-pure-projection"].medianMilliseconds;
  const report = {
    generatedAt: new Date().toISOString(),
    chrome: await browser.version(),
    rounds,
    methodology: "Warm browser/font/HTTP caches, fresh page graph per case-0 to non-default mutation, force all 768 final widths.",
    runtimeContainsJavaScript: false,
    summaries,
    differentialEstimates: {
      block0AndStateHandoffMilliseconds: baseline - handoff,
      block1FcAndPreactivationWithLiveBlock0Milliseconds: baseline - fcFree,
      block1FcAndPreactivationWithOracleHandoffMilliseconds: handoff - both,
      block1AttentionAndLnMilliseconds: both - geluProjection,
      exactGeluOnceMilliseconds: geluProjection - pureProjection,
      pureProjectionMilliseconds: pureProjection,
      allVectorBoundariesFreeSpeedup: baseline / pureProjection,
    },
    note: "Deltas compare different dependency graphs and are architectural upper bounds, not additive profiler attribution.",
  };
  await fs.writeFile(
    new URL("benchmark-results.json", oracleRoot),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  if (summaries.some(({ runtimeScripts }) => runtimeScripts !== 0)) process.exitCode = 1;
  if (summaries.some(({ maximumWidthError }) => maximumWidthError !== 0)) process.exitCode = 1;
  await context.close();
} finally {
  await browser.close();
}
