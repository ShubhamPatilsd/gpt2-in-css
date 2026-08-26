import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const server = process.env.MIXED_HOT2_SERVER ?? "http://127.0.0.1:4189";
const directory = process.env.MIXED_HOT2_DIRECTORY
  ?? "gpt2-mixed-precision-hot2-upper";
const controlDirectory = process.env.MIXED_HOT2_CONTROL_DIRECTORY
  ?? "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated";
const artifactRoot = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(
  await fs.readFile(new URL("reference.json", artifactRoot), "utf8"),
);
const fixtures = reference.certifiedFixtures;
const stages = reference.stages;
const fixtureLimit = Math.min(
  fixtures.hiddenVectors.length,
  Math.max(1, Number.parseInt(
    process.env.MIXED_HOT2_FIXTURE_LIMIT ?? String(fixtures.hiddenVectors.length),
    10,
  )),
);
if (fixtureLimit === 2) {
  const first = fixtures.unrolledStageGroups[0];
  const second = fixtures.unrolledStageGroups[1];
  if (first[0] > 1 || second[0] <= 1 || !second.slice(1).some((group) => group <= 1)) {
    throw new Error(
      `two-fixture falsification coverage changed: ${JSON.stringify([first, second])}`,
    );
  }
}

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

function fixtureStyle(fixture) {
  const hidden = fixtures.hiddenVectors[fixture];
  const properties = hidden
    .map((value, dimension) => `--h${dimension}:${value}`);
  properties.push(`--score-offset:${-fixtures.scoreFloors[fixture] * 256 * 4}px`);
  properties.push(`--query-norm:${Math.sqrt(
    hidden.reduce((sum, value) => sum + value * value, 0),
  )}`);
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

async function settleMixed(page) {
  for (let pass = 0; pass < 3; pass += 1) {
    await page.locator("#result").evaluate(
      (element) => element.getBoundingClientRect().width,
    );
    for (let stage = 0; stage < stages; stage += 1) {
      const wrapper = page.locator(`#mixed-stage-${stage}`);
      if (await wrapper.evaluate((element) => getComputedStyle(element).display) === "none") {
        break;
      }
      const dynamic = page.locator(`#dynamic-fine-stage-${stage}`);
      if (await dynamic.evaluate((element) => getComputedStyle(element).display) !== "none") {
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
        (element, property) => Number(getComputedStyle(element).getPropertyValue(property)),
        `--done-${stage}`,
      );
      if (done === 1) break;
    }
  }
}

async function settleControl(page) {
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

async function observeMixed(page) {
  return page.evaluate((stageCount) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    let group = number(getComputedStyle(document.querySelector("#result")), "--group");
    const observations = [];
    for (let stage = 0; stage < stageCount; stage += 1) {
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
        route: group <= 1 ? "reused-upper-row" : "dynamic-exact-grid",
        dynamicDisplay: dynamic.display,
        fineCode: number(fine, `--fine-code-${stage}`),
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
      reusedHotRows: observations.filter((item) => item.group <= 1).length,
      dynamicFineGrids: observations.filter((item) => item.group > 1).length,
      finalWinner: observations.at(-1)?.bestWinner,
      finalBucket: observations.at(-1)?.bestBucket,
      hotRouteDebug: [0, 1].map((hotGroup) => {
        const inspect = (selector) => {
          const element = document.querySelector(selector);
          if (!element) return null;
          const style = getComputedStyle(element);
          return {
            rectWidth: element.getBoundingClientRect().width,
            computedWidth: style.width,
            display: style.display,
            anchorName: style.anchorName,
          };
        };
        return {
          group: hotGroup,
          exactMax: inspect(`.hot-exact-max-${hotGroup}`),
          routeProxy: inspect(`.hot-route-proxy-${hotGroup}`),
          originalWrapper: inspect(`.group-wrapper:has(>.group-${hotGroup})`),
        };
      }),
    };
  }, stages);
}

async function observeControl(page) {
  return page.evaluate((stageCount) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    const coarse = getComputedStyle(document.querySelector("#result"));
    let group = number(coarse, "--group");
    const observations = [];
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
        fineBucket: number(
          fine,
          stage === 0 ? "--fine-bucket" : `--fine-bucket-${stage}`,
        ),
        fineWinner: number(
          fine,
          stage === 0 ? "--refined-winner" : `--fine-winner-${stage}`,
        ),
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
      finalWinner: observations.at(-1)?.bestWinner,
      finalBucket: observations.at(-1)?.bestBucket,
    };
  }, stages);
}

async function forceExactShadow(page, group) {
  const stage = page.locator("#fine-stage");
  await stage.evaluate((element, value) => {
    element.style.setProperty("--group", String(value));
  }, group);
  for (let pass = 0; pass < 3; pass += 1) {
    for (const selector of ["#fine-stage", ".fine-reader", "#fine-result"]) {
      await page.locator(selector).first().evaluate(
        (element) => element.getBoundingClientRect().width,
      );
    }
  }
  const shadow = await page.locator("#fine-result").evaluate((element, value) => {
    const style = getComputedStyle(element);
    const fineBucket = Number(style.getPropertyValue("--fine-bucket"));
    const fineLocal = Number(style.getPropertyValue("--fine-local"));
    return {
      group: value,
      fineBucket,
      fineLocal,
      fineWinner: value * 256 + fineLocal,
      source: "forced-control-exact-grid",
    };
  }, group);
  await stage.evaluate((element) => element.style.removeProperty("--group"));
  return shadow;
}

async function evaluate(page, fixture, kind) {
  const started = performance.now();
  await setInput(page, fixture);
  if (kind === "mixed") await settleMixed(page);
  else await settleControl(page);
  return {
    fixture,
    milliseconds: performance.now() - started,
    output: kind === "mixed" ? await observeMixed(page) : await observeControl(page),
  };
}

const rounds = Math.max(1, Number.parseInt(process.env.MIXED_HOT2_ROUNDS ?? "3", 10));

async function runRound(browser, round) {
  const mixedContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const controlContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  let mixedLoad;
  let controlLoad;
  if (round % 2 === 0) {
    mixedLoad = await loadPage(mixedContext, directory);
    controlLoad = await loadPage(controlContext, controlDirectory);
  } else {
    controlLoad = await loadPage(controlContext, controlDirectory);
    mixedLoad = await loadPage(mixedContext, directory);
  }
  const warmup = (fixtureLimit - 1 - round + fixtureLimit) % fixtureLimit;
  const mixedFirst = await evaluate(mixedLoad.page, warmup, "mixed");
  const controlFirst = await evaluate(controlLoad.page, warmup, "control");
  const order = Array.from(
    { length: fixtureLimit },
    (_, index) => (index + round) % fixtureLimit,
  );
  const mixedSamples = [];
  const controlSamples = [];
  for (const fixture of order) {
    if ((fixture + round) % 2 === 0) {
      mixedSamples.push(await evaluate(mixedLoad.page, fixture, "mixed"));
      controlSamples.push(await evaluate(controlLoad.page, fixture, "control"));
    } else {
      controlSamples.push(await evaluate(controlLoad.page, fixture, "control"));
      mixedSamples.push(await evaluate(mixedLoad.page, fixture, "mixed"));
    }
  }

  let forcedExact = 0;
  let fromControlRoute = 0;
  let requested = 0;
  for (const mixed of mixedSamples) {
    const control = controlSamples.find((item) => item.fixture === mixed.fixture);
    const shadowByGroup = new Map(control.output.stages.map((stage) => [
      stage.group,
      {
        group: stage.group,
        fineBucket: stage.fineBucket,
        fineWinner: stage.fineWinner,
        source: "control-route-exact-grid",
      },
    ]));
    const requiredGroups = [...new Set(mixed.output.stages.map((stage) => stage.group))];
    const missing = requiredGroups.filter((group) => !shadowByGroup.has(group));
    requested += requiredGroups.length;
    fromControlRoute += requiredGroups.length - missing.length;
    if (missing.length) {
      await setInput(controlLoad.page, mixed.fixture);
      await settleControl(controlLoad.page);
      for (const group of missing) {
        shadowByGroup.set(group, await forceExactShadow(controlLoad.page, group));
        forcedExact += 1;
      }
    }
    control.output.exactShadows = [...shadowByGroup.values()];
    control.output.requiredMixedGroups = requiredGroups;
  }
  const result = {
    round,
    loadOrder: round % 2 === 0 ? ["mixed", "control"] : ["control", "mixed"],
    order,
    cold: {
      mixedLoadMilliseconds: mixedLoad.milliseconds,
      controlLoadMilliseconds: controlLoad.milliseconds,
      mixedFirstEvaluationMilliseconds: mixedFirst.milliseconds,
      controlFirstEvaluationMilliseconds: controlFirst.milliseconds,
      mixedLoadAndFirstEvaluationMilliseconds:
        mixedLoad.milliseconds + mixedFirst.milliseconds,
      controlLoadAndFirstEvaluationMilliseconds:
        controlLoad.milliseconds + controlFirst.milliseconds,
    },
    shadowCoverage: { requested, fromControlRoute, forcedExact },
    requestFailures: { mixed: mixedLoad.failures, control: controlLoad.failures },
    mixedSamples,
    controlSamples,
  };
  await mixedContext.close();
  await controlContext.close();
  return result;
}

function checkRound(round) {
  return round.mixedSamples.map((sample) => {
    const control = round.controlSamples.find((item) => item.fixture === sample.fixture);
    const controlByGroup = new Map(
      control.output.exactShadows.map((stage) => [stage.group, stage]),
    );
    const expectedGroups = fixtures.unrolledStageGroups[sample.fixture];
    let liveBestBucket = -Infinity;
    let liveBestWinner = Infinity;
    const stageChecks = sample.output.stages.map((stage, index) => {
      const shadow = controlByGroup.get(stage.group);
      if (shadow && (shadow.fineBucket > liveBestBucket ||
          (shadow.fineBucket === liveBestBucket && shadow.fineWinner < liveBestWinner))) {
        liveBestBucket = shadow.fineBucket;
        liveBestWinner = shadow.fineWinner;
      }
      return {
        stage: index,
        groupMatchesGeneratedMixedRoute: stage.group === expectedGroups[index],
        liveExactShadowPresent: shadow !== undefined,
        winnerMatchesLiveExactShadow: stage.fineWinner === shadow?.fineWinner,
        bucketMatchesLiveExactShadow: stage.fineBucket === shadow?.fineBucket,
        bestWinnerMatchesLiveRecompute: stage.bestWinner === liveBestWinner,
        bestBucketMatchesLiveRecompute: stage.bestBucket === liveBestBucket,
        certificateGapArithmeticMatches:
          stage.certificateGap === stage.bestBucket - stage.nextUpperBucket,
        doneMatchesLiveGap: stage.done === (stage.certificateGap > 48 ? 1 : 0),
        noUnexpectedConstant255: stage.group > 1 ||
          shadow?.fineWinner % 256 === 255 || stage.fineCode !== 255,
        routeDisplayMatches: stage.group <= 1
          ? stage.dynamicDisplay === "none"
          : stage.dynamicDisplay === "grid",
      };
    });
    const firstDone = sample.output.stages.findIndex((stage) => stage.done === 1);
    const check = {
      round: round.round,
      fixture: sample.fixture,
      stoppedAtFirstLiveDone: firstDone < 0
        ? sample.output.activeStages === stages
        : sample.output.activeStages === firstDone + 1,
      finalExactWinnerMatches:
        sample.output.finalWinner === fixtures.denseWinners[sample.fixture],
      stageChecks,
    };
    check.pass = check.stoppedAtFirstLiveDone &&
      check.finalExactWinnerMatches && stageChecks.every((stage) =>
        Object.entries(stage).every(([key, value]) => key === "stage" || value === true));
    return check;
  });
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const roundReports = [];
  for (let round = 0; round < rounds; round += 1) {
    roundReports.push(await runRound(browser, round));
  }
  const checks = roundReports.flatMap(checkRound);
  const mixedTimes = roundReports.flatMap((round) =>
    round.mixedSamples.map((item) => item.milliseconds));
  const controlTimes = roundReports.flatMap((round) =>
    round.controlSamples.map((item) => item.milliseconds));
  const mixedStats = statistics(mixedTimes);
  const controlStats = statistics(controlTimes);
  const semanticsPass = checks.length === rounds * fixtureLimit &&
    checks.every((check) => check.pass);
  const perRound = roundReports.map((round) => {
    const mixed = statistics(round.mixedSamples.map((item) => item.milliseconds));
    const control = statistics(round.controlSamples.map((item) => item.milliseconds));
    return {
      round: round.round,
      loadOrder: round.loadOrder,
      fixtureOrder: round.order,
      mixedMeanMilliseconds: mixed.mean,
      controlMeanMilliseconds: control.mean,
      meanRatio: mixed.mean / control.mean,
      meanSpeedupPercent: (1 - mixed.mean / control.mean) * 100,
    };
  });
  const reusedHotRows = roundReports.reduce((sum, round) => sum +
    round.mixedSamples.reduce((inner, sample) => inner + sample.output.reusedHotRows, 0), 0);
  const dynamicFineGrids = roundReports.reduce((sum, round) => sum +
    round.mixedSamples.reduce((inner, sample) => inner + sample.output.dynamicFineGrids, 0), 0);
  const requested = roundReports.reduce((sum, round) => sum + round.shadowCoverage.requested, 0);
  const fromControlRoute = roundReports.reduce(
    (sum, round) => sum + round.shadowCoverage.fromControlRoute, 0);
  const forcedExact = roundReports.reduce(
    (sum, round) => sum + round.shadowCoverage.forcedExact, 0);
  const missing = checks.reduce((sum, check) => sum + check.stageChecks.filter(
    (stage) => !stage.liveExactShadowPresent).length, 0);
  report = {
    experiment: directory,
    control: controlDirectory,
    chromeVersion: await browser.version(),
    rounds,
    fixtureLimit,
    semanticsPass,
    decision: semanticsPass && mixedStats.mean < controlStats.mean
      ? "retain"
      : semanticsPass ? "reject-scaling" : "reject-transport",
    comparison: {
      mixed: mixedStats,
      exactInt10Control: controlStats,
      meanRatio: mixedStats.mean / controlStats.mean,
      meanSpeedupPercent: (1 - mixedStats.mean / controlStats.mean) * 100,
      perRound,
    },
    cold: roundReports.map((round) => ({ round: round.round, ...round.cold })),
    work: {
      upperRowsAdded: reference.upperRowsAdded,
      upperRowsReplacedWithGlobalInt16: reference.upperRowsReplacedWithGlobalInt16,
      speculativeParallelFineRows: reference.speculativeParallelFineRows,
      activeStageVisits: reusedHotRows + dynamicFineGrids,
      reusedHotRows,
      dynamicFineGrids,
      fineGridEvaluationsRemoved: reusedHotRows,
    },
    requestFailures: roundReports.map((round) => ({
      round: round.round,
      ...round.requestFailures,
    })),
    shadowCoverage: { requested, fromControlRoute, forcedExact, missing },
    checks,
    generatedBytes: reference.generatedBytes,
    assets: reference.assets,
    roundsDetail: roundReports,
  };
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("browser-results.json", artifactRoot),
  `${JSON.stringify(report, null, 2)}\n`,
);

const comparison = report.comparison;
const corpus = reference.corpusFeasibility;
const tie = reference.tieAnalysis;
const perRoundRows = comparison.perRound.map((round) =>
  `| ${round.round} | ${round.loadOrder.join(" then ")} | ${round.mixedMeanMilliseconds.toFixed(1)} ms | ${round.controlMeanMilliseconds.toFixed(1)} ms | ${round.meanRatio.toFixed(3)}x |`,
).join("\n");
const coldRows = report.cold.map((round) =>
  `| ${round.round} | ${round.mixedLoadMilliseconds.toFixed(1)} ms | ${round.controlLoadMilliseconds.toFixed(1)} ms | ${round.mixedLoadAndFirstEvaluationMilliseconds.toFixed(1)} ms | ${round.controlLoadAndFirstEvaluationMilliseconds.toFixed(1)} ms |`,
).join("\n");
const markdown = `# Mixed-precision hot-2 upper-head feasibility

Decision: **${report.decision}**.

The probe replaces 512 existing int10 upper rows (groups 0 and 1) with global-int16 rows. It adds **0 upper rows** and **0 speculative parallel fine rows**. A selected hot group reuses the tie-preserving \`--group-*\` grid anchor; the separate \`--score-group-*\` routing wrapper alone carries the ${reference.hotUpperAllowanceBuckets}-bucket safety offset. Only selected non-hot groups instantiate the ordinary 256-row fine grid.

## Exactness and feasibility

- Browser fixture checks against live exact per-group shadows: ${report.checks.filter((item) => item.pass).length}/${report.checks.length}; exactness is claimed only for checks whose \`pass\` field is true.
- Exact-shadow coverage: ${report.shadowCoverage.requested - report.shadowCoverage.missing}/${report.shadowCoverage.requested} selected groups (${report.shadowCoverage.fromControlRoute} on the control route, ${report.shadowCoverage.forcedExact} forced through the control exact grid).
- Offline corpus target retention: ${corpus.targetWinnerRetained}/${corpus.states}.
- Standard lexicographic corpus geometry: ${corpus.standardLexicographicGeometryMatches}/${corpus.standardLexicographicGeometryChecks}; agreement with the distinct unrounded raw-score contract is ${corpus.rawVsBucketHotGroupWinnerMatches}/${corpus.rawVsBucketHotGroupWinnerChecks}.
- Fine-grid evaluations removed in the browser screen: ${report.work.fineGridEvaluationsRemoved}/${report.work.activeStageVisits} active stage visits.
- Corpus-path fine-grid evaluations removable: ${corpus.fineGridEvaluationsRemoved}.

The browser probe uses the standard exact fine-stage lexicographic contract: rounded 1/256 score bucket first, then lower token ID. Its selected \`--group-*\` grid anchor carries bucket plus local tie; the separate \`--score-group-*\` wrapper receives the ${reference.hotUpperAllowanceBuckets}-bucket routing allowance. An analysis-only fitted permutation can recover raw-score winners in three bucket-collision cases, but it is not emitted by this probe (${tie.groups.map((item) => `group ${item.group}: ${item.precedenceEdges} fitted precedence edges`).join(", ")}).

Browser score buckets and winners are matched by selected group against the live exact six-stage control, not stale NumPy stage indices. Best-state is recomputed from those live per-group scores; certificate gap and stopping are checked from the mixed route's live next-upper bucket. Dense final winner remains an independent oracle.

## Aggregate warm timing

| Metric | Mixed upper | Six-stage exact/int10 control |
|---|---:|---:|
| warm mean (${comparison.mixed.count} paired samples) | ${comparison.mixed.mean.toFixed(1)} ms | ${comparison.exactInt10Control.mean.toFixed(1)} ms |
| warm median | ${comparison.mixed.median.toFixed(1)} ms | ${comparison.exactInt10Control.median.toFixed(1)} ms |
| warm p90 | ${comparison.mixed.p90.toFixed(1)} ms | ${comparison.exactInt10Control.p90.toFixed(1)} ms |

Mean ratio: **${comparison.meanRatio.toFixed(3)}x** (${comparison.meanSpeedupPercent.toFixed(1)}% ${comparison.meanSpeedupPercent >= 0 ? "faster" : "slower"}).

### Per-round warm means

| Round | Page load order | Mixed upper | Control | Ratio |
|---:|---|---:|---:|---:|
${perRoundRows}

### Cold loads

| Round | Mixed load | Control load | Mixed load + first evaluation | Control load + first evaluation |
|---:|---:|---:|---:|---:|
${coldRows}

## Topology and bytes

- Generated HTML: ${reference.generatedBytes["index.html"].toLocaleString()} bytes.
- Generated topology CSS: ${reference.generatedBytes["topology.css"].toLocaleString()} bytes.
- Reused int10 WOFF2: ${reference.assets.coarseFontWoff2Bytes.toLocaleString()} bytes; reused exact WOFF2: ${reference.assets.exactFontWoff2Bytes.toLocaleString()} bytes. No font was copied or rebuilt.
- The measured exact asset covers the full vocabulary; all byte figures above are actual loaded or reused assets.

## Interpretation

${report.decision === "reject-transport"
  ? "The transport failed exactness; timing is invalid and no scaling decision is made."
  : report.decision === "reject-scaling"
      ? "The exact construction removes selected hot fine-grid work but does not improve measured latency, so it is rejected as a scaling route."
      : "The robust three-round screen passes all semantic gates and improves aggregate warm latency, so this route is retained."}

Chrome: ${report.chromeVersion}. Full observations are in \`browser-results.json\`.
`;
await fs.writeFile(new URL("RESULTS.md", artifactRoot), markdown);

console.log(JSON.stringify({
  decision: report.decision,
  semanticsPass: report.semanticsPass,
  checksPassed: report.checks.filter((item) => item.pass).length,
  checksTotal: report.checks.length,
  comparison: report.comparison,
  cold: report.cold,
  work: report.work,
}, null, 2));

if (!report.semanticsPass) process.exitCode = 1;
