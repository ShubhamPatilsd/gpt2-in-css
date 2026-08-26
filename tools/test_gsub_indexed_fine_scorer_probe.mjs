import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const experimentName = process.env.GSUB_FINE_SCORER_EXPERIMENT ??
  "gsub-indexed-fine-scorer";
const timingRounds = Number.parseInt(process.env.GSUB_FINE_SCORER_TIMING_ROUNDS ?? "15", 10);
const root = new URL(`../experiments/${experimentName}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));
const server = process.env.GSUB_FINE_SCORER_SERVER ?? "http://127.0.0.1:4178";

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function winnerFromWidths(widths, validCandidates = 256) {
  let winnerLocal = 0;
  for (let local = 1; local < validCandidates; local += 1) {
    if (widths[local] > widths[winnerLocal]) winnerLocal = local;
  }
  const tie = (255 - winnerLocal) / 64;
  return {
    winnerLocal,
    winnerBucket: Math.round((widths[winnerLocal] - tie) / 4),
  };
}

function bucketsFromWidths(widths, validCandidates = 256) {
  return widths.slice(0, validCandidates).map((width, local) =>
    Math.round((width - (255 - local) / 64) / 4));
}

function runnerUpFromBuckets(buckets, winnerLocal) {
  let runnerLocal = winnerLocal === 0 ? 1 : 0;
  for (let local = 0; local < buckets.length; local += 1) {
    if (local !== winnerLocal && buckets[local] > buckets[runnerLocal]) {
      runnerLocal = local;
    }
  }
  return {
    runnerLocal,
    runnerBucket: buckets[runnerLocal],
    winnerMarginBuckets: buckets[winnerLocal] - buckets[runnerLocal],
  };
}

function quantile(values, fraction) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor((sorted.length - 1) * fraction)];
}

async function loadPage(browser, path) {
  const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
  await page.goto(`${server}/experiments/${path}/index.html`, {
    waitUntil: "load",
    timeout: 240_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  return page;
}

async function applyCase(page, kind, hidden, floor, group, feature) {
  return page.evaluate(({ kind: pageKind, hidden: values, floor: scoreFloor, group: groupId, feature: featureValue }) => {
    const stage = document.querySelector(pageKind === "gsub" ? "#gsub-stage" : "#fine-stage");
    values.forEach((value, dimension) => {
      stage.style.setProperty(`--h${dimension}`, String(value));
    });
    stage.style.setProperty("--score-offset", `${-scoreFloor * 256 * 4}px`);
    if (pageKind === "gsub") {
      stage.style.setProperty("--probe-feature", String(featureValue));
    } else {
      stage.style.setProperty("--group", String(groupId));
    }
    const selector = pageKind === "gsub" ? ".candidate" : ".fine-candidate";
    const widths = [...stage.querySelectorAll(selector)].map((element) =>
      element.getBoundingClientRect().width);
    return {
      widths,
      stageWidth: stage.getBoundingClientRect().width,
      featureSettings: getComputedStyle(stage).fontFeatureSettings,
    };
  }, { kind, hidden, floor, group, feature });
}

async function measureSwitches(page, kind, groupCases, rounds) {
  return page.evaluate(({ pageKind, cases, count }) => {
    const stage = document.querySelector(pageKind === "gsub" ? "#gsub-stage" : "#fine-stage");
    const property = pageKind === "gsub" ? "--probe-feature" : "--group";
    const values = cases.map((entry) => pageKind === "gsub" ? entry.feature : entry.group);
    for (let warm = 0; warm < 3; warm += 1) {
      for (const value of values) {
        stage.style.setProperty(property, String(value));
        stage.getBoundingClientRect().width;
      }
    }
    const samples = [];
    for (let round = 0; round < count; round += 1) {
      for (const value of values) {
        const started = performance.now();
        stage.style.setProperty(property, String(value));
        stage.getBoundingClientRect().width;
        samples.push(performance.now() - started);
      }
    }
    return samples;
  }, { pageKind: kind, cases: groupCases, count: rounds });
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const loadStarted = performance.now();
  const gsubPage = await loadPage(browser, experimentName);
  const gsubLoadMilliseconds = performance.now() - loadStarted;
  const baselineLoadStarted = performance.now();
  const baselinePage = await loadPage(browser, reference.baselineDirectory);
  const baselineLoadMilliseconds = performance.now() - baselineLoadStarted;

  const comparisons = [];
  const failures = [];
  const observedSettings = new Set();
  const deltaHistogram = new Map();
  const groupMaximumAbsoluteCandidateDelta = new Map();
  const winnerMarginHistogram = new Map();
  const winnerMargins = [];
  let maximumAbsoluteCandidateDelta = 0;
  let candidateComparisons = 0;
  let winnerTokenMatches = 0;
  let winnerBucketMatches = 0;
  let changedAcrossGroups = false;
  let previousFirstFixtureBuckets = null;
  for (const fixture of reference.fixtures.cases) {
    const hidden = reference.fixtures.hiddenVectors[fixture.fixture];
    const floor = reference.fixtures.scoreFloors[fixture.fixture];
    for (const groupCase of fixture.groups) {
      const [gsub, baseline] = await Promise.all([
        applyCase(gsubPage, "gsub", hidden, floor, groupCase.group, groupCase.feature),
        applyCase(baselinePage, "baseline", hidden, floor, groupCase.group, groupCase.feature),
      ]);
      observedSettings.add(gsub.featureSettings);
      const valid = groupCase.validCandidates;
      const gsubBuckets = bucketsFromWidths(gsub.widths, valid);
      const baselineBuckets = bucketsFromWidths(baseline.widths, valid);
      const gsubWinner = winnerFromWidths(gsub.widths, valid);
      const baselineWinner = winnerFromWidths(baseline.widths, valid);
      const gsubRunnerUp = runnerUpFromBuckets(gsubBuckets, gsubWinner.winnerLocal);
      winnerMargins.push(gsubRunnerUp.winnerMarginBuckets);
      winnerMarginHistogram.set(
        gsubRunnerUp.winnerMarginBuckets,
        (winnerMarginHistogram.get(gsubRunnerUp.winnerMarginBuckets) ?? 0) + 1,
      );
      const differingBuckets = [];
      const deltas = [];
      for (let local = 0; local < valid; local += 1) {
        const delta = gsubBuckets[local] - baselineBuckets[local];
        deltas.push(delta);
        candidateComparisons += 1;
        maximumAbsoluteCandidateDelta = Math.max(
          maximumAbsoluteCandidateDelta,
          Math.abs(delta),
        );
        deltaHistogram.set(delta, (deltaHistogram.get(delta) ?? 0) + 1);
        if (delta !== 0) differingBuckets.push(local);
      }
      if (fixture.fixture === 0) {
        if (previousFirstFixtureBuckets && gsubBuckets.some(
          (bucket, local) => bucket !== previousFirstFixtureBuckets[local])) {
          changedAcrossGroups = true;
        }
        previousFirstFixtureBuckets = gsubBuckets;
      }
      const expectedWinnerMatches =
        gsubWinner.winnerLocal === groupCase.winnerLocal &&
        gsubWinner.winnerBucket === groupCase.winnerBucket;
      const winnerMatches =
        gsubWinner.winnerLocal === baselineWinner.winnerLocal &&
        gsubWinner.winnerBucket === baselineWinner.winnerBucket;
      const winnerTokenMatchesCase =
        gsubWinner.winnerLocal === baselineWinner.winnerLocal;
      if (winnerTokenMatchesCase) winnerTokenMatches += 1;
      if (winnerMatches) winnerBucketMatches += 1;
      const caseMaximumAbsoluteDelta = Math.max(...deltas.map(Math.abs));
      groupMaximumAbsoluteCandidateDelta.set(
        groupCase.group,
        Math.max(
          groupMaximumAbsoluteCandidateDelta.get(groupCase.group) ?? 0,
          caseMaximumAbsoluteDelta,
        ),
      );
      if (caseMaximumAbsoluteDelta > 1 || !winnerTokenMatchesCase) {
        failures.push({
          fixture: fixture.fixture,
          group: groupCase.group,
          differingBuckets: differingBuckets.slice(0, 16),
          differingBucketCount: differingBuckets.length,
          maximumAbsoluteCandidateDelta: caseMaximumAbsoluteDelta,
          gsubWinner,
          baselineWinner,
          expectedWinner: {
            winnerLocal: groupCase.winnerLocal,
            winnerBucket: groupCase.winnerBucket,
          },
        });
      }
      comparisons.push({
        fixture: fixture.fixture,
        group: groupCase.group,
        feature: groupCase.feature,
        validCandidates: valid,
        differingBucketCount: differingBuckets.length,
        maximumAbsoluteCandidateDelta: caseMaximumAbsoluteDelta,
        gsubWinner,
        gsubRunnerUp,
        baselineWinner,
        expectedWinnerLocal: groupCase.winnerLocal,
        expectedWinnerBucket: groupCase.winnerBucket,
        modelOracleWinnerMatches: expectedWinnerMatches,
      });
    }
  }

  const timingFixture = reference.fixtures.cases[0];
  const timingHidden = reference.fixtures.hiddenVectors[0];
  const timingFloor = reference.fixtures.scoreFloors[0];
  await Promise.all([
    applyCase(
      gsubPage, "gsub", timingHidden, timingFloor,
      timingFixture.groups[0].group, timingFixture.groups[0].feature,
    ),
    applyCase(
      baselinePage, "baseline", timingHidden, timingFloor,
      timingFixture.groups[0].group, timingFixture.groups[0].feature,
    ),
  ]);
  const [gsubSwitchMilliseconds, baselineSwitchMilliseconds] = await Promise.all([
    measureSwitches(gsubPage, "gsub", timingFixture.groups, timingRounds),
    measureSwitches(baselinePage, "baseline", timingFixture.groups, timingRounds),
  ]);
  const gsubMedian = median(gsubSwitchMilliseconds);
  const baselineMedian = median(baselineSwitchMilliseconds);
  const speedupFraction = 1 - gsubMedian / baselineMedian;
  const dynamicFeatureValid =
    observedSettings.size === reference.groups && changedAcrossGroups;
  const outputMatches = maximumAbsoluteCandidateDelta === 0;
  const oneBucketAllowanceCoversAll = maximumAbsoluteCandidateDelta <= 1;
  const winnerTokenAgreement = winnerTokenMatches / comparisons.length;
  const winnerBucketAgreement = winnerBucketMatches / comparisons.length;
  const speedGatePassed = speedupFraction >= 0.25;
  const hybridAlwaysFallbackGroups = reference.groupIds.filter((group) => group <= 1);
  const hybridBoundGroups = reference.groupIds.filter((group) => group > 1);
  const hybridEmpiricalDeltaBound = Math.max(
    ...hybridBoundGroups.map((group) => groupMaximumAbsoluteCandidateDelta.get(group) ?? 0),
  );
  const hybridMarginThreshold = 2 * hybridEmpiricalDeltaBound;
  const hybridCertifiable = comparisons.filter((entry) =>
    entry.group > 1 && entry.gsubRunnerUp.winnerMarginBuckets > hybridMarginThreshold);
  const hybridAlwaysFallbackCases = comparisons.filter((entry) => entry.group <= 1).length;
  const hybridNearTieFallbackCases = comparisons.filter((entry) =>
    entry.group > 1 && entry.gsubRunnerUp.winnerMarginBuckets <= hybridMarginThreshold).length;
  const hybridFallbackCases = comparisons.length - hybridCertifiable.length;
  const hybridFallbackRate = hybridFallbackCases / comparisons.length;
  const hybridExpectedSwitchMilliseconds =
    (1 - hybridFallbackRate) * gsubMedian + hybridFallbackRate * baselineMedian;
  const hybridSequentialFallbackMilliseconds =
    ((comparisons.length - hybridAlwaysFallbackCases) * gsubMedian +
      hybridFallbackCases * baselineMedian) / comparisons.length;
  const hardGatePassed = dynamicFeatureValid && oneBucketAllowanceCoversAll &&
    winnerTokenAgreement === 1 && speedGatePassed;
  report = {
    chrome: await browser.version(),
    experimentName,
    groups: reference.groupIds,
    fixtures: reference.fixtures.cases.length,
    candidateComparisons,
    gsubLoadMilliseconds,
    baselineLoadMilliseconds,
    numberedFeature: reference.feature,
    observedFeatureSettings: [...observedSettings],
    changedAcrossGroups,
    dynamicFeatureValid,
    outputMatches,
    maximumAbsoluteCandidateDelta,
    candidateDeltaHistogram: Object.fromEntries(
      [...deltaHistogram.entries()].sort(([a], [b]) => a - b),
    ),
    oneBucketAllowanceCoversAll,
    winnerTokenMatches,
    winnerTokenAgreement,
    winnerBucketMatches,
    winnerBucketAgreement,
    groupMaximumAbsoluteCandidateDelta: Object.fromEntries(
      [...groupMaximumAbsoluteCandidateDelta.entries()].sort(([a], [b]) => a - b),
    ),
    hybridCertification: {
      empiricalOnly: true,
      portableBoundProved: false,
      empiricalCandidateDeltaBound: hybridEmpiricalDeltaBound,
      winnerMarginThresholdBuckets: hybridMarginThreshold,
      certificationRule: `group > 1 and GSUB winner margin > ${hybridMarginThreshold} buckets`,
      totalCases: comparisons.length,
      certifiableCases: hybridCertifiable.length,
      certifiableRate: hybridCertifiable.length / comparisons.length,
      fallbackCases: hybridFallbackCases,
      fallbackRate: hybridFallbackRate,
      alwaysFallbackGroups: hybridAlwaysFallbackGroups,
      alwaysFallbackCases: hybridAlwaysFallbackCases,
      nearTieFallbackCases: hybridNearTieFallbackCases,
      winnerMarginBuckets: {
        minimum: Math.min(...winnerMargins),
        median: quantile(winnerMargins, 0.5),
        p90: quantile(winnerMargins, 0.9),
        p95: quantile(winnerMargins, 0.95),
        maximum: Math.max(...winnerMargins),
        histogram: Object.fromEntries(
          [...winnerMarginHistogram.entries()].sort(([a], [b]) => a - b),
        ),
      },
      expectedWeightedSwitchMilliseconds: hybridExpectedSwitchMilliseconds,
      expectedSpeedupVsAllBaselineFraction:
        1 - hybridExpectedSwitchMilliseconds / baselineMedian,
      expectedSequentialFallbackMilliseconds: hybridSequentialFallbackMilliseconds,
      expectedSequentialSpeedupVsAllBaselineFraction:
        1 - hybridSequentialFallbackMilliseconds / baselineMedian,
    },
    failures,
    timingRounds,
    isolatedGroupSwitch: {
      gsubMedianMilliseconds: gsubMedian,
      baselineMedianMilliseconds: baselineMedian,
      speedupFraction,
      speedupPercent: speedupFraction * 100,
      gatePercent: 25,
      gatePassed: speedGatePassed,
      gsubSamples: gsubSwitchMilliseconds,
      baselineSamples: baselineSwitchMilliseconds,
    },
    sizes: {
      woff2Bytes: reference.fontWoff2Bytes,
      expandedTtfBytes: reference.fontTtfBytes,
      expandedToWoff2Ratio: reference.expandedToWoff2Ratio,
      cssBytes: reference.cssBytes,
      htmlBytes: reference.htmlBytes,
      baselineFineWoff2Bytes: reference.baselineFineWoff2Bytes,
      baselineDispatchCssBytes: reference.baselineDispatchCssBytes,
    },
    hardGatePassed,
    decision: hardGatePassed
      ? (reference.groups === reference.fullVocabularyGroups
        ? "retain: full-scale bounded probe passed"
        : "retain for full-scale measurement: bounded eight-group probe passed")
      : "reject: bounded-safety or speed gate failed",
    comparisons,
  };
  await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
  const results = `# GSUB-indexed fine-scorer probe\n\n` +
    `Decision: **${report.decision}**.\n\n` +
    `The numbered ${reference.feature} feature was ${dynamicFeatureValid ? "valid" : "invalid"}; ` +
    `${candidateComparisons} candidate buckets had a maximum absolute delta of ` +
    `${maximumAbsoluteCandidateDelta}; one added certification bucket ` +
    `${oneBucketAllowanceCoversAll ? "covers" : "does not cover"} every delta. ` +
    `Winner-token agreement was ${(winnerTokenAgreement * 100).toFixed(2)}%. ` +
    `Median isolated group switching was ` +
    `${gsubMedian.toFixed(3)} ms for GSUB and ${baselineMedian.toFixed(3)} ms for CSS dispatch ` +
    `(${(speedupFraction * 100).toFixed(1)}% speedup; 25% required).\n\n` +
    `The ${reference.groups}-group fonts occupy ${reference.fontWoff2Bytes.toLocaleString()} WOFF2 bytes and ` +
    `${reference.fontTtfBytes.toLocaleString()} expanded TTF bytes.\n`;
  await fs.writeFile(new URL("RESULTS.md", root), results);
  console.log(JSON.stringify(report, null, 2));
  if (!hardGatePassed) process.exitCode = 1;
} finally {
  await browser.close();
}
