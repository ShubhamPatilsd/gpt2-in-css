#!/usr/bin/env node
/* Verify the groupwise-Cauchy bounds inside the retained six-stage head. */

import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const workspace = path.resolve(new URL("..", import.meta.url).pathname);
const experiment = process.env.GROUPWISE_CASCADE_DIRECTORY
  ?? "gpt2-groupwise-cauchy-blockflow-cascade";
const output = path.join(workspace, "experiments", experiment);
const reference = JSON.parse(await fs.readFile(path.join(output, "reference.json"), "utf8"));
const exactControl = reference.exactControl
  ?? `gpt2-hvar-grid-output-head-certified-int10-unrolled${reference.stages}-gated`;
const exactControlFilename = reference.exactControlFilename ?? "index.html";
const retained = reference.sourceRetained;
const fixtures = reference.certifiedFixtures;
const groupwise = reference.groupwiseFixtures;
const stages = reference.stages;
const tolerance = 0.03;
const fixtureCount = fixtures.hiddenVectors.length;
const timingFixtures = [...new Set([0, 1, fixtureCount - 2, fixtureCount - 1])]
  .filter((fixture) => fixture >= 0 && fixture < fixtureCount);
const compareRetainedPerformance = process.env.GROUPWISE_COMPARE_RETAINED === "1"
  || reference.productionInputRange === undefined;

function statistics(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return {
    count: values.length,
    minimum: sorted[0],
    median: sorted[Math.floor(sorted.length / 2)],
    maximum: sorted.at(-1),
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

const types = new Map([[".html", "text/html"], [".css", "text/css"], [".woff2", "font/woff2"]]);
const server = http.createServer(async (request, response) => {
  try {
    const filename = path.join(workspace, decodeURIComponent(new URL(request.url, "http://x").pathname));
    if (!filename.startsWith(`${workspace}${path.sep}`)) throw new Error("outside workspace");
    const body = await fs.readFile(filename);
    response.writeHead(200, {
      "content-type": types.get(path.extname(filename)) ?? "application/octet-stream",
      "cache-control": "no-store",
    });
    response.end(body);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const baseUrl = `http://127.0.0.1:${server.address().port}`;

async function loadPage(context, directory, filename = "index.html") {
  const page = await context.newPage();
  page.setDefaultTimeout(900_000);
  const failures = [];
  page.on("requestfailed", (request) => failures.push({
    url: request.url(), error: request.failure()?.errorText ?? "unknown",
  }));
  const started = performance.now();
  await page.goto(`${baseUrl}/experiments/${directory}/${filename}`, {
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

async function settleMixed(page) {
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

async function settleExact(page) {
  for (let pass = 0; pass < 3; pass += 1) {
    for (const selector of ["#result", "#fine-stage", "#fine-result"]) {
      await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
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
          await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
        }
      }
    }
  }
}

async function observeMixed(page, includeGeometry = false) {
  return page.evaluate(({ stageCount, geometry }) => {
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
        dynamicDisplay: dynamic.display,
        fineBucket: number(fine, `--fine-bucket-${stage}`),
        fineWinner: number(fine, `--fine-winner-${stage}`),
        bestBucket: number(fine, `--best-bucket-${stage}`),
        bestWinner: number(fine, `--best-winner-${stage}`),
        nextUpperBucket: number(remaining, `--upper-bucket-${stage + 1}`),
        certificateGap: number(remaining, `--certificate-gap-${stage}`),
        done: number(remaining, `--done-${stage}`),
      };
      observations.push(item);
      if (item.done === 1) break;
      group = number(remaining, `--remaining-group-${stage + 1}`);
    }
    const result = {
      stages: observations,
      activeStages: observations.length,
      finalWinner: observations.at(-1)?.bestWinner,
      scripts: document.querySelectorAll("script").length,
    };
    if (geometry) {
      result.groupWidths = [...document.querySelectorAll(".group-wrapper")]
        .map((element) => element.getBoundingClientRect().width);
      result.boundWidths = [...document.querySelectorAll(".group-bound")]
        .map((element) => ({
          group: Number(element.dataset.group),
          width: element.getBoundingClientRect().width,
        }));
      const modelStyle = getComputedStyle(document.querySelector(".cascade"));
      const boundStyle = getComputedStyle(document.querySelector(".group-bound"));
      result.blockNorms = Array.from(
        { length: 96 }, (_, index) => Number(modelStyle.getPropertyValue(`--bn${index}`)),
      );
      result.boundVariation = boundStyle.fontVariationSettings;
      result.boundAxisCount = (result.boundVariation.match(/"/g) ?? []).length / 2;
    }
    return result;
  }, { stageCount: stages, geometry: includeGeometry });
}

async function groupWidths(page) {
  return page.locator(".group-wrapper").evaluateAll(
    (elements) => elements.map((element) => element.getBoundingClientRect().width),
  );
}

async function forceExactShadow(page, group) {
  const stage = page.locator("#fine-stage");
  await stage.evaluate((element, value) => element.style.setProperty("--group", String(value)), group);
  for (let pass = 0; pass < 3; pass += 1) {
    for (const selector of ["#fine-stage", ".fine-reader", "#fine-result"]) {
      await page.locator(selector).first().evaluate((element) => element.getBoundingClientRect().width);
    }
  }
  const shadow = await page.locator("#fine-result").evaluate((element, value) => {
    const style = getComputedStyle(element);
    const fineBucket = Number(style.getPropertyValue("--fine-bucket"));
    const fineLocal = Number(style.getPropertyValue("--fine-local"));
    return { group: value, fineBucket, fineWinner: value * 256 + fineLocal };
  }, group);
  await stage.evaluate((element) => element.style.removeProperty("--group"));
  return shadow;
}

function expectedRoute(widths, count) {
  const remaining = new Set(widths.map((_, group) => group));
  const route = [];
  for (let stage = 0; stage < count; stage += 1) {
    let selected = -1;
    let maximum = -Infinity;
    for (const group of remaining) {
      if (widths[group] > maximum + tolerance) {
        selected = group;
        maximum = widths[group];
      }
    }
    route.push(selected);
    remaining.delete(selected);
  }
  return route;
}

const diagnostics = { candidate: [], retained: [], exact: [] };
const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const candidateContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const coarseContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const retainedContext = compareRetainedPerformance
    ? await browser.newContext({ viewport: { width: 800, height: 200 } }) : null;
  const exactContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const candidateLoad = await loadPage(candidateContext, experiment);
  const coarseLoad = await loadPage(coarseContext, experiment, "control.html");
  const retainedLoad = retainedContext ? await loadPage(retainedContext, retained) : null;
  const exactLoad = await loadPage(exactContext, exactControl, exactControlFilename);
  diagnostics.candidate.push(...candidateLoad.failures);
  if (retainedLoad) diagnostics.retained.push(...retainedLoad.failures);
  diagnostics.exact.push(...exactLoad.failures);

  const checks = [];
  for (let fixture = 0; fixture < fixtures.hiddenVectors.length; fixture += 1) {
    await setInput(coarseLoad.page, fixture);
    await settleMixed(coarseLoad.page);
    const controlWidths = await groupWidths(coarseLoad.page);
    const composed = controlWidths.map(
      (width, group) => width + groupwise.predictedBoundWidths[fixture][group],
    );

    await setInput(candidateLoad.page, fixture);
    await settleMixed(candidateLoad.page);
    const observed = await observeMixed(candidateLoad.page, true);
    // A live bound glyph may round one bucket farther outward than the offline
    // prediction. Route against the measured conservative widths; requiring
    // the predicted order would reject a safe tie reordering.
    const route = expectedRoute(observed.groupWidths, stages);

    await setInput(exactLoad.page, fixture);
    await settleExact(exactLoad.page);
    const shadows = new Map();
    for (const group of new Set(observed.stages.map((stage) => stage.group))) {
      shadows.set(group, await forceExactShadow(exactLoad.page, group));
    }

    let bestBucket = -Infinity;
    let bestWinner = Infinity;
    const stageChecks = observed.stages.map((stage, index) => {
      const shadow = shadows.get(stage.group);
      if (stage.fineBucket > bestBucket ||
          (stage.fineBucket === bestBucket && stage.fineWinner < bestWinner)) {
        bestBucket = stage.fineBucket;
        bestWinner = stage.fineWinner;
      }
      const nextGroup = route[index + 1];
      const expectedNextUpper = nextGroup === undefined
        ? null : Math.floor(composed[nextGroup] / 4);
      const upperTransportShortfall = reference.upperTransportShortfallBuckets ?? 0;
      return {
        stage: index,
        groupMatchesCompositionOracle: stage.group === route[index],
        fineBucketMatchesExactShadow: stage.group <= 1
          ? Math.abs(stage.fineBucket - shadow.fineBucket) <= reference.hotUpperAllowanceBuckets
          : stage.fineBucket === shadow.fineBucket,
        fineWinnerMatchesExactShadow: stage.fineWinner === shadow.fineWinner,
        bestBucketMatchesLiveRecompute: stage.bestBucket === bestBucket,
        bestWinnerMatchesLiveRecompute: stage.bestWinner === bestWinner,
        nextUpperMatchesCompositionOracle: expectedNextUpper === null
          || stage.nextUpperBucket + upperTransportShortfall >= expectedNextUpper,
        gapArithmeticMatches: stage.certificateGap === stage.bestBucket - stage.nextUpperBucket,
        doneMatchesGap: stage.done === Number(stage.certificateGap > reference.stopGapBuckets),
        routeDisplayMatches: stage.group <= 1
          ? stage.dynamicDisplay === "none" : stage.dynamicDisplay === "grid",
      };
    });
    const expectedGroups = route.slice(0, observed.activeStages);
    const groupDeltas = observed.groupWidths.map((value, group) => value - composed[group]);
    const predictedCoarse = groupwise.predictedCoarseWidths?.[fixture] ?? null;
    const coarseGroups = reference.selectivePrecision?.groups
      ?? Array.from({ length: reference.groups - 2 }, (_, index) => index + 2);
    const coarseDeltas = predictedCoarse
      ? coarseGroups.map((group) => controlWidths[group] - predictedCoarse[group]) : null;
    const coarseAllowancePixels = (
      reference.selectivePrecision?.transportAllowanceBuckets ?? 0
    ) * 4;
    const boundByGroup = new Map(observed.boundWidths.map((item) => [item.group, item.width]));
    let exactBounds = 0;
    let oneBucketOutward = 0;
    let unsafeBounds = 0;
    for (let group = 2; group < reference.groups; group += 1) {
      const measured = boundByGroup.get(group);
      const predicted = groupwise.predictedBoundWidths[fixture][group];
      const certified = groupwise.certifiedRadiusPixels[fixture][group];
      if (Math.abs(measured - predicted) <= tolerance) exactBounds += 1;
      else if (Math.abs(measured - predicted - 4) <= tolerance) oneBucketOutward += 1;
      else unsafeBounds += 1;
      if (measured + tolerance < certified) unsafeBounds += 1;
    }
    const firstDone = observed.stages.findIndex((stage) => stage.done === 1);
    const check = {
      fixture,
      expectedGroups,
      measuredGroups: observed.stages.map((stage) => stage.group),
      stageChecks,
      groupCompositionMatches: groupDeltas.every(
        (delta) => delta >= -tolerance && delta <= 4 + tolerance,
      ),
      maximumGroupCompositionDelta: Math.max(...groupDeltas.map(Math.abs)),
      coarseTransportConservative: coarseDeltas
        ? coarseDeltas.every((delta) => delta + coarseAllowancePixels >= -tolerance) : null,
      coarseTransportAllowancePixels: predictedCoarse ? coarseAllowancePixels : null,
      minimumCoarseTransportDelta: coarseDeltas ? Math.min(...coarseDeltas) : null,
      maximumCoarseTransportDelta: coarseDeltas ? Math.max(...coarseDeltas) : null,
      exactBounds,
      oneBucketOutward,
      unsafeBounds,
      boundAxisCount: observed.boundAxisCount,
      scripts: observed.scripts,
      stoppedWithinAvailableStages: firstDone >= 0,
      stoppedAtFirstDone: firstDone < 0 || firstDone === observed.activeStages - 1,
      finalWinnerMatchesTarget: firstDone < 0
        ? null : observed.finalWinner === fixtures.denseWinners[fixture],
      observedFinalWinner: observed.finalWinner,
      targetWinner: fixtures.denseWinners[fixture],
    };
    check.pass = check.groupCompositionMatches && check.unsafeBounds === 0
      && check.coarseTransportConservative !== false
      && check.boundAxisCount === 96 && check.scripts === 0
      && check.stoppedAtFirstDone && check.finalWinnerMatchesTarget !== false
      && stageChecks.every((stage) => Object.entries(stage)
        .every(([key, value]) => key === "stage" || value === true));
    checks.push(check);
  }

  await setInput(candidateLoad.page, 0);
  await settleMixed(candidateLoad.page);
  const liveA = await observeMixed(candidateLoad.page, true);
  await setInput(candidateLoad.page, fixtureCount - 1);
  await settleMixed(candidateLoad.page);
  const liveB = await observeMixed(candidateLoad.page, true);
  const parseAxes = (variation) => new Map(
    [...variation.matchAll(/"(b\d{3})"\s+([\d.eE+-]+)/g)]
      .map((match) => [match[1], Number(match[2])]),
  );
  const axesA = parseAxes(liveA.boundVariation);
  const axesB = parseAxes(liveB.boundVariation);
  const liveness = {
    changedBlockNorms: liveA.blockNorms.reduce(
      (count, value, index) => count + Number(Math.abs(value - liveB.blockNorms[index]) > 1e-9), 0,
    ),
    changedFontAxes: [...axesA].reduce(
      (count, [tag, value]) => count + Number(axesB.get(tag) !== value), 0,
    ),
    changedBoundGlyphs: liveA.boundWidths.reduce(
      (count, item, index) => count + Number(Math.abs(item.width - liveB.boundWidths[index].width) > tolerance), 0,
    ),
  };

  const timing = { candidate: [], retained: [] };
  for (let index = 0; index < timingFixtures.length; index += 1) {
    const fixture = timingFixtures[index];
    const order = !retainedLoad ? [[candidateLoad.page, timing.candidate]] : index % 2 === 0
      ? [[candidateLoad.page, timing.candidate], [retainedLoad.page, timing.retained]]
      : [[retainedLoad.page, timing.retained], [candidateLoad.page, timing.candidate]];
    for (const [page, samples] of order) {
      const started = performance.now();
      await setInput(page, fixture);
      await settleMixed(page);
      samples.push(performance.now() - started);
    }
  }

  const noScriptContext = await browser.newContext({ javaScriptEnabled: false });
  const noScriptPage = await noScriptContext.newPage();
  await noScriptPage.goto(`${baseUrl}/experiments/${experiment}/index.html`, {
    waitUntil: "load", timeout: 900_000,
  });
  const javaScriptDisabledLoad = await noScriptPage.locator("#result").count() === 1;
  await noScriptContext.close();

  const prefixTransportPass = checks.every((check) => check.pass)
    && liveness.changedBlockNorms === 96 && liveness.changedFontAxes === 96
    && liveness.changedBoundGlyphs === reference.groupwiseBoundGroups
    && javaScriptDisabledLoad;
  const exactComplete = prefixTransportPass
    && checks.every((check) => check.stoppedWithinAvailableStages
      && check.finalWinnerMatchesTarget);
  const candidateStats = statistics(timing.candidate);
  const retainedStats = retainedLoad ? statistics(timing.retained) : null;
  report = {
    decision: exactComplete
      ? `retain-groupwise-${stages}-stage-exact-cascade`
      : prefixTransportPass ? "retain-prefix-needs-exact-tail" : "reject-transport",
    chrome: await browser.version(),
    semanticsPass: prefixTransportPass,
    exactComplete,
    checks,
    liveness,
    javaScriptDisabledLoad,
    timing: {
      candidate: candidateStats,
      retained: retainedStats,
      meanRatio: retainedStats ? candidateStats.mean / retainedStats.mean : null,
      medianRatio: retainedStats ? candidateStats.median / retainedStats.median : null,
      samplesMilliseconds: timing,
      interpretation: "paired direction only; four fixtures after correctness",
    },
    coldLoadMilliseconds: {
      candidate: candidateLoad.milliseconds,
      retained: retainedLoad?.milliseconds ?? null,
      exactShadowControl: exactLoad.milliseconds,
    },
    diagnostics,
  };
  await candidateContext.close();
  await coarseContext.close();
  if (retainedContext) await retainedContext.close();
  await exactContext.close();
} finally {
  await browser.close();
  server.close();
}

await fs.writeFile(path.join(output, "browser-results.json"), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify({
  decision: report.decision,
  semanticsPass: report.semanticsPass,
  checksPassed: report.checks.filter((check) => check.pass).length,
  checksTotal: report.checks.length,
  liveness: report.liveness,
  timing: report.timing,
}, null, 2));
if (!report.semanticsPass) process.exitCode = 1;
