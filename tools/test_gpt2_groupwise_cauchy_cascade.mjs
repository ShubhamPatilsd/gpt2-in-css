#!/usr/bin/env node
/* Verify and time the smallest integrated groupwise-Cauchy cascade gate. */

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
const experiment = path.join(workspace, "experiments/gpt2-groupwise-cauchy-cascade");
const reference = JSON.parse(await fs.readFile(path.join(experiment, "reference.json"), "utf8"));
const stages = reference.prefixStages;
const representativeFixtures = [0, 6, 1]; // one-, two-, and three-stage stops
const rounds = Number(process.env.GROUPWISE_CASCADE_ROUNDS ?? 2);
const retainedProfile = {
  directory: "gpt2-mixed-hot2-blockflow-group-max-shard256",
  loadedMedianMilliseconds: 2709.1,
  coldLoadMilliseconds: 56693.5,
  source: "RESULTS.md broad paired screen",
};
const globalCascadeProfile = {
  directory: "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated",
  loadedMedianMilliseconds: 4806,
  coldLoadAndFirstMilliseconds: 49100,
  source: "RESULTS.md ten-fixture screen",
};

if (process.env.GROUPWISE_CASCADE_RECLASSIFY === "1") {
  const resultPath = path.join(experiment, "browser-results.json");
  const existing = JSON.parse(await fs.readFile(resultPath, "utf8"));
  const outwardBucket = (value) => Math.floor((value + 4) / 4) * 4;
  let exact = 0;
  let outwardOneBucket = 0;
  let unsafe = 0;
  for (const sample of existing.samples) {
    const expected = reference.fixtures.browserGroupRadiusPixels[sample.fixture].slice(0, 8);
    expected.forEach((value, index) => {
      const delta = sample.output.boundWidths[index] - outwardBucket(value);
      if (Math.abs(delta) < 0.02) exact += 1;
      else if (Math.abs(delta - 4) < 0.02) outwardOneBucket += 1;
      else unsafe += 1;
    });
  }
  existing.decision = "reject-integrated-topology-correctness";
  existing.timingInterpretation = {
    diagnosticOnly: true,
    optimisticLowerBound: false,
    reason: (
      "the failed router left all three exact stages active; a correct one- or "
      + "two-stage stop could reduce mutation cost"
    ),
    retainedShard256TestedInThisRun: false,
    sourceTopology: "older certified-upper-int10 one-step scroll-timeline reducer",
  };
  existing.groupBoundGeometry = {
    ...existing.groupBoundGeometry,
    measuredWidthsMatchPredictedOutwardBuckets: outwardOneBucket === 0 && unsafe === 0,
    exactPredictedWidths: exact,
    oneBucketOutwardWidths: outwardOneBucket,
    unsafeWidths: unsafe,
    allMeasuredWidthsOutwardSafeAndWithinOneBucket: unsafe === 0,
    interpretation: (
      "all 96 axes and glyph geometry are live; one F2DOT14 boundary crossing "
      + "rounded one additional 4px bucket outward and is conservative"
    ),
  };
  await fs.writeFile(resultPath, `${JSON.stringify(existing, null, 2)}\n`);
  console.log(JSON.stringify({
    decision: existing.decision,
    timingInterpretation: existing.timingInterpretation,
    groupBoundGeometry: existing.groupBoundGeometry,
  }, null, 2));
  process.exit(0);
}

function median(values) {
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2
    ? ordered[middle]
    : (ordered[middle - 1] + ordered[middle]) / 2;
}

function statistics(values) {
  return {
    count: values.length,
    minimum: Math.min(...values),
    median: median(values),
    maximum: Math.max(...values),
    mean: values.reduce((sum, value) => sum + value, 0) / values.length,
  };
}

function fixtureStyle(fixture) {
  const properties = reference.fixtures.hiddenVectors[fixture]
    .map((value, dimension) => `--h${dimension}:${value}`);
  properties.push(
    `--score-offset:${-reference.fixtures.scoreFloors[fixture] * 256 * 4}px`,
  );
  return properties.join(";");
}

async function setInput(page, fixture) {
  await page.evaluate((style) => {
    for (const element of [document.querySelector(".cascade"), document.querySelector("#model")]) {
      element.style.cssText = style;
    }
  }, fixtureStyle(fixture));
}

async function settle(page) {
  for (let pass = 0; pass < 3; pass += 1) {
    for (const selector of ["#result", "#fine-stage", "#fine-result"]) {
      await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
    }
    for (let stage = 1; stage <= stages; stage += 1) {
      const remaining = page.locator(`#remaining-result-${stage}`);
      await remaining.evaluate((element) => element.getBoundingClientRect().width);
      const done = await remaining.evaluate(
        (element, property) => Number(getComputedStyle(element).getPropertyValue(property)),
        `--done-${stage - 1}`,
      );
      if (done === 1) break;
      if (stage < stages) {
        for (const selector of [`#fine-stage-${stage}`, `#fine-result-${stage}`]) {
          await page.locator(selector).evaluate(
            (element) => element.getBoundingClientRect().width,
          );
        }
      }
    }
  }
}

async function observe(page) {
  return page.evaluate((stageCount) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    const coarse = getComputedStyle(document.querySelector("#result"));
    const groups = [number(coarse, "--group")];
    const fineWinners = [];
    const bestWinners = [];
    const done = [];
    const gaps = [];
    for (let stage = 0; stage < stageCount; stage += 1) {
      const fine = getComputedStyle(document.querySelector(
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
      ));
      fineWinners.push(number(
        fine,
        stage === 0 ? "--refined-winner" : `--fine-winner-${stage}`,
      ));
      bestWinners.push(number(fine, `--best-winner-${stage}`));
      const remaining = getComputedStyle(
        document.querySelector(`#remaining-result-${stage + 1}`),
      );
      done.push(number(remaining, `--done-${stage}`));
      gaps.push(number(remaining, `--certificate-gap-${stage}`));
      if (done.at(-1) === 1) break;
      if (stage + 1 < stageCount) {
        groups.push(number(remaining, `--remaining-group-${stage + 1}`));
      }
    }
    const bound = document.querySelector(".group-bound");
    const boundStyle = getComputedStyle(bound);
    return {
      groups,
      fineWinners,
      bestWinners,
      done,
      gaps,
      finalWinner: bestWinners.at(-1),
      fallbackRequired: done.at(-1) === 1 ? 0 : 1,
      boundWidths: [...document.querySelectorAll(".group-bound")]
        .slice(0, 8).map((element) => element.getBoundingClientRect().width),
      boundVariation: boundStyle.fontVariationSettings,
      boundAxisCount: (boundStyle.fontVariationSettings.match(/"/g) ?? []).length / 2,
    };
  }, stages);
}

async function evaluateFixture(page, fixture) {
  const started = performance.now();
  await setInput(page, fixture);
  await settle(page);
  const output = await observe(page);
  return { fixture, milliseconds: performance.now() - started, output };
}

const types = new Map([
  [".html", "text/html"], [".css", "text/css"], [".woff2", "font/woff2"],
]);
const server = http.createServer(async (request, response) => {
  try {
    const filename = path.join(
      workspace,
      decodeURIComponent(new URL(request.url, "http://x").pathname),
    );
    if (!filename.startsWith(`${workspace}${path.sep}`)) throw new Error("outside workspace");
    const body = await fs.readFile(filename);
    response.writeHead(200, {
      "content-type": types.get(path.extname(filename)) ?? "application/octet-stream",
      "cache-control": "no-store",
    });
    response.end(body);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const baseUrl = `http://127.0.0.1:${server.address().port}`;

const diagnostics = { pageErrors: [], requestFailures: [], httpErrors: [] };
const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 800, height: 200 },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(120_000);
  page.on("pageerror", (error) => diagnostics.pageErrors.push(String(error)));
  page.on("requestfailed", (request) => diagnostics.requestFailures.push({
    url: request.url(), error: request.failure()?.errorText ?? "unknown",
  }));
  page.on("response", (response) => {
    if (response.status() >= 400 && !response.url().endsWith("favicon.ico")) {
      diagnostics.httpErrors.push({ url: response.url(), status: response.status() });
    }
  });
  const loadStarted = performance.now();
  await page.goto(
    `${baseUrl}/experiments/gpt2-groupwise-cauchy-cascade/index.html`,
    { waitUntil: "load", timeout: 120_000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const loadMilliseconds = performance.now() - loadStarted;
  const cold = await evaluateFixture(page, 0);
  await evaluateFixture(page, 1);

  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    const order = round % 2 === 0
      ? representativeFixtures
      : [...representativeFixtures].reverse();
    for (const fixture of order) samples.push({ round, ...(await evaluateFixture(page, fixture)) });
  }
  const checks = samples.map((sample) => {
    const fixture = sample.fixture;
    const active = sample.output.groups.length;
    const expectedDone = reference.fixtures.firstDoneZeroBased[fixture];
    const check = {
      fixture,
      routeMatches: sample.output.groups.every(
        (value, index) => value === reference.fixtures.stageGroups[fixture][index],
      ),
      fineWinnersMatch: sample.output.fineWinners.every(
        (value, index) => value === reference.fixtures.stageFineWinners[fixture][index],
      ),
      firstDoneMatches: sample.output.done.findIndex((value) => value === 1) === expectedDone,
      winnerMatchesTarget:
        sample.output.finalWinner === reference.fixtures.targetWinners[fixture],
      fallbackMatches: sample.output.fallbackRequired === Number(expectedDone === null),
      active,
    };
    check.pass = check.routeMatches && check.fineWinnersMatch
      && check.firstDoneMatches && check.winnerMatchesTarget && check.fallbackMatches;
    return check;
  });
  const stats = statistics(samples.map((sample) => sample.milliseconds));
  const first = samples.find((sample) => sample.fixture === 0).output;
  const second = samples.find((sample) => sample.fixture === 1).output;
  const parseAxes = (variation) => new Map(
    [...variation.matchAll(/"(b\d{3})"\s+([\d.eE+-]+)/g)]
      .map((match) => [match[1], Number(match[2])]),
  );
  const firstAxes = parseAxes(first.boundVariation);
  const secondAxes = parseAxes(second.boundVariation);
  const changedBoundAxes = [...firstAxes].reduce(
    (count, [tag, value]) => count + Number(secondAxes.get(tag) !== value), 0,
  );
  const outwardBucket = (value) => Math.floor((value + 4) / 4) * 4;
  const geometryChecks = [0, 1].every((fixture) => {
    const output = samples.find((sample) => sample.fixture === fixture).output;
    return reference.fixtures.browserGroupRadiusPixels[fixture].slice(0, 8)
      .every((value, index) => {
        const delta = output.boundWidths[index] - outwardBucket(value);
        return Math.abs(delta) < 0.02 || Math.abs(delta - 4) < 0.02;
      });
  });
  const prefixBeatsRetained = stats.median < retainedProfile.loadedMedianMilliseconds;
  report = {
    decision: checks.every((check) => check.pass) && geometryChecks
      ? (prefixBeatsRetained ? "continue-to-exact-fallback" : "reject-before-fallback")
      : "reject-correctness-or-carrier",
    chrome: await browser.version(),
    runtimeContainsJavaScript: false,
    fixtureSelection: {
      indices: representativeFixtures,
      purpose: "one-, two-, and three-stage certified stops",
      rounds,
    },
    cold: {
      loadMilliseconds,
      loadAndFirstEvaluationMilliseconds: loadMilliseconds + cold.milliseconds,
    },
    loadedMutation: stats,
    comparisons: {
      retainedProfile,
      globalCascadeProfile,
      medianVsRetainedRatio: stats.median / retainedProfile.loadedMedianMilliseconds,
      medianVsGlobalCascadeRatio: stats.median / globalCascadeProfile.loadedMedianMilliseconds,
      prefixBeatsRetained,
      fullFallbackCanImprovePrefixCost: false,
    },
    correctness: {
      checksPassed: checks.filter((check) => check.pass).length,
      checksTotal: checks.length,
      allPass: checks.every((check) => check.pass),
      checks,
    },
    groupBoundGeometry: {
      boundGlyphs: 197,
      boundAxisCount: first.boundAxisCount,
      changedBoundAxes,
      allAxesLive: first.boundAxisCount === 96 && changedBoundAxes === 96,
      measuredWidthsMatchPredictedOutwardBuckets: geometryChecks,
    },
    fallback: reference.fallback,
    diagnostics,
    samples,
  };
  await context.close();
} finally {
  await browser.close();
  server.closeAllConnections();
  await new Promise((resolve) => server.close(resolve));
}

await fs.writeFile(
  path.join(experiment, "browser-results.json"),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
if (report.decision === "reject-correctness-or-carrier") process.exitCode = 1;
