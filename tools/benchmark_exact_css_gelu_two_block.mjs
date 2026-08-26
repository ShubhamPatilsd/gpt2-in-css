#!/usr/bin/env node
/* Compare the existing and compute-once exact-CSS-GELU two-block pages. */

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
const rounds = Number(process.env.EXACT_CSS_GELU_ROUNDS ?? 6);

const variants = [
  {
    name: "existing-avar2",
    pageFile: "connected-two-block-serial-projection-layoutless.html",
  },
  {
    name: "exact-css-gelu-once",
    pageFile: "connected-two-block-exact-css-gelu-layoutless.html",
  },
];

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
    page.on("response", async (response) => {
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
  const initial = await page.evaluate(() => {
    function deepElements(selector) {
      const found = [];
      const visit = (node) => {
        found.push(...node.querySelectorAll(selector));
        for (const child of node.querySelectorAll("*")) {
          if (child.shadowRoot) visit(child.shadowRoot);
        }
      };
      visit(document);
      return found;
    }
    const outputs = deepElements(".serial-output");
    if (outputs.length !== 768) throw new Error(`expected 768 outputs, got ${outputs.length}`);
    const checksum = outputs.reduce(
      (sum, element) => sum + element.getBoundingClientRect().width,
      0,
    );
    const b0Projection = deepElements(".projection-0")[0];
    const b1Projection = deepElements(".serial-root")[0];
    return {
      elements: deepElements("*").length,
      outputs: outputs.length,
      runtimeScripts: document.scripts.length,
      checksum,
      b0ExactValue: b0Projection ?
        getComputedStyle(b0Projection).getPropertyValue("--b0-g0") : "",
      b1ExactValue: b1Projection ?
        getComputedStyle(b1Projection).getPropertyValue("--b1-g-0000") : "",
      b1AxisCount: b1Projection ?
        (getComputedStyle(b1Projection).fontVariationSettings.match(/"/g) ?? []).length / 2 : 0,
    };
  });
  return { page, initial, resources };
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
  // Warm the complete resource and topology set without timing it.
  for (const variant of variants) {
    const { page } = await preparePage(context, variant);
    await page.close();
    variant.samples = [];
  }

  for (let round = 0; round < rounds; round += 1) {
    const mode = 1 + (round % 3);
    const order = round % 2 ? [...variants].reverse() : variants;
    for (const variant of order) {
      const { page, initial } = await preparePage(context, variant);
      const measured = await page.evaluate((caseIndex) => {
        function deepElements(selector) {
          const found = [];
          const visit = (node) => {
            found.push(...node.querySelectorAll(selector));
            for (const child of node.querySelectorAll("*")) {
              if (child.shadowRoot) visit(child.shadowRoot);
            }
          };
          visit(document);
          return found;
        }
        const outputs = deepElements(".serial-output");
        const started = performance.now();
        document.querySelector(`#case-${caseIndex}`).checked = true;
        const widths = outputs.map((element) => element.getBoundingClientRect().width);
        const milliseconds = performance.now() - started;
        return {
          milliseconds,
          widths,
          checksum: widths.reduce((sum, value) => sum + value, 0),
        };
      }, mode);
      const outputs = measured.widths.map(
        (width) => (width - reference.block1SerialProjectionBase) /
          reference.block1OutputScale,
      );
      variant.samples.push({
        round,
        mode,
        milliseconds: measured.milliseconds,
        checksum: measured.checksum,
        widths: measured.widths,
        outputs,
        toExact: errorSummary(outputs, reference.block1ExactOutputs[mode]),
        toRepresented: errorSummary(outputs, reference.block1RepresentedOutputs[mode]),
        elements: initial.elements,
        runtimeScripts: initial.runtimeScripts,
      });
      await page.close();
    }
    process.stderr.write(`fresh page round ${round + 1}/${rounds}\n`);
  }

  // Validate every coordinate for all four reference cases, including the
  // default case that is intentionally excluded from mutation timing.
  for (const variant of variants) {
    const { page } = await preparePage(context, variant);
    variant.validation = [];
    for (let mode = 0; mode < 4; mode += 1) {
      const widths = await page.evaluate((caseIndex) => {
        function deepElements(selector) {
          const found = [];
          const visit = (node) => {
            found.push(...node.querySelectorAll(selector));
            for (const child of node.querySelectorAll("*")) {
              if (child.shadowRoot) visit(child.shadowRoot);
            }
          };
          visit(document);
          return found;
        }
        document.querySelector(`#case-${caseIndex}`).checked = true;
        return deepElements(".serial-output")
          .map((element) => element.getBoundingClientRect().width);
      }, mode);
      const outputs = widths.map(
        (width) => (width - reference.block1SerialProjectionBase) /
          reference.block1OutputScale,
      );
      variant.validation.push({
        mode,
        widths,
        outputs,
        toExact: errorSummary(outputs, reference.block1ExactOutputs[mode]),
        toRepresented: errorSummary(outputs, reference.block1RepresentedOutputs[mode]),
      });
    }
    await page.close();
  }

  const directAgreement = [];
  for (let mode = 0; mode < 4; mode += 1) {
    const baseline = variants[0].validation[mode];
    const exact = variants[1].validation[mode];
    directAgreement.push({
      mode,
      ...errorSummary(exact.outputs, baseline.outputs),
    });
  }

  const summaries = variants.map((variant) => {
    const times = variant.samples.map(({ milliseconds }) => milliseconds);
    return {
      name: variant.name,
      pageFile: variant.pageFile,
      elements: variant.samples[0].elements,
      runtimeScripts: variant.samples[0].runtimeScripts,
      ...summarize(times),
      maximumRmseToExact: Math.max(...variant.validation.map(({ toExact }) => toExact.rmse)),
      maximumAbsErrorToExact: Math.max(
        ...variant.validation.map(({ toExact }) => toExact.maxAbsError),
      ),
      maximumRmseToRepresented: Math.max(
        ...variant.validation.map(({ toRepresented }) => toRepresented.rmse),
      ),
      maximumAbsErrorToRepresented: Math.max(
        ...variant.validation.map(({ toRepresented }) => toRepresented.maxAbsError),
      ),
      samples: variant.samples.map(({ widths, outputs, ...sample }) => sample),
      validation: variant.validation.map(({ widths, outputs, ...entry }) => entry),
    };
  });
  const report = {
    generatedAt: new Date().toISOString(),
    chrome: await browser.version(),
    rounds,
    cases: [...new Set(variants[0].samples.map(({ mode }) => mode))],
    runtimeContainsJavaScript: false,
    methodology: "Warm browser/font/HTTP caches, then a fresh page/layout graph for every case-0 to non-default case mutation. Each timing forces all 768 final widths. Variant order alternates by round.",
    resourceProfiles,
    summaries,
    directAgreement: {
      maximumRmse: Math.max(...directAgreement.map(({ rmse }) => rmse)),
      maximumAbsError: Math.max(...directAgreement.map(({ maxAbsError }) => maxAbsError)),
      samples: directAgreement,
    },
    speedup: summaries[0].medianMs / summaries[1].medianMs,
  };
  await fs.writeFile(
    path.join(out, "exact-css-gelu-two-block-results.json"),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  if (summaries.some(({ runtimeScripts }) => runtimeScripts !== 0)) process.exitCode = 1;
  await context.close();
} finally {
  await browser.close();
}
