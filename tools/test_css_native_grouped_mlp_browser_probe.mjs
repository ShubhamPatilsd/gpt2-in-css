import fs from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
let chromium;
try {
  ({ chromium } = require("playwright"));
} catch {
  ({ chromium } = require(`${dependencyRoot}/playwright`));
}

const chromePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.CSS_MLP_ROUNDS ?? "16", 10);
if (!Number.isInteger(rounds) || rounds < 4) {
  throw new Error("CSS_MLP_ROUNDS must be an integer of at least 4");
}

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const directory = path.join(root, "experiments", "css-native-grouped-mlp-browser");
const htmlPath = path.join(directory, "index.html");
const html = await fs.readFile(htmlPath, "utf8");
if (/<script(?:\s|>)/i.test(html)) throw new Error("runtime HTML contains JavaScript");
const reference = JSON.parse(await fs.readFile(path.join(directory, "reference.json"), "utf8"));
const vectorCount = reference.architecture.vectors;
if (vectorCount < 4) throw new Error("timing requires at least four distinct vectors");

function percentile(values, fraction) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.max(0, Math.ceil(sorted.length * fraction) - 1)];
}

function formatMilliseconds(value) {
  return `${value.toFixed(2)} ms`;
}

const browser = await chromium.launch({ executablePath: chromePath, headless: true });
let report;
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 1000, height: 160 },
  });
  const page = await context.newPage();
  const coldStarted = performance.now();
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
  await page.evaluate(async () => {
    await document.fonts.ready;
    let checksum = 0;
    for (const element of document.querySelectorAll(".output")) {
      checksum += element.getBoundingClientRect().width;
    }
    return checksum;
  });
  const coldLoadMilliseconds = performance.now() - coldStarted;

  // Full-bank numeric reads are intentionally outside the timed region. Two
  // distinct vectors exercise both fresh style mutations and all 768 outputs.
  const numericCases = [];
  for (const caseIndex of [0, 1]) {
    const widths = await page.evaluate((selected) => {
      document.querySelector(`#vector-${selected}`).checked = true;
      return [...document.querySelectorAll(".output")].map(
        (element) => element.getBoundingClientRect().width,
      );
    }, caseIndex);
    const expected = reference.representedWidths[caseIndex];
    const errors = widths.map((value, output) => Math.abs(value - expected[output]));
    numericCases.push({
      vector: caseIndex,
      maximumAbsoluteError: Math.max(...errors),
      meanAbsoluteError: errors.reduce((sum, value) => sum + value, 0) / errors.length,
    });
  }

  // Warm every vector/font path before sampling. The timed evaluate returns a
  // scalar checksum only: layout visits the complete output bank without
  // serializing 768 widths across the protocol boundary.
  for (let warmup = 0; warmup < vectorCount * 2; warmup += 1) {
    await page.evaluate((selected) => {
      document.querySelector(`#vector-${selected}`).checked = true;
      let checksum = 0;
      for (const element of document.querySelectorAll(".output")) {
        checksum += element.getBoundingClientRect().width;
      }
      return checksum;
    }, warmup % vectorCount);
  }

  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    const vector = (round + 1) % vectorCount;
    const sample = await page.evaluate((selected) => {
      const started = performance.now();
      document.querySelector(`#vector-${selected}`).checked = true;
      let checksum = 0;
      for (const element of document.querySelectorAll(".output")) {
        checksum += element.getBoundingClientRect().width;
      }
      return { milliseconds: performance.now() - started, checksum };
    }, vector);
    samples.push({ round, vector, ...sample });
  }

  const tolerance = reference.numericToleranceFontUnits;
  const maximumAbsoluteError = Math.max(
    ...numericCases.map((item) => item.maximumAbsoluteError),
  );
  const numericPass = numericCases.length >= 2 && maximumAbsoluteError <= tolerance;
  const timings = samples.map((sample) => sample.milliseconds);
  const warmMedianMilliseconds = percentile(timings, 0.5);
  const warmP90Milliseconds = percentile(timings, 0.9);
  const warmMaximumMilliseconds = Math.max(...timings);
  const thresholdMilliseconds = 80;
  const warmMedianPass = warmMedianMilliseconds <= thresholdMilliseconds;
  const elements = await page.locator("*").count();

  report = {
    generatedAt: new Date().toISOString(),
    chromeVersion: await browser.version(),
    runtimeContainsJavaScript: false,
    architecture: reference.architecture,
    coldLoadMilliseconds,
    warmMutation: {
      rounds,
      distinctVectors: vectorCount,
      medianMilliseconds: warmMedianMilliseconds,
      p90Milliseconds: warmP90Milliseconds,
      maximumMilliseconds: warmMaximumMilliseconds,
      samples,
      timedReturnValue: "one scalar checksum; no output-width array",
    },
    numeric: {
      checkedVectors: numericCases.length,
      checkedOutputsPerVector: reference.architecture.outputs,
      toleranceFontUnits: tolerance,
      toleranceRationale: `The reference models F2DOT14 avar2 coefficients and integer HVAR knot deltas. The ${reference.architecture.glyphsPerOutput}-face bound allows 0.5 font unit of final advance rounding per face plus one 1/64 px layout quantization.`,
      maximumAbsoluteError,
      cases: numericCases,
      pass: numericPass,
    },
    footprint: {
      fontBytes: reference.fontBytes,
      htmlBytes: reference.htmlBytes,
      elements,
      glyphsPerOutput: reference.architecture.glyphsPerOutput,
      geometryOutputs: reference.architecture.geometryOutputs,
      preactivationTransportBoxes: reference.architecture.preactivationTransportBoxes,
    },
    gate: {
      warmMedianThresholdMilliseconds: thresholdMilliseconds,
      warmMedianPass,
      numericPass,
      retainForStudentIntegration: warmMedianPass && numericPass,
    },
    comparisonContext: {
      savedExactFullMlpWarmProfileMilliseconds: 251,
      note: "Context only: 251 ms is a saved exact full-MLP profile, not a paired benchmark from this run.",
    },
  };

  await fs.writeFile(
    path.join(directory, "browser-results.json"),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  const gateLabel = report.gate.retainForStudentIntegration ? "RETAIN" : "DO NOT RETAIN";
  const resultsMarkdown = `# CSS-native grouped MLP browser probe

## Result

**${gateLabel} for student integration.** The gate requires numeric correctness and a warm mutation median at or below 80 ms.

| Metric | Result |
| --- | ---: |
| Numeric checks | ${numericPass ? "pass" : "fail"} |
| Maximum absolute error | ${maximumAbsoluteError.toFixed(4)} font units |
| Cold load | ${formatMilliseconds(coldLoadMilliseconds)} |
| Warm median | ${formatMilliseconds(warmMedianMilliseconds)} |
| Warm p90 | ${formatMilliseconds(warmP90Milliseconds)} |
| Warm maximum | ${formatMilliseconds(warmMaximumMilliseconds)} |
| Runtime font bytes | ${reference.fontBytes.toLocaleString("en-US")} |
| DOM elements | ${elements.toLocaleString("en-US")} |
| Glyphs per output | ${reference.architecture.glyphsPerOutput} |
| Geometry outputs | ${reference.architecture.geometryOutputs} |
| Preactivation/transport boxes | ${reference.architecture.preactivationTransportBoxes} |
| Chrome | ${report.chromeVersion} |

Configuration: ${reference.architecture.groups} groups × ${reference.architecture.axesPerGroup} selected axes from one ${reference.architecture.globalInputDimensions}-dimension inherited input list, ${reference.architecture.outputs} outputs, ${rounds} timed rounds. Two complete output banks were checked against a reference that includes avar2 F2DOT14 and HVAR integer-delta quantization. The timed region forces every output width but returns only one checksum.

For context, an earlier saved exact full-MLP profile was 251 ms. This is not a paired benchmark: it was not collected in this run under matched conditions.
`;
  await fs.writeFile(path.join(directory, "RESULTS.md"), resultsMarkdown);
  console.log(JSON.stringify(report, null, 2));
  if (!report.gate.retainForStudentIntegration) process.exitCode = 1;
  await context.close();
} finally {
  await browser.close();
}
