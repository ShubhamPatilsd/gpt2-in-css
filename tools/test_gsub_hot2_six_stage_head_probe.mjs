import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const server = process.env.GSUB_HOT2_SERVER ?? "http://localhost:4178";
const directory =
  "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-gsub-hot2";
const baselineDirectory =
  "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated";
const root = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));
const fixtures = reference.certifiedFixtures;
const stages = reference.stages;
const rounds = Math.max(1, Number.parseInt(process.env.GSUB_HOT2_ROUNDS ?? "1", 10));
const fixtureLimit = Math.min(
  10,
  Math.max(1, Number.parseInt(process.env.GSUB_HOT2_FIXTURE_LIMIT ?? "10", 10)),
);
const wallStarted = performance.now();

function percentile(sorted, fraction) {
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * fraction))];
}

function statistics(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((left, right) => left - right);
  return {
    count: sorted.length,
    minimum: sorted[0],
    median: percentile(sorted, 0.5),
    p90: percentile(sorted, 0.9),
    maximum: sorted.at(-1),
    mean: sorted.reduce((sum, value) => sum + value, 0) / sorted.length,
  };
}

function fixtureStyle(fixture) {
  const values = fixtures.hiddenVectors[fixture]
    .map((value, dimension) => `--h${dimension}:${value}`);
  values.push(`--score-offset:${-fixtures.scoreFloors[fixture] * 256 * 4}px`);
  return values.join(";");
}

async function loadPage(context, targetDirectory) {
  const page = await context.newPage();
  page.setDefaultTimeout(900_000);
  const requestFailures = [];
  page.on("requestfailed", (request) => requestFailures.push({
    url: request.url(),
    error: request.failure()?.errorText,
  }));
  const started = performance.now();
  await page.goto(`${server}/experiments/${targetDirectory}/index.html`, {
    waitUntil: "load",
    timeout: 900_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  return { page, milliseconds: performance.now() - started, requestFailures };
}

async function setInput(page, fixture) {
  await page.evaluate((style) => {
    for (const element of [
      document.querySelector(".cascade"),
      document.querySelector("#model"),
    ]) {
      element.style.cssText = style;
    }
  }, fixtureStyle(fixture));
}

async function settleHot2(page) {
  for (let pass = 0; pass < 3; pass += 1) {
    await page.locator("#result").evaluate((element) => element.getBoundingClientRect().width);
    for (let stage = 0; stage < stages; stage += 1) {
      const wrapper = page.locator(`#hybrid-stage-${stage}`);
      if (await wrapper.evaluate((element) => getComputedStyle(element).display) === "none") {
        break;
      }
      for (const selector of [
        `#split-gsub-top-${stage}`,
        `#split-gsub-runner-${stage}`,
        `#hybrid-decision-${stage}`,
      ]) {
        await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
      }
      const exact = page.locator(`#exact-stage-${stage}`);
      if (await exact.evaluate((element) => getComputedStyle(element).display) !== "none") {
        await exact.evaluate((element) => element.getBoundingClientRect().width);
      }
      for (const selector of [
        `#hybrid-choice-source-${stage}`,
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
        `#remaining-result-${stage + 1}`,
      ]) {
        await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
      }
      const done = await page.locator(`#remaining-result-${stage + 1}`).evaluate(
        (element, property) => Number(getComputedStyle(element).getPropertyValue(property)),
        `--done-${stage}`,
      );
      if (done === 1) break;
    }
  }
}

async function settleBaseline(page) {
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
          await page.locator(selector).evaluate((element) =>
            element.getBoundingClientRect().width);
        }
      }
    }
  }
}

async function observeHot2(page) {
  return page.evaluate((stageCount) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    const coarse = getComputedStyle(document.querySelector("#result"));
    const observations = [];
    let group = number(coarse, "--group");
    for (let stage = 0; stage < stageCount; stage += 1) {
      const wrapper = getComputedStyle(document.querySelector(`#hybrid-stage-${stage}`));
      if (wrapper.display === "none") break;
      const top = getComputedStyle(document.querySelector(`#split-gsub-top-${stage}`));
      const runner = getComputedStyle(
        document.querySelector(`#split-gsub-runner-${stage}`),
      );
      const decision = getComputedStyle(document.querySelector(`#hybrid-decision-${stage}`));
      const exact = getComputedStyle(document.querySelector(`#exact-stage-${stage}`));
      const fine = getComputedStyle(document.querySelector(
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
      ));
      const remaining = getComputedStyle(
        document.querySelector(`#remaining-result-${stage + 1}`),
      );
      const fallback = number(decision, `--fallback-${stage}`);
      observations.push({
        stage,
        group,
        hot2Eligible: group <= 1,
        topDisplay: top.display,
        runnerDisplay: runner.display,
        probeFeature: number(top, "--probe-feature"),
        topLocal: number(decision, `--top-local-${stage}`),
        topBucket: number(decision, `--top-bucket-${stage}`),
        runnerLocal: number(decision, `--runner-local-${stage}`),
        runnerBucket: number(decision, `--runner-bucket-${stage}`),
        marginBuckets: number(decision, `--margin-${stage}`),
        fallback,
        route: group >= 2
          ? "other-group-fallback"
          : fallback === 1 ? "margin-fallback" : "hot2-accept",
        exactDisplay: exact.display,
        fineWinner: number(fine, `--fine-winner-${stage}`),
        fineBucket: number(fine, `--fine-bucket-${stage}`),
        bestWinner: number(fine, `--best-winner-${stage}`),
        bestBucket: number(fine, `--best-bucket-${stage}`),
        selectedGroups: Array.from(
          { length: stage + 1 },
          (_, selected) => number(fine, `--selected-group-${selected}`),
        ),
        done: number(remaining, `--done-${stage}`),
      });
      if (observations.at(-1).done === 1) break;
      group = number(remaining, `--remaining-group-${stage + 1}`);
    }
    return {
      stages: observations,
      activeStages: observations.length,
      finalWinner: observations.at(-1)?.bestWinner,
      finalBucket: observations.at(-1)?.bestBucket,
    };
  }, stages);
}

async function observeBaseline(page) {
  return page.evaluate((stageCount) => {
    const coarse = getComputedStyle(document.querySelector("#result"));
    const groups = [Number(coarse.getPropertyValue("--group"))];
    const fineWinners = [Number(
      getComputedStyle(document.querySelector("#fine-result"))
        .getPropertyValue("--refined-winner"),
    )];
    let bestWinner = Number(
      getComputedStyle(document.querySelector("#fine-result"))
        .getPropertyValue("--best-winner-0"),
    );
    let bestBucket = Number(
      getComputedStyle(document.querySelector("#fine-result"))
        .getPropertyValue("--best-bucket-0"),
    );
    for (let stage = 1; stage <= stageCount; stage += 1) {
      const remaining = getComputedStyle(
        document.querySelector(`#remaining-result-${stage}`),
      );
      const done = Number(remaining.getPropertyValue(`--done-${stage - 1}`));
      bestWinner = Number(remaining.getPropertyValue(`--best-winner-${stage - 1}`));
      bestBucket = Number(remaining.getPropertyValue(`--best-bucket-${stage - 1}`));
      if (done === 1) break;
      if (stage < stageCount) {
        groups.push(Number(remaining.getPropertyValue(`--remaining-group-${stage}`)));
        const fine = getComputedStyle(document.querySelector(`#fine-result-${stage}`));
        fineWinners.push(Number(fine.getPropertyValue(`--fine-winner-${stage}`)));
        bestWinner = Number(fine.getPropertyValue(`--best-winner-${stage}`));
        bestBucket = Number(fine.getPropertyValue(`--best-bucket-${stage}`));
      }
    }
    return { groups, fineWinners, activeStages: groups.length, finalWinner: bestWinner,
      finalBucket: bestBucket };
  }, stages);
}

async function evaluateFixture(page, fixture, kind) {
  const started = performance.now();
  await setInput(page, fixture);
  if (kind === "hot2") await settleHot2(page);
  else await settleBaseline(page);
  return {
    fixture,
    milliseconds: performance.now() - started,
    output: kind === "hot2" ? await observeHot2(page) : await observeBaseline(page),
  };
}

async function resources(page) {
  return page.evaluate(() => performance.getEntriesByType("resource").map((entry) => ({
    name: entry.name,
    transferSize: entry.transferSize,
    encodedBodySize: entry.encodedBodySize,
  })));
}

async function runRound(browser, round) {
  const hot2Context = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const baselineContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  let hot2Load;
  let baselineLoad;
  if (round % 2 === 0) {
    hot2Load = await loadPage(hot2Context, directory);
    baselineLoad = await loadPage(baselineContext, baselineDirectory);
  } else {
    baselineLoad = await loadPage(baselineContext, baselineDirectory);
    hot2Load = await loadPage(hot2Context, directory);
  }
  const warmup = (round + fixtureLimit - 1) % fixtureLimit;
  const hot2First = await evaluateFixture(hot2Load.page, warmup, "hot2");
  const baselineFirst = await evaluateFixture(baselineLoad.page, warmup, "baseline");
  const order = Array.from({ length: fixtureLimit },
    (_, index) => (index + round) % fixtureLimit);
  const hot2Samples = [];
  const baselineSamples = [];
  for (const fixture of order) {
    if ((fixture + round) % 2 === 0) {
      hot2Samples.push(await evaluateFixture(hot2Load.page, fixture, "hot2"));
      baselineSamples.push(await evaluateFixture(baselineLoad.page, fixture, "baseline"));
    } else {
      baselineSamples.push(await evaluateFixture(baselineLoad.page, fixture, "baseline"));
      hot2Samples.push(await evaluateFixture(hot2Load.page, fixture, "hot2"));
    }
  }
  const result = {
    round,
    order,
    cold: {
      hot2LoadMilliseconds: hot2Load.milliseconds,
      baselineLoadMilliseconds: baselineLoad.milliseconds,
      hot2LoadAndFirstEvaluationMilliseconds: hot2Load.milliseconds + hot2First.milliseconds,
      baselineLoadAndFirstEvaluationMilliseconds:
        baselineLoad.milliseconds + baselineFirst.milliseconds,
    },
    warm: {
      hot2: statistics(hot2Samples.map((item) => item.milliseconds)),
      baseline: statistics(baselineSamples.map((item) => item.milliseconds)),
    },
    resources: {
      hot2: await resources(hot2Load.page),
      baseline: await resources(baselineLoad.page),
    },
    requestFailures: [...hot2Load.requestFailures, ...baselineLoad.requestFailures],
    hot2Samples,
    baselineSamples,
  };
  await hot2Context.close();
  await baselineContext.close();
  return result;
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const roundReports = [];
  for (let round = 0; round < rounds; round += 1) {
    roundReports.push(await runRound(browser, round));
  }
  const paired = [];
  for (const round of roundReports) {
    const baselineByFixture = new Map(
      round.baselineSamples.map((item) => [item.fixture, item]),
    );
    for (const hot2 of round.hot2Samples) {
      const baseline = baselineByFixture.get(hot2.fixture);
      const expectedGroups = fixtures.unrolledStageGroups[hot2.fixture];
      const expectedWinners = fixtures.unrolledStageFineWinners[hot2.fixture];
      const stageChecks = hot2.output.stages.map((stage, index) => {
        const expectedFallback = stage.group >= 2 ||
          stage.marginBuckets <= reference.marginThresholdBuckets;
        return {
          groupExact: stage.group === expectedGroups[index],
          winnerExact: stage.fineWinner === expectedWinners[index],
          routeExact: stage.fallback === Number(expectedFallback),
          exactDisplayCorrect: stage.exactDisplay ===
            (expectedFallback ? "grid" : "none"),
          hot2GridCorrect: stage.topDisplay === (stage.group <= 1 ? "grid" : "none") &&
            stage.runnerDisplay === (stage.group <= 1 ? "grid" : "none"),
          featureCorrect: stage.group >= 2 || stage.probeFeature === stage.group + 1,
          immutableVisitsExact: stage.selectedGroups.every(
            (group, selected) => group === expectedGroups[selected]),
        };
      });
      paired.push({
        round: round.round,
        fixture: hot2.fixture,
        hot2Milliseconds: hot2.milliseconds,
        baselineMilliseconds: baseline.milliseconds,
        pairedSpeedup: baseline.milliseconds / hot2.milliseconds,
        hot2: hot2.output,
        baseline: baseline.output,
        stageChecks,
        activeStageCountExact: hot2.output.activeStages === baseline.output.activeStages,
        finalMatchesBaseline: hot2.output.finalWinner === baseline.output.finalWinner,
        finalDenseWinnerCorrect: hot2.output.finalWinner === fixtures.denseWinners[hot2.fixture],
      });
    }
  }
  const hot2Timings = paired.map((item) => item.hot2Milliseconds);
  const baselineTimings = paired.map((item) => item.baselineMilliseconds);
  const routeStages = paired.flatMap((item) => item.hot2.stages);
  const routeCounts = {
    hot2Accepts: routeStages.filter((stage) => stage.route === "hot2-accept").length,
    marginFallbacks: routeStages.filter((stage) => stage.route === "margin-fallback").length,
    otherGroupFallbacks: routeStages.filter(
      (stage) => stage.route === "other-group-fallback",
    ).length,
  };
  routeCounts.activeStages = routeStages.length;
  const semanticsPass = paired.every((item) =>
    item.activeStageCountExact && item.finalMatchesBaseline &&
    item.finalDenseWinnerCorrect && item.stageChecks.every((checks) =>
      Object.values(checks).every(Boolean)));
  const requestFailures = roundReports.flatMap((round) => round.requestFailures);
  const fullBankReferences = roundReports.flatMap((round) => round.resources.hot2)
    .filter((entry) => entry.name.includes("gsub-indexed-fine-scorer/full"));
  const hot2Warm = statistics(hot2Timings);
  const baselineWarm = statistics(baselineTimings);
  report = {
    decision: semanticsPass && requestFailures.length === 0 &&
      fullBankReferences.length === 0 ? "pass" : "fail",
    scalingDecision: hot2Warm.median < baselineWarm.median ? "retain" : "reject",
    chrome: await browser.version(),
    server,
    rounds,
    fixturesPerRound: fixtureLimit,
    comparisons: paired.length,
    semanticsPass,
    allFinalWinnersMatch: paired.every((item) => item.finalMatchesBaseline),
    allActiveStagesMatch: paired.every((item) => item.activeStageCountExact),
    cold: {
      hot2Load: statistics(roundReports.map((round) => round.cold.hot2LoadMilliseconds)),
      baselineLoad: statistics(roundReports.map(
        (round) => round.cold.baselineLoadMilliseconds)),
      hot2LoadAndFirstEvaluation: statistics(roundReports.map(
        (round) => round.cold.hot2LoadAndFirstEvaluationMilliseconds)),
      baselineLoadAndFirstEvaluation: statistics(roundReports.map(
        (round) => round.cold.baselineLoadAndFirstEvaluationMilliseconds)),
    },
    warm: {
      hot2: hot2Warm,
      baseline: baselineWarm,
      composedSpeedup: baselineWarm.median / hot2Warm.median,
      pairedSpeedup: statistics(paired.map((item) => item.pairedSpeedup)),
      perRoundHot2Medians: roundReports.map((round) => round.warm.hot2.median),
      perRoundBaselineMedians: roundReports.map((round) => round.warm.baseline.median),
    },
    routes: routeCounts,
    sources: {
      generatedBytes: reference.generatedBytes,
      reusedAssets: reference.reusedAssets,
      hot2Resources: roundReports[0].resources.hot2,
      fullBankReferences,
    },
    requestFailures,
    durationMilliseconds: performance.now() - wallStarted,
    roundsDetail: roundReports,
    paired,
  };
} finally {
  await browser.close();
}

await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
const ms = (value) => `${value.toFixed(1)} ms`;
const robustRepeat = report.rounds > 1;
const markdown = `# Hot-two six-stage GSUB output-head probe\n\n` +
  `Scaling decision: **${report.scalingDecision}**; semantic decision: ` +
  `**${report.decision}**. Chrome ${report.chrome} ran ${report.rounds} cold round` +
  `${report.rounds === 1 ? "" : "s"} and ${report.comparisons} paired warm comparisons.\n\n` +
  `| Metric | Hot-two hybrid | Exact baseline |\n` +
  `| --- | ---: | ---: |\n` +
  `| Cold load median | ${ms(report.cold.hot2Load.median)} | ${ms(report.cold.baselineLoad.median)} |\n` +
  `| Load + first evaluation median | ${ms(report.cold.hot2LoadAndFirstEvaluation.median)} | ${ms(report.cold.baselineLoadAndFirstEvaluation.median)} |\n` +
  `| Warm mutation median | ${ms(report.warm.hot2.median)} | ${ms(report.warm.baseline.median)} |\n` +
  `| Composed speedup | **${report.warm.composedSpeedup.toFixed(2)}×** | 1.00× |\n\n` +
  `Across ${report.routes.activeStages} active stages, CSS selected ` +
  `${report.routes.hot2Accepts} hot-two accepts, ${report.routes.marginFallbacks} ` +
  `group-0/1 margin fallbacks, and ${report.routes.otherGroupFallbacks} direct ` +
  `other-group exact fallbacks. All active stages and final winners matched exact: ` +
  `${report.semanticsPass}.\n\n` +
  `The page contains only the focused split-complement GSUB top/runner bank. Groups ` +
  `0/1 accept at rendered margin >4; every group >=2 directly displays exact. ` +
  `No full 197-group GSUB bank is included, referenced, or requested. The page reuses ` +
  `${reference.reusedAssets.splitGsubWoff2Bytes.toLocaleString()} bytes of split-GSUB ` +
  `WOFF2 and the existing exact fonts by relative URL; no fonts were copied or rebuilt.\n\n` +
  `Generated source is ${reference.generatedBytes["index.html"].toLocaleString()} bytes ` +
  `of HTML, ${reference.generatedBytes["split-bank.css"].toLocaleString()} bytes of split-bank ` +
  `CSS, and ${reference.generatedBytes["topology.css"].toLocaleString()} bytes of topology CSS. ` +
  `The sources are \`${reference.sourceBaseline}\`, \`${reference.sourceOneStep}\`, and ` +
  `\`${reference.sourceSplitGsub}\`.\n\n` +
  `${robustRepeat ? "This report is the robust repeat." : report.scalingDecision === "retain" ? "This one-round result qualifies for a robust repeat." : "The robust repeat was not run because hot-two did not beat exact."}\n\n` +
  `The four-bucket gate is empirical for this bank, fixture set, and Chrome build.\n`;
await fs.writeFile(new URL("RESULTS.md", root), markdown);

console.log(JSON.stringify({
  decision: report.decision,
  scalingDecision: report.scalingDecision,
  chrome: report.chrome,
  rounds: report.rounds,
  comparisons: report.comparisons,
  semanticsPass: report.semanticsPass,
  cold: report.cold,
  warm: report.warm,
  routes: report.routes,
  fullBankReferences: report.sources.fullBankReferences,
  requestFailures: report.requestFailures,
  durationSeconds: report.durationMilliseconds / 1000,
}, null, 2));
if (report.decision !== "pass") process.exitCode = 1;
