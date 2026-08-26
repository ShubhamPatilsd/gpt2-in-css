import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const directory = "gpt2-hvar-grid-output-head-certified-int10-parallel-tail";
const root = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));
const includeStress = process.env.GPT2_PARALLEL_TAIL_STRESS === "1";
const fixtures = reference.parallelTailFixtures.selected.filter(
  (fixture) => includeStress || fixture.kind !== "forced-parallel-stress",
);
const groups = reference.groups;

async function forcePrefix(page) {
  return page.evaluate(() => {
    document.querySelector("#result").getBoundingClientRect();
    document.querySelector("#fine-stage").getBoundingClientRect();
    document.querySelector("#fine-result").getBoundingClientRect();
    const done = [];
    for (let stage = 1; stage <= 6; stage += 1) {
      const remaining = document.querySelector(`#remaining-result-${stage}`);
      remaining.getBoundingClientRect();
      const value = Number(
        getComputedStyle(remaining).getPropertyValue(`--done-${stage - 1}`),
      );
      done.push(value);
      if (value === 1) break;
      if (stage < 6) {
        document.querySelector(`#fine-stage-${stage}`).getBoundingClientRect();
        document.querySelector(`#fine-result-${stage}`).getBoundingClientRect();
      }
    }
    return done;
  });
}

async function forceTail(page) {
  return page.evaluate(() => {
    const gateWidths = Array.from(document.querySelectorAll(".tail-gate"), (gate) =>
      gate.getBoundingClientRect().width);
    const activeGroups = gateWidths
      .map((width, group) => ({ width, group }))
      .filter(({ width }) => width >= 0.5)
      .map(({ group }) => group);
    for (const group of activeGroups) {
      for (const prefix of ["tail-fine-stage", "tail-fine-reader", "tail-fine-result",
        "tail-score-carrier", "tail-token-carrier"]) {
        document.querySelector(`#${prefix}-${group}`).getBoundingClientRect();
      }
    }
    for (const selector of ["#tail-prefix-score", "#tail-prefix-token",
      "#tail-score-max", "#tail-score-reader", "#tail-score-result",
      "#tail-token-max", "#tail-token-reader", "#tail-final-result"]) {
      document.querySelector(selector).getBoundingClientRect();
    }
    return activeGroups;
  });
}

async function settle(page) {
  await page.evaluate(() => document.fonts.ready);
  let prefixDone = [];
  let activeGroups = [];
  for (let pass = 0; pass < 4; pass += 1) {
    prefixDone = await forcePrefix(page);
    if (!prefixDone.includes(1)) {
      activeGroups = await forceTail(page);
    } else {
      // Force gate style resolution even on the fast path, without touching
      // the expensive scorer grids hidden under the first completed stage.
      activeGroups = await page.evaluate(() =>
        Array.from(document.querySelectorAll(".tail-gate"), (gate, group) => ({
          group,
          width: gate.getBoundingClientRect().width,
        })).filter(({ width }) => width >= 0.5).map(({ group }) => group));
    }
  }
  return { prefixDone, activeGroups };
}

function sameArray(left, right) {
  return left.length === right.length
    && left.every((value, index) => value === right[index]);
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 800, height: 200 },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(600000);
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(String(error)));
  const started = performance.now();
  await page.goto(
    `http://127.0.0.1:4178/experiments/${directory}/index.html`,
    { waitUntil: "load", timeout: 600000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const loadMilliseconds = performance.now() - started;
  const samples = [];

  for (let fixtureIndex = 0; fixtureIndex < fixtures.length; fixtureIndex += 1) {
    const fixture = fixtures[fixtureIndex];
    const fixtureStarted = performance.now();
    await page.evaluate((values) => {
      const cascade = document.querySelector(".cascade");
      const model = document.querySelector("#model");
      for (const element of [cascade, model]) {
        values.hidden.forEach((value, dimension) => {
          element.style.setProperty(`--h${dimension}`, String(value));
        });
        element.style.setProperty(
          "--score-offset",
          `${-values.floor * 256 * 4}px`,
        );
      }
      cascade.style.setProperty("--tail-allowance", String(values.allowance));
    }, {
      hidden: fixture.hiddenVector,
      floor: fixture.scoreFloor,
      allowance: fixture.totalAllowanceBuckets,
    });
    const settled = await settle(page);
    const output = await page.evaluate(() => {
      const number = (style, property) => Number(style.getPropertyValue(property));
      const coarse = getComputedStyle(document.querySelector("#result"));
      const groupsSeen = [number(coarse, "--group")];
      const first = getComputedStyle(document.querySelector("#fine-result"));
      const fineWinners = [number(first, "--refined-winner")];
      const fineBuckets = [number(first, "--fine-bucket")];
      let bestWinner = number(first, "--best-winner-0");
      let bestBucket = number(first, "--best-bucket-0");
      const done = [];
      const gaps = [];
      for (let stage = 1; stage <= 6; stage += 1) {
        const remaining = getComputedStyle(
          document.querySelector(`#remaining-result-${stage}`),
        );
        const stageDone = number(remaining, `--done-${stage - 1}`);
        done.push(stageDone);
        gaps.push(number(remaining, `--certificate-gap-${stage - 1}`));
        bestWinner = number(remaining, `--best-winner-${stage - 1}`);
        bestBucket = number(remaining, `--best-bucket-${stage - 1}`);
        if (stageDone === 1) break;
        if (stage < 6) {
          groupsSeen.push(number(remaining, `--remaining-group-${stage}`));
          const fine = getComputedStyle(
            document.querySelector(`#fine-result-${stage}`),
          );
          fineWinners.push(number(fine, `--fine-winner-${stage}`));
          fineBuckets.push(number(fine, `--fine-bucket-${stage}`));
          bestWinner = number(fine, `--best-winner-${stage}`);
          bestBucket = number(fine, `--best-bucket-${stage}`);
        }
      }

      const gateWidths = Array.from(document.querySelectorAll(".tail-gate"), (gate) =>
        gate.getBoundingClientRect().width);
      const activeGroups = gateWidths
        .map((width, group) => ({ width, group }))
        .filter(({ width }) => width >= 0.5)
        .map(({ group }) => group);
      const active = activeGroups.map((group) => {
        const style = getComputedStyle(document.querySelector(`#tail-fine-result-${group}`));
        return {
          group,
          display: getComputedStyle(
            document.querySelector(`#tail-fine-stage-${group}`),
          ).display,
          winner: number(style, `--tail-winner-${group}`),
          bucket: number(style, `--tail-bucket-${group}`),
          stageGeometryPixels: document.querySelector(
            `#tail-fine-stage-${group}`,
          ).getBoundingClientRect().width,
          readerGeometryPixels: document.querySelector(
            `#tail-fine-reader-${group}`,
          ).getBoundingClientRect().width,
          stageAnchorName: getComputedStyle(
            document.querySelector(`#tail-fine-stage-${group}`),
          ).anchorName,
          scoreGeometryPixels: document.querySelector(
            `#tail-score-carrier-${group}`,
          ).getBoundingClientRect().width,
          tokenGeometryPixels: document.querySelector(
            `#tail-token-carrier-${group}`,
          ).getBoundingClientRect().width,
        };
      });
      const allTailScorerDisplays = Array.from(
        document.querySelectorAll(".tail-fine-stage"),
        (stage) => getComputedStyle(stage).display,
      );
      const score = getComputedStyle(document.querySelector("#tail-score-result"));
      const final = getComputedStyle(document.querySelector("#tail-final-result"));
      return {
        groupsSeen,
        fineWinners,
        fineBuckets,
        done,
        gaps,
        bestWinner,
        bestBucket,
        activeGroups,
        active,
        displayedTailScorers: allTailScorerDisplays.filter(
          (display) => display !== "none",
        ).length,
        mergedBucket: number(score, "--tail-merged-bucket"),
        winningGroup: number(score, "--tail-winning-group"),
        finalTailWinner: number(final, "--tail-final-winner"),
        prefixScoreGeometryPixels: document.querySelector(
          "#tail-prefix-score",
        ).getBoundingClientRect().width,
        mergedScoreGeometryPixels: document.querySelector(
          "#tail-score-max",
        ).getBoundingClientRect().width,
        selectedTokenGeometryPixels: document.querySelector(
          "#tail-token-max",
        ).getBoundingClientRect().width,
      };
    });

    const firstDone = output.done.findIndex((value) => value === 1);
    const firstDoneZeroBased = firstDone >= 0 ? firstDone : null;
    const browserBranches = [{
      group: Math.floor(output.bestWinner / 256),
      winner: output.bestWinner,
      bucket: output.bestBucket,
      source: "prefix",
    }, ...output.active.map((value) => ({ ...value, source: "tail" }))];
    const browserMaximum = browserBranches.reduce((best, value) => {
      if (value.bucket > best.bucket) return value;
      if (value.bucket === best.bucket && value.winner < best.winner) return value;
      return best;
    });
    const fallbackUsed = firstDoneZeroBased === null;
    const finalWinner = fallbackUsed ? output.finalTailWinner : output.bestWinner;
    samples.push({
      fixture: fixtureIndex,
      kind: fixture.kind,
      corpusIndex: fixture.corpusIndex,
      milliseconds: performance.now() - fixtureStarted,
      fallbackUsed,
      firstDoneZeroBased,
      expectedFirstDoneZeroBased: fixture.firstDoneZeroBased,
      expectedCandidateGroups: fixture.candidateGroups,
      expectedCandidateWinners: fixture.candidateFineWinners,
      browserMaximum,
      finalWinner,
      targetWinner: fixture.targetWinner,
      denseWinner: fixture.denseWinner,
      targetMatchesDense: fixture.targetMatchesDense,
      output,
    });
    console.error(JSON.stringify({
      fixture: fixtureIndex,
      corpusIndex: fixture.corpusIndex,
      milliseconds: samples.at(-1).milliseconds,
      activeGroups: output.activeGroups,
      finalWinner,
    }));
  }

  const mutations = samples.map(({ milliseconds }) => milliseconds)
    .sort((left, right) => left - right);
  const fallbackSamples = samples.filter(({ fallbackUsed }) => fallbackUsed);
  const easySamples = samples.filter(({ fallbackUsed }) => !fallbackUsed);
  report = {
    chrome: await browser.version(),
    directory,
    fullFanoutGroups: groups,
    prefixGroups: reference.prefixExactGroups,
    includeStress,
    currentAllowances: reference.fixtureSelection.currentAllowances,
    loadMilliseconds,
    loadAndFirstEvaluationMilliseconds: loadMilliseconds + samples[0].milliseconds,
    elapsedMilliseconds: performance.now() - started,
    medianMutationMilliseconds: mutations[Math.floor(mutations.length / 2)],
    mutationRangeMilliseconds: [mutations[0], mutations.at(-1)],
    fixtures: samples.length,
    easyFixtures: easySamples.length,
    fallbackFixtures: fallbackSamples.length,
    activeGroupCounts: samples.map(({ output }) => output.activeGroups.length),
    easyPathBypassesFallback: easySamples.length > 0 && easySamples.every(({ output }) =>
      output.activeGroups.length === 0 && output.displayedTailScorers === 0),
    hardPathUsesFallback: fallbackSamples.length > 0 && fallbackSamples.every(({ output }) =>
      output.activeGroups.length > 0
      && output.displayedTailScorers === output.activeGroups.length),
    allPrefixGroupsMatchOffline: samples.every(({ output, fixture }) =>
      output.groupsSeen.every((group, index) =>
        group === fixtures[fixture].prefixGroups[index])),
    allScreenPrefixWinnersMatchOffline: samples.filter(
      ({ kind }) => kind !== "forced-parallel-stress",
    ).every(({ output, fixture }) =>
      output.fineWinners.every((winner, index) =>
        winner === fixtures[fixture].prefixFineWinners[index])),
    allStrictStopDecisionsMatchOffline: samples.every((sample) =>
      sample.firstDoneZeroBased === sample.expectedFirstDoneZeroBased),
    allActiveGroupsMatchOffline: samples.every((sample) =>
      sameArray(sample.output.activeGroups, sample.expectedCandidateGroups)),
    allActiveGroupWinnersMatchOffline: samples.every((sample) =>
      sample.output.active.every(({ group, winner }) => {
        const index = sample.expectedCandidateGroups.indexOf(group);
        return index >= 0 && winner === sample.expectedCandidateWinners[index];
      })),
    allNWayScoreGroupMergesMatchBrowserBranches: fallbackSamples.every((sample) =>
      sample.output.mergedBucket === sample.browserMaximum.bucket
      && sample.output.winningGroup === sample.browserMaximum.group
      && sample.output.mergedScoreGeometryPixels === Math.max(
        sample.output.prefixScoreGeometryPixels,
        ...sample.output.active.map(({ scoreGeometryPixels }) => scoreGeometryPixels),
      )),
    allTokenPlaneSelectionsMatchBrowserBranches: fallbackSamples.every((sample) =>
      sample.output.finalTailWinner === sample.browserMaximum.winner
      && sample.output.selectedTokenGeometryPixels === sample.browserMaximum.winner),
    allFinalWinnersMatchOfflineTarget: samples.every(({ finalWinner, targetWinner }) =>
      finalWinner === targetWinner),
    denseWinnersCorrectWhereTargetMatchesDense: samples.filter(
      ({ targetMatchesDense }) => targetMatchesDense,
    ).every(({ finalWinner, denseWinner }) => finalWinner === denseWinner),
    pageErrors,
    samples,
  };
  await context.close();
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("browser-results.json", root),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
