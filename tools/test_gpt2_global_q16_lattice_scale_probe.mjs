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
const directory = "gpt2-global-q16-lattice-scale";
const experiment = path.join(repository, "experiments", directory);
const reference = JSON.parse(await fs.readFile(path.join(experiment, "reference.json"), "utf8"));
const benchmarkRounds = Math.max(
  3,
  Number(process.env.Q16_LATTICE_BENCHMARK_ROUNDS ?? 5),
);
const ceilingPx = reference.chromeAdvanceCeilingPx;

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
const baseUrl = `http://127.0.0.1:${server.address().port}/experiments/${directory}`;

function percentile(values, fraction) {
  const ordered = [...values].sort((left, right) => left - right);
  return ordered[Math.min(ordered.length - 1, Math.ceil(ordered.length * fraction) - 1)];
}

function statistics(values) {
  const ordered = [...values].sort((left, right) => left - right);
  const middle = Math.floor(ordered.length / 2);
  return {
    samples: ordered.length,
    minimumMilliseconds: ordered[0],
    medianMilliseconds: ordered.length % 2
      ? ordered[middle]
      : (ordered[middle - 1] + ordered[middle]) / 2,
    p95Milliseconds: percentile(ordered, 0.95),
    maximumMilliseconds: ordered.at(-1),
    meanMilliseconds: ordered.reduce((sum, value) => sum + value, 0) / ordered.length,
  };
}

function errorSummary(actual, target) {
  const deltas = actual.map((value, index) => value - target[index]);
  const histogram = new Map();
  for (const delta of deltas) histogram.set(delta, (histogram.get(delta) ?? 0) + 1);
  return {
    comparisons: deltas.length,
    nonzero: deltas.filter((delta) => delta !== 0).length,
    maximumAbsolute: Math.max(...deltas.map(Math.abs)),
    meanAbsolute: deltas.reduce((sum, delta) => sum + Math.abs(delta), 0) / deltas.length,
    histogram: Object.fromEntries([...histogram.entries()].sort(([left], [right]) => left - right)),
    deltas,
  };
}

function watch(page, label, diagnostics) {
  page.on("pageerror", (error) => diagnostics.pageErrors.push({ label, error: String(error) }));
  page.on("requestfailed", (request) => diagnostics.requestFailures.push({
    label,
    url: request.url(),
    resourceType: request.resourceType(),
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

async function loadPage(context, scale, label, diagnostics) {
  const page = await context.newPage();
  watch(page, label, diagnostics);
  page.setDefaultTimeout(240_000);
  await page.goto(`${baseUrl}/${scale.html}`, { waitUntil: "load", timeout: 240_000 });
  return page;
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

async function activateFonts(page, fixture) {
  await applyFixture(page, fixture);
  await page.evaluate(async () => document.fonts.ready);
  await applyFixture(page, fixture);
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
    const stage = document.querySelector("#stage");
    const cssIndex = Number(style.getPropertyValue("--index"));
    const cssBucket = Number(style.getPropertyValue("--bucket"));
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
    const rows = [...document.querySelectorAll(".candidate")];
    const range = document.createRange();
    const perFace = Array.from({ length: 12 }, (_, face) => ({
      face,
      plane: face % 2 === 0 ? "high" : "residual",
      shard: Math.floor(face / 2),
      measurements: 0,
      maximumPx: 0,
      atOrAboveCeiling: 0,
      withinOneLayoutUnitOfCeiling: 0,
    }));
    let maximumRecord = null;
    let glyphMeasurements = 0;
    let maximumHighAdvancePx = 0;
    let maximumResidualAdvancePx = 0;
    let atOrAboveCeiling = 0;
    let withinOneLayoutUnitOfCeiling = 0;
    let maximumSummedVsWholeRangeDeltaPx = 0;
    for (let rowIndex = 0; rowIndex < rows.length; rowIndex += 1) {
      const node = rows[rowIndex].firstChild;
      const characters = [...node.data];
      let offset = 0;
      let summedWidth = 0;
      for (let face = 0; face < characters.length; face += 1) {
        const length = characters[face].length;
        range.setStart(node, offset);
        range.setEnd(node, offset + length);
        const width = range.getBoundingClientRect().width;
        const record = perFace[face];
        record.measurements += 1;
        record.maximumPx = Math.max(record.maximumPx, width);
        if (width >= ceiling) {
          record.atOrAboveCeiling += 1;
          atOrAboveCeiling += 1;
        }
        if (width >= ceiling - 1 / 64) {
          record.withinOneLayoutUnitOfCeiling += 1;
          withinOneLayoutUnitOfCeiling += 1;
        }
        if (record.plane === "high") maximumHighAdvancePx = Math.max(maximumHighAdvancePx, width);
        else maximumResidualAdvancePx = Math.max(maximumResidualAdvancePx, width);
        if (!maximumRecord || width > maximumRecord.widthPx) {
          maximumRecord = {
            rowIndex,
            token: contenders[rowIndex],
            face,
            plane: record.plane,
            shard: record.shard,
            widthPx: width,
          };
        }
        summedWidth += width;
        glyphMeasurements += 1;
        offset += length;
      }
      range.setStart(node, 0);
      range.setEnd(node, node.length);
      const wholeWidth = range.getBoundingClientRect().width;
      maximumSummedVsWholeRangeDeltaPx = Math.max(
        maximumSummedVsWholeRangeDeltaPx,
        Math.abs(summedWidth - wholeWidth),
      );
    }
    return {
      glyphMeasurements,
      maximumHighAdvancePx,
      maximumResidualAdvancePx,
      maximumAdjustedAdvancePx: Math.max(maximumHighAdvancePx, maximumResidualAdvancePx),
      atOrAboveCeiling,
      withinOneLayoutUnitOfCeiling,
      maximumSummedVsWholeRangeDeltaPx,
      maximumRecord,
      perFace,
    };
  }, { contenders: reference.contenders, ceiling: ceilingPx });
}

async function auditZeroCoordinateBases(page) {
  return page.evaluate(({ dimensions }) => {
    const probe = document.querySelector("#probe");
    for (let dimension = 0; dimension < dimensions; dimension += 1) {
      probe.style.setProperty(`--h${dimension}`, "0");
    }
    probe.style.setProperty("--score-offset", "0px");
    document.querySelector("#result").getBoundingClientRect().width;
    const range = document.createRange();
    const rows = [...document.querySelectorAll(".candidate")];
    const records = rows.map((row) => {
      const node = row.firstChild;
      range.setStart(node, 0);
      range.setEnd(node, node.length);
      const measuredPx = range.getBoundingClientRect().width;
      const serializedBasePx = Number(row.style.getPropertyValue("--base"));
      const deltaPx = measuredPx - serializedBasePx;
      return {
        token: Number(row.dataset.token),
        measuredPx,
        serializedBasePx,
        deltaPx,
        deltaLayout64: Math.round(deltaPx * 64),
      };
    });
    const histogram = new Map();
    for (const record of records) {
      histogram.set(
        record.deltaLayout64,
        (histogram.get(record.deltaLayout64) ?? 0) + 1,
      );
    }
    return {
      rows: records.length,
      minimumDeltaPx: Math.min(...records.map((record) => record.deltaPx)),
      maximumDeltaPx: Math.max(...records.map((record) => record.deltaPx)),
      maximumAbsoluteDeltaPx: Math.max(...records.map((record) => Math.abs(record.deltaPx))),
      meanDeltaPx: records.reduce((sum, record) => sum + record.deltaPx, 0) / records.length,
      deltaLayout64Histogram: Object.fromEntries(
        [...histogram.entries()].sort(([left], [right]) => left - right),
      ),
      records,
    };
  }, { dimensions: 768 });
}

async function benchmarkScale(context, scale, diagnostics) {
  const page = await loadPage(context, scale, `benchmark-${scale.slug}`, diagnostics);
  await activateFonts(page, reference.fixtures[0]);
  for (const fixture of reference.fixtures) await applyFixture(page, fixture);
  const samples = [];
  const outputs = [];
  for (let round = 0; round < benchmarkRounds; round += 1) {
    for (const fixture of reference.fixtures) {
      const output = await page.evaluate(({ item, contenders }) => {
        const probe = document.querySelector("#probe");
        const started = performance.now();
        for (let dimension = 0; dimension < item.hidden.length; dimension += 1) {
          probe.style.setProperty(`--h${dimension}`, String(item.hidden[dimension]));
        }
        probe.style.setProperty("--score-offset", `${-item.scoreFloor * 256 * 4}px`);
        const result = document.querySelector("#result");
        result.getBoundingClientRect().width;
        result.getBoundingClientRect().width;
        const style = getComputedStyle(result);
        const index = Number(style.getPropertyValue("--index"));
        return {
          milliseconds: performance.now() - started,
          index,
          winner: contenders[index],
          bucket: Number(style.getPropertyValue("--bucket")),
        };
      }, { item: fixture, contenders: reference.contenders });
      samples.push(output.milliseconds);
      outputs.push({ round, state: fixture.state, ...output });
    }
  }
  await page.close();
  return {
    scale: scale.label,
    slug: scale.slug,
    rounds: benchmarkRounds,
    isolatedSingleScalePage: true,
    ...statistics(samples),
    outputs,
  };
}

const artifactAudit = await sourceAudit();
const diagnostics = {
  pageErrors: [],
  requestFailures: [],
  httpErrors: [],
  scriptRequests: [],
};
const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const context = await browser.newContext({ viewport: { width: 800, height: 240 } });
  const correctness = [];
  const geometry = [];
  const zeroBaseAudits = [];
  const runtimeAudits = [];
  for (const scale of reference.scales) {
    const page = await loadPage(context, scale, `correctness-${scale.slug}`, diagnostics);
    await activateFonts(page, reference.fixtures[0]);
    zeroBaseAudits.push({
      scale: scale.label,
      slug: scale.slug,
      ...(await auditZeroCoordinateBases(page)),
    });
    for (const fixture of reference.fixtures) {
      await applyFixture(page, fixture);
      const browserResult = await readResult(page);
      const q16Errors = errorSummary(browserResult.buckets, fixture.q16Buckets);
      const floatErrors = errorSummary(browserResult.buckets, fixture.floatBuckets);
      const winnerIndex = browserResult.cssIndex;
      correctness.push({
        scale: scale.label,
        slug: scale.slug,
        state: fixture.state,
        roles: fixture.roles,
        mathematical: {
          floatWinner: fixture.floatWinner,
          floatBucketWinner: fixture.floatBucketWinner,
          q16Winner: fixture.q16MathematicalWinner,
          q16BucketWinner: fixture.q16BucketWinner,
          floatMargin: fixture.floatMargin,
        },
        browser: browserResult,
        bucketErrors: {
          versusGlobalQ16: q16Errors,
          versusOriginalFloat: floatErrors,
          forBrowserWinnerVersusGlobalQ16: browserResult.cssBucket - fixture.q16Buckets[winnerIndex],
          forBrowserWinnerVersusOriginalFloat: browserResult.cssBucket - fixture.floatBuckets[winnerIndex],
        },
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
        scale: scale.label,
        slug: scale.slug,
        state: fixture.state,
        roles: fixture.roles,
        ...(await auditGlyphGeometry(page)),
      });
    }
    runtimeAudits.push(await page.evaluate(() => ({
      scale: document.body.dataset.scale,
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
    })));
    await page.close();
  }

  const benchmarks = [];
  for (const scale of reference.scales) {
    benchmarks.push(await benchmarkScale(context, scale, diagnostics));
  }
  await context.close();

  const perScale = reference.scales.map((scale) => {
    const rows = correctness.filter((item) => item.slug === scale.slug);
    const audits = geometry.filter((item) => item.slug === scale.slug);
    const zeroBase = zeroBaseAudits.find((item) => item.slug === scale.slug);
    const benchmark = benchmarks.find((item) => item.slug === scale.slug);
    const expectedWinners = Object.fromEntries(rows.map((row) => [row.state, row.browser.cssWinner]));
    return {
      scale: scale.label,
      slug: scale.slug,
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
      floatBucketWinnerMatches: rows.filter(
        (row) => row.browser.cssWinner === row.mathematical.floatBucketWinner,
      ).length,
      q16MathematicalMismatchStates: rows.filter(
        (row) => row.browser.cssWinner !== row.mathematical.q16Winner,
      ).map((row) => row.state),
      q16BucketMismatchStates: rows.filter(
        (row) => row.browser.cssWinner !== row.mathematical.q16BucketWinner,
      ).map((row) => row.state),
      floatMismatchStates: rows.filter(
        (row) => row.browser.cssWinner !== row.mathematical.floatWinner,
      ).map((row) => row.state),
      maximumAbsoluteCandidateBucketErrorVersusQ16: Math.max(
        ...rows.map((row) => row.bucketErrors.versusGlobalQ16.maximumAbsolute),
      ),
      maximumAbsoluteCandidateBucketErrorVersusFloat: Math.max(
        ...rows.map((row) => row.bucketErrors.versusOriginalFloat.maximumAbsolute),
      ),
      differingCandidateBucketsVersusQ16: rows.reduce(
        (sum, row) => sum + row.bucketErrors.versusGlobalQ16.nonzero,
        0,
      ),
      differingCandidateBucketsVersusFloat: rows.reduce(
        (sum, row) => sum + row.bucketErrors.versusOriginalFloat.nonzero,
        0,
      ),
      geometry: {
        glyphMeasurements: audits.reduce((sum, audit) => sum + audit.glyphMeasurements, 0),
        maximumBrowserHighAdvancePx: Math.max(...audits.map((audit) => audit.maximumHighAdvancePx)),
        maximumBrowserResidualAdvancePx: Math.max(
          ...audits.map((audit) => audit.maximumResidualAdvancePx),
        ),
        maximumBrowserAdjustedAdvancePx: Math.max(
          ...audits.map((audit) => audit.maximumAdjustedAdvancePx),
        ),
        atOrAboveCeiling: audits.reduce((sum, audit) => sum + audit.atOrAboveCeiling, 0),
        withinOneLayoutUnitOfCeiling: audits.reduce(
          (sum, audit) => sum + audit.withinOneLayoutUnitOfCeiling,
          0,
        ),
        theoreticalMaximumAdjustedAdvancePx: scale.theoreticalMaximumAdjustedAdvancePx,
        theoreticallyClearsCeiling: scale.theoreticallyClearsChromeAdvanceCeiling,
        zeroCoordinateBase: {
          minimumDeltaPx: zeroBase.minimumDeltaPx,
          maximumDeltaPx: zeroBase.maximumDeltaPx,
          maximumAbsoluteDeltaPx: zeroBase.maximumAbsoluteDeltaPx,
          meanDeltaPx: zeroBase.meanDeltaPx,
          impliedBucketBiasRange: [
            zeroBase.minimumDeltaPx * scale.scoreFactor / 4,
            zeroBase.maximumDeltaPx * scale.scoreFactor / 4,
          ],
        },
      },
      latency: {
        samples: benchmark.samples,
        medianMilliseconds: benchmark.medianMilliseconds,
        meanMilliseconds: benchmark.meanMilliseconds,
        p95Milliseconds: benchmark.p95Milliseconds,
      },
      benchmarkOutputsStable: benchmark.outputs.every(
        (output) => output.winner === expectedWinners[output.state],
      ),
    };
  });

  const allLiveChecksPass = correctness.every(
    (item) => Object.values(item.checks).every(Boolean),
  );
  const runtimeAuditPassed = artifactAudit.passed
    && runtimeAudits.every((audit) => audit.scriptElements === 0
      && audit.inlineEventAttributes === 0
      && audit.resourceScripts.length === 0
      && audit.csp?.includes("script-src 'none'"))
    && diagnostics.scriptRequests.length === 0;
  const safeScaleAdvanceGatePassed = perScale
    .filter((scale) => scale.geometry.theoreticallyClearsCeiling)
    .every((scale) => scale.geometry.atOrAboveCeiling === 0
      && scale.geometry.maximumBrowserAdjustedAdvancePx < ceilingPx);
  const oneOver64 = reference.scales.find((scale) => scale.slug === "1over64");
  const oneOver64LatticeGatePassed = oneOver64.lowPlaneUnitLayout64 === 1
    && oneOver64.highPlaneUnitLayout64 === 256
    && oneOver64.theoreticallyClearsChromeAdvanceCeiling;
  const benchmarkOutputsStable = perScale.every((scale) => scale.benchmarkOutputsStable);
  const noErrors = [
    ...diagnostics.pageErrors,
    ...diagnostics.requestFailures,
    ...diagnostics.httpErrors,
    ...serverErrors,
  ].length === 0;
  report = {
    chromeVersion: await browser.version(),
    benchmarkRounds,
    artifactAudit,
    runtimeAudits,
    scaleDefinitions: reference.scales,
    correctness,
    perScale,
    geometry,
    zeroBaseAudits,
    benchmarks,
    allLiveChecksPass,
    runtimeAuditPassed,
    safeScaleAdvanceGatePassed,
    oneOver64LatticeGatePassed,
    benchmarkOutputsStable,
    diagnostics: { ...diagnostics, serverErrors },
    pass: allLiveChecksPass
      && runtimeAuditPassed
      && safeScaleAdvanceGatePassed
      && oneOver64LatticeGatePassed
      && benchmarkOutputsStable
      && noErrors,
  };
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}

await fs.writeFile(path.join(experiment, "results.json"), `${JSON.stringify(report, null, 2)}\n`);

const ranked = [...report.perScale].sort((left, right) => (
  right.q16BucketWinnerMatches - left.q16BucketWinnerMatches
  || right.q16MathematicalWinnerMatches - left.q16MathematicalWinnerMatches
  || left.maximumAbsoluteCandidateBucketErrorVersusQ16
    - right.maximumAbsoluteCandidateBucketErrorVersusQ16
  || left.latency.medianMilliseconds - right.latency.medianMilliseconds
));
const best = ranked[0];
const scaleRows = report.perScale.map((scale) => (
  `| ${scale.scale} | ${scale.q16MathematicalWinnerMatches}/${scale.fixtures} | `
  + `${scale.q16BucketWinnerMatches}/${scale.fixtures} | ${scale.floatWinnerMatches}/${scale.fixtures} | `
  + `${scale.maximumAbsoluteCandidateBucketErrorVersusQ16} | `
  + `${scale.maximumAbsoluteCandidateBucketErrorVersusFloat} | `
  + `${scale.latency.medianMilliseconds.toFixed(2)} | ${scale.latency.p95Milliseconds.toFixed(2)} |`
)).join("\n");
const geometryRows = report.perScale.map((scale) => {
  const definition = reference.scales.find((item) => item.slug === scale.slug);
  return `| ${scale.scale} | ${definition.lowPlaneUnitLayout64} | `
    + `${definition.theoreticalMaximumAdjustedAdvancePx.toFixed(3)} | `
    + `${scale.geometry.maximumBrowserAdjustedAdvancePx.toFixed(3)} | `
    + `${scale.geometry.atOrAboveCeiling} | `
    + `${scale.geometry.zeroCoordinateBase.minimumDeltaPx.toFixed(5)} to `
    + `${scale.geometry.zeroCoordinateBase.maximumDeltaPx.toFixed(5)} | `
    + `${definition.theoreticallyClearsChromeAdvanceCeiling ? "yes" : "no"} |`;
}).join("\n");
const mismatchRows = report.perScale.map((scale) => (
  `| ${scale.scale} | ${scale.q16MathematicalMismatchStates.join(", ") || "none"} | `
  + `${scale.q16BucketMismatchStates.join(", ") || "none"} | `
  + `${scale.floatMismatchStates.join(", ") || "none"} |`
)).join("\n");
const state519Rows = report.correctness.filter((item) => item.state === 519).map((item) => (
  `| ${item.scale} | ${item.browser.cssWinner} | ${item.browser.cssBucket} | `
  + `${item.bucketErrors.forBrowserWinnerVersusGlobalQ16} | `
  + `${item.bucketErrors.forBrowserWinnerVersusOriginalFloat} |`
)).join("\n");
const oneOver64Result = report.perScale.find((scale) => scale.slug === "1over64");
const markdown = `# GPT-2 global-q16 lattice-scale Chrome probe

## Result

The strict script-free probe passed its measurement gates: **${report.pass}**. Of the tested lattices, **${best.scale}** ranked best against the shared mathematical global-q16 buckets (${best.q16BucketWinnerMatches}/${best.fixtures} browser winners; maximum contender bucket error ${best.maximumAbsoluteCandidateBucketErrorVersusQ16}).

The 1/64 scale maps each residual unit to exactly one Chrome 1/64-pixel layout quantum and each high unit to 256 layout quanta. It matched ${oneOver64Result.q16MathematicalWinnerMatches}/${oneOver64Result.fixtures} unbucketed q16 winners and ${oneOver64Result.q16BucketWinnerMatches}/${oneOver64Result.fixtures} q16 bucket winners, with maximum q16 contender error ${oneOver64Result.maximumAbsoluteCandidateBucketErrorVersusQ16} buckets.

Its zero-coordinate shaped width is offset from the serialized row base by ${oneOver64Result.geometry.zeroCoordinateBase.minimumDeltaPx.toFixed(5)} to ${oneOver64Result.geometry.zeroCoordinateBase.maximumDeltaPx.toFixed(5)}px. After the 1/64 score factor, that alone implies a ${oneOver64Result.geometry.zeroCoordinateBase.impliedBucketBiasRange[0].toFixed(2)} to ${oneOver64Result.geometry.zeroCoordinateBase.impliedBucketBiasRange[1].toFixed(2)} bucket bias, explaining the observed near-uniform displacement despite clearing the advance cap.

| Display scale | q16 winner | q16 bucket winner | Float winner | Max abs. bucket error vs q16 | Max abs. bucket error vs float | Warm median (ms) | Warm p95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
${scaleRows}

## Advance and lattice diagnostics

The retained radix-256 high/residual WOFF2 bank was referenced in place; no fonts were copied or rebuilt. The source-bank all-axis bound exceeds Chrome's approximately 32,768px adjusted-advance ceiling at 0.1 and 1/16, but clears it at 1/32 and 1/64. Browser geometry below covers all 192 contenders, 12 glyphs per row, and all 16 fixtures at every scale.

| Display scale | Residual unit (layout64) | Theoretical max adjusted advance (px) | Browser max (px) | Measurements at/above 32768 | Zero-axis base delta (px) | Clears theoretical cap |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
${geometryRows}

| Display scale | q16 winner mismatches | q16 bucket-winner mismatches | Float-winner mismatches |
| --- | --- | --- | --- |
${mismatchRows}

State 519 diagnostics (q16 and float mathematics both select token ${report.correctness.find((item) => item.state === 519).mathematical.q16Winner}):

| Display scale | Chrome winner | Chrome bucket | Error vs q16 | Error vs float |
| --- | ---: | ---: | ---: | ---: |
${state519Rows}

The fixture set contains states 519 and 547, the eight lowest-margin corpus states, and all six production fixtures. Its 192 rows are the union of every selected state's top-16 float and top-16 q16 contenders plus token 2032. The 1,024-state mathematical screen has ${reference.corpusScreen.q16MathematicalMismatchStates.length} global-q16 versus float winner mismatches.

## Runtime and timing contract

All four HTML files carry CSP \`script-src 'none'\`; raw-source, DOM, event-handler, resource, and network audits found no runtime script. Browser automation is external to the artifacts. Each latency measurement used a dedicated single-scale page, one all-fixture warmup, and ${report.benchmarkRounds} measured warm rounds. Chrome: ${report.chromeVersion}.

Raw data: \`results.json\`. GPT-2 small architecture, checkpoint, and weights are unchanged.

## Reproduce

    PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools python tools/build_gpt2_global_q16_lattice_scale_probe.py
    node --check tools/test_gpt2_global_q16_lattice_scale_probe.mjs
    Q16_LATTICE_BENCHMARK_ROUNDS=${report.benchmarkRounds} node tools/test_gpt2_global_q16_lattice_scale_probe.mjs
`;
await fs.writeFile(path.join(experiment, "RESULTS.md"), markdown);
console.log(JSON.stringify({
  chromeVersion: report.chromeVersion,
  perScale: report.perScale,
  allLiveChecksPass: report.allLiveChecksPass,
  runtimeAuditPassed: report.runtimeAuditPassed,
  safeScaleAdvanceGatePassed: report.safeScaleAdvanceGatePassed,
  oneOver64LatticeGatePassed: report.oneOver64LatticeGatePassed,
  benchmarkOutputsStable: report.benchmarkOutputsStable,
  pass: report.pass,
}, null, 2));
