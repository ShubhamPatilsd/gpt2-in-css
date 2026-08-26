import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const repository = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const directory = "gpt2-progressive-precision-crossover";
const experiment = path.join(repository, "experiments", directory);
const reference = JSON.parse(await fs.readFile(path.join(experiment, "reference.json"), "utf8"));
const benchmarkRounds = Math.max(
  2,
  Number(process.env.PROGRESSIVE_CROSSOVER_BENCHMARK_ROUNDS ?? 3),
);

const contentTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".ttf", "font/ttf"],
  [".woff2", "font/woff2"],
]);
const serverErrors = [];
const server = http.createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
    if (pathname === "/favicon.ico") {
      response.writeHead(204).end();
      return;
    }
    const relative = pathname.replace(/^\/+/, "");
    const filename = path.resolve(repository, relative || "index.html");
    if (filename !== repository && !filename.startsWith(`${repository}${path.sep}`)) {
      response.writeHead(403).end("forbidden");
      return;
    }
    const body = await fs.readFile(filename);
    response.writeHead(200, {
      "content-type": contentTypes.get(path.extname(filename)) ?? "application/octet-stream",
      "cache-control": "no-store",
    });
    response.end(body);
  } catch (error) {
    serverErrors.push(String(error));
    response.writeHead(404).end("not found");
  }
});
await new Promise((resolve, reject) => {
  server.once("error", reject);
  server.listen(0, "127.0.0.1", resolve);
});
const baseUrl = `http://127.0.0.1:${server.address().port}/experiments/${directory}`;

function percentile(values, fraction) {
  const ordered = [...values].sort((left, right) => left - right);
  return ordered[Math.min(ordered.length - 1, Math.ceil(ordered.length * fraction) - 1)];
}

function statistics(values) {
  const ordered = [...values].sort((left, right) => left - right);
  const middle = Math.floor(ordered.length / 2);
  return {
    samples: ordered.length,
    minimumMilliseconds: ordered[0],
    medianMilliseconds: ordered.length % 2
      ? ordered[middle]
      : (ordered[middle - 1] + ordered[middle]) / 2,
    p95Milliseconds: percentile(ordered, 0.95),
    maximumMilliseconds: ordered.at(-1),
    meanMilliseconds: ordered.reduce((sum, value) => sum + value, 0) / ordered.length,
  };
}

function watch(page, label, diagnostics) {
  page.on("pageerror", (error) => diagnostics.pageErrors.push({ label, error: String(error) }));
  page.on("requestfailed", (request) => diagnostics.requestFailures.push({
    label,
    url: request.url(),
    error: request.failure()?.errorText ?? "unknown request failure",
  }));
  page.on("response", (response) => {
    if (response.status() >= 400) {
      diagnostics.httpErrors.push({ label, url: response.url(), status: response.status() });
    }
  });
}

async function loadPage(context, filename, label, diagnostics) {
  const page = await context.newPage();
  watch(page, label, diagnostics);
  page.setDefaultTimeout(240_000);
  await page.goto(`${baseUrl}/${filename}`, { waitUntil: "load", timeout: 240_000 });
  await page.evaluate(async () => document.fonts.ready);
  return page;
}

async function mutate(page, fixture) {
  return page.evaluate(({ hidden, scoreFloor }) => {
    const probe = document.querySelector("#probe");
    const started = performance.now();
    for (let dimension = 0; dimension < hidden.length; dimension += 1) {
      probe.style.setProperty(`--h${dimension}`, String(hidden[dimension]));
    }
    probe.style.setProperty("--score-offset", `${-scoreFloor * 256 * 4}px`);
    const result = document.querySelector("#result");
    result.getBoundingClientRect().width;
    result.getBoundingClientRect().width;
    return {
      milliseconds: performance.now() - started,
      observed: Number(getComputedStyle(result).getPropertyValue("--observed")),
    };
  }, fixture);
}

async function activateFonts(page, fixture) {
  await mutate(page, fixture);
  await page.evaluate(async () => document.fonts.ready);
  await mutate(page, fixture);
}

async function inspect(page, mode, point) {
  return page.evaluate(({ mode, point }) => {
    const firstContent = document.querySelector(".first-wave-content");
    const q12Stage = document.querySelector("#q12-stage");
    const secondGate = document.querySelector("#second-gate");
    const finalStage = document.querySelector("#final-stage");
    return {
      mode,
      scriptElements: document.scripts.length,
      hiddenPropertyCount: 768,
      scoreRows: document.querySelectorAll(".score-row").length,
      q12Rows: document.querySelectorAll(".q12-row").length,
      q16Rows: document.querySelectorAll(".q16-row").length,
      firstGateWidth: document.querySelector("#first-gate").getBoundingClientRect().width,
      firstContentDisplay: getComputedStyle(firstContent).display,
      q12StageWidth: q12Stage?.getBoundingClientRect().width ?? null,
      secondGateWidth: secondGate?.getBoundingClientRect().width ?? null,
      secondContentDisplay: secondGate ? getComputedStyle(finalStage).display : null,
      finalStageWidth: finalStage.getBoundingClientRect().width,
      expected: {
        q12Rows: mode === "progressive" ? point.q12Rows : 0,
        q16Rows: mode === "progressive" ? point.progressiveQ16Rows : point.directQ16Rows,
      },
    };
  }, { mode, point });
}

async function benchmarkPoint(context, point, diagnostics) {
  const pages = {
    direct: await loadPage(context, point.directPage, `direct-${point.q12Rows}`, diagnostics),
    progressive: await loadPage(
      context,
      point.progressivePage,
      `progressive-${point.q12Rows}`,
      diagnostics,
    ),
  };
  await activateFonts(pages.direct, reference.fixtures[0]);
  await activateFonts(pages.progressive, reference.fixtures[0]);
  const inspections = {
    direct: await inspect(pages.direct, "direct", point),
    progressive: await inspect(pages.progressive, "progressive", point),
  };

  // Load every conditional font and exercise every fixture before timing.
  for (const mode of ["direct", "progressive"]) {
    for (const fixture of reference.fixtures) await mutate(pages[mode], fixture);
  }

  const measurements = {
    direct: { samples: [], outputs: [] },
    progressive: { samples: [], outputs: [] },
  };
  for (let round = 0; round < benchmarkRounds; round += 1) {
    const order = round % 2 === 0 ? ["direct", "progressive"] : ["progressive", "direct"];
    for (const mode of order) {
      for (const fixture of reference.fixtures) {
        const sample = await mutate(pages[mode], fixture);
        measurements[mode].samples.push(sample.milliseconds);
        measurements[mode].outputs.push({
          round,
          fixture: fixture.fixture,
          ...sample,
        });
      }
    }
  }
  await Promise.all(Object.values(pages).map((page) => page.close()));

  const direct = {
    ...statistics(measurements.direct.samples),
    outputs: measurements.direct.outputs,
  };
  const progressive = {
    ...statistics(measurements.progressive.samples),
    outputs: measurements.progressive.outputs,
  };
  const inspectionChecks = {
    directNoRuntimeScript: inspections.direct.scriptElements === 0,
    progressiveNoRuntimeScript: inspections.progressive.scriptElements === 0,
    directQ12RowsMatch: inspections.direct.q12Rows === 0,
    directQ16RowsMatch: inspections.direct.q16Rows === point.directQ16Rows,
    progressiveQ12RowsMatch: inspections.progressive.q12Rows === point.q12Rows,
    progressiveQ16RowsMatch:
      inspections.progressive.q16Rows === point.progressiveQ16Rows,
    directFirstWaveActive:
      inspections.direct.firstGateWidth >= 1
      && inspections.direct.firstContentDisplay === "grid",
    progressiveFirstWaveActive:
      inspections.progressive.firstGateWidth >= 1
      && inspections.progressive.firstContentDisplay === "grid"
      && inspections.progressive.q12StageWidth > 0,
    progressiveSecondWaveActive:
      inspections.progressive.secondGateWidth >= 1
      && inspections.progressive.secondContentDisplay === "grid",
    directFinalWidthLive: inspections.direct.finalStageWidth > 0,
    progressiveFinalWidthLive: inspections.progressive.finalStageWidth > 0,
  };
  const outputChecks = {
    directOutputsFinite: direct.outputs.every((output) => Number.isFinite(output.observed)),
    progressiveOutputsFinite:
      progressive.outputs.every((output) => Number.isFinite(output.observed)),
    directOutputsReact:
      new Set(direct.outputs.map((output) => output.observed)).size > 1,
    progressiveOutputsReact:
      new Set(progressive.outputs.map((output) => output.observed)).size > 1,
  };
  return {
    q12Rows: point.q12Rows,
    directQ16Rows: point.directQ16Rows,
    progressiveQ16Rows: point.progressiveQ16Rows,
    inspections,
    inspectionChecks,
    outputChecks,
    direct,
    progressive,
    progressiveToDirectMedianRatio:
      progressive.medianMilliseconds / direct.medianMilliseconds,
    progressiveToDirectMeanRatio:
      progressive.meanMilliseconds / direct.meanMilliseconds,
    progressiveFasterByMean:
      progressive.meanMilliseconds < direct.meanMilliseconds,
  };
}

const diagnostics = { pageErrors: [], requestFailures: [], httpErrors: [] };
const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const context = await browser.newContext({ viewport: { width: 800, height: 240 } });
  const points = [];
  for (const point of reference.scalePoints) {
    points.push(await benchmarkPoint(context, point, diagnostics));
  }
  await context.close();

  const globalBudget = points.find((point) => point.q12Rows === 418);
  const allChecksPass = points.every((point) => (
    [...Object.values(point.inspectionChecks), ...Object.values(point.outputChecks)].every(Boolean)
  ));
  const noErrors = [
    ...diagnostics.pageErrors,
    ...diagnostics.requestFailures,
    ...diagnostics.httpErrors,
    ...serverErrors,
  ].length === 0;
  const firstMeanCrossover = points.find((point) => point.progressiveFasterByMean) ?? null;
  const materiallyFaster = (point) => (
    point.progressiveToDirectMeanRatio <= 0.95
    && point.progressiveToDirectMedianRatio <= 0.95
  );
  const firstMaterialCrossover = points.find(materiallyFaster) ?? null;
  report = {
    chromeVersion: await browser.version(),
    benchmarkRounds,
    methodology: {
      warmup: "one unmeasured pass over all ten fixtures per mode and scale",
      ordering: "alternating direct-progressive / progressive-direct batches",
      mutation: "all 768 hidden CSS custom properties plus score offset",
    },
    points,
    globalBudget: {
      q12Rows: globalBudget.q12Rows,
      directQ16Rows: globalBudget.directQ16Rows,
      progressiveQ16Rows: globalBudget.progressiveQ16Rows,
      progressiveToDirectMedianRatio: globalBudget.progressiveToDirectMedianRatio,
      progressiveToDirectMeanRatio: globalBudget.progressiveToDirectMeanRatio,
      progressiveFasterByMean: globalBudget.progressiveFasterByMean,
      progressiveMateriallyFaster: materiallyFaster(globalBudget),
    },
    firstMeanCrossoverRows: firstMeanCrossover?.q12Rows ?? null,
    firstMaterialCrossoverRows: firstMaterialCrossover?.q12Rows ?? null,
    allChecksPass,
    diagnostics: { ...diagnostics, serverErrors },
    pass: allChecksPass && noErrors,
  };
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}

await fs.writeFile(path.join(experiment, "results.json"), `${JSON.stringify(report, null, 2)}\n`);

const rows = report.points.map((point) => (
  `| ${point.q12Rows} | ${point.progressiveQ16Rows} | `
  + `${point.direct.medianMilliseconds.toFixed(2)} | ${point.progressive.medianMilliseconds.toFixed(2)} | `
  + `${point.direct.meanMilliseconds.toFixed(2)} | ${point.progressive.meanMilliseconds.toFixed(2)} | `
  + `${point.progressiveToDirectMeanRatio.toFixed(3)}× |`
)).join("\n");
const globalDecision = report.globalBudget.progressiveMateriallyFaster
  ? `At the 418→22 global B=4 budget, the extra q12 dependency materially amortizes: progressive is ${
    (1 / report.globalBudget.progressiveToDirectMeanRatio).toFixed(3)
  }× faster by mean.`
  : report.globalBudget.progressiveFasterByMean
    ? `At the 418→22 global B=4 budget, the paths are at parity rather than a robust crossover: progressive is ${
      (1 / report.globalBudget.progressiveToDirectMeanRatio).toFixed(3)
    }× faster by mean but does not clear the 5% mean-and-median materiality threshold.`
    : `At the 418→22 global B=4 budget, the extra q12 dependency does not amortize: progressive is ${
      report.globalBudget.progressiveToDirectMeanRatio.toFixed(3)
    }× slower by mean.`;
const crossover = report.firstMaterialCrossoverRows === null
  ? "No tested scale point has a material mean-and-median crossover."
  : `The first material tested crossover is ${report.firstMaterialCrossoverRows} rows.`;
const markdown = `# Progressive precision real-font crossover probe

## Result

${globalDecision} ${crossover} Structural/live-output checks: **${report.allChecksPass}**. Overall probe pass: **${report.pass}**.

| Direct q16 rows / progressive q12 rows | Progressive q16 rows | Direct median (ms) | Progressive median (ms) | Direct mean (ms) | Progressive mean (ms) | Progressive/direct mean |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
${rows}

This is a latency crossover probe, not a model-correctness result. Both paths use real GPT-2-derived 768-axis font rows and mutate all 768 hidden properties. Direct has one container/layout wave before q16 shaping. Progressive shapes radix-64 q12 rows through the first wave, then uses their max-content anchor to activate a second wave containing the reduced q16 row set.

GPT-2 architecture, checkpoint, and weights are unchanged. Runtime pages contain no JavaScript.

Chrome: ${report.chromeVersion}. Measurements use one unmeasured ten-fixture warmup followed by ${report.benchmarkRounds} alternating warm rounds. Raw data: results.json.

## Reproduce

    PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_progressive_precision_crossover_probe.py
    node --check tools/test_progressive_precision_crossover_probe.mjs
    PROGRESSIVE_CROSSOVER_BENCHMARK_ROUNDS=${report.benchmarkRounds} node tools/test_progressive_precision_crossover_probe.mjs
`;
await fs.writeFile(path.join(experiment, "RESULTS.md"), markdown);
console.log(JSON.stringify({
  chromeVersion: report.chromeVersion,
  benchmarkRounds: report.benchmarkRounds,
  globalBudget: report.globalBudget,
  firstMeanCrossoverRows: report.firstMeanCrossoverRows,
  firstMaterialCrossoverRows: report.firstMaterialCrossoverRows,
  allChecksPass: report.allChecksPass,
  pass: report.pass,
}, null, 2));
