import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const directory = "gpt2-hvar-grid-output-head-certified-upper-int10-remaining-upper";
const root = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));
const fixtures = reference.certifiedFixtures;

async function settle(page) {
  await page.evaluate(() => document.fonts.ready);
  for (let pass = 0; pass < 4; pass += 1) {
    for (const selector of ["#result", "#fine-stage", "#fine-result", "#remaining-result"]) {
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
      for (const selector of ["#model", "#fine-stage"]) {
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
      const coarse = getComputedStyle(document.querySelector("#result"));
      const fine = getComputedStyle(document.querySelector("#fine-result"));
      const remaining = getComputedStyle(document.querySelector("#remaining-result"));
      return {
        upperGroup: Number(coarse.getPropertyValue("--group")),
        fineWinner: Number(fine.getPropertyValue("--refined-winner")),
        fineBucket: Number(fine.getPropertyValue("--fine-bucket")),
        remainingGroup: Number(remaining.getPropertyValue("--remaining-group")),
        remainingBucket: Number(remaining.getPropertyValue("--remaining-bucket")),
        certificateGap: Number(remaining.getPropertyValue("--certificate-gap")),
      };
    });
    samples.push({
      fixture,
      milliseconds: performance.now() - fixtureStarted,
      output,
      expectedUpperGroup: fixtures.upperGroups[fixture],
      expectedFineWinner: fixtures.selectedGroupFineWinners[fixture],
      expectedRemainingGroup: fixtures.remainingUpperGroups[fixture],
      expectedRemainingBucket: fixtures.remainingUpperBuckets[fixture],
      denseWinner: fixtures.denseWinners[fixture],
    });
  }
  report = {
    chrome: await browser.version(),
    loadMilliseconds,
    loadAndFirstEvaluationMilliseconds: loadMilliseconds + samples[0].milliseconds,
    elapsedMilliseconds: performance.now() - started,
    fixtures: samples.length,
    allFineWinnersCorrect: samples.every(({ output, expectedFineWinner }) =>
      output.fineWinner === expectedFineWinner),
    allRemainingGroupsCorrect: samples.every(({ output, expectedRemainingGroup }) =>
      output.remainingGroup === expectedRemainingGroup),
    allRemainingBucketsCorrect: samples.every(({ output, expectedRemainingBucket }) =>
      output.remainingBucket === expectedRemainingBucket),
    browserFirstCertificates: samples.filter(({ output }) => output.certificateGap >= 0).length,
    samples,
  };
  await context.close();
} finally {
  await browser.close();
}

await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
