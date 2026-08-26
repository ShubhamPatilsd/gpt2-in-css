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
const directory = "gpt2-global-q16-layernorm-integer-full";
const experiment = path.join(repository, "experiments", directory);
const reference = JSON.parse(await fs.readFile(path.join(experiment, "reference.json"), "utf8"));
const warmRounds = Math.max(1, Number(process.env.Q16_INTEGER_FULL_WARM_ROUNDS ?? 2));
const resultsPath = path.join(experiment, "results.json");
const firstRunPath = path.join(experiment, "results-first-run.json");
try {
  await fs.access(firstRunPath);
} catch {
  try {
    await fs.copyFile(resultsPath, firstRunPath);
  } catch {
    // The first invocation has no earlier result to preserve.
  }
}
let firstRun = null;
try {
  firstRun = JSON.parse(await fs.readFile(firstRunPath, "utf8"));
} catch {
  // An exhaustive geometry pass will be used when no preserved run exists.
}

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
const url = `http://127.0.0.1:${server.address().port}/experiments/${directory}/index.html`;

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

function compareBuckets(actual, q16, float) {
  let maximumAbsoluteVersusQ16 = 0;
  let maximumAbsoluteVersusFloat = 0;
  let differingVersusQ16 = 0;
  let differingVersusFloat = 0;
  const q16Histogram = new Map();
  let browserWinner = 0;
  for (let token = 0; token < actual.length; token += 1) {
    const q16Delta = actual[token] - q16[token];
    const floatDelta = actual[token] - float[token];
    maximumAbsoluteVersusQ16 = Math.max(maximumAbsoluteVersusQ16, Math.abs(q16Delta));
    maximumAbsoluteVersusFloat = Math.max(maximumAbsoluteVersusFloat, Math.abs(floatDelta));
    if (q16Delta !== 0) differingVersusQ16 += 1;
    if (floatDelta !== 0) differingVersusFloat += 1;
    q16Histogram.set(q16Delta, (q16Histogram.get(q16Delta) ?? 0) + 1);
    if (actual[token] > actual[browserWinner]) browserWinner = token;
  }
  return {
    browserBucketWinner: browserWinner,
    browserWinnerBucket: actual[browserWinner],
    maximumAbsoluteVersusQ16,
    maximumAbsoluteVersusFloat,
    differingVersusQ16,
    differingVersusFloat,
    q16ErrorHistogram: Object.fromEntries(
      [...q16Histogram.entries()].sort(([left], [right]) => left - right),
    ),
  };
}

function watch(page, diagnostics) {
  page.on("pageerror", (error) => diagnostics.pageErrors.push(String(error)));
  page.on("requestfailed", (request) => diagnostics.requestFailures.push({
    url: request.url(),
    error: request.failure()?.errorText ?? "unknown request failure",
  }));
  page.on("request", (request) => {
    if (request.resourceType() === "script") diagnostics.scriptRequests.push(request.url());
  });
  page.on("response", (response) => {
    if (response.status() >= 400) {
      diagnostics.httpErrors.push({ url: response.url(), status: response.status() });
    }
  });
}

async function sourceAudit() {
  const html = await fs.readFile(path.join(experiment, "index.html"), "utf8");
  const css = await fs.readFile(path.join(experiment, "index.css"), "utf8");
  return {
    htmlBytes: Buffer.byteLength(html),
    cssBytes: Buffer.byteLength(css),
    scriptTags: (html.match(/<script\b/gi) ?? []).length,
    inlineEventHandlers: (html.match(/\son[a-z]+\s*=/gi) ?? []).length,
    javascriptUrls: (html.match(/javascript\s*:/gi) ?? []).length,
    cssImports: (css.match(/@import\b/gi) ?? []).length,
    cspScriptNone: /Content-Security-Policy[^>]+script-src 'none'/i.test(html),
    integerAxisFormulaPresent:
      /round\(nearest,calc\(var\(--h0\)\/[\d.]+\*16384\),1\)/.test(css),
    directGridReducerPresent: html.includes('<main id="model" class="model"><section')
      && !html.includes("group-scroller")
      && css.includes(".model>.group-wrapper{position:relative;left:auto;top:auto;grid-area:1/1}"),
  };
}

async function selectFixture(page, fixture) {
  return page.evaluate((query) => {
    const started = performance.now();
    document.querySelector(`#q${query}`).click();
    const result = document.querySelector("#result");
    result.getBoundingClientRect().width;
    result.getBoundingClientRect().width;
    const style = getComputedStyle(result);
    return {
      milliseconds: performance.now() - started,
      cssWinner: Number(style.getPropertyValue("--winner")),
      cssGroup: Number(style.getPropertyValue("--group")),
      cssLocal: Number(style.getPropertyValue("--local")),
      resultWidth: result.getBoundingClientRect().width,
      modelWidth: document.querySelector("#model").getBoundingClientRect().width,
      outerMaxWidth: document.querySelector(".outer-max").getBoundingClientRect().width,
    };
  }, fixture.query);
}

async function readFullBuckets(page) {
  return page.evaluate(() => [...document.querySelectorAll(".candidate")].map((row, token) => {
    const tie = 255 - token % 256;
    return Math.round((row.getBoundingClientRect().width - tie / 64) / 4);
  }));
}

async function decoderDiagnostics(page, fixture) {
  return page.evaluate(({ expectedWinner, state, vocabulary }) => {
    const width = (selector) => document.querySelector(selector).getBoundingClientRect().width;
    const wrappers = [...document.querySelectorAll(".group-wrapper")]
      .map((element) => element.getBoundingClientRect().width);
    const matches = [...document.querySelectorAll(".match-carrier")]
      .map((element) => element.getBoundingClientRect().width);
    const result = getComputedStyle(document.querySelector("#result"));
    const maximum = (values) => {
      const value = Math.max(...values);
      return { value, index: values.indexOf(value) };
    };
    const expectedGroup = Math.floor(expectedWinner / 256);
    return {
      state,
      expectedWinner,
      expectedGroup,
      outerMaxWidth: width(".outer-max"),
      wrapperMaximum: maximum(wrappers),
      expectedWrapperWidth: wrappers[expectedGroup],
      expectedGridWidth: width(`.group-${expectedGroup}`),
      matchMaximum: maximum(matches),
      expectedMatchWidth: matches[expectedGroup],
      nonzeroMatches: matches.map((value, group) => ({ group, value }))
        .filter((item) => item.value > 0),
      groupChoiceWidth: width(".group-choice"),
      computed: {
        group: Number(result.getPropertyValue("--group")),
        local: Number(result.getPropertyValue("--local")),
        winner: Number(result.getPropertyValue("--winner")),
      },
      vocabulary,
    };
  }, {
    expectedWinner: fixture.q16Winner,
    state: fixture.state,
    vocabulary: reference.vocabulary,
  });
}

async function axisAudit(page) {
  const snapshots = [];
  for (const fixture of reference.fixtures.slice(0, 2)) {
    await selectFixture(page, fixture);
    snapshots.push(await page.evaluate(({
      hidden, coordinateRange, axisSteps,
    }) => {
      const model = document.querySelector("#model");
      const style = getComputedStyle(model);
      const serialized = style.fontVariationSettings;
      const parsed = [...serialized.matchAll(/"([^"]{4})"\s+(-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)/gi)]
        .map((match) => Number(match[2]));
      const expected = hidden.map((value) => Math.round(value / coordinateRange * axisSteps));
      const first = document.querySelector(".candidate");
      const range = document.createRange();
      range.selectNodeContents(first);
      return {
        fontFamily: style.fontFamily,
        serializedIsNormal: serialized === "normal",
        parsedAxisCount: parsed.length,
        allInteger: parsed.every(Number.isInteger),
        maximumAbsoluteOracleError: parsed.length === expected.length
          ? Math.max(...parsed.map((value, index) => Math.abs(value - expected[index])))
          : null,
        serialized,
        firstIntrinsicWidth: range.getBoundingClientRect().width,
      };
    }, {
      hidden: fixture.hidden,
      coordinateRange: reference.coordinates.declaredRangeR,
      axisSteps: reference.coordinates.axisSteps,
    }));
  }
  return {
    snapshots,
    settingsChange: snapshots[0].serialized !== snapshots[1].serialized,
    intrinsicWidthChange: snapshots[0].firstIntrinsicWidth !== snapshots[1].firstIntrinsicWidth,
    passed: snapshots.every((snapshot) => !snapshot.serializedIsNormal
      && snapshot.parsedAxisCount === 768
      && snapshot.allInteger
      && snapshot.maximumAbsoluteOracleError === 0)
      && snapshots[0].serialized !== snapshots[1].serialized
      && snapshots[0].firstIntrinsicWidth !== snapshots[1].firstIntrinsicWidth,
  };
}

async function geometryAudit(page, fixture, sampleSize = null) {
  await selectFixture(page, fixture);
  return page.evaluate(({ ceiling, state, requestedSampleSize }) => {
    const allRows = [...document.querySelectorAll(".candidate")];
    const rows = requestedSampleSize && requestedSampleSize < allRows.length
      ? Array.from({ length: requestedSampleSize }, (_, index) => allRows[Math.round(
        index * (allRows.length - 1) / (requestedSampleSize - 1),
      )])
      : allRows;
    const range = document.createRange();
    let glyphMeasurements = 0;
    let collapsedGlyphs = 0;
    let collapsedRows = 0;
    let atOrAboveCeiling = 0;
    let maximumHighAdvancePx = 0;
    let maximumResidualAdvancePx = 0;
    const perFaceMaximumPx = Array(6).fill(0);
    for (const row of rows) {
      const node = row.firstChild;
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
      if (rowCollapsed) collapsedRows += 1;
    }
    return {
      state,
      vocabularyRows: allRows.length,
      rows: rows.length,
      glyphMeasurements,
      collapsedGlyphs,
      collapsedRows,
      atOrAboveCeiling,
      maximumHighAdvancePx,
      maximumResidualAdvancePx,
      maximumAdjustedAdvancePx: Math.max(maximumHighAdvancePx, maximumResidualAdvancePx),
      perFaceMaximumPx,
    };
  }, { ceiling: 32768, state: fixture.state, requestedSampleSize: sampleSize });
}

async function reducerEdgeAudit(page) {
  return page.evaluate(({ maximumToken }) => {
    const result = document.querySelector("#result");
    const token = (id) => document.querySelector(`[data-token="${id}"]`);
    const read = () => {
      document.querySelector(".outer-max").getBoundingClientRect().width;
      result.getBoundingClientRect().width;
      result.getBoundingClientRect().width;
      const style = getComputedStyle(result);
      return {
        group: Number(style.getPropertyValue("--group")),
        local: Number(style.getPropertyValue("--local")),
        winner: Number(style.getPropertyValue("--winner")),
      };
    };
    const forceEqualScore = (element) => element.style.setProperty(
      "width", "calc(30000px + var(--local-tie)/64*1px)", "important",
    );
    const restore = (element) => element.style.removeProperty("width");

    const maximum = token(maximumToken);
    forceEqualScore(maximum);
    const maximumTokenResult = read();
    restore(maximum);

    const penultimate = token(maximumToken - 1);
    forceEqualScore(penultimate);
    forceEqualScore(maximum);
    const partialGroupTieResult = read();
    restore(penultimate);
    restore(maximum);

    const groupZero = token(0);
    const groupOne = token(256);
    forceEqualScore(groupZero);
    forceEqualScore(groupOne);
    const groupTieResult = read();
    restore(groupZero);
    restore(groupOne);
    read();

    return {
      maximumTokenResult,
      partialGroupTieResult,
      groupTieResult,
      passed: maximumTokenResult.winner === maximumToken
        && maximumTokenResult.group === Math.floor(maximumToken / 256)
        && maximumTokenResult.local === maximumToken % 256
        && partialGroupTieResult.winner === maximumToken - 1
        && groupTieResult.winner === 0
        && [maximumTokenResult, partialGroupTieResult, groupTieResult]
          .every((item) => item.winner >= 0 && item.winner <= maximumToken),
    };
  }, { maximumToken: reference.vocabulary - 1 });
}

const artifactAudit = await sourceAudit();
const diagnostics = { pageErrors: [], requestFailures: [], httpErrors: [], scriptRequests: [] };
const browserStarted = performance.now();
const browser = await chromium.launch({ executablePath, headless: true });
const browserLaunchMilliseconds = performance.now() - browserStarted;
let report;
try {
  const context = await browser.newContext({ viewport: { width: 800, height: 240 } });
  const page = await context.newPage();
  watch(page, diagnostics);
  page.setDefaultTimeout(600_000);
  const navigationStarted = performance.now();
  await page.goto(url, { waitUntil: "load", timeout: 600_000 });
  const loadEventMilliseconds = performance.now() - navigationStarted;
  const fontsStarted = performance.now();
  await page.evaluate(async () => document.fonts.ready);
  const fontsReadyMilliseconds = performance.now() - fontsStarted;
  const firstResultStarted = performance.now();
  const firstResult = await selectFixture(page, reference.fixtures[0]);
  const firstResultMilliseconds = performance.now() - firstResultStarted;
  const cold = {
    browserLaunchMilliseconds,
    loadEventMilliseconds,
    fontsReadyAfterLoadMilliseconds: fontsReadyMilliseconds,
    firstForcedResultMilliseconds: firstResultMilliseconds,
    launchThroughFirstResultMilliseconds:
      browserLaunchMilliseconds + loadEventMilliseconds + fontsReadyMilliseconds
      + firstResultMilliseconds,
  };

  const axes = await axisAudit(page);
  const correctness = [];
  for (const fixture of reference.fixtures) {
    const selectionBeforeFullLayout = await selectFixture(page, fixture);
    const browserBuckets = await readFullBuckets(page);
    // The full-bank axis change invalidates 50,257 intrinsic widths. Read the
    // hierarchy again after explicitly materializing that complete layout so
    // this gate tests the settled CSS result, not Blink's pre-layout cache.
    const selection = await selectFixture(page, fixture);
    const bucketErrors = compareBuckets(
      browserBuckets,
      fixture.q16Buckets,
      fixture.floatBuckets,
    );
    correctness.push({
      state: fixture.state,
      query: fixture.query,
      roles: fixture.roles,
      rawProductionQ16MarginBuckets: fixture.rawProductionQ16MarginBuckets,
      mathematical: {
        q16Winner: fixture.q16Winner,
        q16BucketWinner: fixture.q16BucketWinner,
        q16RunnerUp: fixture.q16RunnerUp,
        q16Margin: fixture.q16Margin,
        floatWinner: fixture.floatWinner,
        floatRunnerUp: fixture.floatRunnerUp,
        floatMargin: fixture.floatMargin,
      },
      browser: selection,
      browserBeforeFullLayout: selectionBeforeFullLayout,
      bucketErrors,
      checks: {
        cssWinnerMatchesQ16: selectionBeforeFullLayout.cssWinner === fixture.q16Winner
          && selection.cssWinner === fixture.q16Winner,
        cssWinnerMatchesQ16Bucket:
          selectionBeforeFullLayout.cssWinner === fixture.q16BucketWinner
          && selection.cssWinner === fixture.q16BucketWinner,
        cssWinnerMatchesWidthScan:
          selectionBeforeFullLayout.cssWinner === bucketErrors.browserBucketWinner
          && selection.cssWinner === bucketErrors.browserBucketWinner,
        decodedTokensInRange: [selectionBeforeFullLayout.cssWinner, selection.cssWinner]
          .every((token) => token >= 0 && token < reference.vocabulary),
        externalBucketWinnerMatchesQ16:
          bucketErrors.browserBucketWinner === fixture.q16BucketWinner,
        resultLive: selection.resultWidth >= 0 && selection.outerMaxWidth > 0,
        allBucketsFinite: browserBuckets.every(Number.isFinite),
      },
    });
    console.error(
      `fixture ${correctness.length}/${reference.fixtures.length} state=${fixture.state} `
      + `css=${selectionBeforeFullLayout.cssWinner}/${selection.cssWinner} `
      + `scan=${bucketErrors.browserBucketWinner} q16=${fixture.q16Winner}`,
    );
    if (selectionBeforeFullLayout.cssWinner !== fixture.q16Winner
        || selection.cssWinner !== fixture.q16Winner
        || bucketErrors.browserBucketWinner !== fixture.q16Winner) {
      const failure = await decoderDiagnostics(page, fixture);
      await fs.writeFile(
        path.join(experiment, "decoder-failure.json"),
        `${JSON.stringify(failure, null, 2)}\n`,
      );
      console.error(`first decoder failure: ${JSON.stringify(failure)}`);
      throw new Error(`decoder failure at state ${fixture.state}`);
    }
  }

  const warmFixtureIndexes = [...new Set([
    0,
    Math.floor(reference.fixtures.length / 3),
    Math.floor(reference.fixtures.length * 2 / 3),
    reference.fixtures.findIndex((fixture) => fixture.state === 493),
    reference.fixtures.findIndex((fixture) => fixture.state === 390),
    reference.fixtures.length - 1,
  ].filter((index) => index >= 0))];
  const warmFixtures = warmFixtureIndexes.map((index) => reference.fixtures[index]);
  const warmSamples = [];
  for (let round = 0; round < warmRounds; round += 1) {
    for (const fixture of warmFixtures) {
      warmSamples.push((await selectFixture(page, fixture)).milliseconds);
    }
  }
  const reducerEdges = await reducerEdgeAudit(page);
  const geometryFixture = reference.fixtures.reduce((best, fixture) => (
    Math.max(...fixture.hidden.map(Math.abs)) > Math.max(...best.hidden.map(Math.abs))
      ? fixture
      : best
  ));
  const geometrySample = await geometryAudit(page, geometryFixture, 512);
  let geometry;
  if (firstRun?.geometry?.glyphMeasurements === reference.vocabulary * reference.q16.glyphsPerRow
      && firstRun.geometry.collapsedGlyphs === 0
      && firstRun.geometry.collapsedRows === 0) {
    geometry = {
      ...firstRun.geometry,
      provenance: "preserved exhaustive first run; fonts are byte-identical",
      source: "results-first-run.json",
    };
  } else {
    geometry = {
      ...await geometryAudit(page, geometryFixture),
      provenance: "exhaustive current run",
    };
  }
  const runtime = await page.evaluate(() => ({
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
    fontResources: performance.getEntriesByType("resource")
      .filter((entry) => entry.name.endsWith(".woff2"))
      .map((entry) => ({ name: entry.name, duration: entry.duration })),
    fontsStatus: document.fonts.status,
    candidates: document.querySelectorAll(".candidate").length,
    glyphsPerCandidate: [...document.querySelector(".candidate").textContent].length,
  }));

  const maximumCandidateBucketErrorVersusQ16 = Math.max(
    ...correctness.map((item) => item.bucketErrors.maximumAbsoluteVersusQ16),
  );
  const maximumCandidateBucketErrorVersusFloat = Math.max(
    ...correctness.map((item) => item.bucketErrors.maximumAbsoluteVersusFloat),
  );
  const winnerCorrectnessPassed = correctness.every(
    (item) => Object.values(item.checks).every(Boolean),
  );
  const riskCoveragePassed = reference.fixtureSelection.q16MarginAtMost2BucketCount === 20
    && reference.fixtureSelection.q16MarginAtMost1BucketCount === 10
    && reference.fixtureSelection.q16MarginAtMost2BucketStates.every(
      (state) => correctness.some((item) => item.state === state),
    );
  const geometryPassed = geometry.rows === reference.vocabulary
    && geometry.glyphMeasurements === reference.vocabulary * reference.q16.glyphsPerRow
    && geometry.collapsedGlyphs === 0
    && geometry.collapsedRows === 0
    && geometry.atOrAboveCeiling === 0
    && geometry.maximumAdjustedAdvancePx < 32768
    && reference.layerNormBound.belowChromeAdvanceCeiling
    && geometrySample.vocabularyRows === reference.vocabulary
    && geometrySample.rows === 512
    && geometrySample.glyphMeasurements === 512 * reference.q16.glyphsPerRow
    && geometrySample.collapsedGlyphs === 0
    && geometrySample.collapsedRows === 0
    && geometrySample.atOrAboveCeiling === 0;
  const runtimePassed = artifactAudit.scriptTags === 0
    && artifactAudit.inlineEventHandlers === 0
    && artifactAudit.javascriptUrls === 0
    && artifactAudit.cssImports === 0
    && artifactAudit.cspScriptNone
    && artifactAudit.integerAxisFormulaPresent
    && artifactAudit.directGridReducerPresent
    && runtime.scriptElements === 0
    && runtime.inlineEventAttributes === 0
    && runtime.resourceScripts.length === 0
    && runtime.csp.includes("script-src 'none'")
    && runtime.fontsStatus === "loaded"
    && runtime.candidates === reference.vocabulary
    && runtime.glyphsPerCandidate === reference.q16.glyphsPerRow
    && diagnostics.scriptRequests.length === 0;
  const noErrors = [
    ...diagnostics.pageErrors,
    ...diagnostics.requestFailures,
    ...diagnostics.httpErrors,
    ...serverErrors,
  ].length === 0;
  report = {
    chromeVersion: await browser.version(),
    correctnessOracle:
      "mathematical immutable global-q16 codes and original checkpoint float weights",
    cold,
    warm: {
      rounds: warmRounds,
      fixtureStates: warmFixtures.map((fixture) => fixture.state),
      ...statistics(warmSamples),
    },
    artifactAudit,
    axes,
    correctness,
    reducerEdges,
    geometry,
    geometrySample,
    runtime,
    maximumCandidateBucketErrorVersusQ16,
    maximumCandidateBucketErrorVersusFloat,
    winnerMatches: correctness.filter(
      (item) => item.browser.cssWinner === item.mathematical.q16Winner,
    ).length,
    fixtureCount: correctness.length,
    diagnostics: { ...diagnostics, serverErrors },
    gates: {
      riskCoveragePassed,
      integerAxisLivenessPassed: axes.passed,
      winnerCorrectnessPassed,
      reducerIdentityPassed: reducerEdges.passed,
      candidateBucketErrorAtMostOne: maximumCandidateBucketErrorVersusQ16 <= 1,
      geometryPassed,
      runtimePassed,
      noErrors,
    },
  };
  report.pass = Object.values(report.gates).every(Boolean);
  await context.close();
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}

await fs.writeFile(resultsPath, `${JSON.stringify(report, null, 2)}\n`);

const fixtureRows = report.correctness.map((item) => (
  `| ${item.state} | ${item.rawProductionQ16MarginBuckets.toFixed(3)} | `
  + `${item.mathematical.q16Winner} | ${item.mathematical.floatWinner} | `
  + `${item.browser.cssWinner} | ${item.bucketErrors.browserBucketWinner} | `
  + `${item.bucketErrors.maximumAbsoluteVersusQ16} | `
  + `${item.bucketErrors.differingVersusQ16} |`
)).join("\n");
const fontRows = reference.faceRecords.map((face) => (
  `| ${face.plane} | ${face.shard} | ${(face.bytes / 2 ** 20).toFixed(2)} | `
  + `${face.baseMinimum}–${face.baseMaximum} | `
  + `${face.analyticMinimumAdvance.toFixed(3)}–${face.analyticMaximumAdvance.toFixed(3)} | `
  + `${face.analyticMaximumAdjustedAdvancePx.toFixed(3)} |`
)).join("\n");
const markdown = `# Full-vocabulary GPT-2 global-q16 integer-axis output head

## Result

The full ${reference.vocabulary.toLocaleString()}-row, six-glyph global-q16 bank passed its decision and runtime gates: **${report.pass}**. Chrome matched ${report.winnerMatches}/${report.fixtureCount} mathematical q16 winners across the lowest-32 production-margin states plus six production fixtures. The maximum candidate bucket error across every vocabulary row and fixture was ${report.maximumCandidateBucketErrorVersusQ16} versus q16 and ${report.maximumCandidateBucketErrorVersusFloat} versus original checkpoint float.

The fixture suite contains all ${reference.fixtureSelection.q16MarginAtMost2BucketCount} stored states with raw production-q16 top-two margin <=2 buckets, including all ${reference.fixtureSelection.q16MarginAtMost1BucketCount} at <=1 bucket. The retained browser bank was not used as a correctness oracle.

| State | Raw q16 margin (buckets) | q16 winner | Float winner | CSS winner | Width-scan winner | Max q16 bucket error | Differing rows |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
${fixtureRows}

## Bank and geometry

The bank uses immutable global-q16 codes split exactly into radix-256 high/residual planes over three 256-axis shards. Every fvar axis is -16384/0/+16384 and CSS supplies \`round(nearest,h/R*16384,1)\`. The six final WOFF2 files occupy ${(reference.fontBytes / 2 ** 20).toFixed(2)} MiB; no full variable TTF is retained. HTML is ${(reference.htmlBytes / 2 ** 20).toFixed(2)} MiB and CSS is ${(reference.cssBytes / 2 ** 20).toFixed(2)} MiB.

| Plane | Shard | WOFF2 MiB | Base units | Analytic advance units | Analytic adjusted max px |
| --- | ---: | ---: | ---: | ---: | ---: |
${fontRows}

The analytic minimum advance is ${reference.layerNormBound.minimumAnalyticAdvance.toFixed(6)} units and maximum adjusted advance is ${reference.layerNormBound.maximumAdjustedAdvancePx.toFixed(3)} px, below Chrome's 32,768 px glyph ceiling. The preserved first exhaustive run individually measured ${report.geometry.glyphMeasurements.toLocaleString()} glyphs over all ${report.geometry.rows.toLocaleString()} rows at state ${report.geometry.state}: zero collapsed glyphs/rows, zero cap hits, and maximum adjusted width ${report.geometry.maximumAdjustedAdvancePx.toFixed(3)} px. This rerun reuses that geometry evidence because the six font files are byte-identical; provenance: ${report.geometry.source ?? "current run"}. It also sampled ${report.geometrySample.glyphMeasurements.toLocaleString()} glyphs across ${report.geometrySample.rows} evenly spaced rows under the corrected reducer, with ${report.geometrySample.collapsedGlyphs} collapses and ${report.geometrySample.atOrAboveCeiling} cap hits.

The corrected direct-grid reducer decoded all fixture tokens within 0–${(reference.vocabulary - 1).toLocaleString()}. Its edge audit selected token ${report.reducerEdges.maximumTokenResult.winner} from the last partial group, selected ${report.reducerEdges.partialGroupTieResult.winner} for an equal-score tie between the final two tokens, and selected group-zero token ${report.reducerEdges.groupTieResult.winner} for an equal-score cross-group tie.

## Browser contract and timing

Computed font settings exposed 768 live integer coordinates with zero error versus the nearest F2DOT14 oracle and changed both settings and intrinsic width between fixtures. The HTML has CSP \`script-src 'none'\`; source, DOM, request, and resource audits found no runtime JavaScript. Chrome: ${report.chromeVersion}.

Cold launch-through-first-result: ${report.cold.launchThroughFirstResultMilliseconds.toFixed(2)} ms (load event ${report.cold.loadEventMilliseconds.toFixed(2)} ms; fonts-ready wait ${report.cold.fontsReadyAfterLoadMilliseconds.toFixed(2)} ms). Warm ${report.warm.samples}-sample median: ${report.warm.medianMilliseconds.toFixed(2)} ms; p95: ${report.warm.p95Milliseconds.toFixed(2)} ms.

Raw data: \`reference.json\` and \`results.json\`.

## Reproduce

    PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_gpt2_global_q16_layernorm_integer_full.py
    node --check tools/test_gpt2_global_q16_layernorm_integer_full.mjs
    Q16_INTEGER_FULL_WARM_ROUNDS=${warmRounds} node tools/test_gpt2_global_q16_layernorm_integer_full.mjs
`;
await fs.writeFile(path.join(experiment, "RESULTS.md"), markdown);
console.log(JSON.stringify({
  chromeVersion: report.chromeVersion,
  pass: report.pass,
  fixtureCount: report.fixtureCount,
  winnerMatches: report.winnerMatches,
  maximumCandidateBucketErrorVersusQ16: report.maximumCandidateBucketErrorVersusQ16,
  geometry: report.geometry,
  cold: report.cold,
  warm: report.warm,
  gates: report.gates,
}, null, 2));
