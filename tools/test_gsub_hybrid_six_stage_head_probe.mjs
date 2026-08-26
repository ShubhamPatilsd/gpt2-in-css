import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const server = process.env.GSUB_HYBRID_SERVER ?? "http://localhost:4178";
const directory =
  "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-gsub-hybrid";
const baselineDirectory =
  "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated";
const artifactRoot = new URL(`../experiments/${directory}/`, import.meta.url);
if (process.env.GSUB_HYBRID_PRESERVE_UNSPLIT === "1") {
  await fs.copyFile(
    new URL("browser-results.json", artifactRoot),
    new URL("unsplit-browser-results.json", artifactRoot),
  );
  await fs.copyFile(
    new URL("RESULTS.md", artifactRoot),
    new URL("UNSPLIT-RESULTS.md", artifactRoot),
  );
  console.log("Preserved validated unsplit report and browser results.");
  process.exit(0);
}
const reference = JSON.parse(
  await fs.readFile(new URL("reference.json", artifactRoot), "utf8"),
);
const fixtures = reference.certifiedFixtures;
const stages = reference.stages;
const rounds = Math.max(1, Number.parseInt(process.env.GSUB_HYBRID_ROUNDS ?? "3", 10));
const fixtureLimit = Math.min(
  fixtures.hiddenVectors.length,
  Math.max(1, Number.parseInt(
    process.env.GSUB_HYBRID_FIXTURE_LIMIT ?? String(fixtures.hiddenVectors.length),
    10,
  )),
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
  const properties = fixtures.hiddenVectors[fixture]
    .map((value, dimension) => `--h${dimension}:${value}`);
  properties.push(`--score-offset:${-fixtures.scoreFloors[fixture] * 256 * 4}px`);
  return properties.join(";");
}

async function loadPage(context, targetDirectory) {
  const page = await context.newPage();
  page.setDefaultTimeout(900_000);
  const failures = [];
  page.on("requestfailed", (request) => failures.push({
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
  return { page, failures, milliseconds: performance.now() - started };
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

async function settleHybrid(page) {
  for (let pass = 0; pass < 3; pass += 1) {
    await page.locator("#result").evaluate((element) => element.getBoundingClientRect().width);
    for (let stage = 0; stage < stages; stage += 1) {
      const wrapper = page.locator(`#hybrid-stage-${stage}`);
      const display = await wrapper.evaluate((element) => getComputedStyle(element).display);
      if (display === "none") break;
      for (const selector of [
        `#gsub-top-${stage}`,
        `#split-gsub-top-${stage}`,
        `#gsub-runner-${stage}`,
        `#split-gsub-runner-${stage}`,
        `#hybrid-decision-${stage}`,
      ]) {
        await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
      }
      const exact = page.locator(`#exact-stage-${stage}`);
      const exactDisplay = await exact.evaluate((element) => getComputedStyle(element).display);
      if (exactDisplay !== "none") {
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
          await page.locator(selector).evaluate(
            (element) => element.getBoundingClientRect().width,
          );
        }
      }
    }
  }
}

async function observeHybrid(page) {
  return page.evaluate((stageCount) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    const coarse = getComputedStyle(document.querySelector("#result"));
    const observations = [];
    let group = number(coarse, "--group");
    for (let stage = 0; stage < stageCount; stage += 1) {
      const wrapper = getComputedStyle(document.querySelector(`#hybrid-stage-${stage}`));
      if (wrapper.display === "none") break;
      const splitBank = group <= 1;
      const topElement = document.querySelector(
        splitBank ? `#split-gsub-top-${stage}` : `#gsub-top-${stage}`,
      );
      const runnerElement = document.querySelector(
        splitBank ? `#split-gsub-runner-${stage}` : `#gsub-runner-${stage}`,
      );
      const exactElement = document.querySelector(`#exact-stage-${stage}`);
      const exactFirstCandidate = exactElement.querySelector(".fine-candidate");
      const decisionElement = document.querySelector(`#hybrid-decision-${stage}`);
      const decision = getComputedStyle(decisionElement);
      const fine = getComputedStyle(document.querySelector(
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
      ));
      const topStyle = getComputedStyle(topElement);
      const runnerStyle = getComputedStyle(runnerElement);
      const exactStyle = getComputedStyle(exactElement);
      const exactCandidateStyle = getComputedStyle(exactFirstCandidate);
      const exactDisplay = exactStyle.display;
      const remaining = getComputedStyle(
        document.querySelector(`#remaining-result-${stage + 1}`),
      );
      observations.push({
        stage,
        group,
        bank: splitBank ? "split-complement" : "full",
        scopedGroups: {
          wrapper: number(wrapper, "--group"),
          top: number(topStyle, "--group"),
          runner: number(runnerStyle, "--group"),
          decision: number(decision, "--group"),
          exact: number(exactStyle, "--group"),
          fine: number(fine, "--group"),
        },
        topFeatureSettings: topStyle.fontFeatureSettings,
        topProbeFeature: number(topStyle, "--probe-feature"),
        exactFirstCandidate: {
          group: number(exactCandidateStyle, "--group"),
          fineBase: number(exactCandidateStyle, "--fine-base"),
          fineGlyphs: exactCandidateStyle.getPropertyValue("--fine-glyphs"),
        },
        selectedGroups: Array.from(
          { length: stage + 1 },
          (_, selected) => number(fine, `--selected-group-${selected}`),
        ),
        topLocal: number(decision, `--top-local-${stage}`),
        topBucket: number(decision, `--top-bucket-${stage}`),
        runnerLocal: number(decision, `--runner-local-${stage}`),
        runnerBucket: number(decision, `--runner-bucket-${stage}`),
        marginBuckets: number(decision, `--margin-${stage}`),
        fallback: number(decision, `--fallback-${stage}`),
        exactDisplay,
        fineWinner: number(fine, `--fine-winner-${stage}`),
        fineBucket: number(fine, `--fine-bucket-${stage}`),
        bestWinner: number(fine, `--best-winner-${stage}`),
        bestBucket: number(fine, `--best-bucket-${stage}`),
        certificateGap: number(remaining, `--certificate-gap-${stage}`),
        done: number(remaining, `--done-${stage}`),
      });
      if (observations.at(-1).done === 1) break;
      group = number(remaining, `--remaining-group-${stage + 1}`);
    }
    return {
      stages: observations,
      activeStages: observations.length,
      fallbackStages: observations.filter((item) => item.fallback === 1).length,
      acceptedStages: observations.filter((item) => item.fallback === 0).length,
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
    return {
      groups,
      fineWinners,
      activeStages: groups.length,
      finalWinner: bestWinner,
      finalBucket: bestBucket,
    };
  }, stages);
}

async function evaluateFixture(page, fixture, kind) {
  const started = performance.now();
  await setInput(page, fixture);
  if (kind === "hybrid") await settleHybrid(page);
  else await settleBaseline(page);
  const output = kind === "hybrid"
    ? await observeHybrid(page)
    : await observeBaseline(page);
  return { fixture, milliseconds: performance.now() - started, output };
}

async function runRound(browser, round) {
  const hybridContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const baselineContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  let hybridLoad;
  let baselineLoad;
  if (round % 2 === 0) {
    hybridLoad = await loadPage(hybridContext, directory);
    baselineLoad = await loadPage(baselineContext, baselineDirectory);
  } else {
    baselineLoad = await loadPage(baselineContext, baselineDirectory);
    hybridLoad = await loadPage(hybridContext, directory);
  }

  const warmupFixture = (round + fixtureLimit - 1) % fixtureLimit;
  const hybridFirst = await evaluateFixture(hybridLoad.page, warmupFixture, "hybrid");
  const baselineFirst = await evaluateFixture(baselineLoad.page, warmupFixture, "baseline");
  const order = Array.from(
    { length: fixtureLimit },
    (_, index) => (index + round) % fixtureLimit,
  );
  const hybridSamples = [];
  const baselineSamples = [];
  for (const fixture of order) {
    if ((fixture + round) % 2 === 0) {
      hybridSamples.push(await evaluateFixture(hybridLoad.page, fixture, "hybrid"));
      baselineSamples.push(await evaluateFixture(baselineLoad.page, fixture, "baseline"));
    } else {
      baselineSamples.push(await evaluateFixture(baselineLoad.page, fixture, "baseline"));
      hybridSamples.push(await evaluateFixture(hybridLoad.page, fixture, "hybrid"));
    }
  }

  const result = {
    round,
    order,
    cold: {
      hybridLoadMilliseconds: hybridLoad.milliseconds,
      baselineLoadMilliseconds: baselineLoad.milliseconds,
      hybridLoadAndFirstEvaluationMilliseconds:
        hybridLoad.milliseconds + hybridFirst.milliseconds,
      baselineLoadAndFirstEvaluationMilliseconds:
        baselineLoad.milliseconds + baselineFirst.milliseconds,
      hybridFirstEvaluationMilliseconds: hybridFirst.milliseconds,
      baselineFirstEvaluationMilliseconds: baselineFirst.milliseconds,
    },
    warm: {
      hybrid: statistics(hybridSamples.map((item) => item.milliseconds)),
      baseline: statistics(baselineSamples.map((item) => item.milliseconds)),
    },
    requestFailures: {
      hybrid: hybridLoad.failures,
      baseline: baselineLoad.failures,
    },
    hybridSamples,
    baselineSamples,
  };
  await hybridContext.close();
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
  const hybridSamples = roundReports.flatMap((round) => round.hybridSamples);
  const baselineSamples = roundReports.flatMap((round) => round.baselineSamples);
  const paired = [];
  for (const round of roundReports) {
    const exactByFixture = new Map(
      round.baselineSamples.map((item) => [item.fixture, item]),
    );
    for (const hybrid of round.hybridSamples) {
      const baseline = exactByFixture.get(hybrid.fixture);
      const expectedGroups = fixtures.unrolledStageGroups[hybrid.fixture];
      const expectedFineWinners = fixtures.unrolledStageFineWinners[hybrid.fixture];
      const stageChecks = hybrid.output.stages.map((stage, index) => {
        const threshold = stage.group <= 1
          ? reference.splitMarginThresholdBuckets
          : reference.marginThresholdBuckets;
        const fallbackRule = stage.group === 196 || stage.marginBuckets <= threshold;
        const expectedFeature = `"cv01" ${stage.group + 1}`;
        const featureMatches = stage.topFeatureSettings === expectedFeature ||
          (stage.group === 0 && ["normal", '"cv01"'].includes(
            stage.topFeatureSettings,
          ));
        const scorerGroups = [
          stage.scopedGroups.top,
          stage.scopedGroups.runner,
          stage.scopedGroups.decision,
          stage.scopedGroups.exact,
          stage.exactFirstCandidate.group,
        ];
        return {
          groupMatches: stage.group === expectedGroups[index],
          scorerGroupPropagates: scorerGroups.every((value) => value === stage.group),
          nestedRouterKeepsRootGroup:
            stage.scopedGroups.fine === expectedGroups[0] &&
            stage.scopedGroups.wrapper === expectedGroups[0],
          immutableVisitedGroupsMatch:
            stage.selectedGroups.every((value, selected) =>
              value === expectedGroups[selected]),
          featureDispatchMatchesGroup: featureMatches,
          probeFeatureMatchesGroup: stage.topProbeFeature === stage.group + 1,
          fineWinnerExact: stage.fineWinner === expectedFineWinners[index],
          fallbackMatchesRule: stage.fallback === Number(fallbackRule),
          exactDisplayMatchesRoute: stage.exactDisplay ===
            (fallbackRule ? "grid" : "none"),
          partialGroupConservative: stage.group !== 196 || stage.fallback === 1,
          bankMatchesGroup: stage.bank ===
            (stage.group <= 1 ? "split-complement" : "full"),
          fineBucketDeltaFromExact:
            stage.fineBucket - fixtures.unrolledStageFineBuckets[hybrid.fixture][index],
        };
      });
      paired.push({
        round: round.round,
        fixture: hybrid.fixture,
        hybridMilliseconds: hybrid.milliseconds,
        baselineMilliseconds: baseline.milliseconds,
        speedup: baseline.milliseconds / hybrid.milliseconds,
        hybrid: hybrid.output,
        baseline: baseline.output,
        stageChecks,
        finalDenseWinnerCorrect:
          hybrid.output.finalWinner === fixtures.denseWinners[hybrid.fixture],
        finalMatchesExactBaseline:
          hybrid.output.finalWinner === baseline.output.finalWinner,
      });
    }
  }

  const hybridWarm = statistics(hybridSamples.map((item) => item.milliseconds));
  const baselineWarm = statistics(baselineSamples.map((item) => item.milliseconds));
  const activeStages = hybridSamples.map((item) => item.output.activeStages);
  const fallbackStages = hybridSamples.map((item) => item.output.fallbackStages);
  const acceptedStages = hybridSamples.map((item) => item.output.acceptedStages);
  const routeTotals = {
    active: activeStages.reduce((sum, value) => sum + value, 0),
    fallback: fallbackStages.reduce((sum, value) => sum + value, 0),
    accepted: acceptedStages.reduce((sum, value) => sum + value, 0),
  };
  const allStageRoutesValid = paired.every((sample) => sample.stageChecks.every(
    (checks) => checks.groupMatches && checks.scorerGroupPropagates &&
      checks.nestedRouterKeepsRootGroup &&
      checks.immutableVisitedGroupsMatch &&
      checks.featureDispatchMatchesGroup && checks.fineWinnerExact &&
      checks.probeFeatureMatchesGroup &&
      checks.fallbackMatchesRule && checks.exactDisplayMatchesRoute &&
      checks.partialGroupConservative && checks.bankMatchesGroup,
  ));
  const distinctGroupBankStateGuard = paired.every((sample) => {
    const stagesByGroup = new Map();
    for (const stage of sample.hybrid.stages) {
      const fingerprint = `${stage.scopedGroups.top}:${stage.topFeatureSettings}`;
      if (stagesByGroup.has(stage.group) && stagesByGroup.get(stage.group) !== fingerprint) {
        return false;
      }
      stagesByGroup.set(stage.group, fingerprint);
    }
    return new Set(stagesByGroup.values()).size === stagesByGroup.size;
  });
  const allFinalWinnersMatch = paired.every((sample) => sample.finalMatchesExactBaseline);
  const allDenseWinnersCorrect = paired.every((sample) => sample.finalDenseWinnerCorrect);
  const requestFailures = roundReports.flatMap((round) => [
    ...round.requestFailures.hybrid,
    ...round.requestFailures.baseline,
  ]);
  report = {
    decision: allStageRoutesValid && distinctGroupBankStateGuard &&
      allFinalWinnersMatch && allDenseWinnersCorrect && requestFailures.length === 0
      ? "pass" : "fail",
    chrome: await browser.version(),
    server,
    rounds,
    fixturesPerRound: fixtureLimit,
    comparisons: paired.length,
    allStageRoutesValid,
    distinctGroupBankStateGuard,
    allFinalWinnersMatch,
    allDenseWinnersCorrect,
    cold: {
      hybridLoad: statistics(roundReports.map(
        (round) => round.cold.hybridLoadMilliseconds,
      )),
      baselineLoad: statistics(roundReports.map(
        (round) => round.cold.baselineLoadMilliseconds,
      )),
      hybridLoadAndFirstEvaluation: statistics(roundReports.map(
        (round) => round.cold.hybridLoadAndFirstEvaluationMilliseconds,
      )),
      baselineLoadAndFirstEvaluation: statistics(roundReports.map(
        (round) => round.cold.baselineLoadAndFirstEvaluationMilliseconds,
      )),
    },
    warm: {
      hybrid: hybridWarm,
      baseline: baselineWarm,
      composedSpeedup: baselineWarm.median / hybridWarm.median,
      pairedSpeedup: statistics(paired.map((item) => item.speedup)),
      perRoundHybridMedians: roundReports.map((round) => round.warm.hybrid.median),
      perRoundBaselineMedians: roundReports.map((round) => round.warm.baseline.median),
    },
    routes: {
      totals: routeTotals,
      fallbackRate: routeTotals.fallback / routeTotals.active,
      activeStages: statistics(activeStages),
      fallbackStagesPerEvaluation: statistics(fallbackStages),
      acceptedStagesPerEvaluation: statistics(acceptedStages),
    },
    bucketDeltas: statistics(paired.flatMap((sample) =>
      sample.stageChecks.map((checks) => checks.fineBucketDeltaFromExact),
    )),
    requestFailures,
    durationMilliseconds: performance.now() - wallStarted,
    roundsDetail: roundReports,
    paired,
  };
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("browser-results.json", artifactRoot),
  `${JSON.stringify(report, null, 2)}\n`,
);
const ms = (value) => `${value.toFixed(1)} ms`;
const beatsBaseline = report.warm.composedSpeedup > 1;
const scalingDecision = beatsBaseline ? "retain" : "reject for scaling";
const markdown = `# Six-stage GSUB hybrid output-head probe\n\n` +
  `Scaling decision: **${scalingDecision}**; semantic decision: **${report.decision}**. ` +
  `Chrome ${report.chrome} ran ${report.rounds} cold ` +
  `rounds and ${report.comparisons} warm fixture comparisons. CSS selected every route ` +
  `and winner; JavaScript only changed fixture inputs and observed layout.\n\n` +
  `| Metric | GSUB hybrid | Exact baseline |\n` +
  `| --- | ---: | ---: |\n` +
  `| Cold load median | ${ms(report.cold.hybridLoad.median)} | ${ms(report.cold.baselineLoad.median)} |\n` +
  `| Cold load + first evaluation median | ${ms(report.cold.hybridLoadAndFirstEvaluation.median)} | ${ms(report.cold.baselineLoadAndFirstEvaluation.median)} |\n` +
  `| Warm mutation median | ${ms(report.warm.hybrid.median)} | ${ms(report.warm.baseline.median)} |\n` +
  `| Warm composed speedup | **${report.warm.composedSpeedup.toFixed(2)}×** | 1.00× |\n\n` +
  `The hybrid activated ${report.routes.totals.active} fine stages: ` +
  `${report.routes.totals.accepted} GSUB accepts and ${report.routes.totals.fallback} ` +
  `exact fallbacks (${(report.routes.fallbackRate * 100).toFixed(1)}%). Active stages had ` +
  `median ${report.routes.activeStages.median}; exact fallbacks per evaluation had median ` +
  `${report.routes.fallbackStagesPerEvaluation.median}.\n\n` +
  `The topology conditionally displays the split-complement top/runner grids for ` +
  `groups 0/1 and the full-bank grids for groups 2..196. Both feed shared winner ` +
  `anchors and one exact fallback grid. Group 0/1 accepts require margin >4; full-bank ` +
  `accepts require margin >6; group 196 is always exact.\n\n` +
  `Final winners matched the six-stage exact page in every comparison: ` +
  `${report.allFinalWinnersMatch}. Fine-stage route/winner checks all passed: ` +
  `${report.allStageRoutesValid}. The distinct-group bank-state guard passed: ` +
  `${report.distinctGroupBankStateGuard}. The final partial group 196 was always forced to exact.\n\n` +
  `${beatsBaseline ? "The split-aware head beat the exact baseline, so a robust repeat is warranted." : "The route mix flipped but the head did not beat the exact baseline, so the conditional robust repeat was not run."}\n\n` +
  `The validated three-round unsplit result is preserved in \`UNSPLIT-RESULTS.md\` and ` +
  `\`unsplit-browser-results.json\`; provisional scope-bug measurements are excluded.\n\n` +
  `The six-bucket GSUB gate remains empirical for this font bank and Chrome build; it is ` +
  `not a portable browser-independent proof.\n`;
await fs.writeFile(new URL("RESULTS.md", artifactRoot), markdown);

console.log(JSON.stringify({
  decision: report.decision,
  chrome: report.chrome,
  rounds: report.rounds,
  comparisons: report.comparisons,
  cold: report.cold,
  warm: report.warm,
  routes: report.routes,
  allStageRoutesValid: report.allStageRoutesValid,
  distinctGroupBankStateGuard: report.distinctGroupBankStateGuard,
  allFinalWinnersMatch: report.allFinalWinnersMatch,
  allDenseWinnersCorrect: report.allDenseWinnersCorrect,
  bucketDeltas: report.bucketDeltas,
  requestFailures: report.requestFailures,
  durationSeconds: report.durationMilliseconds / 1000,
}, null, 2));
if (report.decision !== "pass") process.exitCode = 1;
