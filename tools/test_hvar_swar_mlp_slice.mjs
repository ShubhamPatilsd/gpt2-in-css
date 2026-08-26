import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const referenceUrl = new URL("../experiments/hvar-swar-mlp-slice/reference.json", import.meta.url);
const reference = JSON.parse(await fs.readFile(referenceUrl, "utf8"));
const rounds = Number(process.env.HVAR_SWAR_ROUNDS ?? 7);
const variant = process.env.HVAR_SWAR_VARIANT ?? "baseline";
if (!new Set(["baseline", "fused", "fused-fast"]).has(variant)) {
  throw new Error("HVAR_SWAR_VARIANT must be baseline, fused, or fused-fast");
}
const expectedTransport = variant === "fused-fast" ?
  reference.expectedFastTransport : reference.expectedTransport;
const expectedHiddenCodes = variant === "fused-fast" ?
  reference.fastHiddenCodes : reference.hiddenCodes;

function summarize(actual, expected) {
  const differences = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(differences.reduce((sum, value) => sum + value * value, 0) / differences.length),
    maxError: Math.max(...differences.map(Math.abs)),
    finite: actual.filter(Number.isFinite).length,
  };
}

function median(values) {
  const sorted = values.toSorted((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

async function readResults(page) {
  const widths = await page.locator(".result").evaluateAll((elements) =>
    elements.map((element) => element.getBoundingClientRect().width));
  return widths.map((width) =>
    (width - reference.geometryBase) / reference.geometryScale);
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
let report;
try {
  const page = await browser.newPage({ viewport: { width: 64, height: 64 } });
  const started = performance.now();
  const pageName = variant === "baseline" ? "index.html" : `${variant}.html`;
  await page.goto(`http://127.0.0.1:4178/experiments/hvar-swar-mlp-slice/${pageName}`, {
    waitUntil: "load",
    timeout: 180000,
  });
  await page.evaluate(() => document.fonts.ready);
  const initial = await readResults(page);
  const diagnostics = await page.evaluate((expected) => ({
    sources: Array.from(document.querySelectorAll(".source")).slice(0, 4).map((element) => ({
      width: element.getBoundingClientRect().width,
      fontVariationSettings: getComputedStyle(element).fontVariationSettings,
    })),
    packets: Array.from(document.querySelectorAll(".packet")).slice(0, 4).map((element) => {
      const style = getComputedStyle(element);
      return {
        width: element.getBoundingClientRect().width,
        z0: style.getPropertyValue("--z0"),
        h0: style.getPropertyValue("--h0"),
        c0: style.getPropertyValue("--c0"),
        z1: style.getPropertyValue("--z1"),
        h1: style.getPropertyValue("--h1"),
        c1: style.getPropertyValue("--c1"),
      };
    }),
    expectedPacketWidths: expected.packetWidths,
    expectedHiddenCodes: expected.hiddenCodes,
    expectedPre: expected.pre,
    expectedBrowserPre: expected.browserPre,
  }), {
    packetWidths: Array.from({ length: 4 }, (_, index) =>
      expectedHiddenCodes[0][2 * index] + reference.radix * expectedHiddenCodes[0][2 * index + 1]),
    hiddenCodes: expectedHiddenCodes[0].slice(0, 8),
    pre: reference.pre[0].slice(0, 8),
    browserPre: reference.browserPre[0].slice(0, 8),
  });
  const loadAndInitialMilliseconds = performance.now() - started;
  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    const caseIndex = round % 2 === 0 ? 1 : 0;
    const mutationStarted = performance.now();
    await page.locator("#scope").evaluate((element, settings) => {
      element.style.setProperty("--fc-settings", settings);
    }, reference.settings[caseIndex]);
    const actual = await readResults(page);
    samples.push({
      round,
      caseIndex,
      milliseconds: performance.now() - mutationStarted,
      browserVsTransport: summarize(actual, expectedTransport[caseIndex]),
      browserVsFloat: summarize(actual, reference.expectedFloat[caseIndex]),
    });
  }
  report = {
    chrome: await browser.version(),
    variant,
    loadAndInitialMilliseconds,
    diagnostics,
    initial: {
      browserVsTransport: summarize(initial, expectedTransport[0]),
      browserVsFloat: summarize(initial, reference.expectedFloat[0]),
    },
    warmMutationMedianMilliseconds: median(samples.slice(1).map((sample) => sample.milliseconds)),
    warmMutationMaximumMilliseconds: Math.max(...samples.slice(1).map((sample) => sample.milliseconds)),
    elements: await page.locator("*").count(),
    cssBytes: variant === "baseline" ? reference.cssBytes :
      reference[variant === "fused" ? "fusedCssBytes" : "fusedFastCssBytes"],
    htmlBytes: variant === "baseline" ? reference.htmlBytes :
      reference[variant === "fused" ? "fusedHtmlBytes" : "fusedFastHtmlBytes"],
    fontBytes: reference.fontBytes,
    samples,
  };
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL(`../experiments/hvar-swar-mlp-slice/browser-results-${variant}.json`, import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
