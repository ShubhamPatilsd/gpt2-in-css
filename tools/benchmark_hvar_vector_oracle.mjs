import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const origin = process.env.HVAR_ORIGIN ?? "http://127.0.0.1:4178";
const rounds = Number(process.env.HVAR_ORACLE_ROUNDS ?? 5);
const oracleRoot = new URL("../experiments/hvar-vector-oracle/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", oracleRoot), "utf8"));

const variants = [
  {
    name: "baseline-two-live-blocks",
    directory: "avar2-gelu-linear-hvar-full-mlp-g13",
    pageFile: "connected-two-block-serial-projection-layoutless.html",
    realStages: ["block0", "block0-state-transport", "block1-attention", "block1-fc", "block1-preactivation-transport", "block1-projection"],
  },
  {
    name: "oracle-block0-handoff",
    directory: "hvar-vector-oracle",
    pageFile: "oracle-block0-handoff.html",
    realStages: ["block1-attention", "block1-fc", "block1-preactivation-transport", "block1-projection"],
  },
  {
    name: "oracle-b1-fc-preactivation",
    directory: "hvar-vector-oracle",
    pageFile: "oracle-b1-fc-preactivation.html",
    realStages: ["block0", "block0-state-transport", "block1-attention", "block1-projection"],
  },
  {
    name: "oracle-block0-and-b1-fc",
    directory: "hvar-vector-oracle",
    pageFile: "oracle-block0-and-b1-fc.html",
    realStages: ["block1-attention", "block1-projection"],
  },
  {
    name: "oracle-b1-projection-only",
    directory: "hvar-vector-oracle",
    pageFile: "oracle-b1-projection-only.html",
    realStages: ["block1-projection"],
  },
];

function percentile(values, fraction) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor((sorted.length - 1) * fraction)];
}

async function preparePage(context, variant) {
  const page = await context.newPage();
  await page.goto(
    `${origin}/experiments/${variant.directory}/${variant.pageFile}`,
    { waitUntil: "load", timeout: 120000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const initial = await page.evaluate(() => {
    function deepElements(selector) {
      const found = [];
      const visit = (root) => {
        found.push(...root.querySelectorAll(selector));
        for (const element of root.querySelectorAll("*")) {
          if (element.shadowRoot) visit(element.shadowRoot);
        }
      };
      visit(document);
      return found;
    }
    const outputs = deepElements(".serial-output");
    outputs.at(-1).getBoundingClientRect();
    return { elements: deepElements("*").length, outputs: outputs.length };
  });
  return { page, initial };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 1000, height: 120 },
  });

  // Warm shared HTTP/font resources once for every topology; not measured.
  for (const variant of variants) {
    const { page } = await preparePage(context, variant);
    await page.close();
    variant.samples = [];
  }

  for (let round = 0; round < rounds; round += 1) {
    const mode = 1 + (round % (reference.tokenIds.length - 1));
    const order = variants.map((_, offset) => variants[(round + offset) % variants.length]);
    for (const variant of order) {
      const { page, initial } = await preparePage(context, variant);
      const sample = await page.evaluate(({ caseIndex, expectedWidths }) => {
        function deepElements(selector) {
          const found = [];
          const visit = (root) => {
            found.push(...root.querySelectorAll(selector));
            for (const element of root.querySelectorAll("*")) {
              if (element.shadowRoot) visit(element.shadowRoot);
            }
          };
          visit(document);
          return found;
        }
        const started = performance.now();
        document.querySelector(`#case-${caseIndex}`).checked = true;
        const outputs = deepElements(".serial-output");
        const terminalWidth = outputs.at(-1).getBoundingClientRect().width;
        return {
          milliseconds: performance.now() - started,
          terminalWidth,
          terminalWidthError: Math.abs(terminalWidth - expectedWidths.at(-1)),
        };
      }, { caseIndex: mode, expectedWidths: reference.expectedOutputWidths[mode] });
      variant.samples.push({ round, mode, ...initial, ...sample });
      await page.close();
    }
    console.error(`fresh mutation round ${round + 1}/${rounds}`);
  }

  // Validate all coordinates and cases outside the timed samples.
  for (const variant of variants) {
    const { page, initial } = await preparePage(context, variant);
    variant.elements = initial.elements;
    variant.validation = [];
    for (let mode = 0; mode < reference.tokenIds.length; mode += 1) {
      const widths = await page.evaluate((caseIndex) => {
        function deepElements(selector) {
          const found = [];
          const visit = (root) => {
            found.push(...root.querySelectorAll(selector));
            for (const element of root.querySelectorAll("*")) {
              if (element.shadowRoot) visit(element.shadowRoot);
            }
          };
          visit(document);
          return found;
        }
        document.querySelector(`#case-${caseIndex}`).checked = true;
        return deepElements(".serial-output")
          .map((element) => element.getBoundingClientRect().width);
      }, mode);
      const expected = reference.expectedOutputWidths[mode];
      const errors = widths.map((width, index) => Math.abs(width - expected[index]));
      variant.validation.push({
        mode,
        outputs: widths.length,
        maximumWidthError: Math.max(...errors),
        outputRmse: Math.sqrt(errors.reduce((sum, error) => sum + error ** 2, 0) /
          errors.length) / reference.block1OutputScale,
      });
    }
    await page.close();
  }

  const summaries = variants.map((variant) => {
    const times = variant.samples.map(({ milliseconds }) => milliseconds);
    return {
      name: variant.name,
      pageFile: variant.pageFile,
      realStages: variant.realStages,
      elements: variant.elements,
      minimumMilliseconds: Math.min(...times),
      medianMilliseconds: percentile(times, 0.5),
      p90Milliseconds: percentile(times, 0.9),
      maximumMilliseconds: Math.max(...times),
      maximumWidthError: Math.max(...variant.validation.map(({ maximumWidthError }) => maximumWidthError)),
      maximumOutputRmse: Math.max(...variant.validation.map(({ outputRmse }) => outputRmse)),
      samples: variant.samples,
      validation: variant.validation,
    };
  });
  const byName = Object.fromEntries(summaries.map((entry) => [entry.name, entry]));
  const baseline = byName["baseline-two-live-blocks"].medianMilliseconds;
  const handoff = byName["oracle-block0-handoff"].medianMilliseconds;
  const fcOnly = byName["oracle-b1-fc-preactivation"].medianMilliseconds;
  const both = byName["oracle-block0-and-b1-fc"].medianMilliseconds;
  const projection = byName["oracle-b1-projection-only"].medianMilliseconds;
  const report = {
    chrome: await browser.version(),
    rounds,
    methodology: "Fresh page graph per timed case-0 to non-default mutation; shared browser, HTTP, and font caches prewarmed.",
    runtimeContainsJavaScript: false,
    oracleSource: reference.oracleSource,
    summaries,
    differentialEstimates: {
      block0AndStateHandoffMilliseconds: baseline - handoff,
      block1FcAndPreactivationWithLiveBlock0Milliseconds: baseline - fcOnly,
      block1FcAndPreactivationWithOracleHandoffMilliseconds: handoff - both,
      block1AttentionAndLnMilliseconds: both - projection,
      irreducibleProjectionMilliseconds: projection,
      allVectorBoundariesFreeSpeedup: baseline / projection,
    },
    note: "Deltas compare different layout graphs and are architectural upper bounds, not additive profiler attribution.",
  };
  await fs.writeFile(
    new URL("benchmark-results.json", oracleRoot),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  if (summaries.some(({ maximumWidthError }) => maximumWidthError !== 0)) process.exitCode = 1;
  await context.close();
} finally {
  await browser.close();
}
