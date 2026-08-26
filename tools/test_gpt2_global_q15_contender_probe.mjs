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
const directory = "gpt2-global-q15-contender";
const experiment = path.join(repository, "experiments", directory);
const reference = JSON.parse(await fs.readFile(path.join(experiment, "reference.json"), "utf8"));
const q15Modes = Object.keys(reference.q15.displayScales);
const modes = [...q15Modes, "q16"];
const benchmarkRounds = Math.max(3, Number(process.env.Q15_CONTENDER_BENCHMARK_ROUNDS ?? 5));

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

async function loadPage(context, label, diagnostics, mode = "mode-both") {
  const page = await context.newPage();
  watch(page, label, diagnostics);
  page.setDefaultTimeout(240_000);
  await page.goto(`${baseUrl}/index.html`, { waitUntil: "load", timeout: 240_000 });
  await page.evaluate((className) => { document.body.className = className; }, mode);
  return page;
}

async function applyFixture(page, fixture) {
  return page.evaluate(({ hidden, scoreFloor, modes }) => {
    const probe = document.querySelector("#probe");
    const started = performance.now();
    for (let dimension = 0; dimension < hidden.length; dimension += 1) {
      probe.style.setProperty(`--h${dimension}`, String(hidden[dimension]));
    }
    probe.style.setProperty("--score-offset", `${-scoreFloor * 256 * 4}px`);
    for (const mode of modes) {
      document.querySelector(`#${mode}-result`).getBoundingClientRect().width;
    }
    return performance.now() - started;
  }, { ...fixture, modes });
}

async function activateFonts(page, fixture) {
  await applyFixture(page, fixture);
  await page.evaluate(async () => document.fonts.ready);
  await applyFixture(page, fixture);
}

async function readMode(page, mode) {
  return page.evaluate(({ mode, contenders }) => {
    const prefix = mode;
    const widths = [...document.querySelectorAll(`.${prefix}-candidate`)]
      .map((row) => row.getBoundingClientRect().width);
    const maximumWidth = Math.max(...widths);
    const measuredIndex = widths.indexOf(maximumWidth);
    const style = getComputedStyle(document.querySelector(`#${prefix}-result`));
    const cssIndex = Number(style.getPropertyValue(`--${prefix}-index`));
    const cssBucket = Number(style.getPropertyValue(`--${prefix}-bucket`));
    return {
      widths,
      maximumWidth,
      measuredIndex,
      measuredWinner: contenders[measuredIndex],
      measuredBucket: Math.floor(maximumWidth / 4),
      cssIndex,
      cssWinner: contenders[cssIndex],
      cssBucket,
      stageWidth: document.querySelector(`#${prefix}-stage`).getBoundingClientRect().width,
    };
  }, { mode, contenders: reference.contenders });
}

async function benchmarkModes(context, diagnostics) {
  const pages = {};
  const measurements = {};
  for (const mode of modes) {
    pages[mode] = await loadPage(context, `benchmark-${mode}`, diagnostics, `mode-${mode}`);
    await activateFonts(pages[mode], reference.fixtures[0]);
    for (const fixture of reference.fixtures) await applyFixture(pages[mode], fixture);
    measurements[mode] = { samples: [], outputs: [] };
  }
  async function mutate(mode, fixture) {
    return pages[mode].evaluate(
      ({ fixture, mode, contenders }) => {
        const probe = document.querySelector("#probe");
        const started = performance.now();
        for (let dimension = 0; dimension < fixture.hidden.length; dimension += 1) {
          probe.style.setProperty(`--h${dimension}`, String(fixture.hidden[dimension]));
        }
        probe.style.setProperty("--score-offset", `${-fixture.scoreFloor * 256 * 4}px`);
        const result = document.querySelector(`#${mode}-result`);
        result.getBoundingClientRect().width;
        result.getBoundingClientRect().width;
        const style = getComputedStyle(result);
        const index = Number(style.getPropertyValue(`--${mode}-index`));
        return {
          milliseconds: performance.now() - started,
          index,
          winner: contenders[index],
          bucket: Number(style.getPropertyValue(`--${mode}-bucket`)),
        };
      },
      { fixture, mode, contenders: reference.contenders },
    );
  }
  for (let round = 0; round < benchmarkRounds; round += 1) {
    const order = round % 2 === 0 ? modes : [...modes].reverse();
    for (const mode of order) {
      for (const fixture of reference.fixtures) {
        const sample = await mutate(mode, fixture);
        measurements[mode].samples.push(sample.milliseconds);
        measurements[mode].outputs.push({ round, state: fixture.state, ...sample });
      }
    }
  }
  await Promise.all(Object.values(pages).map((page) => page.close()));
  return Object.entries(measurements).map(([mode, measurement]) => ({
    mode,
    rounds: benchmarkRounds,
    warmup: "one unmeasured pass over all fixtures",
    order: "alternating forward/reverse mode batches",
    ...statistics(measurement.samples),
    outputs: measurement.outputs,
  }));
}

const diagnostics = { pageErrors: [], requestFailures: [], httpErrors: [] };
const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const context = await browser.newContext({ viewport: { width: 800, height: 240 } });
  const page = await loadPage(context, "correctness", diagnostics);
  await activateFonts(page, reference.fixtures[0]);
  const correctness = [];
  for (const fixture of reference.fixtures) {
    await applyFixture(page, fixture);
    const browserModes = {};
    for (const mode of modes) browserModes[mode] = await readMode(page, mode);
    const bucketErrorForBrowserWinner = {};
    const checks = {};
    for (const mode of modes) {
      const browserMode = browserModes[mode];
      const buckets = mode === "q16" ? fixture.q16Buckets : fixture.q15CalibratedBuckets;
      const mathematicalBucket = buckets[reference.contenders.indexOf(browserMode.cssWinner)];
      bucketErrorForBrowserWinner[mode] = browserMode.cssBucket - mathematicalBucket;
      checks[`${mode}RowsFinite`] = browserMode.widths.every(
        (width) => Number.isFinite(width) && width >= 0,
      );
      checks[`${mode}StageLive`] = browserMode.stageWidth > 0;
      checks[`${mode}CssIndexMatchesMeasured`] = browserMode.cssIndex === browserMode.measuredIndex;
      checks[`${mode}CssBucketMatchesMeasured`] = browserMode.cssBucket === browserMode.measuredBucket;
    }
    correctness.push({
      state: fixture.state,
      roles: fixture.roles,
      floatWinner: fixture.floatWinner,
      floatBucketWinner: fixture.floatBucketWinner,
      floatMargin: fixture.floatMargin,
      mathematical: {
        q15NearestWinner: fixture.q15NearestMathematicalWinner,
        q15CalibratedWinner: fixture.q15CalibratedMathematicalWinner,
        q16Winner: fixture.q16MathematicalWinner,
        q15NearestBucketWinner: fixture.q15NearestBucketWinner,
        q15CalibratedBucketWinner: fixture.q15CalibratedBucketWinner,
        q16BucketWinner: fixture.q16BucketWinner,
      },
      browser: browserModes,
      bucketErrorForBrowserWinner,
      checks,
    });
  }
  const runtimeScriptElements = await page.locator("script").count();
  await page.close();

  const benchmarks = await benchmarkModes(context, diagnostics);
  await context.close();

  const q16Benchmark = benchmarks.find((item) => item.mode === "q16");
  const expectedBrowser = Object.fromEntries(
    correctness.map((item) => [item.state, Object.fromEntries(
      modes.map((mode) => [mode, item.browser[mode].cssWinner]),
    )]),
  );
  const benchmarkOutputsStable = benchmarks.every((benchmark) => (
    benchmark.outputs.every((output) => output.winner === expectedBrowser[output.state][benchmark.mode])
  ));
  const allLiveChecksPass = correctness.every((item) => Object.values(item.checks).every(Boolean));
  const noErrors = [
    ...diagnostics.pageErrors,
    ...diagnostics.requestFailures,
    ...diagnostics.httpErrors,
    ...serverErrors,
  ].length === 0;
  const collapsedTokens = (mode) => [...new Set(correctness.flatMap((item) => (
    item.browser[mode].widths
      .map((width, index) => (width === 0 ? reference.contenders[index] : null))
      .filter((token) => token !== null)
  )))].sort((left, right) => left - right);
  const q15ByScale = Object.fromEntries(q15Modes.map((mode) => [mode, {
    displayScale: reference.q15.displayScales[mode],
    matchesNearestMathematicalWinner: correctness.filter(
      (item) => item.browser[mode].cssWinner === item.mathematical.q15NearestWinner,
    ).length,
    matchesCalibratedMathematicalWinner: correctness.filter(
      (item) => item.browser[mode].cssWinner === item.mathematical.q15CalibratedWinner,
    ).length,
    matchesProductionBucketWinner: correctness.filter(
      (item) => item.browser[mode].cssWinner === item.mathematical.q15CalibratedBucketWinner,
    ).length,
    productionBucketMismatchStates: correctness
      .filter((item) => item.browser[mode].cssWinner !== item.mathematical.q15CalibratedBucketWinner)
      .map((item) => item.state),
    maximumAbsoluteBucketError: Math.max(
      ...correctness.map((item) => Math.abs(item.bucketErrorForBrowserWinner[mode])),
    ),
    collapsedTokens: collapsedTokens(mode),
  }]));
  const q16Agreement = {
    matchesMathematicalWinner: correctness.filter(
      (item) => item.browser.q16.cssWinner === item.mathematical.q16Winner,
    ).length,
    matchesBucketWinner: correctness.filter(
      (item) => item.browser.q16.cssWinner === item.mathematical.q16BucketWinner,
    ).length,
    bucketMismatchStates: correctness
      .filter((item) => item.browser.q16.cssWinner !== item.mathematical.q16BucketWinner)
      .map((item) => item.state),
    maximumAbsoluteBucketError: Math.max(
      ...correctness.map((item) => Math.abs(item.bucketErrorForBrowserWinner.q16)),
    ),
    collapsedTokens: collapsedTokens("q16"),
  };
  report = {
    chromeVersion: await browser.version(),
    benchmarkRounds,
    runtimeScriptElements,
    correctness,
    browserAgreement: {
      fixtures: correctness.length,
      q15ByScale,
      q16: q16Agreement,
      state519Q16FloatWinnerCollapsed:
        correctness.find((item) => item.state === 519).browser.q16.widths[
          reference.contenders.indexOf(37848)
        ] === 0,
    },
    benchmarks,
    latency: Object.fromEntries(q15Modes.map((mode) => {
      const q15Benchmark = benchmarks.find((item) => item.mode === mode);
      return [mode, {
        displayScale: reference.q15.displayScales[mode],
        q15ToQ16MedianRatio: q15Benchmark.medianMilliseconds / q16Benchmark.medianMilliseconds,
        q15ToQ16MeanRatio: q15Benchmark.meanMilliseconds / q16Benchmark.meanMilliseconds,
        q16ToQ15MeanSpeedup: q16Benchmark.meanMilliseconds / q15Benchmark.meanMilliseconds,
      }];
    })),
    allLiveChecksPass,
    benchmarkOutputsStable,
    diagnostics: { ...diagnostics, serverErrors },
    pass:
      runtimeScriptElements === 0
      && allLiveChecksPass
      && benchmarkOutputsStable
      && noErrors,
  };
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}

await fs.writeFile(path.join(experiment, "results.json"), `${JSON.stringify(report, null, 2)}\n`);

const q16Timing = report.benchmarks.find((item) => item.mode === "q16");
const scaleLabel = (mode) => {
  const value = reference.q15.displayScales[mode];
  if (value === 0.1) return "0.1";
  if (value === 1 / 16) return "1/16";
  if (value === 1 / 32) return "1/32";
  return String(value);
};
const stateRows = report.correctness.map((item) => (
  `| ${item.state} | ${item.roles.join(", ")} | ${item.floatWinner} | `
  + `${item.mathematical.q15NearestWinner} | ${item.mathematical.q15CalibratedWinner} | `
  + `${item.mathematical.q16BucketWinner} | `
  + q15Modes.map((mode) => item.browser[mode].cssWinner).join(" | ") + " | "
  + `${item.browser.q16.cssWinner} | `
  + `${item.floatMargin.toFixed(6)} |`
)).join("\n");
const state519 = report.correctness.find((item) => item.state === 519);
const state493 = report.correctness.find((item) => item.state === 493);
const scaleRows = q15Modes.map((mode) => {
  const agreement = report.browserAgreement.q15ByScale[mode];
  return `| ${scaleLabel(mode)} | ${agreement.matchesProductionBucketWinner}/${report.browserAgreement.fixtures} | `
    + `${agreement.productionBucketMismatchStates.join(", ") || "none"} | `
    + `${agreement.collapsedTokens.length} | ${agreement.maximumAbsoluteBucketError} |`;
}).join("\n");
const timingRows = q15Modes.map((mode) => {
  const timing = report.benchmarks.find((item) => item.mode === mode);
  const ratio = report.latency[mode].q15ToQ16MeanRatio;
  return `| q15 ${scaleLabel(mode)} | 6 | ${timing.medianMilliseconds.toFixed(2)} | `
    + `${timing.meanMilliseconds.toFixed(2)} | ${timing.p95Milliseconds.toFixed(2)} | `
    + `${ratio.toFixed(3)}× |`;
}).join("\n");
const bestMode = [...q15Modes].sort((left, right) => {
  const leftAgreement = report.browserAgreement.q15ByScale[left];
  const rightAgreement = report.browserAgreement.q15ByScale[right];
  return leftAgreement.productionBucketMismatchStates.length
    - rightAgreement.productionBucketMismatchStates.length
    || leftAgreement.maximumAbsoluteBucketError - rightAgreement.maximumAbsoluteBucketError;
})[0];
const bestAgreement = report.browserAgreement.q15ByScale[bestMode];
const q15Columns = q15Modes.map((mode) => `q15 Chrome ${scaleLabel(mode)}`).join(" | ");
const q15Separators = q15Modes.map(() => "---:").join(" | ");
const markdown = `# GPT-2 global-q15 contender browser probe

## Result

The best calibrated-q15 display scale is **${scaleLabel(bestMode)}**: it matches the production q16 bucket winner on ${bestAgreement.matchesProductionBucketWinner}/${report.browserAgreement.fixtures} fixtures, with mismatches at ${bestAgreement.productionBucketMismatchStates.join(", ") || "none"}. Live grid verification passed: **${report.pass}**.

At state 519, the production target is token ${state519.mathematical.q16BucketWinner}; q15 at ${q15Modes.map((mode) => `${scaleLabel(mode)} chooses ${state519.browser[mode].cssWinner}`).join(", ")}, while the retained q16 control chooses ${state519.browser.q16.cssWinner}.

At state 493, production-calibrated q15 and q16 buckets both choose token ${state493.mathematical.q16BucketWinner}; q15 at ${q15Modes.map((mode) => `${scaleLabel(mode)} chooses ${state493.browser[mode].cssWinner}`).join(", ")}, while q16 chooses ${state493.browser.q16.cssWinner}.

| q15 display scale | Production bucket matches | Mismatch states | Zero-width tokens | Max bucket error |
| ---: | ---: | --- | ---: | ---: |
${scaleRows}

The nearest-q15 1,024-state screen has exactly one unbucketed mismatch, state 547 (float token 15 versus q15 token 405). Production calibration makes two residual-only moves: token 15 dimension 496 changes -1887 to -1886, and token 82 dimension 36 changes -2913 to -2912. It reaches 1,024/1,024 original-float winner agreement and 1,024/1,024 global-q16 production-bucket agreement; q16 has zero mathematical mismatches. The live Chrome q15 fonts contain both moves without changing the six-glyph topology. The browser fixture set covers ${reference.coverage.topFloatSlotsCovered}/${reference.coverage.topFloatSlotsRequested} requested top-16 float slots with ${reference.contenderCount} unique contenders.

| State | Selection role | Float | nearest q15 | calibrated q15 | Production bucket | ${q15Columns} | q16 Chrome | Float margin |
| ---: | --- | ---: | ---: | ---: | ---: | ${q15Separators} | ---: | ---: |
${stateRows}

## Latency

| Transport | Glyphs/row | Median (ms) | Mean (ms) | p95 (ms) | Mean/q16 |
| --- | ---: | ---: | ---: | ---: | ---: |
${timingRows}
| retained global q16 | 12 | ${q16Timing.medianMilliseconds.toFixed(2)} | ${q16Timing.meanMilliseconds.toFixed(2)} | ${q16Timing.p95Milliseconds.toFixed(2)} | 1.000× |

The retained q16 control matches ${report.browserAgreement.q16.matchesBucketWinner}/${report.browserAgreement.fixtures} production bucket targets, collapses ${report.browserAgreement.q16.collapsedTokens.length} tokens somewhere in the fixture suite, and has maximum bucket error ${report.browserAgreement.q16.maximumAbsoluteBucketError}. Its state-519 float-winner row ${report.browserAgreement.state519Q16FloatWinnerCollapsed ? "does" : "does not"} collapse to zero width.

This probe uses production-range homogeneous coordinates, real 768-axis rows, and no runtime JavaScript. GPT-2's architecture and source checkpoint are unchanged; the tested q15 approximation contains the two declared residual-code calibrations above. Only ${reference.contenderCount} q15 rows were generated; this is not a full q15 font bank.

Chrome: ${report.chromeVersion}. Timings use one unmeasured all-fixture warmup followed by ${report.benchmarkRounds} warm rounds. Raw data: results.json. The completed nearest, single-move, and two-move-0.1 runs are preserved under nearest-*, single-move-*, and two-move-s10-* filenames.

## Reproduce

    PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_gpt2_global_q15_contender_probe.py
    node --check tools/test_gpt2_global_q15_contender_probe.mjs
    Q15_CONTENDER_BENCHMARK_ROUNDS=${report.benchmarkRounds} node tools/test_gpt2_global_q15_contender_probe.mjs
`;
await fs.writeFile(path.join(experiment, "RESULTS.md"), markdown);
console.log(JSON.stringify({
  chromeVersion: report.chromeVersion,
  browserAgreement: report.browserAgreement,
  latency: report.latency,
  allLiveChecksPass: report.allLiveChecksPass,
  benchmarkOutputsStable: report.benchmarkOutputsStable,
  pass: report.pass,
}, null, 2));
