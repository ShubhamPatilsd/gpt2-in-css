import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const server = process.env.MIXED_HOT2_SERVER ?? "http://127.0.0.1:4191";
const subsetDirectory = "gpt2-mixed-precision-hot2-upper-subset";
const fullDirectory = "gpt2-mixed-precision-hot2-upper";
const controlDirectory = "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated";
const artifactRoot = new URL(`../experiments/${subsetDirectory}/`, import.meta.url);
const retainedRoot = new URL(`../experiments/${fullDirectory}/`, import.meta.url);
const subsetReference = JSON.parse(
  await fs.readFile(new URL("reference.json", artifactRoot), "utf8"),
);
const retainedReference = JSON.parse(
  await fs.readFile(new URL("reference.json", retainedRoot), "utf8"),
);
const fixtures = retainedReference.certifiedFixtures;
const stages = retainedReference.stages;
const repeatRounds = Math.max(
  1,
  Number.parseInt(process.env.MIXED_HOT2_SUBSET_ROUNDS ?? "3", 10),
);

if (fixtures.unrolledStageGroups[0][0] > 1 ||
    fixtures.unrolledStageGroups[1][0] <= 1 ||
    !fixtures.unrolledStageGroups[1].slice(1).some((group) => group <= 1)) {
  throw new Error("fixture 0/1 no longer cover hot-only and non-hot-to-hot routes");
}

function percentile(sorted, fraction) {
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * fraction))];
}

function statistics(values) {
  const sorted = [...values].sort((left, right) => left - right);
  return {
    count: sorted.length,
    minimum: sorted[0],
    median: percentile(sorted, 0.5),
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

function classifyFont(url) {
  if (url.includes(`/${subsetDirectory}/`) && /score-[hl]\d-hot2\.woff2$/.test(url)) {
    return "subset-exact";
  }
  if (url.includes("/gpt2-hvar-grid-output-head-global16-twoplane/") &&
      /score-[hl]\d\.woff2$/.test(url)) {
    return "full-exact";
  }
  return "other-woff2";
}

function summarizeFontRecords(records) {
  const categories = {};
  for (const category of ["subset-exact", "full-exact", "other-woff2"]) {
    const selected = records.filter((record) => record.category === category);
    categories[category] = {
      requests: selected.length,
      bytes: selected.reduce((sum, record) => sum + record.bytes, 0),
      urls: [...new Set(selected.map((record) => record.url))].sort(),
    };
  }
  return {
    requests: records.length,
    bytes: records.reduce((sum, record) => sum + record.bytes, 0),
    urls: [...new Set(records.map((record) => record.url))].sort(),
    categories,
  };
}

function createFontTracker(page) {
  let phase = "cold-load";
  const requestPhases = new Map();
  const pending = new Set();
  const records = [];
  page.on("request", (request) => {
    if (/\.woff2(?:$|\?)/.test(request.url())) requestPhases.set(request, phase);
  });
  page.on("response", (response) => {
    const request = response.request();
    if (!requestPhases.has(request)) return;
    const responsePhase = requestPhases.get(request);
    const task = (async () => {
      const header = await response.headerValue("content-length");
      const bytes = Number.parseInt(header ?? "0", 10);
      records.push({
        phase: responsePhase,
        url: response.url(),
        status: response.status(),
        bytes: Number.isFinite(bytes) ? bytes : 0,
        category: classifyFont(response.url()),
      });
    })();
    pending.add(task);
    task.finally(() => pending.delete(task));
  });
  return {
    setPhase(value) {
      phase = value;
    },
    async flush() {
      while (pending.size) await Promise.all([...pending]);
    },
    report() {
      const byPhase = {};
      for (const name of [
        "cold-load",
        "hot-fixture-0",
        "first-non-hot-fixture-1",
        "hot-reset-fixture-0",
        "subsequent-non-hot-fixture-1",
      ]) {
        byPhase[name] = summarizeFontRecords(
          records.filter((record) => record.phase === name),
        );
      }
      return { records, total: summarizeFontRecords(records), byPhase };
    },
  };
}

async function waitForFontsAndLayout(page) {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
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

async function settleMixed(page) {
  for (let pass = 0; pass < 3; pass += 1) {
    await page.locator("#result").evaluate(
      (element) => element.getBoundingClientRect().width,
    );
    for (let stage = 0; stage < stages; stage += 1) {
      const wrapper = page.locator(`#mixed-stage-${stage}`);
      if (await wrapper.evaluate((element) => getComputedStyle(element).display) === "none") {
        break;
      }
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

async function settleControl(page) {
  for (let pass = 0; pass < 3; pass += 1) {
    for (const selector of ["#result", "#fine-stage", "#fine-result"]) {
      await page.locator(selector).evaluate(
        (element) => element.getBoundingClientRect().width,
      );
    }
    for (let stage = 1; stage <= stages; stage += 1) {
      const remaining = page.locator(`#remaining-result-${stage}`);
      await remaining.evaluate((element) => element.getBoundingClientRect().width);
      const done = await remaining.evaluate(
        (element, property) => Number(getComputedStyle(element).getPropertyValue(property)),
        `--done-${stage - 1}`,
      );
      if (done === 1) break;
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

async function observeMixed(page) {
  return page.evaluate((stageCount) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    let group = number(getComputedStyle(document.querySelector("#result")), "--group");
    const observations = [];
    for (let stage = 0; stage < stageCount; stage += 1) {
      const wrapper = getComputedStyle(document.querySelector(`#mixed-stage-${stage}`));
      if (wrapper.display === "none") break;
      const dynamic = getComputedStyle(
        document.querySelector(`#dynamic-fine-stage-${stage}`),
      );
      const fine = getComputedStyle(document.querySelector(
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
      ));
      const remaining = getComputedStyle(
        document.querySelector(`#remaining-result-${stage + 1}`),
      );
      const item = {
        stage,
        group,
        dynamicDisplay: dynamic.display,
        fineCode: number(fine, `--fine-code-${stage}`),
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

async function observeControl(page) {
  return page.evaluate((stageCount) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    let group = number(getComputedStyle(document.querySelector("#result")), "--group");
    const observations = [];
    for (let stage = 0; stage < stageCount; stage += 1) {
      const fine = getComputedStyle(document.querySelector(
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
      ));
      const remaining = getComputedStyle(
        document.querySelector(`#remaining-result-${stage + 1}`),
      );
      const item = {
        stage,
        group,
        fineBucket: number(
          fine,
          stage === 0 ? "--fine-bucket" : `--fine-bucket-${stage}`,
        ),
        fineWinner: number(
          fine,
          stage === 0 ? "--refined-winner" : `--fine-winner-${stage}`,
        ),
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
    return { stages: observations, finalWinner: observations.at(-1)?.bestWinner };
  }, stages);
}

async function forceExactShadow(page, group) {
  const stage = page.locator("#fine-stage");
  await stage.evaluate((element, value) => {
    element.style.setProperty("--group", String(value));
  }, group);
  for (let pass = 0; pass < 3; pass += 1) {
    for (const selector of ["#fine-stage", ".fine-reader", "#fine-result"]) {
      await page.locator(selector).evaluate(
        (element) => element.getBoundingClientRect().width,
      );
    }
  }
  const shadow = await page.locator("#fine-result").evaluate((element, value) => {
    const style = getComputedStyle(element);
    const fineBucket = Number(style.getPropertyValue("--fine-bucket"));
    const fineLocal = Number(style.getPropertyValue("--fine-local"));
    return {
      group: value,
      fineBucket,
      fineWinner: value * 256 + fineLocal,
      source: "forced-control-exact-grid",
    };
  }, group);
  await stage.evaluate((element) => element.style.removeProperty("--group"));
  return shadow;
}

async function evaluateMixed(page, fixture) {
  const started = performance.now();
  await setInput(page, fixture);
  await settleMixed(page);
  await waitForFontsAndLayout(page);
  return {
    fixture,
    milliseconds: performance.now() - started,
    output: await observeMixed(page),
  };
}

async function loadMixedPage(context, directory) {
  const page = await context.newPage();
  page.setDefaultTimeout(900_000);
  const failures = [];
  page.on("requestfailed", (request) => failures.push({
    url: request.url(),
    error: request.failure()?.errorText,
  }));
  const tracker = createFontTracker(page);
  const started = performance.now();
  await page.goto(`${server}/experiments/${directory}/index.html`, {
    waitUntil: "load",
    timeout: 900_000,
  });
  await waitForFontsAndLayout(page);
  await tracker.flush();
  return { page, tracker, failures, milliseconds: performance.now() - started };
}

async function runVariant(browser, variant, directory, round) {
  const context = await browser.newContext({ viewport: { width: 800, height: 200 } });
  try {
    const loaded = await loadMixedPage(context, directory);
    const mutations = {};
    for (const [name, fixture] of [
      ["hot", 0],
      ["firstNonHot", 1],
      ["hotReset", 0],
      ["subsequentNonHot", 1],
    ]) {
      const phase = {
        hot: "hot-fixture-0",
        firstNonHot: "first-non-hot-fixture-1",
        hotReset: "hot-reset-fixture-0",
        subsequentNonHot: "subsequent-non-hot-fixture-1",
      }[name];
      loaded.tracker.setPhase(phase);
      mutations[name] = await evaluateMixed(loaded.page, fixture);
      await loaded.tracker.flush();
    }
    return {
      round,
      variant,
      directory,
      coldLoadMilliseconds: loaded.milliseconds,
      requestFailures: loaded.failures,
      mutations,
      network: loaded.tracker.report(),
    };
  } finally {
    await context.close();
  }
}

async function runPair(browser, round) {
  const order = round % 2 === 0
    ? [["subset", subsetDirectory], ["full", fullDirectory]]
    : [["full", fullDirectory], ["subset", subsetDirectory]];
  const sequences = {};
  for (const [variant, directory] of order) {
    sequences[variant] = await runVariant(browser, variant, directory, round);
  }
  return { round, loadOrder: order.map(([variant]) => variant), ...sequences };
}

async function collectExactShadows(browser, focusedPair) {
  const required = new Map([[0, new Set()], [1, new Set()]]);
  for (const variant of ["subset", "full"]) {
    for (const sample of Object.values(focusedPair[variant].mutations)) {
      for (const stage of sample.output.stages) required.get(sample.fixture).add(stage.group);
    }
  }
  const context = await browser.newContext({ viewport: { width: 800, height: 200 } });
  try {
    const page = await context.newPage();
    page.setDefaultTimeout(900_000);
    await page.goto(`${server}/experiments/${controlDirectory}/index.html`, {
      waitUntil: "load",
      timeout: 900_000,
    });
    await waitForFontsAndLayout(page);
    const byFixture = {};
    let requested = 0;
    let fromControlRoute = 0;
    let forcedExact = 0;
    for (const fixture of [0, 1]) {
      await setInput(page, fixture);
      await settleControl(page);
      await waitForFontsAndLayout(page);
      const control = await observeControl(page);
      const shadows = new Map(control.stages.map((stage) => [stage.group, {
        group: stage.group,
        fineBucket: stage.fineBucket,
        fineWinner: stage.fineWinner,
        source: "control-route-exact-grid",
      }]));
      for (const group of required.get(fixture)) {
        requested += 1;
        if (shadows.has(group)) fromControlRoute += 1;
        else {
          shadows.set(group, await forceExactShadow(page, group));
          forcedExact += 1;
        }
      }
      byFixture[fixture] = [...shadows.values()].filter(
        (shadow) => required.get(fixture).has(shadow.group),
      );
    }
    return { byFixture, requested, fromControlRoute, forcedExact, missing: 0 };
  } finally {
    await context.close();
  }
}

function validateSample(sample, shadows, round, variant, mutation) {
  const byGroup = new Map(shadows.map((shadow) => [shadow.group, shadow]));
  const expectedGroups = fixtures.unrolledStageGroups[sample.fixture];
  let liveBestBucket = -Infinity;
  let liveBestWinner = Infinity;
  const stageChecks = sample.output.stages.map((stage, index) => {
    const shadow = byGroup.get(stage.group);
    if (shadow && (shadow.fineBucket > liveBestBucket ||
        (shadow.fineBucket === liveBestBucket && shadow.fineWinner < liveBestWinner))) {
      liveBestBucket = shadow.fineBucket;
      liveBestWinner = shadow.fineWinner;
    }
    return {
      stage: index,
      groupMatchesGeneratedRoute: stage.group === expectedGroups[index],
      liveExactShadowPresent: shadow !== undefined,
      winnerMatchesLiveExactShadow: stage.fineWinner === shadow?.fineWinner,
      bucketMatchesLiveExactShadow: stage.fineBucket === shadow?.fineBucket,
      bestWinnerMatchesLiveRecompute: stage.bestWinner === liveBestWinner,
      bestBucketMatchesLiveRecompute: stage.bestBucket === liveBestBucket,
      gapArithmeticMatches:
        stage.certificateGap === stage.bestBucket - stage.nextUpperBucket,
      stoppingMatchesLiveGap: stage.done === (stage.certificateGap > 48 ? 1 : 0),
      routeDisplayMatches: stage.group <= 1
        ? stage.dynamicDisplay === "none"
        : stage.dynamicDisplay === "grid",
      noUnexpectedConstant255:
        stage.group > 1 || shadow?.fineWinner % 256 === 255 || stage.fineCode !== 255,
    };
  });
  const firstDone = sample.output.stages.findIndex((stage) => stage.done === 1);
  const check = {
    round,
    variant,
    mutation,
    fixture: sample.fixture,
    stoppedAtFirstLiveDone: firstDone < 0
      ? sample.output.activeStages === stages
      : sample.output.activeStages === firstDone + 1,
    finalExactWinnerMatches: sample.output.finalWinner === fixtures.denseWinners[sample.fixture],
    stageChecks,
  };
  check.pass = check.stoppedAtFirstLiveDone && check.finalExactWinnerMatches &&
    stageChecks.every((stage) => Object.entries(stage).every(
      ([key, value]) => key === "stage" || value === true));
  return check;
}

function semanticSignature(sample) {
  return JSON.stringify({
    finalWinner: sample.output.finalWinner,
    finalBucket: sample.output.finalBucket,
    stages: sample.output.stages.map((stage) => ({
      group: stage.group,
      fineBucket: stage.fineBucket,
      fineWinner: stage.fineWinner,
      bestBucket: stage.bestBucket,
      bestWinner: stage.bestWinner,
      certificateGap: stage.certificateGap,
      nextUpperBucket: stage.nextUpperBucket,
      done: stage.done,
    })),
  });
}

function exactStartupBytes(sequence) {
  const phases = sequence.network.byPhase;
  return [phases["cold-load"], phases["hot-fixture-0"]].reduce(
    (sum, phase) => sum + phase.categories["subset-exact"].bytes +
      phase.categories["full-exact"].bytes,
    0,
  );
}

function totalStartupFontBytes(sequence) {
  const phases = sequence.network.byPhase;
  return phases["cold-load"].bytes + phases["hot-fixture-0"].bytes;
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const pairs = [await runPair(browser, 0)];
  const exactShadows = await collectExactShadows(browser, pairs[0]);
  const focusedChecks = [];
  for (const variant of ["subset", "full"]) {
    for (const [mutation, sample] of Object.entries(pairs[0][variant].mutations)) {
      focusedChecks.push(validateSample(
        sample,
        exactShadows.byFixture[sample.fixture],
        0,
        variant,
        mutation,
      ));
    }
  }
  const focusedCrossVariantMatches = Object.keys(pairs[0].subset.mutations).every(
    (mutation) => semanticSignature(pairs[0].subset.mutations[mutation]) ===
      semanticSignature(pairs[0].full.mutations[mutation]),
  );
  const focusedSemanticsPass = focusedChecks.every((check) => check.pass) &&
    focusedCrossVariantMatches;
  const focusedStartupBytesImprove =
    totalStartupFontBytes(pairs[0].subset) < totalStartupFontBytes(pairs[0].full) &&
    exactStartupBytes(pairs[0].subset) < exactStartupBytes(pairs[0].full);

  if (focusedSemanticsPass && focusedStartupBytesImprove) {
    for (let round = 1; round < repeatRounds; round += 1) {
      pairs.push(await runPair(browser, round));
    }
  }

  const checks = [];
  const crossVariant = [];
  for (const pair of pairs) {
    for (const variant of ["subset", "full"]) {
      for (const [mutation, sample] of Object.entries(pair[variant].mutations)) {
        checks.push(validateSample(
          sample,
          exactShadows.byFixture[sample.fixture],
          pair.round,
          variant,
          mutation,
        ));
      }
    }
    for (const mutation of Object.keys(pair.subset.mutations)) {
      crossVariant.push({
        round: pair.round,
        mutation,
        pass: semanticSignature(pair.subset.mutations[mutation]) ===
          semanticSignature(pair.full.mutations[mutation]),
      });
    }
  }

  const semanticsPass = checks.every((check) => check.pass) &&
    crossVariant.every((check) => check.pass);
  const startupBytesImproveEveryRound = pairs.every((pair) =>
    totalStartupFontBytes(pair.subset) < totalStartupFontBytes(pair.full) &&
    exactStartupBytes(pair.subset) < exactStartupBytes(pair.full));
  const timing = {};
  for (const variant of ["subset", "full"]) {
    timing[variant] = {
      coldLoad: statistics(pairs.map((pair) => pair[variant].coldLoadMilliseconds)),
      hotMutation: statistics(pairs.map(
        (pair) => pair[variant].mutations.hot.milliseconds)),
      firstNonHotMutation: statistics(pairs.map(
        (pair) => pair[variant].mutations.firstNonHot.milliseconds)),
      subsequentNonHotMutation: statistics(pairs.map(
        (pair) => pair[variant].mutations.subsequentNonHot.milliseconds)),
    };
  }
  const warmHotMeanRatio = timing.subset.hotMutation.mean / timing.full.hotMutation.mean;
  const warmHotTimingWithin15Percent = warmHotMeanRatio >= 0.85 && warmHotMeanRatio <= 1.15;
  const requestFailures = pairs.flatMap((pair) => [
    ...pair.subset.requestFailures.map((failure) => ({ ...failure, round: pair.round, variant: "subset" })),
    ...pair.full.requestFailures.map((failure) => ({ ...failure, round: pair.round, variant: "full" })),
  ]);
  const completedRepeat = pairs.length === repeatRounds;
  report = {
    timestamp: new Date().toISOString(),
    chromeVersion: await browser.version(),
    backgroundLoadCaveat:
      "PID 16288 (long-running Cursor editor MCP server) remained near 100% CPU by user instruction; paired relative request-byte and semantic results are primary, while absolute cold times are conditional on that load.",
    requestedRounds: repeatRounds,
    completedRounds: pairs.length,
    decision: !focusedSemanticsPass
      ? "reject-semantics"
      : !focusedStartupBytesImprove
        ? "reject-startup-bytes"
        : semanticsPass && startupBytesImproveEveryRound && completedRepeat
          ? "retain-subset"
          : "reject-repeat",
    focusedSemanticsPass,
    focusedStartupBytesImprove,
    semanticsPass,
    startupBytesImproveEveryRound,
    completedRepeat,
    exactShadowCoverage: {
      requested: exactShadows.requested,
      fromControlRoute: exactShadows.fromControlRoute,
      forcedExact: exactShadows.forcedExact,
      missing: exactShadows.missing,
    },
    checks,
    crossVariant,
    timing,
    warmHotMeanRatio,
    warmHotTimingWithin15Percent,
    requestFailures,
    staticBytes: {
      subsetExactBank: subsetReference.hotSubsetBank.woff2Bytes,
      fullExactBank: subsetReference.fullExactBank.woff2Bytes,
    },
    pairs,
  };
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("browser-results.json", artifactRoot),
  `${JSON.stringify(report, null, 2)}\n`,
);

const format = (value) => value.toFixed(1);
const focused = report.pairs[0];
const roundRows = report.pairs.map((pair) => `| ${pair.round} | ${pair.loadOrder.join(" then ")} | ${format(pair.subset.coldLoadMilliseconds)} ms | ${format(pair.full.coldLoadMilliseconds)} ms | ${totalStartupFontBytes(pair.subset).toLocaleString()} | ${totalStartupFontBytes(pair.full).toLocaleString()} |`).join("\n");
const beforeNonHot = [
  ...focused.subset.network.byPhase["cold-load"].urls,
  ...focused.subset.network.byPhase["hot-fixture-0"].urls,
];
const firstNonHotUrls = focused.subset.network.byPhase["first-non-hot-fixture-1"].urls;
const markdown = `# Mixed-precision hot-2 exact-font subset browser probe

Decision: **${report.decision}**.

The retained full-bank mixed page and subset page used identical row topology. The focused same-page sequence was fixture 0 (hot-only), fixture 1 (non-hot to hot), fixture 0, then fixture 1 again. The additional rounds repeated that sequence only after focused semantics and startup-byte gates passed.

## Exactness

- Live exact-shadow checks: ${report.checks.filter((check) => check.pass).length}/${report.checks.length} mutations; ${report.checks.flatMap((check) => check.stageChecks).filter((check) => Object.entries(check).every(([key, value]) => key === "stage" || value === true)).length}/${report.checks.flatMap((check) => check.stageChecks).length} stage gates.
- Dense final winners: ${report.checks.filter((check) => check.finalExactWinnerMatches).length}/${report.checks.length}.
- Subset/full semantic signatures: ${report.crossVariant.filter((check) => check.pass).length}/${report.crossVariant.length}.
- Exact-shadow coverage: ${report.exactShadowCoverage.requested - report.exactShadowCoverage.missing}/${report.exactShadowCoverage.requested} selected fixture/group pairs (${report.exactShadowCoverage.fromControlRoute} on route, ${report.exactShadowCoverage.forcedExact} forced).

## Requested fonts

- Focused subset hot startup exact bytes: ${exactStartupBytes(focused.subset).toLocaleString()}; full-bank page: ${exactStartupBytes(focused.full).toLocaleString()}.
- Subset-page startup exact breakdown: ${focused.subset.network.byPhase["cold-load"].categories["subset-exact"].bytes.toLocaleString()} subset bytes plus ${focused.subset.network.byPhase["cold-load"].categories["full-exact"].bytes.toLocaleString()} eagerly requested full-bank bytes. The eager full-bank requests are score-h0/l0, so the browser does not realize the static ideal of a subset-only hot load.
- Focused subset total WOFF2 startup bytes: ${totalStartupFontBytes(focused.subset).toLocaleString()}; full-bank page: ${totalStartupFontBytes(focused.full).toLocaleString()}.
- Full exact bytes lazily requested by the subset page on first non-hot activation: ${focused.subset.network.byPhase["first-non-hot-fixture-1"].categories["full-exact"].bytes.toLocaleString()} across ${focused.subset.network.byPhase["first-non-hot-fixture-1"].categories["full-exact"].requests} responses.
- Full exact bytes requested on the subsequent non-hot activation: ${focused.subset.network.byPhase["subsequent-non-hot-fixture-1"].categories["full-exact"].bytes.toLocaleString()}.

Actual subset-page WOFF2 URLs requested before first non-hot activation (${beforeNonHot.length}):

${beforeNonHot.map((url) => `- \`${url}\``).join("\n")}

New subset-page WOFF2 URLs requested by first non-hot activation (${firstNonHotUrls.length}):

${firstNonHotUrls.map((url) => `- \`${url}\``).join("\n")}

## Timing

Absolute cold times are conditional: ${report.backgroundLoadCaveat}

| Metric | Subset page mean | Retained full-bank mean |
|---|---:|---:|
| cold load | ${format(report.timing.subset.coldLoad.mean)} ms | ${format(report.timing.full.coldLoad.mean)} ms |
| hot fixture-0 mutation | ${format(report.timing.subset.hotMutation.mean)} ms | ${format(report.timing.full.hotMutation.mean)} ms |
| first non-hot fixture-1 mutation | ${format(report.timing.subset.firstNonHotMutation.mean)} ms | ${format(report.timing.full.firstNonHotMutation.mean)} ms |
| subsequent non-hot fixture-1 mutation | ${format(report.timing.subset.subsequentNonHotMutation.mean)} ms | ${format(report.timing.full.subsequentNonHotMutation.mean)} ms |

Hot semantics are unchanged: **${report.crossVariant.filter((check) => check.mutation === "hot").every((check) => check.pass)}**. Hot timing ratio is **${report.warmHotMeanRatio.toFixed(3)}x**; within the predeclared ±15% small-repeat band: **${report.warmHotTimingWithin15Percent}**.

### Cold repeat

| Round | Load order | Subset cold | Full cold | Subset startup WOFF2 bytes | Full startup WOFF2 bytes |
|---:|---|---:|---:|---:|---:|
${roundRows}

The static bank sizes are ${report.staticBytes.subsetExactBank.toLocaleString()} bytes subset and ${report.staticBytes.fullExactBank.toLocaleString()} bytes full. Measured request figures above count the response Content-Length for actual WOFF2 requests; they do not count declared-but-unrequested faces. Request failures: ${report.requestFailures.length}.

Chrome: ${report.chromeVersion}. Full observations are in browser-results.json; the pre-browser static report is preserved as RESULTS-static.md.
`;
await fs.writeFile(new URL("RESULTS.md", artifactRoot), markdown);

console.log(JSON.stringify({
  decision: report.decision,
  completedRounds: report.completedRounds,
  semanticsPass: report.semanticsPass,
  checksPassed: report.checks.filter((check) => check.pass).length,
  checksTotal: report.checks.length,
  timing: report.timing,
  warmHotMeanRatio: report.warmHotMeanRatio,
  startup: report.pairs.map((pair) => ({
    round: pair.round,
    subsetWoff2Bytes: totalStartupFontBytes(pair.subset),
    fullWoff2Bytes: totalStartupFontBytes(pair.full),
  })),
}, null, 2));

if (!report.semanticsPass || report.decision !== "retain-subset") process.exitCode = 1;
