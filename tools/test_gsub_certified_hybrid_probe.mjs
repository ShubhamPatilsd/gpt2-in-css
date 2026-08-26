import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const server = process.env.GSUB_HYBRID_SERVER ?? "http://127.0.0.1:4178";
const timingRounds = Number.parseInt(process.env.GSUB_HYBRID_TIMING_ROUNDS ?? "5", 10);
const root = new URL("../experiments/gsub-certified-hybrid/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));
const format = (value) => value == null ? "n/a" : `${value.toFixed(2)} ms`;

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

async function loadPage(browser, path) {
  const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
  const started = performance.now();
  await page.goto(`${server}/experiments/${path}`, { waitUntil: "load", timeout: 240_000 });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  return { page, milliseconds: performance.now() - started };
}

async function mutate(page, selector, fixture, group) {
  const hidden = reference.hiddenVectors[fixture];
  const floor = reference.scoreFloors[fixture];
  return page.evaluate(({ selector: rootSelector, hidden: values, floor: scoreFloor, group: groupId }) => {
    const scope = document.querySelector(rootSelector);
    values.forEach((value, dimension) => scope.style.setProperty(`--h${dimension}`, String(value)));
    scope.style.setProperty("--score-offset", `${-scoreFloor * 256 * 4}px`);
    scope.style.setProperty("--group", String(groupId));
    scope.getBoundingClientRect();
  }, { selector, hidden, floor, group });
}

async function settle(page) {
  await page.evaluate(() => new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function observeHybrid(page) {
  return page.evaluate(() => {
    const width = (selector) => document.querySelector(selector).getBoundingClientRect().width;
    const display = (selector) => getComputedStyle(document.querySelector(selector)).display;
    const distribution = (stageSelector) => {
      const widths = [...document.querySelectorAll(`${stageSelector} .gsub-candidate`)].map(
        (element) => element.getBoundingClientRect().width);
      let winnerLocal = 0;
      for (let local = 1; local < widths.length; local += 1) {
        if (widths[local] > widths[winnerLocal]) winnerLocal = local;
      }
      return {
        minimum: Math.min(...widths),
        maximum: Math.max(...widths),
        positive: widths.filter((value) => value > 0).length,
        distinct: new Set(widths).size,
        winnerLocal,
        winnerWidth: widths[winnerLocal],
      };
    };
    const finalStyle = getComputedStyle(document.querySelector("#final-result"));
    const exactStyle = getComputedStyle(document.querySelector("#exact-result"));
    return {
      topStageWidth: width("#gsub-top"),
      runnerStageWidth: width("#gsub-runner"),
      topDistribution: distribution("#gsub-top"),
      runnerDistribution: distribution("#gsub-runner"),
      topToken: Math.round(width("#top-token")),
      runnerLocal: Math.round(width("#runner-token")),
      marginBuckets: Math.round(width("#margin-result")),
      fallback: Math.round(width("#fallback-result")),
      exactDisplay: display("#exact-stage"),
      activeExactWinner: Math.round(width("#exact-result")),
      finalWinner: Math.round(width("#final-result")),
      finalComputedWidth: finalStyle.width,
      finalInheritedFallback: finalStyle.getPropertyValue("--fallback"),
      finalPositionAnchor: finalStyle.positionAnchor,
      exactAnchorName: exactStyle.anchorName,
      anchorSizeSupported: CSS.supports("width", "anchor-size(--exact-token width)"),
      boundedFeature: getComputedStyle(document.querySelector("#gsub-top")).fontFeatureSettings,
    };
  });
}

async function observeExact(page) {
  return page.evaluate(() => Math.round(
    document.querySelector("#baseline-exact-result").getBoundingClientRect().width));
}

async function forceHybrid(page) {
  return page.evaluate(() => document.querySelector("#final-result").getBoundingClientRect().width);
}

async function forcePure(page) {
  return page.evaluate(() => document.querySelector("#pure-gsub-stage").getBoundingClientRect().width);
}

async function observePure(page, group) {
  return page.evaluate((groupId) => {
    const widths = [...document.querySelectorAll("#pure-gsub-stage .gsub-candidate")].map(
      (element) => element.getBoundingClientRect().width);
    let local = 0;
    for (let index = 1; index < widths.length; index += 1) {
      if (widths[index] > widths[local]) local = index;
    }
    return groupId * 256 + local;
  }, group);
}

async function timeCases(page, selector, cases, rounds, observer) {
  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    for (const entry of cases) {
      const started = performance.now();
      await mutate(page, selector, entry.fixture, entry.group);
      await observer(page, entry.group);
      samples.push({ fixture: entry.fixture, group: entry.group, milliseconds: performance.now() - started });
    }
  }
  return samples;
}

function sampleMedian(samples, cases = null) {
  const keys = cases && new Set(cases.map((entry) => `${entry.fixture}:${entry.group}`));
  const values = samples
    .filter((entry) => !keys || keys.has(`${entry.fixture}:${entry.group}`))
    .map((entry) => entry.milliseconds);
  return values.length ? median(values) : null;
}

function resources(page) {
  return page.evaluate(() => performance.getEntriesByType("resource").map((entry) => ({
    name: entry.name,
    transferSize: entry.transferSize,
    decodedBodySize: entry.decodedBodySize,
  })));
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const [bounded, full, exact, pureBounded, pureFull] = await Promise.all([
    loadPage(browser, "gsub-certified-hybrid/index.html"),
    loadPage(browser, "gsub-certified-hybrid/full.html"),
    loadPage(browser, "gsub-certified-hybrid/exact.html"),
    loadPage(browser, "gsub-certified-hybrid/pure-bounded.html"),
    loadPage(browser, "gsub-certified-hybrid/pure-full.html"),
  ]);

  const pages = { bounded: bounded.page, full: full.page };
  const comparisons = [];
  const failures = [];
  for (const entry of reference.cases) {
    await mutate(exact.page, "#exact-root", entry.fixture, entry.group);
    await Promise.all(Object.values(pages).map((page) =>
      mutate(page, "#hybrid-root", entry.fixture, entry.group)));
    await Promise.all([settle(exact.page), ...Object.values(pages).map(settle)]);
    const baselineWinner = await observeExact(exact.page);
    for (const [bank, page] of Object.entries(pages)) {
      const observed = await observeHybrid(page);
      const expectedFallback = entry.group <= 1 || observed.marginBuckets <= reference.marginThresholdBuckets;
      const topologyHealthy = observed.topStageWidth > 0 && observed.runnerStageWidth > 0 &&
        observed.topDistribution.positive > 1 && observed.topDistribution.distinct > 1 &&
        observed.runnerDistribution.positive > 1 && observed.runnerDistribution.distinct > 1;
      const routeSourceMatches = expectedFallback
        ? observed.activeExactWinner === baselineWinner
        : observed.topToken === baselineWinner;
      const valid = observed.finalWinner === baselineWinner &&
        observed.fallback === Number(expectedFallback) &&
        (expectedFallback ? observed.exactDisplay === "grid" : observed.exactDisplay === "none") &&
        topologyHealthy && routeSourceMatches;
      const comparison = {
        ...entry, bank, baselineWinner, expectedFallback, topologyHealthy,
        routeSourceMatches, ...observed, valid,
      };
      comparisons.push(comparison);
      if (!valid) failures.push(comparison);
    }
  }

  const accepted = comparisons.filter((entry) => !entry.expectedFallback);
  const fallback = comparisons.filter((entry) => entry.expectedFallback);
  const acceptedByBank = Object.fromEntries(Object.keys(pages).map((bank) => [
    bank,
    accepted.filter((entry) => entry.bank === bank),
  ]));
  const fallbackByBank = Object.fromEntries(Object.keys(pages).map((bank) => [
    bank,
    fallback.filter((entry) => entry.bank === bank),
  ]));
  const timingCases = reference.cases;
  const boundedHybridSamples = await timeCases(
    bounded.page, "#hybrid-root", timingCases, timingRounds, forceHybrid);
  const fullHybridSamples = await timeCases(
    full.page, "#hybrid-root", timingCases, timingRounds, forceHybrid);
  const exactSamples = await timeCases(
    exact.page, "#exact-root", timingCases, timingRounds, observeExact);
  const boundedPureSamples = await timeCases(
    pureBounded.page, "#pure-root", timingCases, timingRounds, forcePure);
  const fullPureSamples = await timeCases(
    pureFull.page, "#pure-root", timingCases, timingRounds, forcePure);

  const medians = {
    boundedHybridMilliseconds: sampleMedian(boundedHybridSamples),
    fullHybridMilliseconds: sampleMedian(fullHybridSamples),
    exactMilliseconds: sampleMedian(exactSamples),
    boundedPureGsubMilliseconds: sampleMedian(boundedPureSamples),
    fullPureGsubMilliseconds: sampleMedian(fullPureSamples),
    boundedAcceptedHybridMilliseconds: sampleMedian(boundedHybridSamples, acceptedByBank.bounded),
    fullAcceptedHybridMilliseconds: sampleMedian(fullHybridSamples, acceptedByBank.full),
    boundedAcceptedPureGsubMilliseconds: sampleMedian(boundedPureSamples, acceptedByBank.bounded),
    fullAcceptedPureGsubMilliseconds: sampleMedian(fullPureSamples, acceptedByBank.full),
    boundedFallbackHybridMilliseconds: sampleMedian(boundedHybridSamples, fallbackByBank.bounded),
    fullFallbackHybridMilliseconds: sampleMedian(fullHybridSamples, fallbackByBank.full),
    boundedFallbackExactMilliseconds: sampleMedian(exactSamples, fallbackByBank.bounded),
    fullFallbackExactMilliseconds: sampleMedian(exactSamples, fallbackByBank.full),
  };
  const difference = (left, right) => left == null || right == null ? null : left - right;
  medians.boundedTopologyOverheadMilliseconds =
    difference(medians.boundedAcceptedHybridMilliseconds, medians.boundedAcceptedPureGsubMilliseconds);
  medians.fullTopologyOverheadMilliseconds =
    difference(medians.fullAcceptedHybridMilliseconds, medians.fullAcceptedPureGsubMilliseconds);
  medians.boundedFallbackOverExactMilliseconds =
    difference(medians.boundedFallbackHybridMilliseconds, medians.boundedFallbackExactMilliseconds);
  medians.fullFallbackOverExactMilliseconds =
    difference(medians.fullFallbackHybridMilliseconds, medians.fullFallbackExactMilliseconds);

  report = {
    chrome: browser.version(),
    thresholdBuckets: reference.marginThresholdBuckets,
    casesPerBank: reference.cases.length,
    comparisonCount: comparisons.length,
    acceptedCases: accepted.length,
    fallbackCases: fallback.length,
    finalWinnerMatches: comparisons.length - failures.length,
    allFinalWinnersMatchExact: failures.length === 0 && accepted.length > 0 && fallback.length > 0,
    failures,
    loadMilliseconds: {
      boundedHybrid: bounded.milliseconds,
      fullHybrid: full.milliseconds,
      exact: exact.milliseconds,
      boundedPureGsub: pureBounded.milliseconds,
      fullPureGsub: pureFull.milliseconds,
    },
    timingRounds,
    mutationMedians: medians,
    topology: reference.topology,
    resources: {
      boundedHybrid: await resources(bounded.page),
      fullHybrid: await resources(full.page),
      exact: await resources(exact.page),
    },
    comparisons,
  };
} finally {
  await browser.close();
}

await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
const m = report.mutationMedians;
const performanceRejected = report.allFinalWinnersMatchExact &&
  m.boundedFallbackHybridMilliseconds > m.exactMilliseconds &&
  m.fullFallbackHybridMilliseconds > m.exactMilliseconds;
const decision = report.allFinalWinnersMatchExact
  ? (performanceRejected ? "reject: topology cost erases hybrid benefit" : "pass")
  : "fail: rendered winner mismatch";
const markdown = `# GSUB-certified hybrid composition\n\n` +
  `Decision: **${decision}**. Correctness passed: the page-selected final winner matched the exact CSS-dispatched ` +
  `baseline in ${report.finalWinnerMatches}/${report.comparisonCount} bounded/full comparisons. ` +
  `${report.acceptedCases} cases accepted GSUB and ${report.fallbackCases} activated exact fallback.\n\n` +
  `| Median mutation | Time |\n| --- | ---: |\n` +
  `| Bounded pure GSUB (accepted cases) | ${format(m.boundedAcceptedPureGsubMilliseconds)} |\n` +
  `| Bounded hybrid (accepted cases) | ${format(m.boundedAcceptedHybridMilliseconds)} |\n` +
  `| Bounded accepted-path topology overhead | ${format(m.boundedTopologyOverheadMilliseconds)} |\n` +
  `| Full pure GSUB (accepted cases) | ${format(m.fullAcceptedPureGsubMilliseconds)} |\n` +
  `| Full hybrid (accepted cases) | ${format(m.fullAcceptedHybridMilliseconds)} |\n` +
  `| Full accepted-path topology overhead | ${format(m.fullTopologyOverheadMilliseconds)} |\n` +
  `| Exact CSS-dispatched baseline | ${format(m.exactMilliseconds)} |\n\n` +
  `Fallback-path overhead over exact was ${format(m.boundedFallbackOverExactMilliseconds)} ` +
  `for the bounded bank and ${format(m.fullFallbackOverExactMilliseconds)} for the full bank.\n\n` +
  `The gate is CSS-only: a max-content grid decodes the GSUB top-1, a second grid masks ` +
  `that local index to decode the runner-up, and the rendered bucket margin selects either ` +
  `the GSUB token or the conditionally displayed exact scorer. JavaScript only mutates inputs ` +
  `and reads element geometry.\n\n` +
  `## Limitations\n\n` +
  `The six-bucket threshold remains an empirical Chromium/font-construction bound, not a ` +
  `portable proof. The probe covers eight selected groups and ten adversarial/representative ` +
  `fixture-group pairs; it does not certify arbitrary hidden vectors or other browser versions. ` +
  `Timing includes Playwright round trips and mixes accepted and fallback cases.\n`;
await fs.writeFile(new URL("RESULTS.md", root), markdown);
console.log(JSON.stringify({
  decision,
  comparisons: report.comparisonCount,
  finalWinnerMatches: report.finalWinnerMatches,
  acceptedCases: report.acceptedCases,
  fallbackCases: report.fallbackCases,
  mutationMedians: report.mutationMedians,
}, null, 2));
if (!report.allFinalWinnersMatchExact) process.exitCode = 1;
