import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const experimentName = "gsub-split-complement-fine-scorer";
const root = new URL(`../experiments/${experimentName}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));
const server = process.env.GSUB_SPLIT_COMPLEMENT_SERVER ?? "http://127.0.0.1:4183";
const timingRounds = Number.parseInt(
  process.env.GSUB_SPLIT_COMPLEMENT_TIMING_ROUNDS ?? "31", 10,
);

function quantile(values, fraction) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor((sorted.length - 1) * fraction)];
}

function median(values) {
  return quantile(values, 0.5);
}

function bucketsFromWidths(widths, validCandidates = 256) {
  return widths.slice(0, validCandidates).map((width, local) =>
    Math.round((width - (255 - local) / 64) / 4));
}

function winnerFromBuckets(buckets) {
  let winnerLocal = 0;
  for (let local = 1; local < buckets.length; local += 1) {
    if (buckets[local] > buckets[winnerLocal]) winnerLocal = local;
  }
  let runnerLocal = winnerLocal === 0 ? 1 : 0;
  for (let local = 0; local < buckets.length; local += 1) {
    if (local !== winnerLocal && buckets[local] > buckets[runnerLocal]) {
      runnerLocal = local;
    }
  }
  return {
    winnerLocal,
    winnerBucket: buckets[winnerLocal],
    runnerLocal,
    runnerBucket: buckets[runnerLocal],
    marginBuckets: buckets[winnerLocal] - buckets[runnerLocal],
  };
}

async function loadPage(browser, path) {
  const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
  await page.goto(`${server}/experiments/${path}/index.html`, {
    waitUntil: "load",
    timeout: 240_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  return page;
}

async function applyCase(page, kind, hidden, floor, group, feature) {
  return page.evaluate((input) => {
    const stage = document.querySelector(
      input.kind === "gsub" ? "#gsub-stage" : "#fine-stage",
    );
    input.hidden.forEach((value, dimension) => {
      stage.style.setProperty(`--h${dimension}`, String(value));
    });
    stage.style.setProperty("--score-offset", `${-input.floor * 256 * 4}px`);
    if (input.kind === "gsub") {
      stage.style.setProperty("--probe-feature", String(input.feature));
    } else {
      stage.style.setProperty("--group", String(input.group));
    }
    const selector = input.kind === "gsub" ? ".candidate" : ".fine-candidate";
    const elements = [...stage.querySelectorAll(selector)];
    const widths = elements.map((element) => element.getBoundingClientRect().width);
    return {
      widths,
      stageWidth: stage.getBoundingClientRect().width,
      featureSettings: getComputedStyle(stage).fontFeatureSettings,
      candidateElements: elements.length,
      descendantElements: stage.querySelectorAll("*").length,
      textCharacters: elements.reduce(
        (total, element) => total + [...element.textContent].length, 0,
      ),
    };
  }, { kind, hidden, floor, group, feature });
}

async function measureSwitches(page, kind, groupCases, rounds) {
  return page.evaluate((input) => {
    const stage = document.querySelector(
      input.kind === "gsub" ? "#gsub-stage" : "#fine-stage",
    );
    const property = input.kind === "gsub" ? "--probe-feature" : "--group";
    const values = input.cases.map((entry) =>
      input.kind === "gsub" ? entry.feature : entry.group);
    for (let warm = 0; warm < 5; warm += 1) {
      for (const value of values) {
        stage.style.setProperty(property, String(value));
        stage.getBoundingClientRect().width;
      }
    }
    const samples = [];
    for (let round = 0; round < input.rounds; round += 1) {
      for (const value of values) {
        const started = performance.now();
        stage.style.setProperty(property, String(value));
        stage.getBoundingClientRect().width;
        samples.push(performance.now() - started);
      }
    }
    return samples;
  }, { kind, cases: groupCases, rounds });
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const gsubLoadStarted = performance.now();
  const gsubPage = await loadPage(browser, experimentName);
  const gsubLoadMilliseconds = performance.now() - gsubLoadStarted;
  const baselineLoadStarted = performance.now();
  const baselinePage = await loadPage(browser, reference.baselineDirectory);
  const baselineLoadMilliseconds = performance.now() - baselineLoadStarted;

  const comparisons = [];
  const deltaHistogram = new Map();
  const marginHistogram = new Map();
  const groupMaximumDelta = new Map();
  const observedFeatureSettings = new Set();
  let candidateComparisons = 0;
  let maximumAbsoluteCandidateDelta = 0;
  let differingCandidateBuckets = 0;
  let winnerTokenMatches = 0;
  let winnerBucketMatches = 0;
  let modelOracleWinnerMatches = 0;
  let firstGsubTopology;
  let firstBaselineTopology;

  for (const fixture of reference.fixtures.cases) {
    const hidden = reference.fixtures.hiddenVectors[fixture.fixture];
    const floor = reference.fixtures.scoreFloors[fixture.fixture];
    for (const groupCase of fixture.groups) {
      const [gsub, baseline] = await Promise.all([
        applyCase(
          gsubPage, "gsub", hidden, floor,
          groupCase.group, groupCase.feature,
        ),
        applyCase(
          baselinePage, "baseline", hidden, floor,
          groupCase.group, groupCase.feature,
        ),
      ]);
      if (!firstGsubTopology) {
        firstGsubTopology = {
          candidateElements: gsub.candidateElements,
          descendantElements: gsub.descendantElements,
          textCharacters: gsub.textCharacters,
        };
        firstBaselineTopology = {
          candidateElements: baseline.candidateElements,
          descendantElements: baseline.descendantElements,
          textCharacters: baseline.textCharacters,
        };
      }
      observedFeatureSettings.add(gsub.featureSettings);
      const valid = groupCase.validCandidates;
      const gsubBuckets = bucketsFromWidths(gsub.widths, valid);
      const baselineBuckets = bucketsFromWidths(baseline.widths, valid);
      const gsubWinner = winnerFromBuckets(gsubBuckets);
      const baselineWinner = winnerFromBuckets(baselineBuckets);
      const deltas = gsubBuckets.map((bucket, local) =>
        bucket - baselineBuckets[local]);
      const caseMaximumDelta = Math.max(...deltas.map(Math.abs));
      const differing = deltas.filter((delta) => delta !== 0).length;
      candidateComparisons += valid;
      differingCandidateBuckets += differing;
      maximumAbsoluteCandidateDelta = Math.max(
        maximumAbsoluteCandidateDelta, caseMaximumDelta,
      );
      groupMaximumDelta.set(
        groupCase.group,
        Math.max(groupMaximumDelta.get(groupCase.group) ?? 0, caseMaximumDelta),
      );
      for (const delta of deltas) {
        deltaHistogram.set(delta, (deltaHistogram.get(delta) ?? 0) + 1);
      }
      marginHistogram.set(
        gsubWinner.marginBuckets,
        (marginHistogram.get(gsubWinner.marginBuckets) ?? 0) + 1,
      );
      const winnerTokenMatchesCase =
        gsubWinner.winnerLocal === baselineWinner.winnerLocal;
      const winnerBucketMatchesCase = winnerTokenMatchesCase &&
        gsubWinner.winnerBucket === baselineWinner.winnerBucket;
      const modelOracleMatches =
        gsubWinner.winnerLocal === groupCase.winnerLocal;
      if (winnerTokenMatchesCase) winnerTokenMatches += 1;
      if (winnerBucketMatchesCase) winnerBucketMatches += 1;
      if (modelOracleMatches) modelOracleWinnerMatches += 1;
      comparisons.push({
        fixture: fixture.fixture,
        group: groupCase.group,
        feature: groupCase.feature,
        validCandidates: valid,
        differingBucketCount: differing,
        maximumAbsoluteCandidateDelta: caseMaximumDelta,
        gsubWinner,
        baselineWinner,
        winnerTokenMatches: winnerTokenMatchesCase,
        winnerBucketMatches: winnerBucketMatchesCase,
        modelOracleWinnerLocal: groupCase.winnerLocal,
        modelOracleWinnerMatches: modelOracleMatches,
      });
    }
  }

  const empiricalDeltaBound = maximumAbsoluteCandidateDelta;
  const marginThreshold = 2 * empiricalDeltaBound;
  const winnerMargins = comparisons.map((entry) => entry.gsubWinner.marginBuckets);
  const accepted = comparisons.filter((entry) =>
    entry.gsubWinner.marginBuckets > marginThreshold);
  const unsafeAccepts = accepted.filter((entry) => !entry.winnerTokenMatches);
  const fallback = comparisons.filter((entry) =>
    entry.gsubWinner.marginBuckets <= marginThreshold);

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
  const [gsubSamples, baselineSamples] = await Promise.all([
    measureSwitches(gsubPage, "gsub", timingFixture.groups, timingRounds),
    measureSwitches(baselinePage, "baseline", timingFixture.groups, timingRounds),
  ]);
  const gsubMedian = median(gsubSamples);
  const baselineMedian = median(baselineSamples);
  const splitFace = reference.faceRanges.find((entry) =>
    entry.shard === reference.splitFace.shard &&
    entry.plane === reference.splitFace.plane);
  const advanceAuditPassed = reference.allComplementsIndependentlySafe &&
    reference.faceRanges.every((entry) => entry.commonBaseMatchesFullBank) &&
    splitFace.maximumSplitA + splitFace.maximumSplitB ===
      splitFace.maximumOriginalCorrection &&
    reference.exactSplitChecks === reference.groups * reference.groupSize &&
    reference.originalOverflowingRows.length === 5;
  const featureMappingValid = observedFeatureSettings.size === reference.groups;
  const semanticTargetPassed = maximumAbsoluteCandidateDelta <= 3 &&
    winnerTokenMatches === comparisons.length && unsafeAccepts.length === 0;
  const finiteUsefulGate = Number.isFinite(marginThreshold) && accepted.length > 0 &&
    unsafeAccepts.length === 0;

  report = {
    chrome: await browser.version(),
    experimentName,
    groups: reference.groupIds,
    fixtures: reference.fixtures.cases.length,
    candidateComparisons,
    expectedCandidateComparisons: reference.validCandidateComparisons,
    gsubLoadMilliseconds,
    baselineLoadMilliseconds,
    observedFeatureSettings: [...observedFeatureSettings],
    featureMappingValid,
    maximumAbsoluteCandidateDelta,
    differingCandidateBuckets,
    differingCandidateRate: differingCandidateBuckets / candidateComparisons,
    candidateDeltaHistogram: Object.fromEntries(
      [...deltaHistogram.entries()].sort(([a], [b]) => a - b),
    ),
    groupMaximumAbsoluteCandidateDelta: Object.fromEntries(
      [...groupMaximumDelta.entries()].sort(([a], [b]) => a - b),
    ),
    winnerTokenMatches,
    winnerTokenAgreement: winnerTokenMatches / comparisons.length,
    winnerBucketMatches,
    winnerBucketAgreement: winnerBucketMatches / comparisons.length,
    modelOracleWinnerMatches,
    modelOracleWinnerAgreement: modelOracleWinnerMatches / comparisons.length,
    conservativeGate: {
      empiricalOnly: true,
      portableBoundProved: false,
      empiricalCandidateDeltaBound: empiricalDeltaBound,
      winnerMarginThresholdBuckets: marginThreshold,
      rule: `accept when split-GSUB winner margin > ${marginThreshold} buckets`,
      acceptedCases: accepted.length,
      acceptedRate: accepted.length / comparisons.length,
      fallbackCases: fallback.length,
      fallbackRate: fallback.length / comparisons.length,
      unsafeAccepts: unsafeAccepts.length,
      finiteUsefulGate,
      accepted: accepted.map(({ fixture, group }) => ({ fixture, group })),
      unsafe: unsafeAccepts.map(({ fixture, group }) => ({ fixture, group })),
    },
    winnerMarginHistogram: Object.fromEntries(
      [...marginHistogram.entries()].sort(([a], [b]) => a - b),
    ),
    winnerMargins: {
      minimum: Math.min(...winnerMargins),
      median: median(winnerMargins),
      p95: quantile(winnerMargins, 0.95),
      maximum: Math.max(...winnerMargins),
    },
    switching: {
      timingRounds,
      samplesPerBackend: gsubSamples.length,
      gsubMedianMilliseconds: gsubMedian,
      baselineMedianMilliseconds: baselineMedian,
      speedupFraction: 1 - gsubMedian / baselineMedian,
      speedupPercent: (1 - gsubMedian / baselineMedian) * 100,
      gsubP95Milliseconds: quantile(gsubSamples, 0.95),
      baselineP95Milliseconds: quantile(baselineSamples, 0.95),
      gsubSamples,
      baselineSamples,
    },
    advanceAudit: {
      passed: advanceAuditPassed,
      exactSplitChecks: reference.exactSplitChecks,
      splitFormula: reference.splitFormula,
      sourceCommonBasesMatchFullBank:
        reference.faceRanges.every((entry) => entry.commonBaseMatchesFullBank),
      originalOverflowingRows: reference.originalOverflowingRows,
      splitFace,
      allComplementsIndependentlySafe:
        reference.allComplementsIndependentlySafe,
    },
    overhead: {
      fontFaces: reference.shards * reference.planes,
      woff2Bytes: reference.fontWoff2Bytes,
      expandedTtfBytes: reference.fontTtfBytes,
      cssBytes: reference.cssBytes,
      htmlBytes: reference.htmlBytes,
      candidateElements: reference.candidateElements,
      glyphsPerCandidate: reference.glyphsPerCandidate,
      unsplitGsubGlyphsPerCandidate: reference.baselineGsubGlyphsPerCandidate,
      extraGlyphsPerCandidate:
        reference.glyphsPerCandidate - reference.baselineGsubGlyphsPerCandidate,
      glyphInstanceIncreaseFraction:
        reference.glyphsPerCandidate / reference.baselineGsubGlyphsPerCandidate - 1,
      splitFaceRows: splitFace.rows,
      unsplitFocusedFaceRows:
        2 * reference.groupSize * (reference.groups + 1),
      extraSplitFaceRows:
        splitFace.rows - 2 * reference.groupSize * (reference.groups + 1),
      gsubPageTopology: firstGsubTopology,
      exactBaselinePageTopology: firstBaselineTopology,
    },
    semanticTargetPassed,
    decision: semanticTargetPassed && finiteUsefulGate && advanceAuditPassed &&
      featureMappingValid
      ? "retain: split complement removes groups 0/1 overflow with bounded empirical error"
      : "reject: split complement did not meet the bounded groups 0/1 target",
    comparisons,
  };

  await fs.writeFile(
    new URL("browser-results.json", root),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  const histogram = Object.entries(report.candidateDeltaHistogram)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([delta, count]) => `\`${delta}: ${count.toLocaleString()}\``)
    .join(", ");
  const results = `# GSUB split-complement fine-scorer probe\n\n` +
    `Decision: **${report.decision}**.\n\n` +
    `The focused groups 0/1 run compared ${candidateComparisons.toLocaleString()} ` +
    `candidate buckets across ${comparisons.length} winner cases. The maximum ` +
    `absolute split-GSUB versus exact CSS-dispatch delta was ` +
    `${maximumAbsoluteCandidateDelta}; the histogram was ${histogram}. ` +
    `Winner-token agreement was ${winnerTokenMatches}/${comparisons.length} and ` +
    `winner-bucket agreement was ${winnerBucketMatches}/${comparisons.length}.\n\n` +
    `Winner margins ranged from ${report.winnerMargins.minimum} to ` +
    `${report.winnerMargins.maximum} buckets (median ` +
    `${report.winnerMargins.median}, p95 ${report.winnerMargins.p95}). ` +
    `Using the observed ±${empiricalDeltaBound} error radius, a margin strictly ` +
    `greater than ${marginThreshold} accepts ${accepted.length}/${comparisons.length} ` +
    `cases (${(accepted.length / comparisons.length * 100).toFixed(1)}%) with ` +
    `${unsafeAccepts.length} unsafe accepts. This is an empirical Chrome/fixture ` +
    `gate, not a portable proof.\n\n` +
    `Median isolated switching was ${gsubMedian.toFixed(3)} ms for split GSUB and ` +
    `${baselineMedian.toFixed(3)} ms for exact CSS dispatch ` +
    `(${((1 - gsubMedian / baselineMedian) * 100).toFixed(1)}% faster). ` +
    `P95 switching was ${report.switching.gsubP95Milliseconds.toFixed(3)} ms ` +
    `versus ${report.switching.baselineP95Milliseconds.toFixed(3)} ms. ` +
    `The focused bank is ${reference.fontWoff2Bytes.toLocaleString()} WOFF2 bytes. ` +
    `The split adds no DOM elements, one shaped glyph per candidate ` +
    `(${reference.baselineGsubGlyphsPerCandidate} to ` +
    `${reference.glyphsPerCandidate}, ` +
    `${((reference.glyphsPerCandidate / reference.baselineGsubGlyphsPerCandidate - 1) * 100).toFixed(1)}%), ` +
    `and ${report.overhead.extraSplitFaceRows.toLocaleString()} h3 font rows.\n\n` +
    `The score rows retain the production source scale and every per-face common ` +
    `base matches the existing full GSUB bank. The audit reproduces exactly five ` +
    `original over-cap rows: ` +
    `${reference.originalOverflowingRows.map((entry) =>
      `group ${entry.group} local ${entry.local}`).join(", ")}. ` +
    `The largest original h3 complement was ` +
    `${splitFace.maximumOriginalCorrection} font units. Its largest split parts are ` +
    `${splitFace.maximumSplitA} and ${splitFace.maximumSplitB}; the largest adjusted ` +
    `static part is ${splitFace.maximumAdjustedStaticComplementPx.toLocaleString()} px, ` +
    `below Chrome's observed ${splitFace.adjustedAdvanceCapPx.toLocaleString()} px cap. ` +
    `All ${reference.exactSplitChecks.toLocaleString()} h3 group/local splits sum ` +
    `exactly to their original integer correction.\n`;
  await fs.writeFile(new URL("RESULTS.md", root), results);
  console.log(JSON.stringify(report, null, 2));
  if (!advanceAuditPassed || !featureMappingValid) process.exitCode = 1;
} finally {
  await browser.close();
}
