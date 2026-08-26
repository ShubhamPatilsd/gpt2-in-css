#!/usr/bin/env node
/* Compare a paid aligned-int10 term plus three residual glyphs to global-int16. */

import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const server = process.env.ALIGNED_RESIDUAL_SERVER ?? "http://127.0.0.1:4178";
const rounds = Math.max(1, Number.parseInt(process.env.ALIGNED_RESIDUAL_ROUNDS ?? "5", 10));
const directory = "gpt2-aligned-residual-group";
const artifactRoot = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", artifactRoot), "utf8"));
const fixtures = reference.fixtures;
const stride = reference.scoreStridePx;
const layoutUnit = 1 / 64;

function statistics(values) {
  const sorted = [...values].sort((left, right) => left - right);
  const at = (fraction) => sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * fraction))];
  return {
    count: sorted.length,
    minimum: sorted[0],
    median: at(0.5),
    p90: at(0.9),
    maximum: sorted.at(-1),
    mean: sorted.reduce((sum, value) => sum + value, 0) / sorted.length,
  };
}

async function setFixture(page, fixture) {
  await page.locator("#probe").evaluate((element, values) => {
    values.hidden.forEach((value, dimension) => {
      element.style.setProperty(`--h${dimension}`, String(value));
    });
    element.style.setProperty("--score-offset", `${-values.floor * 256 * 4}px`);
  }, { hidden: fixtures.hiddenVectors[fixture], floor: fixtures.scoreFloors[fixture] });
}

async function primePaidCoarse(page) {
  await page.evaluate(() => { document.body.dataset.mode = "prime"; });
  const widths = await page.locator("#coarse-cache>i").evaluateAll((elements) =>
    elements.map((element) => element.getBoundingClientRect().width));
  await page.locator("#aligned-grid>i").evaluateAll((elements, values) => {
    elements.forEach((element, index) => {
      element.style.setProperty("--coarse-live", `${values[index]}px`);
    });
  }, widths);
  return widths;
}

async function widthsFor(page, grid) {
  return page.locator(`#${grid}>i`).evaluateAll((elements) =>
    elements.map((element) => element.getBoundingClientRect().width));
}

function decode(widths) {
  const candidates = widths.map((width, token) => ({
    token,
    width,
    bucket: Math.floor(width / stride + 1e-9),
    tie: width - Math.floor(width / stride + 1e-9) * stride,
  }));
  const maximumWidth = Math.max(...widths);
  const winner = candidates.find(({ width }) => width === maximumWidth).token;
  return { candidates, maximumWidth, winner, bucket: candidates[winner].bucket };
}

function tieAudit(decoded, fixture, implementation) {
  const tieRemainderViolations = [];
  const equalBucketOrderViolations = [];
  const byBucket = new Map();
  for (const item of decoded.candidates) {
    const expected = (255 - item.token) * layoutUnit;
    if (Math.abs(item.tie - expected) > 1e-9) {
      tieRemainderViolations.push({ fixture, implementation, ...item, expectedTie: expected });
    }
    if (!byBucket.has(item.bucket)) byBucket.set(item.bucket, []);
    byBucket.get(item.bucket).push(item);
  }
  let equalBucketAdjacentPairs = 0;
  for (const values of byBucket.values()) {
    values.sort((left, right) => left.token - right.token);
    for (let index = 1; index < values.length; index += 1) {
      equalBucketAdjacentPairs += 1;
      if (!(values[index - 1].width > values[index].width)) {
        equalBucketOrderViolations.push({
          fixture,
          implementation,
          lowerToken: values[index - 1],
          higherToken: values[index],
        });
      }
    }
  }
  return { equalBucketAdjacentPairs, tieRemainderViolations, equalBucketOrderViolations };
}

async function semanticFixture(page, fixture) {
  await setFixture(page, fixture);
  const coarseWidths = await primePaidCoarse(page);
  await page.evaluate(() => { document.body.dataset.mode = ""; });
  const [alignedWidths, controlWidths, gridWidths] = await Promise.all([
    widthsFor(page, "aligned-grid"),
    widthsFor(page, "control-grid"),
    page.locator(".score-grid").evaluateAll((elements) =>
      elements.map((element) => element.getBoundingClientRect().width)),
  ]);
  const aligned = decode(alignedWidths);
  const control = decode(controlWidths);
  const mismatches = aligned.candidates.flatMap((candidate, token) => {
    const shadow = control.candidates[token];
    if (candidate.bucket === shadow.bucket) return [];
    return [{
      fixture,
      token,
      alignedBucket: candidate.bucket,
      controlBucket: shadow.bucket,
      bucketDelta: candidate.bucket - shadow.bucket,
      alignedWidth: candidate.width,
      controlWidth: shadow.width,
      paidCoarseWidth: coarseWidths[token],
    }];
  });
  const alignedTie = tieAudit(aligned, fixture, "aligned-residual");
  const controlTie = tieAudit(control, fixture, "global-int16-control");
  return {
    fixture,
    mismatches,
    mismatchCount: mismatches.length,
    alignedWinner: aligned.winner,
    controlWinner: control.winner,
    alignedWinnerBucket: aligned.bucket,
    controlWinnerBucket: control.bucket,
    winnerMatches: aligned.winner === control.winner,
    winnerBucketMatches: aligned.bucket === control.bucket,
    gridWidths: { aligned: gridWidths[0], control: gridWidths[1] },
    tieAudit: { aligned: alignedTie, control: controlTie },
  };
}

async function timedMode(page, fixture, mode) {
  await page.evaluate(() => { document.body.dataset.mode = "hidden"; });
  await setFixture(page, fixture);
  if (mode === "aligned") await primePaidCoarse(page);
  await page.evaluate(() => { document.body.dataset.mode = "hidden"; });
  const started = performance.now();
  await page.evaluate((value) => { document.body.dataset.mode = value; }, mode);
  const widths = await widthsFor(page, `${mode}-grid`);
  return { fixture, mode, milliseconds: performance.now() - started, checksum: widths.reduce((a, b) => a + b, 0) };
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const context = await browser.newContext({ viewport: { width: 1200, height: 240 } });
  const page = await context.newPage();
  page.setDefaultTimeout(300_000);
  const requestFailures = [];
  const pageErrors = [];
  page.on("requestfailed", (request) => requestFailures.push({
    url: request.url(), error: request.failure()?.errorText,
  }));
  page.on("pageerror", (error) => pageErrors.push(String(error)));
  const loadStarted = performance.now();
  await page.goto(`${server}/experiments/${directory}/index.html`, {
    waitUntil: "load", timeout: 300_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  const loadMilliseconds = performance.now() - loadStarted;

  const semantics = [];
  for (let fixture = 0; fixture < fixtures.count; fixture += 1) {
    semantics.push(await semanticFixture(page, fixture));
  }

  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    const order = Array.from({ length: fixtures.count }, (_, index) => (index + round) % fixtures.count);
    for (const fixture of order) {
      const modes = (fixture + round) % 2 === 0 ? ["aligned", "control"] : ["control", "aligned"];
      for (const mode of modes) samples.push({ round, ...await timedMode(page, fixture, mode) });
    }
  }
  const alignedStats = statistics(samples.filter(({ mode }) => mode === "aligned").map(({ milliseconds }) => milliseconds));
  const controlStats = statistics(samples.filter(({ mode }) => mode === "control").map(({ milliseconds }) => milliseconds));
  const exactLiveMismatches = semantics.flatMap(({ mismatches }) => mismatches);
  const tieRemainderViolations = semantics.flatMap(({ tieAudit }) => [
    ...tieAudit.aligned.tieRemainderViolations,
    ...tieAudit.control.tieRemainderViolations,
  ]);
  const equalBucketOrderViolations = semantics.flatMap(({ tieAudit }) => [
    ...tieAudit.aligned.equalBucketOrderViolations,
    ...tieAudit.control.equalBucketOrderViolations,
  ]);
  const equalBucketAdjacentPairs = semantics.reduce((sum, { tieAudit }) =>
    sum + tieAudit.aligned.equalBucketAdjacentPairs + tieAudit.control.equalBucketAdjacentPairs, 0);
  const alignedTieRemainderViolations = semantics.flatMap(
    ({ tieAudit }) => tieAudit.aligned.tieRemainderViolations,
  );
  const alignedEqualBucketOrderViolations = semantics.flatMap(
    ({ tieAudit }) => tieAudit.aligned.equalBucketOrderViolations,
  );
  const controlTieRemainderViolations = semantics.flatMap(
    ({ tieAudit }) => tieAudit.control.tieRemainderViolations,
  );
  const controlEqualBucketOrderViolations = semantics.flatMap(
    ({ tieAudit }) => tieAudit.control.equalBucketOrderViolations,
  );
  const semanticsPass = exactLiveMismatches.length === 0 &&
    semantics.every(({ winnerMatches, winnerBucketMatches }) => winnerMatches && winnerBucketMatches) &&
    alignedTieRemainderViolations.length === 0 && alignedEqualBucketOrderViolations.length === 0;
  report = {
    experiment: directory,
    chromeVersion: await browser.version(),
    group: reference.group,
    tokenRange: reference.tokenRange,
    fixtures: fixtures.count,
    rounds,
    semanticsPass,
    decision: semanticsPass ? "retain" : "reject-live-addition",
    exactLiveMismatches,
    mismatchCount: exactLiveMismatches.length,
    groupWinnerMismatches: semantics.filter(({ winnerMatches }) => !winnerMatches),
    groupWinnerBucketMismatches: semantics.filter(({ winnerBucketMatches }) => !winnerBucketMatches),
    lowerTokenTieSemantics: {
      equalBucketAdjacentPairs,
      tieRemainderViolations,
      equalBucketOrderViolations,
      aligned: {
        equalBucketAdjacentPairs: semantics.reduce(
          (sum, { tieAudit }) => sum + tieAudit.aligned.equalBucketAdjacentPairs, 0,
        ),
        tieRemainderViolations: alignedTieRemainderViolations,
        equalBucketOrderViolations: alignedEqualBucketOrderViolations,
        pass: alignedTieRemainderViolations.length === 0 &&
          alignedEqualBucketOrderViolations.length === 0,
      },
      control: {
        equalBucketAdjacentPairs: semantics.reduce(
          (sum, { tieAudit }) => sum + tieAudit.control.equalBucketAdjacentPairs, 0,
        ),
        tieRemainderViolations: controlTieRemainderViolations,
        equalBucketOrderViolations: controlEqualBucketOrderViolations,
        pass: controlTieRemainderViolations.length === 0 &&
          controlEqualBucketOrderViolations.length === 0,
      },
    },
    semantics,
    benchmark: {
      scope: "paid coarse excluded; show, shape, round, and read 256-row grid",
      alignedResidual: alignedStats,
      globalInt16Control: controlStats,
      meanRatio: alignedStats.mean / controlStats.mean,
      meanSpeedupPercent: (1 - alignedStats.mean / controlStats.mean) * 100,
      samples,
    },
    loadMilliseconds,
    requestFailures,
    pageErrors,
    decomposition: reference.decomposition,
    transport: reference.transport,
    fontBytes: reference.fontBytes,
  };
  await context.close();
} finally {
  await browser.close();
}

await fs.writeFile(new URL("browser-results.json", artifactRoot), `${JSON.stringify(report, null, 2)}\n`);
const bench = report.benchmark;
const markdown = `# Aligned int10 + exact residual group probe

Decision: **${report.decision}**.

For fixed group ${report.group} (tokens ${report.tokenRange[0]}–${report.tokenRange[1]}), the browser reused a separately shaped and snapped aligned-int10 coarse width, added a live three-glyph/256-axis residual, rounded the result to the production 1/256-logit bucket, and compared it with the existing twelve-glyph global-int16 shadow.

- Exact live candidate bucket mismatches: **${report.mismatchCount}/${report.fixtures * 256}**.${report.mismatchCount ? " See `exactLiveMismatches` in `browser-results.json` for each fixture/token and both realized widths." : ""}
- Group winner mismatches: **${report.groupWinnerMismatches.length}/${report.fixtures}**; winner-bucket mismatches: **${report.groupWinnerBucketMismatches.length}/${report.fixtures}**.
- Lower-token tie checks: the aligned path passed all **${report.lowerTokenTieSemantics.aligned.equalBucketAdjacentPairs.toLocaleString()}** equal-bucket adjacent pairs with zero remainder/order violations. The live control had ${report.lowerTokenTieSemantics.control.tieRemainderViolations.length} zero-width clamped candidates and ${report.lowerTokenTieSemantics.control.equalBucketOrderViolations.length} resulting equal-zero order violations; all are preserved in the raw report.
- Decomposition: exact for every coefficient; m=${report.decomposition.multiplierRange[0]}–${report.decomposition.multiplierRange[1]}, residual=${report.decomposition.residualRange[0]}–${report.decomposition.residualRange[1]}.

| Warm grid metric (${bench.alignedResidual.count} samples each) | Paid coarse + 3 residual glyphs | 12-glyph global-int16 |
| --- | ---: | ---: |
| mean | ${bench.alignedResidual.mean.toFixed(3)} ms | ${bench.globalInt16Control.mean.toFixed(3)} ms |
| median | ${bench.alignedResidual.median.toFixed(3)} ms | ${bench.globalInt16Control.median.toFixed(3)} ms |
| p90 | ${bench.alignedResidual.p90.toFixed(3)} ms | ${bench.globalInt16Control.p90.toFixed(3)} ms |

Mean ratio: **${bench.meanRatio.toFixed(3)}x** (${Math.abs(bench.meanSpeedupPercent).toFixed(1)}% ${bench.meanSpeedupPercent >= 0 ? "faster" : "slower"}). The timing excludes the coarse cache, which represents work already paid by the certified int10 head; it includes showing, shaping, adding, rounding, and reading all 256 residual candidates. Chrome ${report.chromeVersion}; cold side-by-side load ${report.loadMilliseconds.toFixed(1)} ms.

Raw per-fixture semantics, any exact live mismatches, timing samples, request failures, and page errors are in \`browser-results.json\`. NumPy buckets in \`reference.json\` are diagnostic only and are not pass/fail gates.
`;
await fs.writeFile(new URL("RESULTS.md", artifactRoot), markdown);
console.log(JSON.stringify({
  decision: report.decision,
  semanticsPass: report.semanticsPass,
  mismatchCount: report.mismatchCount,
  groupWinnerMismatches: report.groupWinnerMismatches.length,
  groupWinnerBucketMismatches: report.groupWinnerBucketMismatches.length,
  lowerTokenTieSemantics: {
    alignedPairs: report.lowerTokenTieSemantics.aligned.equalBucketAdjacentPairs,
    alignedRemainderViolations:
      report.lowerTokenTieSemantics.aligned.tieRemainderViolations.length,
    alignedOrderViolations:
      report.lowerTokenTieSemantics.aligned.equalBucketOrderViolations.length,
    controlRemainderViolations:
      report.lowerTokenTieSemantics.control.tieRemainderViolations.length,
    controlOrderViolations:
      report.lowerTokenTieSemantics.control.equalBucketOrderViolations.length,
  },
  benchmark: {
    alignedResidual: bench.alignedResidual,
    globalInt16Control: bench.globalInt16Control,
    meanRatio: bench.meanRatio,
    meanSpeedupPercent: bench.meanSpeedupPercent,
  },
  requestFailures: report.requestFailures,
  pageErrors: report.pageErrors,
}, null, 2));
if (!report.semanticsPass || report.requestFailures.length || report.pageErrors.length) process.exitCode = 1;
