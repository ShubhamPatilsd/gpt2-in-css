import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const workspace = path.resolve(new URL("..", import.meta.url).pathname);
const experiment = path.join(workspace, "experiments/gpt2-groupwise-cauchy-blockflow-gate");
const reference = JSON.parse(await fs.readFile(path.join(experiment, "reference.json"), "utf8"));
const tolerance = 0.03;

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function mean(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function close(actual, expected) {
  return Math.abs(actual - expected) <= tolerance;
}

const types = new Map([[".html", "text/html"], [".css", "text/css"], [".woff2", "font/woff2"]]);
const server = http.createServer(async (request, response) => {
  try {
    const filename = path.join(workspace, decodeURIComponent(new URL(request.url, "http://x").pathname));
    if (!filename.startsWith(`${workspace}${path.sep}`)) throw new Error("outside workspace");
    const body = await fs.readFile(filename);
    response.writeHead(200, { "content-type": types.get(path.extname(filename)) ?? "application/octet-stream" });
    response.end(body);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const baseUrl = `http://127.0.0.1:${server.address().port}`;

async function applyFixture(page, fixtureIndex) {
  const fixture = reference.fixtures[fixtureIndex];
  return page.locator("#model").evaluate((model, payload) => {
    const started = performance.now();
    payload.hidden.forEach((value, dimension) => model.style.setProperty(`--h${dimension}`, String(value)));
    model.style.setProperty("--score-offset", `${-payload.floor * 256 * 4}px`);
    const groups = [...document.querySelectorAll(".group-wrapper")].map((node) => node.getBoundingClientRect().width);
    const bounds = [...document.querySelectorAll(".group-bound")].map((node) => node.getBoundingClientRect().width);
    const chunk = document.querySelector("#chunk-max").getBoundingClientRect().width;
    const outer = document.querySelector("#outer-max").getBoundingClientRect().width;
    const modelStyle = getComputedStyle(model);
    const boundStyle = document.querySelector(".group-bound")
      ? getComputedStyle(document.querySelector(".group-bound")) : null;
    const variation = boundStyle?.fontVariationSettings ?? "normal";
    return {
      milliseconds: performance.now() - started,
      groups,
      bounds,
      chunk,
      outer,
      blockNorms: Array.from({ length: 96 }, (_, index) => Number(modelStyle.getPropertyValue(`--bn${index}`))),
      variation,
      axisCount: (variation.match(/"/g) ?? []).length / 2,
      candidates: document.querySelectorAll(".candidate").length,
      scripts: document.querySelectorAll("script").length,
    };
  }, { hidden: fixture.hidden, floor: fixture.scoreFloor });
}

const browser = await chromium.launch({ executablePath, headless: true });
const report = { scope: reference.decisionScope, chrome: await browser.version(), correctness: [], timing: null };
try {
  const context = await browser.newContext({ viewport: { width: 320, height: 120 } });
  const pages = {};
  for (const kind of ["control", "candidate"]) {
    const page = await context.newPage();
    await page.goto(`${baseUrl}/experiments/gpt2-groupwise-cauchy-blockflow-gate/${kind}.html`, {
      waitUntil: "domcontentloaded", timeout: 90_000,
    });
    await page.waitForFunction(() => document.fonts.status === "loaded", null, { timeout: 90_000 });
    pages[kind] = page;
  }

  for (let index = 0; index < reference.fixtures.length; index += 1) {
    const fixture = reference.fixtures[index];
    const control = await applyFixture(pages.control, index);
    const candidate = await applyFixture(pages.candidate, index);
    const compositionOracle = control.groups.map(
      (width, group) => width + fixture.boundWidths[group],
    );
    const oracleMaximum = Math.max(...compositionOracle);
    // indexOf makes an exact tie deterministic in favor of the lower group.
    const expectedSelected = compositionOracle.indexOf(oracleMaximum);
    const measuredSelected = candidate.groups.indexOf(Math.max(...candidate.groups));
    const boundDeltas = candidate.bounds.map(
      (value, group) => value - fixture.boundWidths[group],
    );
    const exactBoundPredictions = boundDeltas.filter((delta) => Math.abs(delta) <= tolerance).length;
    const oneBucketBoundPredictions = boundDeltas.filter(
      (delta) => Math.abs(delta) > tolerance
        && Math.abs(delta) <= reference.boundPredictionTolerancePx + tolerance,
    ).length;
    const boundGeometry = boundDeltas.every(
      (delta) => Math.abs(delta) <= reference.boundPredictionTolerancePx + tolerance,
    );
    const outwardSafe = candidate.bounds.every(
      (value, group) => value + tolerance >= fixture.certifiedRadiusPixels[group],
    );
    const totalGeometry = candidate.groups.every(
      (value, group) => Math.abs(value - compositionOracle[group])
        <= reference.boundPredictionTolerancePx + tolerance,
    );
    const componentSumGeometry = candidate.groups.every(
      (value, group) => close(value, control.groups[group] + candidate.bounds[group]),
    );
    const coarseGeometry = control.groups.every((value, group) => close(value, fixture.coarseWidths[group]));
    const reducerCorrect = close(candidate.chunk, Math.max(...candidate.groups))
      && close(candidate.outer, candidate.chunk)
      && Math.abs(candidate.outer - oracleMaximum)
        <= reference.boundPredictionTolerancePx + tolerance;
    report.correctness.push({
      fixture: fixture.name,
      expectedSelectedGroup: expectedSelected,
      measuredSelectedGroup: measuredSelected,
      numpySelectedGroupDiagnostic: fixture.selectedGroup,
      topBucketGap: fixture.topBucketGap,
      topTieCount: fixture.topTieCount,
      coarseGeometry,
      boundGeometry,
      boundPredictionCounts: {
        exact: exactBoundPredictions,
        withinOneBucket: oneBucketBoundPredictions,
        beyondOneBucket: candidate.bounds.length
          - exactBoundPredictions - oneBucketBoundPredictions,
      },
      outwardSafe,
      totalGeometry,
      componentSumGeometry,
      reducerCorrect,
      candidateAxisCount: candidate.axisCount,
      scripts: candidate.scripts,
      representativeCoarseWidths: [0, 1, 2, 15].map((group) => ({
        group,
        measured: control.groups[group],
        expected: fixture.coarseWidths[group],
        delta: control.groups[group] - fixture.coarseWidths[group],
      })),
      representativeBoundWidths: [0, 1, 2, 15].map((group) => ({
        group,
        measured: candidate.bounds[group],
        expected: fixture.boundWidths[group],
        delta: candidate.bounds[group] - fixture.boundWidths[group],
      })),
      boundWidthMismatches: candidate.bounds.flatMap((value, group) => (
        close(value, fixture.boundWidths[group]) ? [] : [{
          group,
          measured: value,
          expected: fixture.boundWidths[group],
          delta: value - fixture.boundWidths[group],
          carrierPixels: fixture.carrierPixels[group],
        }]
      )),
      pass: measuredSelected === expectedSelected && boundGeometry
        && outwardSafe && totalGeometry && componentSumGeometry && reducerCorrect
        && candidate.axisCount === 96
        && candidate.candidates === reference.candidateRows && candidate.scripts === 0,
    });
  }

  const [axisBeforeIndex, axisAfterIndex] = reference.axisLivePair;
  const axisBefore = await applyFixture(pages.candidate, axisBeforeIndex);
  const axisAfter = await applyFixture(pages.candidate, axisAfterIndex);
  const parseAxes = (text) => new Map([...text.matchAll(/"(b\d{3})"\s+([\d.eE+-]+)/g)]
    .map((match) => [match[1], Number(match[2])]));
  const beforeAxes = parseAxes(axisBefore.variation);
  const afterAxes = parseAxes(axisAfter.variation);
  report.axisLiveness = {
    changedBlockNorms: axisBefore.blockNorms.reduce(
      (count, value, index) => count + Number(value !== axisAfter.blockNorms[index]), 0,
    ),
    changedFontAxes: Array.from({ length: 96 }, (_, index) => `b${String(index).padStart(3, "0")}`)
      .reduce((count, tag) => count + Number(beforeAxes.get(tag) !== afterAxes.get(tag)), 0),
    changedBoundGlyphs: axisBefore.bounds.reduce(
      (count, value, index) => count + Number(!close(value, axisAfter.bounds[index])), 0,
    ),
  };

  // A second load establishes that the artifact is functional with page JavaScript disabled.
  const noJs = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 320, height: 120 } });
  const noJsPage = await noJs.newPage();
  await noJsPage.goto(`${baseUrl}/experiments/gpt2-groupwise-cauchy-blockflow-gate/candidate.html`, {
    waitUntil: "domcontentloaded", timeout: 90_000,
  });
  report.javaScriptDisabled = await noJsPage.locator("#outer-max").count() === 1
    && await noJsPage.locator("script").count() === 0;
  await noJs.close();

  report.distinctOracleWinners = new Set(
    report.correctness.map((row) => row.expectedSelectedGroup),
  ).size;
  report.boundPredictionCounts = report.correctness.reduce(
    (total, row) => ({
      exact: total.exact + row.boundPredictionCounts.exact,
      withinOneBucket: total.withinOneBucket + row.boundPredictionCounts.withinOneBucket,
      beyondOneBucket: total.beyondOneBucket + row.boundPredictionCounts.beyondOneBucket,
    }),
    { exact: 0, withinOneBucket: 0, beyondOneBucket: 0 },
  );
  report.correctnessPass = report.correctness.every((row) => row.pass)
    && report.axisLiveness.changedBlockNorms === 96
    && report.axisLiveness.changedFontAxes === 96
    && report.axisLiveness.changedBoundGlyphs === reference.groupCount
    && report.distinctOracleWinners >= 3
    && report.javaScriptDisabled;
  if (report.correctnessPass) {
    const times = { control: [], candidate: [] };
    for (let iteration = 0; iteration < reference.timing.iterations; iteration += 1) {
      const target = (iteration + 1) % (reference.fixtures.length - 1);
      const reset = iteration % (reference.fixtures.length - 1);
      const order = iteration % 2 ? ["candidate", "control"] : ["control", "candidate"];
      for (const kind of order) {
        await applyFixture(pages[kind], reset);
        const measured = await applyFixture(pages[kind], target);
        times[kind].push(measured.milliseconds);
      }
    }
    const controlMean = mean(times.control);
    const candidateMean = mean(times.candidate);
    const controlMedian = median(times.control);
    const candidateMedian = median(times.candidate);
    const decisivePenalty = candidateMean >= controlMean * 1.5
      && candidateMedian >= controlMedian * 1.5
      && candidateMean - controlMean >= 50
      && candidateMedian - controlMedian >= 50;
    report.timing = {
      samplesMilliseconds: times,
      controlMean, candidateMean, controlMedian, candidateMedian,
      meanRatio: candidateMean / controlMean,
      medianRatio: candidateMedian / controlMedian,
      decisivePenalty,
    };
  }
  report.decision = !report.correctnessPass
    ? "reject-composition-prefix"
    : report.timing.decisivePenalty
      ? "reject-decisive-loaded-mutation-penalty"
      : "pass-narrow-composition-gate";
  await fs.writeFile(path.join(experiment, "browser-results.json"), `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
  if (report.decision !== "pass-narrow-composition-gate") process.exitCode = 1;
  await context.close();
} finally {
  await browser.close();
  server.close();
}
