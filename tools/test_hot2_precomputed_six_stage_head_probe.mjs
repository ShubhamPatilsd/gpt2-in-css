import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const server = process.env.HOT2_PRECOMPUTED_SERVER ?? "http://127.0.0.1:4178";
const directory =
  "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-hot2-precomputed";
const baselineDirectory =
  "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated";
const artifactRoot = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(
  await fs.readFile(new URL("reference.json", artifactRoot), "utf8"),
);
const fixtures = reference.certifiedFixtures;
const stages = reference.stages;
const rounds = Math.max(
  1,
  Number.parseInt(process.env.HOT2_PRECOMPUTED_ROUNDS ?? "1", 10),
);
const semanticOnly = process.env.HOT2_PRECOMPUTED_SEMANTIC_ONLY === "1";
let priorDiagnostic = null;
try {
  priorDiagnostic = JSON.parse(
    await fs.readFile(new URL("browser-results.json", artifactRoot), "utf8"),
  );
} catch {
  priorDiagnostic = null;
}
const fixtureLimit = Math.min(
  fixtures.hiddenVectors.length,
  Math.max(1, Number.parseInt(
    process.env.HOT2_PRECOMPUTED_FIXTURE_LIMIT ??
      String(fixtures.hiddenVectors.length),
    10,
  )),
);
if (fixtureLimit !== fixtures.hiddenVectors.length || fixtureLimit !== 10) {
  throw new Error(
    `the certification screen requires all 10 fixtures; received ${fixtureLimit}`,
  );
}
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

async function settleVariant(page) {
  for (let pass = 0; pass < 3; pass += 1) {
    for (const selector of [
      "#hot-cache-grid-0",
      "#hot-cache-result-0",
      "#hot-cache-grid-1",
      "#hot-cache-result-1",
      "#result",
    ]) {
      await page.locator(selector).evaluate(
        (element) => element.getBoundingClientRect().width,
      );
    }
    for (let stage = 0; stage < stages; stage += 1) {
      const wrapper = page.locator(`#hot2-stage-${stage}`);
      const display = await wrapper.evaluate((element) => getComputedStyle(element).display);
      if (display === "none") break;
      const dynamic = page.locator(`#dynamic-fine-stage-${stage}`);
      const dynamicDisplay = await dynamic.evaluate(
        (element) => getComputedStyle(element).display,
      );
      if (dynamicDisplay !== "none") {
        await dynamic.evaluate((element) => element.getBoundingClientRect().width);
      }
      for (const selector of [
        `#hot2-choice-source-${stage}`,
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
        `#remaining-result-${stage + 1}`,
      ]) {
        await page.locator(selector).evaluate(
          (element) => element.getBoundingClientRect().width,
        );
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
      await page.locator(selector).evaluate(
        (element) => element.getBoundingClientRect().width,
      );
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

async function observeVariant(page) {
  return page.evaluate((stageCount) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    const hotCaches = [0, 1].map((group) => {
      const grid = getComputedStyle(document.querySelector(`#hot-cache-grid-${group}`));
      const result = getComputedStyle(document.querySelector(`#hot-cache-result-${group}`));
      return {
        group,
        gridDisplay: grid.display,
        groupProperty: number(grid, "--group"),
        fineBucket: number(result, `--hot-fine-bucket-${group}`),
        fineLocal: number(result, `--hot-fine-local-${group}`),
        fineWinner: number(result, `--hot-fine-winner-${group}`),
      };
    });
    const coarse = getComputedStyle(document.querySelector("#result"));
    let group = number(coarse, "--group");
    const observations = [];
    for (let stage = 0; stage < stageCount; stage += 1) {
      const wrapper = getComputedStyle(document.querySelector(`#hot2-stage-${stage}`));
      if (wrapper.display === "none") break;
      const dynamic = getComputedStyle(
        document.querySelector(`#dynamic-fine-stage-${stage}`),
      );
      const choice = getComputedStyle(
        document.querySelector(`#hot2-choice-source-${stage}`),
      );
      const fine = getComputedStyle(document.querySelector(
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
      ));
      const remaining = getComputedStyle(
        document.querySelector(`#remaining-result-${stage + 1}`),
      );
      const item = {
        stage,
        group,
        route: group <= 1 ? `hot-cache-${group}` : "dynamic-exact",
        dynamicDisplay: dynamic.display,
        dynamicGroup: number(dynamic, "--group"),
        choiceGroup: number(choice, "--group"),
        fineBucket: number(fine, `--fine-bucket-${stage}`),
        fineLocal: number(fine, `--fine-local-${stage}`),
        fineWinner: number(fine, `--fine-winner-${stage}`),
        bestBucket: number(fine, `--best-bucket-${stage}`),
        bestWinner: number(fine, `--best-winner-${stage}`),
        certificateGap: number(remaining, `--certificate-gap-${stage}`),
        done: number(remaining, `--done-${stage}`),
      };
      observations.push(item);
      if (item.done === 1) break;
      group = number(remaining, `--remaining-group-${stage + 1}`);
    }
    return {
      hotCaches,
      stages: observations,
      activeStages: observations.length,
      hotCacheHits: observations.filter((item) => item.group <= 1).length,
      nonHotDynamicStages: observations.filter((item) => item.group > 1).length,
      finalWinner: observations.at(-1)?.bestWinner,
      finalBucket: observations.at(-1)?.bestBucket,
    };
  }, stages);
}

async function observeBaseline(page) {
  return page.evaluate((stageCount) => {
    const coarse = getComputedStyle(document.querySelector("#result"));
    const observations = [];
    let group = Number(coarse.getPropertyValue("--group"));
    for (let stage = 0; stage < stageCount; stage += 1) {
      const fine = getComputedStyle(document.querySelector(
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
      ));
      const remaining = getComputedStyle(
        document.querySelector(`#remaining-result-${stage + 1}`),
      );
      const item = {
        stage,
        group,
        fineBucket: Number(fine.getPropertyValue(
          stage === 0 ? "--fine-bucket" : `--fine-bucket-${stage}`,
        )),
        fineWinner: Number(fine.getPropertyValue(
          stage === 0 ? "--refined-winner" : `--fine-winner-${stage}`,
        )),
        bestBucket: Number(fine.getPropertyValue(`--best-bucket-${stage}`)),
        bestWinner: Number(fine.getPropertyValue(`--best-winner-${stage}`)),
        certificateGap: Number(
          remaining.getPropertyValue(`--certificate-gap-${stage}`),
        ),
        done: Number(remaining.getPropertyValue(`--done-${stage}`)),
      };
      observations.push(item);
      if (item.done === 1) break;
      group = Number(remaining.getPropertyValue(`--remaining-group-${stage + 1}`));
    }
    return {
      stages: observations,
      activeStages: observations.length,
      finalWinner: observations.at(-1)?.bestWinner,
      finalBucket: observations.at(-1)?.bestBucket,
    };
  }, stages);
}

async function evaluateFixture(page, fixture, kind) {
  const started = performance.now();
  await setInput(page, fixture);
  if (kind === "variant") await settleVariant(page);
  else await settleBaseline(page);
  const output = kind === "variant"
    ? await observeVariant(page)
    : await observeBaseline(page);
  return { fixture, milliseconds: performance.now() - started, output };
}

function semanticCheck(fixture, variant, baseline) {
  const expectedGroups = fixtures.unrolledStageGroups[fixture];
  const expectedWinners = fixtures.unrolledStageFineWinners[fixture];
  const expectedBestWinners = fixtures.unrolledBestWinners[fixture];
  const expectedActive = baseline.activeStages;
  const stageChecks = variant.stages.map((stage, index) => {
    const baselineStage = baseline.stages[index];
    return {
      stage: index,
      baselineStagePresent: baselineStage !== undefined,
      groupMatches: stage.group === expectedGroups[index] &&
        stage.group === baselineStage?.group,
      fixtureFineWinnerMatches: stage.fineWinner === expectedWinners[index],
      fineWinnerMatches: stage.fineWinner === baselineStage?.fineWinner,
      fineBucketMatches: stage.fineBucket === baselineStage?.fineBucket,
      fixtureBestWinnerMatches: stage.bestWinner === expectedBestWinners[index],
      bestWinnerMatches: stage.bestWinner === baselineStage?.bestWinner,
      bestBucketMatches: stage.bestBucket === baselineStage?.bestBucket,
      gapMatches: stage.certificateGap === baselineStage?.certificateGap,
      doneMatches: stage.done === baselineStage?.done,
      routeDisplayMatches: stage.group <= 1
        ? stage.dynamicDisplay === "none"
        : stage.dynamicDisplay === "grid",
    };
  });
  const cacheChecks = variant.hotCaches.map((cache) => {
    const activeStage = variant.stages.find((stage) => stage.group === cache.group);
    return {
      group: cache.group,
      visible: cache.gridDisplay === "grid",
      fixedGroup: cache.groupProperty === cache.group,
      winnerMatches: activeStage === undefined ||
        cache.fineWinner === activeStage.fineWinner,
      bucketMatches: activeStage === undefined ||
        cache.fineBucket === activeStage.fineBucket,
    };
  });
  const check = {
    fixture,
    expectedActive,
    activeStagesMatch: variant.activeStages === expectedActive,
    finalWinnerMatches: variant.finalWinner === baseline.finalWinner &&
      variant.finalWinner === expectedBestWinners[expectedActive - 1],
    finalBucketMatches: variant.finalBucket === baseline.finalBucket,
    stageChecks,
    cacheChecks,
  };
  check.pass = check.activeStagesMatch && check.finalWinnerMatches &&
    check.finalBucketMatches && stageChecks.every((stage) =>
      Object.entries(stage).every(([key, value]) => key === "stage" || value === true)) &&
    cacheChecks.every((cache) =>
      Object.entries(cache).every(([key, value]) => key === "group" || value === true));
  return check;
}

async function runRound(browser, round) {
  const variantContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const baselineContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  let variantLoad;
  let baselineLoad;
  if (round % 2 === 0) {
    variantLoad = await loadPage(variantContext, directory);
    baselineLoad = await loadPage(baselineContext, baselineDirectory);
  } else {
    baselineLoad = await loadPage(baselineContext, baselineDirectory);
    variantLoad = await loadPage(variantContext, directory);
  }

  const warmupFixture = (fixtureLimit - 1 - round + fixtureLimit) % fixtureLimit;
  const variantFirst = await evaluateFixture(variantLoad.page, warmupFixture, "variant");
  const baselineFirst = await evaluateFixture(baselineLoad.page, warmupFixture, "baseline");
  const semanticScreen = [];
  for (let fixture = 0; fixture < fixtureLimit; fixture += 1) {
    const baseline = await evaluateFixture(baselineLoad.page, fixture, "baseline");
    const variant = await evaluateFixture(variantLoad.page, fixture, "variant");
    semanticScreen.push({
      fixture,
      check: semanticCheck(fixture, variant.output, baseline.output),
      variant: variant.output,
      baseline: baseline.output,
    });
  }
  const fixture4 = semanticScreen.find((item) => item.fixture === 4);
  const fixture1 = semanticScreen.find((item) => item.fixture === 1);
  const semanticGuards = {
    allTenFixtures: semanticScreen.length === 10,
    allChecksPass: semanticScreen.every((item) => item.check.pass),
    fixture4GroupOneThenZero: fixture4?.variant.stages[0]?.group === 1 &&
      fixture4?.variant.stages[1]?.group === 0,
    fixture1ActiveDynamicGroup5: fixture1?.variant.stages.some(
      (stage) => stage.group === 5 && stage.dynamicDisplay === "grid",
    ) ?? false,
  };
  if (!Object.values(semanticGuards).every(Boolean)) {
    await variantContext.close();
    await baselineContext.close();
    throw new Error(`semantic preflight failed: ${JSON.stringify(semanticGuards)}`);
  }
  if (semanticOnly) {
    const result = {
      round,
      cold: {
        variantLoadMilliseconds: variantLoad.milliseconds,
        baselineLoadMilliseconds: baselineLoad.milliseconds,
        variantFirstEvaluationMilliseconds: variantFirst.milliseconds,
        baselineFirstEvaluationMilliseconds: baselineFirst.milliseconds,
        variantLoadAndFirstEvaluationMilliseconds:
          variantLoad.milliseconds + variantFirst.milliseconds,
        baselineLoadAndFirstEvaluationMilliseconds:
          baselineLoad.milliseconds + baselineFirst.milliseconds,
      },
      requestFailures: {
        variant: variantLoad.failures,
        baseline: baselineLoad.failures,
      },
      semanticGuards,
      semanticScreen,
      variantSamples: [],
      baselineSamples: [],
    };
    await variantContext.close();
    await baselineContext.close();
    return result;
  }
  const order = Array.from(
    { length: fixtureLimit },
    (_, index) => (index + round) % fixtureLimit,
  );
  const variantSamples = [];
  const baselineSamples = [];
  for (const fixture of order) {
    if ((fixture + round) % 2 === 0) {
      variantSamples.push(await evaluateFixture(variantLoad.page, fixture, "variant"));
      baselineSamples.push(await evaluateFixture(baselineLoad.page, fixture, "baseline"));
    } else {
      baselineSamples.push(await evaluateFixture(baselineLoad.page, fixture, "baseline"));
      variantSamples.push(await evaluateFixture(variantLoad.page, fixture, "variant"));
    }
  }
  const result = {
    round,
    order,
    cold: {
      variantLoadMilliseconds: variantLoad.milliseconds,
      baselineLoadMilliseconds: baselineLoad.milliseconds,
      variantFirstEvaluationMilliseconds: variantFirst.milliseconds,
      baselineFirstEvaluationMilliseconds: baselineFirst.milliseconds,
      variantLoadAndFirstEvaluationMilliseconds:
        variantLoad.milliseconds + variantFirst.milliseconds,
      baselineLoadAndFirstEvaluationMilliseconds:
        baselineLoad.milliseconds + baselineFirst.milliseconds,
    },
    warm: {
      variant: statistics(variantSamples.map((item) => item.milliseconds)),
      baseline: statistics(baselineSamples.map((item) => item.milliseconds)),
    },
    requestFailures: {
      variant: variantLoad.failures,
      baseline: baselineLoad.failures,
    },
    semanticGuards,
    semanticScreen,
    variantSamples,
    baselineSamples,
  };
  await variantContext.close();
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
  if (semanticOnly) {
    const semanticScreen = roundReports.flatMap((round) => round.semanticScreen);
    const checks = semanticScreen.map((item) => item.check);
    const semanticGuards = {
      allTenFixtures: semanticScreen.length === 10 * rounds,
      allChecksPass: checks.every((check) => check.pass),
      fixture4GroupOneThenZero: semanticScreen
        .filter((item) => item.fixture === 4)
        .every((item) => item.variant.stages[0]?.group === 1 &&
          item.variant.stages[1]?.group === 0),
      fixture1ActiveDynamicGroup5: semanticScreen
        .filter((item) => item.fixture === 1)
        .every((item) => item.variant.stages.some(
          (stage) => stage.group === 5 && stage.dynamicDisplay === "grid",
        )),
    };
    if (!Object.values(semanticGuards).every(Boolean)) {
      throw new Error(
        `persisted semantic guards failed: ${JSON.stringify(semanticGuards)}`,
      );
    }
    const cleanDiagnostic = priorDiagnostic?.fixtureLimit === 1 &&
      priorDiagnostic?.semanticsPass === true
      ? {
          fixtureLimit: priorDiagnostic.fixtureLimit,
          comparison: priorDiagnostic.comparison,
          cold: priorDiagnostic.roundsDetail?.[0]?.cold,
          note: "clean fixture-0 diagnostic collected before the contaminated full run",
        }
      : null;
    const variantOutputs = semanticScreen.map((item) => item.variant);
    report = {
      experiment: directory,
      baseline: baselineDirectory,
      chromeVersion: await browser.version(),
      rounds,
      fixtureLimit,
      semanticOnly: true,
      semanticsPass: true,
      decision: "reject-scaling",
      semanticGuards,
      checks,
      semanticScreen,
      corpusCoverage: {
        fixture4GroupOneThenZero: semanticGuards.fixture4GroupOneThenZero,
        fixture1ActiveDynamicGroup5: semanticGuards.fixture1ActiveDynamicGroup5,
        hotCacheHits: variantOutputs.reduce(
          (sum, output) => sum + output.hotCacheHits,
          0,
        ),
        nonHotDynamicStages: variantOutputs.reduce(
          (sum, output) => sum + output.nonHotDynamicStages,
          0,
        ),
        activeStages: variantOutputs.reduce(
          (sum, output) => sum + output.activeStages,
          0,
        ),
      },
      cleanSingleFixtureDiagnostic: cleanDiagnostic,
      fullTimingStatus: (
        "not reported: the completed full timing pass overlapped another Chrome " +
        "test briefly and then failed in post-processing before persistence; it was " +
        "not repeated because the clean fixture-0 diagnostic was already 1.79x slower"
      ),
      roundsDetail: roundReports,
      generatedBytes: reference.generatedBytes,
      reusedAssets: reference.reusedAssets,
      wallMilliseconds: performance.now() - wallStarted,
    };
  } else {
  const checks = [];
  const paired = [];
  for (const round of roundReports) {
    const baselineByFixture = new Map(
      round.baselineSamples.map((item) => [item.fixture, item]),
    );
    for (const variant of round.variantSamples) {
      const fixture = variant.fixture;
      const baseline = baselineByFixture.get(fixture);
      const expectedGroups = fixtures.unrolledStageGroups[fixture];
      const expectedWinners = fixtures.unrolledStageFineWinners[fixture];
      const expectedBestWinners = fixtures.unrolledBestWinners[fixture];
      const expectedActive = baseline.output.activeStages;
      const stageChecks = variant.output.stages.map((stage, index) => {
        const baselineStage = baseline.output.stages[index];
        return {
          stage: index,
          baselineStagePresent: baselineStage !== undefined,
          groupMatches: stage.group === expectedGroups[index] &&
            stage.group === baselineStage?.group,
          fixtureFineWinnerMatches: stage.fineWinner === expectedWinners[index],
          fineWinnerMatches: stage.fineWinner === baselineStage?.fineWinner,
          fineBucketMatches: stage.fineBucket === baselineStage?.fineBucket,
          fixtureBestWinnerMatches: stage.bestWinner === expectedBestWinners[index],
          bestWinnerMatches: stage.bestWinner === baselineStage?.bestWinner,
          bestBucketMatches: stage.bestBucket === baselineStage?.bestBucket,
          gapMatches: stage.certificateGap === baselineStage?.certificateGap,
          routeDisplayMatches: stage.group <= 1
            ? stage.dynamicDisplay === "none"
            : stage.dynamicDisplay === "grid",
        };
      });
      const cacheChecks = variant.output.hotCaches.map((cache) => {
        const index = variant.output.stages.findIndex(
          (stage) => stage.group === cache.group,
        );
        const activeStage = index >= 0 ? variant.output.stages[index] : null;
        return {
          group: cache.group,
          visible: cache.gridDisplay === "grid",
          fixedGroup: cache.groupProperty === cache.group,
          winnerMatches: activeStage === null ||
            cache.fineWinner === activeStage.fineWinner,
          bucketMatches: activeStage === null ||
            cache.fineBucket === activeStage.fineBucket,
        };
      });
      const check = {
        round: round.round,
        fixture,
        expectedActive,
        activeStagesMatch: variant.output.activeStages === expectedActive &&
          baseline.output.activeStages === expectedActive,
        finalWinnerMatches: variant.output.finalWinner === baseline.output.finalWinner &&
          variant.output.finalWinner === expectedBestWinners[expectedActive - 1],
        finalBucketMatches: variant.output.finalBucket === baseline.output.finalBucket &&
          variant.output.finalBucket === baseline.output.finalBucket,
        stageChecks,
        cacheChecks,
      };
      check.pass = check.activeStagesMatch && check.finalWinnerMatches &&
        check.finalBucketMatches && stageChecks.every((stage) =>
          Object.entries(stage).every(([key, value]) => key === "stage" || value === true)) &&
        cacheChecks.every((cache) =>
          Object.entries(cache).every(([key, value]) => key === "group" || value === true));
      checks.push(check);
      paired.push({
        round: round.round,
        fixture,
        variantMilliseconds: variant.milliseconds,
        baselineMilliseconds: baseline.milliseconds,
        deltaMilliseconds: variant.milliseconds - baseline.milliseconds,
        ratio: variant.milliseconds / baseline.milliseconds,
        activeStages: variant.output.activeStages,
        hotCacheHits: variant.output.hotCacheHits,
        nonHotDynamicStages: variant.output.nonHotDynamicStages,
      });
    }
  }
  const variantTimes = paired.map((item) => item.variantMilliseconds);
  const baselineTimes = paired.map((item) => item.baselineMilliseconds);
  const variantMean = statistics(variantTimes).mean;
  const baselineMean = statistics(baselineTimes).mean;
  const semanticsPass = checks.every((check) => check.pass);
  const fixture4Samples = roundReports.flatMap((round) => round.variantSamples)
    .filter((item) => item.fixture === 4);
  const fixture1Samples = roundReports.flatMap((round) => round.variantSamples)
    .filter((item) => item.fixture === 1);
  const corpusCoverage = {
    fixture4GroupOneThenZero: fixture4Samples.every((item) =>
      item.output.stages[0]?.group === 1 && item.output.stages[1]?.group === 0),
    fixture1ActiveDynamicGroup5: fixture1Samples.every((item) =>
      item.output.stages.some(
        (stage) => stage.group === 5 && stage.dynamicDisplay === "grid",
      )),
    hotCacheHits: paired.reduce((sum, item) => sum + item.hotCacheHits, 0),
    nonHotDynamicStages: paired.reduce(
      (sum, item) => sum + item.nonHotDynamicStages,
      0,
    ),
    activeStages: paired.reduce((sum, item) => sum + item.activeStages, 0),
  };
  if (!semanticsPass || !corpusCoverage.fixture4GroupOneThenZero ||
      !corpusCoverage.fixture1ActiveDynamicGroup5) {
    throw new Error(
      `timed semantic guards failed: ${JSON.stringify({ semanticsPass, corpusCoverage })}`,
    );
  }
  report = {
    experiment: directory,
    baseline: baselineDirectory,
    chromeVersion: await browser.version(),
    rounds,
    fixtureLimit,
    semanticsPass,
    decision: semanticsPass && variantMean < baselineMean
      ? (rounds >= 3 ? "retain" : "promising-repeat-required")
      : "reject-scaling",
    comparison: {
      variant: statistics(variantTimes),
      baseline: statistics(baselineTimes),
      meanDeltaMilliseconds: variantMean - baselineMean,
      meanRatio: variantMean / baselineMean,
      meanSpeedupPercent: (1 - variantMean / baselineMean) * 100,
    },
    corpusCoverage,
    checks,
    paired,
    roundsDetail: roundReports,
    generatedBytes: reference.generatedBytes,
    reusedAssets: reference.reusedAssets,
    wallMilliseconds: performance.now() - wallStarted,
  };
  }
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("browser-results.json", artifactRoot),
  `${JSON.stringify(report, null, 2)}\n`,
);

const coverage = report.corpusCoverage;
const firstCold = report.roundsDetail[0].cold;
const reportMarkdown = report.semanticOnly
  ? `# Hot-2 root-precomputed exact six-stage result

Decision: **reject-scaling**.

The full 10-fixture semantic screen passed **${report.checks.filter((item) => item.pass).length}/${report.checks.length} checks**. Every active stage matched the live exact baseline for selected group, fine winner and bucket, merged winner and bucket, certificate gap, stopping, and dynamic-grid visibility. Fixture 4 exercised active group **1 then 0**; fixture 1 exercised active non-hot dynamic group **5**. JavaScript only mutated fixture inputs and observed layout.

## Coverage

- Active serial stages: ${coverage.activeStages}.
- Hot-cache hits: ${coverage.hotCacheHits}.
- Non-hot dynamic exact stages: ${coverage.nonHotDynamicStages}.
- Fixture 4 active group 1 then 0: ${coverage.fixture4GroupOneThenZero}.
- Fixture 1 active dynamic group 5: ${coverage.fixture1ActiveDynamicGroup5}.
- Fixed speculative work per mutation: 512 hot rows.

## Scaling decision

The clean fixture-0 diagnostic measured **${report.cleanSingleFixtureDiagnostic.comparison.variant.mean.toFixed(1)} ms** for root precompute versus **${report.cleanSingleFixtureDiagnostic.comparison.baseline.mean.toFixed(1)} ms** exact, a **${report.cleanSingleFixtureDiagnostic.comparison.meanRatio.toFixed(2)}x slowdown**. The completed full timing pass was potentially contaminated by a brief overlapping Chrome test and then failed in report post-processing, so it is not reported or repeated. The clean loss is already decisive: eagerly evaluating both hot grids does not repay shared-anchor reuse.

Generated HTML: ${reference.generatedBytes["index.html"].toLocaleString()} bytes; topology CSS: ${reference.generatedBytes["topology.css"].toLocaleString()} bytes. Reused ${reference.reusedAssets.fontWoff2Bytes.toLocaleString()} bytes across ${reference.reusedAssets.fontFiles.length} existing WOFF2 files; no fonts copied or rebuilt.

Chrome: ${report.chromeVersion}. Full semantic observations are in \`browser-results.json\`.
`
  : `# Hot-2 root-precomputed exact six-stage result

Decision: **${report.decision}**.

The two fixed global-int16 grids preserve exact score and global-token tie geometry: **${report.checks.filter((item) => item.pass).length}/${report.checks.length} fixture-round checks passed**, including every active stage, the fixture ordered group 1 then 0, and active non-hot stages. JavaScript only mutates fixture inputs and observes layout.

## One-round cold and warm measurement

| Metric | Hot-2 precomputed | Exact baseline |
|---|---:|---:|
| cold load | ${firstCold.variantLoadMilliseconds.toFixed(1)} ms | ${firstCold.baselineLoadMilliseconds.toFixed(1)} ms |
| cold load + first evaluation | ${firstCold.variantLoadAndFirstEvaluationMilliseconds.toFixed(1)} ms | ${firstCold.baselineLoadAndFirstEvaluationMilliseconds.toFixed(1)} ms |
| warm mean (${comparison.variant.count} samples) | ${comparison.variant.mean.toFixed(1)} ms | ${comparison.baseline.mean.toFixed(1)} ms |
| warm median | ${comparison.variant.median.toFixed(1)} ms | ${comparison.baseline.median.toFixed(1)} ms |
| warm p90 | ${comparison.variant.p90.toFixed(1)} ms | ${comparison.baseline.p90.toFixed(1)} ms |

Mean ratio: **${comparison.meanRatio.toFixed(3)}x** (${comparison.meanSpeedupPercent.toFixed(1)}% ${comparison.meanSpeedupPercent >= 0 ? "faster" : "slower"}).

## Work and scaling

- Fixed work per mutation: 512 hot rows (groups 0 and 1), regardless of the selected route.
- Active serial stages observed: ${coverage.activeStages}.
- Hot-cache hits: ${coverage.hotCacheHits}.
- Non-hot dynamic exact stages: ${coverage.nonHotDynamicStages}.
- Fixture 4 active group 1 then 0: ${coverage.fixture4GroupOneThenZero}.
- Fixture 1 active dynamic group 5: ${coverage.fixture1ActiveDynamicGroup5}.
- Generated HTML: ${reference.generatedBytes["index.html"].toLocaleString()} bytes; topology CSS: ${reference.generatedBytes["topology.css"].toLocaleString()} bytes.
- Reused exact WOFF2 assets: ${reference.reusedAssets.fontWoff2Bytes.toLocaleString()} bytes across ${reference.reusedAssets.fontFiles.length} files; no fonts copied or rebuilt.

## Interpretation

${report.decision === "reject-scaling"
  ? "Root caching is semantically exact but does not scale as a latency optimization in this composition. It eagerly computes both hot groups on every mutation, and the shared anchor reuse does not repay that speculative work. No robust repeat was run because the one-round mean did not beat the exact baseline."
  : report.decision === "promising-repeat-required"
    ? "The one-round result beats the exact baseline, so a robust repeat is required before retaining the route."
    : "The robust repeat retains the route: shared exact anchor reuse repays the fixed 512-row speculative cost."}

Chrome: ${report.chromeVersion}. Full observations are in \`browser-results.json\`.
`;
await fs.writeFile(new URL("RESULTS.md", artifactRoot), reportMarkdown);

console.log(JSON.stringify({
  decision: report.decision,
  semanticsPass: report.semanticsPass,
  checksPassed: report.checks.filter((item) => item.pass).length,
  checksTotal: report.checks.length,
  comparison: report.comparison,
  corpusCoverage: report.corpusCoverage,
  cold: firstCold,
  wallMilliseconds: report.wallMilliseconds,
}, null, 2));

if (!report.semanticsPass || !coverage.fixture4GroupOneThenZero ||
    !coverage.fixture1ActiveDynamicGroup5) {
  process.exitCode = 1;
}
