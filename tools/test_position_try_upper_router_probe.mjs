import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const output = new URL("../experiments/position-try-upper-router/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", output), "utf8"));
const batches = Number(process.env.POSITION_TRY_ROUTER_BENCH_BATCHES ?? 31);
const mutationsPerBatch = Number(process.env.POSITION_TRY_ROUTER_BENCH_MUTATIONS ?? 40);

function median(values) {
  const ordered = values.toSorted((left, right) => left - right);
  return ordered[Math.floor(ordered.length / 2)];
}

async function settle(page) {
  await page.locator("#result").evaluate((element) => {
    element.getBoundingClientRect();
  });
}

async function readRoute(page) {
  return page.locator("#result").evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return {
      scoreBucket: Math.round(rect.width / 4),
      group: Math.round(rect.height) - 1,
      width: rect.width,
      height: rect.height,
      positionAnchor: style.positionAnchor,
      positionTryOrder: style.positionTryOrder,
    };
  });
}

async function validateFixtures(page, kind) {
  const checks = [];
  const probe = page.locator("#probe");
  for (let fixture = 0; fixture < reference.fixtures; fixture += 1) {
    await probe.evaluate((element, value) => { element.dataset.fixture = String(value); }, fixture);
    const firstGroup = reference.firstGroups[fixture];
    const source = page.locator(`.score-source-${firstGroup}`);
    if (kind === "position-try") {
      await probe.evaluate((element, epoch) => {
        element.style.removeProperty("--excluded-group");
        element.style.setProperty("--router-epoch", String(epoch));
      }, fixture % 2);
    } else {
      await source.evaluate((element) => { element.style.removeProperty("--enabled"); });
    }
    await settle(page);
    const unmasked = await readRoute(page);
    if (kind === "position-try") {
      await probe.evaluate((element, group) => {
        element.style.setProperty("--excluded-group", String(group));
      }, firstGroup);
    } else {
      await source.evaluate((element) => { element.style.setProperty("--enabled", "0"); });
    }
    await settle(page);
    const masked = await readRoute(page);
    if (kind === "position-try") {
      await probe.evaluate((element) => {
        element.style.removeProperty("--excluded-group");
      });
    } else {
      await source.evaluate((element) => { element.style.removeProperty("--enabled"); });
    }
    checks.push({
      fixture,
      kind,
      unmasked,
      masked,
      expectedUnmasked: {
        group: firstGroup,
        scoreBucket: reference.firstBuckets[fixture],
      },
      expectedMasked: {
        group: reference.maskedNextGroups[fixture],
        scoreBucket: reference.maskedNextBuckets[fixture],
      },
      correct: unmasked.group === firstGroup
        && unmasked.scoreBucket === reference.firstBuckets[fixture]
        && masked.group === reference.maskedNextGroups[fixture]
        && masked.scoreBucket === reference.maskedNextBuckets[fixture],
    });
  }
  return checks;
}

async function benchmark(page, kind) {
  const fixture = 0;
  const firstGroup = reference.firstGroups[fixture];
  await page.locator("#probe").evaluate((element, value) => {
    element.dataset.fixture = String(value);
  }, fixture);
  const result = page.locator("#result");
  const source = page.locator(`.score-source-${firstGroup}`);
  await source.evaluate((element) => { element.style.removeProperty("--enabled"); });
  await page.locator("#probe").evaluate((element) => {
    element.style.removeProperty("--excluded-group");
  });
  await settle(page);

  const samples = await result.evaluate(
    (element, [selector, sampleBatches, batchSize, expectedFirst, expectedNext, routerKind]) => {
      const scoreSource = document.querySelector(selector);
      const probe = document.querySelector("#probe");
      const durations = [];
      let exact = true;
      for (let warmup = 0; warmup < 20; warmup += 1) {
        const masked = warmup % 2 === 0;
        if (routerKind === "position-try") {
          probe.style.setProperty("--excluded-group", masked ? String(expectedFirst) : "-1");
        } else {
          scoreSource.style.setProperty("--enabled", masked ? "0" : "1");
        }
        element.getBoundingClientRect();
      }
      for (let batch = 0; batch < sampleBatches; batch += 1) {
        const started = performance.now();
        for (let mutation = 0; mutation < batchSize; mutation += 1) {
          const masked = mutation % 2 === 0;
          if (routerKind === "position-try") {
            probe.style.setProperty("--excluded-group", masked ? String(expectedFirst) : "-1");
          } else {
            scoreSource.style.setProperty("--enabled", masked ? "0" : "1");
          }
          const rect = element.getBoundingClientRect();
          const group = Math.round(rect.height) - 1;
          exact &&= group === (masked ? expectedNext : expectedFirst);
        }
        durations.push((performance.now() - started) / batchSize);
      }
      scoreSource.style.setProperty("--enabled", "1");
      probe.style.setProperty("--excluded-group", "-1");
      element.getBoundingClientRect();
      return { durations, exact };
    },
    [
      `.score-source-${firstGroup}`,
      batches,
      mutationsPerBatch,
      firstGroup,
      reference.maskedNextGroups[fixture],
      kind,
    ],
  );
  return {
    kind,
    batches,
    mutationsPerBatch,
    medianMilliseconds: median(samples.durations),
    minimumMilliseconds: Math.min(...samples.durations),
    maximumMilliseconds: Math.max(...samples.durations),
    exactDuringBenchmark: samples.exact,
    samplesMilliseconds: samples.durations,
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 800, height: 400 },
  });
  const positionPage = await context.newPage();
  const baselinePage = await context.newPage();
  await positionPage.goto(new URL("index.html", output).href, { waitUntil: "load" });
  await baselinePage.goto(new URL("baseline.html", output).href, { waitUntil: "load" });

  const support = await positionPage.evaluate(() => {
    const style = getComputedStyle(document.querySelector("#result"));
    return {
      positionTryOrder: CSS.supports("position-try-order", "most-width")
        && style.positionTryOrder === "most-width",
      positionTryFallbacks: CSS.supports("position-try-fallbacks", "--upper-0"),
      negativeAnchorSizeInset: CSS.supports("right", "calc(-1 * anchor-size(width))"),
      parsedFallbackCount: style.positionTryFallbacks.split(",").length,
    };
  });
  const positionChecks = await validateFixtures(positionPage, "position-try");
  const baselineChecks = await validateFixtures(baselinePage, "baseline-two-pass");

  const baselineBenchmark = await benchmark(baselinePage, "baseline-two-pass");
  const positionBenchmark = await benchmark(positionPage, "position-try");
  const coveragePage = await context.newPage();
  const coverageCandidates = 12;
  const intendedWinner = 9;
  const anchors = Array.from(
    { length: coverageCandidates },
    (_, index) => `<i class="coverage-anchor coverage-anchor-${index}"></i>`,
  ).join("");
  const coverageRules = Array.from({ length: coverageCandidates }, (_, index) => `
    .coverage-anchor-${index}{position:fixed;anchor-name:--coverage-anchor-${index};
      width:${index === intendedWinner ? 500 : 100 + index}px;height:1px}
    @position-try --coverage-${index}{position-anchor:--coverage-anchor-${index};
      left:0;right:calc(-1 * anchor-size(width));top:0;
      width:anchor-size(width);height:${index + 1}px}`).join("");
  const coverageFallbacks = Array.from(
    { length: coverageCandidates },
    (_, index) => `--coverage-${index}`,
  ).join(",");
  await coveragePage.setContent(`<style>${coverageRules}
    .coverage-result{position:fixed;left:900px;top:0;width:1px;height:1px;
      position-try-order:most-width;position-try-fallbacks:${coverageFallbacks}}
    </style>${anchors}<i class="coverage-result"></i>`);
  const selectionCoverage = await coveragePage.locator(".coverage-result").evaluate(
    (element, winner) => {
      const rect = element.getBoundingClientRect();
      const selected = Math.round(rect.height) - 1;
      return {
        intendedWinner: winner,
        selected,
        selectedWidth: rect.width,
        positionAnchor: getComputedStyle(element).positionAnchor,
        correct: selected === winner,
      };
    },
    intendedWinner,
  );
  await coveragePage.close();
  const speedup = baselineBenchmark.medianMilliseconds
    / positionBenchmark.medianMilliseconds;
  const syntaxSupported = Object.entries(support)
    .filter(([name]) => name !== "parsedFallbackCount")
    .every(([, value]) => value)
    && support.parsedFallbackCount === reference.groups;
  const exact = positionChecks.every(({ correct }) => correct)
    && baselineChecks.every(({ correct }) => correct)
    && baselineBenchmark.exactDuringBenchmark
    && positionBenchmark.exactDuringBenchmark
    && selectionCoverage.correct;
  const accepted = syntaxSupported && exact && speedup >= 2;
  const rejectionReasons = [];
  if (!syntaxSupported) rejectionReasons.push("Chrome does not support the required position-try grammar");
  if (!positionChecks.every(({ correct }) => correct)) {
    rejectionReasons.push("one or more certified fixture/mask selections was inexact");
  }
  if (!selectionCoverage.correct) {
    rejectionReasons.push(
      `Chrome most-width effectively considered only the first five fallbacks: selected ${selectionCoverage.selected}, not late unique argmax ${selectionCoverage.intendedWinner}`,
    );
  }
  if (speedup < 2) rejectionReasons.push(`isolated mutation speedup was ${speedup.toFixed(3)}x (<2x)`);
  report = {
    status: accepted ? "accepted" : "rejected",
    accepted,
    rejectionReasons,
    chrome: await browser.version(),
    runtimeJavaScript: false,
    support,
    validation: {
      certifiedFixtures: positionChecks,
      baselineFixtures: baselineChecks,
      selectionCoverage,
      allExact: exact,
    },
    benchmark: {
      mutation: "exclude/restore the first selected group and force router geometry",
      positionTryMutation: "toggle --excluded-group; score-only mutations separately toggle --router-epoch",
      baseline: baselineBenchmark,
      positionTry: positionBenchmark,
      speedup,
      requiredSpeedup: 2,
    },
    elapsedMilliseconds: performance.now(),
  };
  await context.close();
} finally {
  await browser.close();
}

await fs.writeFile(new URL("browser-results.json", output), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify({
  status: report.status,
  rejectionReasons: report.rejectionReasons,
  chrome: report.chrome,
  syntaxSupported: report.support.positionTryOrder
    && report.support.positionTryFallbacks
    && report.support.negativeAnchorSizeInset
    && report.support.parsedFallbackCount === reference.groups,
  allExact: report.validation.allExact,
  speedup: report.benchmark.speedup,
  baselineMedianMilliseconds: report.benchmark.baseline.medianMilliseconds,
  positionTryMedianMilliseconds: report.benchmark.positionTry.medianMilliseconds,
}, null, 2));
if (!report.accepted) process.exitCode = 1;
