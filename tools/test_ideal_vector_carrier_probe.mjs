#!/usr/bin/env node
/* Deconfounded benchmark for HTML/CSS-only ideal vector carrier probes. */

import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const output = path.join(root, "experiments", "ideal-vector-carrier");
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const cacheRounds = Number(process.env.IDEAL_VECTOR_CACHE_ROUNDS ?? 24);
const cacheWarmups = Number(process.env.IDEAL_VECTOR_CACHE_WARMUPS ?? 5);
const freshRounds = Number(process.env.IDEAL_VECTOR_FRESH_ROUNDS ?? 16);
const variants = ["fixed", "literal", "vars"];

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

function parseSettings(serialized) {
  const entries = [];
  const pattern = /"([^"]+)"\s+([-+]?\d*\.?\d+(?:e[-+]?\d+)?)/gi;
  for (const match of serialized.matchAll(pattern)) {
    entries.push({ tag: match[1], value: Number(match[2]) });
  }
  return entries;
}

function interpolateEndpoints(endpoints, fraction) {
  return endpoints[0].map(({ tag, value }, index) => ({
    tag,
    value: value * (1 - fraction) + endpoints[1][index].value * fraction,
  }));
}

function settings(entries) {
  return entries.map(({ tag, value }) => `"${tag}" ${value.toPrecision(10)}`).join(",");
}

function declarations(entries) {
  return entries.map(({ value }, index) =>
    `--v-${String(index).padStart(4, "0")}:${value.toPrecision(10)};`).join("");
}

function uniqueRule(variant, entries) {
  if (variant === "vars") return `body.fresh #state{${declarations(entries)}}`;
  if (variant === "literal") return `body.fresh #bank{font-variation-settings:${settings(entries)}}`;
  return `body.fresh #bank{font-variation-settings:"${entries[0].tag}" 0}`;
}

async function preparePage(context, stage, variant) {
  const page = await context.newPage();
  const url = pathToFileURL(path.join(output, `${stage}-${variant}.html`)).href;
  await page.goto(url, { waitUntil: "load", timeout: 120_000 });
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => {
    const bank = document.querySelector("#bank");
    return bank.scrollWidth + bank.scrollHeight;
  });
  return page;
}

async function readEndpointAxes(context, stage) {
  const page = await preparePage(context, stage, "literal");
  const serialized = await page.evaluate(() => {
    const bank = document.querySelector("#bank");
    const first = getComputedStyle(bank).fontVariationSettings;
    document.body.classList.add("case1");
    bank.scrollWidth;
    const second = getComputedStyle(bank).fontVariationSettings;
    return [first, second];
  });
  await page.close();
  const endpoints = serialized.map(parseSettings);
  if (endpoints[0].length === 0 || endpoints[0].length !== endpoints[1].length) {
    throw new Error(`${stage}: could not recover both axis vectors`);
  }
  return endpoints;
}

async function benchmarkCacheHits(context, stage, variant) {
  const page = await preparePage(context, stage, variant);
  const result = await page.evaluate(({ count, discarded }) => {
    const bank = document.querySelector("#bank");
    // Ensure both exact vectors have already been shaped in this page.
    for (const case1 of [true, false, true, false]) {
      document.body.classList.toggle("case1", case1);
      void (bank.scrollWidth + bank.scrollHeight);
    }
    const samples = [];
    let checksum = 0;
    for (let index = 0; index < count + discarded; index += 1) {
      const started = performance.now();
      document.body.classList.toggle("case1", index % 2 === 1);
      checksum += bank.scrollWidth + bank.scrollHeight;
      const elapsed = performance.now() - started;
      if (index >= discarded) samples.push(elapsed);
    }
    return { samples, checksum };
  }, { count: cacheRounds, discarded: cacheWarmups });
  await page.close();
  return { ...summarize(result.samples), samples: result.samples, checksum: result.checksum };
}

async function benchmarkFreshVectors(context, stage, variant, endpoints, reference) {
  const samples = [];
  const accuracy = [];
  for (let index = 0; index < freshRounds; index += 1) {
    const fraction = (index + 1) / (freshRounds + 1);
    const vector = interpolateEndpoints(endpoints, fraction);
    const page = await preparePage(context, stage, variant);
    const rule = uniqueRule(variant, vector);
    const expected = reference.expectedWidths[0].map((value, outputIndex) =>
      value * (1 - fraction) + reference.expectedWidths[1][outputIndex] * fraction);
    const sample = await page.evaluate(({ cssRule, targetWidths, checkAccuracy }) => {
      const style = document.createElement("style");
      style.textContent = cssRule;
      document.head.append(style);
      const bank = document.querySelector("#bank");
      const started = performance.now();
      document.body.className = "fresh";
      const checksum = bank.scrollWidth + bank.scrollHeight;
      const milliseconds = performance.now() - started;
      if (!checkAccuracy) return { milliseconds, checksum, accuracy: null };
      const actual = [...document.querySelectorAll(".output")].map((node) => {
        const range = document.createRange();
        range.selectNodeContents(node);
        return range.getBoundingClientRect().width;
      });
      const errors = actual.map((value, outputIndex) => value - targetWidths[outputIndex]);
      return {
        milliseconds,
        checksum,
        accuracy: {
          outputs: actual.length,
          rmsePx: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) /
            errors.length),
          maxAbsErrorPx: Math.max(...errors.map(Math.abs)),
        },
      };
    }, { cssRule: rule, targetWidths: expected, checkAccuracy: variant !== "fixed" });
    samples.push(sample.milliseconds);
    if (sample.accuracy) accuracy.push({ fraction, ...sample.accuracy });
    await page.close();
  }
  return {
    ...summarize(samples),
    samples,
    distinctVectors: variant === "fixed" ? 0 : freshRounds,
    controlMutations: variant === "fixed" ? freshRounds : 0,
    accuracy: accuracy.length ? {
      maximumRmsePx: Math.max(...accuracy.map(({ rmsePx }) => rmsePx)),
      maximumAbsErrorPx: Math.max(...accuracy.map(({ maxAbsErrorPx }) => maxAbsErrorPx)),
      samples: accuracy,
    } : null,
  };
}

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--disable-background-timer-throttling"],
});

try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const results = [];
  for (const stage of ["fc", "projection"]) {
    const reference = JSON.parse(await fs.readFile(
      path.join(output, `${stage}-reference.json`),
      "utf8",
    ));
    const endpoints = await readEndpointAxes(context, stage);
    if (endpoints[0].length !== reference.inputCount) {
      throw new Error(`${stage}: expected ${reference.inputCount} axes, got ${endpoints[0].length}`);
    }
    // Warm every page/font topology before measuring fresh page graphs.
    for (const variant of variants) {
      const page = await preparePage(context, stage, variant);
      await page.close();
    }
    for (const variant of variants) {
      const cacheHit = await benchmarkCacheHits(context, stage, variant);
      const freshVector = await benchmarkFreshVectors(
        context,
        stage,
        variant,
        endpoints,
        reference,
      );
      results.push({
        stage,
        variant,
        inputCount: reference.inputCount,
        outputCount: reference.outputCount,
        glyphCount: reference.glyphCount,
        cacheHit,
        freshVector,
      });
      process.stdout.write(
        `${stage.padEnd(10)} ${variant.padEnd(7)} cache ${cacheHit.medianMs.toFixed(2)} ms, ` +
        `fresh ${freshVector.medianMs.toFixed(2)} ms\n`,
      );
    }
  }
  const report = {
    chrome: await browser.version(),
    cacheRounds,
    cacheWarmups,
    freshRounds,
    methodology: {
      cacheHit: "Repeatedly revisit two already-shaped vectors in one page.",
      freshVector: "One never-before-shaped interpolated axis vector per fresh page graph; browser, font, and file caches remain warm. Rule construction/parsing occurs before timing.",
      fixed: "Fresh-page control changes selector state but keeps effective axes fixed; it has no fresh vector by definition.",
    },
    generatedAt: new Date().toISOString(),
    results,
  };
  await fs.writeFile(
    path.join(output, "benchmark-results.json"),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  const computed = results.filter(({ variant }) => variant !== "fixed");
  if (freshRounds < 8 || computed.some(({ freshVector }) =>
    freshVector.distinctVectors !== freshRounds ||
    freshVector.accuracy.maximumAbsErrorPx > 0.3)) {
    process.exitCode = 1;
  }
} finally {
  await browser.close();
}
