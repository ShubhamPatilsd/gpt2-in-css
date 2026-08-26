import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const experimentName = "cmap14-indexed-fine-scorer";
const timingRounds = Number.parseInt(process.env.CMAP14_FINE_SCORER_TIMING_ROUNDS ?? "15", 10);
const root = new URL(`../experiments/${experimentName}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));
const server = process.env.CMAP14_FINE_SCORER_SERVER ?? "http://127.0.0.1:4178";

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

function tiedWinnerLocals(buckets) {
  const maximum = Math.max(...buckets);
  return buckets.flatMap((bucket, local) => bucket === maximum ? [local] : []);
}

function arraysEqual(left, right) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
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

async function applyCase(page, kind, hidden, floor, group, groupIndex) {
  return page.evaluate(({ pageKind, values, scoreFloor, groupId, localGroupIndex }) => {
    const stage = document.querySelector(pageKind === "cmap14" ? "#cmap14-stage" : "#fine-stage");
    values.forEach((value, dimension) => {
      stage.style.setProperty(`--h${dimension}`, String(value));
    });
    stage.style.setProperty("--score-offset", `${-scoreFloor * 256 * 4}px`);
    if (pageKind === "cmap14") {
      stage.dataset.group = String(localGroupIndex);
    } else {
      stage.style.setProperty("--group", String(groupId));
    }
    const selector = pageKind === "cmap14" ? ".cmap-candidate" : ".fine-candidate";
    const widths = [...stage.querySelectorAll(selector)].map((element) =>
      element.getBoundingClientRect().width);
    return {
      widths,
      stageWidth: stage.getBoundingClientRect().width,
      activeGroup: pageKind === "cmap14" ? stage.dataset.group : String(groupId),
    };
  }, { pageKind: kind, values: hidden, scoreFloor: floor, groupId: group, localGroupIndex: groupIndex });
}

async function auditSequences(page, groupIndex, expectedBases, selectors, advanceCeiling) {
  return page.evaluate(({ activeGroup, bases, variationSelectors, ceiling }) => {
    const stage = document.querySelector("#cmap14-stage");
    stage.dataset.group = String(activeGroup);
    const candidates = [...stage.querySelectorAll(".cmap-candidate")];
    let unsupportedSequences = 0;
    let splitSequences = 0;
    let malformedSequences = 0;
    let faceSequenceMeasurements = 0;
    let minimumPairWidth = Number.POSITIVE_INFINITY;
    let maximumPairWidth = 0;
    let saturatedPairWidths = 0;
    const samples = [];
    const stageStyle = getComputedStyle(stage);
    const inheritedBasesPresent = bases.every((base, face) => {
      const value = stageStyle.getPropertyValue(`--base-${face}`).trim();
      return value !== "" && Number.isInteger(base);
    });
    if (!inheritedBasesPresent) malformedSequences += candidates.length;
    for (let local = 0; local < candidates.length; local += 1) {
      const candidate = candidates[local];
      const spans = [...candidate.querySelectorAll(".face-sequence")];
      const selectorValue = getComputedStyle(candidate).getPropertyValue("--selector").trim();
      if (spans.length !== bases.length || selectorValue === "") malformedSequences += 1;
      let firstPairWidth = null;
      let firstContent = null;
      for (const span of spans) {
        const generated = getComputedStyle(span, "::before");
        const content = generated.content;
        if (getComputedStyle(span).display !== "contents") malformedSequences += 1;
        // The production carrier is display:contents to avoid a per-face
        // 32768px inline-box clamp. Temporarily materialize only this carrier
        // as an inline box to prove that its generated UVS maps to a nonzero
        // score glyph, then restore the scalable topology before timing.
        span.style.display = "inline";
        const pairWidth = span.getBoundingClientRect().width;
        span.style.removeProperty("display");
        faceSequenceMeasurements += 1;
        minimumPairWidth = Math.min(minimumPairWidth, pairWidth);
        maximumPairWidth = Math.max(maximumPairWidth, pairWidth);
        if (pairWidth >= ceiling) saturatedPairWidths += 1;
        if (content === "none" || content === "normal" || content === "") {
          unsupportedSequences += 1;
        }
        // Every ordinary base maps to a zero-width sentinel. Positive width is
        // therefore direct evidence that base+VS shaped through cmap format 14
        // as one mapped score glyph instead of remaining unsupported or split.
        if (!(pairWidth > 0)) splitSequences += 1;
        if (firstPairWidth === null) {
          firstPairWidth = pairWidth;
          firstContent = content;
        }
      }
      if (samples.length < 4) {
        samples.push({
          local,
          selector: variationSelectors[local],
          generatedContent: firstContent,
          pairWidth: firstPairWidth,
        });
      }
    }
    return {
      groupIndex: activeGroup,
      candidates: candidates.length,
      faceSequenceMeasurements,
      minimumPairWidth,
      maximumPairWidth,
      saturatedPairWidths,
      unsupportedSequences,
      splitSequences,
      malformedSequences,
      samples,
    };
  }, {
    activeGroup: groupIndex,
    bases: expectedBases,
    variationSelectors: selectors,
    ceiling: advanceCeiling,
  });
}

async function measureSwitches(page, kind, groupCases, rounds) {
  return page.evaluate(({ pageKind, cases, count }) => {
    const stage = document.querySelector(pageKind === "cmap14" ? "#cmap14-stage" : "#fine-stage");
    const values = cases.map((entry) => pageKind === "cmap14" ? entry.groupIndex : entry.group);
    const apply = pageKind === "cmap14"
      ? (value) => { stage.dataset.group = String(value); }
      : (value) => { stage.style.setProperty("--group", String(value)); };
    for (let warm = 0; warm < 3; warm += 1) {
      for (const value of values) {
        apply(value);
        stage.getBoundingClientRect().width;
      }
    }
    const samples = [];
    for (let round = 0; round < count; round += 1) {
      for (const value of values) {
        const started = performance.now();
        apply(value);
        stage.getBoundingClientRect().width;
        samples.push(performance.now() - started);
      }
    }
    return samples;
  }, { pageKind: kind, cases: groupCases, count: rounds });
}

if (reference.groups !== 8 || reference.groupIds.length !== 8) {
  throw new Error("CMAP14 probe must remain exactly eight groups");
}
const expectedSelectors = [
  ...Array.from({ length: 16 }, (_, index) => 0xFE00 + index),
  ...Array.from({ length: 240 }, (_, index) => 0xE0100 + index),
];
if (!arraysEqual(reference.variationSelectors, expectedSelectors)) {
  throw new Error("reference does not contain the exact 256 standardized/supplementary selectors");
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const loadStarted = performance.now();
  const cmapPage = await loadPage(browser, experimentName);
  const cmapLoadMilliseconds = performance.now() - loadStarted;
  const baselineLoadStarted = performance.now();
  const baselinePage = await loadPage(browser, reference.baselineDirectory);
  const baselineLoadMilliseconds = performance.now() - baselineLoadStarted;

  const comparisons = [];
  const failures = [];
  const sequenceAudits = [];
  const observedGroups = new Set();
  const deltaHistogram = new Map();
  let maximumAbsoluteCandidateDelta = 0;
  let candidateComparisons = 0;
  let winnerMatches = 0;
  let winnerBucketMatches = 0;
  let tieCases = 0;
  let tieSetMatches = 0;
  let changedAcrossGroups = false;
  let previousFirstFixtureBuckets = null;

  for (const fixture of reference.fixtures.cases) {
    const hidden = reference.fixtures.hiddenVectors[fixture.fixture];
    const floor = reference.fixtures.scoreFloors[fixture.fixture];
    for (const groupCase of fixture.groups) {
      const cmap = await applyCase(
        cmapPage, "cmap14", hidden, floor, groupCase.group, groupCase.groupIndex,
      );
      const baseline = await applyCase(
        baselinePage, "baseline", hidden, floor, groupCase.group, groupCase.groupIndex,
      );
      observedGroups.add(cmap.activeGroup);
      const valid = groupCase.validCandidates;
      const cmapBuckets = bucketsFromWidths(cmap.widths, valid);
      const baselineBuckets = bucketsFromWidths(baseline.widths, valid);
      const cmapWinner = winnerFromWidths(cmap.widths, valid);
      const baselineWinner = winnerFromWidths(baseline.widths, valid);
      const cmapTies = tiedWinnerLocals(cmapBuckets);
      const baselineTies = tiedWinnerLocals(baselineBuckets);
      if (baselineTies.length > 1) {
        tieCases += 1;
        if (arraysEqual(cmapTies, baselineTies)) tieSetMatches += 1;
      }
      const differingBuckets = [];
      let caseMaximumAbsoluteDelta = 0;
      for (let local = 0; local < valid; local += 1) {
        const delta = cmapBuckets[local] - baselineBuckets[local];
        candidateComparisons += 1;
        caseMaximumAbsoluteDelta = Math.max(caseMaximumAbsoluteDelta, Math.abs(delta));
        maximumAbsoluteCandidateDelta = Math.max(maximumAbsoluteCandidateDelta, Math.abs(delta));
        deltaHistogram.set(delta, (deltaHistogram.get(delta) ?? 0) + 1);
        if (delta !== 0) differingBuckets.push(local);
      }
      if (fixture.fixture === 0) {
        if (previousFirstFixtureBuckets && cmapBuckets.some(
          (bucket, local) => bucket !== previousFirstFixtureBuckets[local])) {
          changedAcrossGroups = true;
        }
        previousFirstFixtureBuckets = cmapBuckets;
        const expectedBases = reference.faceRanges.map(
          (face) => face.baseCodepoints[groupCase.groupIndex],
        );
        sequenceAudits.push(await auditSequences(
          cmapPage,
          groupCase.groupIndex,
          expectedBases,
          reference.variationSelectors,
          reference.chromeAdvanceCeilingPx,
        ));
      }
      const winnerMatchesCase = cmapWinner.winnerLocal === baselineWinner.winnerLocal;
      const winnerBucketMatchesCase = winnerMatchesCase &&
        cmapWinner.winnerBucket === baselineWinner.winnerBucket;
      if (winnerMatchesCase) winnerMatches += 1;
      if (winnerBucketMatchesCase) winnerBucketMatches += 1;
      if (caseMaximumAbsoluteDelta > reference.existingBoundedBucketDelta || !winnerMatchesCase) {
        failures.push({
          fixture: fixture.fixture,
          group: groupCase.group,
          differingBuckets: differingBuckets.slice(0, 16),
          differingBucketCount: differingBuckets.length,
          maximumAbsoluteCandidateDelta: caseMaximumAbsoluteDelta,
          cmapWinner,
          baselineWinner,
          cmapTies,
          baselineTies,
        });
      }
      comparisons.push({
        fixture: fixture.fixture,
        group: groupCase.group,
        groupIndex: groupCase.groupIndex,
        validCandidates: valid,
        differingBucketCount: differingBuckets.length,
        maximumAbsoluteCandidateDelta: caseMaximumAbsoluteDelta,
        cmapWinner,
        baselineWinner,
        cmapTies,
        baselineTies,
        modelOracleWinnerLocal: groupCase.winnerLocal,
        modelOracleWinnerBucket: groupCase.winnerBucket,
      });
    }
  }

  const unsupportedSequences = sequenceAudits.reduce(
    (sum, audit) => sum + audit.unsupportedSequences, 0,
  );
  const splitSequences = sequenceAudits.reduce((sum, audit) => sum + audit.splitSequences, 0);
  const malformedSequences = sequenceAudits.reduce(
    (sum, audit) => sum + audit.malformedSequences, 0,
  );
  const sequenceMappingValid = unsupportedSequences === 0 && splitSequences === 0 &&
    malformedSequences === 0;
  const topologyValid = reference.topology.candidateElements === 256 &&
    reference.topology.faceSpans === 12 * 256 &&
    reference.topology.groupSpecificDomElements === 0 &&
    sequenceAudits.every((audit) =>
      audit.candidates === 256 && audit.faceSequenceMeasurements === 12 * 256);
  const maximumAuditedFaceWidth = Math.max(
    ...sequenceAudits.map((audit) => audit.maximumPairWidth),
  );
  const saturatedPairWidths = sequenceAudits.reduce(
    (sum, audit) => sum + audit.saturatedPairWidths, 0,
  );
  const faceWidthCeilingPassed = saturatedPairWidths === 0 &&
    maximumAuditedFaceWidth < reference.chromeAdvanceCeilingPx &&
    reference.maximumFixtureFaceWidthPx < reference.chromeAdvanceCeilingPx;
  if (!sequenceMappingValid) {
    failures.push({ unsupportedSequences, splitSequences, malformedSequences });
  }
  if (!topologyValid) failures.push({ topologyValid, topology: reference.topology });
  if (!faceWidthCeilingPassed) {
    failures.push({
      faceWidthCeilingPassed,
      maximumAuditedFaceWidth,
      maximumFixtureFaceWidthPx: reference.maximumFixtureFaceWidthPx,
      ceiling: reference.chromeAdvanceCeilingPx,
      saturatedPairWidths,
    });
  }

  const timingFixture = reference.fixtures.cases[0];
  const timingHidden = reference.fixtures.hiddenVectors[0];
  const timingFloor = reference.fixtures.scoreFloors[0];
  await applyCase(
    cmapPage, "cmap14", timingHidden, timingFloor,
    timingFixture.groups[0].group, timingFixture.groups[0].groupIndex,
  );
  await applyCase(
    baselinePage, "baseline", timingHidden, timingFloor,
    timingFixture.groups[0].group, timingFixture.groups[0].groupIndex,
  );
  const cmapSwitchMilliseconds = await measureSwitches(
    cmapPage, "cmap14", timingFixture.groups, timingRounds,
  );
  const baselineSwitchMilliseconds = await measureSwitches(
    baselinePage, "baseline", timingFixture.groups, timingRounds,
  );
  const cmapMedian = median(cmapSwitchMilliseconds);
  const baselineMedian = median(baselineSwitchMilliseconds);
  const speedupFraction = 1 - cmapMedian / baselineMedian;
  const dynamicGroupValid = observedGroups.size === reference.groups && changedAcrossGroups;
  const boundedDeltaPassed =
    maximumAbsoluteCandidateDelta <= reference.existingBoundedBucketDelta;
  const exactOutputPassed = maximumAbsoluteCandidateDelta === 0;
  const winnerAgreement = winnerMatches / comparisons.length;
  const winnerBucketAgreement = winnerBucketMatches / comparisons.length;
  const speedGatePassed = speedupFraction >= 0.25;
  const hardGatePassed = topologyValid && sequenceMappingValid && faceWidthCeilingPassed &&
    dynamicGroupValid && exactOutputPassed &&
    winnerAgreement === 1 && speedGatePassed;

  report = {
    chrome: await browser.version(),
    experimentName,
    groups: reference.groupIds,
    fixtures: reference.fixtures.cases.length,
    candidateComparisons,
    cmapLoadMilliseconds,
    baselineLoadMilliseconds,
    selectorCoverage: {
      standardizedBmpSelectors: 16,
      supplementarySelectors: 240,
      totalSelectors: reference.variationSelectors.length,
      intendedSequences: reference.groups * reference.variationSelectors.length *
        reference.faceRanges.length,
      auditedFaceSequences: sequenceAudits.reduce(
        (sum, audit) => sum + audit.faceSequenceMeasurements, 0,
      ),
      unsupportedSequences,
      splitSequences,
      malformedSequences,
      valid: sequenceMappingValid,
      audits: sequenceAudits,
    },
    faceWidthCeiling: {
      displayScale: reference.displayScale,
      fontSizePx: reference.fontSizePx,
      ceilingPx: reference.chromeAdvanceCeilingPx,
      maximumFixtureFaceWidthPx: reference.maximumFixtureFaceWidthPx,
      maximumTheoreticalFaceWidthPx: reference.maximumTheoreticalFaceWidthPx,
      maximumAuditedFaceWidthPx: maximumAuditedFaceWidth,
      saturatedPairWidths,
      passed: faceWidthCeilingPassed,
    },
    topology: {
      ...reference.topology,
      valid: topologyValid,
    },
    observedGroups: [...observedGroups].map(Number).sort((a, b) => a - b),
    changedAcrossGroups,
    dynamicGroupValid,
    existingBoundedBucketDelta: reference.existingBoundedBucketDelta,
    maximumAbsoluteCandidateDelta,
    candidateDeltaHistogram: Object.fromEntries(
      [...deltaHistogram.entries()].sort(([a], [b]) => a - b),
    ),
    boundedDeltaPassed,
    exactOutputPassed,
    winnerMatches,
    winnerAgreement,
    winnerBucketMatches,
    winnerBucketAgreement,
    tieCases,
    tieSetMatches,
    tieSetAgreement: tieCases === 0 ? null : tieSetMatches / tieCases,
    failures,
    timingRounds,
    isolatedGroupSwitch: {
      cmapMedianMilliseconds: cmapMedian,
      baselineMedianMilliseconds: baselineMedian,
      speedupFraction,
      speedupPercent: speedupFraction * 100,
      gatePercent: 25,
      gatePassed: speedGatePassed,
      cmapSamples: cmapSwitchMilliseconds,
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
    finalDecision: hardGatePassed ? "retain-for-full-scale" : "reject",
    fullScaleBuildAuthorized: hardGatePassed,
    decision: hardGatePassed
      ? "retain for full-scale: exact bounded eight-group CMAP14 probe passed"
      : (!topologyValid || !sequenceMappingValid
        ? "reject: no scalable declarative CSS-controlled CMAP14 sequence path"
        : "final reject: half-scale exactness, winner, or speed gate failed"),
    comparisons,
  };
  await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
  const tieSummary = tieCases === 0
    ? "No baseline top-bucket ties occurred in these fixtures."
    : `${tieCases} baseline top-bucket tie cases were observed; ${tieSetMatches} retained the same tie set.`;
  const results = `# CMAP format-14 indexed fine-scorer probe\n\n` +
    `Decision: **${report.decision}**.\n\n` +
    `Exactly eight spread groups (${reference.groupIds.join(", ")}) and ` +
    `${reference.fixtures.cases.length} certified fixtures were tested. All ` +
    `${reference.variationSelectors.length} variation selectors were present: 16 BMP standardized ` +
    `selectors and 240 supplementary selectors. Sequence auditing found ` +
    `${unsupportedSequences} unsupported, ${splitSequences} split, and ` +
    `${malformedSequences} malformed sequences.\n\n` +
    `${candidateComparisons.toLocaleString()} candidate buckets had a maximum absolute delta of ` +
    `${maximumAbsoluteCandidateDelta}; the existing bounded-probe limit is ` +
    `${reference.existingBoundedBucketDelta}. Winner-token agreement was ` +
    `${(winnerAgreement * 100).toFixed(2)}% and winner-bucket agreement was ` +
    `${(winnerBucketAgreement * 100).toFixed(2)}%. ${tieSummary}\n\n` +
    `Median isolated group switching was ${cmapMedian.toFixed(3)} ms for CMAP14 and ` +
    `${baselineMedian.toFixed(3)} ms for the same CSS-dispatched baseline ` +
    `(${(speedupFraction * 100).toFixed(1)}% improvement; 25% required).\n\n` +
    `The fonts occupy ${reference.fontWoff2Bytes.toLocaleString()} WOFF2 bytes and ` +
    `${reference.fontTtfBytes.toLocaleString()} expanded TTF bytes; CSS is ` +
    `${reference.cssBytes.toLocaleString()} bytes.\n`;
  await fs.writeFile(new URL("RESULTS.md", root), results);
  console.log(JSON.stringify(report, null, 2));
  if (!hardGatePassed) process.exitCode = 1;
} finally {
  await browser.close();
}
