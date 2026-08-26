import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const directory = "gpt2-hvar-grid-output-head-certified-int10-parallel-pair";
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
    "#pair-max", "#pair-result",
  ];
  for (let pass = 0; pass < 4; pass += 1) {
    for (const selector of selectors) {
      await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
    }
  }
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
      const pair = getComputedStyle(document.querySelector("#pair-result"));
      const rect = (selector) => document.querySelector(selector).getBoundingClientRect().width;
      return {
        firstWinner: Number(first.getPropertyValue("--refined-winner")),
        firstBucket: Number(first.getPropertyValue("--fine-bucket")),
        secondGroup: Number(group.getPropertyValue("--pair-group")),
        secondWinner: Number(second.getPropertyValue("--fine-winner-2")),
        secondBucket: Number(second.getPropertyValue("--fine-bucket-2")),
        pairWinner: Number(pair.getPropertyValue("--pair-winner")),
        pairBucket: Number(pair.getPropertyValue("--pair-bucket")),
        firstGeometryPixels: rect("#pair-carrier-1"),
        secondGeometryPixels: rect("#pair-carrier-2"),
        mergedGeometryPixels: rect("#pair-max"),
      };
    });
    const firstWinsInBrowser = output.firstBucket > output.secondBucket
      || (output.firstBucket === output.secondBucket
        && output.firstWinner < output.secondWinner);
    const browserPairWinner = firstWinsInBrowser
      ? output.firstWinner : output.secondWinner;
    const browserPairBucket = Math.max(output.firstBucket, output.secondBucket);
    output.firstGeometryErrorPixels = output.firstGeometryPixels - (
      output.firstBucket * reference.scoreGeometryPixelsPerBucket
      + (50256 - output.firstWinner) / 64
    );
    output.secondGeometryErrorPixels = output.secondGeometryPixels - (
      output.secondBucket * reference.scoreGeometryPixelsPerBucket
      + (50256 - output.secondWinner) / 64
    );
    samples.push({
      fixture,
      milliseconds: performance.now() - fixtureStarted,
      output,
      expectedFirstWinner: fixtures.selectedGroupFineWinners[fixture],
      expectedSecondGroup: fixtures.parallelSecondGroups[fixture],
      expectedSecondWinner: fixtures.parallelSecondFineWinners[fixture],
      expectedPairWinner: fixtures.parallelPairWinners[fixture],
      expectedPairBucket: fixtures.parallelPairBuckets[fixture],
      browserPairWinner,
      browserPairBucket,
      denseWinner: fixtures.denseWinners[fixture],
    });
  }
  const mutations = samples.map(({ milliseconds }) => milliseconds)
    .sort((left, right) => left - right);
  report = {
    chrome: await browser.version(),
    directory,
    branchStructure: reference.branchStructure,
    scoreGeometryPixelsPerBucket: reference.scoreGeometryPixelsPerBucket,
    chromeLayoutLimitPixels: reference.chromeLayoutLimitPixels,
    maxFixtureMergeGeometryPixels: Math.max(
      ...samples.map(({ output }) => output.mergedGeometryPixels),
    ),
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
    allPairWinnersCorrect: samples.every(({ output, expectedPairWinner }) =>
      output.pairWinner === expectedPairWinner),
    allPairBucketsCorrect: samples.every(({ output, expectedPairBucket }) =>
      output.pairBucket === expectedPairBucket),
    allMergedBucketsDecodeBrowserBranchMax: samples.every(({
      output, browserPairBucket,
    }) => output.pairBucket === browserPairBucket),
    allMergedWinnersDecodeBrowserBranchMax: samples.every(({
      output, browserPairWinner,
    }) => output.pairWinner === browserPairWinner),
    maxCarrierGeometryErrorPixels: Math.max(...samples.flatMap(({ output }) => [
      Math.abs(output.firstGeometryErrorPixels),
      Math.abs(output.secondGeometryErrorPixels),
    ])),
    browserBranchMaxDenseWinnersCorrect: samples.filter(({
      browserPairWinner, denseWinner,
    }) => browserPairWinner === denseWinner).length,
    mergedGeometryIsBranchMax: samples.every(({ output }) =>
      output.mergedGeometryPixels
        === Math.max(output.firstGeometryPixels, output.secondGeometryPixels)),
    finalDenseWinnersCorrect: samples.filter(({ output, denseWinner }) =>
      output.pairWinner === denseWinner).length,
    comparison: {
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
