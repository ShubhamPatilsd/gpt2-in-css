#!/usr/bin/env node
/* Compare six-glyph virtual-base hot rows against the retained twelve-glyph rows. */

import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const server = process.env.ONEPLANE_SERVER ?? "http://127.0.0.1:4189";
const directory = process.env.ONEPLANE_DIRECTORY ?? "gpt2-virtual-base-oneplane-hot2";
const controlDirectory = "gpt2-mixed-precision-hot2-upper";
const artifactRoot = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", artifactRoot), "utf8"));
const fixtures = reference.certifiedFixtures;
const stages = reference.stages;
const rounds = Math.max(1, Number.parseInt(process.env.ONEPLANE_ROUNDS ?? "3", 10));
const fixtureLimit = Math.min(
  fixtures.hiddenVectors.length,
  Math.max(1, Number.parseInt(process.env.ONEPLANE_FIXTURE_LIMIT ??
    String(fixtures.hiddenVectors.length), 10)),
);

function statistics(values) {
  const sorted = [...values].sort((left, right) => left - right);
  const at = (fraction) => sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * fraction))];
  return {
    count: sorted.length,
    minimum: sorted[0],
    median: at(0.5),
    p90: at(0.9),
    maximum: sorted.at(-1),
    mean: sorted.reduce((sum, value) => sum + value, 0) / sorted.length,
  };
}

function fixtureStyle(fixture) {
  const properties = fixtures.hiddenVectors[fixture]
    .map((value, dimension) => `--h${dimension}:${value}`);
  properties.push(`--score-offset:${-fixtures.scoreFloors[fixture] * 256 * 4}px`);
  return properties.join(";");
}

async function loadPage(context, targetDirectory) {
  const page = await context.newPage();
  page.setDefaultTimeout(900_000);
  const failures = [];
  page.on("requestfailed", (request) => failures.push({
    url: request.url(), error: request.failure()?.errorText,
  }));
  const started = performance.now();
  await page.goto(`${server}/experiments/${targetDirectory}/index.html`, {
    waitUntil: "load", timeout: 900_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  return { page, failures, milliseconds: performance.now() - started };
}

async function setInput(page, fixture) {
  await page.evaluate((style) => {
    for (const element of [document.querySelector(".cascade"), document.querySelector("#model")]) {
      element.style.cssText = style;
    }
  }, fixtureStyle(fixture));
}

async function settle(page) {
  for (let pass = 0; pass < 3; pass += 1) {
    await page.locator("#result").evaluate((element) => element.getBoundingClientRect().width);
    for (let stage = 0; stage < stages; stage += 1) {
      const wrapper = page.locator(`#mixed-stage-${stage}`);
      if (await wrapper.evaluate((element) => getComputedStyle(element).display) === "none") break;
      const dynamic = page.locator(`#dynamic-fine-stage-${stage}`);
      if (await dynamic.evaluate((element) => getComputedStyle(element).display) !== "none") {
        await dynamic.evaluate((element) => element.getBoundingClientRect().width);
      }
      for (const selector of [
        `#mixed-choice-source-${stage}`,
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
        `#remaining-result-${stage + 1}`,
      ]) {
        await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
      }
      const done = await page.locator(`#remaining-result-${stage + 1}`).evaluate(
        (element, property) => Number(getComputedStyle(element).getPropertyValue(property)),
        `--done-${stage}`,
      );
      if (done === 1) break;
    }
  }
}

async function observe(page) {
  return page.evaluate((stageCount) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    let group = number(getComputedStyle(document.querySelector("#result")), "--group");
    const observations = [];
    for (let stage = 0; stage < stageCount; stage += 1) {
      const wrapper = getComputedStyle(document.querySelector(`#mixed-stage-${stage}`));
      if (wrapper.display === "none") break;
      const dynamic = getComputedStyle(document.querySelector(`#dynamic-fine-stage-${stage}`));
      const fine = getComputedStyle(document.querySelector(
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
      ));
      const remaining = getComputedStyle(document.querySelector(`#remaining-result-${stage + 1}`));
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
      finalWinner: observations.at(-1)?.bestWinner,
      finalBucket: observations.at(-1)?.bestBucket,
    };
  }, stages);
}

async function evaluate(page, fixture) {
  const started = performance.now();
  await setInput(page, fixture);
  await settle(page);
  return { fixture, milliseconds: performance.now() - started, output: await observe(page) };
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const roundReports = [];
  for (let round = 0; round < rounds; round += 1) {
    const candidateContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
    const controlContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
    let candidateLoad;
    let controlLoad;
    if (round % 2 === 0) {
      candidateLoad = await loadPage(candidateContext, directory);
      controlLoad = await loadPage(controlContext, controlDirectory);
    } else {
      controlLoad = await loadPage(controlContext, controlDirectory);
      candidateLoad = await loadPage(candidateContext, directory);
    }
    const warmup = (fixtureLimit - 1 - round + fixtureLimit) % fixtureLimit;
    await evaluate(candidateLoad.page, warmup);
    await evaluate(controlLoad.page, warmup);
    const order = Array.from({ length: fixtureLimit }, (_, index) => (index + round) % fixtureLimit);
    const candidateSamples = [];
    const controlSamples = [];
    for (const fixture of order) {
      if ((fixture + round) % 2 === 0) {
        candidateSamples.push(await evaluate(candidateLoad.page, fixture));
        controlSamples.push(await evaluate(controlLoad.page, fixture));
      } else {
        controlSamples.push(await evaluate(controlLoad.page, fixture));
        candidateSamples.push(await evaluate(candidateLoad.page, fixture));
      }
    }
    roundReports.push({
      round,
      loadOrder: round % 2 === 0 ? ["one-plane", "two-plane"] : ["two-plane", "one-plane"],
      order,
      cold: { candidate: candidateLoad.milliseconds, control: controlLoad.milliseconds },
      requestFailures: { candidate: candidateLoad.failures, control: controlLoad.failures },
      candidateSamples,
      controlSamples,
    });
    await candidateContext.close();
    await controlContext.close();
  }

  const checks = [];
  for (const round of roundReports) {
    for (const candidate of round.candidateSamples) {
      const control = round.controlSamples.find((item) => item.fixture === candidate.fixture);
      const sameStages = candidate.output.stages.length === control.output.stages.length &&
        candidate.output.stages.every((stage, index) =>
          JSON.stringify(stage) === JSON.stringify(control.output.stages[index]));
      checks.push({
        round: round.round,
        fixture: candidate.fixture,
        sameStages,
        finalDenseWinner: candidate.output.finalWinner === fixtures.denseWinners[candidate.fixture],
        candidate: candidate.output,
        control: control.output,
        pass: sameStages && candidate.output.finalWinner === fixtures.denseWinners[candidate.fixture],
      });
    }
  }
  const candidateStats = statistics(roundReports.flatMap((round) =>
    round.candidateSamples.map((item) => item.milliseconds)));
  const controlStats = statistics(roundReports.flatMap((round) =>
    round.controlSamples.map((item) => item.milliseconds)));
  const semanticsPass = checks.length === rounds * fixtureLimit && checks.every((item) => item.pass);
  const ratio = candidateStats.mean / controlStats.mean;
  report = {
    experiment: directory,
    control: controlDirectory,
    chromeVersion: await browser.version(),
    rounds,
    fixtureLimit,
    semanticsPass,
    decision: semanticsPass && ratio < 1 ? "retain" : semanticsPass ? "reject-scaling" : "reject-transport",
    comparison: {
      onePlane: candidateStats,
      twoPlane: controlStats,
      meanRatio: ratio,
      meanSpeedupPercent: (1 - ratio) * 100,
      perRound: roundReports.map((round) => {
        const candidate = statistics(round.candidateSamples.map((item) => item.milliseconds));
        const control = statistics(round.controlSamples.map((item) => item.milliseconds));
        return { round: round.round, candidateMean: candidate.mean, controlMean: control.mean,
          ratio: candidate.mean / control.mean };
      }),
    },
    checks,
    cold: roundReports.map((round) => ({ round: round.round, ...round.cold })),
    requestFailures: roundReports.map((round) => ({ round: round.round, ...round.requestFailures })),
    assets: reference.assets,
    virtualBase: reference.virtualBase,
  };
} finally {
  await browser.close();
}

await fs.writeFile(new URL("browser-results.json", artifactRoot), `${JSON.stringify(report, null, 2)}\n`);
const comparison = report.comparison;
const markdown = `# ${reference.reportTitle ?? "Virtual-base one-plane hot-2 exact rows"}

Decision: **${report.decision}**.

${reference.encodingDescription ?? "The retained hot-2 topology is unchanged. Each exact hot row uses direct-int16 score glyphs instead of twelve high/residual glyphs. Always-on HVAR regions raise each glyph's effective base enough to keep its full signed-axis domain nonnegative."}

- Browser route identity versus the retained two-plane implementation: ${report.checks.filter((item) => item.pass).length}/${report.checks.length} fixtures.
- Glyphs per hot row: ${reference.glyphsPerHotRow} versus ${reference.controlGlyphsPerHotRow} (${reference.hotGlyphReductionPercent.toFixed(1)}% fewer).
- One-plane hot fonts: ${reference.assets.onePlaneFontWoff2Bytes.toLocaleString()} bytes across ${reference.assets.onePlaneFontFiles} files.
${reference.virtualBase ? `- Maximum extra bias axes per font: ${reference.virtualBase.maximumBiasAxes}.` : ""}

| Metric | One plane | Retained two plane |
| --- | ---: | ---: |
| warm mean (${comparison.onePlane.count} samples) | ${comparison.onePlane.mean.toFixed(1)} ms | ${comparison.twoPlane.mean.toFixed(1)} ms |
| warm median | ${comparison.onePlane.median.toFixed(1)} ms | ${comparison.twoPlane.median.toFixed(1)} ms |
| warm p90 | ${comparison.onePlane.p90.toFixed(1)} ms | ${comparison.twoPlane.p90.toFixed(1)} ms |

Mean ratio: **${comparison.meanRatio.toFixed(3)}x** (${comparison.meanSpeedupPercent.toFixed(1)}% ${comparison.meanSpeedupPercent >= 0 ? "faster" : "slower"}). Chrome: ${report.chromeVersion}.

Full stage observations, cold loads, and request failures are in \`browser-results.json\`.
`;
await fs.writeFile(new URL("RESULTS.md", artifactRoot), markdown);
console.log(JSON.stringify({
  decision: report.decision,
  semanticsPass: report.semanticsPass,
  checksPassed: report.checks.filter((item) => item.pass).length,
  checksTotal: report.checks.length,
  comparison: report.comparison,
  cold: report.cold,
}, null, 2));
if (!report.semanticsPass) process.exitCode = 1;
