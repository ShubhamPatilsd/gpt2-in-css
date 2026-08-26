import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const experimentName = "gsub-lattice-scale-fine-scorer";
const timingRounds = Number.parseInt(process.env.GSUB_LATTICE_TIMING_ROUNDS ?? "15", 10);
const server = process.env.GSUB_LATTICE_SERVER ?? "http://127.0.0.1:4178";
const root = new URL(`../experiments/${experimentName}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function quantile(values, fraction) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor((sorted.length - 1) * fraction)];
}

function bucketsFromWidths(widths) {
  return widths.map((width, local) =>
    Math.round((width - (255 - local) / 64) / reference.scoreStridePx));
}

function winnerFromBuckets(buckets) {
  let local = 0;
  for (let index = 1; index < buckets.length; index += 1) {
    if (buckets[index] > buckets[local]) local = index;
  }
  return { local, bucket: buckets[local] };
}

async function loadPage(browser, file) {
  const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
  const started = performance.now();
  await page.goto(`${server}/experiments/${experimentName}/${file}`, {
    waitUntil: "load",
    timeout: 240_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  return {
    page,
    loadMilliseconds: performance.now() - started,
    fontStatus: await page.evaluate(() => document.fonts.status),
    fontResources: await page.evaluate(() => performance.getEntriesByType("resource")
      .filter((entry) => /\.woff2(?:$|\?)/.test(entry.name))
      .map((entry) => ({ name: entry.name, duration: entry.duration, transferSize: entry.transferSize }))),
  };
}

async function applyCase(page, kind, hidden, floor, group, feature, auditAdvances) {
  return page.evaluate(({ pageKind, values, scoreFloor, groupId, featureValue, audit }) => {
    const isGsub = pageKind === "gsub";
    const stage = document.querySelector(isGsub ? "#gsub-stage" : "#exact-stage");
    values.forEach((value, dimension) => stage.style.setProperty(`--h${dimension}`, String(value)));
    stage.style.setProperty("--score-offset", `${-scoreFloor * 256 * 4}px`);
    stage.style.setProperty(isGsub ? "--probe-feature" : "--group", String(
      isGsub ? featureValue : groupId,
    ));
    const selector = isGsub ? ".candidate" : ".exact-candidate";
    const candidates = [...stage.querySelectorAll(selector)];
    const widths = candidates.map((element) => element.getBoundingClientRect().width);
    let advanceAudit = null;
    if (isGsub && audit) {
      const range = document.createRange();
      let maximumGlyphAdvancePx = 0;
      let maximumScoreAdvancePx = 0;
      let maximumComplementAdvancePx = 0;
      let saturatedGlyphAdvances = 0;
      let saturatedScoreAdvances = 0;
      let saturatedComplementAdvances = 0;
      let glyphMeasurements = 0;
      let maximumRecord = null;
      for (let local = 0; local < candidates.length; local += 1) {
        const node = candidates[local].firstChild;
        const characters = [...node.data];
        let offset = 0;
        for (let index = 0; index < characters.length; index += 1) {
          const length = characters[index].length;
          range.setStart(node, offset);
          range.setEnd(node, offset + length);
          const width = range.getBoundingClientRect().width;
          const isComplement = index % 2 === 1;
          glyphMeasurements += 1;
          if (width >= 32768) {
            saturatedGlyphAdvances += 1;
            if (isComplement) saturatedComplementAdvances += 1;
            else saturatedScoreAdvances += 1;
          }
          if (isComplement) maximumComplementAdvancePx = Math.max(maximumComplementAdvancePx, width);
          else maximumScoreAdvancePx = Math.max(maximumScoreAdvancePx, width);
          if (width > maximumGlyphAdvancePx) {
            maximumGlyphAdvancePx = width;
            maximumRecord = { local, face: Math.floor(index / 2), isComplement, width };
          }
          offset += length;
        }
      }
      advanceAudit = {
        glyphMeasurements,
        maximumGlyphAdvancePx,
        maximumScoreAdvancePx,
        maximumComplementAdvancePx,
        saturatedGlyphAdvances,
        saturatedScoreAdvances,
        saturatedComplementAdvances,
        maximumRecord,
      };
    }
    const style = getComputedStyle(stage);
    return {
      widths,
      featureSettings: style.fontFeatureSettings,
      groupValue: style.getPropertyValue("--group").trim(),
      fontSize: style.fontSize,
      stageWidth: stage.getBoundingClientRect().width,
      advanceAudit,
    };
  }, {
    pageKind: kind,
    values: hidden,
    scoreFloor: floor,
    groupId: group,
    featureValue: feature,
    audit: auditAdvances,
  });
}

async function measureSwitches(page, kind, cases, rounds) {
  return page.evaluate(({ pageKind, groupCases, count }) => {
    const isGsub = pageKind === "gsub";
    const stage = document.querySelector(isGsub ? "#gsub-stage" : "#exact-stage");
    const property = isGsub ? "--probe-feature" : "--group";
    const values = groupCases.map((entry) => isGsub ? entry.feature : entry.group);
    for (let warm = 0; warm < 5; warm += 1) {
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
  }, { pageKind: kind, groupCases: cases, count: rounds });
}

if (reference.boundedOnly !== true || reference.fullBuildPerformed !== false ||
    reference.groups !== 8 || reference.fixtures.cases.length !== 10 ||
    reference.displayScale !== 0.03125 || reference.fontSizePx !== 31.25 ||
    reference.lowPlaneUnitLayout64 !== 2 || reference.highPlaneUnitLayout64 !== 512 ||
    reference.expectedCandidateBuckets !== 20480) {
  throw new Error("reference violates the bounded lattice-scale contract");
}
if (reference.geometryFactor !== reference.exactGeometryFactor) {
  throw new Error("GSUB and exact pages do not use the same regenerated geometry factor");
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const gsubLoad = await loadPage(browser, "index.html");
  const exactLoad = await loadPage(browser, "exact.html");
  const comparisons = [];
  const failures = [];
  const deltaHistogram = new Map();
  const featureSettings = new Set();
  const exactGroups = new Set();
  const advanceAudits = [];
  let candidateComparisons = 0;
  let differingCandidateBuckets = 0;
  let maximumAbsoluteCandidateDelta = 0;
  let gsubExactWinnerMatches = 0;
  let gsubExactWinnerBucketMatches = 0;
  let gsubOracleWinnerMatches = 0;
  let gsubOracleWinnerBucketMatches = 0;
  let exactOracleWinnerMatches = 0;
  let exactOracleWinnerBucketMatches = 0;
  let changedAcrossGroups = false;
  let previousFirstFixtureBuckets = null;

  for (const fixture of reference.fixtures.cases) {
    const hidden = reference.fixtures.hiddenVectors[fixture.fixture];
    const floor = reference.fixtures.scoreFloors[fixture.fixture];
    for (const groupCase of fixture.groups) {
      const [gsub, exact] = await Promise.all([
        applyCase(gsubLoad.page, "gsub", hidden, floor, groupCase.group, groupCase.feature, true),
        applyCase(exactLoad.page, "exact", hidden, floor, groupCase.group, groupCase.feature, false),
      ]);
      featureSettings.add(gsub.featureSettings);
      exactGroups.add(exact.groupValue);
      advanceAudits.push({ fixture: fixture.fixture, group: groupCase.group, ...gsub.advanceAudit });
      if (gsub.fontSize !== "31.25px" || exact.fontSize !== "31.25px") {
        failures.push({ fixture: fixture.fixture, group: groupCase.group, fontSizes: [gsub.fontSize, exact.fontSize] });
      }
      const valid = groupCase.validCandidates;
      const gsubBuckets = bucketsFromWidths(gsub.widths.slice(0, valid));
      const exactBuckets = bucketsFromWidths(exact.widths.slice(0, valid));
      const oracleBuckets = groupCase.buckets.slice(0, valid);
      const gsubWinner = winnerFromBuckets(gsubBuckets);
      const exactWinner = winnerFromBuckets(exactBuckets);
      const oracleWinner = { local: groupCase.winnerLocal, bucket: groupCase.winnerBucket };
      if (fixture.fixture === 0) {
        if (previousFirstFixtureBuckets && gsubBuckets.some(
          (bucket, local) => bucket !== previousFirstFixtureBuckets[local])) changedAcrossGroups = true;
        previousFirstFixtureBuckets = gsubBuckets;
      }
      let caseMaximumAbsoluteDelta = 0;
      let caseDifferingBuckets = 0;
      for (let local = 0; local < valid; local += 1) {
        const delta = gsubBuckets[local] - exactBuckets[local];
        candidateComparisons += 1;
        if (delta !== 0) {
          differingCandidateBuckets += 1;
          caseDifferingBuckets += 1;
        }
        caseMaximumAbsoluteDelta = Math.max(caseMaximumAbsoluteDelta, Math.abs(delta));
        maximumAbsoluteCandidateDelta = Math.max(maximumAbsoluteCandidateDelta, Math.abs(delta));
        deltaHistogram.set(delta, (deltaHistogram.get(delta) ?? 0) + 1);
      }
      const winnerMatches = gsubWinner.local === exactWinner.local;
      const winnerBucketMatches = winnerMatches && gsubWinner.bucket === exactWinner.bucket;
      const gsubOracleMatches = gsubWinner.local === oracleWinner.local;
      const exactOracleMatches = exactWinner.local === oracleWinner.local;
      if (winnerMatches) gsubExactWinnerMatches += 1;
      if (winnerBucketMatches) gsubExactWinnerBucketMatches += 1;
      if (gsubOracleMatches) gsubOracleWinnerMatches += 1;
      if (gsubOracleMatches && gsubWinner.bucket === oracleWinner.bucket) gsubOracleWinnerBucketMatches += 1;
      if (exactOracleMatches) exactOracleWinnerMatches += 1;
      if (exactOracleMatches && exactWinner.bucket === oracleWinner.bucket) exactOracleWinnerBucketMatches += 1;
      if (caseMaximumAbsoluteDelta !== 0 || !winnerMatches || !gsubOracleMatches || !exactOracleMatches) {
        failures.push({
          fixture: fixture.fixture,
          group: groupCase.group,
          caseDifferingBuckets,
          caseMaximumAbsoluteDelta,
          gsubWinner,
          exactWinner,
          oracleWinner,
        });
      }
      comparisons.push({
        fixture: fixture.fixture,
        group: groupCase.group,
        feature: groupCase.feature,
        validCandidates: valid,
        differingCandidateBuckets: caseDifferingBuckets,
        maximumAbsoluteCandidateDelta: caseMaximumAbsoluteDelta,
        gsubWinner,
        exactWinner,
        oracleWinner,
      });
    }
  }

  if (candidateComparisons !== 20480) failures.push({ candidateComparisons, expected: 20480 });
  const cases = comparisons.length;
  const maximumBrowserGlyphAdvancePx = Math.max(...advanceAudits.map((entry) => entry.maximumGlyphAdvancePx));
  const maximumBrowserScoreAdvancePx = Math.max(...advanceAudits.map((entry) => entry.maximumScoreAdvancePx));
  const maximumBrowserComplementAdvancePx = Math.max(...advanceAudits.map((entry) => entry.maximumComplementAdvancePx));
  const saturatedGlyphAdvances = advanceAudits.reduce((sum, entry) => sum + entry.saturatedGlyphAdvances, 0);
  const saturatedScoreAdvances = advanceAudits.reduce((sum, entry) => sum + entry.saturatedScoreAdvances, 0);
  const saturatedComplementAdvances = advanceAudits.reduce(
    (sum, entry) => sum + entry.saturatedComplementAdvances, 0,
  );
  const glyphMeasurements = advanceAudits.reduce((sum, entry) => sum + entry.glyphMeasurements, 0);
  const advanceCeilingPassed = saturatedGlyphAdvances === 0 &&
    maximumBrowserGlyphAdvancePx < reference.chromeAdvanceCeilingPx &&
    reference.maximumBoundedStaticComplement.adjustedPx < reference.chromeAdvanceCeilingPx &&
    reference.knownFullH3Complement.adjustedPx === 10536 &&
    reference.knownFullH3Complement.adjustedPx < reference.chromeAdvanceCeilingPx &&
    reference.sourceTheoreticalAdvances.highPlaneMaximumFontUnits === 3662 &&
    reference.sourceTheoreticalAdvances.highPlaneAdjustedPx === 29296 &&
    reference.sourceTheoreticalAdvances.maximumAdjustedPx < reference.chromeAdvanceCeilingPx;
  if (!advanceCeilingPassed) failures.push({
    advanceCeilingPassed,
    maximumBrowserGlyphAdvancePx,
    saturatedGlyphAdvances,
  });

  const timingFixture = reference.fixtures.cases[0];
  const timingHidden = reference.fixtures.hiddenVectors[0];
  const timingFloor = reference.fixtures.scoreFloors[0];
  await applyCase(gsubLoad.page, "gsub", timingHidden, timingFloor,
    timingFixture.groups[0].group, timingFixture.groups[0].feature, false);
  await applyCase(exactLoad.page, "exact", timingHidden, timingFloor,
    timingFixture.groups[0].group, timingFixture.groups[0].feature, false);
  const gsubSwitchMilliseconds = await measureSwitches(
    gsubLoad.page, "gsub", timingFixture.groups, timingRounds,
  );
  const exactSwitchMilliseconds = await measureSwitches(
    exactLoad.page, "exact", timingFixture.groups, timingRounds,
  );
  const gsubMedian = median(gsubSwitchMilliseconds);
  const exactMedian = median(exactSwitchMilliseconds);
  const speedupFraction = 1 - gsubMedian / exactMedian;
  const speedGatePassed = speedupFraction >= 0.25;
  const dynamicFeatureValid = featureSettings.size === 8 && changedAcrossGroups;
  const dynamicExactDispatchValid = exactGroups.size === 8;
  const exactAgreement = maximumAbsoluteCandidateDelta === 0 &&
    gsubExactWinnerMatches === cases && gsubExactWinnerBucketMatches === cases;
  const historical = reference.historicalPointOneScale;
  const clearlyImprovedAgreement =
    maximumAbsoluteCandidateDelta < historical.maximumAbsoluteCandidateDelta &&
    differingCandidateBuckets < historical.differingCandidateBuckets &&
    gsubExactWinnerMatches === cases &&
    gsubExactWinnerBucketMatches / cases > historical.winnerBucketAgreement;
  const modelOracleWinnerGatePassed = gsubOracleWinnerMatches === cases && exactOracleWinnerMatches === cases;
  const winnerAgreementGatePassed = gsubExactWinnerMatches === cases;
  const agreementGatePassed = winnerAgreementGatePassed;
  const hardGatePassed = dynamicFeatureValid && dynamicExactDispatchValid && advanceCeilingPassed &&
    candidateComparisons === reference.expectedCandidateBuckets && modelOracleWinnerGatePassed &&
    winnerAgreementGatePassed;

  report = {
    chrome: await browser.version(),
    experimentName,
    boundedOnly: true,
    fullBuildPerformed: false,
    groups: reference.groupIds,
    fixtures: reference.fixtures.cases.length,
    cases,
    candidateComparisons,
    expectedCandidateComparisons: reference.expectedCandidateBuckets,
    lattice: {
      displayScale: reference.displayScale,
      fontSizePx: reference.fontSizePx,
      lowPlaneUnitPx: reference.lowPlaneUnitPx,
      lowPlaneUnitLayout64: reference.lowPlaneUnitLayout64,
      highPlaneUnitPx: reference.highPlaneUnitPx,
      highPlaneUnitLayout64: reference.highPlaneUnitLayout64,
      gsubEquivalentBasePx: reference.gsubEquivalentBasePx,
      geometryFactor: reference.geometryFactor,
      exactGeometryFactor: reference.exactGeometryFactor,
      factorsMatch: reference.geometryFactor === reference.exactGeometryFactor,
    },
    dynamicFeatureSettings: {
      observed: [...featureSettings].sort(),
      changedAcrossGroups,
      valid: dynamicFeatureValid,
    },
    dynamicExactDispatch: {
      observedGroups: [...exactGroups].map(Number).sort((a, b) => a - b),
      valid: dynamicExactDispatchValid,
    },
    agreement: {
      exactAgreement,
      clearlyImprovedAgreement,
      bucketDeltasDiagnosticOnly: true,
      winnerAgreementGatePassed,
      gatePassed: agreementGatePassed,
      differingCandidateBuckets,
      maximumAbsoluteCandidateDelta,
      candidateDeltaHistogram: Object.fromEntries([...deltaHistogram.entries()].sort(([a], [b]) => a - b)),
      gsubVsExactWinnerMatches: gsubExactWinnerMatches,
      gsubVsExactWinnerAgreement: gsubExactWinnerMatches / cases,
      gsubVsExactWinnerBucketMatches: gsubExactWinnerBucketMatches,
      gsubVsExactWinnerBucketAgreement: gsubExactWinnerBucketMatches / cases,
      historicalPointOneScaleInformationalOnly: historical,
    },
    modelOracleWinners: {
      gatePassed: modelOracleWinnerGatePassed,
      gsubWinnerMatches: gsubOracleWinnerMatches,
      gsubWinnerAgreement: gsubOracleWinnerMatches / cases,
      gsubWinnerBucketMatches: gsubOracleWinnerBucketMatches,
      gsubWinnerBucketAgreement: gsubOracleWinnerBucketMatches / cases,
      exactWinnerMatches: exactOracleWinnerMatches,
      exactWinnerAgreement: exactOracleWinnerMatches / cases,
      exactWinnerBucketMatches: exactOracleWinnerBucketMatches,
      exactWinnerBucketAgreement: exactOracleWinnerBucketMatches / cases,
    },
    advanceCeiling: {
      ceilingPx: reference.chromeAdvanceCeilingPx,
      glyphMeasurements,
      maximumBrowserGlyphAdvancePx,
      maximumBrowserScoreAdvancePx,
      maximumBrowserComplementAdvancePx,
      saturatedGlyphAdvances,
      saturatedScoreAdvances,
      saturatedComplementAdvances,
      maximumBoundedStaticComplement: reference.maximumBoundedStaticComplement,
      knownFullH3ComplementProjection: reference.knownFullH3Complement,
      sourceTheoreticalAdvances: reference.sourceTheoreticalAdvances,
      passed: advanceCeilingPassed,
    },
    load: {
      gsubMilliseconds: gsubLoad.loadMilliseconds,
      exactMilliseconds: exactLoad.loadMilliseconds,
      gsubFontStatus: gsubLoad.fontStatus,
      exactFontStatus: exactLoad.fontStatus,
      gsubFontResources: gsubLoad.fontResources,
      exactFontResources: exactLoad.fontResources,
    },
    timingRounds,
    isolatedGroupSwitch: {
      gsubMedianMilliseconds: gsubMedian,
      exactCssDispatchMedianMilliseconds: exactMedian,
      gsubP90Milliseconds: quantile(gsubSwitchMilliseconds, 0.9),
      exactCssDispatchP90Milliseconds: quantile(exactSwitchMilliseconds, 0.9),
      speedupFraction,
      speedupPercent: speedupFraction * 100,
      gatePercent: 25,
      gatePassed: speedGatePassed,
      gsubSamples: gsubSwitchMilliseconds,
      exactCssDispatchSamples: exactSwitchMilliseconds,
    },
    sizes: {
      reusedGsubWoff2Bytes: reference.reusedGsubWoff2Bytes,
      reusedGsubTtfBytes: reference.reusedGsubTtfBytes,
      reusedExactWoff2Bytes: reference.reusedExactWoff2Bytes,
      gsubHtmlBytes: reference.gsubHtmlBytes,
      gsubCssBytes: reference.gsubCssBytes,
      exactHtmlBytes: reference.exactHtmlBytes,
      exactCssBytes: reference.exactCssBytes,
      generatedBytes: reference.generatedBytes,
    },
    failures,
    limitations: reference.limitations,
    hardGatePassed,
    fullScaleBuildAuthorized: hardGatePassed,
    decision: hardGatePassed
      ? "retain for full-scale: bounded lattice probe passed winner, oracle-winner, and advance gates"
      : "reject lattice scaling: bounded probe failed winner, oracle-winner, or advance gate",
    comparisons,
  };
  await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
  const results = `# GSUB lattice-scale fine-scorer probe\n\n` +
    `Decision: **${report.decision}**.\n\n` +
    `This was bounded to eight groups and ten fixtures; no full bank was built. ` +
    `${candidateComparisons.toLocaleString()} candidate buckets were compared against a newly generated ` +
    `0.03125-scale exact CSS-dispatch baseline. The maximum absolute delta was ` +
    `${maximumAbsoluteCandidateDelta}, with ${differingCandidateBuckets.toLocaleString()} differing buckets. ` +
    `GSUB/exact winner agreement was ${(gsubExactWinnerMatches / cases * 100).toFixed(2)}%; ` +
    `GSUB/model-oracle and exact/model-oracle winner agreement were ` +
    `${(gsubOracleWinnerMatches / cases * 100).toFixed(2)}% and ` +
    `${(exactOracleWinnerMatches / cases * 100).toFixed(2)}%.\n\n` +
    `Dynamic cv01 settings were ${dynamicFeatureValid ? "valid" : "invalid"}. ` +
    `${glyphMeasurements.toLocaleString()} individual glyph advances were measured; the maximum was ` +
    `${maximumBrowserGlyphAdvancePx.toFixed(3)}px. The source-font theoretical maximum is ` +
    `${reference.sourceTheoreticalAdvances.maximumAdjustedPx.toLocaleString()}px and the existing ` +
    `full-bank h3 complement projects to ` +
    `${reference.knownFullH3Complement.adjustedPx.toLocaleString()}px at this scale, below the ` +
    `${reference.chromeAdvanceCeilingPx.toLocaleString()}px ceiling.\n\n` +
    `Median isolated group switching was ${gsubMedian.toFixed(3)}ms for GSUB and ` +
    `${exactMedian.toFixed(3)}ms for matched CSS dispatch ` +
    `(${(speedupFraction * 100).toFixed(1)}% speedup; 25% required).\n\n` +
    `Limitations: ${reference.limitations.join(" ")}\n`;
  await fs.writeFile(new URL("RESULTS.md", root), results);
  console.log(JSON.stringify(report, null, 2));
  if (!hardGatePassed) process.exitCode = 1;
} finally {
  await browser.close();
}
