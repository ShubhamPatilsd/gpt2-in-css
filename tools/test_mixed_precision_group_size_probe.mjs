import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const server = process.env.MIXED_GROUP_SIZE_SERVER ?? "http://127.0.0.1:4189";
const experiment = "gpt2-mixed-precision-group-size-sweep";
const controlPath = "gpt2-mixed-precision-hotk-sweep/k2";
const experimentRoot = new URL(`../experiments/${experiment}/`, import.meta.url);
const controlRoot = new URL(`../experiments/${controlPath}/`, import.meta.url);
const manifest = JSON.parse(
  await fs.readFile(new URL("browser-artifacts.json", experimentRoot), "utf8"),
);
const requested = new Set(
  (process.env.MIXED_GROUP_SIZE_VARIANTS ?? manifest.candidateVariants.join(","))
    .split(",")
    .filter(Boolean),
);
const variants = manifest.candidateVariants.filter((name) => requested.has(name));
if (variants.length === 0) throw new Error("no prepared variant selected");
const rounds = Math.max(
  1,
  Number.parseInt(process.env.MIXED_GROUP_SIZE_ROUNDS ?? "1", 10),
);
const fixtureLimit = Math.min(
  10,
  Math.max(
    1,
    Number.parseInt(process.env.MIXED_GROUP_SIZE_FIXTURE_LIMIT ?? "10", 10),
  ),
);
const variantIndexOffset = Math.max(
  0,
  Number.parseInt(process.env.MIXED_GROUP_SIZE_VARIANT_INDEX_OFFSET ?? "0", 10),
);

function normalizeReference(reference) {
  return {
    ...reference,
    scoreScale: reference.scoreScale ?? 256,
    scoreStridePx: reference.scoreStridePx ?? 4,
    stopGapBuckets: reference.stopGapBuckets ?? 48,
    exactUpperRows: reference.exactUpperRows ??
      reference.upperRowsReplacedWithGlobalInt16,
  };
}

const controlReference = normalizeReference(JSON.parse(
  await fs.readFile(new URL("reference.json", controlRoot), "utf8"),
));

function percentile(sorted, fraction) {
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * fraction))];
}

function statistics(values) {
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

function fixtureStyle(reference, fixture) {
  const fixtures = reference.certifiedFixtures;
  const declarations = fixtures.hiddenVectors[fixture]
    .map((value, dimension) => `--h${dimension}:${value}`);
  declarations.push(
    `--score-offset:${-fixtures.scoreFloors[fixture] * reference.scoreScale * reference.scoreStridePx}px`,
  );
  return declarations.join(";");
}

async function loadPage(context, path) {
  const page = await context.newPage();
  page.setDefaultTimeout(900_000);
  const failures = [];
  page.on("requestfailed", (request) => failures.push({
    url: request.url(),
    error: request.failure()?.errorText,
  }));
  const started = performance.now();
  await page.goto(`${server}/experiments/${path}/index.html`, {
    waitUntil: "load",
    timeout: 900_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(
      () => requestAnimationFrame(resolve),
    ));
  });
  return { page, failures, milliseconds: performance.now() - started };
}

async function setInput(page, reference, fixture) {
  await page.locator("#model, .fine-stage").evaluateAll((elements, style) => {
    for (const element of elements) element.style.cssText = style;
  }, fixtureStyle(reference, fixture));
}

async function settleMixed(page, stages) {
  for (let pass = 0; pass < 3; pass += 1) {
    await page.locator("#result").evaluate(
      (element) => element.getBoundingClientRect().width,
    );
    for (let stage = 0; stage < stages; stage += 1) {
      const wrapper = page.locator(`#mixed-stage-${stage}`);
      if (await wrapper.evaluate(
        (element) => getComputedStyle(element).display,
      ) === "none") break;
      const dynamic = page.locator(`#dynamic-fine-stage-${stage}`);
      if (await dynamic.evaluate(
        (element) => getComputedStyle(element).display,
      ) !== "none") {
        await dynamic.evaluate((element) => element.getBoundingClientRect().width);
      }
      for (const selector of [
        `#mixed-choice-source-${stage}`,
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
        `#remaining-result-${stage + 1}`,
      ]) {
        await page.locator(selector).evaluate(
          (element) => element.getBoundingClientRect().width,
        );
      }
      const done = await page.locator(`#remaining-result-${stage + 1}`).evaluate(
        (element, property) => Number(
          getComputedStyle(element).getPropertyValue(property),
        ),
        `--done-${stage}`,
      );
      if (done === 1) break;
    }
  }
}

async function observeMixed(page, reference) {
  return page.evaluate(({ stages, hotGroups }) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    const hot = new Set(hotGroups);
    let group = number(getComputedStyle(document.querySelector("#result")), "--group");
    const observations = [];
    for (let stage = 0; stage < stages; stage += 1) {
      const wrapper = getComputedStyle(document.querySelector(`#mixed-stage-${stage}`));
      if (wrapper.display === "none") break;
      const dynamic = getComputedStyle(
        document.querySelector(`#dynamic-fine-stage-${stage}`),
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
        route: hot.has(group) ? "reused-exact-upper" : "dynamic-fine-grid",
        dynamicDisplay: dynamic.display,
        fineLocal: number(fine, `--fine-local-${stage}`),
        fineBucket: number(fine, `--fine-bucket-${stage}`),
        fineWinner: number(fine, `--fine-winner-${stage}`),
        bestBucket: number(fine, `--best-bucket-${stage}`),
        bestWinner: number(fine, `--best-winner-${stage}`),
        certificateGap: number(remaining, `--certificate-gap-${stage}`),
        nextUpperBucket: number(remaining, `--upper-bucket-${stage + 1}`),
        done: number(remaining, `--done-${stage}`),
      };
      observations.push(item);
      if (item.done === 1) break;
      group = number(remaining, `--remaining-group-${stage + 1}`);
    }
    return {
      stages: observations,
      activeStages: observations.length,
      reusedExactUpper: observations.filter(
        (item) => item.route === "reused-exact-upper",
      ).length,
      dynamicFineGrids: observations.filter(
        (item) => item.route === "dynamic-fine-grid",
      ).length,
      finalWinner: observations.at(-1)?.bestWinner,
      finalBucket: observations.at(-1)?.bestBucket,
    };
  }, { stages: reference.stages, hotGroups: reference.hotGroups });
}

async function evaluate(page, reference, fixture) {
  const started = performance.now();
  await setInput(page, reference, fixture);
  await settleMixed(page, reference.stages);
  return {
    fixture,
    milliseconds: performance.now() - started,
    output: await observeMixed(page, reference),
  };
}

async function forceVariantExactShadow(page, reference, group) {
  const stage = page.locator("#dynamic-fine-stage-0");
  const originalStyle = await stage.getAttribute("style");
  await stage.evaluate((element, selectedGroup) => {
    element.style.setProperty("--group", String(selectedGroup));
    element.style.setProperty("display", "grid", "important");
  }, group);
  let width = 0;
  for (let pass = 0; pass < 3; pass += 1) {
    width = await stage.evaluate((element) => element.getBoundingClientRect().width);
  }
  // Mirror the CSS contract in number space: convert the measured geometry to
  // px once, divide by scoreStridePx once, then decode the variant's
  // scoreStridePx/groupSize tie payload.
  const geometryPx = width + 0.001;
  const fineBucket = Math.floor(geometryPx / reference.scoreStridePx);
  const remainderPx = geometryPx - fineBucket * reference.scoreStridePx;
  const tieStepPx = reference.scoreStridePx / reference.groupSize;
  const tieCode = Math.round(remainderPx / tieStepPx);
  const fineLocal = reference.groupSize - 1 - tieCode;
  const shadow = {
    group,
    width,
    geometryPx,
    scoreStridePx: reference.scoreStridePx,
    tieStepPx,
    tieCode,
    fineBucket,
    fineLocal,
    fineWinner: group * reference.groupSize + fineLocal,
    validLocal: Number.isInteger(fineLocal) &&
      fineLocal >= 0 && fineLocal < reference.groupSize,
    source: "forced-variant-dynamic-exact-grid",
  };
  await stage.evaluate((element, savedStyle) => {
    if (savedStyle === null) element.removeAttribute("style");
    else element.setAttribute("style", savedStyle);
  }, originalStyle);
  return shadow;
}

async function attachLiveShadows(page, reference, samples) {
  let requested = 0;
  for (const sample of samples) {
    await setInput(page, reference, sample.fixture);
    await settleMixed(page, reference.stages);
    const groups = [...new Set(sample.output.stages.map((stage) => stage.group))];
    const shadows = [];
    for (const group of groups) {
      shadows.push(await forceVariantExactShadow(page, reference, group));
      requested += 1;
    }
    sample.output.exactShadows = shadows;
  }
  return requested;
}

function verifyLive(reference, sample) {
  const shadows = new Map(
    sample.output.exactShadows.map((shadow) => [shadow.group, shadow]),
  );
  let bestBucket = -Infinity;
  let bestWinner = Infinity;
  const expectedRoute = reference.certifiedFixtures
    .unrolledStageGroups[sample.fixture];
  const stageChecks = sample.output.stages.map((stage, index) => {
    const shadow = shadows.get(stage.group);
    if (shadow && (shadow.fineBucket > bestBucket ||
        (shadow.fineBucket === bestBucket && shadow.fineWinner < bestWinner))) {
      bestBucket = shadow.fineBucket;
      bestWinner = shadow.fineWinner;
    }
    const hot = reference.hotGroups.includes(stage.group);
    return {
      stage: index,
      routeGroupMatchesOfflineDiagnostic: stage.group === expectedRoute[index],
      liveExactShadowPresent: shadow !== undefined,
      liveExactShadowHasValidLocal: shadow?.validLocal === true,
      winnerMatchesLiveExactShadow: stage.fineWinner === shadow?.fineWinner,
      bucketMatchesLiveExactShadow: stage.fineBucket === shadow?.fineBucket,
      bestWinnerMatchesLiveRecompute: stage.bestWinner === bestWinner,
      bestBucketMatchesLiveRecompute: stage.bestBucket === bestBucket,
      gapArithmeticMatches:
        stage.certificateGap === stage.bestBucket - stage.nextUpperBucket,
      doneMatchesLiveGap:
        stage.done === (stage.certificateGap > reference.stopGapBuckets ? 1 : 0),
      routeDisplayMatches: hot
        ? stage.dynamicDisplay === "none"
        : stage.dynamicDisplay === "grid",
    };
  });
  const firstDone = sample.output.stages.findIndex((stage) => stage.done === 1);
  const liveChecksPass = stageChecks.every((stage) => [
    "liveExactShadowPresent",
    "liveExactShadowHasValidLocal",
    "winnerMatchesLiveExactShadow",
    "bucketMatchesLiveExactShadow",
    "bestWinnerMatchesLiveRecompute",
    "bestBucketMatchesLiveRecompute",
    "gapArithmeticMatches",
    "doneMatchesLiveGap",
    "routeDisplayMatches",
  ].every((key) => stage[key] === true));
  const check = {
    fixture: sample.fixture,
    stoppedAtFirstLiveDone: firstDone < 0
      ? sample.output.activeStages === reference.stages
      : sample.output.activeStages === firstDone + 1,
    finalWinnerMatchesLiveExactRoute: sample.output.finalWinner === bestWinner,
    finalDenseWinnerMatchesFixture:
      sample.output.finalWinner ===
      reference.certifiedFixtures.denseWinners[sample.fixture],
    stageChecks,
  };
  check.pass = liveChecksPass && check.stoppedAtFirstLiveDone &&
    check.finalWinnerMatchesLiveExactRoute && check.finalDenseWinnerMatchesFixture;
  return check;
}

function verifyControl(reference, sample) {
  return {
    fixture: sample.fixture,
    finalDenseWinnerMatchesFixture:
      sample.output.finalWinner ===
      reference.certifiedFixtures.denseWinners[sample.fixture],
    stoppedAtLiveDone: sample.output.stages.at(-1)?.done === 1 ||
      sample.output.activeStages === reference.stages,
  };
}

function workSummary(reference, samples) {
  const activeStageVisits = samples.reduce(
    (sum, sample) => sum + sample.output.activeStages,
    0,
  );
  const reusedExactUpper = samples.reduce(
    (sum, sample) => sum + sample.output.reusedExactUpper,
    0,
  );
  const dynamicFineGrids = samples.reduce(
    (sum, sample) => sum + sample.output.dynamicFineGrids,
    0,
  );
  return {
    exactUpperRows: reference.exactUpperRows,
    activeStageVisits,
    reusedExactUpper,
    dynamicFineGrids,
    dynamicFineCandidateRows: dynamicFineGrids * reference.groupSize,
  };
}

async function runPair(variant, variantIndex) {
  const candidateReference = normalizeReference(JSON.parse(await fs.readFile(
    new URL(`${variant}/reference.json`, experimentRoot),
    "utf8",
  )));
  if (candidateReference.certifiedFixtures.hiddenVectors.length < fixtureLimit ||
      controlReference.certifiedFixtures.hiddenVectors.length < fixtureLimit) {
    throw new Error(`requested ${fixtureLimit} fixtures are unavailable`);
  }

  const browser = await chromium.launch({
    executablePath,
    headless: true,
    args: ["--disable-background-timer-throttling"],
  });
  const candidateContext = await browser.newContext({
    viewport: { width: 800, height: 200 },
  });
  const controlContext = await browser.newContext({
    viewport: { width: 800, height: 200 },
  });
  let candidateLoad;
  let controlLoad;
  try {
    if (variantIndex % 2 === 0) {
      candidateLoad = await loadPage(
        candidateContext,
        `${experiment}/${variant}`,
      );
      controlLoad = await loadPage(controlContext, controlPath);
    } else {
      controlLoad = await loadPage(controlContext, controlPath);
      candidateLoad = await loadPage(
        candidateContext,
        `${experiment}/${variant}`,
      );
    }

    const warmup = fixtureLimit - 1 - (variantIndex % fixtureLimit);
    await evaluate(candidateLoad.page, candidateReference, warmup);
    await evaluate(controlLoad.page, controlReference, warmup);
    const fixtureOrder = Array.from(
      { length: fixtureLimit },
      (_, index) => index,
    );
    const candidateSamples = [];
    const controlSamples = [];
    for (const fixture of fixtureOrder) {
      if ((fixture + variantIndex) % 2 === 0) {
        candidateSamples.push(await evaluate(
          candidateLoad.page,
          candidateReference,
          fixture,
        ));
        controlSamples.push(await evaluate(
          controlLoad.page,
          controlReference,
          fixture,
        ));
      } else {
        controlSamples.push(await evaluate(
          controlLoad.page,
          controlReference,
          fixture,
        ));
        candidateSamples.push(await evaluate(
          candidateLoad.page,
          candidateReference,
          fixture,
        ));
      }
    }

    const shadowsRequested = await attachLiveShadows(
      candidateLoad.page,
      candidateReference,
      candidateSamples,
    );
    const candidateChecks = candidateSamples.map(
      (sample) => verifyLive(candidateReference, sample),
    );
    const controlChecks = controlSamples.map(
      (sample) => verifyControl(controlReference, sample),
    );
    const candidateStats = statistics(
      candidateSamples.map((sample) => sample.milliseconds),
    );
    const controlStats = statistics(
      controlSamples.map((sample) => sample.milliseconds),
    );
    const candidateWork = workSummary(candidateReference, candidateSamples);
    const controlWork = workSummary(controlReference, controlSamples);
    const semanticsPass = candidateChecks.every((check) => check.pass) &&
      controlChecks.every((check) => check.finalDenseWinnerMatchesFixture &&
        check.stoppedAtLiveDone);
    return {
      variant,
      isolatedFreshBrowser: true,
      loadOrder: variantIndex % 2 === 0
        ? ["candidate", "retained-g256-k2"]
        : ["retained-g256-k2", "candidate"],
      fixtureOrder,
      warmupFixture: warmup,
      requestFailures: {
        candidate: candidateLoad.failures,
        control: controlLoad.failures,
      },
      cold: {
        candidateLoadMilliseconds: candidateLoad.milliseconds,
        controlLoadMilliseconds: controlLoad.milliseconds,
        loadRatio: candidateLoad.milliseconds / controlLoad.milliseconds,
      },
      semanticsPass,
      decision: !semanticsPass
        ? "reject-transport"
        : candidateStats.mean < controlStats.mean
          ? "candidate-win"
          : "reject-scaling",
      comparison: {
        candidate: candidateStats,
        retainedG256K2: controlStats,
        normalizedWarmMeanRatio: candidateStats.mean / controlStats.mean,
        warmSpeedupPercent:
          (1 - candidateStats.mean / controlStats.mean) * 100,
      },
      work: {
        candidate: candidateWork,
        retainedG256K2: controlWork,
        normalized: {
          activeStageVisits:
            candidateWork.activeStageVisits / controlWork.activeStageVisits,
          dynamicFineGrids:
            candidateWork.dynamicFineGrids / controlWork.dynamicFineGrids,
          dynamicFineCandidateRows:
            candidateWork.dynamicFineCandidateRows /
            controlWork.dynamicFineCandidateRows,
        },
      },
      shadows: {
        requested: shadowsRequested,
        present: candidateChecks.reduce(
          (sum, check) => sum + check.stageChecks.filter(
            (stage) => stage.liveExactShadowPresent,
          ).length,
          0,
        ),
        source: "candidate variant's forced dynamic exact grid",
      },
      candidateChecks,
      controlChecks,
      candidateSamples,
      controlSamples,
    };
  } finally {
    await candidateContext.close();
    await controlContext.close();
    await browser.close();
  }
}

const results = [];
for (let index = 0; index < variants.length; index += 1) {
  results.push(await runPair(variants[index], index + variantIndexOffset));
}

const report = {
  chromeVersion: "fresh isolated Chromium process per variant",
  rounds,
  fixtureCount: fixtureLimit,
  isolatedPerVariant: true,
  control: controlPath,
  loadOrderAlternated: true,
  robustRepeatPerformed: false,
  longLivedCursorMcpTerminated: false,
  offlineResultsPreserved: true,
  allSemanticsPass: results.every((result) => result.semanticsPass),
  results,
};
await fs.writeFile(
  new URL("browser-results.json", experimentRoot),
  `${JSON.stringify(report, null, 2)}\n`,
);

const rows = results.map((result) =>
  `| ${result.variant} | ${result.semanticsPass ? "pass" : "FAIL"} | ` +
  `${result.comparison.candidate.mean.toFixed(1)} | ` +
  `${result.comparison.retainedG256K2.mean.toFixed(1)} | ` +
  `${result.comparison.normalizedWarmMeanRatio.toFixed(3)} | ` +
  `${result.work.candidate.dynamicFineCandidateRows.toLocaleString()} | ` +
  `${result.work.retainedG256K2.dynamicFineCandidateRows.toLocaleString()} | ` +
  `${result.decision} |`,
).join("\n");
const markdown = `# Mixed exact-upper group-size browser screen

One isolated round over ${fixtureLimit === 10 ? "all 10" : fixtureLimit} fixtures was run for each candidate. Every pair used a fresh candidate page, a fresh retained G256 K2 page, and a fresh browser process. Candidate/control load order alternated. No robust repeat was performed, and the long-lived Cursor MCP was not terminated.

| Variant | Live semantics | Candidate warm mean ms | G256 K2 mean ms | Normalized ratio | Candidate dynamic rows | G256 dynamic rows | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
${rows}

Fine winners and buckets are checked against each candidate's forced live dynamic exact grid. Best winner/bucket, certificate gap, done state, and final winner are then recomputed from those live shadows. NumPy bucket arrays are retained only as offline route diagnostics and are not transport pass/fail gates.

Full observations are in \`browser-results.json\`. The original offline report and \`offline-results.json\` are unchanged.
`;
await fs.writeFile(new URL("BROWSER-RESULTS.md", experimentRoot), markdown);

console.log(JSON.stringify({
  rounds,
  fixtureCount: report.fixtureCount,
  allSemanticsPass: report.allSemanticsPass,
  robustRepeatPerformed: report.robustRepeatPerformed,
  longLivedCursorMcpTerminated: report.longLivedCursorMcpTerminated,
  results: results.map((result) => ({
    variant: result.variant,
    semanticsPass: result.semanticsPass,
    decision: result.decision,
    normalizedWarmMeanRatio: result.comparison.normalizedWarmMeanRatio,
    warmSpeedupPercent: result.comparison.warmSpeedupPercent,
    work: result.work,
    shadows: result.shadows,
  })),
}, null, 2));

if (!report.allSemanticsPass) process.exitCode = 1;
