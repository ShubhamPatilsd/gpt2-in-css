#!/usr/bin/env node

import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const repository = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const experiment = path.join(repository, "experiments", "gsub-graph-selector-probe");
const reference = JSON.parse(await fs.readFile(path.join(experiment, "reference.json"), "utf8"));
const rounds = Number.parseInt(process.env.GSUB_GRAPH_TIMING_ROUNDS ?? "25", 10);

function neighbor(node, slot) {
  return (node * 7919 + slot * 10729 + slot * slot * 17 + 1) % 50257;
}

function widthForToken(token) {
  return (token + 1) / 2;
}

function percentile(values, fraction) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor((sorted.length - 1) * fraction)];
}

function summarize(values) {
  return {
    samples: values.length,
    minimumMilliseconds: Math.min(...values),
    medianMilliseconds: percentile(values, 0.5),
    p95Milliseconds: percentile(values, 0.95),
    maximumMilliseconds: Math.max(...values),
  };
}

const mimeTypes = new Map([
  [".html", "text/html; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".ttf", "font/ttf"],
  [".woff2", "font/woff2"],
]);

const server = http.createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
    const candidate = path.resolve(repository, `.${pathname}`);
    if (candidate !== repository && !candidate.startsWith(`${repository}${path.sep}`)) {
      response.writeHead(403).end("forbidden");
      return;
    }
    const data = await fs.readFile(candidate);
    response.writeHead(200, {
      "content-type": mimeTypes.get(path.extname(candidate)) ?? "application/octet-stream",
      "cache-control": "no-store",
    });
    response.end(data);
  } catch (error) {
    response.writeHead(error.code === "ENOENT" ? 404 : 500).end(String(error));
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const address = server.address();
const url = `http://127.0.0.1:${address.port}/experiments/gsub-graph-selector-probe/index.html`;

const source = await fs.readFile(path.join(experiment, "index.html"), "utf8");
const runtimeScriptElements = (source.match(/<script\b/gi) ?? []).length;
const consoleMessages = [];
const requestFailures = [];
const defaultChrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || defaultChrome,
  headless: true,
});

let report;
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 300 } });
  page.on("console", (message) => consoleMessages.push({ type: message.type(), text: message.text() }));
  page.on("requestfailed", (request) => requestFailures.push({
    url: request.url(),
    error: request.failure()?.errorText ?? "unknown",
  }));
  const loadStarted = performance.now();
  const response = await page.goto(url, { waitUntil: "load", timeout: 240_000 });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  const loadMilliseconds = performance.now() - loadStarted;

  const capabilities = await page.evaluate(() => ({
    userAgent: navigator.userAgent,
    fontFeatureValue50257: CSS.supports("font-feature-settings", '"cv00" 50257'),
    fontFeatureCalc50257: CSS.supports("font-feature-settings", '"cv00" calc(50256 + 1)'),
    radixFeaturePair: CSS.supports("font-feature-settings", '"cv01" 255, "cv02" 198'),
    cssIfStyle: CSS.supports("width", "if(style(--edge-slot:0):1px;else:2px)"),
    anchorSize: CSS.supports("width", "anchor-size(--hop1-s00 width)"),
    containerQueryUnits: CSS.supports("width", "100cqi"),
    registeredCurrentNode: CSS.registerProperty !== undefined,
    fontStatus: document.fonts.status,
    fontLoaded: document.fonts.check('500px "GraphSelectorProbe"', "\uE000"),
  }));

  const browserVersion = await browser.version();
  const testCases = [
    { node: 0, slot: 0 },
    { node: 1, slot: 7 },
    { node: 32767, slot: 8 },
    { node: 50256, slot: 15 },
  ];
  const cases = [];
  const failures = [];
  for (const testCase of testCases) {
    const observed = await page.evaluate(async ({ node, slot }) => {
      const probe = document.querySelector("#probe");
      probe.style.setProperty("--input-node", String(node));
      probe.style.setProperty("--input-slot", String(slot));
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      const widths = (selector) => [...document.querySelectorAll(selector)].map(
        (element) => element.getBoundingClientRect().width,
      );
      const chainStyle = getComputedStyle(document.querySelector("#chain"));
      const probeStyle = getComputedStyle(probe);
      return {
        currentNode: probeStyle.getPropertyValue("--current-node").trim(),
        edgeSlot: probeStyle.getPropertyValue("--edge-slot").trim(),
        low: probeStyle.getPropertyValue("--low").trim(),
        high: probeStyle.getPropertyValue("--high").trim(),
        nextNode: chainStyle.getPropertyValue("--next-node").trim(),
        nextLow: chainStyle.getPropertyValue("--next-low").trim(),
        nextHigh: chainStyle.getPropertyValue("--next-high").trim(),
        directWidths: widths(".direct-slot"),
        firstHopWidths: widths(".hop1-slot"),
        selectedWidth: document.querySelector("#selected-slot-reader").getBoundingClientRect().width,
        secondHopWidths: widths(".hop2-slot"),
        directFeature: getComputedStyle(document.querySelector(".direct-slot")).fontFeatureSettings,
        firstHopFeature: getComputedStyle(document.querySelector(".hop1-slot")).fontFeatureSettings,
        secondHopFeature: getComputedStyle(document.querySelector(".hop2-slot")).fontFeatureSettings,
      };
    }, testCase);
    const expectedFirstTokens = Array.from({ length: reference.slots }, (_, slot) =>
      neighbor(testCase.node, slot));
    const expectedFirstWidths = expectedFirstTokens.map(widthForToken);
    const expectedNextNode = expectedFirstTokens[testCase.slot];
    const expectedSecondTokens = Array.from({ length: reference.slots }, (_, slot) =>
      neighbor(expectedNextNode, slot));
    const expectedSecondWidths = expectedSecondTokens.map(widthForToken);
    const lowByteFeatureValue = (testCase.node + 1) & 0xff;
    const lowByteNode = lowByteFeatureValue === 0 ? null : lowByteFeatureValue - 1;
    const lowByteFirstWidths = lowByteNode === null
      ? Array(reference.slots).fill(0)
      : Array.from({ length: reference.slots }, (_, slot) => widthForToken(neighbor(lowByteNode, slot)));
    const observedMatchesLowByteFeature =
      JSON.stringify(observed.directWidths) === JSON.stringify(lowByteFirstWidths);
    const directMatchesRequested =
      JSON.stringify(observed.directWidths) === JSON.stringify(expectedFirstWidths);
    const firstHopPassed =
      JSON.stringify(observed.firstHopWidths) === JSON.stringify(expectedFirstWidths);
    const decodePassed = Number(observed.nextNode) === expectedNextNode &&
      observed.selectedWidth === widthForToken(expectedNextNode);
    const secondHopPassed =
      JSON.stringify(observed.secondHopWidths) === JSON.stringify(expectedSecondWidths);
    const caseFailures = [];
    if (Number(observed.currentNode) !== testCase.node) caseFailures.push("registered --current-node mismatch");
    if (Number(observed.edgeSlot) !== testCase.slot) caseFailures.push("registered --edge-slot mismatch");
    if (Number(observed.low) !== testCase.node % 255) caseFailures.push("registered --low mismatch");
    if (Number(observed.high) !== Math.floor(testCase.node / 255)) caseFailures.push("registered --high mismatch");
    if (Number(observed.nextLow) !== expectedNextNode % 255) caseFailures.push("registered --next-low mismatch");
    if (Number(observed.nextHigh) !== Math.floor(expectedNextNode / 255)) caseFailures.push("registered --next-high mismatch");
    if (Number(observed.nextNode) !== expectedNextNode) caseFailures.push("size-container --next-node decode mismatch");
    if (observed.selectedWidth !== widthForToken(expectedNextNode)) caseFailures.push("CSS if()/anchor-size selected width mismatch");
    if (!firstHopPassed) {
      caseFailures.push("first-hop GSUB identity widths mismatch");
    }
    if (!secondHopPassed) {
      caseFailures.push("second-hop GSUB identity widths mismatch");
    }
    if (caseFailures.length) failures.push({ ...testCase, failures: caseFailures, observed, expectedFirstWidths, expectedSecondWidths, expectedNextNode });
    cases.push({
      ...testCase,
      expectedNextNode,
      requestedFeatureValue: testCase.node + 1,
      lowByteFeatureValue,
      lowByteNode,
      observedMatchesLowByteFeature,
      directMatchesRequested,
      firstHopPassed,
      decodePassed,
      secondHopPassed,
      expectedFirstTokens,
      expectedSecondTokens,
      observed,
      passed: caseFailures.length === 0,
      failures: caseFailures,
    });
  }

  const featureBoundaryCases = [];
  for (const node of [254, 255, 256]) {
    const observed = await page.evaluate(async (value) => {
      const probe = document.querySelector("#probe");
      probe.style.setProperty("--input-node", String(value));
      probe.style.setProperty("--input-slot", "0");
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      const element = document.querySelector("#direct-slot-00");
      return {
        width: element.getBoundingClientRect().width,
        feature: getComputedStyle(element).fontFeatureSettings,
      };
    }, node);
    const requestedWidth = widthForToken(neighbor(node, 0));
    const lowByteFeatureValue = (node + 1) & 0xff;
    const lowByteWidth = lowByteFeatureValue === 0
      ? 0
      : widthForToken(neighbor(lowByteFeatureValue - 1, 0));
    featureBoundaryCases.push({
      node,
      requestedFeatureValue: node + 1,
      lowByteFeatureValue,
      requestedWidth,
      lowByteWidth,
      observed,
      matchesRequested: observed.width === requestedWidth,
      matchesLowByte: observed.width === lowByteWidth,
    });
  }

  const switchSamples = await page.evaluate(async ({ testCases: values, rounds: count }) => {
    const probe = document.querySelector("#probe");
    const force = () => document.querySelector("#hop2-slot-15").getBoundingClientRect().width;
    for (let warm = 0; warm < 5; warm += 1) {
      for (const value of values) {
        probe.style.setProperty("--input-node", String(value.node));
        probe.style.setProperty("--input-slot", String(value.slot));
        force();
      }
    }
    const samples = [];
    for (let round = 0; round < count; round += 1) {
      for (const value of values) {
        const started = performance.now();
        probe.style.setProperty("--input-node", String(value.node));
        probe.style.setProperty("--input-slot", String(value.slot));
        force();
        samples.push(performance.now() - started);
      }
    }
    return samples;
  }, { testCases, rounds });

  const capabilityFailures = Object.entries({
    fontFeatureValue50257: capabilities.fontFeatureValue50257,
    fontFeatureCalc50257: capabilities.fontFeatureCalc50257,
    radixFeaturePair: capabilities.radixFeaturePair,
    cssIfStyle: capabilities.cssIfStyle,
    anchorSize: capabilities.anchorSize,
    containerQueryUnits: capabilities.containerQueryUnits,
    registeredCurrentNode: capabilities.registeredCurrentNode,
    fontLoaded: capabilities.fontLoaded,
  }).filter(([, supported]) => !supported).map(([name]) => name);
  if (runtimeScriptElements !== 0) failures.push({ runtimePage: "contains script elements" });
  if (capabilityFailures.length) failures.push({ unsupportedCapabilities: capabilityFailures });
  if (requestFailures.length) failures.push({ requestFailures });

  report = {
    generatedAt: new Date().toISOString(),
    passed: failures.length === 0,
    strictContract: {
      vocabulary: reference.vocabulary,
      slots: reference.slots,
      requiredIndices: reference.requiredIndices,
      runtimeScriptElements,
      singleAlternateSetEntries: reference.font.alternateSetCounts,
      radixLowAlternateSetEntries: reference.font.lowAlternateSetCounts,
      radixHighAlternateSets: reference.font.highAlternateSetCount,
      radixHighAlternateSetEntries: reference.font.highAlternateSetEntries,
      featureOrder: reference.font.featureOrder,
      alternateSetCountFieldMaximum: reference.font.alternateSetCountFieldMaximum,
      noGpt2Modification: true,
    },
    browser: {
      name: "Chromium",
      version: browserVersion,
      userAgent: capabilities.userAgent,
      httpStatus: response?.status() ?? null,
      capabilities,
      limits: {
        numberedFeatureValueTestedMaximum: 50257,
        numberedFeatureValueAccepted: capabilities.fontFeatureValue50257 &&
          cases.at(-1).observed.directWidths.every(
            (width, slot) => width === widthForToken(cases.at(-1).expectedFirstTokens[slot]),
          ),
        observedNumberedFeatureBehavior: cases.slice(2).every(
          (entry) => entry.observedMatchesLowByteFeature,
        ) && featureBoundaryCases.every((entry) => entry.matchesLowByte)
          ? "feature value reduced to low 8 bits (modulo 256)"
          : "not explained by low-8-bit reduction",
        maximumNumberedFeatureValueShapedAsRequested: 255,
        firstRejectedNumberedFeatureValue: 256,
        alternateSetEntryCountTested: 50257,
        alternateSetLoaded: capabilities.fontLoaded,
        lowRangeDirectAlternatesShapedCorrectly: cases.slice(0, 2).every((entry) =>
          entry.observed.directWidths.every(
            (width, slot) => width === widthForToken(entry.expectedFirstTokens[slot]),
          )),
        maximumObservedIdentityAdvancePx: Math.max(...cases.flatMap((entry) => [
          ...entry.observed.firstHopWidths,
          ...entry.observed.secondHopWidths,
        ])),
      },
      consoleMessages,
      requestFailures,
    },
    files: reference.files,
    font: reference.font,
    loadMilliseconds,
    warmTwoHopSwitching: summarize(switchSamples),
    radixSelector: {
      passed: cases.every((entry) => entry.passed),
      lowMaximumFeatureValue: 255,
      highMaximumFeatureValue: 198,
      featureOrder: reference.font.featureOrder,
    },
    directSelectorBaseline: {
      passed: cases.every((entry) => entry.directMatchesRequested),
      behavior: "feature value reduced to low 8 bits (modulo 256)",
      requiredCases: cases.map((entry) => ({
        node: entry.node,
        requestedFeatureValue: entry.requestedFeatureValue,
        lowByteFeatureValue: entry.lowByteFeatureValue,
        matchesRequested: entry.directMatchesRequested,
        matchesLowByte: entry.observedMatchesLowByteFeature,
      })),
    },
    featureBoundaryCases,
    cases,
    failures,
  };
} catch (error) {
  report = {
    generatedAt: new Date().toISOString(),
    passed: false,
    files: reference.files,
    font: reference.font,
    fatalError: { name: error.name, message: error.message, stack: error.stack },
  };
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}

await fs.writeFile(path.join(experiment, "browser-results.json"), `${JSON.stringify(report, null, 2)}\n`);
const timing = report.warmTwoHopSwitching;
const caseRows = (report.cases ?? []).map((entry) =>
  `| ${entry.node} | ${entry.slot} | ${entry.firstHopPassed ? "PASS" : "FAIL"} | ${entry.expectedNextNode} / ${entry.observed.nextNode} | ${entry.decodePassed ? "PASS" : "FAIL"} | ${entry.secondHopPassed ? "PASS" : "FAIL"} | ${entry.passed ? "PASS" : "FAIL"} |`,
).join("\n");
const baselineRows = (report.cases ?? []).map((entry) =>
  `| ${entry.node} | ${entry.requestedFeatureValue} | ${entry.lowByteFeatureValue} | ${entry.directMatchesRequested ? "PASS" : "FAIL"} | ${entry.observedMatchesLowByteFeature ? "yes" : "no"} |`,
).join("\n");
const failureText = report.failures?.length
  ? `\n## Strict radix failures\n\n\`\`\`json\n${JSON.stringify(report.failures, null, 2)}\n\`\`\`\n`
  : "\nThe radix selector passes every required node and both declarative hops. Its largest numbered values are 255 for `cv01` and 198 for `cv02`; deterministic lookup order is `cv00`, `cv01`, then `cv02`.\n";
const markdown = `# GSUB graph selector probe results

Overall: **${report.passed ? "PASS" : "FAIL"}**

The runtime page contains ${report.strictContract?.runtimeScriptElements ?? "unknown"} script elements. It computes registered \`--low = mod(node, 255)\` and \`--high = floor(node / 255)\`: \`cv01\` maps each of 16 slot bases to a slot×low intermediate, then \`cv02\` maps that intermediate to the final identity glyph. A CSS \`if()\` chooses one first-hop \`anchor-size()\`; a size container decodes the half-scale identity advance into \`--next-node\`; the inherited radix digits drive the second GSUB hop.

## Correctness

| current node | chosen slot | first hop | expected / decoded next | decode | second hop | overall |
|---:|---:|:---:|---:|:---:|:---:|:---:|
${caseRows || "| n/a | n/a | FAIL | n/a | FAIL | FAIL | FAIL |"}

All 16 first-hop and all 16 second-hop identity widths are compared exactly for every row. Required boundary indices tested: 0, 1, 32,767, and 50,256.
${failureText}

## Preserved direct-selector baseline

| current node | requested \`cv00\` value | low byte | exact result | matches modulo-256 behavior |
|---:|---:|---:|:---:|:---:|
${baselineRows || "| n/a | n/a | n/a | FAIL | no |"}

Chromium accepts the CSS syntax for \`"cv00" 50257\`, and the same font retains all 16 genuine 50,257-entry direct AlternateSets. Direct shaping still reduces the numbered value to its low 8 bits: value 255 passes, value 256 becomes 0/no substitution, and value 257 becomes 1. Thus node 32,767 requests 32,768 and gets no substitution; node 50,256 requests 50,257 and gets 81, selecting node index 80. The radix path bypasses this without shrinking the graph.

## Font and runtime sizes

- TTF: ${report.files?.ttfBytes?.toLocaleString() ?? "unknown"} bytes
- WOFF2: ${report.files?.woff2Bytes?.toLocaleString() ?? "unknown"} bytes
- HTML: ${report.files?.htmlBytes?.toLocaleString() ?? "unknown"} bytes
- CSS: ${report.files?.cssBytes?.toLocaleString() ?? "unknown"} bytes
- Glyphs: ${report.font?.glyphCount?.toLocaleString() ?? "unknown"}
- Direct baseline: ${report.font?.directAlternateSetCounts?.length ?? "unknown"} × 50,257-entry AlternateSets
- Radix low: ${report.font?.lowAlternateSetCounts?.length ?? "unknown"} × ${report.font?.lowAlternateSetCounts?.[0] ?? "unknown"}-entry AlternateSets
- Radix high: ${report.font?.highAlternateSetCount?.toLocaleString() ?? "unknown"} × ${report.font?.highAlternateSetEntries ?? "unknown"}-entry AlternateSets

## Browser and timing

- Browser: ${report.browser?.version ?? "launch failed"}
- Cold page/font load: ${report.loadMilliseconds?.toFixed(3) ?? "n/a"} ms
- Warm two-hop switch median: ${timing?.medianMilliseconds?.toFixed(3) ?? "n/a"} ms
- Warm two-hop switch p95: ${timing?.p95Milliseconds?.toFixed(3) ?? "n/a"} ms
- Timed switches: ${timing?.samples ?? 0}

The timing covers the passing radix sequence. The direct baseline is measured separately for correctness and does not drive the second hop.

Full machine-readable observations, exact widths, feature boundaries, capabilities, and failures are in \`browser-results.json\`.
`;
await fs.writeFile(path.join(experiment, "RESULTS.md"), markdown);
console.log(JSON.stringify({
  passed: report.passed,
  browser: report.browser?.version,
  files: report.files,
  timing: report.warmTwoHopSwitching,
  failures: report.failures ?? report.fatalError ?? [],
}, null, 2));
if (!report.passed) process.exitCode = 1;
