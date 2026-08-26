import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rootName = "gpt2-hvar-grid-output-head-certified-int10-batched-tail";
const sizes = (process.env.GPT2_CERTIFIED_BATCH_SIZES ?? "4")
  .split(",").filter(Boolean).map((value) => Number.parseInt(value, 10));
const includeStress = process.env.GPT2_BATCH_STRESS === "1";

function sameArray(left, right) {
  return left.length === right.length
    && left.every((value, index) => value === right[index]);
}

function sameSet(left, right) {
  return sameArray([...left].sort((a, b) => a - b), [...right].sort((a, b) => a - b));
}

async function setFixture(page, fixture) {
  await page.evaluate((values) => {
    const cascade = document.querySelector(".cascade");
    const model = document.querySelector("#model");
    for (const element of [cascade, model]) {
      values.hidden.forEach((value, dimension) => {
        element.style.setProperty(`--h${dimension}`, String(value));
      });
      element.style.setProperty("--score-offset", `${-values.floor * 1024}px`);
    }
    cascade.style.setProperty("--tail-allowance", String(values.allowance));
  }, {
    hidden: fixture.hiddenVector,
    floor: fixture.scoreFloor,
    allowance: fixture.totalAllowanceBuckets,
  });
}

async function forcePrefix(page, stages = 6) {
  return page.evaluate((stageCount) => {
    for (const selector of ["#result", "#fine-stage", "#fine-result"]) {
      document.querySelector(selector).getBoundingClientRect();
    }
    const done = [];
    for (let stage = 1; stage <= stageCount; stage += 1) {
      const remaining = document.querySelector(`#remaining-result-${stage}`);
      remaining.getBoundingClientRect();
      const stageDone = Number(
        getComputedStyle(remaining).getPropertyValue(`--done-${stage - 1}`),
      );
      done.push(stageDone);
      if (stageDone === 1) break;
      if (stage < stageCount) {
        document.querySelector(`#fine-stage-${stage}`).getBoundingClientRect();
        document.querySelector(`#fine-result-${stage}`).getBoundingClientRect();
      }
    }
    return done;
  }, stages);
}

async function settleBatch(page, batch) {
  await page.evaluate(() => document.fonts.ready);
  for (let pass = 0; pass < 4; pass += 1) {
    const done = await forcePrefix(page, 6);
    if (!done.includes(1)) {
      await page.evaluate((batchSize) => {
        for (let slot = 1; slot < batchSize; slot += 1) {
          document.querySelector(`#batch-group-${slot}`).getBoundingClientRect();
        }
        for (let slot = 0; slot < batchSize; slot += 1) {
          for (const prefix of ["batch-fine-stage", "batch-fine-reader",
            "batch-fine-result", "batch-score-carrier", "batch-token-carrier"]) {
            document.querySelector(`#${prefix}-${slot}`).getBoundingClientRect();
          }
        }
        for (const selector of ["#batch-score-max", "#batch-score-reader",
          "#batch-score-result", "#batch-token-max", "#batch-token-reader",
          "#batch-final-result", "#batch-certificate-result"]) {
          document.querySelector(selector).getBoundingClientRect();
        }
      }, batch);
    }
  }
}

async function settleSerial(page, stages) {
  await page.evaluate(() => document.fonts.ready);
  for (let pass = 0; pass < 4; pass += 1) await forcePrefix(page, stages);
}

async function readPrefix(page, maximumStages) {
  return page.evaluate((stageCount) => {
    const number = (style, name) => Number(style.getPropertyValue(name));
    const first = getComputedStyle(document.querySelector("#fine-result"));
    const coarse = getComputedStyle(document.querySelector("#result"));
    const groups = [number(coarse, "--group")];
    const winners = [number(first, "--refined-winner")];
    const buckets = [number(first, "--fine-bucket")];
    let bestWinner = number(first, "--best-winner-0");
    let bestBucket = number(first, "--best-bucket-0");
    const done = [];
    for (let stage = 1; stage <= stageCount; stage += 1) {
      const remaining = getComputedStyle(document.querySelector(`#remaining-result-${stage}`));
      const stageDone = number(remaining, `--done-${stage - 1}`);
      done.push(stageDone);
      bestWinner = number(remaining, `--best-winner-${stage - 1}`);
      bestBucket = number(remaining, `--best-bucket-${stage - 1}`);
      if (stageDone === 1) break;
      if (stage < stageCount) {
        groups.push(number(remaining, `--remaining-group-${stage}`));
        const fine = getComputedStyle(document.querySelector(`#fine-result-${stage}`));
        winners.push(number(fine, `--fine-winner-${stage}`));
        buckets.push(number(fine, `--fine-bucket-${stage}`));
        bestWinner = number(fine, `--best-winner-${stage}`);
        bestBucket = number(fine, `--best-bucket-${stage}`);
      }
    }
    return { groups, winners, buckets, done, bestWinner, bestBucket };
  }, maximumStages);
}

async function runBatch(batch, reference, fixtures) {
  const browser = await chromium.launch({ executablePath, headless: true });
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
      `http://127.0.0.1:4178/experiments/${rootName}/b${batch}/index.html`,
      { waitUntil: "load", timeout: 600000 },
    );
    await page.evaluate(() => document.fonts.ready);
    const loadMilliseconds = performance.now() - started;
    const samples = [];
    for (let fixtureIndex = 0; fixtureIndex < fixtures.length; fixtureIndex += 1) {
      const fixture = fixtures[fixtureIndex];
      const fixtureStarted = performance.now();
      await setFixture(page, fixture);
      await settleBatch(page, batch);
      const prefix = await readPrefix(page, 6);
      const output = await page.evaluate((batchSize) => {
        const number = (style, name) => Number(style.getPropertyValue(name));
        const start = document.querySelector("#batch-start");
        const compute = getComputedStyle(document.querySelector("#batch-compute"));
        const groups = [];
        const exact = [];
        for (let slot = 0; slot < batchSize; slot += 1) {
          const group = number(compute, `--batch-group-${slot}`);
          const style = getComputedStyle(document.querySelector(`#batch-fine-result-${slot}`));
          groups.push(group);
          exact.push({
            slot,
            group,
            winner: number(style, `--batch-winner-${slot}`),
            bucket: number(style, `--batch-bucket-${slot}`),
            scoreGeometryPixels: document.querySelector(
              `#batch-score-carrier-${slot}`,
            ).getBoundingClientRect().width,
            tokenGeometryPixels: document.querySelector(
              `#batch-token-carrier-${slot}`,
            ).getBoundingClientRect().width,
          });
        }
        const score = getComputedStyle(document.querySelector("#batch-score-result"));
        const final = getComputedStyle(document.querySelector("#batch-final-result"));
        const certificate = getComputedStyle(
          document.querySelector("#batch-certificate-result"),
        );
        return {
          batchStartDisplay: getComputedStyle(start).display,
          groups,
          exact,
          displayedScorers: getComputedStyle(start).display === "none" ? 0
            : Array.from(document.querySelectorAll(".batch-fine-stage"))
              .filter((element) => getComputedStyle(element).display !== "none").length,
          mergedBucket: number(score, "--batch-merged-bucket"),
          winningGroup: number(score, "--batch-winning-group"),
          finalWinner: number(final, "--batch-final-winner"),
          nextGroup: number(certificate, "--batch-next-group"),
          nextUpper: number(certificate, "--batch-next-upper"),
          certificateGap: number(certificate, "--batch-certificate-gap"),
          batchDone: number(certificate, "--batch-done"),
          prefixScoreGeometryPixels: document.querySelector(
            "#batch-prefix-score",
          ).getBoundingClientRect().width,
          mergedScoreGeometryPixels: document.querySelector(
            "#batch-score-max",
          ).getBoundingClientRect().width,
          selectedTokenGeometryPixels: document.querySelector(
            "#batch-token-max",
          ).getBoundingClientRect().width,
        };
      }, batch);
      const prefixDone = prefix.done.includes(1);
      const branches = [{
        group: Math.floor(prefix.bestWinner / 256),
        winner: prefix.bestWinner,
        bucket: prefix.bestBucket,
      }, ...output.exact];
      const browserMaximum = branches.reduce((best, value) => {
        if (value.bucket > best.bucket) return value;
        if (value.bucket === best.bucket && value.winner < best.winner) return value;
        return best;
      });
      samples.push({
        fixture: fixtureIndex,
        kind: fixture.kind,
        corpusIndex: fixture.corpusIndex,
        milliseconds: performance.now() - fixtureStarted,
        prefixDone,
        prefix,
        output,
        browserMaximum,
        targetWinner: fixture.targetWinner,
        expectedGroups: fixture.batchGroups,
        expectedWinners: fixture.batchFineWinners,
        expectedNextGroup: fixture.batchNextGroup,
        expectedBatchCertified: fixture.batchCertified,
      });
      console.error(JSON.stringify({
        kind: "batch",
        batch,
        fixture: fixture.corpusIndex,
        milliseconds: samples.at(-1).milliseconds,
        groups: output.groups,
        done: output.batchDone,
      }));
    }
    const mutations = samples.map(({ milliseconds }) => milliseconds)
      .sort((left, right) => left - right);
    const active = samples.filter(({ prefixDone }) => !prefixDone);
    const gated = samples.filter(({ prefixDone }) => prefixDone);
    const report = {
      chrome: await browser.version(),
      batchSize: batch,
      includeStress,
      htmlBytes: reference.htmlBytes,
      cssBytes: reference.cssBytes,
      domElements: reference.domElements,
      loadMilliseconds,
      loadAndFirstEvaluationMilliseconds: loadMilliseconds + samples[0].milliseconds,
      medianMutationMilliseconds: mutations[Math.floor(mutations.length / 2)],
      mutationRangeMilliseconds: [mutations[0], mutations.at(-1)],
      activeFixtures: active.length,
      gatedFixtures: gated.length,
      easyPathGatesWholeBatch: gated.length > 0 && gated.every(({ output }) =>
        output.batchStartDisplay === "none"),
      activePathDisplaysExactlyBScorers: active.length > 0 && active.every(({ output }) =>
        output.batchStartDisplay === "block" && output.displayedScorers === batch),
      allSelectedGroupsUnique: active.length > 0 && active.every(({ output }) =>
        new Set(output.groups).size === batch),
      allSelectedGroupSetsMatchOffline: active.length > 0 && active.every(({ output, expectedGroups }) =>
        sameSet(output.groups, expectedGroups)),
      allSelectedGroupOrderMatchesOffline: active.length > 0 && active.every(({ output, expectedGroups }) =>
        sameArray(output.groups, expectedGroups)),
      allSelectedFineWinnersMatchOffline: active.length > 0 && active.every(({ output, expectedGroups,
        expectedWinners }) => output.exact.every(({ group, winner }) => {
        const index = expectedGroups.indexOf(group);
        return index >= 0 && winner === expectedWinners[index];
      })),
      allScoreGroupMergesMatchBrowserBranches: active.length > 0 && active.every(({ output,
        browserMaximum }) => output.mergedBucket === browserMaximum.bucket
        && output.winningGroup === browserMaximum.group
        && output.mergedScoreGeometryPixels === Math.max(
          output.prefixScoreGeometryPixels,
          ...output.exact.map(({ scoreGeometryPixels }) => scoreGeometryPixels),
        )),
      allTokenPlaneSelectionsMatchBrowserBranches: active.length > 0 && active.every(({ output,
        browserMaximum }) => output.finalWinner === browserMaximum.winner
        && output.selectedTokenGeometryPixels === browserMaximum.winner),
      allPostBatchNextGroupsMatchOffline: active.length > 0 && active.every(({ output,
        expectedNextGroup }) => output.nextGroup === expectedNextGroup),
      allPostBatchCertificatesMatchOffline: active.length > 0 && active.every(({ output,
        expectedBatchCertified }) => (output.batchDone === 1) === expectedBatchCertified),
      allFinalWinnersMatchOfflineTarget: samples.every(({ prefixDone, prefix, output,
        targetWinner }) => (prefixDone ? prefix.bestWinner : output.finalWinner) === targetWinner),
      pageErrors,
      samples,
    };
    await context.close();
    return report;
  } finally {
    await browser.close();
  }
}

async function runSerial(batch, fixtures) {
  const stages = 6 + batch;
  const browser = await chromium.launch({ executablePath, headless: true });
  try {
    const context = await browser.newContext({
      javaScriptEnabled: false,
      viewport: { width: 800, height: 200 },
    });
    const page = await context.newPage();
    page.setDefaultTimeout(600000);
    const started = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/${rootName}/b${batch}/serial/index.html`,
      { waitUntil: "load", timeout: 600000 },
    );
    await page.evaluate(() => document.fonts.ready);
    const loadMilliseconds = performance.now() - started;
    const samples = [];
    for (const fixture of fixtures) {
      const fixtureStarted = performance.now();
      await setFixture(page, fixture);
      await settleSerial(page, stages);
      const output = await readPrefix(page, stages);
      samples.push({
        corpusIndex: fixture.corpusIndex,
        milliseconds: performance.now() - fixtureStarted,
        activeExactGroups: output.groups.length,
        finalWinner: output.bestWinner,
        targetWinner: fixture.targetWinner,
      });
      console.error(JSON.stringify({
        kind: "serial",
        batch,
        fixture: fixture.corpusIndex,
        milliseconds: samples.at(-1).milliseconds,
        activeExactGroups: output.groups.length,
      }));
    }
    const mutations = samples.map(({ milliseconds }) => milliseconds)
      .sort((left, right) => left - right);
    const report = {
      stages,
      loadMilliseconds,
      loadAndFirstEvaluationMilliseconds: loadMilliseconds + samples[0].milliseconds,
      medianMutationMilliseconds: mutations[Math.floor(mutations.length / 2)],
      mutationRangeMilliseconds: [mutations[0], mutations.at(-1)],
      allFinalWinnersMatchOfflineTarget: samples.every(({ finalWinner, targetWinner }) =>
        finalWinner === targetWinner),
      samples,
    };
    await context.close();
    return report;
  } finally {
    await browser.close();
  }
}

const comparisons = [];
for (const batch of sizes) {
  const variantRoot = new URL(
    `../experiments/${rootName}/b${batch}/`, import.meta.url,
  );
  const reference = JSON.parse(
    await fs.readFile(new URL("reference.json", variantRoot), "utf8"),
  );
  const fixtures = reference.fixtures.filter(
    (fixture) => includeStress || fixture.kind !== "forced-parallel-stress",
  );
  const batchReport = await runBatch(batch, reference, fixtures);
  const serialReport = await runSerial(batch, fixtures);
  const report = {
    ...batchReport,
    equivalentSerial: serialReport,
    warmMedianDeltaVersusSerialMilliseconds:
      batchReport.medianMutationMilliseconds - serialReport.medianMutationMilliseconds,
    coldAndFirstDeltaVersusSerialMilliseconds:
      batchReport.loadAndFirstEvaluationMilliseconds
      - serialReport.loadAndFirstEvaluationMilliseconds,
  };
  await fs.writeFile(
    new URL("browser-results.json", variantRoot),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  comparisons.push(report);
}

const outputRoot = new URL(`../experiments/${rootName}/`, import.meta.url);
await fs.writeFile(
  new URL("browser-comparison.json", outputRoot),
  `${JSON.stringify({ sizes, includeStress, comparisons }, null, 2)}\n`,
);
console.log(JSON.stringify({
  sizes,
  includeStress,
  comparisons: comparisons.map((report) => ({
    batchSize: report.batchSize,
    batchColdAndFirstMilliseconds: report.loadAndFirstEvaluationMilliseconds,
    batchWarmMedianMilliseconds: report.medianMutationMilliseconds,
    serialColdAndFirstMilliseconds:
      report.equivalentSerial.loadAndFirstEvaluationMilliseconds,
    serialWarmMedianMilliseconds: report.equivalentSerial.medianMutationMilliseconds,
    allSelectedGroupSetsMatchOffline: report.allSelectedGroupSetsMatchOffline,
    allSelectedFineWinnersMatchOffline: report.allSelectedFineWinnersMatchOffline,
    allFinalWinnersMatchOfflineTarget: report.allFinalWinnersMatchOfflineTarget,
  })),
}, null, 2));
