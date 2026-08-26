#!/usr/bin/env node
/* Benchmark CSS-computed GELU once versus avar2-per-output GELU. */

import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const origin = process.env.CSS_GELU_ORIGIN ?? "http://127.0.0.1:4178";
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const out = path.join(root, "experiments", "css-gelu-projection");
const reference = JSON.parse(await fs.readFile(path.join(out, "reference.json"), "utf8"));
const requestedSamples = Number(process.env.CSS_GELU_SAMPLES ?? reference.samples.length);
const sampleVectors = reference.samples.slice(0, requestedSamples);
const localControlSamples = Number(process.env.CSS_GELU_LOCAL_SAMPLES ?? 1);

let variants = [
  {
    name: "avar2-projection-oracle",
    url: `${origin}/experiments/hvar-vector-oracle/oracle-b1-projection-only.html`,
    kind: "avar",
    topology: "GELU avar2 remapping occurs inside each of 768 output runs",
  },
  {
    name: "exact-css-inherited",
    url: `${origin}/experiments/css-gelu-projection/exact-inherited.html`,
    kind: "preactivation",
    topology: "3,072 typed GELU values computed on #state, inherited into one #bank axis list",
  },
  {
    name: "hinge-8-inherited",
    url: `${origin}/experiments/css-gelu-projection/hinge-8-inherited.html`,
    kind: "preactivation",
    topology: "8-knot max()/calc() GELU values computed on #state and inherited",
  },
  {
    name: "hinge-16-inherited",
    url: `${origin}/experiments/css-gelu-projection/hinge-16-inherited.html`,
    kind: "preactivation",
    topology: "16-knot max()/calc() GELU values computed on #state and inherited",
  },
  {
    name: "hinge-32-inherited",
    url: `${origin}/experiments/css-gelu-projection/hinge-32-inherited.html`,
    kind: "preactivation",
    topology: "32-knot max()/calc() GELU values computed on #state and inherited",
  },
  {
    name: "ideal-post-gelu",
    url: `${origin}/experiments/css-gelu-projection/ideal-post-gelu.html`,
    kind: "post-gelu",
    topology: "Exact post-GELU vector supplied directly to the pure projection",
  },
  {
    name: "exact-css-output-local-control",
    url: `${origin}/experiments/css-gelu-projection/exact-output-local.html`,
    kind: "preactivation",
    topology: "Control: every output owns the 3,072 GELU expressions and axis list",
  },
];
if (process.env.CSS_GELU_SKIP_LOCAL === "1") {
  variants = variants.filter(({ name }) => name !== "exact-css-output-local-control");
}

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

function declarationBlock(prefix, values, digits, important = false) {
  return values.map((value, index) =>
    `--${prefix}-${String(index).padStart(digits, "0")}:${Number(value).toPrecision(12)}` +
      `${important ? "!important" : ""};`,
  ).join("");
}

function injectionRule(variant, sample) {
  if (variant.kind === "preactivation") {
    const preactivation = declarationBlock("p", sample.preactivations, 4);
    return `body.fresh #state{${preactivation}}`;
  }
  if (variant.kind === "post-gelu") {
    const hidden = declarationBlock(
      "g",
      sample.exactGelu.map((value) => value / reference.hiddenScale),
      4,
    );
    return `body.fresh #state{${hidden}}`;
  }
  const normalized = declarationBlock(
    "serial-z",
    sample.normalizedPreactivations,
    4,
    true,
  );
  const avarResidual = declarationBlock("b1-r1", sample.residuals, 3, true);
  // Beat the source page's body:has(#case-N:checked) case selectors.
  return `body.fresh.fresh.fresh .oracle-fc.oracle-residual{${normalized}${avarResidual}}`;
}

async function preparePage(context, variant) {
  const page = await context.newPage();
  await page.goto(variant.url, { waitUntil: "load", timeout: 120_000 });
  await page.evaluate(() => document.fonts.ready);
  const initial = await page.evaluate((kind) => {
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
    const selector = kind === "avar" ? ".serial-output" : ".output";
    const outputs = deepElements(selector);
    if (outputs.length !== 768) throw new Error(`expected 768 outputs, got ${outputs.length}`);
    const terminalWidth = outputs.at(-1).getBoundingClientRect().width;
    return {
      elements: deepElements("*").length,
      runtimeScripts: document.scripts.length,
      terminalWidth,
    };
  }, variant.kind);
  return { page, initial };
}

async function typedTopologyCheck(context, filename, local) {
  const variant = {
    url: `${origin}/experiments/css-gelu-projection/${filename}`,
    kind: "preactivation",
  };
  const { page } = await preparePage(context, variant);
  const result = await page.evaluate(({ isLocal }) => {
    const state = document.querySelector("#state");
    const bank = document.querySelector("#bank");
    const output = document.querySelector(".output");
    const names = ["--g-0000", "--g-0001", "--g-0042", "--g-3071"];
    const inspect = (element) => names.map((name) => {
      const typed = element.computedStyleMap().get(name);
      return {
        name,
        constructor: typed?.constructor?.name ?? null,
        value: typed?.value ?? null,
        serialized: getComputedStyle(element).getPropertyValue(name),
      };
    });
    return {
      expectedOwner: isLocal ? ".output" : "#state",
      state: inspect(state),
      bank: inspect(bank),
      output: inspect(output),
      bankAxisCount: (getComputedStyle(bank).fontVariationSettings.match(/"/g) ?? []).length / 2,
      outputAxisCount: (getComputedStyle(output).fontVariationSettings.match(/"/g) ?? []).length / 2,
    };
  }, { isLocal: local });
  await page.close();
  return result;
}

async function benchmarkFresh(context, variant) {
  const samples = [];
  const accuracy = [];
  let elements = null;
  let runtimeScripts = null;
  const vectors = variant.name === "exact-css-output-local-control" ?
    sampleVectors.slice(0, localControlSamples) : sampleVectors;
  for (const sample of vectors) {
    const { page, initial } = await preparePage(context, variant);
    elements = initial.elements;
    runtimeScripts = initial.runtimeScripts;
    const cssRule = injectionRule(variant, sample);
    const measured = await page.evaluate(({ rule, kind, expected, correction, base, scale }) => {
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
      const style = document.createElement("style");
      style.textContent = rule;
      document.head.append(style);
      const selector = kind === "avar" ? ".serial-output" : ".output";
      let outputs = deepElements(selector);
      const started = performance.now();
      document.body.classList.add("fresh");
      const widths = outputs.map((element) => element.getBoundingClientRect().width);
      const terminalWidth = widths.at(-1);
      const checksum = widths.reduce((sum, value) => sum + value, 0);
      const milliseconds = performance.now() - started;
      outputs = deepElements(selector);
      const represented = widths.map((width) => (width - base) / scale);
      const actual = kind === "avar" ? represented :
        represented.map((value, index) => value + correction[index]);
      const errors = actual.map((value, index) => value - expected[index]);
      return {
        milliseconds,
        terminalWidth,
        checksum,
        accuracy: {
          outputs: actual.length,
          rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) /
            errors.length),
          maxAbsError: Math.max(...errors.map(Math.abs)),
          cosine: actual.reduce((sum, value, index) => sum + value * expected[index], 0) /
            Math.sqrt(
              actual.reduce((sum, value) => sum + value * value, 0) *
              expected.reduce((sum, value) => sum + value * value, 0),
            ),
        },
      };
    }, {
      rule: cssRule,
      kind: variant.kind,
      expected: sample.expectedOutput,
      correction: sample.expectedOutput.map((value, index) =>
        value - sample.expectedProjection[index]),
      base: reference.baseWidth,
      scale: reference.outputScale,
    });
    samples.push({
      sample: sample.index,
      milliseconds: measured.milliseconds,
      terminalWidth: measured.terminalWidth,
      checksum: measured.checksum,
    });
    accuracy.push({ sample: sample.index, ...measured.accuracy });
    await page.close();
  }
  const times = samples.map(({ milliseconds }) => milliseconds);
  return {
    ...summarize(times),
    distinctVectors: samples.length,
    elements,
    runtimeScripts,
    samples,
    accuracy: {
      maximumRmse: Math.max(...accuracy.map(({ rmse }) => rmse)),
      maximumAbsError: Math.max(...accuracy.map(({ maxAbsError }) => maxAbsError)),
      minimumCosine: Math.min(...accuracy.map(({ cosine }) => cosine)),
      samples: accuracy,
    },
  };
}

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--disable-background-timer-throttling"],
});

try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  for (const variant of variants) {
    const { page } = await preparePage(context, variant);
    await page.close();
  }

  const topology = {
    inherited: await typedTopologyCheck(context, "exact-inherited.html", false),
    outputLocal: process.env.CSS_GELU_SKIP_LOCAL === "1" ? null :
      await typedTopologyCheck(context, "exact-output-local.html", true),
  };
  const results = [];
  for (const variant of variants) {
    const freshVector = await benchmarkFresh(context, variant);
    results.push({ ...variant, freshVector });
    process.stderr.write(
      `${variant.name.padEnd(31)} ${freshVector.medianMs.toFixed(1)} ms, ` +
      `RMSE ${freshVector.accuracy.maximumRmse.toFixed(5)}\n`,
    );
  }

  const byName = Object.fromEntries(results.map((entry) => [entry.name, entry]));
  const ideal = byName["ideal-post-gelu"].freshVector.medianMs;
  const report = {
    generatedAt: new Date().toISOString(),
    chrome: await browser.version(),
    freshVectors: sampleVectors.length,
    localControlFreshVectors: localControlSamples,
    runtimeContainsJavaScript: false,
    methodology: "Each timed sample uses a fresh page/layout graph and a never-before-used interpolation of browser-captured block-1 vectors. HTTP, browser, and font caches stay warm. The external harness inserts the vector rule before timing; timing begins at the selector mutation and ends after forcing the terminal output width.",
    topologyVerification: topology,
    results,
    comparisons: {
      exactInheritedVsAvar2Speedup:
        byName["avar2-projection-oracle"].freshVector.medianMs /
        byName["exact-css-inherited"].freshVector.medianMs,
      exactInheritedOverIdealMs:
        byName["exact-css-inherited"].freshVector.medianMs - ideal,
      hinge8OverIdealMs: byName["hinge-8-inherited"].freshVector.medianMs - ideal,
      hinge16OverIdealMs: byName["hinge-16-inherited"].freshVector.medianMs - ideal,
      hinge32OverIdealMs: byName["hinge-32-inherited"].freshVector.medianMs - ideal,
      outputLocalVsInheritedSlowdown: byName["exact-css-output-local-control"] ?
        byName["exact-css-output-local-control"].freshVector.medianMs /
          byName["exact-css-inherited"].freshVector.medianMs : null,
    },
  };
  await fs.writeFile(
    path.join(out, "benchmark-results.json"),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  if (results.some(({ name, freshVector }) =>
    freshVector.distinctVectors !==
      (name === "exact-css-output-local-control" ? localControlSamples : sampleVectors.length) ||
    freshVector.runtimeScripts !== 0)) {
    process.exitCode = 1;
  }
} finally {
  await browser.close();
}
