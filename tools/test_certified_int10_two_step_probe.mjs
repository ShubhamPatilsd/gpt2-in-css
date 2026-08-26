import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const directory = "gpt2-hvar-grid-output-head-certified-upper-int10-two-step";
const root = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));
const fixtures = reference.certifiedFixtures;

async function settle(page) {
  await page.evaluate(() => document.fonts.ready);
  for (let pass = 0; pass < 4; pass += 1) {
    for (const selector of [
      "#result", "#fine-stage", "#fine-result", "#remaining-result",
      "#fine-stage-2", "#fine-result-2",
    ]) {
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
  page.setDefaultTimeout(240000);
  const started = performance.now();
  await page.goto(
    `http://127.0.0.1:4178/experiments/${directory}/index.html`,
    { waitUntil: "load", timeout: 240000 },
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
        element.style.setProperty(
          "--score-offset",
          `${-values.floor * 256 * 4}px`,
        );
      }
    }, { hidden: fixtures.hiddenVectors[fixture], floor: fixtures.scoreFloors[fixture] });
    await settle(page);
    const output = await page.evaluate(() => {
      const first = getComputedStyle(document.querySelector("#fine-result"));
      const remaining = getComputedStyle(document.querySelector("#remaining-result"));
      const second = getComputedStyle(document.querySelector("#fine-result-2"));
      return {
        firstWinner: Number(first.getPropertyValue("--refined-winner")),
        firstBucket: Number(first.getPropertyValue("--fine-bucket")),
        secondGroup: Number(remaining.getPropertyValue("--remaining-group")),
        secondWinner: Number(second.getPropertyValue("--refined-winner-2")),
        secondBucket: Number(second.getPropertyValue("--fine-bucket-2")),
        bestTwoWinner: Number(second.getPropertyValue("--best-two-winner")),
        bestTwoBucket: Number(second.getPropertyValue("--best-two-bucket")),
        useSecond: Number(second.getPropertyValue("--use-second")),
      };
    });
    samples.push({
      fixture,
      milliseconds: performance.now() - fixtureStarted,
      output,
      expectedFirstWinner: fixtures.selectedGroupFineWinners[fixture],
      expectedSecondGroup: fixtures.remainingUpperGroups[fixture],
      expectedSecondWinner: fixtures.secondGroupFineWinners[fixture],
      expectedBestTwoWinner: fixtures.bestTwoFineWinners[fixture],
      denseWinner: fixtures.denseWinners[fixture],
    });
  }
  report = {
    chrome: await browser.version(),
    loadMilliseconds,
    loadAndFirstEvaluationMilliseconds: loadMilliseconds + samples[0].milliseconds,
    elapsedMilliseconds: performance.now() - started,
    fixtures: samples.length,
    allSecondGroupsCorrect: samples.every(({ output, expectedSecondGroup }) =>
      output.secondGroup === expectedSecondGroup),
    allSecondWinnersCorrect: samples.every(({ output, expectedSecondWinner }) =>
      output.secondWinner === expectedSecondWinner),
    allBestTwoWinnersCorrect: samples.every(({ output, expectedBestTwoWinner }) =>
      output.bestTwoWinner === expectedBestTwoWinner),
    finalDenseWinnersCorrect: samples.filter(({ output, denseWinner }) =>
      output.bestTwoWinner === denseWinner).length,
    samples,
  };
  await context.close();
} finally {
  await browser.close();
}

await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
