import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const experimentName = process.env.GSUB_CONSTANT_BASE_EXPERIMENT ??
  "gsub-constant-base-fine-scorer";
const timingRounds = Number.parseInt(
  process.env.GSUB_CONSTANT_BASE_TIMING_ROUNDS ?? "15", 10,
);
const server = process.env.GSUB_CONSTANT_BASE_SERVER ?? "http://127.0.0.1:4178";
const root = new URL(`../experiments/${experimentName}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function bucketsFromWidths(widths, validCandidates) {
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

async function loadPage(browser, directory) {
  const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
  const started = performance.now();
  await page.goto(`${server}/experiments/${directory}/index.html`, {
    waitUntil: "load",
    timeout: 240_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  return { page, loadMilliseconds: performance.now() - started };
}

async function applyCase(page, kind, hidden, floor, group, feature) {
  return page.evaluate(({ pageKind, values, scoreFloor, groupId, featureValue }) => {
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
      featureSettings: getComputedStyle(stage).fontFeatureSettings,
    };
  }, {
    pageKind: kind,
    values: hidden,
    scoreFloor: floor,
    groupId: group,
    featureValue: feature,
  });
}

async function measureSwitches(page, kind, groupCases, rounds) {
  return page.evaluate(({ pageKind, cases, count }) => {
    const stage = document.querySelector(pageKind === "gsub" ? "#gsub-stage" : "#fine-stage");
    const property = pageKind === "gsub" ? "--probe-feature" : "--group";
    const values = cases.map((entry) =>
      pageKind === "gsub" ? entry.feature : entry.group);
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

async function auditDom(page, kind) {
  return page.evaluate((pageKind) => {
    const stage = document.querySelector(pageKind === "gsub" ? "#gsub-stage" : "#fine-stage");
    const selector = pageKind === "gsub" ? ".candidate" : ".fine-candidate";
    const candidates = [...stage.querySelectorAll(selector)];
    return {
      documentElements: document.querySelectorAll("*").length,
      stageElements: stage.querySelectorAll("*").length,
      candidates: candidates.length,
      candidateDescendants: candidates.reduce(
        (sum, candidate) => sum + candidate.querySelectorAll("*").length, 0,
      ),
      minimumCodepointsPerCandidate: Math.min(
        ...candidates.map((candidate) => [...candidate.textContent].length),
      ),
      maximumCodepointsPerCandidate: Math.max(
        ...candidates.map((candidate) => [...candidate.textContent].length),
      ),
    };
  }, kind);
}

async function auditNaturalWidths(page, hidden, groupCases) {
  return page.evaluate(({ values, cases }) => {
    const stage = document.querySelector("#gsub-stage");
    const candidates = [...stage.querySelectorAll(".candidate")];
    const setHidden = (vector) => vector.forEach((value, dimension) => {
      stage.style.setProperty(`--h${dimension}`, String(value));
    });
    const measureNatural = () => {
      candidates.forEach((candidate) => candidate.style.setProperty("width", "max-content"));
      const widths = candidates.map((candidate) => candidate.getBoundingClientRect().width);
      candidates.forEach((candidate) => candidate.style.removeProperty("width"));
      return widths;
    };
    stage.style.setProperty("--score-offset", "0px");
    const diagnostics = [];
    for (const entry of cases) {
      stage.style.setProperty("--probe-feature", String(entry.feature));
      setHidden(Array(values.length).fill(0));
      const zeroWidths = measureNatural();
      setHidden(values);
      const naturalWidths = measureNatural();
      const deltas = naturalWidths.map((width, local) => width - zeroWidths[local]);
      diagnostics.push({
        group: entry.group,
        feature: entry.feature,
        computedFontFeatureSettings: getComputedStyle(stage).fontFeatureSettings,
        zeroWidth: {
          minimum: Math.min(...zeroWidths),
          maximum: Math.max(...zeroWidths),
          firstEight: zeroWidths.slice(0, 8),
        },
        naturalWidthBeforeScoreOffset: {
          minimum: Math.min(...naturalWidths),
          maximum: Math.max(...naturalWidths),
          firstEight: naturalWidths.slice(0, 8),
          checksum: naturalWidths.reduce((sum, width) => sum + width, 0),
        },
        hvarDelta: {
          changedCandidates: deltas.filter((delta) => delta !== 0).length,
          maximumAbsolute: Math.max(...deltas.map(Math.abs)),
          firstEight: deltas.slice(0, 8),
        },
      });
    }
    return diagnostics;
  }, { values: hidden, cases: groupCases });
}

async function auditFaceVariation(page, hidden, faces) {
  return page.evaluate(({ values, faceRanges }) => {
    const stage = document.querySelector("#gsub-stage");
    const sampleLocals = [0, 1, 11, 34, 127, 188, 255];
    stage.style.setProperty("--probe-feature", "1");
    stage.style.setProperty("--score-offset", "0px");
    const probes = faceRanges.flatMap((face, faceIndex) => sampleLocals.map((local) => {
      const span = document.createElement("span");
      span.textContent = String.fromCodePoint(face.codepointStart + local);
      span.dataset.face = String(faceIndex);
      span.dataset.local = String(local);
      Object.assign(span.style, {
        position: "absolute",
        display: "inline-block",
        width: "max-content",
        whiteSpace: "pre",
        fontFamily: face.family,
        fontSize: `${getComputedStyle(stage).fontSize}`,
        fontKerning: "none",
        fontSynthesis: "none",
      });
      stage.append(span);
      return span;
    }));
    const setHidden = (vector) => vector.forEach((value, dimension) => {
      stage.style.setProperty(`--h${dimension}`, String(value));
    });
    setHidden(Array(values.length).fill(0));
    const zeroWidths = probes.map((probe) => probe.getBoundingClientRect().width);
    setHidden(values);
    const variedWidths = probes.map((probe) => probe.getBoundingClientRect().width);
    const result = faceRanges.map((face, faceIndex) => {
      const start = faceIndex * sampleLocals.length;
      const deltas = sampleLocals.map((_, index) =>
        variedWidths[start + index] - zeroWidths[start + index]);
      return {
        face: faceIndex,
        shard: face.shard,
        plane: face.plane,
        family: face.family,
        sampleLocals,
        zeroWidths: zeroWidths.slice(start, start + sampleLocals.length),
        variedWidths: variedWidths.slice(start, start + sampleLocals.length),
        deltas,
        variesUnderHiddenVector: deltas.some((delta) => delta !== 0),
      };
    });
    probes.forEach((probe) => probe.remove());
    return result;
  }, { values: hidden, faceRanges: faces });
}

if (!reference.fullBuild && (
  reference.groups !== 8 || reference.fixtures.cases.length !== 10
)) {
  throw new Error("bounded probe must retain exactly eight groups and ten fixtures");
}
if (reference.glyphsPerFacePerCandidate !== 1 ||
    reference.correctionGlyphsPerFacePerCandidate !== 0) {
  throw new Error("probe topology is not single-glyph constant-base GSUB");
}
if (!reference.faceRanges.every((face) =>
  face.commonBase === face.maximumL1 + reference.baseMargin &&
  face.commonBase + face.maximumL1 <= 65_535 &&
  face.uint16AdvanceSafe)) {
  throw new Error("one or more common-base face ranges are unsafe");
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const gsubLoad = await loadPage(browser, experimentName);
  const baselineLoad = await loadPage(browser, reference.baselineDirectory);
  const chrome = await browser.version();

  const diagnosticFixture = reference.fixtures.cases[0];
  const diagnosticHidden = reference.fixtures.hiddenVectors[diagnosticFixture.fixture];
  const naturalWidthDiagnostics = await auditNaturalWidths(
    gsubLoad.page, diagnosticHidden, diagnosticFixture.groups,
  );
  const faceVariationDiagnostics = await auditFaceVariation(
    gsubLoad.page, diagnosticHidden, reference.faceRanges,
  );
  const allFacesVaryUnderHiddenVector = faceVariationDiagnostics.every(
    (face) => face.variesUnderHiddenVector,
  );

  const comparisons = [];
  const failures = [];
  const observedFeatureSettings = new Set();
  const deltaHistogram = new Map();
  let candidateComparisons = 0;
  let maximumAbsoluteCandidateDelta = 0;
  let winnerTokenMatches = 0;
  let winnerBucketMatches = 0;
  let modelOracleBucketMatches = 0;
  let changedAcrossGroups = false;
  let previousFirstFixtureBuckets = null;

  for (const fixture of reference.fixtures.cases) {
    const hidden = reference.fixtures.hiddenVectors[fixture.fixture];
    const floor = reference.fixtures.scoreFloors[fixture.fixture];
    for (const groupCase of fixture.groups) {
      const [gsub, baseline] = await Promise.all([
        applyCase(
          gsubLoad.page, "gsub", hidden, floor,
          groupCase.group, groupCase.feature,
        ),
        applyCase(
          baselineLoad.page, "baseline", hidden, floor,
          groupCase.group, groupCase.feature,
        ),
      ]);
      observedFeatureSettings.add(gsub.featureSettings);
      const valid = groupCase.validCandidates;
      const gsubBuckets = bucketsFromWidths(gsub.widths, valid);
      const baselineBuckets = bucketsFromWidths(baseline.widths, valid);
      const gsubWinner = winnerFromBuckets(gsubBuckets);
      const baselineWinner = winnerFromBuckets(baselineBuckets);
      const differingBuckets = [];
      let caseMaximumAbsoluteDelta = 0;
      for (let local = 0; local < valid; local += 1) {
        const delta = gsubBuckets[local] - baselineBuckets[local];
        candidateComparisons += 1;
        caseMaximumAbsoluteDelta = Math.max(caseMaximumAbsoluteDelta, Math.abs(delta));
        maximumAbsoluteCandidateDelta = Math.max(maximumAbsoluteCandidateDelta, Math.abs(delta));
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
      const winnerTokenMatchesCase =
        gsubWinner.winnerLocal === baselineWinner.winnerLocal;
      const winnerBucketMatchesCase = winnerTokenMatchesCase &&
        gsubWinner.winnerBucket === baselineWinner.winnerBucket;
      if (winnerTokenMatchesCase) winnerTokenMatches += 1;
      if (winnerBucketMatchesCase) winnerBucketMatches += 1;
      if (gsubBuckets.every((bucket, local) => bucket === groupCase.buckets[local])) {
        modelOracleBucketMatches += 1;
      }
      if (caseMaximumAbsoluteDelta !== 0 || !winnerBucketMatchesCase) {
        failures.push({
          fixture: fixture.fixture,
          group: groupCase.group,
          differingBuckets: differingBuckets.slice(0, 16),
          differingBucketCount: differingBuckets.length,
          maximumAbsoluteCandidateDelta: caseMaximumAbsoluteDelta,
          gsubWinner,
          baselineWinner,
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
        baselineWinner,
      });
    }
  }

  const [gsubDom, baselineDom] = await Promise.all([
    auditDom(gsubLoad.page, "gsub"),
    auditDom(baselineLoad.page, "baseline"),
  ]);
  const topologyValid =
    gsubDom.candidates === reference.topology.candidateElements &&
    gsubDom.candidateDescendants === reference.topology.candidateDescendants &&
    gsubDom.minimumCodepointsPerCandidate === reference.topology.codepointsPerCandidate &&
    gsubDom.maximumCodepointsPerCandidate === reference.topology.codepointsPerCandidate &&
    reference.topology.perFaceInlineBoxes === 0;

  const timingFixture = reference.fixtures.cases[0];
  const timingHidden = reference.fixtures.hiddenVectors[0];
  const timingFloor = reference.fixtures.scoreFloors[0];
  await applyCase(
    gsubLoad.page, "gsub", timingHidden, timingFloor,
    timingFixture.groups[0].group, timingFixture.groups[0].feature,
  );
  await applyCase(
    baselineLoad.page, "baseline", timingHidden, timingFloor,
    timingFixture.groups[0].group, timingFixture.groups[0].feature,
  );
  const gsubSwitchMilliseconds = await measureSwitches(
    gsubLoad.page, "gsub", timingFixture.groups, timingRounds,
  );
  const baselineSwitchMilliseconds = await measureSwitches(
    baselineLoad.page, "baseline", timingFixture.groups, timingRounds,
  );
  const gsubMedian = median(gsubSwitchMilliseconds);
  const baselineMedian = median(baselineSwitchMilliseconds);
  const speedupFraction = 1 - gsubMedian / baselineMedian;
  const comparisonsCount = comparisons.length;
  const largeDeltaCandidateComparisons = [...deltaHistogram.entries()].reduce(
    (sum, [delta, count]) => sum + (Math.abs(delta) > 10 ? count : 0), 0,
  );
  const winnerTokenMismatches = comparisons.filter((entry) =>
    entry.gsubWinner.winnerLocal !== entry.baselineWinner.winnerLocal);
  const exactOutputPassed = maximumAbsoluteCandidateDelta === 0;
  const winnerTokenAgreement = winnerTokenMatches / comparisonsCount;
  const winnerBucketAgreement = winnerBucketMatches / comparisonsCount;
  const dynamicFeatureValid =
    observedFeatureSettings.size === reference.groups && changedAcrossGroups;
  const chrome153 = chrome.startsWith("153.");
  const speedGatePassed = speedupFraction >= 0.25;
  const advanceStorageSafe = reference.faceRanges.every((face) =>
    face.commonBase + face.maximumL1 <= 65_535);
  const adjustedAdvanceMitigationValid = topologyValid &&
    reference.topology.perFaceInlineBoxes === 0 &&
    reference.maximumTheoreticalAdjustedAdvancePx < reference.chromeAdvanceCeilingPx;
  const hardGatePassed = chrome153 && advanceStorageSafe &&
    adjustedAdvanceMitigationValid && allFacesVaryUnderHiddenVector &&
    dynamicFeatureValid && exactOutputPassed &&
    winnerTokenAgreement === 1 && winnerBucketAgreement === 1 && speedGatePassed;

  report = {
    chrome,
    chrome153,
    experimentName,
    groups: reference.groupIds,
    fixtures: reference.fixtures.cases.length,
    candidateComparisons,
    loadMilliseconds: {
      gsub: gsubLoad.loadMilliseconds,
      baseline: baselineLoad.loadMilliseconds,
    },
    numberedFeature: reference.feature,
    observedFeatureSettings: [...observedFeatureSettings],
    changedAcrossGroups,
    dynamicFeatureValid,
    wiringDiagnostics: {
      naturalWidthsBeforeScoreOffset: naturalWidthDiagnostics,
      faceVariationUnderHiddenVector: faceVariationDiagnostics,
      allFacesVaryUnderHiddenVector,
      sourceAlternateMappings: reference.mappingAudits,
    },
    exactOutputPassed,
    maximumAbsoluteCandidateDelta,
    largeDeltaCandidateComparisons,
    candidateDeltaHistogram: Object.fromEntries(
      [...deltaHistogram.entries()].sort(([left], [right]) => left - right),
    ),
    winnerTokenMatches,
    winnerTokenAgreement,
    winnerTokenMismatches,
    winnerBucketMatches,
    winnerBucketAgreement,
    modelOracleExactCases: modelOracleBucketMatches,
    modelOracleExactRate: modelOracleBucketMatches / comparisonsCount,
    advanceSafety: {
      maximumCommonBasePlusL1: Math.max(
        ...reference.faceRanges.map((face) => face.commonBase + face.maximumL1),
      ),
      uint16Limit: 65_535,
      storageSafe: advanceStorageSafe,
      adjustedAdvanceCeilingPx: reference.chromeAdvanceCeilingPx,
      maximumFixtureAdjustedAdvancePx: reference.maximumFixtureAdjustedAdvancePx,
      maximumTheoreticalAdjustedAdvancePx: reference.maximumTheoreticalAdjustedAdvancePx,
      mitigation: reference.adjustedAdvanceMitigation,
      mitigationValid: adjustedAdvanceMitigationValid,
    },
    dom: {
      gsub: gsubDom,
      baseline: baselineDom,
      topologyValid,
    },
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
    failures,
    hardGatePassed,
    fullScaleBuildAuthorized: hardGatePassed && !reference.fullBuild,
    decision: hardGatePassed
      ? (reference.fullBuild
        ? "retain: full constant-base scorer passed"
        : "retain for optional full-scale build: bounded constant-base scorer is exact and materially faster")
      : "reject: 40-face constant-base sharding is numerically unstable and slower than CSS dispatch",
    comparisons,
  };
  await fs.writeFile(
    new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`,
  );
  const results = `# Constant-base GSUB fine-scorer probe\n\n` +
    `Decision: **${report.decision}**.\n\n` +
    `${candidateComparisons.toLocaleString()} candidate buckets across ` +
    `${reference.fixtures.cases.length} fixtures and ${reference.groups} groups had a maximum ` +
    `absolute delta of ${maximumAbsoluteCandidateDelta} versus the exact CSS-dispatch baseline. ` +
    `${largeDeltaCandidateComparisons.toLocaleString()} candidate comparisons exceeded 10 buckets. ` +
    `Winner-token and winner-bucket agreement were ` +
    `${(winnerTokenAgreement * 100).toFixed(2)}% and ` +
    `${(winnerBucketAgreement * 100).toFixed(2)}%; the ${winnerTokenMismatches.length} winner swaps ` +
    `were ${winnerTokenMismatches.map((entry) =>
      `fixture ${entry.fixture}/group ${entry.group}: local ${entry.baselineWinner.winnerLocal}→${entry.gsubWinner.winnerLocal}`
    ).join(", ")}.\n\n` +
    `Median isolated group switching was ${gsubMedian.toFixed(3)} ms for constant-base GSUB ` +
    `and ${baselineMedian.toFixed(3)} ms for CSS dispatch ` +
    `(${(speedupFraction * 100).toFixed(1)}% improvement; 25% required). ` +
    `Load was ${gsubLoad.loadMilliseconds.toFixed(1)} ms versus ` +
    `${baselineLoad.loadMilliseconds.toFixed(1)} ms.\n\n` +
    `The bounded fonts occupy ${reference.fontWoff2Bytes.toLocaleString()} WOFF2 bytes. ` +
    `The scorer DOM has ${gsubDom.documentElements.toLocaleString()} elements versus ` +
    `${baselineDom.documentElements.toLocaleString()} for the baseline; each candidate has ` +
    `${gsubDom.candidateDescendants} total descendants and 40 codepoints/glyphs total ` +
    `(one glyph for each of 40 faces). ` +
    `No full build was launched.\n`;
  await fs.writeFile(new URL("RESULTS.md", root), results);
  console.log(JSON.stringify(report, null, 2));
  if (!hardGatePassed) process.exitCode = 1;
} finally {
  await browser.close();
}
