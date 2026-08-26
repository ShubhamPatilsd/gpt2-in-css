import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const repository = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const experiment = path.join(repository, "experiments", "gpt2-token-uncertainty-gate");
const reference = JSON.parse(await fs.readFile(path.join(experiment, "reference.json"), "utf8"));
const benchmarkRounds = Math.max(5, Number(process.env.TOKEN_GATE_BENCHMARK_ROUNDS ?? 5));

const contentTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
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
const address = server.address();
const url = `http://127.0.0.1:${address.port}/experiments/gpt2-token-uncertainty-gate/index.html`;

function percentile(values, percentage) {
  const ordered = [...values].sort((left, right) => left - right);
  return ordered[Math.min(ordered.length - 1, Math.ceil(ordered.length * percentage) - 1)];
}

function statistics(values) {
  const ordered = [...values].sort((left, right) => left - right);
  const middle = Math.floor(ordered.length / 2);
  const median = ordered.length % 2
    ? ordered[middle]
    : (ordered[middle - 1] + ordered[middle]) / 2;
  return {
    samples: values.length,
    minimumMilliseconds: ordered[0],
    medianMilliseconds: median,
    p95Milliseconds: percentile(ordered, 0.95),
    maximumMilliseconds: ordered.at(-1),
    meanMilliseconds: values.reduce((sum, value) => sum + value, 0) / values.length,
  };
}

function number(style, property) {
  const value = Number(style.getPropertyValue(property));
  if (!Number.isFinite(value)) throw new Error(`non-numeric ${property}: ${value}`);
  return value;
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
  await page.goto(url, { waitUntil: "load", timeout: 240_000 });
  await page.evaluate(async (className) => {
    document.body.className = className;
    await document.fonts.ready;
  }, mode);
  return page;
}

async function applyFixture(page, fixture) {
  await page.evaluate(({ hidden, scoreFloor }) => {
    const probe = document.querySelector("#probe");
    for (let dimension = 0; dimension < hidden.length; dimension += 1) {
      probe.style.setProperty(`--h${dimension}`, String(hidden[dimension]));
    }
    probe.style.setProperty("--score-offset", `${-scoreFloor * 256 * 4}px`);
  }, fixture);
}

async function settleCorrectness(page) {
  await page.evaluate(() => {
    for (let pass = 0; pass < 3; pass += 1) {
      document.querySelector("#lower-max").getBoundingClientRect().width;
      document.querySelector("#gated-max").getBoundingClientRect().width;
      document.querySelector("#gated-result").getBoundingClientRect().width;
      document.querySelector("#full-result").getBoundingClientRect().width;
    }
  });
}

async function readCorrectness(page) {
  return page.evaluate(() => {
    const activeTokens = [];
    const carrierWidths = [];
    for (let token = 0; token < 256; token += 1) {
      const carrier = document.querySelector(`#gate-${token}`);
      const exact = document.querySelector(`#gated-exact-${token}`);
      const width = carrier.getBoundingClientRect().width;
      carrierWidths.push(width);
      if (getComputedStyle(exact).display !== "none") activeTokens.push(token);
    }
    const gated = getComputedStyle(document.querySelector("#gated-result"));
    const full = getComputedStyle(document.querySelector("#full-result"));
    return {
      activeTokens,
      carrierWidths,
      lowerMaxBucket: document.querySelector("#lower-max").getBoundingClientRect().width / 4,
      gatedWinner: Number(gated.getPropertyValue("--gated-winner")),
      gatedBucket: Number(gated.getPropertyValue("--gated-bucket")),
      fullWinner: Number(full.getPropertyValue("--full-winner")),
      fullBucket: Number(full.getPropertyValue("--full-bucket")),
      debug: {
        coarse0Width: document.querySelector("#coarse-0").getBoundingClientRect().width,
        coarse11Width: document.querySelector("#coarse-11").getBoundingClientRect().width,
        full0Width: document.querySelector(".full-exact").getBoundingClientRect().width,
        full11Width: document.querySelectorAll(".full-exact")[11].getBoundingClientRect().width,
        lowerWidthStyle: getComputedStyle(document.querySelector("#lower-max")).width,
        coarseFont: getComputedStyle(document.querySelector("#coarse-0")).fontFamily,
        fineFont: getComputedStyle(document.querySelector(".full-exact")).fontFamily,
        queryNorm: Number(getComputedStyle(document.querySelector("#gate-path"))
          .getPropertyValue("--query-norm")),
        lowerChunk0: document.querySelector("#lower-chunk-0").getBoundingClientRect().width,
        cssRuleCount: [...document.styleSheets].reduce((sum, sheet) => sum + sheet.cssRules.length, 0),
      },
    };
  });
}

async function readSyntheticChecks(page) {
  return page.evaluate(() => ({
    equalityCarrierWidth: document.querySelector("#equality-gate").getBoundingClientRect().width,
    equalityDescendantDisplay: getComputedStyle(
      document.querySelector("#equality-gate b"),
    ).display,
    belowCarrierWidth: document.querySelector("#below-gate").getBoundingClientRect().width,
    belowDescendantDisplay: getComputedStyle(document.querySelector("#below-gate b")).display,
    lowerTokenTieWinner: Number(
      getComputedStyle(document.querySelector("#tie-result")).getPropertyValue("--tie-local"),
    ),
  }));
}

async function benchmarkBalanced(context, diagnostics) {
  const pages = {
    gated: await loadPage(context, "benchmark-gated", diagnostics, "mode-gated"),
    full: await loadPage(context, "benchmark-full", diagnostics, "mode-full"),
  };
  for (const [mode, page] of Object.entries(pages)) {
    const selector = mode === "gated" ? "#gated-result" : "#full-result";
    await applyFixture(page, reference.fixtures.at(-1));
    await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
  }

  const results = {
    gated: { mode: "gated", samples: [], outputs: [] },
    full: { mode: "full", samples: [], outputs: [] },
  };
  const orderByRound = [];
  for (let round = 0; round < benchmarkRounds; round += 1) {
    const order = round % 2 === 0 ? ["gated", "full"] : ["full", "gated"];
    orderByRound.push(order);
    for (const mode of order) {
      const page = pages[mode];
      const resultSelector = mode === "gated" ? "#gated-result" : "#full-result";
      const winnerProperty = mode === "gated" ? "--gated-winner" : "--full-winner";
      for (const fixture of reference.fixtures) {
        const sample = await page.evaluate(({ fixture: values, resultSelector, winnerProperty }) => {
          const probe = document.querySelector("#probe");
          const started = performance.now();
          for (let dimension = 0; dimension < values.hidden.length; dimension += 1) {
            probe.style.setProperty(`--h${dimension}`, String(values.hidden[dimension]));
          }
          probe.style.setProperty("--score-offset", `${-values.scoreFloor * 256 * 4}px`);
          const result = document.querySelector(resultSelector);
          result.getBoundingClientRect().width;
          result.getBoundingClientRect().width;
          const style = getComputedStyle(result);
          return {
            milliseconds: performance.now() - started,
            winner: Number(style.getPropertyValue(winnerProperty)),
          };
        }, { fixture, resultSelector, winnerProperty });
        results[mode].samples.push(sample.milliseconds);
        results[mode].outputs.push({
          round,
          fixture: fixture.fixture,
          milliseconds: sample.milliseconds,
          winner: sample.winner,
        });
      }
    }
  }
  await Promise.all(Object.values(pages).map((page) => page.close()));
  return {
    order: "alternating ten-mutation mode batches by round",
    orderByRound,
    gated: {
      mode: "gated",
      rounds: benchmarkRounds,
      ...statistics(results.gated.samples),
      timingsMilliseconds: results.gated.samples,
      outputs: results.gated.outputs,
    },
    full: {
      mode: "full",
      rounds: benchmarkRounds,
      ...statistics(results.full.samples),
      timingsMilliseconds: results.full.samples,
      outputs: results.full.outputs,
    },
  };
}

const diagnostics = { pageErrors: [], requestFailures: [], httpErrors: [] };
const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const context = await browser.newContext({ viewport: { width: 800, height: 240 } });
  const correctnessPage = await loadPage(context, "correctness", diagnostics);
  const synthetic = await readSyntheticChecks(correctnessPage);
  const fixtures = [];
  for (const fixture of reference.fixtures) {
    await applyFixture(correctnessPage, fixture);
    await settleCorrectness(correctnessPage);
    const browserOutput = await readCorrectness(correctnessPage);
    const activeSetMatches = JSON.stringify(browserOutput.activeTokens)
      === JSON.stringify(fixture.activeTokens);
    const gatesAreBinary = browserOutput.carrierWidths.every((width) => width === 0 || width === 1);
    fixtures.push({
      fixture: fixture.fixture,
      expected: {
        activeTokens: fixture.activeTokens,
        lowerMaxBucket: fixture.lowerMaxBucket,
        exactWinner: fixture.exactWinner,
        exactWinnerBucket: fixture.exactWinnerBucket,
      },
      browser: browserOutput,
      checks: {
        activeSetMatches,
        gatesAreBinary,
        lowerMaxWithinCoarseAllowance:
          Math.abs(browserOutput.lowerMaxBucket - fixture.lowerMaxBucket)
          <= reference.bucketContract.coarseAllowanceBuckets,
        gatedMatchesFullWinner: browserOutput.gatedWinner === browserOutput.fullWinner,
        gatedMatchesFullBucket: browserOutput.gatedBucket === browserOutput.fullBucket,
        fullWinnerMatchesOracle: browserOutput.fullWinner === fixture.exactWinner,
        fullBucketWithinFineAllowance:
          Math.abs(browserOutput.fullBucket - fixture.exactWinnerBucket)
          <= reference.bucketContract.fineAllowanceBuckets,
      },
    });
  }
  await correctnessPage.close();

  const balancedBenchmark = await benchmarkBalanced(context, diagnostics);
  const gatedBenchmark = balancedBenchmark.gated;
  const fullBenchmark = balancedBenchmark.full;
  const benchmarkWinnersCorrect = [...gatedBenchmark.outputs, ...fullBenchmark.outputs].every(
    ({ fixture, winner }) => winner === reference.fixtures[fixture].exactWinner,
  );
  const syntheticChecks = {
    equalityStaysActive:
      synthetic.equalityCarrierWidth === 1
      && synthetic.equalityDescendantDisplay !== "none",
    strictBelowIsInactive:
      synthetic.belowCarrierWidth === 0
      && synthetic.belowDescendantDisplay === "none",
    equalBucketChoosesLowerToken: synthetic.lowerTokenTieWinner === 3,
  };
  const fixtureChecks = fixtures.flatMap(({ fixture, checks }) =>
    Object.entries(checks).map(([name, pass]) => ({ fixture, name, pass })));
  const allFixtureChecksPass = fixtureChecks.every(({ pass }) => pass);
  const noErrors = diagnostics.pageErrors.length === 0
    && diagnostics.requestFailures.length === 0
    && diagnostics.httpErrors.length === 0
    && serverErrors.length === 0;
  const semanticPass = allFixtureChecksPass
    && Object.values(syntheticChecks).every(Boolean)
    && benchmarkWinnersCorrect
    && noErrors;
  const robustlyBeatsFull = gatedBenchmark.medianMilliseconds < fullBenchmark.medianMilliseconds
    && gatedBenchmark.meanMilliseconds < fullBenchmark.meanMilliseconds
    && gatedBenchmark.p95Milliseconds < fullBenchmark.p95Milliseconds;
  report = {
    chrome: await browser.version(),
    url,
    fixtures: fixtures.length,
    topology: {
      group: reference.group,
      gateCarriers: reference.gateCarriers,
      exactGlyphsPerActiveToken: reference.exactGlyphsPerActiveToken,
      inactiveRowsUseDisplayNone: true,
    },
    synthetic,
    syntheticChecks,
    fixtureChecks,
    allFixtureChecksPass,
    benchmarkWinnersCorrect,
    scalingDecision: {
      decision: semanticPass && robustlyBeatsFull ? "retain" : "reject-scaling",
      robustlyBeatsFull,
      criterion: "gated median, mean, and p95 must each be lower than full",
    },
    benchmark: {
      order: balancedBenchmark.order,
      orderByRound: balancedBenchmark.orderByRound,
      gated: gatedBenchmark,
      full: fullBenchmark,
      medianFullOverGatedRatio:
        fullBenchmark.medianMilliseconds / gatedBenchmark.medianMilliseconds,
      meanFullOverGatedRatio:
        fullBenchmark.meanMilliseconds / gatedBenchmark.meanMilliseconds,
    },
    diagnostics: { ...diagnostics, serverErrors },
    noRequestOrPageErrors: noErrors,
    fixturesDetail: fixtures,
    pass: semanticPass,
  };
  await context.close();
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}

await fs.writeFile(
  path.join(experiment, "browser-results.json"),
  `${JSON.stringify(report, null, 2)}\n`,
);

const activeCounts = reference.fixtures.map(({ activeCount }) => activeCount);
const bucketDeltas = report.fixturesDetail.map(({ expected, browser: output }) =>
  output.fullBucket - expected.exactWinnerBucket);
const lowerDeltas = report.fixturesDetail.map(({ expected, browser: output }) =>
  output.lowerMaxBucket - expected.lowerMaxBucket);
const failedChecks = report.fixtureChecks.filter(({ pass }) => !pass);
const errorCount = report.diagnostics.pageErrors.length
  + report.diagnostics.requestFailures.length
  + report.diagnostics.httpErrors.length
  + report.diagnostics.serverErrors.length;
const resultSummary = report.pass
  ? `The fixed group-0 browser graph **passed** all ${report.fixtures} certified fixtures. Its 256 lightweight carriers activated only **${Math.min(...activeCounts)}–${Math.max(...activeCounts)} exact rows** (mean **${reference.offlineChecks.activeCountMean.toFixed(1)}**) out of 256, and every browser active set exactly matched the offline uncertainty oracle.`
  : `**REJECTED:** the fixed group-0 graph did not satisfy its browser contract. ${failedChecks.length} fixture checks failed, synthetic equality/tie checks were ${Object.values(report.syntheticChecks).every(Boolean) ? "complete" : "incomplete"}, benchmark winners were ${report.benchmarkWinnersCorrect ? "correct" : "incorrect"}, and ${errorCount} request/page/server errors were observed. See \`browser-results.json\` for the authoritative diagnostics.`;
const correctnessSummary = report.pass
  ? `The gate implements \`upper >= L\`, where \`L=max(lower)\`. A synthetic equality case remained active, a value strictly below \`L\` remained inactive, and equal rounded buckets selected the lower token ID. The browser's gated winner and rounded 1/256 bucket matched the normal full 256-row exact grid on **${report.fixtures}/${report.fixtures}** fixtures. Full-grid winners also matched the offline global-int16 oracle; browser bucket deltas were **${Math.min(...bucketDeltas)} to ${Math.max(...bucketDeltas)} buckets**, within the retained ${reference.bucketContract.fineAllowanceBuckets}-bucket fine allowance. Browser/offline \`L\` deltas were **${Math.min(...lowerDeltas).toFixed(3)} to ${Math.max(...lowerDeltas).toFixed(3)} buckets**, within the ${reference.bucketContract.coarseAllowanceBuckets}-bucket coarse allowance.`
  : `No positive correctness conclusion is claimed. Failed checks: ${failedChecks.length ? failedChecks.map(({ fixture, name }) => `fixture ${fixture} ${name}`).join(", ") : "none at fixture level"}.`;
const scalingSummary = report.scalingDecision.decision === "retain"
  ? "**Scaling decision: retain.** The gated page's median, mean, and p95 warm mutation costs all beat the full exact page."
  : "**Scaling decision: reject-scaling.** Semantics pass, but the gated page does not robustly beat the full exact page under the preregistered criterion that median, mean, and p95 must all be lower.";
const results = `# Fixed-group token uncertainty gate

## Result

${resultSummary}

${correctnessSummary}

${scalingSummary}

| Warm mutation metric | Gated | Full 256-row exact |
| --- | ---: | ---: |
| Samples | ${report.benchmark.gated.samples} | ${report.benchmark.full.samples} |
| Median | ${report.benchmark.gated.medianMilliseconds.toFixed(3)} ms | ${report.benchmark.full.medianMilliseconds.toFixed(3)} ms |
| Mean | ${report.benchmark.gated.meanMilliseconds.toFixed(3)} ms | ${report.benchmark.full.meanMilliseconds.toFixed(3)} ms |
| p95 | ${report.benchmark.gated.p95Milliseconds.toFixed(3)} ms | ${report.benchmark.full.p95Milliseconds.toFixed(3)} ms |

Median full/gated ratio: **${report.benchmark.medianFullOverGatedRatio.toFixed(2)}×**. Values below 1 mean the gated graph was slower. This is a local warm-mutation measurement of one fixed group, not a whole-vocabulary latency claim.

The screen used ${report.benchmark.gated.rounds} rounds / ${report.benchmark.gated.samples} mutations per mode. To balance page order, each round ran one ten-fixture mode batch and alternated whether gated or full ran first. Every individual timing and the exact per-round order are retained in \`browser-results.json\`.

## Contract

- Coarse interval: row-wise signed int10 center plus/minus \`l2(h) * l2(w16-w10)\`.
- Outward browser slack: ${reference.bucketContract.coarseAllowanceBuckets} coarse buckets plus ${reference.bucketContract.fineAllowanceBuckets} fine buckets.
- Exact scorer: the retained twelve-glyph global-int16 row and rounded-1/256/lower-token tie encoding.
- Scope: fixed group 0 only. No 197-group router or six-stage cascade is integrated.
- Browser: ${report.chrome}.
- Request failures, HTTP errors, page errors, and server errors: **${errorCount}**.

Raw measurements and every per-fixture active set are in \`browser-results.json\`; the offline oracle is in \`reference.json\`.

## Reproduce

\`\`\`sh
PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_token_uncertainty_gate_probe.py
node tools/test_token_uncertainty_gate_probe.mjs
\`\`\`
`;
await fs.writeFile(path.join(experiment, "RESULTS.md"), results);

console.log(JSON.stringify({
  pass: report.pass,
  chrome: report.chrome,
  allFixtureChecksPass: report.allFixtureChecksPass,
  syntheticChecks: report.syntheticChecks,
  benchmarkWinnersCorrect: report.benchmarkWinnersCorrect,
  scalingDecision: report.scalingDecision,
  noRequestOrPageErrors: report.noRequestOrPageErrors,
  activeCounts: {
    minimum: Math.min(...activeCounts),
    maximum: Math.max(...activeCounts),
    mean: reference.offlineChecks.activeCountMean,
  },
  benchmark: report.benchmark,
}, null, 2));

if (!report.pass) process.exitCode = 1;
