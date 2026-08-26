#!/usr/bin/env node
/* Verify and compare the production six-stage + batch-17 exact tail. */

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
const experiment = "gpt2-groupwise-cauchy-blockflow-production-batch17";
const prefixDirectory = "gpt2-groupwise-cauchy-blockflow-production-range-prefix6";
const serialDirectory = "gpt2-groupwise-cauchy-blockflow-production-range";
const output = path.join(workspace, "experiments", experiment);
const reference = JSON.parse(await fs.readFile(path.join(output, "reference.json"), "utf8"));
const prefixReference = JSON.parse(await fs.readFile(
  path.join(workspace, "experiments", prefixDirectory, "reference.json"), "utf8",
));
const fixtures = prefixReference.certifiedFixtures;
const groupwise = prefixReference.groupwiseFixtures;
const batch = reference.batchSize;
const prefixStages = reference.prefixGroups;
const tolerance = 0.03;

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
  return [
    ...hidden.map((value, dimension) => `--h${dimension}:${value}`),
    `--score-offset:${-fixtures.scoreFloors[fixture] * 256 * 4}px`,
    `--query-norm:${Math.sqrt(hidden.reduce((sum, value) => sum + value * value, 0))}`,
  ].join(";");
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

async function settlePrefix(page, maximumStages = prefixStages) {
  for (let pass = 0; pass < 3; pass += 1) {
    await page.locator("#result").evaluate((element) => element.getBoundingClientRect().width);
    for (let stage = 0; stage < maximumStages; stage += 1) {
      const wrapper = page.locator(`#mixed-stage-${stage}`);
      if (await wrapper.count() === 0
          || await wrapper.evaluate((element) => getComputedStyle(element).display) === "none") break;
      const dynamic = page.locator(`#dynamic-fine-stage-${stage}`);
      if (await dynamic.count() && await dynamic.evaluate(
        (element) => getComputedStyle(element).display,
      ) !== "none") await dynamic.evaluate((element) => element.getBoundingClientRect().width);
      for (const selector of [
        `#mixed-choice-source-${stage}`,
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
        `#remaining-result-${stage + 1}`,
      ]) await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
      const done = await page.locator(`#remaining-result-${stage + 1}`).evaluate(
        (element, property) => Number(getComputedStyle(element).getPropertyValue(property)),
        `--done-${stage}`,
      );
      if (done === 1) break;
    }
  }
}

async function settleBatch(page) {
  for (let pass = 0; pass < 3; pass += 1) {
    await settlePrefix(page);
    if (await page.locator("#batch-start").evaluate(
      (element) => getComputedStyle(element).display,
    ) === "none") continue;
    for (let slot = 1; slot < batch; slot += 1) {
      await page.locator(`#batch-group-${slot}`).evaluate(
        (element) => element.getBoundingClientRect().width,
      );
    }
    for (let slot = 0; slot < batch; slot += 1) {
      for (const prefix of ["batch-fine-stage", "batch-fine-reader", "batch-fine-result",
        "batch-score-carrier", "batch-token-carrier"]) {
        await page.locator(`#${prefix}-${slot}`).evaluate(
          (element) => element.getBoundingClientRect().width,
        );
      }
    }
    for (const selector of ["#batch-score-max", "#batch-score-reader", "#batch-score-result",
      "#batch-token-max", "#batch-token-reader", "#batch-final-result",
      "#batch-certificate-result"]) {
      await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
    }
  }
}

async function settleSerial(page) {
  await settlePrefix(page, 23);
}

async function readPrefix(page) {
  return page.evaluate((stageCount) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    const coarse = getComputedStyle(document.querySelector("#result"));
    let group = number(coarse, "--group");
    const groups = [];
    const done = [];
    let bestBucket;
    let bestWinner;
    for (let stage = 0; stage < stageCount; stage += 1) {
      const wrapper = getComputedStyle(document.querySelector(`#mixed-stage-${stage}`));
      if (wrapper.display === "none") break;
      groups.push(group);
      const fine = getComputedStyle(document.querySelector(
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
      ));
      bestBucket = number(fine, `--best-bucket-${stage}`);
      bestWinner = number(fine, `--best-winner-${stage}`);
      const remaining = getComputedStyle(document.querySelector(`#remaining-result-${stage + 1}`));
      const stageDone = number(remaining, `--done-${stage}`);
      done.push(stageDone);
      if (stageDone === 1) break;
      group = number(remaining, `--remaining-group-${stage + 1}`);
    }
    return { groups, done, bestBucket, bestWinner };
  }, prefixStages);
}

async function readBatch(page) {
  return page.evaluate((batchSize) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    const start = getComputedStyle(document.querySelector("#batch-start"));
    const compute = getComputedStyle(document.querySelector("#batch-compute"));
    const exact = [];
    for (let slot = 0; slot < batchSize; slot += 1) {
      const fine = getComputedStyle(document.querySelector(`#batch-fine-result-${slot}`));
      exact.push({
        slot,
        group: number(compute, `--batch-group-${slot}`),
        bucket: number(fine, `--batch-bucket-${slot}`),
        winner: number(fine, `--batch-winner-${slot}`),
      });
    }
    const score = getComputedStyle(document.querySelector("#batch-score-result"));
    const final = getComputedStyle(document.querySelector("#batch-final-result"));
    const certificate = getComputedStyle(document.querySelector("#batch-certificate-result"));
    return {
      display: start.display,
      exact,
      mergedBucket: number(score, "--batch-merged-bucket"),
      winningGroup: number(score, "--batch-winning-group"),
      finalWinner: number(final, "--batch-final-winner"),
      nextGroup: number(certificate, "--batch-next-group"),
      nextUpper: number(certificate, "--batch-next-upper"),
      gap: number(certificate, "--batch-certificate-gap"),
      done: number(certificate, "--batch-done"),
    };
  }, batch);
}

async function forceExactShadow(page, group) {
  const stage = page.locator("#fine-stage");
  await stage.evaluate((element, value) => element.style.setProperty("--group", String(value)), group);
  for (let pass = 0; pass < 3; pass += 1) {
    for (const selector of ["#fine-stage", ".fine-reader", "#fine-result"]) {
      await page.locator(selector).first().evaluate((element) => element.getBoundingClientRect().width);
    }
  }
  const result = await page.locator("#fine-result").evaluate((element, value) => {
    const style = getComputedStyle(element);
    const bucket = Number(style.getPropertyValue("--fine-bucket"));
    const local = Number(style.getPropertyValue("--fine-local"));
    return { group: value, bucket, winner: value * 256 + local };
  }, group);
  await stage.evaluate((element) => element.style.removeProperty("--group"));
  return result;
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

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const candidateContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const controlContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const serialContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const exactContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const candidateLoad = await loadPage(candidateContext, experiment);
  const controlLoad = await loadPage(controlContext, prefixDirectory, "control.html");
  const serialLoad = await loadPage(serialContext, serialDirectory);
  const exactLoad = await loadPage(exactContext, serialDirectory, "exact-control.html");
  const diagnostics = [candidateLoad, controlLoad, serialLoad, exactLoad]
    .flatMap(({ failures }) => failures);

  const checks = [];
  for (let fixture = 0; fixture < fixtures.hiddenVectors.length; fixture += 1) {
    await setInput(controlLoad.page, fixture);
    await settlePrefix(controlLoad.page);
    const controlWidths = await controlLoad.page.locator(".group-wrapper").evaluateAll(
      (elements) => elements.map((element) => element.getBoundingClientRect().width),
    );
    const composed = controlWidths.map(
      (width, group) => width + groupwise.predictedBoundWidths[fixture][group],
    );
    const route = expectedRoute(composed, prefixStages + batch + 1);

    await setInput(candidateLoad.page, fixture);
    await settleBatch(candidateLoad.page);
    const prefix = await readPrefix(candidateLoad.page);
    const tail = await readBatch(candidateLoad.page);
    const prefixDone = prefix.done.includes(1);
    const expectedBatchGroups = route.slice(prefixStages, prefixStages + batch);
    let shadowPass = true;
    const shadows = [];
    if (!prefixDone) {
      await setInput(exactLoad.page, fixture);
      for (const item of tail.exact) {
        const shadow = await forceExactShadow(exactLoad.page, item.group);
        shadows.push(shadow);
        shadowPass &&= item.bucket === shadow.bucket && item.winner === shadow.winner;
      }
    }
    const branches = [{
      group: Math.floor(prefix.bestWinner / 256),
      bucket: prefix.bestBucket,
      winner: prefix.bestWinner,
    }, ...tail.exact];
    const merged = branches.reduce((best, item) => {
      if (item.bucket > best.bucket
          || (item.bucket === best.bucket && item.winner < best.winner)) return item;
      return best;
    });
    const expectedNextUpper = Math.floor(composed[route[prefixStages + batch]] / 4);
    const finalWinner = prefixDone ? prefix.bestWinner : tail.finalWinner;
    const check = {
      fixture,
      sourceStateIndex: fixtures.sourceStateIndices[fixture],
      requiredGroups: fixtures.requiredGroupsAtCalibratedStop[fixture],
      prefixDone,
      prefixGroups: prefix.groups,
      batchGroups: tail.exact.map(({ group }) => group),
      expectedBatchGroups,
      prefixRouteMatches: prefix.groups.every((group, index) => group === route[index]),
      gateMatches: prefixDone ? tail.display === "none" : tail.display !== "none",
      uniqueBatchGroups: prefixDone || new Set(tail.exact.map(({ group }) => group)).size === batch,
      batchRouteMatches: prefixDone || tail.exact.every(
        ({ group }, index) => group === expectedBatchGroups[index],
      ),
      exactShadowsMatch: prefixDone || shadowPass,
      mergedBucketMatches: prefixDone || tail.mergedBucket === merged.bucket,
      mergedWinnerMatches: prefixDone || tail.finalWinner === merged.winner,
      winningGroupMatches: prefixDone || tail.winningGroup === merged.group,
      nextGroupMatches: prefixDone || tail.nextGroup === route[prefixStages + batch],
      nextUpperWithinCalibratedShortfall: prefixDone
        || tail.nextUpper + reference.upperTransportShortfallBuckets >= expectedNextUpper,
      gapArithmeticMatches: prefixDone || tail.gap === tail.mergedBucket - tail.nextUpper,
      doneMatchesGap: prefixDone || tail.done === Number(tail.gap > reference.stopGapBuckets),
      finalWinner,
      finalWinnerMatchesTarget: finalWinner === fixtures.denseWinners[fixture],
      batchDone: tail.done,
      shadows,
    };
    check.pass = [
      "prefixRouteMatches", "gateMatches", "uniqueBatchGroups", "batchRouteMatches",
      "exactShadowsMatch", "mergedBucketMatches", "mergedWinnerMatches",
      "winningGroupMatches", "nextGroupMatches", "nextUpperWithinCalibratedShortfall",
      "gapArithmeticMatches", "doneMatchesGap", "finalWinnerMatchesTarget",
    ].every((key) => check[key]);
    checks.push(check);
  }

  const timing = { batch17: [], serial23: [] };
  for (const fixture of [0, 1, 2, 5]) {
    for (const [page, settle, samples] of fixture % 2 === 0
      ? [[candidateLoad.page, settleBatch, timing.batch17],
        [serialLoad.page, settleSerial, timing.serial23]]
      : [[serialLoad.page, settleSerial, timing.serial23],
        [candidateLoad.page, settleBatch, timing.batch17]]) {
      const started = performance.now();
      await setInput(page, fixture);
      await settle(page);
      samples.push(performance.now() - started);
    }
  }

  const noScriptContext = await browser.newContext({ javaScriptEnabled: false });
  const noScriptPage = await noScriptContext.newPage();
  await noScriptPage.goto(`${baseUrl}/experiments/${experiment}/index.html`, {
    waitUntil: "load", timeout: 900_000,
  });
  const javaScriptDisabledLoad = await noScriptPage.locator("#batch-start").count() === 1;
  await noScriptContext.close();
  const batchStats = statistics(timing.batch17);
  const serialStats = statistics(timing.serial23);
  const semanticsPass = checks.every(({ pass }) => pass)
    && diagnostics.length === 0 && javaScriptDisabledLoad;
  const latencyPass = batchStats.mean < serialStats.mean
    && batchStats.median < serialStats.median;
  report = {
    decision: !semanticsPass ? "reject-production-batch17-semantics"
      : latencyPass ? "retain-production-batch17-tail"
        : "reject-production-batch17-latency",
    chrome: await browser.version(),
    semanticsPass,
    latencyPass,
    javaScriptDisabledLoad,
    checks,
    timing: {
      batch17: batchStats,
      serial23: serialStats,
      meanRatio: batchStats.mean / serialStats.mean,
      medianRatio: batchStats.median / serialStats.median,
      samplesMilliseconds: timing,
    },
    coldLoadMilliseconds: {
      batch17: candidateLoad.milliseconds,
      serial23: serialLoad.milliseconds,
      exactControl: exactLoad.milliseconds,
    },
    diagnostics,
  };
  await candidateContext.close();
  await controlContext.close();
  await serialContext.close();
  await exactContext.close();
} finally {
  await browser.close();
  server.close();
}

await fs.writeFile(path.join(output, "browser-results.json"), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify({
  decision: report.decision,
  semanticsPass: report.semanticsPass,
  checksPassed: report.checks.filter(({ pass }) => pass).length,
  checksTotal: report.checks.length,
  timing: report.timing,
  coldLoadMilliseconds: report.coldLoadMilliseconds,
}, null, 2));
if (!report.semanticsPass) process.exitCode = 1;
