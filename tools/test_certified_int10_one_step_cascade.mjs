import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const directory = "gpt2-hvar-grid-output-head-certified-upper-int10-one-step";
const root = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));
const fixtures = reference.certifiedFixtures;
const url = `http://127.0.0.1:4178/experiments/${directory}/index.html`;

async function settle(page) {
  await page.locator("#fine-stage").evaluate((element) =>
    element.getBoundingClientRect().width);
  await page.evaluate(() => document.fonts.ready);
  for (let pass = 0; pass < 3; pass += 1) {
    await page.locator("#result").evaluate((element) =>
      element.getBoundingClientRect().width);
    await page.locator("#fine-stage").evaluate((element) =>
      element.getBoundingClientRect().width);
    await page.locator("#fine-result").evaluate((element) =>
      element.getBoundingClientRect().width);
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
  page.setDefaultTimeout(240000);
  const started = performance.now();
  await page.goto(url, { waitUntil: "load", timeout: 240000 });
  await page.evaluate(() => document.fonts.ready);
  const loadMilliseconds = performance.now() - started;
  const samples = [];
  for (let fixture = 0; fixture < fixtures.hiddenVectors.length; fixture += 1) {
    const fixtureStarted = performance.now();
    await page.evaluate((values) => {
      for (const selector of ["#model", "#fine-stage"]) {
        const element = document.querySelector(selector);
        values.hidden.forEach((value, dimension) => {
          element.style.setProperty(`--h${dimension}`, String(value));
        });
        element.style.setProperty(
          "--score-offset",
          `${-values.floor * values.scoreScale * values.scoreStridePx}px`,
        );
      }
    }, {
      hidden: fixtures.hiddenVectors[fixture],
      floor: fixtures.scoreFloors[fixture],
      scoreScale: 256,
      scoreStridePx: 4,
    });
    await settle(page);
    const output = await page.evaluate(() => {
      const coarse = getComputedStyle(document.querySelector("#result"));
      const fine = getComputedStyle(document.querySelector("#fine-result"));
      return {
        upperWinner: Number(coarse.getPropertyValue("--winner")),
        upperGroup: Number(coarse.getPropertyValue("--group")),
        fineWinner: Number(fine.getPropertyValue("--refined-winner")),
        fineBucket: Number(fine.getPropertyValue("--fine-bucket")),
        queryNorm: Number(getComputedStyle(document.querySelector(".group-scroller"))
          .getPropertyValue("--query-norm")),
      };
    });
    samples.push({
      fixture,
      milliseconds: performance.now() - fixtureStarted,
      output,
      expectedUpperWinner: fixtures.upperWinners[fixture],
      expectedUpperGroup: fixtures.upperGroups[fixture],
      expectedFineWinner: fixtures.selectedGroupFineWinners[fixture],
      expectedFineBucket: fixtures.selectedGroupFineBuckets[fixture],
      denseWinner: fixtures.denseWinners[fixture],
      denseWinnerInSelectedGroup:
        fixtures.upperGroups[fixture] === fixtures.denseGroups[fixture],
    });
  }
  report = {
    chrome: await browser.version(),
    loadMilliseconds,
    loadAndFirstEvaluationMilliseconds: loadMilliseconds + samples[0].milliseconds,
    elapsedMilliseconds: performance.now() - started,
    fixtures: samples.length,
    allUpperGroupsCorrect: samples.every(({ output, expectedUpperGroup }) =>
      output.upperGroup === expectedUpperGroup),
    allFineWinnersCorrect: samples.every(({ output, expectedFineWinner }) =>
      output.fineWinner === expectedFineWinner),
    allFineBucketsCorrect: samples.every(({ output, expectedFineBucket }) =>
      output.fineBucket === expectedFineBucket),
    denseWinnerInFirstGroup: samples.filter(({ denseWinnerInSelectedGroup }) =>
      denseWinnerInSelectedGroup).length,
    finalDenseWinnersCorrect: samples.filter(({ output, denseWinner }) =>
      output.fineWinner === denseWinner).length,
    samples,
  };
  await context.close();
} finally {
  await browser.close();
}

await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
