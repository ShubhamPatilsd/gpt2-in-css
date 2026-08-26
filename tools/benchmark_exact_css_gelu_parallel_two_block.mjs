#!/usr/bin/env node
/* Compare serial and parallel block-1 graphs with compute-once CSS GELU. */

import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const origin = process.env.EXACT_CSS_GELU_ORIGIN ?? "http://127.0.0.1:4178";
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const out = path.join(root, "experiments", "avar2-gelu-linear-hvar-full-mlp-g13");
const reference = JSON.parse(await fs.readFile(path.join(out, "reference.json"), "utf8"));
const rounds = Number(process.env.EXACT_PARALLEL_ROUNDS ?? 6);

const allVariants = [
  {
    name: "old-parallel-avar2",
    pageFile: "connected-two-block-shadow-staged-layoutless.html",
    outputSelector: ".b1-output",
    outputBase: reference.baseAdvance,
  },
  {
    name: "exact-serial",
    pageFile: "connected-two-block-exact-css-gelu-layoutless.html",
    outputSelector: ".serial-output",
    outputBase: reference.block1SerialProjectionBase,
  },
  {
    name: "exact-inline",
    pageFile: "connected-two-block-exact-css-gelu-inline-layoutless.html",
    outputSelector: ".serial-output",
    outputBase: reference.block1SerialProjectionBase,
  },
  ...[2, 3, 4, 5, 7].map((branches) => ({
    name: `exact-hybrid-${branches}`,
    pageFile: `connected-two-block-hybrid-${branches}-exact-css-gelu-layoutless.html`,
    outputSelector: ".b1-output",
    outputBase: reference.baseAdvance,
  })),
  {
    name: "exact-shadow-hybrid-1",
    pageFile: "connected-two-block-shadow-hybrid-1-exact-css-gelu-layoutless.html",
    outputSelector: ".b1-output",
    outputBase: reference.block1SerialProjectionBase,
  },
  ...[2, 3, 4].map((branches) => ({
    name: `exact-shadow-hybrid-${branches}`,
    pageFile: `connected-two-block-shadow-hybrid-${branches}-exact-css-gelu-layoutless.html`,
    outputSelector: ".b1-output",
    outputBase: reference.baseAdvance,
  })),
  {
    name: "exact-parallel",
    pageFile: "connected-two-block-parallel-exact-css-gelu-layoutless.html",
    outputSelector: ".b1-output",
    outputBase: reference.baseAdvance,
  },
];
const requestedNames = new Set(
  (process.env.EXACT_PARALLEL_ONLY ?? "").split(",").filter(Boolean),
);
const variants = requestedNames.size ?
  allVariants.filter(({ name }) => requestedNames.has(name)) : allVariants;
if (variants.length === 0) throw new Error("EXACT_PARALLEL_ONLY selected no variants");

function percentile(values, fraction) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor((sorted.length - 1) * fraction)];
}

function summarize(values) {
  return {
    medianMs: percentile(values, 0.5),
    p10Ms: percentile(values, 0.1),
    p90Ms: percentile(values, 0.9),
    minMs: Math.min(...values),
    maxMs: Math.max(...values),
  };
}

function errorSummary(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) /
      errors.length),
    maxAbsError: Math.max(...errors.map(Math.abs)),
  };
}

async function preparePage(context, variant, captureResources = false) {
  const page = await context.newPage();
  const resources = new Map();
  if (captureResources) {
    page.on("response", (response) => {
      const length = Number(response.headers()["content-length"] ?? 0);
      resources.set(response.url(), {
        url: response.url(),
        contentType: response.headers()["content-type"] ?? "",
        bytes: length,
      });
    });
  }
  await page.goto(
    `${origin}/experiments/avar2-gelu-linear-hvar-full-mlp-g13/${variant.pageFile}`,
    { waitUntil: "load", timeout: 180_000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const initial = await page.evaluate((selector) => {
    function deepElements(query) {
      const found = [];
      const visit = (node) => {
        found.push(...node.querySelectorAll(query));
        for (const child of node.querySelectorAll("*")) {
          if (child.shadowRoot) visit(child.shadowRoot);
        }
      };
      visit(document);
      return found;
    }
    const outputs = deepElements(selector);
    if (outputs.length !== 768) throw new Error(`expected 768 outputs, got ${outputs.length}`);
    const checksum = outputs.reduce(
      (sum, element) => sum + element.getBoundingClientRect().width,
      0,
    );
    const b0Projection = deepElements(".projection-0")[0];
    const b1Projection = deepElements(".b1-projection-0,.serial-root")[0];
    const style = b1Projection ? getComputedStyle(b1Projection) : null;
    return {
      elements: deepElements("*").length,
      outputs: outputs.length,
      runtimeScripts: document.scripts.length,
      checksum,
      b0ExactValue: b0Projection ?
        getComputedStyle(b0Projection).getPropertyValue("--b0-g0") : "",
      b1ExactValue: style ?
        (style.getPropertyValue("--b1-g0") ||
          style.getPropertyValue("--b1-g-0000")) : "",
    };
  }, variant.outputSelector);
  return { page, initial, resources };
}

function decode(widths, variant) {
  return widths.map(
    (width) => (width - variant.outputBase) / reference.block1OutputScale,
  );
}

async function resourceProfile(browser, variant) {
  const context = await browser.newContext({ viewport: { width: 1000, height: 120 } });
  const { page, initial, resources } = await preparePage(context, variant, true);
  await page.waitForTimeout(100);
  const entries = [...resources.values()];
  const byType = {};
  for (const entry of entries) {
    const type = entry.contentType.split(";")[0] || "unknown";
    byType[type] = (byType[type] ?? 0) + entry.bytes;
  }
  await page.close();
  await context.close();
  return {
    requests: entries.length,
    totalBytes: entries.reduce((sum, entry) => sum + entry.bytes, 0),
    byContentType: byType,
    initial,
  };
}

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--disable-background-timer-throttling"],
});

try {
  const resourceProfiles = {};
  for (const variant of variants) {
    resourceProfiles[variant.name] = await resourceProfile(browser, variant);
  }

  const context = await browser.newContext({ viewport: { width: 1000, height: 120 } });
  for (const variant of variants) {
    const { page } = await preparePage(context, variant);
    await page.close();
    variant.samples = [];
  }

  for (let round = 0; round < rounds; round += 1) {
    const mode = 1 + (round % 3);
    const rotation = round % variants.length;
    const order = [...variants.slice(rotation), ...variants.slice(0, rotation)];
    for (const variant of order) {
      const { page, initial } = await preparePage(context, variant);
      const measured = await page.evaluate(({ caseIndex, selector }) => {
        function deepElements(query) {
          const found = [];
          const visit = (node) => {
            found.push(...node.querySelectorAll(query));
            for (const child of node.querySelectorAll("*")) {
              if (child.shadowRoot) visit(child.shadowRoot);
            }
          };
          visit(document);
          return found;
        }
        const outputs = deepElements(selector);
        const started = performance.now();
        document.querySelector(`#case-${caseIndex}`).checked = true;
        const widths = outputs.map((element) => element.getBoundingClientRect().width);
        return {
          milliseconds: performance.now() - started,
          widths,
          checksum: widths.reduce((sum, value) => sum + value, 0),
        };
      }, { caseIndex: mode, selector: variant.outputSelector });
      const outputs = decode(measured.widths, variant);
      variant.samples.push({
        round,
        mode,
        milliseconds: measured.milliseconds,
        checksum: measured.checksum,
        toExact: errorSummary(outputs, reference.block1ExactOutputs[mode]),
        toRepresented: errorSummary(outputs, reference.block1RepresentedOutputs[mode]),
        elements: initial.elements,
        runtimeScripts: initial.runtimeScripts,
      });
      await page.close();
    }
    process.stderr.write(`fresh page round ${round + 1}/${rounds}\n`);
  }

  for (const variant of variants) {
    const { page } = await preparePage(context, variant);
    variant.validation = [];
    for (let mode = 0; mode < 4; mode += 1) {
      const widths = await page.evaluate(({ caseIndex, selector }) => {
        function deepElements(query) {
          const found = [];
          const visit = (node) => {
            found.push(...node.querySelectorAll(query));
            for (const child of node.querySelectorAll("*")) {
              if (child.shadowRoot) visit(child.shadowRoot);
            }
          };
          visit(document);
          return found;
        }
        document.querySelector(`#case-${caseIndex}`).checked = true;
        return deepElements(selector)
          .map((element) => element.getBoundingClientRect().width);
      }, { caseIndex: mode, selector: variant.outputSelector });
      const outputs = decode(widths, variant);
      variant.validation.push({
        mode,
        toExact: errorSummary(outputs, reference.block1ExactOutputs[mode]),
        toRepresented: errorSummary(outputs, reference.block1RepresentedOutputs[mode]),
      });
    }
    await page.close();
  }

  const summaries = variants.map((variant) => ({
    name: variant.name,
    pageFile: variant.pageFile,
    elements: variant.samples[0].elements,
    runtimeScripts: variant.samples[0].runtimeScripts,
    ...summarize(variant.samples.map(({ milliseconds }) => milliseconds)),
    maximumRmseToExact: Math.max(...variant.validation.map(({ toExact }) => toExact.rmse)),
    maximumAbsErrorToExact: Math.max(
      ...variant.validation.map(({ toExact }) => toExact.maxAbsError),
    ),
    maximumRmseToRepresented: Math.max(
      ...variant.validation.map(({ toRepresented }) => toRepresented.rmse),
    ),
    samples: variant.samples,
    validation: variant.validation,
  }));
  const byName = Object.fromEntries(summaries.map((entry) => [entry.name, entry]));
  const ratio = (baseline, candidate) =>
    byName[baseline] && byName[candidate] ?
      byName[baseline].medianMs / byName[candidate].medianMs : null;
  const report = {
    generatedAt: new Date().toISOString(),
    chrome: await browser.version(),
    rounds,
    runtimeContainsJavaScript: false,
    methodology: "Warm browser/font/HTTP caches, then a fresh page/layout graph for every case-0 to non-default case mutation. Every timing forces all 768 final widths. Variant order rotates by round.",
    resourceProfiles,
    summaries,
    speedups: {
      exactParallelOverExactSerial: ratio("exact-serial", "exact-parallel"),
      exactParallelOverOldParallel: ratio("old-parallel-avar2", "exact-parallel"),
      exactHybrid2OverExactSerial: ratio("exact-serial", "exact-hybrid-2"),
      exactHybrid3OverExactSerial: ratio("exact-serial", "exact-hybrid-3"),
      exactHybrid4OverExactSerial: ratio("exact-serial", "exact-hybrid-4"),
      exactHybrid5OverExactSerial: ratio("exact-serial", "exact-hybrid-5"),
      exactHybrid7OverExactSerial: ratio("exact-serial", "exact-hybrid-7"),
      exactShadowHybrid2OverExactSerial:
        ratio("exact-serial", "exact-shadow-hybrid-2"),
      exactShadowHybrid1OverExactSerial:
        ratio("exact-serial", "exact-shadow-hybrid-1"),
      exactShadowHybrid3OverExactSerial:
        ratio("exact-serial", "exact-shadow-hybrid-3"),
      exactShadowHybrid4OverExactSerial:
        ratio("exact-serial", "exact-shadow-hybrid-4"),
      exactInlineOverExactSerial: ratio("exact-serial", "exact-inline"),
    },
  };
  const outputName = process.env.EXACT_PARALLEL_OUTPUT ??
    "exact-css-gelu-parallel-two-block-results.json";
  await fs.writeFile(
    path.join(out, outputName),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  if (summaries.some(({ runtimeScripts }) => runtimeScripts !== 0)) process.exitCode = 1;
  await context.close();
} finally {
  await browser.close();
}
