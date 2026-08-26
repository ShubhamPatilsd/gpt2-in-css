import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const server = process.env.MIXED_HOT2_SERVER ?? "http://127.0.0.1:4189";
const candidateDirectory = process.env.BLOCK_HOT2_DIRECTORY
  ?? "gpt2-mixed-hot2-block-gate-b4";
const controlDirectory = process.env.BLOCK_HOT2_CONTROL_DIRECTORY
  ?? "gpt2-mixed-precision-hot2-upper";
const outputStem = process.env.BLOCK_HOT2_AB_OUTPUT_STEM ?? "ab-results";
const artifactRoot = new URL(`../experiments/${candidateDirectory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", artifactRoot), "utf8"));
const fixtures = reference.certifiedFixtures;
const stages = reference.stages;
const rounds = Math.max(1, Number(process.env.BLOCK_HOT2_AB_ROUNDS ?? 3));
const fixtureLimit = Math.min(
  fixtures.hiddenVectors.length,
  Math.max(1, Number(process.env.BLOCK_HOT2_AB_FIXTURES ?? fixtures.hiddenVectors.length)),
);

function percentile(values, fraction) {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * fraction))];
}

function statistics(values) {
  return {
    count: values.length,
    minimum: Math.min(...values),
    median: percentile(values, 0.5),
    p90: percentile(values, 0.9),
    maximum: Math.max(...values),
    mean: values.reduce((sum, value) => sum + value, 0) / values.length,
  };
}

function fixtureStyle(fixture) {
  const hidden = fixtures.hiddenVectors[fixture];
  const properties = hidden.map((value, dimension) => `--h${dimension}:${value}`);
  properties.push(`--score-offset:${-fixtures.scoreFloors[fixture] * 256 * 4}px`);
  properties.push(`--query-norm:${Math.sqrt(
    hidden.reduce((sum, value) => sum + value * value, 0),
  )}`);
  return properties.join(";");
}

function watch(page, label, diagnostics) {
  page.on("pageerror", (error) => diagnostics.pageErrors.push({ label, error: String(error) }));
  page.on("requestfailed", (request) => diagnostics.requestFailures.push({
    label,
    url: request.url(),
    error: request.failure()?.errorText ?? "unknown request failure",
  }));
  page.on("response", (response) => {
    if (response.status() >= 400 && !response.url().endsWith("favicon.ico")) {
      diagnostics.httpErrors.push({ label, url: response.url(), status: response.status() });
    }
  });
}

async function loadPage(context, directory, label, diagnostics) {
  const page = await context.newPage();
  watch(page, label, diagnostics);
  page.setDefaultTimeout(900_000);
  const started = performance.now();
  await page.goto(`${server}/experiments/${directory}/index.html`, {
    waitUntil: "load",
    timeout: 900_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  return { page, loadMilliseconds: performance.now() - started };
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
      const fine = getComputedStyle(document.querySelector(
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
      ));
      const remaining = getComputedStyle(document.querySelector(`#remaining-result-${stage + 1}`));
      const item = {
        stage,
        group,
        fineBucket: number(fine, `--fine-bucket-${stage}`),
        fineWinner: number(fine, `--fine-winner-${stage}`),
        bestBucket: number(fine, `--best-bucket-${stage}`),
        bestWinner: number(fine, `--best-winner-${stage}`),
        done: number(remaining, `--done-${stage}`),
      };
      observations.push(item);
      if (item.done === 1) break;
      group = number(remaining, `--remaining-group-${stage + 1}`);
    }
    return {
      stages: observations,
      groups: observations.map((item) => item.group),
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

const diagnostics = { pageErrors: [], requestFailures: [], httpErrors: [] };
const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const candidateContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const controlContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const candidate = await loadPage(candidateContext, candidateDirectory, "candidate", diagnostics);
  const control = await loadPage(controlContext, controlDirectory, "control", diagnostics);
  await evaluate(candidate.page, fixtureLimit - 1);
  await evaluate(control.page, fixtureLimit - 1);

  const candidateSamples = [];
  const controlSamples = [];
  for (let round = 0; round < rounds; round += 1) {
    // Keep the fixture sequence fixed so the last input of one round never
    // equals the first input of the next two-fixture round.
    const order = Array.from({ length: fixtureLimit }, (_, index) => index);
    for (const fixture of order) {
      if ((fixture + round) % 2 === 0) {
        candidateSamples.push({ round, ...(await evaluate(candidate.page, fixture)) });
        controlSamples.push({ round, ...(await evaluate(control.page, fixture)) });
      } else {
        controlSamples.push({ round, ...(await evaluate(control.page, fixture)) });
        candidateSamples.push({ round, ...(await evaluate(candidate.page, fixture)) });
      }
    }
  }
  await candidateContext.close();
  await controlContext.close();

  const checks = candidateSamples.map((sample) => {
    const controlSample = controlSamples.find(
      (item) => item.round === sample.round && item.fixture === sample.fixture,
    );
    const expectedGroups = fixtures.unrolledStageGroups[sample.fixture]
      .slice(0, sample.output.groups.length);
    const check = {
      round: sample.round,
      fixture: sample.fixture,
      routeMatchesControl:
        JSON.stringify(sample.output.groups) === JSON.stringify(controlSample.output.groups),
      routeMatchesGenerated:
        JSON.stringify(sample.output.groups) === JSON.stringify(expectedGroups),
      bucketMatchesControl: sample.output.finalBucket === controlSample.output.finalBucket,
      winnerMatchesControl: sample.output.finalWinner === controlSample.output.finalWinner,
      winnerMatchesOracle: sample.output.finalWinner === fixtures.denseWinners[sample.fixture],
    };
    check.pass = check.routeMatchesGenerated
      && check.bucketMatchesControl
      && check.winnerMatchesControl
      && check.winnerMatchesOracle;
    return check;
  });
  const candidateStats = statistics(candidateSamples.map((item) => item.milliseconds));
  const controlStats = statistics(controlSamples.map((item) => item.milliseconds));
  const semanticsPass = checks.every((check) => check.pass);
  report = {
    experiment: candidateDirectory,
    control: controlDirectory,
    chromeVersion: await browser.version(),
    rounds,
    fixtureLimit,
    semanticsPass,
    checksPassed: checks.filter((check) => check.pass).length,
    checksTotal: checks.length,
    decision: semanticsPass && candidateStats.mean < controlStats.mean ? "retain" : (
      semanticsPass ? "reject-scaling" : "reject-transport"
    ),
    comparison: {
      candidate: candidateStats,
      control: controlStats,
      retainedMixedHot2: controlStats,
      meanRatio: candidateStats.mean / controlStats.mean,
      medianRatio: candidateStats.median / controlStats.median,
      meanSpeedupPercent: (1 - candidateStats.mean / controlStats.mean) * 100,
    },
    loads: {
      candidateMilliseconds: candidate.loadMilliseconds,
      controlMilliseconds: control.loadMilliseconds,
    },
    diagnostics,
    checks,
    candidateSamples,
    controlSamples,
  };
} finally {
  await browser.close();
}

await fs.writeFile(new URL(`${outputStem}.json`, artifactRoot), `${JSON.stringify(report, null, 2)}\n`);
const comparison = report.comparison;
const markdown = `# Mixed hot-2 block-gate A/B

Decision against ${controlDirectory}: **${report.decision}**.

The B=${reference.blockSize ?? "n/a"} candidate passed ${report.checksPassed}/${report.checksTotal} paired semantic checks. Its ${comparison.candidate.count}-sample warm mean was ${comparison.candidate.mean.toFixed(1)} ms versus ${comparison.control.mean.toFixed(1)} ms for the control page, ratio **${comparison.meanRatio.toFixed(3)}×** (${comparison.meanSpeedupPercent.toFixed(1)}% ${comparison.meanSpeedupPercent >= 0 ? "faster" : "slower"}). Medians were ${comparison.candidate.median.toFixed(1)} ms versus ${comparison.control.median.toFixed(1)} ms.

Both pages were loaded once, warmed once, and then evaluated in alternating order for ${report.rounds} rounds over ${report.fixtureLimit} fixtures. Every candidate route, final bucket, and winner had to match the retained page, the generated route, and the dense oracle. Chrome: ${report.chromeVersion}.
`;
await fs.writeFile(
  new URL(`${outputStem === "ab-results" ? "AB_RESULTS" : outputStem}.md`, artifactRoot),
  markdown,
);
console.log(JSON.stringify({
  decision: report.decision,
  semanticsPass: report.semanticsPass,
  checksPassed: report.checksPassed,
  checksTotal: report.checksTotal,
  comparison: report.comparison,
  loads: report.loads,
  diagnostics: report.diagnostics,
}, null, 2));
if (!report.semanticsPass) process.exitCode = 1;
