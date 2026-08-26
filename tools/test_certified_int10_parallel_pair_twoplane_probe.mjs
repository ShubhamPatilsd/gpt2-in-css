import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const directory = "gpt2-hvar-grid-output-head-certified-int10-parallel-pair-twoplane";
const root = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));
const fixtures = reference.certifiedFixtures;

async function readBenchmark(directoryName) {
  try {
    const result = JSON.parse(await fs.readFile(
      new URL(`../experiments/${directoryName}/browser-results.json`, import.meta.url),
      "utf8",
    ));
    const mutations = result.samples.map(({ milliseconds }) => milliseconds)
      .sort((left, right) => left - right);
    return {
      directory: directoryName,
      loadMilliseconds: result.loadMilliseconds,
      loadAndFirstEvaluationMilliseconds: result.loadAndFirstEvaluationMilliseconds,
      medianMutationMilliseconds: mutations[Math.floor(mutations.length / 2)],
      mutationRangeMilliseconds: [mutations[0], mutations.at(-1)],
    };
  } catch {
    return null;
  }
}

async function settle(page) {
  await page.evaluate(() => document.fonts.ready);
  const selectors = [
    "#result", "#fine-stage", "#fine-result", "#pair-group-result",
    "#fine-stage-2", "#fine-result-2", "#pair-carrier-1", "#pair-carrier-2",
    "#pair-max", "#pair-score-result", "#pair-token-choice", "#pair-result",
  ];
  for (let pass = 0; pass < 4; pass += 1) {
    for (const selector of selectors) {
      await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
    }
  }
}

async function runSyntheticTie(page, values) {
  await page.evaluate((probe) => {
    document.querySelector("#result").style.setProperty("--group", String(probe.firstGroup));
    document.querySelector("#fine-result").style.width = `${probe.firstToken}px`;
    document.querySelector("#fine-result-2").style.width = `${probe.secondToken}px`;
    document.querySelector("#pair-carrier-1").style.width = `${
      probe.bucket * 1024 + (197 - probe.firstGroup) * 4
    }px`;
    document.querySelector("#pair-carrier-2").style.width = `${
      probe.bucket * 1024 + (197 - probe.secondGroup) * 4
    }px`;
  }, values);
  for (let pass = 0; pass < 4; pass += 1) {
    for (const selector of ["#pair-max", "#pair-score-result", "#pair-token-choice", "#pair-result"]) {
      await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
    }
  }
  return page.evaluate(() => {
    const score = getComputedStyle(document.querySelector("#pair-score-result"));
    const pair = getComputedStyle(document.querySelector("#pair-result"));
    return {
      winningGroup: Number(score.getPropertyValue("--pair-winning-group")),
      useSecond: Number(score.getPropertyValue("--pair-use-second")),
      selectedTokenGeometryPixels:
        document.querySelector("#pair-token-choice").getBoundingClientRect().width,
      pairWinner: Number(pair.getPropertyValue("--pair-winner")),
    };
  });
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 800, height: 200 },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(300000);
  const started = performance.now();
  await page.goto(
    `http://127.0.0.1:4178/experiments/${directory}/index.html`,
    { waitUntil: "load", timeout: 300000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const loadMilliseconds = performance.now() - started;
  const samples = [];
  for (let fixture = 0; fixture < fixtures.hiddenVectors.length; fixture += 1) {
    const fixtureStarted = performance.now();
    await page.evaluate((values) => {
      for (const selector of ["#model", "#fine-stage", "#fine-stage-2"]) {
        const element = document.querySelector(selector);
        values.hidden.forEach((value, dimension) => {
          element.style.setProperty(`--h${dimension}`, String(value));
        });
        element.style.setProperty("--score-offset", `${-values.floor * 256 * 4}px`);
      }
    }, { hidden: fixtures.hiddenVectors[fixture], floor: fixtures.scoreFloors[fixture] });
    await settle(page);
    const output = await page.evaluate(() => {
      const first = getComputedStyle(document.querySelector("#fine-result"));
      const group = getComputedStyle(document.querySelector("#pair-group-result"));
      const second = getComputedStyle(document.querySelector("#fine-result-2"));
      const score = getComputedStyle(document.querySelector("#pair-score-result"));
      const pair = getComputedStyle(document.querySelector("#pair-result"));
      const rect = (selector) => document.querySelector(selector).getBoundingClientRect().width;
      return {
        firstWinner: Number(first.getPropertyValue("--refined-winner")),
        firstBucket: Number(first.getPropertyValue("--fine-bucket")),
        secondGroup: Number(group.getPropertyValue("--pair-group")),
        secondWinner: Number(second.getPropertyValue("--fine-winner-2")),
        secondBucket: Number(second.getPropertyValue("--fine-bucket-2")),
        scoreBucket: Number(score.getPropertyValue("--pair-bucket")),
        winningGroup: Number(score.getPropertyValue("--pair-winning-group")),
        useSecond: Number(score.getPropertyValue("--pair-use-second")),
        pairWinner: Number(pair.getPropertyValue("--pair-winner")),
        firstScoreGeometryPixels: rect("#pair-carrier-1"),
        secondScoreGeometryPixels: rect("#pair-carrier-2"),
        mergedScoreGeometryPixels: rect("#pair-max"),
        selectedTokenGeometryPixels: rect("#pair-token-choice"),
      };
    });
    const firstWinsInBrowser = output.firstBucket > output.secondBucket
      || (output.firstBucket === output.secondBucket
        && output.firstWinner < output.secondWinner);
    const browserPairWinner = firstWinsInBrowser
      ? output.firstWinner : output.secondWinner;
    const browserPairBucket = Math.max(output.firstBucket, output.secondBucket);
    const browserWinningGroup = Math.floor(browserPairWinner / 256);
    samples.push({
      fixture,
      milliseconds: performance.now() - fixtureStarted,
      output,
      expectedFirstWinner: fixtures.selectedGroupFineWinners[fixture],
      expectedSecondGroup: fixtures.parallelSecondGroups[fixture],
      expectedSecondWinner: fixtures.parallelSecondFineWinners[fixture],
      expectedOfflinePairWinner: fixtures.parallelPairWinners[fixture],
      browserPairWinner,
      browserPairBucket,
      browserWinningGroup,
      denseWinner: fixtures.denseWinners[fixture],
    });
  }
  const syntheticTieInputs = [
    { bucket: 5000, firstGroup: 5, firstToken: 1480, secondGroup: 3, secondToken: 1018 },
    { bucket: 5000, firstGroup: 2, firstToken: 700, secondGroup: 7, secondToken: 1800 },
  ];
  const syntheticEqualBucketTies = [];
  for (const input of syntheticTieInputs) {
    syntheticEqualBucketTies.push({ input, output: await runSyntheticTie(page, input) });
  }
  const mutations = samples.map(({ milliseconds }) => milliseconds)
    .sort((left, right) => left - right);
  report = {
    chrome: await browser.version(),
    directory,
    mergePlanes: reference.mergePlanes,
    scoreGeometryPixelsPerBucket: reference.scoreGeometryPixelsPerBucket,
    groupTiePixelsPerGroup: reference.groupTiePixelsPerGroup,
    maxGroupTieBandPixels: reference.maxGroupTieBandPixels,
    loadMilliseconds,
    loadAndFirstEvaluationMilliseconds: loadMilliseconds + samples[0].milliseconds,
    elapsedMilliseconds: performance.now() - started,
    medianMutationMilliseconds: mutations[Math.floor(mutations.length / 2)],
    mutationRangeMilliseconds: [mutations[0], mutations.at(-1)],
    fixtures: samples.length,
    allFirstWinnersCorrect: samples.every(({ output, expectedFirstWinner }) =>
      output.firstWinner === expectedFirstWinner),
    allSecondGroupsCorrect: samples.every(({ output, expectedSecondGroup }) =>
      output.secondGroup === expectedSecondGroup),
    allSecondWinnersCorrect: samples.every(({ output, expectedSecondWinner }) =>
      output.secondWinner === expectedSecondWinner),
    mergedScoreGeometryIsBranchMax: samples.every(({ output }) =>
      output.mergedScoreGeometryPixels === Math.max(
        output.firstScoreGeometryPixels, output.secondScoreGeometryPixels,
      )),
    allScoreBucketsDecodeBrowserBranchMax: samples.every(({
      output, browserPairBucket,
    }) => output.scoreBucket === browserPairBucket),
    allWinningGroupsDecodeBrowserBranchMax: samples.every(({
      output, browserWinningGroup,
    }) => output.winningGroup === browserWinningGroup),
    allBranchSelectionsCorrect: samples.every(({ output, browserPairWinner }) =>
      output.selectedTokenGeometryPixels === browserPairWinner),
    allPairWinnersDecodeBrowserBranchMax: samples.every(({
      output, browserPairWinner,
    }) => output.pairWinner === browserPairWinner),
    allPairWinnersMatchOffline: samples.every(({
      output, expectedOfflinePairWinner,
    }) => output.pairWinner === expectedOfflinePairWinner),
    finalDenseWinnersCorrect: samples.filter(({ output, denseWinner }) =>
      output.pairWinner === denseWinner).length,
    syntheticEqualBucketGroupTiesCorrect: syntheticEqualBucketTies.every(({
      input, output,
    }) => {
      const firstWins = input.firstGroup < input.secondGroup;
      return output.winningGroup === Math.min(input.firstGroup, input.secondGroup)
        && output.useSecond === (firstWins ? 0 : 1)
        && output.pairWinner === (firstWins ? input.firstToken : input.secondToken);
    }),
    syntheticEqualBucketTies,
    comparison: {
      failedOnePlane: await readBenchmark(
        "gpt2-hvar-grid-output-head-certified-int10-parallel-pair",
      ),
      serialTwoStep: await readBenchmark(
        "gpt2-hvar-grid-output-head-certified-upper-int10-two-step",
      ),
      gatedSixStage: await readBenchmark(
        "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated",
      ),
    },
    samples,
  };
  await context.close();
} finally {
  await browser.close();
}

await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
