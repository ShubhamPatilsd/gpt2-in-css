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
const directory = "gpt2-progressive-precision-block-gate";
const experiment = path.join(repository, "experiments", directory);
const reference = JSON.parse(await fs.readFile(path.join(experiment, "reference.json"), "utf8"));
const benchmarkRounds = Math.max(
  2,
  Number(process.env.PROGRESSIVE_PRECISION_BENCHMARK_ROUNDS ?? 3),
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
const baseUrl = `http://127.0.0.1:${server.address().port}/experiments`;

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

async function loadPage(context, url, label, diagnostics, bodyClass = "") {
  const page = await context.newPage();
  watch(page, label, diagnostics);
  page.setDefaultTimeout(240_000);
  await page.goto(url, { waitUntil: "load", timeout: 240_000 });
  await page.evaluate(async (className) => {
    document.body.className = className;
    await document.fonts.ready;
  }, bodyClass);
  return page;
}

async function applyFixture(page, fixture) {
  await page.evaluate(({ hidden, scoreFloor, queryNorm }) => {
    const probe = document.querySelector("#probe");
    for (let dimension = 0; dimension < hidden.length; dimension += 1) {
      probe.style.setProperty(`--h${dimension}`, String(hidden[dimension]));
    }
    probe.style.setProperty("--score-offset", `${-scoreFloor * 256 * 4}px`);
    probe.style.setProperty("--query-norm", String(queryNorm));
  }, fixture);
}

async function settleProgressive(page) {
  await page.evaluate(() => {
    for (let pass = 0; pass < 4; pass += 1) {
      document.querySelector("#q10-lower-max").getBoundingClientRect().width;
      document.querySelector("#q12-lower-max").getBoundingClientRect().width;
      document.querySelector("#progressive-max").getBoundingClientRect().width;
      document.querySelector("#progressive-result").getBoundingClientRect().width;
    }
  });
}

async function readProgressive(page) {
  return page.evaluate((blockCount) => {
    const q10ActiveBlocks = [];
    const q16ActiveBlocks = [];
    const q10CarrierWidths = [];
    const q16CarrierWidths = [];
    const q12Displays = [];
    const q16Displays = [];
    for (let block = 0; block < blockCount; block += 1) {
      const q10Carrier = document.querySelector(`#q10-gate-${block}`);
      const q16Carrier = document.querySelector(`#q16-gate-${block}`);
      const q12Block = document.querySelector(`#q12-block-${block}`);
      const q16Block = document.querySelector(`#q16-block-${block}`);
      const q10Width = q10Carrier.getBoundingClientRect().width;
      const q16Width = q16Carrier.getBoundingClientRect().width;
      const q12Display = getComputedStyle(q12Block).display;
      const q16Display = getComputedStyle(q16Block).display;
      q10CarrierWidths.push(q10Width);
      q16CarrierWidths.push(q16Width);
      q12Displays.push(q12Display);
      q16Displays.push(q16Display);
      if (q12Display !== "none") q10ActiveBlocks.push(block);
      if (q16Display !== "none") q16ActiveBlocks.push(block);
    }
    const result = getComputedStyle(document.querySelector("#progressive-result"));
    return {
      q10ActiveBlocks,
      q16ActiveBlocks,
      q10CarrierWidths,
      q16CarrierWidths,
      q12Displays,
      q16Displays,
      q10LowerMaxBucket: document.querySelector("#q10-lower-max").getBoundingClientRect().width / 4,
      q12LowerMaxBucket: document.querySelector("#q12-lower-max").getBoundingClientRect().width / 4,
      winner: Number(result.getPropertyValue("--winner")),
      winnerBucket: Number(result.getPropertyValue("--winner-bucket")),
      scriptElements: document.scripts.length,
      cssRuleCount: [...document.styleSheets]
        .reduce((sum, sheet) => sum + sheet.cssRules.length, 0),
      debug: {
        q10Row0Width: document.querySelector("#q10-0").getBoundingClientRect().width,
        q10Row11Width: document.querySelector("#q10-11").getBoundingClientRect().width,
        q10Row0AnchorName: getComputedStyle(document.querySelector("#q10-0")).anchorName,
        q10Chunk0PositionAnchor: getComputedStyle(
          document.querySelector(".q10-lower-chunk-0"),
        ).positionAnchor,
        q10Chunk0Width: document.querySelector(".q10-lower-chunk-0").getBoundingClientRect().width,
        q10Chunk0ComputedWidth: getComputedStyle(
          document.querySelector(".q10-lower-chunk-0"),
        ).width,
        q10LowerComputedWidth: getComputedStyle(
          document.querySelector("#q10-lower-max"),
        ).width,
      },
    };
  }, reference.blockCount);
}

async function benchmarkModes(context, diagnostics) {
  const configurations = {
    progressive: {
      url: `${baseUrl}/${directory}/index.html`,
      bodyClass: "",
      selector: "#progressive-result",
      property: "--winner",
    },
    direct: {
      url: `${baseUrl}/gpt2-token-uncertainty-block-gate/index-b4.html`,
      bodyClass: "mode-gated",
      selector: "#gated-result",
      property: "--gated-winner",
    },
    full: {
      url: `${baseUrl}/gpt2-token-uncertainty-block-gate/index-b4.html`,
      bodyClass: "mode-full",
      selector: "#full-result",
      property: "--full-winner",
    },
  };
  const pages = {};
  const measurements = {};
  for (const [mode, configuration] of Object.entries(configurations)) {
    pages[mode] = await loadPage(
      context,
      configuration.url,
      `benchmark-${mode}`,
      diagnostics,
      configuration.bodyClass,
    );
    measurements[mode] = { samples: [], outputs: [] };
  }

  async function mutate(mode, fixture) {
    const configuration = configurations[mode];
    return pages[mode].evaluate(
      ({ values, selector, property }) => {
        const probe = document.querySelector("#probe");
        const started = performance.now();
        for (let dimension = 0; dimension < values.hidden.length; dimension += 1) {
          probe.style.setProperty(`--h${dimension}`, String(values.hidden[dimension]));
        }
        probe.style.setProperty("--score-offset", `${-values.scoreFloor * 256 * 4}px`);
        probe.style.setProperty("--query-norm", String(values.queryNorm));
        const result = document.querySelector(selector);
        result.getBoundingClientRect().width;
        result.getBoundingClientRect().width;
        return {
          milliseconds: performance.now() - started,
          winner: Number(getComputedStyle(result).getPropertyValue(property)),
        };
      },
      { values: fixture, selector: configuration.selector, property: configuration.property },
    );
  }

  // Exercise every conditional font/layout path before measuring mutation latency.
  for (const mode of Object.keys(configurations)) {
    for (const fixture of reference.fixtures) await mutate(mode, fixture);
  }
  for (let round = 0; round < benchmarkRounds; round += 1) {
    const order = round % 2 === 0
      ? ["progressive", "direct", "full"]
      : ["full", "direct", "progressive"];
    for (const mode of order) {
      for (const fixture of reference.fixtures) {
        const sample = await mutate(mode, fixture);
        measurements[mode].samples.push(sample.milliseconds);
        measurements[mode].outputs.push({ round, fixture: fixture.fixture, ...sample });
      }
    }
  }
  await Promise.all(Object.values(pages).map((page) => page.close()));
  return Object.entries(measurements).map(([mode, measurement]) => ({
    mode,
    rounds: benchmarkRounds,
    warmup: "one unmeasured pass over all ten fixtures per mode",
    order: "alternating progressive-direct-full / full-direct-progressive batches",
    ...statistics(measurement.samples),
    outputs: measurement.outputs,
  }));
}

const diagnostics = { pageErrors: [], requestFailures: [], httpErrors: [] };
const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const context = await browser.newContext({ viewport: { width: 800, height: 240 } });
  const page = await loadPage(
    context,
    `${baseUrl}/${directory}/index.html`,
    "correctness-progressive",
    diagnostics,
  );
  const correctness = [];
  for (const fixture of reference.fixtures) {
    await applyFixture(page, fixture);
    await settleProgressive(page);
    const browserResult = await readProgressive(page);
    correctness.push({
      fixture: fixture.fixture,
      expected: {
        q10ActiveBlocks: fixture.q10ActiveBlocks,
        q16ActiveBlocks: fixture.q16ActiveBlocks,
        q10LowerMaxBucket: fixture.lowerMaxBucket,
        q12LowerMaxBucket: fixture.q12LowerMaxBucket,
        winner: fixture.exactWinner,
        winnerBucket: fixture.exactWinnerBucket,
      },
      browser: browserResult,
      checks: {
        q10ActiveBlocksMatch:
          JSON.stringify(browserResult.q10ActiveBlocks) === JSON.stringify(fixture.q10ActiveBlocks),
        q16ActiveBlocksMatch:
          JSON.stringify(browserResult.q16ActiveBlocks) === JSON.stringify(fixture.q16ActiveBlocks),
        q10CarriersAreBinary:
          browserResult.q10CarrierWidths.every((width) => width === 0 || width === 1),
        q16CarriersAreBinary:
          browserResult.q16CarrierWidths.every((width) => width === 0 || width === 1),
        q12DisplaysMatch: browserResult.q12Displays.every((display, block) => (
          fixture.q10ActiveBlocks.includes(block) ? display === "grid" : display === "none"
        )),
        q16DisplaysMatch: browserResult.q16Displays.every((display, block) => (
          fixture.q16ActiveBlocks.includes(block) ? display === "grid" : display === "none"
        )),
        q10LowerWithinAllowance:
          Math.abs(browserResult.q10LowerMaxBucket - fixture.lowerMaxBucket)
          <= reference.allowanceBucketsAtEachTransition,
        q12LowerWithinAllowance:
          Math.abs(browserResult.q12LowerMaxBucket - fixture.q12LowerMaxBucket)
          <= reference.allowanceBucketsAtEachTransition,
        winnerMatchesOracle: browserResult.winner === fixture.exactWinner,
        winnerBucketWithinFineAllowance:
          Math.abs(browserResult.winnerBucket - fixture.exactWinnerBucket) <= 8,
        runtimeHasNoScript: browserResult.scriptElements === 0,
      },
    });
  }
  await page.close();

  const benchmarks = await benchmarkModes(context, diagnostics);
  await context.close();

  const allFixtureChecksPass = correctness.every((fixture) => (
    Object.values(fixture.checks).every(Boolean)
  ));
  const benchmarkWinnersCorrect = benchmarks.every((benchmark) => (
    benchmark.outputs.every((output) => (
      output.winner === reference.fixtures[output.fixture].exactWinner
    ))
  ));
  const noErrors = [
    ...diagnostics.pageErrors,
    ...diagnostics.requestFailures,
    ...diagnostics.httpErrors,
    ...serverErrors,
  ].length === 0;
  const progressive = benchmarks.find((item) => item.mode === "progressive");
  const direct = benchmarks.find((item) => item.mode === "direct");
  const full = benchmarks.find((item) => item.mode === "full");
  report = {
    chromeVersion: await browser.version(),
    benchmarkRounds,
    correctness,
    benchmarks,
    comparisons: {
      directToProgressiveMedianRatio:
        direct.medianMilliseconds / progressive.medianMilliseconds,
      directToProgressiveMeanRatio:
        direct.meanMilliseconds / progressive.meanMilliseconds,
      progressiveToDirectMedianRatio:
        progressive.medianMilliseconds / direct.medianMilliseconds,
      progressiveToDirectMeanRatio:
        progressive.meanMilliseconds / direct.meanMilliseconds,
      fullToProgressiveMedianRatio:
        full.medianMilliseconds / progressive.medianMilliseconds,
      fullToProgressiveMeanRatio:
        full.meanMilliseconds / progressive.meanMilliseconds,
    },
    allFixtureChecksPass,
    benchmarkWinnersCorrect,
    diagnostics: { ...diagnostics, serverErrors },
    pass: allFixtureChecksPass && benchmarkWinnersCorrect && noErrors,
  };
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}

await fs.writeFile(path.join(experiment, "results.json"), `${JSON.stringify(report, null, 2)}\n`);

const timings = Object.fromEntries(report.benchmarks.map((item) => [item.mode, item]));
const progressiveBeatsDirect = report.comparisons.directToProgressiveMeanRatio > 1;
const decision = progressiveBeatsDirect
  ? "The progressive q12 wave beats the direct q10→q16 B=4 gate in this vertical slice."
  : "The progressive q12 wave is correct but slower than the direct q10→q16 B=4 gate in this vertical slice; do not scale this exact browser topology yet.";
const timingRows = report.benchmarks.map((item) => (
  `| ${item.mode} | ${item.medianMilliseconds.toFixed(2)} | ${item.meanMilliseconds.toFixed(2)} | `
  + `${item.p95Milliseconds.toFixed(2)} |`
)).join("\n");
const markdown = `# Progressive precision block-gate browser probe

## Result

${decision} All ${reference.fixtures.length} certified group-0 fixtures ${report.allFixtureChecksPass ? "passed" : "did not pass"}; every benchmark mutation ${report.benchmarkWinnersCorrect ? "matched" : "did not match"} the q16 oracle. Overall correctness pass: **${report.pass}**.

| Path | Median (ms) | Mean (ms) | p95 (ms) |
| --- | ---: | ---: | ---: |
${timingRows}

Progressive/direct mean slowdown: **${report.comparisons.progressiveToDirectMeanRatio.toFixed(3)}×**. Full/progressive mean speedup: **${report.comparisons.fullToProgressiveMeanRatio.toFixed(3)}×**.

The progressive path shapes a mean ${reference.offline.meanQ12Rows.toFixed(1)} q12 rows and ${reference.offline.meanQ16Rows.toFixed(1)} q16 rows, versus ${reference.offline.meanQ12Rows.toFixed(1)} q16 rows in the direct B=4 gate. The q12 transport is radix-64 high/residual, three 256-axis shards per plane, at display scale ${reference.q12Transport.displayScale}.

## Correctness contract

- GPT-2 small architecture, checkpoint, and weights are unchanged; this is numerical representation and certified search only.
- q10 intervals activate contiguous four-row q12 blocks; q12 intervals activate contiguous four-row q16 blocks; q16 supplies the final exact argmax.
- Each transition uses an inclusive upper-versus-global-lower comparison and ${reference.allowanceBucketsAtEachTransition} outward buckets.
- The runtime HTML contains no JavaScript. The external Playwright verifier checks both gate waves, binary carriers, wrapper visibility, q16 winner/bucket, and mutation outputs.

Chrome: ${report.chromeVersion}. Timings use one unmeasured all-fixture warmup, then ${report.benchmarkRounds} alternating rounds of all ten fixture mutations per path. Raw measurements: results.json.

## Reproduce

    PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_progressive_precision_block_gate_probe.py
    node --check tools/test_progressive_precision_block_gate_probe.mjs
    PROGRESSIVE_PRECISION_BENCHMARK_ROUNDS=${report.benchmarkRounds} node tools/test_progressive_precision_block_gate_probe.mjs
`;
await fs.writeFile(path.join(experiment, "RESULTS.md"), markdown);
console.log(JSON.stringify(report, null, 2));
