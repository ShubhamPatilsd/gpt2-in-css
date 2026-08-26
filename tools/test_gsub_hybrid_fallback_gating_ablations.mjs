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
const measuredRounds = Number.parseInt(process.env.GSUB_FALLBACK_GATING_ROUNDS ?? "7", 10);
const warmupRounds = Number.parseInt(process.env.GSUB_FALLBACK_GATING_WARMUPS ?? "2", 10);
const experimentRoot = new URL("../experiments/gsub-certified-hybrid/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", experimentRoot), "utf8"));

if (!Number.isInteger(measuredRounds) || measuredRounds < 7 ||
    !Number.isInteger(warmupRounds) || warmupRounds < 2) {
  throw new Error("Fallback-gating ablation requires >= 7 measured rounds and >= 2 warmups");
}

const banks = ["bounded", "full"];
const transitions = [
  "accept->accept",
  "accept->fallback",
  "fallback->accept",
  "fallback->fallback",
];
const variants = [
  {
    id: "conditional-display",
    label: "Current conditional display:none/grid",
    css: `#exact-stage {
      display: if(style(--fallback:1):grid;else:none) !important;
      content-visibility: visible !important;
      visibility: visible !important;
      contain-intrinsic-size: none !important;
    }`,
    support: [
      ["display", "if(style(--fallback:1):grid;else:none)"],
    ],
    expected: {
      accept: { display: "none", contentVisibility: "visible", visibility: "visible" },
      fallback: { display: "grid", contentVisibility: "visible", visibility: "visible" },
    },
  },
  {
    id: "conditional-content-visibility",
    label: "Conditional content-visibility:hidden/visible; stage stays grid",
    css: `#exact-stage {
      display: grid !important;
      content-visibility: if(style(--fallback:1):visible;else:hidden) !important;
      visibility: visible !important;
      contain-intrinsic-size: auto 1px !important;
    }`,
    support: [
      ["content-visibility", "if(style(--fallback:1):visible;else:hidden)"],
      ["contain-intrinsic-size", "auto 1px"],
    ],
    expected: {
      accept: { display: "grid", contentVisibility: "hidden", visibility: "visible" },
      fallback: { display: "grid", contentVisibility: "visible", visibility: "visible" },
    },
  },
  {
    id: "conditional-visibility",
    label: "Conditional visibility:hidden/visible; stage stays grid",
    css: `#exact-stage {
      display: grid !important;
      content-visibility: visible !important;
      visibility: if(style(--fallback:1):visible;else:hidden) !important;
      contain-intrinsic-size: none !important;
    }`,
    support: [
      ["visibility", "if(style(--fallback:1):visible;else:hidden)"],
    ],
    expected: {
      accept: { display: "grid", contentVisibility: "visible", visibility: "hidden" },
      fallback: { display: "grid", contentVisibility: "visible", visibility: "visible" },
    },
  },
];

const cases = reference.cases.map((entry) => ({
  ...entry,
  hidden: reference.hiddenVectors[entry.fixture],
  floor: reference.scoreFloors[entry.fixture],
}));
const caseKey = (entry) => `${entry.fixture}:${entry.group}`;

function median(values) {
  if (values.length === 0) return null;
  const ordered = [...values].sort((left, right) => left - right);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2
    ? ordered[middle]
    : (ordered[middle - 1] + ordered[middle]) / 2;
}

function round(value, digits = 3) {
  if (value == null) return null;
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function formatMs(value) {
  return value == null ? "n/a" : `${value.toFixed(2)} ms`;
}

function caseOrder(roundIndex, count) {
  const base = Array.from({ length: count }, (_, index) => index);
  const directed = roundIndex % 2 === 0 ? base : base.reverse();
  const offset = roundIndex % count;
  return directed.slice(offset).concat(directed.slice(0, offset));
}

async function settle(page) {
  await page.evaluate(() => new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function loadHybridPage(browser, bank, variant) {
  const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
  const file = bank === "bounded" ? "index.html" : "full.html";
  await page.goto(`${server}/experiments/gsub-certified-hybrid/${file}`, {
    waitUntil: "load",
    timeout: 240_000,
  });
  const setup = await page.evaluate(async ({ css, support, cases: selectedCases }) => {
    await document.fonts.ready;
    const style = document.createElement("style");
    style.dataset.fallbackGatingAblation = "true";
    style.textContent = css;
    document.head.append(style);
    window.__fallbackGatingCases = selectedCases;
    window.__fallbackGatingPreviousRoute = null;
    const supportChecks = support.map(([property, value]) => ({
      property,
      value,
      supported: CSS.supports(property, value),
    }));
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const exact = document.querySelector("#exact-stage");
    const computed = getComputedStyle(exact);
    return {
      supportChecks,
      supportedSyntax: supportChecks.every((check) => check.supported),
      injectedStyleCount: document.querySelectorAll("style[data-fallback-gating-ablation]").length,
      initialComputed: {
        display: computed.display,
        contentVisibility: computed.contentVisibility,
        visibility: computed.visibility,
        containIntrinsicSize: computed.containIntrinsicSize,
      },
    };
  }, { css: variant.css, support: variant.support, cases });
  return { kind: "hybrid", bank, variant, page, setup };
}

async function loadExactPage(browser, bank) {
  const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
  await page.goto(`${server}/experiments/gsub-certified-hybrid/exact.html`, {
    waitUntil: "load",
    timeout: 240_000,
  });
  await page.evaluate(async (selectedCases) => {
    await document.fonts.ready;
    window.__fallbackGatingCases = selectedCases;
    window.__fallbackGatingPreviousRoute = null;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  }, cases);
  return { kind: "exact", bank, id: "exact-baseline", page };
}

async function applyCase(entry, selected) {
  return entry.page.evaluate(({ kind, fixture, group }) => {
    const testCase = window.__fallbackGatingCases.find((candidate) =>
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
    const exactStyle = getComputedStyle(document.querySelector("#exact-stage"));
    return {
      finalWinner,
      fallback,
      route: fallback === 0 ? "accept" : "fallback",
      exactComputed: {
        display: exactStyle.display,
        contentVisibility: exactStyle.contentVisibility,
        visibility: exactStyle.visibility,
        containIntrinsicSize: exactStyle.containIntrinsicSize,
      },
    };
  }, { kind: entry.kind, fixture: selected.fixture, group: selected.group });
}

async function setRoutes(entry, routeByCase) {
  await entry.page.evaluate((routes) => {
    for (const testCase of window.__fallbackGatingCases) {
      testCase.route = routes[`${testCase.fixture}:${testCase.group}`];
    }
    window.__fallbackGatingPreviousRoute = null;
  }, routeByCase);
}

async function timeSequence(entry, order) {
  return entry.page.evaluate(({ kind, order }) => {
    const root = document.querySelector(kind === "exact" ? "#exact-root" : "#hybrid-root");
    const target = document.querySelector(
      kind === "exact" ? "#baseline-exact-result" : "#final-result");
    const samples = [];
    for (const caseIndex of order) {
      const selected = window.__fallbackGatingCases[caseIndex];
      const started = performance.now();
      selected.hidden.forEach((value, dimension) =>
        root.style.setProperty(`--h${dimension}`, String(value)));
      root.style.setProperty("--score-offset", `${-selected.floor * 256 * 4}px`);
      root.style.setProperty("--group", String(selected.group));
      const forcedGeometry = target.getBoundingClientRect().width;
      const milliseconds = performance.now() - started;
      const route = kind === "exact"
        ? selected.route
        : (Math.round(document.querySelector("#fallback-result").getBoundingClientRect().width) === 0
          ? "accept"
          : "fallback");
      const transition = window.__fallbackGatingPreviousRoute == null
        ? null
        : `${window.__fallbackGatingPreviousRoute}->${route}`;
      window.__fallbackGatingPreviousRoute = route;
      samples.push({
        fixture: selected.fixture,
        group: selected.group,
        route,
        transition,
        milliseconds,
        forcedGeometry,
      });
    }
    return samples;
  }, { kind: entry.kind, order });
}

function summarize(samples) {
  const summarizeSubset = (subset) => ({
    sampleCount: subset.length,
    medianMilliseconds: round(median(subset.map((sample) => sample.milliseconds))),
  });
  return {
    overall: summarizeSubset(samples),
    accept: summarizeSubset(samples.filter((sample) => sample.route === "accept")),
    fallback: summarizeSubset(samples.filter((sample) => sample.route === "fallback")),
    transitions: Object.fromEntries(transitions.map((transition) => [
      transition,
      summarizeSubset(samples.filter((sample) => sample.transition === transition)),
    ])),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
const setup = [];
const correctness = [];
const rejections = [];
const samples = [];
let chrome;
try {
  chrome = browser.version();
  for (const bank of banks) {
    const hybridEntries = [];
    for (const variant of variants) {
      const entry = await loadHybridPage(browser, bank, variant);
      hybridEntries.push(entry);
      setup.push({ bank, variant: variant.id, ...entry.setup });
    }
    const exactEntry = await loadExactPage(browser, bank);

    const exactByCase = {};
    for (const selected of cases) {
      exactByCase[caseKey(selected)] = (await applyCase(exactEntry, selected)).finalWinner;
    }

    const currentEntry = hybridEntries.find((entry) => entry.variant.id === "conditional-display");
    const routeByCase = {};
    for (const selected of cases) {
      routeByCase[caseKey(selected)] = (await applyCase(currentEntry, selected)).route;
    }

    for (const entry of hybridEntries) {
      for (const selected of cases) {
        const observed = await applyCase(entry, selected);
        const expectedStyle = entry.variant.expected[observed.route];
        const styleMatches = Object.entries(expectedStyle).every(
          ([property, value]) => observed.exactComputed[property] === value);
        correctness.push({
          bank,
          variant: entry.variant.id,
          fixture: selected.fixture,
          group: selected.group,
          label: selected.label,
          route: observed.route,
          expectedRoute: routeByCase[caseKey(selected)],
          exactWinner: exactByCase[caseKey(selected)],
          observedWinner: observed.finalWinner,
          finalWinnerMatchesExact: observed.finalWinner === exactByCase[caseKey(selected)],
          routeMatchesCurrent: observed.route === routeByCase[caseKey(selected)],
          computedGateMatchesRoute: styleMatches,
          observed,
          valid: observed.finalWinner === exactByCase[caseKey(selected)] &&
            observed.route === routeByCase[caseKey(selected)] && styleMatches,
        });
      }
    }

    for (const entry of hybridEntries) {
      const failures = correctness.filter((check) =>
        check.bank === bank && check.variant === entry.variant.id && !check.valid);
      const reasons = [];
      if (!entry.setup.supportedSyntax) {
        const unsupported = entry.setup.supportChecks.filter((check) => !check.supported)
          .map((check) => `${check.property}: ${check.value}`);
        reasons.push(`unsupported CSS syntax: ${unsupported.join(", ")}`);
      }
      if (entry.setup.injectedStyleCount !== 1) {
        reasons.push(`expected one injected stylesheet, observed ${entry.setup.injectedStyleCount}`);
      }
      if (failures.length > 0) {
        reasons.push(`${failures.length}/${cases.length} correctness/gate-state checks failed`);
      }
      entry.accepted = reasons.length === 0;
      if (!entry.accepted) {
        rejections.push({ bank, variant: entry.variant.id, reasons, failures });
      }
    }

    const timingEntries = [exactEntry, ...hybridEntries.filter((entry) => entry.accepted)];
    for (const entry of timingEntries) await setRoutes(entry, routeByCase);

    for (let warmup = 0; warmup < warmupRounds; warmup += 1) {
      const order = caseOrder(warmup, cases.length);
      const directed = warmup % 2 === 0 ? timingEntries : [...timingEntries].reverse();
      const offset = warmup % directed.length;
      const targetOrder = directed.slice(offset).concat(directed.slice(0, offset));
      for (const entry of targetOrder) await timeSequence(entry, order);
    }

    for (let measuredRound = 0; measuredRound < measuredRounds; measuredRound += 1) {
      const order = caseOrder(measuredRound, cases.length);
      const directed = measuredRound % 2 === 0 ? timingEntries : [...timingEntries].reverse();
      const offset = measuredRound % directed.length;
      const targetOrder = directed.slice(offset).concat(directed.slice(0, offset));
      for (let targetOrderIndex = 0; targetOrderIndex < targetOrder.length; targetOrderIndex += 1) {
        const entry = targetOrder[targetOrderIndex];
        const measured = await timeSequence(entry, order);
        samples.push(...measured.map((sample) => ({
          bank,
          target: entry.kind === "exact" ? entry.id : entry.variant.id,
          kind: entry.kind,
          round: measuredRound,
          targetOrder: targetOrderIndex,
          ...sample,
        })));
      }
    }

    await Promise.all([...hybridEntries, exactEntry].map((entry) => entry.page.close()));
  }
} finally {
  await browser.close();
}

const acceptedVariants = Object.fromEntries(banks.map((bank) => [
  bank,
  variants.filter((variant) => !rejections.some((rejection) =>
    rejection.bank === bank && rejection.variant === variant.id)).map((variant) => variant.id),
]));
const summaries = Object.fromEntries(banks.map((bank) => {
  const targets = ["exact-baseline", ...acceptedVariants[bank]];
  return [bank, Object.fromEntries(targets.map((target) => [
    target,
    summarize(samples.filter((sample) => sample.bank === bank && sample.target === target)),
  ]))];
}));

const fullScreenCounts = { accept: 1744, fallback: 226, total: 1970 };
const acceptProbability = fullScreenCounts.accept / fullScreenCounts.total;
const fallbackProbability = fullScreenCounts.fallback / fullScreenCounts.total;
const transitionProbabilities = {
  "accept->accept": acceptProbability ** 2,
  "accept->fallback": acceptProbability * fallbackProbability,
  "fallback->accept": fallbackProbability * acceptProbability,
  "fallback->fallback": fallbackProbability ** 2,
};
const projection = {
  source: "full 1,970-case screen",
  counts: fullScreenCounts,
  acceptRate: round(acceptProbability, 6),
  fallbackRate: round(fallbackProbability, 6),
  assumption: "Consecutive routes are independent and measured transition medians transfer to the full-screen route mix.",
  transitionProbabilities: Object.fromEntries(Object.entries(transitionProbabilities)
    .map(([transition, probability]) => [transition, round(probability, 6)])),
  byBank: Object.fromEntries(banks.map((bank) => [
    bank,
    Object.fromEntries(acceptedVariants[bank].map((variant) => {
      const estimatedMilliseconds = transitions.reduce((total, transition) =>
        total + transitionProbabilities[transition] *
          summaries[bank][variant].transitions[transition].medianMilliseconds, 0);
      const exactMilliseconds = summaries[bank]["exact-baseline"].overall.medianMilliseconds;
      return [variant, {
        estimatedMilliseconds: round(estimatedMilliseconds),
        exactBaselineMilliseconds: exactMilliseconds,
        projectedSpeedupVsExact: round(exactMilliseconds / estimatedMilliseconds),
      }];
    })),
  ])),
};

const correctnessFailures = correctness.filter((check) => !check.valid);
const report = {
  generatedAt: new Date().toISOString(),
  server,
  chrome,
  executablePath,
  headless: true,
  platform: `${os.platform()} ${os.release()} (${os.arch()})`,
  timing: {
    warmupRounds,
    measuredRounds,
    casesPerRound: cases.length,
    samplesPerAcceptedCell: measuredRounds * cases.length,
    order: "10-case order reverses on odd rounds and rotates by round; target order also reverses and rotates",
    boundary: "in-page performance.now(): first of 768 input custom-property writes through score-offset/group writes and forced final/exact geometry",
    excludes: "page load, fonts.ready, one-time CSS injection, support/correctness checks, route bookkeeping, warmups, and Playwright round trips",
  },
  cssOnlyConstraint: "JavaScript injects each variant stylesheet once before timing and mutates inputs; CSS alone computes route and winner.",
  cases: cases.map(({ hidden, floor, ...entry }) => entry),
  variants,
  setup,
  correctness: {
    checks: correctness.length,
    passed: correctness.length - correctnessFailures.length,
    allAcceptedVariantsPassed: rejections.every((rejection) =>
      rejection.reasons.some((reason) => reason.startsWith("unsupported CSS syntax"))),
    failures: correctnessFailures,
    observations: correctness,
  },
  rejections,
  acceptedVariants,
  summaries,
  fullScreenTransitionProjection: projection,
  samples,
};

await fs.writeFile(new URL("fallback-gating-results.json", experimentRoot),
  `${JSON.stringify(report, null, 2)}\n`);

const summaryRows = banks.flatMap((bank) => [
  `| ${bank} | Exact baseline | ${formatMs(summaries[bank]["exact-baseline"].overall.medianMilliseconds)} | ` +
    `${formatMs(summaries[bank]["exact-baseline"].accept.medianMilliseconds)} | ` +
    `${formatMs(summaries[bank]["exact-baseline"].fallback.medianMilliseconds)} |`,
  ...acceptedVariants[bank].map((variantId) => {
    const variant = variants.find((candidate) => candidate.id === variantId);
    const summary = summaries[bank][variantId];
    return `| ${bank} | ${variant.label} | ${formatMs(summary.overall.medianMilliseconds)} | ` +
      `${formatMs(summary.accept.medianMilliseconds)} | ${formatMs(summary.fallback.medianMilliseconds)} |`;
  }),
]).join("\n");
const transitionRows = banks.flatMap((bank) => acceptedVariants[bank].flatMap((variantId) => {
  const variant = variants.find((candidate) => candidate.id === variantId);
  return transitions.map((transition) => {
    const summary = summaries[bank][variantId].transitions[transition];
    return `| ${bank} | ${variant.label} | ${transition} | ${summary.sampleCount} | ` +
      `${formatMs(summary.medianMilliseconds)} |`;
  });
})).join("\n");
const projectionRows = banks.flatMap((bank) => acceptedVariants[bank].map((variantId) => {
  const variant = variants.find((candidate) => candidate.id === variantId);
  const projected = projection.byBank[bank][variantId];
  return `| ${bank} | ${variant.label} | ${formatMs(projected.estimatedMilliseconds)} | ` +
    `${formatMs(projected.exactBaselineMilliseconds)} | ${projected.projectedSpeedupVsExact.toFixed(2)}× |`;
})).join("\n");
const correctnessPassed = correctness.length - correctnessFailures.length;
const rejectionText = rejections.length === 0
  ? "No variant was rejected: all three syntaxes were supported, their computed gate states followed the CSS route, and all final winners matched the exact page."
  : rejections.map((rejection) => {
    const variant = variants.find((candidate) => candidate.id === rejection.variant);
    return `- **${rejection.bank} / ${variant.label}: rejected.** ${rejection.reasons.join("; ")}.`;
  }).join("\n");

const currentProjection = projection.byBank.full["conditional-display"]?.estimatedMilliseconds;
const contentProjection = projection.byBank.full["conditional-content-visibility"]?.estimatedMilliseconds;
const visibilityProjection = projection.byBank.full["conditional-visibility"]?.estimatedMilliseconds;
const contentFallbackAccept = summaries.full["conditional-content-visibility"]
  ?.transitions["fallback->accept"].medianMilliseconds;
const currentFallbackAccept = summaries.full["conditional-display"]
  ?.transitions["fallback->accept"].medianMilliseconds;
const bestFullVariant = acceptedVariants.full
  .map((variantId) => [variantId, projection.byBank.full[variantId].estimatedMilliseconds])
  .sort((left, right) => left[1] - right[1])[0];
const bestVariantLabel = variants.find((variant) => variant.id === bestFullVariant?.[0])?.label ?? "none";

const markdown = `# GSUB-certified hybrid fallback-gating ablation\n\n` +
  `Chrome **${chrome}** (${executablePath}), headless on ${report.platform}, using ` +
  `\`${server}\`. Each accepted bank/variant cell has ${measuredRounds} in-page measured rounds ` +
  `after ${warmupRounds} warmups (${measuredRounds * cases.length} samples): all 10 reference ` +
  `cases, reversed on odd rounds and rotated every round. Target order also reverses and rotates.\n\n` +
  `The current conditional \`display:none/grid\` gate is compared with exact-stage ` +
  `\`content-visibility:hidden/visible\` plus \`contain-intrinsic-size:auto 1px\`, and with a ` +
  `low-risk \`visibility:hidden/visible\` control. Both alternatives keep the exact stage ` +
  `\`display:grid\`. Each variant stylesheet is injected once before timing; routing and winner ` +
  `selection remain CSS-only.\n\n` +
  `Correctness: **${correctnessPassed}/${correctness.length} final-winner, route, and computed-gate ` +
  `checks passed** against the separate exact CSS page. The case mix is adversarial (3 accept, ` +
  `7 fallback), not the full-screen distribution.\n\n` +
  `## Accept/fallback medians\n\n` +
  `| Bank | Target | Overall | Accept | Fallback |\n| --- | --- | ---: | ---: | ---: |\n${summaryRows}\n\n` +
  `## Four transition medians\n\n` +
  `| Bank | Variant | Transition | Samples | Median |\n` +
  `| --- | --- | --- | ---: | ---: |\n${transitionRows}\n\n` +
  `The clock starts before the first of 768 input writes and ends after score-offset/group writes ` +
  `and the forced final geometry read. Route lookup and transition bookkeeping occur after the ` +
  `clock. Page load, font readiness, CSS injection, checks, warmups, and automation round trips ` +
  `are excluded.\n\n` +
  `## Full-screen 11.47%-fallback transition projection\n\n` +
  `This weights the four measured transition medians by independent consecutive routes using ` +
  `P(accept)=1,744/1,970=${(acceptProbability * 100).toFixed(2)}% and ` +
  `P(fallback)=226/1,970=${(fallbackProbability * 100).toFixed(2)}%. It is a projection, not a ` +
  `direct 1,970-case run.\n\n` +
  `| Bank | Variant | Projected transition-weighted time | Exact median | Speedup vs exact |\n` +
  `| --- | --- | ---: | ---: | ---: |\n${projectionRows}\n\n` +
  `On the full bank, fallback→accept is ${formatMs(currentFallbackAccept)} for the current gate ` +
  `and ${formatMs(contentFallbackAccept)} for content visibility. The full-bank projections are ` +
  `${formatMs(currentProjection)} current, ${formatMs(contentProjection)} content visibility, and ` +
  `${formatMs(visibilityProjection)} visibility; the lowest is **${bestVariantLabel}**.\n\n` +
  `## Rejections\n\n${rejectionText}\n\n` +
  `## Scope\n\n` +
  `The bounded and full production hybrid pages and their existing 10 cases are reused unchanged. ` +
  `This ablation changes only one-time injected exact-stage presentation CSS. It does not alter ` +
  `the CSS fallback predicate, top/runner routing, final winner mux, page sources, or certification ` +
  `claim.\n`;

await fs.writeFile(new URL("FALLBACK-GATING-RESULTS.md", experimentRoot), markdown);

console.log(JSON.stringify({
  chrome,
  timing: report.timing,
  correctness: {
    passed: correctnessPassed,
    checks: correctness.length,
    failures: correctnessFailures.length,
  },
  rejections,
  summaries,
  fullScreenTransitionProjection: projection,
}, null, 2));

if (rejections.some((rejection) => rejection.variant === "conditional-display") ||
    acceptedVariants.full.length < 2 || acceptedVariants.bounded.length < 2) {
  process.exitCode = 1;
}
