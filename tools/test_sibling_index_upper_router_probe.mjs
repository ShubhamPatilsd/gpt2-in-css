import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const output = new URL("../experiments/sibling-index-upper-router/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", output), "utf8"));
const coldSamples = Number(process.env.SIBLING_INDEX_ROUTER_COLD_SAMPLES ?? 25);
const warmBatches = Number(process.env.SIBLING_INDEX_ROUTER_WARM_BATCHES ?? 31);
const mutationsPerBatch = Number(
  process.env.SIBLING_INDEX_ROUTER_MUTATIONS_PER_BATCH ?? 40,
);

function median(values) {
  const ordered = [...values].sort((left, right) => left - right);
  return ordered[Math.floor(ordered.length / 2)];
}

function summarize(values) {
  return {
    samples: values.length,
    medianMilliseconds: median(values),
    minimumMilliseconds: Math.min(...values),
    maximumMilliseconds: Math.max(...values),
    samplesMilliseconds: values,
  };
}

function percent(value) {
  return `${(value * 100).toFixed(1)}%`;
}

function milliseconds(value) {
  return value.toFixed(3);
}

async function readRoute(page) {
  return page.locator("#result").evaluate((element, stride) => {
    const rect = element.getBoundingClientRect();
    const scoreMax = document.querySelector(".score-max").getBoundingClientRect();
    const groupMax = document.querySelector(".group-max").getBoundingClientRect();
    return {
      group: Math.round(rect.height) - 1,
      scoreBucket: Math.round(rect.width / stride),
      width: rect.width,
      height: rect.height,
      scoreMaxWidth: scoreMax.width,
      groupMaxWidth: groupMax.width,
    };
  }, reference.scoreStridePixels);
}

async function setState(page, scores, visited = []) {
  await page.locator("#probe").evaluate((probe, state) => {
    const sources = probe.querySelectorAll(".score-source");
    const candidates = probe.querySelectorAll(".candidate");
    const visitedSet = new Set(state.visited);
    for (let group = 0; group < state.scores.length; group += 1) {
      const score = String(state.scores[group]);
      const active = visitedSet.has(group) ? "0" : "1";
      sources[group].style.setProperty("--score", score);
      sources[group].style.setProperty("--active", active);
      candidates[group].style.setProperty("--score", score);
      candidates[group].style.setProperty("--active", active);
    }
  }, { scores, visited });
}

async function restoreDefault(page) {
  await setState(page, reference.defaultScores);
  await readRoute(page);
}

async function inspectSupport(page) {
  return page.locator("#probe").evaluate((probe, groups) => {
    const candidates = probe.querySelectorAll(".candidate");
    const matches = probe.querySelectorAll(".match");
    const localSources = probe.querySelectorAll(".local-source");
    const positions = [0, Math.floor(groups / 2), groups - 1];
    const candidateIndices = positions.map((position) => Number(
      getComputedStyle(candidates[position]).getPropertyValue("--candidate-index"),
    ));
    const inheritedMatchIndices = positions.map((position) => Number(
      getComputedStyle(matches[position]).getPropertyValue("--candidate-index"),
    ));
    const localAnchorNames = positions.map(
      (position) => getComputedStyle(localSources[position]).anchorName,
    );
    const matchPositionAnchors = positions.map(
      (position) => getComputedStyle(matches[position]).positionAnchor,
    );
    const matchAnchorNames = positions.map(
      (position) => getComputedStyle(matches[position]).anchorName,
    );
    const anchorScopes = positions.map(
      (position) => getComputedStyle(candidates[position]).anchorScope,
    );
    return {
      cssSupportsSiblingIndexWidth: CSS.supports(
        "width",
        `calc((${groups + 1} - sibling-index()) * 1px)`,
      ),
      cssSupportsSiblingCountWidth: CSS.supports(
        "width",
        "calc(sibling-count() * 1px)",
      ),
      cssSupportsAnchorScope: CSS.supports("anchor-scope", "--local-score"),
      sampledPositions: positions,
      candidateIndices,
      inheritedMatchIndices,
      localAnchorNames,
      matchPositionAnchors,
      matchAnchorNames,
      anchorScopes,
      exactComputedIndices: candidateIndices.every(
        (value, index) => value === positions[index] + 1,
      ) && inheritedMatchIndices.every(
        (value, index) => value === positions[index] + 1,
      ),
      repeatedLocalAnchorsComputed: localAnchorNames.every(
        (value) => value === "--local-score",
      ) && matchPositionAnchors.every((value) => value === "--local-score")
        && anchorScopes.every((value) => value === "--local-score"),
      uniqueReducedAnchorsComputed: matchAnchorNames.every(
        (value, index) => value === `--match-${positions[index]}`,
      ),
    };
  }, reference.groups);
}

async function validateEveryWinner(page, kind) {
  return page.locator("#result").evaluate(
    (element, config) => {
      const sources = [...document.querySelectorAll(".score-source")];
      const candidates = [...document.querySelectorAll(".candidate")];
      const observedGroups = [];
      const observedBuckets = [];
      const setGroup = (group, score, active = 1) => {
        sources[group].style.setProperty("--score", String(score));
        sources[group].style.setProperty("--active", String(active));
        candidates[group].style.setProperty("--score", String(score));
        candidates[group].style.setProperty("--active", String(active));
      };
      for (let group = 0; group < config.groups; group += 1) setGroup(group, 100);
      let previous = 0;
      setGroup(previous, 220);
      for (let winner = 0; winner < config.groups; winner += 1) {
        if (winner !== previous) {
          setGroup(previous, 100);
          setGroup(winner, 220);
        }
        const rect = element.getBoundingClientRect();
        observedGroups.push(Math.round(rect.height) - 1);
        observedBuckets.push(Math.round(rect.width / config.stride));
        previous = winner;
      }
      const mismatchPositions = observedGroups.flatMap((group, position) => (
        group === position && observedBuckets[position] === 220 ? [] : [position]
      ));
      return {
        kind: config.kind,
        positionsTested: config.groups,
        expectedBucket: 220,
        observedGroups,
        observedBuckets,
        mismatchPositions,
        allExact: mismatchPositions.length === 0,
      };
    },
    {
      groups: reference.groups,
      stride: reference.scoreStridePixels,
      kind,
    },
  );
}

async function validateTies(page, kind) {
  const checks = [];
  const base = Array(reference.groups).fill(100);
  for (const pair of reference.tieCases) {
    const scores = [...base];
    for (const group of pair) scores[group] = 220;
    await setState(page, scores);
    const observed = await readRoute(page);
    const expectedGroup = Math.min(...pair);
    checks.push({
      kind,
      tiedGroups: pair,
      expectedGroup,
      expectedBucket: 220,
      observed,
      correct: observed.group === expectedGroup && observed.scoreBucket === 220,
    });
  }
  return checks;
}

async function validateVisited(page, kind) {
  const checks = [];
  for (const fixture of reference.visitedCases) {
    await setState(page, fixture.scores, fixture.visited);
    const observed = await readRoute(page);
    checks.push({
      kind,
      name: fixture.name,
      visited: fixture.visited,
      expectedGroup: fixture.expectedGroup,
      expectedBucket: fixture.expectedBucket,
      observed,
      correct: observed.group === fixture.expectedGroup
        && observed.scoreBucket === fixture.expectedBucket,
    });
  }
  return checks;
}

async function benchmarkWarm(page, kind) {
  const first = 29;
  const second = 163;
  const result = await page.locator("#result").evaluate(
    (element, config) => {
      const sources = document.querySelectorAll(".score-source");
      const candidates = document.querySelectorAll(".candidate");
      const setGroup = (group, score) => {
        sources[group].style.setProperty("--score", String(score));
        sources[group].style.setProperty("--active", "1");
        candidates[group].style.setProperty("--score", String(score));
        candidates[group].style.setProperty("--active", "1");
      };
      for (let group = 0; group < config.groups; group += 1) setGroup(group, 100);
      const mutate = (selectSecond) => {
        setGroup(config.first, selectSecond ? 240 : 260);
        setGroup(config.second, selectSecond ? 260 : 240);
        const rect = element.getBoundingClientRect();
        return {
          group: Math.round(rect.height) - 1,
          bucket: Math.round(rect.width / config.stride),
        };
      };
      let exact = true;
      for (let warmup = 0; warmup < 30; warmup += 1) {
        const secondWins = warmup % 2 === 1;
        const observed = mutate(secondWins);
        exact &&= observed.group === (secondWins ? config.second : config.first)
          && observed.bucket === 260;
      }
      const durations = [];
      for (let batch = 0; batch < config.batches; batch += 1) {
        const started = performance.now();
        for (let mutation = 0; mutation < config.mutationsPerBatch; mutation += 1) {
          const secondWins = mutation % 2 === 1;
          const observed = mutate(secondWins);
          exact &&= observed.group === (secondWins ? config.second : config.first)
            && observed.bucket === 260;
        }
        durations.push(
          (performance.now() - started) / config.mutationsPerBatch,
        );
      }
      return { durations, exact };
    },
    {
      groups: reference.groups,
      stride: reference.scoreStridePixels,
      first,
      second,
      batches: warmBatches,
      mutationsPerBatch,
    },
  );
  return {
    kind,
    mutation: `swap unique 260-bucket winner between groups ${first} and ${second}`,
    batches: warmBatches,
    mutationsPerBatch,
    exactDuringBenchmark: result.exact,
    ...summarize(result.durations),
  };
}

async function coldNavigationSample(context, url, kind, sample) {
  const page = await context.newPage();
  const session = await context.newCDPSession(page);
  await session.send("Network.enable");
  await session.send("Network.setCacheDisabled", { cacheDisabled: true });
  await page.addInitScript((expected) => {
    window.addEventListener("load", () => {
      const geometryStarted = performance.now();
      const element = document.querySelector("#result");
      const rect = element.getBoundingClientRect();
      const firstResultMilliseconds = performance.now();
      window.__siblingIndexColdResult = {
        firstResultMilliseconds,
        forcedGeometryMilliseconds: firstResultMilliseconds - geometryStarted,
        group: Math.round(rect.height) - 1,
        scoreBucket: Math.round(rect.width / expected.stride),
      };
    }, { once: true });
  }, { stride: reference.scoreStridePixels });
  const target = new URL(url);
  target.searchParams.set("cold", `${kind}-${sample}-${performance.now()}`);
  const hostStarted = performance.now();
  await page.goto(target.href, { waitUntil: "load" });
  const inPage = await page.evaluate(() => {
    const navigation = performance.getEntriesByType("navigation")[0];
    return {
      ...window.__siblingIndexColdResult,
      domContentLoadedMilliseconds: navigation.domContentLoadedEventEnd,
      loadEventMilliseconds: navigation.loadEventEnd,
    };
  });
  const hostWallMilliseconds = performance.now() - hostStarted;
  await page.close();
  return {
    ...inPage,
    hostWallMilliseconds,
    exact: inPage.group === reference.defaultGroup
      && inPage.scoreBucket === reference.defaultBucket,
  };
}

async function benchmarkCold(context) {
  const urls = {
    siblingIndex: new URL("index.html", output),
    baseline: new URL("baseline.html", output),
  };
  const raw = { siblingIndex: [], baseline: [] };
  for (let sample = 0; sample < coldSamples; sample += 1) {
    const order = sample % 2 === 0
      ? ["siblingIndex", "baseline"]
      : ["baseline", "siblingIndex"];
    for (const kind of order) {
      raw[kind].push(await coldNavigationSample(context, urls[kind], kind, sample));
    }
  }
  const summarizeKind = (key, label) => ({
    kind: label,
    cacheDisabled: true,
    freshPagePerSample: true,
    exactDuringBenchmark: raw[key].every(({ exact }) => exact),
    firstResult: summarize(raw[key].map(({ firstResultMilliseconds }) => (
      firstResultMilliseconds
    ))),
    hostWall: summarize(raw[key].map(({ hostWallMilliseconds }) => hostWallMilliseconds)),
    domContentLoaded: summarize(raw[key].map(({ domContentLoadedMilliseconds }) => (
      domContentLoadedMilliseconds
    ))),
    loadEvent: summarize(raw[key].map(({ loadEventMilliseconds }) => loadEventMilliseconds)),
    observations: raw[key],
  });
  return {
    method: "fresh page, disk cache disabled, unique file-URL query; init script forces and timestamps result geometry synchronously in the load event",
    injectedMeasurementScript: true,
    siblingIndex: summarizeKind("siblingIndex", "sibling-index"),
    baseline: summarizeKind("baseline", "explicit-class"),
  };
}

async function currentSourceBytes() {
  const names = ["index.html", "sibling-index.css", "baseline.html", "baseline.css"];
  const sizes = {};
  for (const name of names) {
    sizes[name] = (await fs.stat(new URL(name, output))).size;
  }
  return {
    siblingIndex: {
      "index.html": sizes["index.html"],
      "sibling-index.css": sizes["sibling-index.css"],
      total: sizes["index.html"] + sizes["sibling-index.css"],
    },
    baseline: {
      "baseline.html": sizes["baseline.html"],
      "baseline.css": sizes["baseline.css"],
      total: sizes["baseline.html"] + sizes["baseline.css"],
    },
  };
}

function resultsMarkdown(report) {
  const { source, cold, warm } = report.comparison;
  const verdict = report.accepted
    ? "Accept the sibling-index/local-anchor form for source and cold-load reduction."
    : "Do not accept the sibling-index/local-anchor form as a material source-and-cold-load win.";
  const semanticLine = report.exactSemantics
    ? `All ${reference.groups} unique-winner positions, ${reference.tieCases.length} tie cases, and ${reference.visitedCases.length} visited-mask cases were exact in both routers.`
    : "At least one support, computed-value, winner, tie, mask, or benchmark exactness check failed.";
  return `# Sibling-index/local-anchor upper router

## Result

${verdict}

Chrome ${report.chrome} parsed the required \`sibling-index()\` and \`anchor-scope\` grammar. ${semanticLine}

The generic page is ${source.siblingIndex.total.toLocaleString("en-US")} raw HTML+CSS bytes versus ${source.baseline.total.toLocaleString("en-US")} bytes for the structurally matched explicit-class baseline, a ${percent(source.reduction)} reduction. Median cache-disabled navigation-to-first-result was ${milliseconds(cold.siblingIndex.firstResult.medianMilliseconds)} ms versus ${milliseconds(cold.baseline.firstResult.medianMilliseconds)} ms, a ${percent(cold.reduction)} reduction. The materiality gates were at least ${percent(reference.materialSourceReductionThreshold)} source reduction and ${percent(reference.materialColdReductionThreshold)} cold reduction.

Warm winner mutation was measured but is not an acceptance gate: ${milliseconds(warm.siblingIndex.medianMilliseconds)} ms/mutation for sibling-index versus ${milliseconds(warm.baseline.medianMilliseconds)} ms/mutation for explicit classes (${warm.ratio.toFixed(3)}x baseline/sibling-index). This isolated router probe makes no shaping or end-to-end runtime improvement claim.

## Raw bytes

| Router | HTML | CSS | Total |
| --- | ---: | ---: | ---: |
| sibling-index/local-anchor | ${source.siblingIndex["index.html"].toLocaleString("en-US")} | ${source.siblingIndex["sibling-index.css"].toLocaleString("en-US")} | ${source.siblingIndex.total.toLocaleString("en-US")} |
| explicit ID/class | ${source.baseline["baseline.html"].toLocaleString("en-US")} | ${source.baseline["baseline.css"].toLocaleString("en-US")} | ${source.baseline.total.toLocaleString("en-US")} |

## Semantics checked

- \`CSS.supports()\` for tree-counting width expressions and \`anchor-scope\`.
- Computed candidate indices 1, 99, and 197, including inherited registered-integer values on match elements.
- Repeated computed \`--local-score\` anchor names and scopes, with unique globally reduced match anchors.
- A unique 220-bucket maximum at every zero-based group 0 through 196.
- Equal-score ties select the lowest zero-based group index.
- Single, pair, scattered, and all-but-one visited masks.

Full observations and timing samples are in \`browser-results.json\`.

## Reproduce

\`\`\`sh
python3 tools/build_sibling_index_upper_router_probe.py
SIBLING_INDEX_ROUTER_RUN_CHROME=1 node tools/test_sibling_index_upper_router_probe.mjs
\`\`\`
`;
}

if (process.env.SIBLING_INDEX_ROUTER_RUN_CHROME !== "1") {
  console.error(
    "Chrome benchmark is gated; set SIBLING_INDEX_ROUTER_RUN_CHROME=1 after confirming an uncontended run window.",
  );
  process.exit(2);
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const context = await browser.newContext({
    javaScriptEnabled: true,
    viewport: { width: 800, height: 400 },
  });
  const siblingPage = await context.newPage();
  const baselinePage = await context.newPage();
  await siblingPage.goto(new URL("index.html", output).href, { waitUntil: "load" });
  await baselinePage.goto(new URL("baseline.html", output).href, { waitUntil: "load" });

  const support = await inspectSupport(siblingPage);
  const defaults = {
    siblingIndex: await readRoute(siblingPage),
    baseline: await readRoute(baselinePage),
  };
  const defaultExact = Object.values(defaults).every(
    ({ group, scoreBucket }) => group === reference.defaultGroup
      && scoreBucket === reference.defaultBucket,
  );

  const uniqueWinners = {
    siblingIndex: await validateEveryWinner(siblingPage, "sibling-index"),
    baseline: await validateEveryWinner(baselinePage, "explicit-class"),
  };
  await restoreDefault(siblingPage);
  await restoreDefault(baselinePage);
  const ties = {
    siblingIndex: await validateTies(siblingPage, "sibling-index"),
    baseline: await validateTies(baselinePage, "explicit-class"),
  };
  const visitedMasks = {
    siblingIndex: await validateVisited(siblingPage, "sibling-index"),
    baseline: await validateVisited(baselinePage, "explicit-class"),
  };
  await restoreDefault(siblingPage);
  await restoreDefault(baselinePage);

  const warm = {
    baseline: await benchmarkWarm(baselinePage, "explicit-class"),
    siblingIndex: await benchmarkWarm(siblingPage, "sibling-index"),
  };
  await siblingPage.close();
  await baselinePage.close();
  const cold = await benchmarkCold(context);
  const source = await currentSourceBytes();
  const sourceReduction = (source.baseline.total - source.siblingIndex.total)
    / source.baseline.total;
  const coldReduction = (
    cold.baseline.firstResult.medianMilliseconds
      - cold.siblingIndex.firstResult.medianMilliseconds
  ) / cold.baseline.firstResult.medianMilliseconds;
  const exactSemantics = support.cssSupportsSiblingIndexWidth
    && support.cssSupportsSiblingCountWidth
    && support.cssSupportsAnchorScope
    && support.exactComputedIndices
    && support.repeatedLocalAnchorsComputed
    && support.uniqueReducedAnchorsComputed
    && defaultExact
    && uniqueWinners.siblingIndex.allExact
    && uniqueWinners.baseline.allExact
    && Object.values(ties).flat().every(({ correct }) => correct)
    && Object.values(visitedMasks).flat().every(({ correct }) => correct)
    && warm.siblingIndex.exactDuringBenchmark
    && warm.baseline.exactDuringBenchmark
    && cold.siblingIndex.exactDuringBenchmark
    && cold.baseline.exactDuringBenchmark;
  const materialSourceReduction = sourceReduction
    >= reference.materialSourceReductionThreshold;
  const materialColdReduction = coldReduction
    >= reference.materialColdReductionThreshold;
  const accepted = exactSemantics && materialSourceReduction && materialColdReduction;
  report = {
    status: accepted ? "accepted" : "rejected",
    accepted,
    exactSemantics,
    chrome: await browser.version(),
    runtimeJavaScriptInGeneratedPages: false,
    injectedBenchmarkMeasurementScript: true,
    topology: {
      groups: reference.groups,
      elementsPerRouter: reference.elementsPerRouter,
      scoreWidthsIdenticalAcrossRouters: true,
      siblingIndexIdentity: "registered inherited --candidate-index",
      localAnchor: "wrapper-scoped repeated --local-score",
      globalReductionAnchors: "unique --score-N and --match-N names",
    },
    support,
    validation: {
      defaults,
      defaultExact,
      uniqueWinners,
      ties,
      visitedMasks,
    },
    comparison: {
      source: {
        ...source,
        reduction: sourceReduction,
        materialThreshold: reference.materialSourceReductionThreshold,
        materialReduction: materialSourceReduction,
      },
      cold: {
        ...cold,
        reduction: coldReduction,
        materialThreshold: reference.materialColdReductionThreshold,
        materialReduction: materialColdReduction,
      },
      warm: {
        ...warm,
        ratio: warm.baseline.medianMilliseconds
          / warm.siblingIndex.medianMilliseconds,
        acceptanceGate: false,
      },
    },
  };
  await context.close();
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("browser-results.json", output),
  `${JSON.stringify(report, null, 2)}\n`,
);
await fs.writeFile(new URL("RESULTS.md", output), resultsMarkdown(report));
console.log(JSON.stringify({
  status: report.status,
  chrome: report.chrome,
  exactSemantics: report.exactSemantics,
  sourceBytes: {
    siblingIndex: report.comparison.source.siblingIndex.total,
    baseline: report.comparison.source.baseline.total,
    reduction: report.comparison.source.reduction,
    material: report.comparison.source.materialReduction,
  },
  coldFirstResultMedianMilliseconds: {
    siblingIndex: report.comparison.cold.siblingIndex.firstResult.medianMilliseconds,
    baseline: report.comparison.cold.baseline.firstResult.medianMilliseconds,
    reduction: report.comparison.cold.reduction,
    material: report.comparison.cold.materialReduction,
  },
  warmMutationMedianMilliseconds: {
    siblingIndex: report.comparison.warm.siblingIndex.medianMilliseconds,
    baseline: report.comparison.warm.baseline.medianMilliseconds,
    baselineOverSiblingIndex: report.comparison.warm.ratio,
  },
}, null, 2));
if (!report.exactSemantics) process.exitCode = 1;
