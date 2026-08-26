import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.TIMELINE_HVAR_ROUNDS ?? "9", 10);

const reference = JSON.parse(await fs.readFile(
  new URL(
    "../experiments/gpt2-block-css/view-timeline-block-hybrid-fc-packed4-hvar-reference.json",
    import.meta.url,
  ),
  "utf8",
));
const gatherReference = JSON.parse(await fs.readFile(
  new URL(
    "../experiments/gpt2-block-css/view-timeline-block-hybrid-fc-packed4-hvar-gather-reference.json",
    import.meta.url,
  ),
  "utf8",
));
const gather8Reference = JSON.parse(await fs.readFile(
  new URL(
    "../experiments/gpt2-block-css/view-timeline-block-hybrid-fc-packed4-hvar-gather8-reference.json",
    import.meta.url,
  ),
  "utf8",
));
const directLnReference = JSON.parse(await fs.readFile(
  new URL(
    "../experiments/gpt2-block-css/view-timeline-block-hybrid-fc-packed4-hvar-direct-ln-reference.json",
    import.meta.url,
  ),
  "utf8",
));

const allVariants = [
  {
    name: "packed4-transport-only",
    file: "view-timeline-block-hybrid-fc-packed4-transport.html",
    kind: "transport",
  },
  {
    name: "packed4-hvar-width",
    file: "view-timeline-block-hybrid-fc-packed4-hvar.html",
    kind: "hvar",
  },
  {
    name: "packed4-hvar-direct-layernorm",
    file: "view-timeline-block-hybrid-fc-packed4-hvar-direct-ln.html",
    kind: "direct-ln",
  },
  {
    name: "packed4-hvar-registered-gather",
    file: "view-timeline-block-hybrid-fc-packed4-hvar-gather.html",
    kind: "gather",
  },
  {
    name: "packed4-hvar-registered-gather8",
    file: "view-timeline-block-hybrid-fc-packed4-hvar-gather8.html",
    kind: "gather8",
  },
  {
    name: "packed4-hvar-registered-gather-flat",
    file: "view-timeline-block-hybrid-fc-packed4-hvar-gather-flat.html",
    kind: "gather",
  },
  {
    name: "packed4-hvar-registered-gather-fixed",
    file: "view-timeline-block-hybrid-fc-packed4-hvar-gather-fixed.html",
    kind: "gather",
  },
  {
    name: "packed4-output-timelines",
    file: "view-timeline-block-hybrid-fc-packed4.html",
    kind: "numeric",
  },
];
const selectedVariants = new Set(
  (process.env.TIMELINE_HVAR_VARIANTS ?? allVariants.map(({ name }) => name).join(","))
    .split(",").map((name) => name.trim()).filter(Boolean),
);
const variants = allVariants.filter(({ name }) => selectedVariants.has(name));
if (variants.length === 0) throw new Error("no timeline/HVAR variants selected");

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function error(actual, expected) {
  const delta = actual.map((value, index) => value - expected[index]);
  const worstIndex = delta.reduce(
    (best, value, index) => Math.abs(value) > Math.abs(delta[best]) ? index : best,
    0,
  );
  return {
    rmse: Math.sqrt(delta.reduce((sum, value) => sum + value * value, 0) / delta.length),
    maximum: Math.max(...delta.map(Math.abs)),
    worstIndex,
    worstActual: actual[worstIndex],
    worstExpected: expected[worstIndex],
  };
}

async function readOutput(page, variant, caseIndex) {
  if (variant.kind === "hvar") {
    const widths = await page.locator(".packed4-hvar-metric").evaluateAll(
      (elements) => elements.map((element) => element.getBoundingClientRect().width),
    );
    return widths.map((width, output) =>
      reference.residualCases[caseIndex][output] +
      (width * reference.unitsPerEm / reference.fontSize -
        reference.projectionBases[output]) *
        reference.hiddenRange * reference.projectionScales[output] +
      reference.projectionBias[output]);
  }
  if (variant.kind === "gather" || variant.kind === "gather8") {
    return page.locator("#final").evaluate((element, width) => {
      const style = getComputedStyle(element);
      return Array.from({ length: width }, (_value, index) => Number(
        style.getPropertyValue(`--next-${String(index).padStart(3, "0")}`),
      ));
    }, reference.width);
  }
  if (variant.kind === "direct-ln") {
    return page.locator("#final").evaluate((element, width) => {
      const style = getComputedStyle(element);
      return Array.from({ length: width }, (_value, index) => Number(
        style.getPropertyValue(`--next-norm-${String(index).padStart(3, "0")}`),
      ));
    }, reference.width);
  }
  if (variant.kind === "numeric") {
    return page.locator("#final").evaluate((element, width) => {
      const style = getComputedStyle(element);
      return Array.from({ length: width }, (_value, index) => Number(
        style.getPropertyValue(`--out-${String(index).padStart(3, "0")}`),
      ));
    }, reference.width);
  }
  return page.locator("#final").evaluate((element, groups) => {
    const style = getComputedStyle(element);
    const values = [];
    for (let group = 0; group < groups; group += 1) {
      values.push(Number(style.getPropertyValue(`--q4c${group}`)));
      values.push(Number(style.getPropertyValue(`--q4e${group}`)));
    }
    return values;
  }, reference.fcTimelines);
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 900, height: 240 } });
  const reports = [];
  for (const variant of variants) {
    const page = await context.newPage();
    const loadStarted = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/gpt2-block-css/${variant.file}`,
      { waitUntil: "load", timeout: 180000 },
    );
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(() => new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const initial = await readOutput(page, variant, 0);
    const loadMilliseconds = performance.now() - loadStarted;
    const samples = [];
    for (let round = 0; round < rounds + 2; round += 1) {
      const caseIndex = (round + 1) % reference.inputCases.length;
      const started = performance.now();
      await page.locator(".norm1").evaluate((element, input) => {
        for (let index = 0; index < input.length; index += 1) {
          element.style.setProperty(
            `--x-${String(index).padStart(3, "0")}`,
            input[index],
          );
        }
      }, reference.inputCases[caseIndex]);
      // Scroll-driven animations update on the rendering timeline. Two frames
      // measure the point at which a user or following CSS stage can reliably
      // observe the new vector, rather than an occasionally stale first read.
      await page.evaluate(() => new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const actual = await readOutput(page, variant, caseIndex);
      const milliseconds = performance.now() - started;
      const expectedTransport = variant.kind === "gather"
        ? gatherReference.expectedGatherCases[caseIndex]
        : variant.kind === "gather8"
          ? gather8Reference.expectedGatherCases[caseIndex]
        : variant.kind === "direct-ln"
          ? directLnReference.expectedPackedLayerNormCases[caseIndex]
          : reference.expectedPackedCases[caseIndex];
      const expectedDense = variant.kind === "direct-ln"
        ? directLnReference.expectedDenseLayerNormCases[caseIndex]
        : reference.expectedDenseQuantizedCases[caseIndex];
      samples.push({
        round,
        caseIndex,
        milliseconds,
        checksum: actual.reduce((sum, value) => sum + value, 0),
        outputError: variant.kind === "transport"
          ? null
          : error(actual, expectedTransport),
        denseError: variant.kind === "transport"
          ? null
          : error(actual, expectedDense),
      });
    }
    const measured = samples.slice(2);
    const diagnostics = variant.kind === "direct-ln"
      ? await page.evaluate(() => {
        const finalStyle = getComputedStyle(document.querySelector("#final"));
        const source = document.querySelector('[data-output="138"]');
        return {
          mean: finalStyle.getPropertyValue("--hv-mean").trim(),
          variance: finalStyle.getPropertyValue("--hv-variance").trim(),
          value138: finalStyle.getPropertyValue("--hv-138").trim(),
          norm138: finalStyle.getPropertyValue("--next-norm-138").trim(),
          source138Width: source.getBoundingClientRect().width,
          source138Anchor: getComputedStyle(source).anchorName,
        };
      })
      : null;
    reports.push({
      ...variant,
      loadMilliseconds,
      initialChecksum: initial.reduce((sum, value) => sum + value, 0),
      settledMedianMilliseconds: median(measured.map(({ milliseconds }) => milliseconds)),
      settledMinimumMilliseconds: Math.min(...measured.map(({ milliseconds }) => milliseconds)),
      settledMaximumMilliseconds: Math.max(...measured.map(({ milliseconds }) => milliseconds)),
      rmseMaximum: variant.kind === "transport" ? null : Math.max(
        ...measured.map(({ outputError }) => outputError.rmse),
      ),
      maximumError: variant.kind === "transport" ? null : Math.max(
        ...measured.map(({ outputError }) => outputError.maximum),
      ),
      denseRmseMaximum: variant.kind === "transport" ? null : Math.max(
        ...measured.map(({ denseError }) => denseError.rmse),
      ),
      denseMaximumError: variant.kind === "transport" ? null : Math.max(
        ...measured.map(({ denseError }) => denseError.maximum),
      ),
      diagnostics,
      samples,
    });
    await page.close();
  }

  const byName = Object.fromEntries(reports.map((report) => [report.name, report]));
  const timing = (name) => byName[name]?.settledMedianMilliseconds ?? null;
  const difference = (left, right) => left === null || right === null
    ? null
    : left - right;
  const ratio = (numerator, denominator) => numerator === null || denominator === null
    ? null
    : numerator / denominator;
  const transport = timing("packed4-transport-only");
  const hvar = timing("packed4-hvar-width");
  const directLn = timing("packed4-hvar-direct-layernorm");
  const gather = timing("packed4-hvar-registered-gather");
  const gather8 = timing("packed4-hvar-registered-gather8");
  const flatGather = timing("packed4-hvar-registered-gather-flat");
  const fixedGather = timing("packed4-hvar-registered-gather-fixed");
  const timelines = timing("packed4-output-timelines");
  const result = {
    chrome: await browser.version(),
    rounds,
    reports,
    comparison: {
      hvarProjectionIncrementMilliseconds: difference(hvar, transport),
      directLayerNormIncrementMilliseconds: difference(directLn, hvar),
      registeredGatherIncrementMilliseconds: difference(gather, hvar),
      registeredGather8IncrementMilliseconds: difference(gather8, hvar),
      flatGatherIncrementMilliseconds: difference(flatGather, hvar),
      fixedGatherIncrementMilliseconds: difference(fixedGather, hvar),
      outputTimelineIncrementMilliseconds: difference(timelines, transport),
      gatherVersusOutputTimelineSpeedup: ratio(timelines, gather),
      gather8VersusOutputTimelineSpeedup: ratio(timelines, gather8),
      flatGatherVersusOutputTimelineSpeedup: ratio(timelines, flatGather),
      fixedGatherVersusOutputTimelineSpeedup: ratio(timelines, fixedGather),
      hvarVersusOutputTimelineSpeedup: ratio(timelines, hvar),
      hvarVersusOutputTimelineSavingsPercent:
        ratio(hvar, timelines) === null ? null : (1 - hvar / timelines) * 100,
    },
  };
  const outputName = process.env.TIMELINE_HVAR_OUTPUT ??
    "view-timeline-block-hybrid-fc-packed4-hvar-browser.json";
  await fs.writeFile(
    new URL(
      `../experiments/gpt2-block-css/${outputName}`,
      import.meta.url,
    ),
    `${JSON.stringify(result, null, 2)}\n`,
  );
  console.log(JSON.stringify(result, null, 2));
  await context.close();
} finally {
  await browser.close();
}
