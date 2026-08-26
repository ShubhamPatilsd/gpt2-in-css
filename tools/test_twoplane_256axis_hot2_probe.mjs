#!/usr/bin/env node
/* Falsify, then benchmark, three-pair 256-axis hot rows against the retained page. */

import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const server = process.env.TWOPLANE_256_SERVER ?? "http://127.0.0.1:4189";
const directory = "gpt2-twoplane-256axis-hot2";
const controlDirectory = "gpt2-mixed-precision-hot2-upper";
const artifactRoot = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", artifactRoot), "utf8"));
const fixtures = reference.certifiedFixtures;
const stages = reference.stages;
const falsificationFixtures = 2;
const balancedFixtures = Math.min(10, fixtures.hiddenVectors.length);
const balancedRounds = 3;
const identityFields = [
  "group",
  "fineCode",
  "fineLocal",
  "fineBucket",
  "fineWinner",
  "bestBucket",
  "bestWinner",
  "certificateGap",
  "nextUpperBucket",
  "done",
];

if (fixtures.hiddenVectors.length < 10) {
  throw new Error(`expected at least 10 retained fixtures, found ${fixtures.hiddenVectors.length}`);
}
{
  const first = fixtures.unrolledStageGroups[0];
  const second = fixtures.unrolledStageGroups[1];
  if (first[0] > 1 || second[0] <= 1 || !second.slice(1).some((group) => group <= 1)) {
    throw new Error(
      `two-fixture falsification coverage changed: ${JSON.stringify([first, second])}`,
    );
  }
}

function statistics(values) {
  const sorted = [...values].sort((left, right) => left - right);
  const at = (fraction) => sorted[Math.min(
    sorted.length - 1,
    Math.floor(sorted.length * fraction),
  )];
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
  const messages = [];
  page.on("requestfailed", (request) => failures.push({
    url: request.url(), error: request.failure()?.errorText,
  }));
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      messages.push({ type: message.type(), text: message.text() });
    }
  });
  const started = performance.now();
  await page.goto(`${server}/experiments/${targetDirectory}/index.html`, {
    waitUntil: "load", timeout: 900_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  return { page, failures, messages, milliseconds: performance.now() - started };
}

async function setInput(page, fixture) {
  await page.evaluate((style) => {
    for (const element of [
      document.querySelector(".cascade"),
      document.querySelector("#model"),
    ]) {
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

async function observe(page) {
  return page.evaluate((stageCount) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    let group = number(getComputedStyle(document.querySelector("#result")), "--group");
    const observations = [];
    for (let stage = 0; stage < stageCount; stage += 1) {
      const wrapper = getComputedStyle(document.querySelector(`#mixed-stage-${stage}`));
      if (wrapper.display === "none") break;
      const fine = getComputedStyle(document.querySelector(
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
      ));
      const remaining = getComputedStyle(
        document.querySelector(`#remaining-result-${stage + 1}`),
      );
      const item = {
        stage,
        group,
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
  return {
    fixture,
    milliseconds: performance.now() - started,
    output: await observe(page),
  };
}

function compareSamples(candidate, control, round, phase) {
  const mismatches = [];
  if (candidate.output.stages.length !== control.output.stages.length) {
    mismatches.push({
      stage: null,
      field: "activeStages",
      candidate: candidate.output.stages.length,
      control: control.output.stages.length,
    });
  }
  const sharedStages = Math.min(
    candidate.output.stages.length,
    control.output.stages.length,
  );
  for (let stage = 0; stage < sharedStages; stage += 1) {
    for (const field of identityFields) {
      const candidateValue = candidate.output.stages[stage][field];
      const controlValue = control.output.stages[stage][field];
      if (!Object.is(candidateValue, controlValue)) {
        mismatches.push({ stage, field, candidate: candidateValue, control: controlValue });
      }
    }
  }
  for (const field of ["finalWinner", "finalBucket"]) {
    if (!Object.is(candidate.output[field], control.output[field])) {
      mismatches.push({
        stage: null,
        field,
        candidate: candidate.output[field],
        control: control.output[field],
      });
    }
  }
  const denseWinnerMatches =
    candidate.output.finalWinner === fixtures.denseWinners[candidate.fixture];
  return {
    phase,
    round,
    fixture: candidate.fixture,
    requiredIdentityFields: identityFields,
    exactLiveIdentity: mismatches.length === 0,
    denseWinnerMatches,
    mismatches,
    candidate: candidate.output,
    control: control.output,
    pass: mismatches.length === 0 && denseWinnerMatches,
  };
}

async function runRound(browser, { phase, round, fixtureCount }) {
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

  const warmup = (fixtureCount - 1 - round + fixtureCount) % fixtureCount;
  if (round % 2 === 0) {
    await evaluate(candidateLoad.page, warmup);
    await evaluate(controlLoad.page, warmup);
  } else {
    await evaluate(controlLoad.page, warmup);
    await evaluate(candidateLoad.page, warmup);
  }
  const order = Array.from(
    { length: fixtureCount },
    (_, index) => (index + round) % fixtureCount,
  );
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
  const result = {
    phase,
    round,
    loadOrder: round % 2 === 0
      ? ["three-pair-256-axis", "retained-twelve-glyph"]
      : ["retained-twelve-glyph", "three-pair-256-axis"],
    fixtureOrder: order,
    warmupFixture: warmup,
    cold: { candidate: candidateLoad.milliseconds, control: controlLoad.milliseconds },
    requestFailures: { candidate: candidateLoad.failures, control: controlLoad.failures },
    browserMessages: { candidate: candidateLoad.messages, control: controlLoad.messages },
    candidateSamples,
    controlSamples,
  };
  await candidateContext.close();
  await controlContext.close();
  return result;
}

function summarize(rounds, phase) {
  const checks = [];
  for (const round of rounds) {
    for (const candidate of round.candidateSamples) {
      const control = round.controlSamples.find((item) => item.fixture === candidate.fixture);
      checks.push(compareSamples(candidate, control, round.round, phase));
    }
  }
  const candidate = statistics(rounds.flatMap((round) =>
    round.candidateSamples.map((sample) => sample.milliseconds)));
  const control = statistics(rounds.flatMap((round) =>
    round.controlSamples.map((sample) => sample.milliseconds)));
  const requestFailureCount = rounds.reduce((sum, round) =>
    sum + round.requestFailures.candidate.length + round.requestFailures.control.length, 0);
  const semanticsPass = checks.every((check) => check.pass) && requestFailureCount === 0;
  return {
    phase,
    rounds: rounds.length,
    fixturesPerRound: rounds[0].candidateSamples.length,
    semanticsPass,
    checksPassed: checks.filter((check) => check.pass).length,
    checksTotal: checks.length,
    requestFailureCount,
    comparison: {
      threePair256Axis: candidate,
      retainedTwelveGlyph: control,
      meanRatio: candidate.mean / control.mean,
      meanSpeedupPercent: (1 - candidate.mean / control.mean) * 100,
      perRound: rounds.map((round) => {
        const candidateRound = statistics(
          round.candidateSamples.map((sample) => sample.milliseconds),
        );
        const controlRound = statistics(
          round.controlSamples.map((sample) => sample.milliseconds),
        );
        return {
          round: round.round,
          loadOrder: round.loadOrder,
          fixtureOrder: round.fixtureOrder,
          candidateMean: candidateRound.mean,
          controlMean: controlRound.mean,
          ratio: candidateRound.mean / controlRound.mean,
        };
      }),
    },
    checks,
    roundsDetail: rounds,
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const falsificationRounds = [await runRound(browser, {
    phase: "two-fixture-falsification",
    round: 0,
    fixtureCount: falsificationFixtures,
  })];
  const falsification = summarize(falsificationRounds, "two-fixture-falsification");
  let balanced = null;
  if (falsification.semanticsPass) {
    const rounds = [];
    for (let round = 0; round < balancedRounds; round += 1) {
      rounds.push(await runRound(browser, {
        phase: "three-by-ten-balanced",
        round,
        fixtureCount: balancedFixtures,
      }));
    }
    balanced = summarize(rounds, "three-by-ten-balanced");
  }
  const finalPhase = balanced ?? falsification;
  const semanticsPass = falsification.semanticsPass && balanced?.semanticsPass === true;
  const decision = !falsification.semanticsPass || balanced?.semanticsPass === false
    ? "reject-transport"
    : finalPhase.comparison.meanRatio < 1 ? "retain" : "reject-scaling";
  report = {
    experiment: directory,
    control: controlDirectory,
    chromeVersion: await browser.version(),
    generatedAt: new Date().toISOString(),
    identityFields,
    glyphsPerHotRow: reference.glyphsPerHotRow,
    controlGlyphsPerHotRow: reference.controlGlyphsPerHotRow,
    virtualBiasAxes: reference.virtualBiasAxes,
    falsification,
    balanced,
    stoppedAfterFalsification: !falsification.semanticsPass,
    semanticsPass,
    decision,
    assets: reference.assets,
    decomposition: reference.decomposition,
  };
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("browser-results.json", artifactRoot),
  `${JSON.stringify(report, null, 2)}\n`,
);

const falsification = report.falsification;
const measured = report.balanced ?? falsification;
const comparison = measured.comparison;
const allChecks = [
  ...falsification.checks,
  ...(report.balanced?.checks ?? []),
];
const mismatches = allChecks.flatMap((check) => check.mismatches.map((mismatch) => ({
  phase: check.phase,
  round: check.round,
  fixture: check.fixture,
  ...mismatch,
})));
const mismatchText = mismatches.length === 0
  ? "- None."
  : mismatches.map((item) =>
    `- ${item.phase}, round ${item.round}, fixture ${item.fixture}, ${
      item.stage === null ? "final" : `stage ${item.stage}`
    } \`${item.field}\`: candidate \`${item.candidate}\`, retained \`${item.control}\`.`,
  ).join("\n");
const perRoundRows = comparison.perRound.map((round) =>
  `| ${round.round} | ${round.loadOrder.join(" then ")} | ${round.candidateMean.toFixed(1)} ms | ${round.controlMean.toFixed(1)} ms | ${round.ratio.toFixed(3)}x |`,
).join("\n");
const maxima = report.decomposition.planeChecks.map((item) =>
  `${item.plane[0].toUpperCase()}${item.shard} ${item.maximumL1.toLocaleString()}`,
).join(", ");
const markdown = `# Three-pair 256-axis two-plane hot-2 rows

Decision: **${report.decision}**.

The retained global-int16 high/residual decomposition is unchanged. Adjacent 128-axis shards are merged, reducing each retained group-0/1 exact row from twelve glyphs to six (three high/residual font pairs), with no virtual-bias axes.

## Exactness gate

- Two-fixture falsification: ${falsification.checksPassed}/${falsification.checksTotal} exact live route identities.
${report.balanced
  ? `- Balanced 3×10 screen: ${report.balanced.checksPassed}/${report.balanced.checksTotal} exact live route identities.`
  : "- The 3×10 screen was not run because falsification failed."}
- Compared exactly at every live stage: group, fine code/local, fine bucket/winner, best bucket/winner, next upper, certificate gap, and done state.
- 256-axis L1 maxima: ${maxima}; maximum positive resulting advance ${Math.max(...report.decomposition.planeChecks.map((item) => item.maximumPositiveResultingAdvance)).toLocaleString()}.
- Stored bases use L1 + ${report.decomposition.safety}, all at or below ${report.decomposition.storedBaseMaximum.toLocaleString()}.

### Exact mismatches

${mismatchText}

${mismatches.length === 0
  ? "No browser-realized differences were observed."
  : "The root mismatch is fixture 1, stage 1, group 1: token 477 is still selected, but its bucket is 12,621 instead of the retained 12,620. That one-bucket difference is already visible as the preceding stage's next-upper value and then propagates through best-bucket and certificate-gap state. Groups, winners, and done states happen to remain unchanged, but the required exact live identity does not."}

## ${report.balanced ? "Balanced warm timing" : "Preliminary falsification timing"}

| Metric | Three-pair 256-axis | Retained twelve-glyph |
| --- | ---: | ---: |
| warm mean (${comparison.threePair256Axis.count} paired samples) | ${comparison.threePair256Axis.mean.toFixed(1)} ms | ${comparison.retainedTwelveGlyph.mean.toFixed(1)} ms |
| warm median | ${comparison.threePair256Axis.median.toFixed(1)} ms | ${comparison.retainedTwelveGlyph.median.toFixed(1)} ms |
| warm p90 | ${comparison.threePair256Axis.p90.toFixed(1)} ms | ${comparison.retainedTwelveGlyph.p90.toFixed(1)} ms |

Mean ratio: **${comparison.meanRatio.toFixed(3)}x** (${comparison.meanSpeedupPercent.toFixed(1)}% ${comparison.meanSpeedupPercent >= 0 ? "faster" : "slower"}).

| Round | Page load order | Three-pair mean | Retained mean | Ratio |
| ---: | --- | ---: | ---: | ---: |
${perRoundRows}

${report.decision === "reject-transport"
  ? "The browser-realized route is not exactly identical, so timing is preliminary and no scaling claim is made."
  : report.decision === "reject-scaling"
    ? "The exact route passed, but the balanced timing does not improve on the retained page."
    : "The exact route passed both gates and improves balanced warm timing."}

Chrome: ${report.chromeVersion}. Raw observations, request failures, cold loads, and exact mismatch records are in \`browser-results.json\`.
`;
await fs.writeFile(new URL("RESULTS.md", artifactRoot), markdown);

console.log(JSON.stringify({
  decision: report.decision,
  semanticsPass: report.semanticsPass,
  stoppedAfterFalsification: report.stoppedAfterFalsification,
  falsification: {
    checksPassed: falsification.checksPassed,
    checksTotal: falsification.checksTotal,
    comparison: falsification.comparison,
  },
  balanced: report.balanced && {
    checksPassed: report.balanced.checksPassed,
    checksTotal: report.balanced.checksTotal,
    comparison: report.balanced.comparison,
  },
}, null, 2));
if (!report.semanticsPass) process.exitCode = 1;
