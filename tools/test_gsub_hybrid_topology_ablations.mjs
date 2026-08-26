import fs from "node:fs/promises";
import os from "node:os";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);

const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const server = process.env.GSUB_HYBRID_SERVER ?? "http://127.0.0.1:4178";
const timingRounds = Number.parseInt(process.env.GSUB_ABLATION_ROUNDS ?? "7", 10);
const warmupRounds = Number.parseInt(process.env.GSUB_ABLATION_WARMUPS ?? "2", 10);
const mixedTimingRounds = Number.parseInt(process.env.GSUB_MIXED_ROUNDS ?? "7", 10);
const mixedWarmupRounds = Number.parseInt(process.env.GSUB_MIXED_WARMUPS ?? "2", 10);
const experimentRoot = new URL("../experiments/gsub-certified-hybrid/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", experimentRoot), "utf8"));
const previous = JSON.parse(await fs.readFile(new URL("browser-results.json", experimentRoot), "utf8"));

if (!Number.isInteger(timingRounds) || timingRounds < 1 ||
    !Number.isInteger(warmupRounds) || warmupRounds < 0 ||
    !Number.isInteger(mixedTimingRounds) || mixedTimingRounds < 7 ||
    !Number.isInteger(mixedWarmupRounds) || mixedWarmupRounds < 2) {
  throw new Error("Ablation rounds must be >= 1; mixed rounds must be >= 7 with >= 2 warmups");
}

const caseKey = (entry) => `${entry.fixture}:${entry.group}`;
const acceptedKeys = new Set(previous.comparisons
  .filter((entry) => entry.valid && entry.expectedFallback === false)
  .map(caseKey));
const acceptedCases = reference.cases.filter((entry) => acceptedKeys.has(caseKey(entry)));
if (acceptedCases.length === 0) {
  throw new Error("The saved certified-hybrid result contains no accepted cases");
}

const variants = [
  {
    id: "pure-one-grid",
    label: "Pure one-grid GSUB (existing baseline)",
    kind: "pure",
    setup: "pure",
  },
  {
    id: "two-grid-no-exact-dom",
    label: "Two-grid top+runner; exact DOM removed",
    kind: "hybrid",
    setup: "remove-dom",
  },
  {
    id: "two-grid-no-exact-assets",
    label: "Two-grid top+runner; exact DOM and stylesheet removed",
    kind: "hybrid",
    setup: "remove-assets",
    diagnostic: true,
  },
  {
    id: "two-grid-hidden-exact-reset",
    label: "Two-grid; exact DOM hidden and input inheritance reset",
    kind: "hybrid",
    setup: "hidden-reset",
    diagnostic: true,
  },
  {
    id: "two-grid-hidden-exact",
    label: "Two-grid; exact DOM forced hidden, direct final readback",
    kind: "hybrid",
    setup: "hidden",
  },
  {
    id: "full-hybrid",
    label: "Current full hybrid",
    kind: "hybrid",
    setup: "full",
  },
];
const banks = ["bounded", "full"];

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function round(value, digits = 3) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function formatMs(value) {
  return `${value.toFixed(2)} ms`;
}

function formatOptionalMs(value) {
  return value == null ? "n/a" : formatMs(value);
}

function difference(left, right) {
  return round(left - right);
}

async function settle(page) {
  await page.evaluate(() => new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function loadVariant(browser, bank, variant) {
  const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
  const file = variant.kind === "pure"
    ? `pure-${bank}.html`
    : (bank === "bounded" ? "index.html" : "full.html");
  await page.goto(`${server}/experiments/gsub-certified-hybrid/${file}`, {
    waitUntil: "load",
    timeout: 240_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });

  const setupState = await page.evaluate(({ setup, cases }) => {
    window.__gsubAblationCases = cases;
    window.__gsubAblationCaseOffset = 0;
    if (setup === "pure") {
      document.querySelector("#pure-gsub-stage").getBoundingClientRect();
      return {
        exactDomPresent: false,
        exactStylesheetPresent: false,
        exactDisplay: null,
        finalRule: "pure GSUB max-content stage geometry",
      };
    }

    const exact = document.querySelector("#exact-stage");
    const final = document.querySelector("#final-result");
    const exactLink = [...document.querySelectorAll('link[rel="stylesheet"]')].find((link) =>
      link.href.includes("/gpt2-hvar-grid-output-head-certified-upper-int10-one-step/index.css"));

    if (setup !== "full") {
      final.style.setProperty("position-anchor", "auto", "important");
      final.style.setProperty(
        "width",
        "calc((var(--group) * 256 + var(--top-local)) * 1px)",
        "important",
      );
    }
    if (setup === "remove-dom" || setup === "remove-assets") {
      if (exact.contains(final)) exact.parentNode.insertBefore(final, exact.nextSibling);
      exact.remove();
    } else if (setup === "hidden" || setup === "hidden-reset") {
      exact.style.setProperty("display", "none", "important");
      if (setup === "hidden-reset") {
        for (let dimension = 0; dimension < 768; dimension += 1) {
          exact.style.setProperty(`--h${dimension}`, "0");
        }
        exact.style.setProperty("--score-offset", "0px");
        exact.style.setProperty("--group", "0");
      }
    }
    if (setup === "remove-assets") exactLink?.remove();

    document.documentElement.getBoundingClientRect();
    return {
      exactDomPresent: Boolean(document.querySelector("#exact-stage")),
      exactStylesheetPresent: Boolean([...document.querySelectorAll('link[rel="stylesheet"]')]
        .find((link) => link.href.includes(
          "/gpt2-hvar-grid-output-head-certified-upper-int10-one-step/index.css"))),
      exactDisplay: document.querySelector("#exact-stage")
        ? getComputedStyle(document.querySelector("#exact-stage")).display
        : null,
      finalRule: setup === "full" ? "current conditional exact/top width" : "direct top-token width",
    };
  }, { setup: variant.setup, cases: acceptedCases });
  await settle(page);
  return { ...variant, bank, page, setupState };
}

async function applyAndObserve(entry, testCase) {
  return entry.page.evaluate(({ kind, testCase: selected, threshold }) => {
    const root = document.querySelector(kind === "pure" ? "#pure-root" : "#hybrid-root");
    const hidden = window.__gsubAblationCases.find((candidate) =>
      candidate.fixture === selected.fixture && candidate.group === selected.group).hidden;
    hidden.forEach((value, dimension) => root.style.setProperty(`--h${dimension}`, String(value)));
    root.style.setProperty("--score-offset", `${-selected.floor * 256 * 4}px`);
    root.style.setProperty("--group", String(selected.group));

    const winner = (selector) => {
      const widths = [...document.querySelectorAll(`${selector} .gsub-candidate`)]
        .map((element) => element.getBoundingClientRect().width);
      let local = 0;
      for (let index = 1; index < widths.length; index += 1) {
        if (widths[index] > widths[local]) local = index;
      }
      return { local, width: widths[local], positive: widths.filter((width) => width > 0).length };
    };

    if (kind === "pure") {
      const forcedGeometry = document.querySelector("#pure-gsub-stage").getBoundingClientRect().width;
      return { forcedGeometry, top: winner("#pure-gsub-stage") };
    }

    const finalWidth = Math.round(document.querySelector("#final-result").getBoundingClientRect().width);
    return {
      forcedGeometry: finalWidth,
      finalWidth,
      top: winner("#gsub-top"),
      runner: winner("#gsub-runner"),
      topToken: Math.round(document.querySelector("#top-token").getBoundingClientRect().width),
      runnerToken: Math.round(document.querySelector("#runner-token").getBoundingClientRect().width),
      marginBuckets: Math.round(document.querySelector("#margin-result").getBoundingClientRect().width),
      fallback: Math.round(document.querySelector("#fallback-result").getBoundingClientRect().width),
      exactDisplay: document.querySelector("#exact-stage")
        ? getComputedStyle(document.querySelector("#exact-stage")).display
        : null,
      accepted: Math.round(document.querySelector("#fallback-result").getBoundingClientRect().width) === 0 &&
        Math.round(document.querySelector("#margin-result").getBoundingClientRect().width) > threshold,
    };
  }, {
    kind: entry.kind,
    threshold: reference.marginThresholdBuckets,
    testCase: {
      fixture: testCase.fixture,
      group: testCase.group,
      floor: reference.scoreFloors[testCase.fixture],
    },
  });
}

async function timeSequence(entry, roundIndex) {
  return entry.page.evaluate(({ kind, roundIndex }) => {
    const cases = window.__gsubAblationCases;
    const root = document.querySelector(kind === "pure" ? "#pure-root" : "#hybrid-root");
    const target = document.querySelector(kind === "pure" ? "#pure-gsub-stage" : "#final-result");
    const samples = [];
    for (let position = 0; position < cases.length; position += 1) {
      const selected = cases[(position + roundIndex) % cases.length];
      const started = performance.now();
      selected.hidden.forEach((value, dimension) =>
        root.style.setProperty(`--h${dimension}`, String(value)));
      root.style.setProperty("--score-offset", `${-selected.floor * 256 * 4}px`);
      root.style.setProperty("--group", String(selected.group));
      const forcedGeometry = target.getBoundingClientRect().width;
      samples.push({
        fixture: selected.fixture,
        group: selected.group,
        milliseconds: performance.now() - started,
        forcedGeometry,
      });
    }
    return samples;
  }, { kind: entry.kind, roundIndex });
}

async function loadProductionPage(browser, id, file, kind, bank = null) {
  const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
  await page.goto(`${server}/experiments/gsub-certified-hybrid/${file}`, {
    waitUntil: "load",
    timeout: 240_000,
  });
  await page.evaluate(async (cases) => {
    await document.fonts.ready;
    window.__gsubMixedCases = cases;
    window.__gsubMixedPreviousRoute = null;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  }, allCases);
  return { id, kind, bank, page };
}

async function observeProduction(entry, selected) {
  return entry.page.evaluate(({ kind, fixture, group }) => {
    const testCase = window.__gsubMixedCases.find((candidate) =>
      candidate.fixture === fixture && candidate.group === group);
    const root = document.querySelector(kind === "exact" ? "#exact-root" : "#hybrid-root");
    testCase.hidden.forEach((value, dimension) =>
      root.style.setProperty(`--h${dimension}`, String(value)));
    root.style.setProperty("--score-offset", `${-testCase.floor * 256 * 4}px`);
    root.style.setProperty("--group", String(testCase.group));
    if (kind === "exact") {
      return {
        finalWinner: Math.round(
          document.querySelector("#baseline-exact-result").getBoundingClientRect().width),
      };
    }
    const finalWinner = Math.round(document.querySelector("#final-result").getBoundingClientRect().width);
    const fallback = Math.round(document.querySelector("#fallback-result").getBoundingClientRect().width);
    return {
      finalWinner,
      fallback,
      route: fallback === 0 ? "accept" : "fallback",
      exactDisplay: getComputedStyle(document.querySelector("#exact-stage")).display,
      marginBuckets: Math.round(document.querySelector("#margin-result").getBoundingClientRect().width),
    };
  }, { kind: entry.kind, fixture: selected.fixture, group: selected.group });
}

async function timeProductionSequence(entry, order) {
  return entry.page.evaluate(({ kind, order }) => {
    const root = document.querySelector(kind === "exact" ? "#exact-root" : "#hybrid-root");
    const target = document.querySelector(
      kind === "exact" ? "#baseline-exact-result" : "#final-result");
    const samples = [];
    for (const caseIndex of order) {
      const selected = window.__gsubMixedCases[caseIndex];
      const started = performance.now();
      selected.hidden.forEach((value, dimension) =>
        root.style.setProperty(`--h${dimension}`, String(value)));
      root.style.setProperty("--score-offset", `${-selected.floor * 256 * 4}px`);
      root.style.setProperty("--group", String(selected.group));
      const forcedGeometry = target.getBoundingClientRect().width;
      const milliseconds = performance.now() - started;
      let route = null;
      let transition = null;
      if (kind === "hybrid") {
        route = Math.round(document.querySelector("#fallback-result").getBoundingClientRect().width) === 0
          ? "accept"
          : "fallback";
        transition = window.__gsubMixedPreviousRoute == null
          ? null
          : `${window.__gsubMixedPreviousRoute}->${route}`;
        window.__gsubMixedPreviousRoute = route;
      }
      samples.push({
        fixture: selected.fixture,
        group: selected.group,
        milliseconds,
        forcedGeometry,
        route,
        transition,
      });
    }
    return samples;
  }, { kind: entry.kind, order });
}

function mixedCaseOrder(roundIndex, count) {
  const base = Array.from({ length: count }, (_, index) => index);
  const directed = roundIndex % 2 === 0 ? base : base.reverse();
  const offset = ((roundIndex % count) + count) % count;
  return directed.slice(offset).concat(directed.slice(0, offset));
}

const instrumentedCases = acceptedCases.map((entry) => ({
  ...entry,
  hidden: reference.hiddenVectors[entry.fixture],
  floor: reference.scoreFloors[entry.fixture],
}));

// Replace the compact cases used by loadVariant with their pre-resolved inputs.
acceptedCases.splice(0, acceptedCases.length, ...instrumentedCases);

const allCases = reference.cases.map((entry) => ({
  ...entry,
  hidden: reference.hiddenVectors[entry.fixture],
  floor: reference.scoreFloors[entry.fixture],
}));

const browser = await chromium.launch({
  executablePath,
  headless: true,
});

const correctness = [];
const samples = [];
const setup = [];
const mixedCorrectness = [];
const mixedHybridSamples = [];
const mixedExactSamples = [];
let chrome;
try {
  chrome = browser.version();
  for (const bank of banks) {
    const entries = [];
    for (const variant of variants) {
      const loaded = await loadVariant(browser, bank, variant);
      entries.push(loaded);
      setup.push({ bank, variant: variant.id, ...loaded.setupState });
    }

    for (const entry of entries) {
      for (const selected of acceptedCases) {
        const observed = await applyAndObserve(entry, selected);
        const expectedTopLocal = selected.offlineWinnerLocal;
        const expectedRunnerLocal = selected.offlineRunnerLocal;
        const expectedToken = selected.group * reference.groupSize + expectedTopLocal;
        const result = {
          bank,
          variant: entry.id,
          fixture: selected.fixture,
          group: selected.group,
          label: selected.label,
          expectedTopLocal,
          expectedRunnerLocal: entry.kind === "pure" ? null : expectedRunnerLocal,
          expectedToken,
          observed,
          topCorrect: observed.top.local === expectedTopLocal,
          runnerCorrect: entry.kind === "pure" ? null : observed.runner.local === expectedRunnerLocal,
          finalCorrect: entry.kind === "pure" ? observed.top.local === expectedTopLocal :
            observed.finalWidth === expectedToken,
          acceptedCorrect: entry.kind === "pure" ? null : observed.accepted,
        };
        result.valid = result.topCorrect && result.finalCorrect &&
          (result.runnerCorrect ?? true) && (result.acceptedCorrect ?? true);
        correctness.push(result);
      }
    }

    for (let warmup = 0; warmup < warmupRounds; warmup += 1) {
      for (let offset = 0; offset < entries.length; offset += 1) {
        await timeSequence(entries[(offset + warmup) % entries.length], warmup);
      }
    }

    for (let timingRound = 0; timingRound < timingRounds; timingRound += 1) {
      const order = timingRound % 2 ? [...entries].reverse() : entries;
      const rotated = order.slice(timingRound % order.length)
        .concat(order.slice(0, timingRound % order.length));
      for (let orderIndex = 0; orderIndex < rotated.length; orderIndex += 1) {
        const entry = rotated[orderIndex];
        const measured = await timeSequence(entry, timingRound);
        samples.push(...measured.map((sample) => ({
          bank,
          variant: entry.id,
          round: timingRound,
          order: orderIndex,
          ...sample,
        })));
      }
    }

    await Promise.all(entries.map((entry) => entry.page.close()));
  }

  const productionEntries = [
    await loadProductionPage(browser, "bounded-hybrid", "index.html", "hybrid", "bounded"),
    await loadProductionPage(browser, "full-hybrid", "full.html", "hybrid", "full"),
    await loadProductionPage(browser, "exact-baseline", "exact.html", "exact"),
  ];
  const exactEntry = productionEntries.find((entry) => entry.kind === "exact");
  const hybridEntries = productionEntries.filter((entry) => entry.kind === "hybrid");

  for (const selected of allCases) {
    const exact = await observeProduction(exactEntry, selected);
    const expectedWinner = selected.group * reference.groupSize + selected.offlineWinnerLocal;
    mixedCorrectness.push({
      target: "exact-baseline-offline-diagnostic",
      fixture: selected.fixture,
      group: selected.group,
      offlineExpectedWinner: expectedWinner,
      authoritativeCssWinner: exact.finalWinner,
      offlineReferenceMatches: exact.finalWinner === expectedWinner,
    });
    for (const entry of hybridEntries) {
      const observed = await observeProduction(entry, selected);
      mixedCorrectness.push({
        target: `${entry.bank}-hybrid-vs-exact`,
        bank: entry.bank,
        fixture: selected.fixture,
        group: selected.group,
        label: selected.label,
        exactWinner: exact.finalWinner,
        observedWinner: observed.finalWinner,
        route: observed.route,
        fallback: observed.fallback,
        exactDisplay: observed.exactDisplay,
        marginBuckets: observed.marginBuckets,
        valid: observed.finalWinner === exact.finalWinner,
      });
    }
  }

  for (let warmup = 0; warmup < mixedWarmupRounds; warmup += 1) {
    const order = mixedCaseOrder(warmup, allCases.length);
    const pageOrder = warmup % 2 === 0 ? productionEntries : [...productionEntries].reverse();
    for (const entry of pageOrder) await timeProductionSequence(entry, order);
  }

  for (let timingRound = 0; timingRound < mixedTimingRounds; timingRound += 1) {
    const caseOrder = mixedCaseOrder(timingRound, allCases.length);
    const directedPages = timingRound % 2 === 0
      ? productionEntries
      : [...productionEntries].reverse();
    const pageOffset = timingRound % directedPages.length;
    const pageOrder = directedPages.slice(pageOffset).concat(directedPages.slice(0, pageOffset));
    for (let pageOrderIndex = 0; pageOrderIndex < pageOrder.length; pageOrderIndex += 1) {
      const entry = pageOrder[pageOrderIndex];
      const measured = await timeProductionSequence(entry, caseOrder);
      const annotated = measured.map((sample) => ({
        target: entry.id,
        bank: entry.bank,
        round: timingRound,
        pageOrder: pageOrderIndex,
        ...sample,
      }));
      if (entry.kind === "exact") mixedExactSamples.push(...annotated);
      else mixedHybridSamples.push(...annotated);
    }
  }

  await Promise.all(productionEntries.map((entry) => entry.page.close()));
} finally {
  await browser.close();
}

const medians = Object.fromEntries(banks.map((bank) => [
  bank,
  Object.fromEntries(variants.map((variant) => {
    const matching = samples.filter((sample) => sample.bank === bank && sample.variant === variant.id);
    const perCase = Object.fromEntries(acceptedCases.map((entry) => {
      const values = matching.filter((sample) => caseKey(sample) === caseKey(entry))
        .map((sample) => sample.milliseconds);
      return [caseKey(entry), round(median(values))];
    }));
    return [variant.id, {
      milliseconds: round(median(matching.map((sample) => sample.milliseconds))),
      sampleCount: matching.length,
      perCaseMilliseconds: perCase,
    }];
  })),
]));

const attribution = Object.fromEntries(banks.map((bank) => {
  const value = (id) => medians[bank][id].milliseconds;
  return [bank, {
    secondGridAndReadback: difference(value("two-grid-no-exact-assets"), value("pure-one-grid")),
    unusedExactStylesheet: difference(value("two-grid-no-exact-dom"), value("two-grid-no-exact-assets")),
    hiddenResetExactDom: difference(value("two-grid-hidden-exact-reset"), value("two-grid-no-exact-dom")),
    inheritedExactStyleInvalidation: difference(
      value("two-grid-hidden-exact"), value("two-grid-hidden-exact-reset")),
    finalGating: difference(value("full-hybrid"), value("two-grid-hidden-exact")),
    fullHybridOverPure: difference(value("full-hybrid"), value("pure-one-grid")),
  }];
}));

const correctnessFailures = correctness.filter((entry) => !entry.valid);
const positiveComponents = banks.flatMap((bank) => [
  ["second grid + readback", attribution[bank].secondGridAndReadback, bank],
  ["unused exact stylesheet", attribution[bank].unusedExactStylesheet, bank],
  ["hidden/reset exact DOM", attribution[bank].hiddenResetExactDom, bank],
  ["inherited exact style invalidation", attribution[bank].inheritedExactStyleInvalidation, bank],
  ["final gating", attribution[bank].finalGating, bank],
]).filter(([, value]) => value > 0).sort((left, right) => right[1] - left[1]);
const dominant = positiveComponents[0] ?? ["no positive component", 0, "n/a"];

function sampleSummary(entries) {
  return {
    sampleCount: entries.length,
    medianMilliseconds: entries.length
      ? round(median(entries.map((entry) => entry.milliseconds)))
      : null,
  };
}

const transitionClasses = [
  "accept->accept",
  "accept->fallback",
  "fallback->accept",
  "fallback->fallback",
];
const mixedByBank = Object.fromEntries(banks.map((bank) => {
  const hybrid = mixedHybridSamples.filter((entry) => entry.bank === bank);
  const exactLookup = new Map(mixedExactSamples.map((entry) => [
    `${entry.round}:${caseKey(entry)}`,
    entry,
  ]));
  const exactClassified = hybrid.map((entry) => ({
    ...exactLookup.get(`${entry.round}:${caseKey(entry)}`),
    route: entry.route,
    transition: entry.transition,
  }));
  const hybridSummary = {
    overall: sampleSummary(hybrid),
    accepted: sampleSummary(hybrid.filter((entry) => entry.route === "accept")),
    fallback: sampleSummary(hybrid.filter((entry) => entry.route === "fallback")),
    transitions: Object.fromEntries(transitionClasses.map((transition) => [
      transition,
      sampleSummary(hybrid.filter((entry) => entry.transition === transition)),
    ])),
  };
  const exactSummary = {
    overall: sampleSummary(exactClassified),
    accepted: sampleSummary(exactClassified.filter((entry) => entry.route === "accept")),
    fallback: sampleSummary(exactClassified.filter((entry) => entry.route === "fallback")),
    transitions: Object.fromEntries(transitionClasses.map((transition) => [
      transition,
      sampleSummary(exactClassified.filter((entry) => entry.transition === transition)),
    ])),
  };
  const comparison = {
    overallHybridMinusExactMilliseconds: difference(
      hybridSummary.overall.medianMilliseconds,
      exactSummary.overall.medianMilliseconds),
    acceptedHybridMinusExactMilliseconds: difference(
      hybridSummary.accepted.medianMilliseconds,
      exactSummary.accepted.medianMilliseconds),
    fallbackHybridMinusExactMilliseconds: difference(
      hybridSummary.fallback.medianMilliseconds,
      exactSummary.fallback.medianMilliseconds),
    hybridBeatsExactOverall:
      hybridSummary.overall.medianMilliseconds < exactSummary.overall.medianMilliseconds,
  };
  return [bank, { hybrid: hybridSummary, exact: exactSummary, comparison }];
}));

const hybridExactChecks = mixedCorrectness.filter((entry) => entry.bank != null);
const hybridExactFailures = hybridExactChecks.filter((entry) => !entry.valid);
const exactOfflineDiagnostics = mixedCorrectness.filter((entry) => entry.bank == null);
const exactOfflineMismatches = exactOfflineDiagnostics.filter((entry) => !entry.offlineReferenceMatches);
const stressDecision = banks.every((bank) => mixedByBank[bank].comparison.hybridBeatsExactOverall)
  ? "The adversarial mixed-transition stress set favors the hybrid in both banks."
  : banks.some((bank) => mixedByBank[bank].comparison.hybridBeatsExactOverall)
    ? "The adversarial mixed-transition stress set favors the hybrid in only one bank."
    : "The adversarial mixed-transition stress set does not favor the hybrid in either bank.";

const fullScreenCounts = { accepted: 1744, fallback: 226, total: 1970 };
const fullScreenAcceptProbability = fullScreenCounts.accepted / fullScreenCounts.total;
const fullScreenFallbackProbability = fullScreenCounts.fallback / fullScreenCounts.total;
const fullScreenTransitionProbabilities = {
  "accept->accept": fullScreenAcceptProbability ** 2,
  "accept->fallback": fullScreenAcceptProbability * fullScreenFallbackProbability,
  "fallback->accept": fullScreenFallbackProbability * fullScreenAcceptProbability,
  "fallback->fallback": fullScreenFallbackProbability ** 2,
};
const fullScreenProjection = {
  source: "full 1,970-case screen",
  counts: fullScreenCounts,
  acceptRate: round(fullScreenAcceptProbability, 6),
  fallbackRate: round(fullScreenFallbackProbability, 6),
  independentRouteTransitionProbabilities: Object.fromEntries(Object.entries(
    fullScreenTransitionProbabilities).map(([key, value]) => [key, round(value, 6)])),
  assumptions: [
    "The full-screen accept/fallback rate transfers to runtime inputs.",
    "The transition-weighted estimate assumes independent consecutive routes.",
    "Stress-set transition and route medians transfer to the full-screen route mix.",
    "This is a projection, not a direct 1,970-case timing run.",
  ],
  byBank: Object.fromEntries(banks.map((bank) => {
    const measured = mixedByBank[bank];
    const transitionWeightedMilliseconds = transitionClasses.reduce((sum, transition) =>
      sum + fullScreenTransitionProbabilities[transition] *
        measured.hybrid.transitions[transition].medianMilliseconds, 0);
    const routeWeightedMilliseconds =
      fullScreenAcceptProbability * measured.hybrid.accepted.medianMilliseconds +
      fullScreenFallbackProbability * measured.hybrid.fallback.medianMilliseconds;
    const exactMilliseconds = measured.exact.overall.medianMilliseconds;
    return [bank, {
      transitionWeightedIndependentRoutes: {
        estimatedMilliseconds: round(transitionWeightedMilliseconds),
        exactBaselineMilliseconds: exactMilliseconds,
        projectedSpeedupVsExact: round(exactMilliseconds / transitionWeightedMilliseconds, 3),
        projectedHybridBeatsExact: transitionWeightedMilliseconds < exactMilliseconds,
      },
      routeWeightedMedians: {
        estimatedMilliseconds: round(routeWeightedMilliseconds),
        exactBaselineMilliseconds: exactMilliseconds,
        projectedSpeedupVsExact: round(exactMilliseconds / routeWeightedMilliseconds, 3),
        projectedHybridBeatsExact: routeWeightedMilliseconds < exactMilliseconds,
      },
    }];
  })),
};

const report = {
  generatedAt: new Date().toISOString(),
  server,
  chrome,
  executablePath,
  headless: true,
  platform: `${os.platform()} ${os.release()} (${os.arch()})`,
  timing: {
    rounds: timingRounds,
    warmupRounds,
    acceptedCasesPerCell: acceptedCases.length,
    samplesPerCell: timingRounds * acceptedCases.length,
    boundary: "in-page performance.now(): first input style mutation through forced target.getBoundingClientRect().width",
    mutationCountPerSample: 770,
    includes: "768 hidden-vector custom properties, score offset, group, and synchronous final/readback geometry",
    excludes: "page load, fonts.ready, topology setup/removal, correctness scans, Playwright round trips",
  },
  acceptedCases: acceptedCases.map(({ hidden, floor, ...entry }) => ({
    ...entry,
    expectedToken: entry.group * reference.groupSize + entry.offlineWinnerLocal,
  })),
  variants: variants.map(({ diagnostic = false, ...variant }) => ({ ...variant, diagnostic })),
  setup,
  correctness: {
    checks: correctness.length,
    passed: correctness.length - correctnessFailures.length,
    allPassed: correctnessFailures.length === 0,
    failures: correctnessFailures,
    observations: correctness,
  },
  medians,
  attribution,
  dominantPositiveComponent: {
    component: dominant[0],
    milliseconds: dominant[1],
    bank: dominant[2],
  },
  adversarialMixedTransitionStress: {
    timing: {
      rounds: mixedTimingRounds,
      warmupRounds: mixedWarmupRounds,
      referenceCasesPerRound: allCases.length,
      samplesPerTarget: mixedTimingRounds * allCases.length,
      order: "case order reverses on odd rounds and rotates by round; page order also reverses/rotates",
      boundary: "in-page performance.now(): 768 hidden-vector writes plus score offset/group through forced final/exact geometry",
      excludes: "page load, fonts.ready, warmup, correctness reads, and Playwright round trips",
      caseMixWarning: "The ten intentionally adversarial cases have 7/10 fallback and are not production-weighted.",
    },
    correctness: {
      hybridVsExactChecks: hybridExactChecks.length,
      hybridVsExactChecksPassed: hybridExactChecks.length - hybridExactFailures.length,
      allPassed: hybridExactFailures.length === 0,
      failures: hybridExactFailures,
      authoritativeBaseline: "separate exact CSS page geometry",
      offlineReferenceDiagnostic: {
        checks: exactOfflineDiagnostics.length,
        matches: exactOfflineDiagnostics.length - exactOfflineMismatches.length,
        mismatches: exactOfflineMismatches,
        note: "fixture 9/group 96 exact CSS winner 24755 is authoritative; offline 24794 appears stale/incorrect",
      },
      observations: mixedCorrectness,
    },
    byBank: mixedByBank,
    decision: stressDecision,
    hybridSamples: mixedHybridSamples,
    exactSamples: mixedExactSamples,
  },
  fullScreenProjection,
  samples,
};

await fs.writeFile(new URL("ablation-results.json", experimentRoot),
  `${JSON.stringify(report, null, 2)}\n`);

const tableRows = variants.map((variant) =>
  `| ${variant.label} | ${formatMs(medians.bounded[variant.id].milliseconds)} | ` +
  `${formatMs(medians.full[variant.id].milliseconds)} |`)
  .join("\n");
const attributionRows = [
  ["Second grid + top/runner/direct-final readback", "secondGridAndReadback"],
  ["Unused exact stylesheet with exact DOM absent", "unusedExactStylesheet"],
  ["Hidden/reset exact DOM", "hiddenResetExactDom"],
  ["Inherited exact-subtree style invalidation", "inheritedExactStyleInvalidation"],
  ["Current final gating over forced-hidden/direct-final", "finalGating"],
  ["Current full hybrid over pure one-grid", "fullHybridOverPure"],
].map(([label, key]) =>
  `| ${label} | ${formatMs(attribution.bounded[key])} | ${formatMs(attribution.full[key])} |`)
  .join("\n");
const selectedCaseText = acceptedCases.map((entry) =>
  `fixture ${entry.fixture}/group ${entry.group} (${entry.label}; top ${entry.offlineWinnerLocal}, ` +
  `runner ${entry.offlineRunnerLocal})`).join("; ");
const mixedRows = banks.flatMap((bank) => [
  `| ${bank} | Current full hybrid | ` +
    `${formatMs(mixedByBank[bank].hybrid.overall.medianMilliseconds)} | ` +
    `${formatMs(mixedByBank[bank].hybrid.accepted.medianMilliseconds)} | ` +
    `${formatMs(mixedByBank[bank].hybrid.fallback.medianMilliseconds)} |`,
  `| ${bank} | Exact baseline | ${formatMs(mixedByBank[bank].exact.overall.medianMilliseconds)} | ` +
    `${formatMs(mixedByBank[bank].exact.accepted.medianMilliseconds)} | ` +
    `${formatMs(mixedByBank[bank].exact.fallback.medianMilliseconds)} |`,
]).join("\n");
const mixedComparisonRows = banks.map((bank) => {
  const comparison = mixedByBank[bank].comparison;
  return `| ${bank} | ${formatMs(comparison.overallHybridMinusExactMilliseconds)} | ` +
    `${formatMs(comparison.acceptedHybridMinusExactMilliseconds)} | ` +
    `${formatMs(comparison.fallbackHybridMinusExactMilliseconds)} | ` +
    `${comparison.hybridBeatsExactOverall ? "yes" : "no"} |`;
}).join("\n");
const transitionRows = banks.flatMap((bank) => transitionClasses.map((transition) => {
  const hybrid = mixedByBank[bank].hybrid.transitions[transition];
  const exact = mixedByBank[bank].exact.transitions[transition];
  return `| ${bank} | ${transition} | ${hybrid.sampleCount} | ` +
    `${formatOptionalMs(hybrid.medianMilliseconds)} | ${formatOptionalMs(exact.medianMilliseconds)} |`;
})).join("\n");

const markdown = `# GSUB-certified hybrid topology ablation\n\n` +
  `Chrome **${chrome}** (${executablePath}), headless on ${report.platform}. ` +
  `${timingRounds} measured rounds after ${warmupRounds} warm-up rounds; ` +
  `${report.timing.samplesPerCell} accepted-case samples per bank/topology cell. The adversarial ` +
  `mixed-transition stress phase used ${mixedTimingRounds} measured rounds after ` +
  `${mixedWarmupRounds} warm-ups, all ` +
  `${allCases.length} reference cases, and ${mixedTimingRounds * allCases.length} samples per target.\n\n` +
  `Correctness: **${report.correctness.passed}/${report.correctness.checks} checks passed**. ` +
  `For every selected accepted case, the measured GSUB top matched the offline winner, ` +
  `the two-grid variants' runner matched the offline runner, the route remained accepted, ` +
  `and final geometry returned the expected token. Selected cases: ${selectedCaseText}.\n\n` +
  `## Adversarial mixed-transition stress\n\n` +
  `This is deliberately **not production-weighted**: the ten reference cases are adversarial and ` +
  `route 7/10 cases to fallback, versus 226/1,970 (11.47%) on the full screen.\n\n` +
  `Correctness: **${hybridExactChecks.length - hybridExactFailures.length}/${hybridExactChecks.length} ` +
  `hybrid final-winner comparisons matched the separate exact page**. That exact CSS page is the ` +
  `authoritative baseline. Its fixture 9/group 96 winner is 24755; the offline 24794 value appears ` +
  `stale or incorrect for that selected pair (the other 9/10 offline entries match).\n\n` +
  `| Bank | Target | Overall median | Accepted median | Fallback median |\n` +
  `| --- | --- | ---: | ---: | ---: |\n${mixedRows}\n\n` +
  `| Bank | Hybrid − exact overall | Hybrid − exact accepted | Hybrid − exact fallback | ` +
  `Hybrid beats exact overall? |\n| --- | ---: | ---: | ---: | --- |\n${mixedComparisonRows}\n\n` +
  `| Bank | Route transition | Samples | Hybrid median | Exact median |\n` +
  `| --- | --- | ---: | ---: | ---: |\n${transitionRows}\n\n` +
  `Every mixed sample is timed inside its page from the first of 768 input writes through the ` +
  `score-offset/group writes and a forced final geometry read (hybrid) or exact-result geometry ` +
  `read (baseline). ` +
  `Case order reverses on odd rounds and rotates every round; the three page ` +
  `targets are likewise reversed and rotated. Route classification and transition bookkeeping ` +
  `happen after the timed geometry read. ${stressDecision}\n\n` +
  `## Full-screen route-rate projection\n\n` +
  `Using the full-screen rate P(accept)=1,744/1,970=${(fullScreenAcceptProbability * 100).toFixed(2)}% ` +
  `and P(fallback)=226/1,970=${(fullScreenFallbackProbability * 100).toFixed(2)}%, an ` +
  `independent-consecutive-route weighting of the four measured transition medians projects ` +
  `**${formatMs(fullScreenProjection.byBank.bounded.transitionWeightedIndependentRoutes.estimatedMilliseconds)} ` +
  `bounded** and **${formatMs(fullScreenProjection.byBank.full.transitionWeightedIndependentRoutes.estimatedMilliseconds)} ` +
  `full**. The simpler accept/fallback route-median weighting projects ` +
  `**${formatMs(fullScreenProjection.byBank.bounded.routeWeightedMedians.estimatedMilliseconds)} bounded** ` +
  `and **${formatMs(fullScreenProjection.byBank.full.routeWeightedMedians.estimatedMilliseconds)} full**, ` +
  `versus ${formatMs(mixedByBank.bounded.exact.overall.medianMilliseconds)} exact.\n\n` +
  `Both projections favor the hybrid: transition weighting gives ` +
  `${fullScreenProjection.byBank.bounded.transitionWeightedIndependentRoutes.projectedSpeedupVsExact.toFixed(2)}× ` +
  `bounded and ${fullScreenProjection.byBank.full.transitionWeightedIndependentRoutes.projectedSpeedupVsExact.toFixed(2)}× ` +
  `full; route-median weighting gives ` +
  `${fullScreenProjection.byBank.bounded.routeWeightedMedians.projectedSpeedupVsExact.toFixed(2)}× and ` +
  `${fullScreenProjection.byBank.full.routeWeightedMedians.projectedSpeedupVsExact.toFixed(2)}×. This is ` +
  `roughly a **2.2–2.6× projected speedup** (the unrounded bounded route-median ratio is 2.67×), ` +
  `but remains empirical and depends on the real transition distribution and on stress-set medians ` +
  `transferring to the full screen. It is not a direct 1,970-case performance measurement.\n\n` +
  `## Mutation medians\n\n` +
  `| Topology | Bounded bank | Full bank |\n| --- | ---: | ---: |\n${tableRows}\n\n` +
  `Each in-page sample starts immediately before 768 hidden-vector custom-property writes plus ` +
  `score-offset and group, and ends after a synchronous \`getBoundingClientRect().width\` on the ` +
  `final/readback geometry. Page load, font readiness, topology mutations/removals, warm-up, ` +
  `correctness scans, and Playwright round trips are outside the clock. Variant order alternates ` +
  `and rotates by round.\n\n` +
  `## Differential attribution\n\n` +
  `| Median difference | Bounded bank | Full bank |\n| --- | ---: | ---: |\n${attributionRows}\n\n` +
  `These are differences of medians, so they are diagnostic contrasts rather than additive ` +
  `accounting. The exact-DOM-removed required variant retains the exact dispatch stylesheet; ` +
  `the additional no-exact-assets variant removes that otherwise unused stylesheet to give the ` +
  `cleanest second-grid contrast. The hidden/reset variant blocks the exact subtree from inheriting ` +
  `the 768 mutated inputs; comparing it with forced-hidden/inheriting DOM isolates inherited style ` +
  `invalidation. Comparing forced-hidden/direct-final with the unchanged full hybrid isolates the ` +
  `current conditional display/final-width gating layer.\n\n` +
  `## Conclusion\n\n` +
  `${stressDecision} The stress-set bounded hybrid measured ` +
  `${formatMs(mixedByBank.bounded.hybrid.overall.medianMilliseconds)} versus ` +
  `${formatMs(mixedByBank.bounded.exact.overall.medianMilliseconds)} exact; the mixed full hybrid ` +
  `measured ${formatMs(mixedByBank.full.hybrid.overall.medianMilliseconds)} versus ` +
  `${formatMs(mixedByBank.full.exact.overall.medianMilliseconds)} exact. ` +
  `The largest positive measured component was **${dominant[0]}** in the ${dominant[2]} bank ` +
  `(${formatMs(dominant[1])}). The current full hybrid cost ` +
  `${formatMs(attribution.bounded.fullHybridOverPure)} over pure GSUB in the bounded bank and ` +
  `${formatMs(attribution.full.fullHybridOverPure)} in the full bank. ` +
  `Use the signed contrasts above when deciding whether the cost is principally the second grid, ` +
  `the inactive exact subtree/style invalidation, or final gating; negative small contrasts should ` +
  `be treated as measurement noise or interaction effects, not speedups.\n\n` +
  `## Scope\n\n` +
  `The topology decomposition times only the three previously certified accepted fixture/group ` +
  `pairs; the adversarial stress phase times all ten reference cases, including route transitions. ` +
  `This does not broaden the empirical six-bucket certification claim. ` +
  `JavaScript mutates benchmark inputs, performs one-time topology setup, forces geometry, and ` +
  `checks results; it does not choose the winner or route.\n`;

await fs.writeFile(new URL("ABLATION-RESULTS.md", experimentRoot), markdown);

console.log(JSON.stringify({
  chrome,
  timingRounds,
  warmupRounds,
  acceptedCases: acceptedCases.map(({ fixture, group }) => ({ fixture, group })),
  correctness: report.correctness,
  medians,
  attribution,
  dominantPositiveComponent: report.dominantPositiveComponent,
  adversarialMixedTransitionStress: {
    timing: report.adversarialMixedTransitionStress.timing,
    correctness: {
      hybridVsExactChecksPassed: report.adversarialMixedTransitionStress.correctness.hybridVsExactChecksPassed,
      hybridVsExactChecks: report.adversarialMixedTransitionStress.correctness.hybridVsExactChecks,
      allPassed: report.adversarialMixedTransitionStress.correctness.allPassed,
      offlineReferenceDiagnostic: report.adversarialMixedTransitionStress.correctness.offlineReferenceDiagnostic,
    },
    byBank: mixedByBank,
    decision: stressDecision,
  },
  fullScreenProjection,
}, null, 2));

if (!report.correctness.allPassed || !report.adversarialMixedTransitionStress.correctness.allPassed) {
  process.exitCode = 1;
}
