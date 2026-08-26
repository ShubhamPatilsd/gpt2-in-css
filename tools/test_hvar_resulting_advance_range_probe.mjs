#!/usr/bin/env node
/* Measure Chrome's per-glyph and run-level arithmetic for HVAR advances. */

import fs from "node:fs/promises";
import http from "node:http";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const output = new URL("../experiments/hvar-resulting-advance-range/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", output), "utf8"));
const toleranceDesignUnits = 1;

const mime = new Map([
  ["/index.html", "text/html; charset=utf-8"],
  ["/range-probe.woff2", "font/woff2"],
]);
const server = http.createServer(async (request, response) => {
  const pathname = new URL(request.url, "http://127.0.0.1").pathname;
  if (!mime.has(pathname)) {
    response.writeHead(404).end("not found");
    return;
  }
  try {
    response.writeHead(200, { "Content-Type": mime.get(pathname), "Cache-Control": "no-store" });
    response.end(await fs.readFile(new URL(pathname.slice(1), output)));
  } catch (error) {
    response.writeHead(500).end(String(error));
  }
});
await new Promise((resolve, reject) => {
  server.once("error", reject);
  server.listen(0, "127.0.0.1", resolve);
});
const { port } = server.address();

function classify(actual, hypotheses) {
  const errors = Object.fromEntries(Object.entries(hypotheses).map(
    ([name, expected]) => [name, Math.abs(actual - expected)],
  ));
  const minimum = Math.min(...Object.values(errors));
  return {
    actual,
    errors,
    matches: Object.entries(errors)
      .filter(([, error]) => error <= toleranceDesignUnits)
      .map(([name]) => name),
    nearest: Object.entries(errors)
      .filter(([, error]) => error === minimum)
      .map(([name]) => name),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  const browserMessages = [];
  page.on("console", (message) => browserMessages.push({ type: message.type(), text: message.text() }));
  await page.goto(`http://127.0.0.1:${port}/index.html`, { waitUntil: "load", timeout: 120_000 });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  const fontLoaded = await page.evaluate(() => document.fonts.check("64px RangeProbe", "\uE100"));
  if (!fontLoaded) throw new Error(`RangeProbe failed to load: ${JSON.stringify(browserMessages)}`);

  const raw = {};
  for (const axisValue of reference.axisValues) {
    raw[String(axisValue)] = await page.evaluate(async ({ axisTag, axisValue, scale }) => {
      const setting = `"${axisTag}" ${axisValue}`;
      document.querySelector("#html").style.fontVariationSettings = setting;
      document.querySelector("#svg").style.fontVariationSettings = setting;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      const toUnits = (pixels) => pixels / scale;
      const results = {};
      for (const row of document.querySelectorAll("[data-case]")) {
        const name = row.dataset.case;
        const html = {};
        for (const kind of ["target", "forward", "reverse"]) {
          const element = row.querySelector(`.${kind}`);
          const range = document.createRange();
          range.selectNodeContents(element);
          html[kind] = {
            intrinsicUnits: toUnits(element.getBoundingClientRect().width),
            rangeUnits: toUnits(range.getBoundingClientRect().width),
          };
        }
        const svgRow = document.querySelector(`[data-svg-case="${name}"]`);
        const svg = {};
        for (const kind of ["target", "forward", "reverse"]) {
          const element = svgRow.querySelector(`.${kind}`);
          svg[kind] = {
            lengthUnits: toUnits(element.getComputedTextLength()),
            startsUnits: Array.from({ length: element.textContent.length }, (_, index) =>
              toUnits(element.getStartPositionOfChar(index).x)),
          };
        }
        results[name] = { html, svg };
      }
      return results;
    }, { axisTag: reference.axisTag, axisValue, scale: reference.scale });
  }

  const cases = {};
  for (const record of reference.cases) {
    cases[record.name] = {};
    for (const axisValue of reference.axisValues) {
      const axisKey = String(axisValue);
      const observed = raw[axisKey][record.name];
      const predictions = record.predictions[axisKey];
      const targetMethods = {
        htmlIntrinsic: observed.html.target.intrinsicUnits,
        htmlRange: observed.html.target.rangeUnits,
        svgLength: observed.svg.target.lengthUnits,
      };
      const runMethods = {
        forwardHtmlIntrinsic: observed.html.forward.intrinsicUnits,
        reverseHtmlIntrinsic: observed.html.reverse.intrinsicUnits,
        forwardHtmlRange: observed.html.forward.rangeUnits,
        reverseHtmlRange: observed.html.reverse.rangeUnits,
        forwardSvgLength: observed.svg.forward.lengthUnits,
        reverseSvgLength: observed.svg.reverse.lengthUnits,
      };
      cases[record.name][axisKey] = {
        target: Object.fromEntries(Object.entries(targetMethods).map(
          ([method, actual]) => [method, classify(actual, predictions.target)])),
        run: Object.fromEntries(Object.entries(runMethods).map(
          ([method, actual]) => [method, classify(actual, predictions.run)])),
        svgStartsUnits: {
          forward: observed.svg.forward.startsUnits,
          reverse: observed.svg.reverse.startsUnits,
        },
      };
    }
  }

  const runMethods = [
    "forwardHtmlIntrinsic", "reverseHtmlIntrinsic", "forwardHtmlRange",
    "reverseHtmlRange", "forwardSvgLength", "reverseSvgLength",
  ];
  const allMethodsMatch = (caseName, axis, hypothesis) => runMethods.every((method) =>
    cases[caseName][String(axis)].run[method].matches.includes(hypothesis));
  const targetMethods = ["htmlIntrinsic", "htmlRange", "svgLength"];
  const allTargetMethodsMatch = (caseName, axis, hypothesis) => targetMethods.every((method) =>
    cases[caseName][String(axis)].target[method].matches.includes(hypothesis));
  const inRangeControlsPass = reference.axisValues.every((axis) =>
    ["control-low", "control-high", "control-zero"].every((name) =>
      allMethodsMatch(name, axis, "unclamped")));
  const negativePerGlyphClamp = ["negative-mild", "negative-large"].every((name) =>
    allMethodsMatch(name, 1, "perGlyphClamp0To65535"));
  const negativeResultsAdditive = ["negative-mild", "negative-large"].every((name) =>
    allMethodsMatch(name, 1, "unclamped"));
  const isolatedNegativeBoxesCollapse = ["negative-mild", "negative-large"].every((name) =>
    allTargetMethodsMatch(name, 1, "clamp0To65535"));
  const highResultsUnclamped = ["above-mild", "above-large"].every((name) =>
    allMethodsMatch(name, 1, "unclamped"));
  const minAndDefaultUnclamped = [-1, 0].every((axis) =>
    reference.cases.every(({ name }) => allMethodsMatch(name, axis, "unclamped")));
  const orderIndependent = reference.axisValues.every((axis) => reference.cases.every(({ name }) => {
    const run = cases[name][String(axis)].run;
    return [
      ["forwardHtmlIntrinsic", "reverseHtmlIntrinsic"],
      ["forwardHtmlRange", "reverseHtmlRange"],
      ["forwardSvgLength", "reverseSvgLength"],
    ].every(([forward, reverse]) => Math.abs(run[forward].actual - run[reverse].actual)
      <= toleranceDesignUnits);
  }));
  const verdict = negativePerGlyphClamp
    ? "reject-negative-resulting-advances"
    : negativeResultsAdditive && highResultsUnclamped && inRangeControlsPass
        && minAndDefaultUnclamped && orderIndependent
      ? "signed-results-survive-additively"
      : "other-or-inconclusive";
  const report = {
    chrome: await browser.version(),
    generatedAt: new Date().toISOString(),
    toleranceDesignUnits,
    fontLoaded,
    browserMessages,
    fontValidation: reference.fontValidation,
    checks: {
      inRangeControlsPass,
      negativePerGlyphClamp,
      negativeResultsAdditive,
      isolatedNegativeBoxesCollapse,
      highResultsUnclamped,
      minAndDefaultUnclamped,
      orderIndependent,
    },
    verdict,
    cases,
    raw,
  };
  await fs.writeFile(new URL("browser-results.json", output), `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify({ chrome: report.chrome, checks: report.checks, verdict }, null, 2));
  if (!inRangeControlsPass || !minAndDefaultUnclamped || !orderIndependent) process.exitCode = 1;
} finally {
  await browser.close();
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
}
