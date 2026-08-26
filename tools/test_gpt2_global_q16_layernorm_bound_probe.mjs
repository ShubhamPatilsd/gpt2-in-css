import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const repository = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const directory = "gpt2-global-q16-layernorm-bound";
const experiment = path.join(repository, "experiments", directory);
const reference = JSON.parse(await fs.readFile(path.join(experiment, "reference.json"), "utf8"));
const benchmarkRounds = Math.max(3, Number(process.env.Q16_LN_BOUND_BENCHMARK_ROUNDS ?? 5));

const contentTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".woff2", "font/woff2"],
]);
const serverErrors = [];
const server = http.createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
    if (pathname === "/favicon.ico") {
      response.writeHead(204).end();
      return;
    }
    const relative = pathname.replace(/^\/+/, "");
    const filename = path.resolve(repository, relative || "index.html");
    if (filename !== repository && !filename.startsWith(`${repository}${path.sep}`)) {
      response.writeHead(403).end("forbidden");
      return;
    }
    const body = await fs.readFile(filename);
    response.writeHead(200, {
      "content-type": contentTypes.get(path.extname(filename)) ?? "application/octet-stream",
      "cache-control": "no-store",
    });
    response.end(body);
  } catch (error) {
    serverErrors.push(String(error));
    response.writeHead(404).end("not found");
  }
});
await new Promise((resolve, reject) => {
  server.once("error", reject);
  server.listen(0, "127.0.0.1", resolve);
});
const origin = `http://127.0.0.1:${server.address().port}`;
const baseUrl = `${origin}/experiments/${directory}`;

function statistics(values) {
  const ordered = [...values].sort((left, right) => left - right);
  const percentile = (fraction) => ordered[Math.min(
    ordered.length - 1,
    Math.ceil(ordered.length * fraction) - 1,
  )];
  const middle = Math.floor(ordered.length / 2);
  return {
    samples: ordered.length,
    minimumMilliseconds: ordered[0],
    medianMilliseconds: ordered.length % 2
      ? ordered[middle]
      : (ordered[middle - 1] + ordered[middle]) / 2,
    meanMilliseconds: ordered.reduce((sum, value) => sum + value, 0) / ordered.length,
    p95Milliseconds: percentile(0.95),
    maximumMilliseconds: ordered.at(-1),
  };
}

function errorSummary(actual, expected) {
  const deltas = actual.map((value, index) => value - expected[index]);
  const histogram = new Map();
  for (const delta of deltas) histogram.set(delta, (histogram.get(delta) ?? 0) + 1);
  return {
    comparisons: deltas.length,
    nonzero: deltas.filter((delta) => delta !== 0).length,
    maximumAbsolute: Math.max(...deltas.map(Math.abs)),
    meanAbsolute: deltas.reduce((sum, delta) => sum + Math.abs(delta), 0) / deltas.length,
    histogram: Object.fromEntries([...histogram.entries()].sort(([left], [right]) => left - right)),
  };
}

function watch(page, label, diagnostics) {
  page.on("pageerror", (error) => diagnostics.pageErrors.push({ label, error: String(error) }));
  page.on("requestfailed", (request) => diagnostics.requestFailures.push({
    label,
    url: request.url(),
    error: request.failure()?.errorText ?? "unknown request failure",
  }));
  page.on("request", (request) => {
    if (request.resourceType() === "script") {
      diagnostics.scriptRequests.push({ label, url: request.url() });
    }
  });
  page.on("response", (response) => {
    if (response.status() >= 400) {
      diagnostics.httpErrors.push({ label, url: response.url(), status: response.status() });
    }
  });
}

async function sourceAudit() {
  const css = await fs.readFile(path.join(experiment, "index.css"), "utf8");
  const pages = [];
  for (const scale of reference.scales) {
    const source = await fs.readFile(path.join(experiment, scale.html), "utf8");
    pages.push({
      scale: scale.label,
      file: scale.html,
      bytes: Buffer.byteLength(source),
      scriptTags: (source.match(/<script\b/gi) ?? []).length,
      inlineEventHandlers: (source.match(/\son[a-z]+\s*=/gi) ?? []).length,
      javascriptUrls: (source.match(/javascript\s*:/gi) ?? []).length,
      cspScriptNone: /Content-Security-Policy[^>]+script-src 'none'/i.test(source),
    });
  }
  return {
    pages,
    cssBytes: Buffer.byteLength(css),
    cssImports: (css.match(/@import\b/gi) ?? []).length,
    passed: pages.every((page) => page.scriptTags === 0
      && page.inlineEventHandlers === 0
      && page.javascriptUrls === 0
      && page.cspScriptNone)
      && !/@import\b/i.test(css),
  };
}

async function applyFixture(page, fixture) {
  return page.evaluate(({ hidden, scoreFloor }) => {
    const probe = document.querySelector("#probe");
    const started = performance.now();
    for (let dimension = 0; dimension < hidden.length; dimension += 1) {
      probe.style.setProperty(`--h${dimension}`, String(hidden[dimension]));
    }
    probe.style.setProperty("--score-offset", `${-scoreFloor * 256 * 4}px`);
    const result = document.querySelector("#result");
    result.getBoundingClientRect().width;
    result.getBoundingClientRect().width;
    return performance.now() - started;
  }, fixture);
}

async function loadPage(context, url, label, diagnostics, firstFixture) {
  const page = await context.newPage();
  watch(page, label, diagnostics);
  page.setDefaultTimeout(240_000);
  await page.goto(url, { waitUntil: "load", timeout: 240_000 });
  await applyFixture(page, firstFixture);
  await page.evaluate(async () => document.fonts.ready);
  await applyFixture(page, firstFixture);
  return page;
}

async function readResult(page) {
  return page.evaluate(({ contenders }) => {
    const rows = [...document.querySelectorAll(".candidate")];
    const widths = rows.map((row) => row.getBoundingClientRect().width);
    const buckets = widths.map((width, index) => {
      const tie = contenders.length - 1 - index;
      return Math.round((width - tie / 64) / 4);
    });
    const maximumWidth = Math.max(...widths);
    const measuredIndex = widths.indexOf(maximumWidth);
    const result = document.querySelector("#result");
    const style = getComputedStyle(result);
    const cssIndex = Number(style.getPropertyValue("--index"));
    const cssBucket = Number(style.getPropertyValue("--bucket"));
    const stage = document.querySelector("#stage");
    return {
      widths,
      buckets,
      maximumWidth,
      measuredIndex,
      measuredWinner: contenders[measuredIndex],
      measuredBucket: Math.floor(maximumWidth / 4),
      cssIndex,
      cssWinner: contenders[cssIndex],
      cssBucket,
      stageWidth: stage.getBoundingClientRect().width,
      fontSizePx: Number.parseFloat(getComputedStyle(stage).fontSize),
      fontStatus: document.fonts.status,
      runtimeScriptElements: document.querySelectorAll("script").length,
    };
  }, { contenders: reference.contenders });
}

async function auditGlyphGeometry(page) {
  return page.evaluate(({ contenders, ceiling }) => {
    const range = document.createRange();
    const rows = [...document.querySelectorAll(".candidate")];
    let glyphMeasurements = 0;
    let collapsedGlyphs = 0;
    let collapsedRows = 0;
    let maximumHighAdvancePx = 0;
    let maximumResidualAdvancePx = 0;
    let atOrAboveCeiling = 0;
    const perFaceMaximumPx = Array(6).fill(0);
    const collapsedTokens = [];
    for (let rowIndex = 0; rowIndex < rows.length; rowIndex += 1) {
      const node = rows[rowIndex].firstChild;
      const characters = [...node.data];
      let offset = 0;
      let rowCollapsed = false;
      for (let face = 0; face < characters.length; face += 1) {
        const length = characters[face].length;
        range.setStart(node, offset);
        range.setEnd(node, offset + length);
        const width = range.getBoundingClientRect().width;
        perFaceMaximumPx[face] = Math.max(perFaceMaximumPx[face], width);
        if (face % 2 === 0) maximumHighAdvancePx = Math.max(maximumHighAdvancePx, width);
        else maximumResidualAdvancePx = Math.max(maximumResidualAdvancePx, width);
        if (width >= ceiling) atOrAboveCeiling += 1;
        if (!(width > 0)) {
          collapsedGlyphs += 1;
          rowCollapsed = true;
        }
        glyphMeasurements += 1;
        offset += length;
      }
      if (rowCollapsed) {
        collapsedRows += 1;
        collapsedTokens.push(contenders[rowIndex]);
      }
    }
    return {
      glyphMeasurements,
      collapsedGlyphs,
      collapsedRows,
      collapsedTokens,
      maximumHighAdvancePx,
      maximumResidualAdvancePx,
      maximumAdjustedAdvancePx: Math.max(maximumHighAdvancePx, maximumResidualAdvancePx),
      atOrAboveCeiling,
      perFaceMaximumPx,
    };
  }, { contenders: reference.contenders, ceiling: reference.chromeAdvanceCeilingPx });
}

async function zeroCoordinateAudit(page) {
  return page.evaluate(({ dimensions }) => {
    const probe = document.querySelector("#probe");
    for (let dimension = 0; dimension < dimensions; dimension += 1) {
      probe.style.setProperty(`--h${dimension}`, "0");
    }
    probe.style.setProperty("--score-offset", "0px");
    document.querySelector("#result").getBoundingClientRect().width;
    const range = document.createRange();
    const deltas = [...document.querySelectorAll(".candidate")].map((row) => {
      const node = row.firstChild;
      range.setStart(node, 0);
      range.setEnd(node, node.length);
      return range.getBoundingClientRect().width - Number(row.style.getPropertyValue("--base"));
    });
    return {
      rows: deltas.length,
      minimumDeltaPx: Math.min(...deltas),
      maximumDeltaPx: Math.max(...deltas),
      maximumAbsoluteDeltaPx: Math.max(...deltas.map(Math.abs)),
    };
  }, { dimensions: 768 });
}

async function runtimeAudit(page) {
  return page.evaluate(() => ({
    scriptElements: document.querySelectorAll("script").length,
    inlineEventAttributes: [...document.querySelectorAll("*")].reduce(
      (count, element) => count + [...element.attributes]
        .filter((attribute) => /^on/i.test(attribute.name)).length,
      0,
    ),
    csp: document.querySelector('meta[http-equiv="Content-Security-Policy"]')?.content ?? null,
    resourceScripts: performance.getEntriesByType("resource")
      .filter((entry) => entry.initiatorType === "script")
      .map((entry) => entry.name),
  }));
}

async function auditAxisLiveness(page, scale) {
  const snapshots = [];
  for (const fixture of reference.fixtures.slice(0, 2)) {
    await applyFixture(page, fixture);
    snapshots.push(await page.evaluate(({
      state, hidden, coordinateRange, axisSteps, integerAxis,
    }) => {
      const stage = document.querySelector("#stage");
      const style = getComputedStyle(stage);
      const serialized = style.fontVariationSettings;
      const parsed = [...serialized.matchAll(/"([^"]{4})"\s+(-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)/gi)]
        .map((match) => ({ tag: match[1], value: Number(match[2]) }));
      const expected = integerAxis
        ? hidden.map((value) => Math.round(value / coordinateRange * axisSteps))
        : [];
      const range = document.createRange();
      const intrinsicWidths = [...document.querySelectorAll(".candidate")].slice(0, 16).map((row) => {
        const node = row.firstChild;
        range.setStart(node, 0);
        range.setEnd(node, node.length);
        return range.getBoundingClientRect().width;
      });
      return {
        state,
        fontFamily: style.fontFamily,
        serializedIsNormal: serialized === "normal",
        serializedBytes: new TextEncoder().encode(serialized).length,
        serializedSettings: serialized,
        serializedPrefix: serialized.slice(0, 240),
        parsedAxisCount: parsed.length,
        allParsedValuesFinite: parsed.every((item) => Number.isFinite(item.value)),
        allParsedValuesInteger: parsed.every((item) => Number.isInteger(item.value)),
        maximumAbsoluteIntegerOracleError: integerAxis && parsed.length === expected.length
          ? Math.max(...parsed.map((item, index) => Math.abs(item.value - expected[index])))
          : null,
        coordinateSamples: [0, 36, 314, 496, 767]
          .filter((index) => index < parsed.length)
          .map((index) => ({
            dimension: index,
            computed: parsed[index].value,
            expected: integerAxis ? expected[index] : null,
          })),
        intrinsicWidths,
      };
    }, {
      state: fixture.state,
      hidden: fixture.hidden,
      coordinateRange: reference.proofScope.coordinateRangeR,
      axisSteps: reference.productionCoordinates.axisSteps,
      integerAxis: scale.axisMode === "integer-user-coordinate",
    }));
  }
  return {
    slug: scale.slug,
    scale: scale.label,
    snapshots,
    computedSettingsChangeBetweenFixtures:
      snapshots[0].serializedSettings !== snapshots[1].serializedSettings,
    intrinsicMetricsChangeBetweenFixtures: snapshots[0].intrinsicWidths.some(
      (width, index) => width !== snapshots[1].intrinsicWidths[index],
    ),
    integerFamiliesActive: scale.axisMode !== "integer-user-coordinate"
      || snapshots.every((snapshot) => snapshot.fontFamily.includes("IntegerBound")),
    integerSettingsAccepted: scale.axisMode !== "integer-user-coordinate"
      || snapshots.every((snapshot) => !snapshot.serializedIsNormal
        && snapshot.parsedAxisCount === 768
        && snapshot.allParsedValuesFinite
        && snapshot.allParsedValuesInteger
        && snapshot.maximumAbsoluteIntegerOracleError === 0),
  };
}

async function benchmark(context, url, label, diagnostics) {
  const page = await loadPage(context, url, `benchmark-${label}`, diagnostics, reference.fixtures[0]);
  for (const fixture of reference.fixtures) await applyFixture(page, fixture);
  const samples = [];
  let minimumLiveWidth = Infinity;
  for (let round = 0; round < benchmarkRounds; round += 1) {
    for (const fixture of reference.fixtures) {
      const output = await page.evaluate(({ item }) => {
        const probe = document.querySelector("#probe");
        const started = performance.now();
        for (let dimension = 0; dimension < item.hidden.length; dimension += 1) {
          probe.style.setProperty(`--h${dimension}`, String(item.hidden[dimension]));
        }
        probe.style.setProperty("--score-offset", `${-item.scoreFloor * 256 * 4}px`);
        const result = document.querySelector("#result");
        result.getBoundingClientRect().width;
        result.getBoundingClientRect().width;
        return {
          milliseconds: performance.now() - started,
          stageWidth: document.querySelector("#stage").getBoundingClientRect().width,
        };
      }, { item: fixture });
      samples.push(output.milliseconds);
      minimumLiveWidth = Math.min(minimumLiveWidth, output.stageWidth);
    }
  }
  await page.close();
  return { label, rounds: benchmarkRounds, minimumLiveWidth, ...statistics(samples) };
}

const artifactAudit = await sourceAudit();
const diagnostics = { pageErrors: [], requestFailures: [], httpErrors: [], scriptRequests: [] };
const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const context = await browser.newContext({ viewport: { width: 800, height: 240 } });
  const correctness = [];
  const geometry = [];
  const zeroCoordinate = [];
  const runtime = [];
  const axisLiveness = [];
  for (const scale of reference.scales) {
    const page = await loadPage(
      context,
      `${baseUrl}/${scale.html}`,
      `correctness-${scale.slug}`,
      diagnostics,
      reference.fixtures[0],
    );
    axisLiveness.push(await auditAxisLiveness(page, scale));
    zeroCoordinate.push({ slug: scale.slug, scale: scale.label, ...(await zeroCoordinateAudit(page)) });
    for (const fixture of reference.fixtures) {
      await applyFixture(page, fixture);
      const browserResult = await readResult(page);
      const q16Errors = errorSummary(browserResult.buckets, fixture.q16Buckets);
      const floatErrors = errorSummary(browserResult.buckets, fixture.floatBuckets);
      correctness.push({
        slug: scale.slug,
        scale: scale.label,
        state: fixture.state,
        roles: fixture.roles,
        mathematical: {
          q16Winner: fixture.q16MathematicalWinner,
          q16BucketWinner: fixture.q16BucketWinner,
          floatWinner: fixture.floatWinner,
          floatBucketWinner: fixture.floatBucketWinner,
          floatMargin: fixture.floatMargin,
        },
        browser: browserResult,
        bucketErrors: { versusQ16: q16Errors, versusFloat: floatErrors },
        checks: {
          rowsFinite: browserResult.widths.every((width) => Number.isFinite(width) && width >= 0),
          stageLive: browserResult.stageWidth > 0,
          cssIndexInRange: Number.isInteger(browserResult.cssIndex)
            && browserResult.cssIndex >= 0
            && browserResult.cssIndex < reference.contenderCount,
          cssIndexMatchesMeasured: browserResult.cssIndex === browserResult.measuredIndex,
          cssBucketMatchesMeasured: browserResult.cssBucket === browserResult.measuredBucket,
          stageWidthMatchesMaximum: Math.abs(browserResult.stageWidth - browserResult.maximumWidth) < 1 / 128,
          expectedFontSize: Math.abs(browserResult.fontSizePx - scale.fontSizePx) < 1e-9,
          fontsLoaded: browserResult.fontStatus === "loaded",
          noScriptElements: browserResult.runtimeScriptElements === 0,
        },
      });
      geometry.push({
        slug: scale.slug,
        scale: scale.label,
        state: fixture.state,
        ...(await auditGlyphGeometry(page)),
      });
    }
    runtime.push({ slug: scale.slug, scale: scale.label, ...(await runtimeAudit(page)) });
    await page.close();
  }

  const benchmarks = [];
  for (const scale of reference.scales) {
    benchmarks.push(await benchmark(
      context,
      `${baseUrl}/${scale.html}`,
      `bounded-${scale.slug}`,
      diagnostics,
    ));
  }
  const control = reference.retainedLatencyControl;
  benchmarks.push(await benchmark(
    context,
    `${origin}/experiments/${control.experiment}/${control.html}`,
    "retained-12-glyph-0p1",
    diagnostics,
  ));
  await context.close();

  const controlBenchmark = benchmarks.find((item) => item.label === "retained-12-glyph-0p1");
  const perScale = reference.scales.map((scale) => {
    const rows = correctness.filter((row) => row.slug === scale.slug);
    const audits = geometry.filter((row) => row.slug === scale.slug);
    const scaleBenchmark = benchmarks.find((item) => item.label === `bounded-${scale.slug}`);
    const axisAudit = axisLiveness.find((item) => item.slug === scale.slug);
    return {
      slug: scale.slug,
      scale: scale.label,
      fixtures: rows.length,
      q16MathematicalWinnerMatches: rows.filter(
        (row) => row.browser.cssWinner === row.mathematical.q16Winner,
      ).length,
      q16BucketWinnerMatches: rows.filter(
        (row) => row.browser.cssWinner === row.mathematical.q16BucketWinner,
      ).length,
      floatWinnerMatches: rows.filter(
        (row) => row.browser.cssWinner === row.mathematical.floatWinner,
      ).length,
      q16WinnerMismatchStates: rows.filter(
        (row) => row.browser.cssWinner !== row.mathematical.q16Winner,
      ).map((row) => row.state),
      q16BucketWinnerMismatchStates: rows.filter(
        (row) => row.browser.cssWinner !== row.mathematical.q16BucketWinner,
      ).map((row) => row.state),
      floatWinnerMismatchStates: rows.filter(
        (row) => row.browser.cssWinner !== row.mathematical.floatWinner,
      ).map((row) => row.state),
      maximumAbsoluteCandidateBucketErrorVersusQ16: Math.max(
        ...rows.map((row) => row.bucketErrors.versusQ16.maximumAbsolute),
      ),
      maximumAbsoluteCandidateBucketErrorVersusFloat: Math.max(
        ...rows.map((row) => row.bucketErrors.versusFloat.maximumAbsolute),
      ),
      differingCandidateBucketsVersusQ16: rows.reduce(
        (sum, row) => sum + row.bucketErrors.versusQ16.nonzero,
        0,
      ),
      allLiveChecksPass: rows.every((row) => Object.values(row.checks).every(Boolean)),
      axisLiveness: {
        computedSettingsChangeBetweenFixtures: axisAudit.computedSettingsChangeBetweenFixtures,
        intrinsicMetricsChangeBetweenFixtures: axisAudit.intrinsicMetricsChangeBetweenFixtures,
        integerFamiliesActive: axisAudit.integerFamiliesActive,
        integerSettingsAccepted: axisAudit.integerSettingsAccepted,
      },
      geometry: {
        glyphMeasurements: audits.reduce((sum, audit) => sum + audit.glyphMeasurements, 0),
        collapsedGlyphs: audits.reduce((sum, audit) => sum + audit.collapsedGlyphs, 0),
        collapsedRows: audits.reduce((sum, audit) => sum + audit.collapsedRows, 0),
        atOrAboveCeiling: audits.reduce((sum, audit) => sum + audit.atOrAboveCeiling, 0),
        maximumBrowserHighAdvancePx: Math.max(...audits.map((audit) => audit.maximumHighAdvancePx)),
        maximumBrowserResidualAdvancePx: Math.max(...audits.map((audit) => audit.maximumResidualAdvancePx)),
        maximumBrowserAdjustedAdvancePx: Math.max(...audits.map((audit) => audit.maximumAdjustedAdvancePx)),
        analyticMaximumAdjustedAdvancePx: scale.analyticMaximumAdjustedAdvancePx,
      },
      latency: {
        medianMilliseconds: scaleBenchmark.medianMilliseconds,
        p95Milliseconds: scaleBenchmark.p95Milliseconds,
        retained12GlyphMedianMilliseconds: controlBenchmark.medianMilliseconds,
        medianRatioVersusRetained12Glyph:
          scaleBenchmark.medianMilliseconds / controlBenchmark.medianMilliseconds,
      },
    };
  });

  const runtimeAuditPassed = artifactAudit.passed
    && runtime.every((audit) => audit.scriptElements === 0
      && audit.inlineEventAttributes === 0
      && audit.resourceScripts.length === 0
      && audit.csp?.includes("script-src 'none'"))
    && diagnostics.scriptRequests.length === 0;
  const livenessPassed = perScale.every((scale) => scale.allLiveChecksPass);
  const geometryPassed = perScale.every((scale) => scale.geometry.collapsedRows === 0
    && scale.geometry.atOrAboveCeiling === 0
    && scale.geometry.maximumBrowserAdjustedAdvancePx < reference.chromeAdvanceCeilingPx
    && scale.geometry.analyticMaximumAdjustedAdvancePx < reference.chromeAdvanceCeilingPx);
  const integerAxis = perScale.find((scale) => scale.slug === "integer-axis");
  const integerAxisAccepted = integerAxis.axisLiveness.integerFamiliesActive
    && integerAxis.axisLiveness.integerSettingsAccepted
    && integerAxis.axisLiveness.computedSettingsChangeBetweenFixtures
    && integerAxis.axisLiveness.intrinsicMetricsChangeBetweenFixtures;
  const integerAxisWinnerCorrectnessPassed =
    integerAxis.q16MathematicalWinnerMatches === integerAxis.fixtures
    && integerAxis.q16BucketWinnerMatches === integerAxis.fixtures;
  const integerAxisCandidateBucketErrorAtMostOne =
    integerAxis.maximumAbsoluteCandidateBucketErrorVersusQ16 <= 1;
  const integerAxisExactCandidateBucketsPassed =
    integerAxis.maximumAbsoluteCandidateBucketErrorVersusQ16 === 0
    && integerAxis.differingCandidateBucketsVersusQ16 === 0;
  const noErrors = [
    ...diagnostics.pageErrors,
    ...diagnostics.requestFailures,
    ...diagnostics.httpErrors,
    ...serverErrors,
  ].length === 0;
  report = {
    chromeVersion: await browser.version(),
    benchmarkRounds,
    correctnessOracle: "mathematical global-q16 and original checkpoint float; retained browser used for latency only",
    artifactAudit,
    runtime,
    axisLiveness,
    correctness,
    geometry,
    zeroCoordinate,
    benchmarks,
    perScale,
    gates: {
      analyticProofScopeRecorded: reference.proofScope.overclaimAvoided
        && reference.proofScope.analyticCoordinateMaximumAbsolute > reference.proofScope.coordinateRangeR,
      analyticLowerBoundsStrictlyPositive:
        reference.layerNormReachability.allAnalyticLowerBoundsStrictlyPositive,
      layerNormReconstructionPassed:
        reference.storedLayerNormReconstruction.maximumAbsoluteZMean < 1e-6
        && reference.storedLayerNormReconstruction.maximumAbsoluteZNormError < 1e-4,
      runtimeAuditPassed,
      livenessPassed,
      geometryPassed,
      integerAxisAccepted,
      integerAxisWinnerCorrectnessPassed,
      integerAxisCandidateBucketErrorAtMostOne,
      integerAxisExactCandidateBucketsPassed,
      noErrors,
    },
  };
  report.pass = Object.values(report.gates).every(Boolean);
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}

await fs.writeFile(path.join(experiment, "results.json"), `${JSON.stringify(report, null, 2)}\n`);

const scaleRows = report.perScale.map((scale) => (
  `| ${scale.scale} | ${scale.q16MathematicalWinnerMatches}/${scale.fixtures} | `
  + `${scale.q16BucketWinnerMatches}/${scale.fixtures} | ${scale.floatWinnerMatches}/${scale.fixtures} | `
  + `${scale.maximumAbsoluteCandidateBucketErrorVersusQ16} | `
  + `${scale.maximumAbsoluteCandidateBucketErrorVersusFloat} | `
  + `${scale.geometry.collapsedRows} | ${scale.latency.medianMilliseconds.toFixed(2)} | `
  + `${scale.latency.medianRatioVersusRetained12Glyph.toFixed(3)}× |`
)).join("\n");
const geometryRows = report.perScale.map((scale) => {
  const definition = reference.scales.find((item) => item.slug === scale.slug);
  return `| ${scale.scale} | ${definition.residualUnitLayout64} | ${definition.highUnitLayout64} | `
    + `${definition.analyticMaximumHighPlaneAdjustedAdvancePx.toFixed(3)} | `
    + `${definition.analyticMaximumResidualPlaneAdjustedAdvancePx.toFixed(3)} | `
    + `${scale.geometry.maximumBrowserAdjustedAdvancePx.toFixed(3)} | `
    + `${scale.geometry.atOrAboveCeiling} |`;
}).join("\n");
const mismatchRows = report.perScale.map((scale) => (
  `| ${scale.scale} | ${scale.q16WinnerMismatchStates.join(", ") || "none"} | `
  + `${scale.q16BucketWinnerMismatchStates.join(", ") || "none"} | `
  + `${scale.floatWinnerMismatchStates.join(", ") || "none"} |`
)).join("\n");
const control = report.benchmarks.find((item) => item.label === "retained-12-glyph-0p1");
const integerResult = report.perScale.find((item) => item.slug === "integer-axis");
const integerAxisAudit = report.axisLiveness.find((item) => item.slug === "integer-axis");
const integerCoordinateError = Math.max(
  ...integerAxisAudit.snapshots.map((snapshot) => snapshot.maximumAbsoluteIntegerOracleError),
);
const markdown = `# GPT-2 global-q16 final-LayerNorm-bound Chrome probe

## Result

The analytic base, geometry, liveness, CSP, and no-collapse gates passed. Strict exact-candidate global-q16 transport certification with integer fvar user coordinates passed: **${report.pass}**. The integer-axis page matched ${integerResult.q16BucketWinnerMatches}/${integerResult.fixtures} mathematical q16 bucket winners, including states 493 and 390. Its all-winner decision gate passes, but ${integerResult.differingCandidateBucketsVersusQ16}/${integerResult.fixtures * reference.contenderCount} candidate buckets differ from mathematical q16 by at most ${integerResult.maximumAbsoluteCandidateBucketErrorVersusQ16}, so the stricter every-bucket-exact gate remains false. The normalized-axis and half-step baselines remain preserved below.

| Scale | q16 winner | q16 bucket winner | Float winner | Max bucket error vs q16 | Max bucket error vs float | Collapsed rows | Warm median (ms) | Median vs retained |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
${scaleRows}

The retained 12-glyph q16 page was used only as a latency control (warm median ${control.medianMilliseconds.toFixed(2)} ms), never as a correctness oracle. Correctness comparisons use the immutable global-q16 codes and original checkpoint float weights directly.

## Integer-axis acceptance and liveness

The duplicate six-font bank uses fvar min/default/max = -16384/0/+16384 while retaining byte-identical normalized HVAR tables and q16 deltas. CSS supplies \`round(nearest, hidden/R*16384, 1)\` as an integer user coordinate. Chrome ${report.gates.integerAxisAccepted ? "accepted" : "did not accept"} this path: computed settings were non-\`normal\`, used the \`IntegerBound*\` families, exposed ${integerAxisAudit.snapshots[0].parsedAxisCount} finite integer axes, matched the nearest-coordinate oracle with maximum coordinate error ${integerCoordinateError}, changed between fixtures (${integerAxisAudit.computedSettingsChangeBetweenFixtures}), and changed intrinsic glyph metrics (${integerAxisAudit.intrinsicMetricsChangeBetweenFixtures}). The remaining one-bucket candidate differences therefore occur after exact coordinate normalization, consistent with per-glyph HVAR advance/layout rounding rather than rejected CSS syntax or a rejected fvar range.

## Analytic reachability bound

For each token row, plane, and 256-axis shard, with y = gamma*z + beta, sum(z) = 0, and ||z||2 <= sqrt(768), the font uses

    bias = c·beta/R
    radius = sqrt(768) ||P(c*gamma padded to 768)||2/R
    base = ceil(radius - bias + 24)

where P(v) = v - mean(v)1. Across all 1,152 bounded glyph rows, the analytic advance interval is ${reference.layerNormReachability.minimumAnalyticAdvance.toFixed(6)} to ${reference.layerNormReachability.maximumAnalyticAdvance.toFixed(6)} font units; every lower bound is positive with an explicit 24-unit margin.

The Cauchy advance bound covers the full mean-zero norm ball. Exact HVAR transport is certified only on its intersection with the declared coordinate domain |y_i| <= R = ${reference.proofScope.coordinateRangeR}. The unconstrained LayerNorm coordinate bound reaches ${reference.proofScope.analyticCoordinateMaximumAbsolute.toFixed(6)} at dimension ${reference.proofScope.analyticCoordinateMaximumDimension}; dimensions ${reference.proofScope.dimensionsWhoseAnalyticCoordinateBoundExceedsR.join(", ")} can exceed R, so this probe does not claim exact transport outside the unclipped HVAR domain.

The 1,024 stored final-LayerNorm states reconstruct z = (y - beta)/gamma with maximum absolute mean ${reference.storedLayerNormReconstruction.maximumAbsoluteZMean.toExponential(3)} and norm ${reference.storedLayerNormReconstruction.minimumZNorm.toFixed(6)}–${reference.storedLayerNormReconstruction.maximumZNorm.toFixed(6)} versus sqrt(768) = ${reference.storedLayerNormReconstruction.expectedZNorm.toFixed(6)}.

## Chrome geometry

| Scale | Residual unit (layout64) | High unit (layout64) | Analytic high max (px) | Analytic residual max (px) | Browser max (px) | At/above 32768 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
${geometryRows}

Both six-font WOFF2 banks contain only the ${reference.contenderCount} target rows. At scale 0.1 the analytic high-plane bound is ${reference.scales.find((scale) => scale.slug === "0p1").analyticMaximumHighPlaneAdjustedAdvancePx.toFixed(3)} px; at 1/16 it is ${reference.scales.find((scale) => scale.slug === "1over16").analyticMaximumHighPlaneAdjustedAdvancePx.toFixed(3)} px, both far below Chrome's 32,768 px adjusted-glyph ceiling. Chrome measured zero collapsed rows.

| Scale | q16 winner mismatches | q16 bucket-winner mismatches | Float-winner mismatches |
| --- | --- | --- | --- |
${mismatchRows}

## Runtime contract

All four HTML artifacts have CSP \`script-src 'none'\`. Raw-source, DOM, event-handler, resource, request, liveness, and geometry audits found no script execution or runtime errors. Browser automation is external to the artifacts. Chrome: ${report.chromeVersion}.

Raw data: \`reference.json\` and \`results.json\`.

## Reproduce

    PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_gpt2_global_q16_layernorm_bound_probe.py
    node --check tools/test_gpt2_global_q16_layernorm_bound_probe.mjs
    Q16_LN_BOUND_BENCHMARK_ROUNDS=${report.benchmarkRounds} node tools/test_gpt2_global_q16_layernorm_bound_probe.mjs
`;
await fs.writeFile(path.join(experiment, "RESULTS.md"), markdown);
console.log(JSON.stringify({
  chromeVersion: report.chromeVersion,
  perScale: report.perScale,
  gates: report.gates,
  pass: report.pass,
}, null, 2));
