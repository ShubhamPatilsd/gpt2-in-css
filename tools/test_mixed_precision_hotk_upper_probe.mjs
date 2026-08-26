import fs from "node:fs/promises";
import { createRequire } from "node:module";

// This harness is intentionally dormant after the offline-first build.  The
// explicit opt-in prevents a static validation or accidental invocation from
// launching Chrome before the sweep owner approves the browser screen.
if (process.env.MIXED_HOTK_CONFIRM_BROWSER !== "1") {
  throw new Error(
    "browser run is gated; set MIXED_HOTK_CONFIRM_BROWSER=1 after approving offline candidates",
  );
}

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const server = process.env.MIXED_HOTK_SERVER ?? "http://127.0.0.1:4189";
const artifactRoot = new URL(
  "../experiments/gpt2-mixed-precision-hotk-sweep/",
  import.meta.url,
);
const manifest = JSON.parse(
  await fs.readFile(new URL("browser-artifacts.json", artifactRoot), "utf8"),
);
const offline = JSON.parse(
  await fs.readFile(new URL("offline-results.json", artifactRoot), "utf8"),
);
const controlDirectory = manifest.controlDirectory;
const rounds = Math.max(
  1,
  Number.parseInt(process.env.MIXED_HOTK_ROUNDS ?? "3", 10),
);

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

function fixtureStyle(fixtures, fixture) {
  const properties = fixtures.hiddenVectors[fixture]
    .map((value, dimension) => `--h${dimension}:${value}`);
  properties.push(`--score-offset:${-fixtures.scoreFloors[fixture] * 256 * 4}px`);
  return properties.join(";");
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
    await new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  return { page, failures, milliseconds: performance.now() - started };
}

async function setInput(page, fixtures, fixture) {
  await page.evaluate((style) => {
    for (const element of [
      document.querySelector(".cascade"),
      document.querySelector("#model"),
    ]) {
      element.style.cssText = style;
    }
  }, fixtureStyle(fixtures, fixture));
}

async function settleMixed(page, stages) {
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

async function settleControl(page, stages) {
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

async function observeMixed(page, stages, hotGroups) {
  return page.evaluate(({ stageCount, hot }) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    const hotSet = new Set(hot);
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
        route: hotSet.has(group) ? "reused-upper-row" : "dynamic-exact-grid",
        dynamicDisplay: dynamic.display,
        fineCode: number(fine, `--fine-code-${stage}`),
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
      reusedHotRows: observations.filter((item) => hotSet.has(item.group)).length,
      dynamicFineGrids: observations.filter((item) => !hotSet.has(item.group)).length,
      finalWinner: observations.at(-1)?.bestWinner,
    };
  }, { stageCount: stages, hot: hotGroups });
}

async function observeControl(page, stages) {
  return page.evaluate((stageCount) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    let group = number(
      getComputedStyle(document.querySelector("#result")),
      "--group",
    );
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
        done: number(remaining, `--done-${stage}`),
      };
      observations.push(item);
      if (item.done === 1) break;
      group = number(remaining, `--remaining-group-${stage + 1}`);
    }
    return { stages: observations };
  }, stages);
}

async function forceExactShadow(page, group) {
  const fineStage = page.locator("#fine-stage");
  await fineStage.evaluate((element, value) => {
    element.style.setProperty("--group", String(value));
  }, group);
  for (let pass = 0; pass < 3; pass += 1) {
    for (const selector of ["#fine-stage", ".fine-reader", "#fine-result"]) {
      await page.locator(selector).evaluate(
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
      fineWinner: value * 256 + fineLocal,
      source: "forced-control-exact-grid",
    };
  }, group);
  await fineStage.evaluate((element) => element.style.removeProperty("--group"));
  return shadow;
}

async function evaluateCandidate(page, fixtures, fixture, reference) {
  const started = performance.now();
  await setInput(page, fixtures, fixture);
  await settleMixed(page, reference.stages);
  return {
    fixture,
    milliseconds: performance.now() - started,
    output: await observeMixed(page, reference.stages, reference.hotGroups),
  };
}

async function evaluateControl(page, fixtures, fixture, stages) {
  const started = performance.now();
  await setInput(page, fixtures, fixture);
  await settleControl(page, stages);
  return {
    fixture,
    milliseconds: performance.now() - started,
    output: await observeControl(page, stages),
  };
}

async function runCandidate(browser, candidate, candidateIndex) {
  const reference = JSON.parse(await fs.readFile(
    new URL(`k${candidate.k}/reference.json`, artifactRoot),
    "utf8",
  ));
  const fixtures = reference.certifiedFixtures;
  const fixtureLimit = Math.min(
    fixtures.hiddenVectors.length,
    Math.max(1, Number.parseInt(
      process.env.MIXED_HOTK_FIXTURE_LIMIT ?? String(fixtures.hiddenVectors.length),
      10,
    )),
  );
  const roundReports = [];
  for (let round = 0; round < rounds; round += 1) {
    const candidateContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
    const controlContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
    let candidateLoad;
    let controlLoad;
    if ((round + candidateIndex) % 2 === 0) {
      candidateLoad = await loadPage(
        candidateContext,
        `gpt2-mixed-precision-hotk-sweep/k${candidate.k}`,
      );
      controlLoad = await loadPage(controlContext, controlDirectory);
    } else {
      controlLoad = await loadPage(controlContext, controlDirectory);
      candidateLoad = await loadPage(
        candidateContext,
        `gpt2-mixed-precision-hotk-sweep/k${candidate.k}`,
      );
    }
    const order = Array.from(
      { length: fixtureLimit },
      (_, index) => (index + round) % fixtureLimit,
    );
    const warmup = (fixtureLimit - 1 - round + fixtureLimit) % fixtureLimit;
    await evaluateCandidate(candidateLoad.page, fixtures, warmup, reference);
    await evaluateControl(controlLoad.page, fixtures, warmup, reference.stages);
    const candidateSamples = [];
    const controlSamples = [];
    for (const fixture of order) {
      if ((fixture + round) % 2 === 0) {
        candidateSamples.push(await evaluateCandidate(
          candidateLoad.page, fixtures, fixture, reference,
        ));
        controlSamples.push(await evaluateControl(
          controlLoad.page, fixtures, fixture, reference.stages,
        ));
      } else {
        controlSamples.push(await evaluateControl(
          controlLoad.page, fixtures, fixture, reference.stages,
        ));
        candidateSamples.push(await evaluateCandidate(
          candidateLoad.page, fixtures, fixture, reference,
        ));
      }
    }
    for (const sample of candidateSamples) {
      const control = controlSamples.find((item) => item.fixture === sample.fixture);
      const shadows = new Map(control.output.stages.map((stage) => [stage.group, stage]));
      for (const group of new Set(sample.output.stages.map((stage) => stage.group))) {
        if (!shadows.has(group)) {
          await setInput(controlLoad.page, fixtures, sample.fixture);
          await settleControl(controlLoad.page, reference.stages);
          shadows.set(group, await forceExactShadow(controlLoad.page, group));
        }
      }
      control.output.exactShadows = [...shadows.values()];
    }
    roundReports.push({
      round,
      order,
      loadOrder: (round + candidateIndex) % 2 === 0
        ? ["candidate", "control"] : ["control", "candidate"],
      cold: {
        candidateLoadMilliseconds: candidateLoad.milliseconds,
        controlLoadMilliseconds: controlLoad.milliseconds,
      },
      requestFailures: {
        candidate: candidateLoad.failures,
        control: controlLoad.failures,
      },
      candidateSamples,
      controlSamples,
    });
    await candidateContext.close();
    await controlContext.close();
  }

  const checks = [];
  for (const round of roundReports) {
    for (const sample of round.candidateSamples) {
      const control = round.controlSamples.find((item) => item.fixture === sample.fixture);
      const shadows = new Map(control.output.exactShadows.map((item) => [item.group, item]));
      let bestBucket = -Infinity;
      let bestWinner = Infinity;
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
          routeGroupMatchesOffline: stage.group ===
            fixtures.unrolledStageGroups[sample.fixture][index],
          exactShadowPresent: shadow !== undefined,
          winnerMatchesExactShadow: stage.fineWinner === shadow?.fineWinner,
          bucketMatchesExactShadow: stage.fineBucket === shadow?.fineBucket,
          bestWinnerMatchesLiveRecompute: stage.bestWinner === bestWinner,
          bestBucketMatchesLiveRecompute: stage.bestBucket === bestBucket,
          gapArithmeticMatches:
            stage.certificateGap === stage.bestBucket - stage.nextUpperBucket,
          doneMatchesGap: stage.done === (stage.certificateGap > 48 ? 1 : 0),
          routeDisplayMatches: hot
            ? stage.dynamicDisplay === "none"
            : stage.dynamicDisplay === "grid",
          standardTieDecoderNotStuckAt255:
            !hot || shadow?.fineWinner % 256 === 255 || stage.fineCode !== 255,
        };
      });
      const firstDone = sample.output.stages.findIndex((stage) => stage.done === 1);
      const pass = stageChecks.every((stage) => Object.entries(stage).every(
        ([key, value]) => key === "stage" || value === true,
      )) && sample.output.finalWinner === fixtures.denseWinners[sample.fixture] &&
        (firstDone < 0
          ? sample.output.activeStages === reference.stages
          : sample.output.activeStages === firstDone + 1);
      checks.push({ round: round.round, fixture: sample.fixture, pass, stageChecks });
    }
  }
  const candidateTimes = roundReports.flatMap((round) =>
    round.candidateSamples.map((sample) => sample.milliseconds));
  const controlTimes = roundReports.flatMap((round) =>
    round.controlSamples.map((sample) => sample.milliseconds));
  const candidateStats = statistics(candidateTimes);
  const controlStats = statistics(controlTimes);
  const semanticsPass = checks.length === rounds * fixtureLimit &&
    checks.every((check) => check.pass);
  return {
    k: candidate.k,
    hotGroups: reference.hotGroups,
    fixtureLimit,
    semanticsPass,
    decision: !semanticsPass ? "reject-transport"
      : candidateStats.mean < controlStats.mean ? "candidate-win" : "reject-scaling",
    comparison: {
      candidate: candidateStats,
      control: controlStats,
      meanRatio: candidateStats.mean / controlStats.mean,
      meanSpeedupPercent: (1 - candidateStats.mean / controlStats.mean) * 100,
    },
    work: {
      upperRowsAdded: reference.upperRowsAdded,
      upperRowsReplacedWithGlobalInt16: reference.upperRowsReplacedWithGlobalInt16,
      activeStageVisits: roundReports.reduce((sum, round) => sum +
        round.candidateSamples.reduce((inner, sample) =>
          inner + sample.output.activeStages, 0), 0),
      reusedHotRows: roundReports.reduce((sum, round) => sum +
        round.candidateSamples.reduce((inner, sample) =>
          inner + sample.output.reusedHotRows, 0), 0),
      dynamicFineGrids: roundReports.reduce((sum, round) => sum +
        round.candidateSamples.reduce((inner, sample) =>
          inner + sample.output.dynamicFineGrids, 0), 0),
    },
    checks,
    roundsDetail: roundReports,
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const candidates = [];
  for (let index = 0; index < manifest.candidates.length; index += 1) {
    candidates.push(await runCandidate(browser, manifest.candidates[index], index));
  }
  report = {
    chromeVersion: await browser.version(),
    rounds,
    screeningOnly: true,
    robustRepeatPerformed: false,
    benchmarkCaveat:
      "Long-lived Cursor MCP load was present, as in prior paired benchmarks, and was intentionally not terminated.",
    candidateK: manifest.candidateK,
    offlineParetoK: offline.pareto.contiguousLowK,
    allSemanticsPass: candidates.every((candidate) => candidate.semanticsPass),
    candidates,
  };
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("browser-results.json", artifactRoot),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify({
  chromeVersion: report.chromeVersion,
  rounds: report.rounds,
  allSemanticsPass: report.allSemanticsPass,
  candidates: report.candidates.map((candidate) => ({
    k: candidate.k,
    decision: candidate.decision,
    semanticsPass: candidate.semanticsPass,
    comparison: candidate.comparison,
    work: candidate.work,
  })),
}, null, 2));

if (!report.allSemanticsPass) process.exitCode = 1;
