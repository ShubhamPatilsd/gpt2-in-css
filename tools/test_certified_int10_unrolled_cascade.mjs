import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const stages = Number.parseInt(process.env.GPT2_CERTIFIED_STAGES ?? "6", 10);
const gated = process.env.GPT2_CERTIFIED_GATE === "1";
const incrementalMask = process.env.GPT2_CERTIFIED_INCREMENTAL_MASK === "1";
const packedMask = process.env.GPT2_CERTIFIED_PACKED_MASK === "1";
const directory = process.env.GPT2_CERTIFIED_CASCADE_DIR
  ?? `gpt2-hvar-grid-output-head-certified-int10-unrolled${stages}`
    + `${gated ? "-gated" : ""}${incrementalMask ? "-linear-mask" : ""}`
    + `${packedMask ? "-packed-mask" : ""}`;
const root = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));
const fixtures = reference.certifiedFixtures;
const fixtureLimit = Math.min(
  fixtures.hiddenVectors.length,
  Number.parseInt(
    process.env.GPT2_CERTIFIED_FIXTURE_LIMIT ?? String(fixtures.hiddenVectors.length),
    10,
  ),
);

async function settle(page) {
  await page.evaluate(() => document.fonts.ready);
  for (let pass = 0; pass < 3; pass += 1) {
    for (const selector of ["#result", "#fine-stage", "#fine-result"]) {
      await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
    }
    for (let stage = 1; stage <= stages; stage += 1) {
      const remaining = page.locator(`#remaining-result-${stage}`);
      await remaining.evaluate((element) => element.getBoundingClientRect().width);
      const stageDone = await remaining.evaluate(
        (element, property) => Number(getComputedStyle(element).getPropertyValue(property)),
        `--done-${stage - 1}`,
      );
      if (gated && stageDone === 1) {
        break;
      }
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
  for (let fixture = 0; fixture < fixtureLimit; fixture += 1) {
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
    }, { hidden: fixtures.hiddenVectors[fixture], floor: fixtures.scoreFloors[fixture] });
    await settle(page);
    const output = await page.evaluate(({ stageCount, gateLaterStages }) => {
      const coarse = getComputedStyle(document.querySelector("#result"));
      const groups = [Number(coarse.getPropertyValue("--group"))];
      const fineWinners = [Number(
        getComputedStyle(document.querySelector("#fine-result"))
          .getPropertyValue("--refined-winner"),
      )];
      const done = [];
      const gaps = [];
      let bestWinner = Number(
        getComputedStyle(document.querySelector("#fine-result"))
          .getPropertyValue("--best-winner-0"),
      );
      let bestBucket = Number(
        getComputedStyle(document.querySelector("#fine-result"))
          .getPropertyValue("--best-bucket-0"),
      );
      for (let stage = 1; stage <= stageCount; stage += 1) {
        const remaining = getComputedStyle(
          document.querySelector(`#remaining-result-${stage}`),
        );
        const stageDone = Number(
          remaining.getPropertyValue(`--done-${stage - 1}`),
        );
        done.push(stageDone);
        gaps.push(Number(
          remaining.getPropertyValue(`--certificate-gap-${stage - 1}`),
        ));
        bestWinner = Number(
          remaining.getPropertyValue(`--best-winner-${stage - 1}`),
        );
        bestBucket = Number(
          remaining.getPropertyValue(`--best-bucket-${stage - 1}`),
        );
        if (gateLaterStages && stageDone === 1) {
          break;
        }
        if (stage < stageCount) {
          groups.push(Number(remaining.getPropertyValue(`--remaining-group-${stage}`)));
          const fine = getComputedStyle(
            document.querySelector(`#fine-result-${stage}`),
          );
          fineWinners.push(Number(fine.getPropertyValue(`--fine-winner-${stage}`)));
          bestWinner = Number(fine.getPropertyValue(`--best-winner-${stage}`));
          bestBucket = Number(fine.getPropertyValue(`--best-bucket-${stage}`));
        }
      }
      return {
        groups,
        fineWinners,
        done,
        gaps,
        bestWinner,
        bestBucket,
        activeExactStages: groups.length,
      };
    }, { stageCount: stages, gateLaterStages: gated });
    const firstDone = output.done.findIndex((value) => value === 1);
    const expectedBestWinner = fixtures.unrolledBestWinners[fixture][
      output.activeExactStages - 1
    ];
    samples.push({
      fixture,
      milliseconds: performance.now() - fixtureStarted,
      output,
      firstDoneZeroBased: firstDone >= 0 ? firstDone : null,
      expectedGroups: fixtures.unrolledStageGroups[fixture],
      expectedFineWinners: fixtures.unrolledStageFineWinners[fixture],
      expectedBestWinner,
      expectedFirstDoneZeroBased: fixtures.unrolledFirstDoneZeroBased[fixture],
      denseWinner: fixtures.denseWinners[fixture],
    });
  }
  report = {
    chrome: await browser.version(),
    directory,
    stages,
    gated,
    incrementalMask,
    packedMask,
    scoreSlackBucketsPerSide: reference.scoreSlackBucketsPerSide,
    loadMilliseconds,
    loadAndFirstEvaluationMilliseconds: loadMilliseconds + samples[0].milliseconds,
    elapsedMilliseconds: performance.now() - started,
    fixtures: samples.length,
    allGroupsUnique: samples.every(({ output }) =>
      new Set(output.groups).size === output.groups.length),
    allGroupsMatchOffline: samples.every(({ output, expectedGroups }) =>
      output.groups.every((value, index) => value === expectedGroups[index])),
    allGroupSetsMatchOffline: samples.every(({ output, expectedGroups }) =>
      output.groups.length === expectedGroups.slice(0, output.groups.length).length
      && output.groups.every((value) =>
        expectedGroups.slice(0, output.groups.length).includes(value))),
    allFineWinnersMatchOffline: samples.every(({ output, expectedFineWinners }) =>
      output.fineWinners.every((value, index) => value === expectedFineWinners[index])),
    allSelectedGroupFineWinnersMatchOffline: samples.every(({
      output,
      expectedGroups,
      expectedFineWinners,
    }) => output.groups.every((group, index) => {
      const expectedIndex = expectedGroups.indexOf(group);
      return expectedIndex >= 0
        && output.fineWinners[index] === expectedFineWinners[expectedIndex];
    })),
    allBestWinnersMatchOffline: samples.every(({ output, expectedBestWinner }) =>
      output.bestWinner === expectedBestWinner),
    allFirstDoneMatchOffline: samples.every((sample) =>
      sample.firstDoneZeroBased === sample.expectedFirstDoneZeroBased),
    finalDenseWinnersCorrect: samples.filter(({ output, denseWinner }) =>
      output.bestWinner === denseWinner).length,
    activeExactStages: samples.map(({ output }) => output.activeExactStages),
    samples,
  };
  await context.close();
} finally {
  await browser.close();
}

await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
