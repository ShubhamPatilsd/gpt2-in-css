import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const root = new URL("../experiments/gsub-merged-base-fine-scorer/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));
const server = process.env.GSUB_MERGED_BASE_SERVER ?? "http://127.0.0.1:4178";
const timingRounds = Number.parseInt(process.env.GSUB_MERGED_BASE_TIMING_ROUNDS ?? "15", 10);

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
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
  return { winnerLocal, winnerBucket: buckets[winnerLocal] };
}

async function loadPage(browser, relativePath) {
  const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
  const started = performance.now();
  await page.goto(`${server}/experiments/${relativePath}`, {
    waitUntil: "load",
    timeout: 240_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  return { page, loadMilliseconds: performance.now() - started };
}

async function applyCase(page, kind, hidden, floor, groupCase) {
  return page.evaluate(({ pageKind, values, scoreFloor, group, feature }) => {
    const selectors = {
      merged: ["#gsub-stage", ".candidate", "--probe-feature", feature],
      baseline: ["#fine-stage", ".fine-candidate", "--group", group],
      matched: ["#exact-stage", ".exact-candidate", "--group", group],
    };
    const [stageSelector, candidateSelector, property, propertyValue] = selectors[pageKind];
    const stage = document.querySelector(stageSelector);
    values.forEach((value, dimension) => {
      stage.style.setProperty(`--h${dimension}`, String(value));
    });
    stage.style.setProperty("--score-offset", `${-scoreFloor * 256 * 4}px`);
    stage.style.setProperty(property, String(propertyValue));
    const widths = [...stage.querySelectorAll(candidateSelector)].map((element) =>
      element.getBoundingClientRect().width);
    return {
      widths,
      stageWidth: stage.getBoundingClientRect().width,
      featureSettings: getComputedStyle(stage).fontFeatureSettings,
      candidateNodes: stage.querySelectorAll(candidateSelector).length,
    };
  }, {
    pageKind: kind,
    values: hidden,
    scoreFloor: floor,
    group: groupCase.group,
    feature: groupCase.feature,
  });
}

async function measureSwitches(page, kind, groupCases, rounds) {
  return page.evaluate(({ pageKind, cases, count }) => {
    const config = {
      merged: ["#gsub-stage", "--probe-feature", "feature"],
      baseline: ["#fine-stage", "--group", "group"],
      matched: ["#exact-stage", "--group", "group"],
    }[pageKind];
    const stage = document.querySelector(config[0]);
    const values = cases.map((entry) => entry[config[2]]);
    for (let warm = 0; warm < 3; warm += 1) {
      for (const value of values) {
        stage.style.setProperty(config[1], String(value));
        stage.getBoundingClientRect().width;
      }
    }
    const samples = [];
    for (let round = 0; round < count; round += 1) {
      for (const value of values) {
        const started = performance.now();
        stage.style.setProperty(config[1], String(value));
        stage.getBoundingClientRect().width;
        samples.push(performance.now() - started);
      }
    }
    return samples;
  }, { pageKind: kind, cases: groupCases, count: rounds });
}

function createComparisonAccumulator(name) {
  return {
    name,
    candidateComparisons: 0,
    differingCandidateBuckets: 0,
    maximumAbsoluteCandidateDelta: 0,
    deltaHistogram: new Map(),
    winnerTokenMatches: 0,
    winnerBucketMatches: 0,
    cases: [],
  };
}

function compareCase(accumulator, fixture, groupCase, actualBuckets, expectedBuckets) {
  const deltas = actualBuckets.map((bucket, local) => bucket - expectedBuckets[local]);
  for (const delta of deltas) {
    accumulator.candidateComparisons += 1;
    if (delta !== 0) accumulator.differingCandidateBuckets += 1;
    accumulator.maximumAbsoluteCandidateDelta = Math.max(
      accumulator.maximumAbsoluteCandidateDelta,
      Math.abs(delta),
    );
    accumulator.deltaHistogram.set(delta, (accumulator.deltaHistogram.get(delta) ?? 0) + 1);
  }
  const actualWinner = winnerFromBuckets(actualBuckets);
  const expectedWinner = winnerFromBuckets(expectedBuckets);
  const tokenMatches = actualWinner.winnerLocal === expectedWinner.winnerLocal;
  const bucketMatches = tokenMatches && actualWinner.winnerBucket === expectedWinner.winnerBucket;
  if (tokenMatches) accumulator.winnerTokenMatches += 1;
  if (bucketMatches) accumulator.winnerBucketMatches += 1;
  accumulator.cases.push({
    fixture,
    group: groupCase.group,
    validCandidates: groupCase.validCandidates,
    differingCandidateBuckets: deltas.filter((delta) => delta !== 0).length,
    maximumAbsoluteCandidateDelta: Math.max(...deltas.map(Math.abs)),
    actualWinner,
    expectedWinner,
  });
}

function finalizeComparison(accumulator) {
  const cases = accumulator.cases.length;
  return {
    name: accumulator.name,
    candidateComparisons: accumulator.candidateComparisons,
    differingCandidateBuckets: accumulator.differingCandidateBuckets,
    maximumAbsoluteCandidateDelta: accumulator.maximumAbsoluteCandidateDelta,
    deltaHistogram: Object.fromEntries(
      [...accumulator.deltaHistogram.entries()].sort(([a], [b]) => a - b),
    ),
    winnerTokenMatches: accumulator.winnerTokenMatches,
    winnerTokenAgreement: accumulator.winnerTokenMatches / cases,
    winnerBucketMatches: accumulator.winnerBucketMatches,
    winnerBucketAgreement: accumulator.winnerBucketMatches / cases,
    exact: accumulator.maximumAbsoluteCandidateDelta === 0,
    cases: accumulator.cases,
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const [safe, sourceScale, matched, baseline] = await Promise.all([
    loadPage(browser, "gsub-merged-base-fine-scorer/index.html"),
    loadPage(browser, "gsub-merged-base-fine-scorer/source-scale.html"),
    loadPage(browser, "gsub-merged-base-fine-scorer/matched-exact.html"),
    loadPage(browser, `${reference.baselineDirectory}/index.html`),
  ]);
  const primaryAccumulator = createComparisonAccumulator("safe merged vs existing exact baseline");
  const matchedAccumulator = createComparisonAccumulator("safe merged vs matched-scale exact audit");
  const sourceAccumulator = createComparisonAccumulator("source-scale merged vs existing exact baseline");
  const observedFeatureSettings = new Set();
  const firstFixtureGroupBuckets = [];
  let candidateNodes = null;

  for (const fixture of reference.fixtures.cases) {
    const hidden = reference.fixtures.hiddenVectors[fixture.fixture];
    const floor = reference.fixtures.scoreFloors[fixture.fixture];
    for (const groupCase of fixture.groups) {
      const [safeCase, sourceCase, matchedCase, baselineCase] = await Promise.all([
        applyCase(safe.page, "merged", hidden, floor, groupCase),
        applyCase(sourceScale.page, "merged", hidden, floor, groupCase),
        applyCase(matched.page, "matched", hidden, floor, groupCase),
        applyCase(baseline.page, "baseline", hidden, floor, groupCase),
      ]);
      observedFeatureSettings.add(safeCase.featureSettings);
      candidateNodes ??= safeCase.candidateNodes;
      const valid = groupCase.validCandidates;
      const safeBuckets = bucketsFromWidths(safeCase.widths, valid);
      const sourceBuckets = bucketsFromWidths(sourceCase.widths, valid);
      const matchedBuckets = bucketsFromWidths(matchedCase.widths, valid);
      const baselineBuckets = bucketsFromWidths(baselineCase.widths, valid);
      compareCase(
        primaryAccumulator, fixture.fixture, groupCase, safeBuckets, baselineBuckets,
      );
      compareCase(
        matchedAccumulator, fixture.fixture, groupCase, safeBuckets, matchedBuckets,
      );
      compareCase(
        sourceAccumulator, fixture.fixture, groupCase, sourceBuckets, baselineBuckets,
      );
      if (fixture.fixture === 0) firstFixtureGroupBuckets.push(safeBuckets);
    }
  }

  const primary = finalizeComparison(primaryAccumulator);
  const matchedScaleAudit = finalizeComparison(matchedAccumulator);
  const sourceScaleAudit = finalizeComparison(sourceAccumulator);
  for (const comparison of [primary, matchedScaleAudit, sourceScaleAudit]) {
    if (comparison.candidateComparisons !== reference.expectedCandidateBuckets) {
      throw new Error(
        `${comparison.name}: compared ${comparison.candidateComparisons}, expected ` +
        `${reference.expectedCandidateBuckets}`,
      );
    }
  }
  const changedAcrossGroups = firstFixtureGroupBuckets.slice(1).some((buckets, index) =>
    buckets.some((bucket, local) => bucket !== firstFixtureGroupBuckets[index][local]));
  const dynamicFeatureValid =
    observedFeatureSettings.size === reference.groups && changedAcrossGroups;

  const timingFixture = reference.fixtures.cases[0];
  const timingHidden = reference.fixtures.hiddenVectors[0];
  const timingFloor = reference.fixtures.scoreFloors[0];
  await Promise.all([
    applyCase(safe.page, "merged", timingHidden, timingFloor, timingFixture.groups[0]),
    applyCase(baseline.page, "baseline", timingHidden, timingFloor, timingFixture.groups[0]),
  ]);
  const [mergedSamples, baselineSamples] = await Promise.all([
    measureSwitches(safe.page, "merged", timingFixture.groups, timingRounds),
    measureSwitches(baseline.page, "baseline", timingFixture.groups, timingRounds),
  ]);
  const mergedMedian = median(mergedSamples);
  const baselineMedian = median(baselineSamples);
  const speedupFraction = 1 - mergedMedian / baselineMedian;
  const speedGatePassed = speedupFraction >= 0.25;
  const semanticsPassed = primary.exact && matchedScaleAudit.exact &&
    primary.winnerTokenAgreement === 1 && primary.winnerBucketAgreement === 1;
  const hardGatePassed = dynamicFeatureValid && semanticsPassed && speedGatePassed;
  const projectedFullWoff2Bytes = reference.projectedMergedFullWoff2Bytes;
  const fullBuildReasonable = hardGatePassed && projectedFullWoff2Bytes < 50_000_000;

  report = {
    chrome: await browser.version(),
    boundedOnly: true,
    groups: reference.groupIds,
    fixtures: reference.fixtures.cases.length,
    expectedCandidateBuckets: reference.expectedCandidateBuckets,
    numberedFeature: reference.feature,
    observedFeatureSettings: [...observedFeatureSettings],
    changedAcrossGroups,
    dynamicFeatureValid,
    displayScales: {
      source: reference.sourceDisplayScale,
      safe: reference.safeDisplayScale,
      safeLowLayoutUnitsPerFontUnit: reference.safeScaleLayoutUnitsPerLowFontUnit,
      safeHighLayoutUnitsPerFontUnit: reference.safeScaleLayoutUnitsPerHighFontUnit,
    },
    advanceCeilingAudit: reference.boundedHighPlaneAdvanceAudit,
    existingExactAdvanceCeilingAudit: reference.existingExactHighPlaneAdvanceAudit,
    primary,
    matchedScaleAudit,
    sourceScaleAudit,
    semanticsPassed,
    timingRounds,
    isolatedGroupSwitch: {
      mergedMedianMilliseconds: mergedMedian,
      baselineMedianMilliseconds: baselineMedian,
      speedupFraction,
      speedupPercent: speedupFraction * 100,
      gatePercent: 25,
      gatePassed: speedGatePassed,
      mergedSamples,
      baselineSamples,
    },
    loads: {
      safeMergedMilliseconds: safe.loadMilliseconds,
      sourceScaleMergedMilliseconds: sourceScale.loadMilliseconds,
      matchedExactMilliseconds: matched.loadMilliseconds,
      existingExactMilliseconds: baseline.loadMilliseconds,
    },
    sizes: {
      fontWoff2Bytes: reference.fontWoff2Bytes,
      fontTtfBytes: reference.fontTtfBytes,
      generatedMarkupCssBytes: reference.generatedMarkupCssBytes,
      primaryHtmlBytes: reference.htmlBytes,
      primaryCssBytes: reference.cssBytes,
      candidateNodes,
      glyphsPerCandidate: reference.glyphsPerCandidate,
      sourceGlyphsPerCandidate: reference.sourceGlyphsPerCandidate,
    },
    fullScaleDisposition: {
      consideredBecauseBoundedExact: hardGatePassed,
      projectedWoff2Bytes: projectedFullWoff2Bytes,
      reasonableUnder50MbGate: fullBuildReasonable,
      built: false,
      reason: hardGatePassed
        ? (fullBuildReasonable
          ? "bounded pass; full build would be permitted but was not requested by the measured gate"
          : "bounded pass, but the existing full GSUB bank projects to 82.5 MB WOFF2")
        : (semanticsPassed
          ? "bounded speed gate failed"
          : "bounded exactness failed; full construction is not justified"),
    },
    hardGatePassed,
    decision: hardGatePassed
      ? "retain bounded; full build deferred by storage gate"
      : "reject pure GSUB merged-base path at bounded scale",
  };
  await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);

  const sourceOverflowFaces = reference.boundedHighPlaneAdvanceAudit.filter(
    (entry) => entry.sourceScaleExceedsCeiling).length;
  const exactOverflowMeasurements = reference.existingExactHighPlaneAdvanceAudit.reduce(
    (sum, entry) => sum + entry.overflowingMeasurements, 0);
  const exactOverflowRows = reference.existingExactHighPlaneAdvanceAudit.reduce(
    (sum, entry) => sum + entry.tokenRowsOverflowingAtLeastOnce, 0);
  const results = `# GSUB merged-base fine-scorer probe\n\n` +
    `Decision: **${report.decision}**.\n\n` +
    `This bounded probe patches each selectable score glyph's hmtx advance to the sum of ` +
    `its original score and zero-HVAR complement advances. GSUB and HVAR table digests are ` +
    `unchanged, and the page renders one glyph per face instead of score-plus-complement.\n\n` +
    `## Semantic result\n\n` +
    `The primary comparison against the existing exact CSS-dispatch baseline covered ` +
    `${primary.candidateComparisons.toLocaleString()} candidate buckets and 80 winners. ` +
    `${primary.differingCandidateBuckets.toLocaleString()} buckets differed; maximum absolute ` +
    `delta was ${primary.maximumAbsoluteCandidateDelta}. Winner-token agreement was ` +
    `${(primary.winnerTokenAgreement * 100).toFixed(2)}% and winner-bucket agreement was ` +
    `${(primary.winnerBucketAgreement * 100).toFixed(2)}%.\n\n` +
    `At the same safe scale, merged GSUB versus a matched exact CSS-dispatch audit had ` +
    `${matchedScaleAudit.differingCandidateBuckets.toLocaleString()} differing buckets, maximum ` +
    `delta ${matchedScaleAudit.maximumAbsoluteCandidateDelta}, and ` +
    `${(matchedScaleAudit.winnerTokenAgreement * 100).toFixed(2)}% winner-token agreement ` +
    `(${matchedScaleAudit.winnerBucketMatches}/80 winner buckets). ` +
    `This separates merge error from any scale-induced difference relative to the existing ` +
    `0.1-scale baseline.\n\n` +
    `## Advance ceiling and remedy\n\n` +
    `At display scale 0.1, ${sourceOverflowFaces}/6 high-plane faces exceed Chrome's ` +
    `${reference.chromeAdvanceCeilingPx.toLocaleString()} px adjusted-advance ceiling on these fixtures. ` +
    `That source-scale diagnostic had ${sourceScaleAudit.differingCandidateBuckets.toLocaleString()} ` +
    `differing buckets and maximum delta ${sourceScaleAudit.maximumAbsoluteCandidateDelta}. ` +
    `The primary probe uses display scale ${reference.safeDisplayScale}; each low-plane font unit is ` +
    `${reference.safeScaleLayoutUnitsPerLowFontUnit} layout-grid units and each high-plane unit is ` +
    `${reference.safeScaleLayoutUnitsPerHighFontUnit}, while the inverse geometry factor preserves the ` +
    `same mathematical score target. All bounded fixture advances clear the ceiling. This is not a ` +
    `proof for every corner of the normalized 768-axis cube. The existing 0.1-scale exact comparator ` +
    `also has ${exactOverflowMeasurements.toLocaleString()} high-face candidate/fixture advances over ` +
    `the ceiling across ${exactOverflowRows.toLocaleString()} face-local token rows. Therefore lowering ` +
    `the scale removes clamp behavior that is part of that browser baseline; the large primary deltas ` +
    `are a semantic change, not an arithmetic rescaling bug.\n\n` +
    `## Runtime and size\n\n` +
    `Median isolated group switching was ${mergedMedian.toFixed(3)} ms for merged GSUB and ` +
    `${baselineMedian.toFixed(3)} ms for existing exact CSS dispatch ` +
    `(${(speedupFraction * 100).toFixed(1)}% speedup; 25% required). The bounded fonts occupy ` +
    `${reference.fontWoff2Bytes.toLocaleString()} WOFF2 bytes and ` +
    `${reference.fontTtfBytes.toLocaleString()} expanded TTF bytes. The primary DOM has ` +
    `${candidateNodes} candidate nodes and ${reference.glyphsPerCandidate} glyphs per candidate ` +
    `(versus ${reference.sourceGlyphsPerCandidate} in the score-plus-complement source).\n\n` +
    `## Full-scale disposition\n\n` +
    `${report.fullScaleDisposition.reason[0].toUpperCase()}${report.fullScaleDisposition.reason.slice(1)}. ` +
    `No full bank was built. A score-only merged full bank ` +
    `would project to roughly ${projectedFullWoff2Bytes.toLocaleString()} WOFF2 bytes from the ` +
    `existing full score fonts, before any further size optimization.\n`;
  await fs.writeFile(new URL("RESULTS.md", root), results);
  console.log(JSON.stringify(report, null, 2));
  if (!hardGatePassed) process.exitCode = 1;
} finally {
  await browser.close();
}
