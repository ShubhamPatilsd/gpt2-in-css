import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const directoryUrl = process.env.SVG_CHAIN_URL ??
  "http://127.0.0.1:4178/experiments/svg-filter-full-block";
const transport = process.env.SVG_TRANSPORT ?? "chain";
const timingRuns = Number(process.env.SVG_TIMING_RUNS ?? 6);
const mutationRuns = Number(process.env.SVG_MUTATION_RUNS ?? 20);
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/svg-filter-full-block/reference.json", import.meta.url,
), "utf8"));

async function rowsFromPng(png) {
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: info.width * info.height }, (_, index) => {
    const offset = index * info.channels;
    return [data[offset], data[offset + 1]];
  });
}

async function pixelRows(locator) {
  return rowsFromPng(await locator.screenshot({ animations: "disabled" }));
}

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  const largest = expected.reduce(
    (best, value, index, values) => Math.abs(value) > Math.abs(values[best]) ? index : best, 0,
  );
  return {
    maxError: Math.max(...errors.map(Math.abs)),
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    actualRange: [Math.min(...actual), Math.max(...actual)],
    levels: new Set(actual.map((value) => value.toFixed(8))).size,
    largestExpected: { index: largest, expected: expected[largest], actual: actual[largest] },
  };
}

const boundaryEncodings = transport === "nested"
  ? ["signed", "centered", "signed", "signed", "centered"]
  : ["centered", "centered", "centered", "centered", "centered"];
const stages = [
  [`${transport}-1.html`, "n1", "n1_range", boundaryEncodings[0]],
  [`${transport}-2.html`, "residual", "residual_range", boundaryEncodings[1]],
  [`${transport}-3.html`, "n2", "n2_range", boundaryEncodings[2]],
  [`${transport}-4.html`, "hidden", "hidden_range", boundaryEncodings[3]],
  [`${transport}.html`, "expected", "output_range", boundaryEncodings[4]],
];

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 3072, height: 900 } });
  const accuracy = {};
  const actualVectors = {};
  for (const [file, key, rangeKey, encoding] of stages) {
    await page.goto(`${directoryUrl}/${file}?accuracy=${Date.now()}`, { waitUntil: "load" });
    const rows = await pixelRows(page.locator("svg"));
    const range = reference[rangeKey];
    const actual = encoding === "signed"
      ? rows.map(([red, green]) => (red - green) * range / 255)
      : rows.map(([red]) => (red / 255 - reference.surface_center) * 2 * range);
    accuracy[file] = summarize(actual, reference[key]);
    actualVectors[key] = actual;
  }
  await fs.writeFile("/tmp/svg-filter-chain-actual.json", JSON.stringify(actualVectors));
  const attentionDebug = {};
  if (transport === "chain" && process.env.SVG_DEBUG_ATTENTION === "1") {
  await page.goto(`${directoryUrl}/chain-2.html?debug=source-${Date.now()}`, { waitUntil: "load" });
  await page.locator("svg").evaluate((svg) => {
    svg.setAttribute("width", "768");
    svg.setAttribute("height", "1");
    svg.setAttribute("viewBox", "0 0 768 1");
  });
  await page.locator("#chain-attention").evaluate((filter) => {
    const primitive = document.createElementNS("http://www.w3.org/2000/svg", "feOffset");
    primitive.setAttribute("in", "SourceGraphic");
    primitive.setAttribute("x", "0");
    primitive.setAttribute("y", "0");
    primitive.setAttribute("width", "768");
    primitive.setAttribute("height", "1");
    filter.append(primitive);
  });
  const sourceRows = await pixelRows(page.locator("svg"));
  const sourceActual = sourceRows.map(([red]) =>
    (red / 255 - reference.surface_center) * 2 * reference.n1_range
  );
  attentionDebug.SourceGraphic = summarize(sourceActual, reference.n1);
  for (const input of [
    "attention-total2",
    "attention-bias",
    "attention-row-scaled",
    "attention-row-signed",
    "attention-scales",
    "attention-common-signed",
    "attention-common",
  ]) {
    await page.goto(`${directoryUrl}/chain-2.html?debug=${input}-${Date.now()}`, { waitUntil: "load" });
    await page.locator("#chain-attention").evaluate((filter, name) => {
      const primitive = document.createElementNS("http://www.w3.org/2000/svg", "feOffset");
      primitive.setAttribute("in", name);
      primitive.setAttribute("dx", "-255");
      primitive.setAttribute("x", "0");
      primitive.setAttribute("y", "0");
      primitive.setAttribute("width", "1");
      primitive.setAttribute("height", "768");
      filter.append(primitive);
    }, input);
    const rows = await pixelRows(page.locator("svg"));
    const largest = reference.residual.reduce(
      (best, value, index, values) => Math.abs(value) > Math.abs(values[best]) ? index : best, 0,
    );
    attentionDebug[input] = {
      red: [Math.min(...rows.map((row) => row[0])), Math.max(...rows.map((row) => row[0]))],
      green: [Math.min(...rows.map((row) => row[1])), Math.max(...rows.map((row) => row[1]))],
      atLargestExpected: rows[largest],
    };
  }
  }
  const timings = [];
  for (let index = 0; index < timingRuns; index += 1) {
    const run = await browser.newPage({ viewport: { width: 512, height: 900 } });
    const start = performance.now();
    await run.goto(`${directoryUrl}/${transport}.html?run=${index}-${Date.now()}`, { waitUntil: "load" });
    await run.locator("svg").screenshot({ animations: "disabled" });
    timings.push(performance.now() - start);
    await run.close();
  }
  const warm = timings.slice(1).sort((a, b) => a - b);
  const stageTimings = {};
  if (process.env.SVG_PROFILE_STAGES === "1") {
    for (const [file] of stages) {
      const samples = [];
      for (let index = 0; index < 4; index += 1) {
        const run = await browser.newPage({ viewport: { width: 3072, height: 900 } });
        const start = performance.now();
        await run.goto(`${directoryUrl}/${file}?profile=${index}-${Date.now()}`, { waitUntil: "load" });
        await run.locator("svg").screenshot({ animations: "disabled" });
        samples.push(performance.now() - start);
        await run.close();
      }
      const sorted = samples.slice(1).sort((a, b) => a - b);
      stageTimings[file] = {
        samples,
        warmMedianMilliseconds: sorted[Math.floor(sorted.length / 2)],
      };
    }
  }
  const mutationTimings = [];
  const mutationChecksums = [];
  const mutationPngs = {};
  if (transport === "chain") {
    const run = await browser.newPage({ viewport: { width: 512, height: 900 } });
    await run.goto(`${directoryUrl}/chain.html?mutation=${Date.now()}`, { waitUntil: "load" });
    await run.locator("svg").screenshot({ animations: "disabled" });
    for (let index = 0; index < mutationRuns; index += 1) {
      const start = performance.now();
      const href = index % 2 ? "x.png" : "x-alt.png";
      await run.locator("#chain-ln1 feImage").first().evaluate(
        (element, href) => element.setAttribute("href", href),
        href,
      );
      const png = await run.locator("svg").screenshot({ animations: "disabled" });
      mutationTimings.push(performance.now() - start);
      mutationChecksums.push(png.reduce((sum, value) => (sum + value) >>> 0, 0));
      mutationPngs[href] = png;
    }
    await run.close();
  }
  const sortedMutations = mutationTimings.slice(1).sort((a, b) => a - b);
  const mutationAccuracy = {};
  for (const [href, expectedKey] of [["x.png", "expected"], ["x-alt.png", "expected_alt"]]) {
    if (!mutationPngs[href]) continue;
    const rows = await rowsFromPng(mutationPngs[href]);
    const actual = rows.map(([red]) =>
      (red / 255 - reference.surface_center) * 2 * reference.output_range
    );
    mutationAccuracy[href] = summarize(actual, reference[expectedKey]);
  }
  const result = {
    accuracy,
    attentionDebug,
    timings,
    warmMedianMilliseconds: warm.length ? warm[Math.floor(warm.length / 2)] : timings[0],
    stageTimings,
    mutationTimings,
    mutationChecksums,
    mutationAccuracy,
    mutationWarmMedianMilliseconds: sortedMutations.length
      ? sortedMutations[Math.floor(sortedMutations.length / 2)]
      : null,
  };
  console.log(JSON.stringify(result, null, 2));
  if (transport === "chain") {
    const finalAccuracy = accuracy["chain.html"];
    if (finalAccuracy.maxError > 10 || finalAccuracy.rmse > 1) {
      throw new Error(`full-block accuracy regression: ${JSON.stringify(finalAccuracy)}`);
    }
    const alternateAccuracy = mutationAccuracy["x-alt.png"];
    if (alternateAccuracy.maxError > 10 || alternateAccuracy.rmse > 1) {
      throw new Error(
        `live-residual alternate-input regression: ${JSON.stringify(alternateAccuracy)}`,
      );
    }
    if (result.mutationWarmMedianMilliseconds > 172) {
      throw new Error(
        `13x performance gate missed: ${result.mutationWarmMedianMilliseconds.toFixed(2)} ms`,
      );
    }
    if (new Set(mutationChecksums).size !== 2) {
      throw new Error("alternating inputs did not produce two alternating outputs");
    }
  }
} finally {
  await browser.close();
}
