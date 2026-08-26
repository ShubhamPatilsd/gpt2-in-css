import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const experiment = new URL("../experiments/opsz-container-handoff/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", experiment), "utf8"));
const base = "http://127.0.0.1:4178/experiments/opsz-container-handoff";
const rounds = Number(process.env.OPSZ_HANDOFF_ROUNDS ?? 9);
const warmups = 8;

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const results = { correctness: [], scaling: {}, fourAxis: {} };
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 500 } });
  await page.goto(`${base}/index.html`, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  for (let caseIndex = 0; caseIndex < reference.cases.length; caseIndex += 1) {
    await page.evaluate((index) => {
      document.querySelector(`#case-${index}`).checked = true;
    }, caseIndex);
    const rows = await page.locator("section[data-mode]").evaluateAll((sections) => sections.map((section) => {
      const source = section.querySelector(".source");
      const bridge = section.querySelector(".bridge");
      const sink = section.querySelector(".sink");
      const sinkStyle = getComputedStyle(sink);
      return {
        mode: section.dataset.mode,
        sourceWidth: source.getBoundingClientRect().width,
        bridgeWidth: bridge.getBoundingClientRect().width,
        sinkWidth: sink.getBoundingClientRect().width,
        sinkFontSize: Number.parseFloat(sinkStyle.fontSize),
        fontVariationSettings: sinkStyle.fontVariationSettings,
        fontOpticalSizing: sinkStyle.fontOpticalSizing,
      };
    }));
    results.correctness.push({ input: reference.cases[caseIndex].input, rows });
  }
  results.normalFlowAnchor = await page.locator("#flow-probe").evaluate((section) => ({
    sourceWidth: section.querySelector(".flow-source").getBoundingClientRect().width,
    bridgeWidth: section.querySelector(".flow-bridge").getBoundingClientRect().width,
    valueWidth: section.querySelector(".flow-value").getBoundingClientRect().width,
  }));

  for (const size of reference.sizes) {
    results.scaling[size] = {};
    for (const mode of reference.modes) {
      await page.goto(`${base}/n${size}-${mode}.html`, { waitUntil: "load" });
      await page.evaluate(() => document.fonts.ready);
      const samples = await page.evaluate(({ rounds: count, warmups: warmupCount }) => {
        const radios = [...document.querySelectorAll('input[name="case"]')];
        const sinks = [...document.querySelectorAll(".sink")];
        const values = [];
        let checksum = 0;
        for (let round = 0; round < count + warmupCount; round += 1) {
          const started = performance.now();
          radios[round % radios.length].checked = true;
          for (const sink of sinks) checksum += sink.getBoundingClientRect().width;
          const elapsed = performance.now() - started;
          if (round >= warmupCount) values.push(elapsed);
        }
        return { values, checksum, elements: document.querySelectorAll("*").length };
      }, { rounds, warmups });
      results.scaling[size][mode] = {
        medianMilliseconds: median(samples.values),
        samplesMilliseconds: samples.values,
        checksum: samples.checksum,
        elements: samples.elements,
      };
    }

    const groups = size / 4;
    await page.goto(`${base}/four-axis-n${groups}.html`, { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
    const fourCorrectness = [];
    for (let caseIndex = 0; caseIndex < reference.fourAxisCases.length; caseIndex += 1) {
      const measured = await page.evaluate((index) => {
        document.querySelector(`#four-case-${index}`).checked = true;
        const sink = document.querySelector(".four-sink");
        const style = getComputedStyle(sink);
        return {
          width: sink.getBoundingClientRect().width,
          fontSize: Number.parseFloat(style.fontSize),
          fontWeight: style.fontWeight,
          fontStretch: style.fontStretch,
          fontStyle: style.fontStyle,
          fontOpticalSizing: style.fontOpticalSizing,
          fontVariationSettings: style.fontVariationSettings,
        };
      }, caseIndex);
      fourCorrectness.push(measured);
    }
    const fourSamples = await page.evaluate(({ rounds: count, warmups: warmupCount }) => {
      const radios = [...document.querySelectorAll('input[name="four-case"]')];
      const sinks = [...document.querySelectorAll(".four-sink")];
      const values = [];
      let checksum = 0;
      for (let round = 0; round < count + warmupCount; round += 1) {
        const started = performance.now();
        radios[round % radios.length].checked = true;
        for (const sink of sinks) checksum += sink.getBoundingClientRect().width;
        const elapsed = performance.now() - started;
        if (round >= warmupCount) values.push(elapsed);
      }
      return { values, checksum, elements: document.querySelectorAll("*").length };
    }, { rounds, warmups });
    results.fourAxis[size] = {
      groups,
      correctness: fourCorrectness,
      medianMilliseconds: median(fourSamples.values),
      samplesMilliseconds: fourSamples.values,
      checksum: fourSamples.checksum,
      elements: fourSamples.elements,
    };
  }
} finally {
  await browser.close();
}

for (const size of reference.sizes) {
  for (let caseIndex = 0; caseIndex < reference.fourAxisCases.length; caseIndex += 1) {
    const expected = reference.fourAxisCases[caseIndex];
    const actual = results.fourAxis[size].correctness[caseIndex];
    if (Math.abs(actual.width - expected.sinkWidth) > 0.15
        || Math.abs(actual.fontSize - expected.fontSize) > 0.08) {
      throw new Error(`four-axis handoff mismatch: ${JSON.stringify({ size, expected, actual })}`);
    }
  }
}

for (let caseIndex = 0; caseIndex < reference.cases.length; caseIndex += 1) {
  const expectedCase = reference.cases[caseIndex];
  for (const row of results.correctness[caseIndex].rows) {
    const expected = expectedCase.modes[row.mode];
    if (Math.abs(row.sourceWidth - expectedCase.sourceWidth) > 0.08
        || Math.abs(row.bridgeWidth - expectedCase.sourceWidth) > 0.08
        || Math.abs(row.sinkFontSize - expectedCase.sourceWidth) > 0.08
        || Math.abs(row.sinkWidth - expected.consumerWidth) > 0.12) {
      throw new Error(`handoff mismatch: ${JSON.stringify({ expectedCase, row })}`);
    }
  }
}
if (results.normalFlowAnchor.bridgeWidth !== 0 || results.normalFlowAnchor.valueWidth !== 0) {
  throw new Error(`normal-flow anchor-size unexpectedly resolved: ${JSON.stringify(results.normalFlowAnchor)}`);
}

for (const filename of ["index.html", ...reference.sizes.flatMap((size) => [
  `n${size}-none.html`,
  `n${size}-auto.html`,
  `n${size}-explicit.html`,
  `four-axis-n${size / 4}.html`,
])]) {
  const html = await fs.readFile(new URL(filename, experiment), "utf8");
  if (html.toLowerCase().includes("<script")) {
    throw new Error(`runtime fixture contains JavaScript: ${filename}`);
  }
}

await fs.writeFile(new URL("browser-results.json", experiment), `${JSON.stringify(results, null, 2)}\n`);
console.log(JSON.stringify(results, null, 2));
