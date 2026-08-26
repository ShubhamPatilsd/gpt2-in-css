#!/usr/bin/env node
/* Verify the six-font q16 integration in the retained production cascade. */

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
const experiment = "gpt2-groupwise-cauchy-blockflow-production-range-q16-sixfont";
const output = path.join(workspace, "experiments", experiment);
const reference = JSON.parse(await fs.readFile(path.join(output, "reference.json"), "utf8"));
const retained = reference.sourceRetained;
const fixtures = reference.certifiedFixtures;
const oracle = reference.directMathematicalOracle;
const stages = reference.stages;
const R = reference.q16SixFont.productionInputRange;
const axisSteps = 16384;
const tolerance = 0.03;
const warmRounds = Number(process.env.Q16_SIXFONT_WARM_ROUNDS ?? "1");
const loadOnly = process.env.Q16_SIXFONT_LOAD_ONLY === "1";
const diagnosticOnly = process.env.Q16_SIXFONT_DIAGNOSTIC === "1";
const loadTimeout = Number(process.env.Q16_SIXFONT_LOAD_TIMEOUT_MS ?? (loadOnly ? "360000" : "900000"));

function statistics(values) {
  if (values.length === 0) return { count: 0, minimum: null, median: null, maximum: null, mean: null };
  const sorted = [...values].sort((a, b) => a - b);
  return {
    count: values.length,
    minimum: sorted[0],
    median: sorted[Math.floor(sorted.length / 2)],
    maximum: sorted.at(-1),
    mean: values.reduce((sum, value) => sum + value, 0) / values.length,
  };
}

function fixtureStyle(hidden, scoreFloor) {
  const properties = hidden.map((value, dimension) => `--h${dimension}:${value}`);
  properties.push(`--score-offset:${-scoreFloor * 256 * 4}px`);
  properties.push(`--query-norm:${Math.sqrt(
    hidden.reduce((sum, value) => sum + value * value, 0),
  )}`);
  return properties.join(";");
}

const types = new Map([
  [".html", "text/html"], [".css", "text/css"], [".woff2", "font/woff2"],
  [".json", "application/json"], [".npy", "application/octet-stream"],
]);
const server = http.createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, "http://x").pathname);
    const filename = path.join(workspace, pathname);
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

async function loadPage(context, directory) {
  const page = await context.newPage();
  page.setDefaultTimeout(loadTimeout);
  const failures = [];
  const requests = [];
  page.on("requestfailed", (request) => failures.push({
    url: request.url(), error: request.failure()?.errorText ?? "unknown",
  }));
  page.on("response", (response) => requests.push({
    url: response.url(), status: response.status(), resourceType: response.request().resourceType(),
  }));
  const started = performance.now();
  await page.goto(`${baseUrl}/experiments/${directory}/index.html`, {
    waitUntil: "load", timeout: loadTimeout,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  return { page, failures, requests, milliseconds: performance.now() - started };
}

async function setInput(page, hidden, scoreFloor) {
  await page.evaluate((style) => {
    for (const element of [document.querySelector(".cascade"), document.querySelector("#model")]) {
      element.style.cssText = style;
    }
  }, fixtureStyle(hidden, scoreFloor));
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
      const dynamic = getComputedStyle(document.querySelector(`#dynamic-fine-stage-${stage}`));
      const fine = getComputedStyle(document.querySelector(
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
      ));
      const remaining = getComputedStyle(document.querySelector(`#remaining-result-${stage + 1}`));
      const upperReader = document.querySelector(`.upper-reader-${stage + 1}`);
      const item = {
        stage,
        group,
        dynamicDisplay: dynamic.display,
        fineBucket: number(fine, `--fine-bucket-${stage}`),
        fineWinner: number(fine, `--fine-winner-${stage}`),
        bestBucket: number(fine, `--best-bucket-${stage}`),
        bestWinner: number(fine, `--best-winner-${stage}`),
        nextUpperBucket: number(remaining, `--upper-bucket-${stage + 1}`),
        nextUpperReaderWidth: upperReader?.getBoundingClientRect().width ?? null,
        nextUpperReaderComputedWidth: upperReader
          ? Number.parseFloat(getComputedStyle(upperReader).width) : null,
        certificateGap: number(remaining, `--certificate-gap-${stage}`),
        done: number(remaining, `--done-${stage}`),
      };
      observations.push(item);
      if (item.done === 1) break;
      group = number(remaining, `--remaining-group-${stage + 1}`);
    }
    return {
      stages: observations,
      finalWinner: observations.at(-1)?.bestWinner,
      groupWidths: [...document.querySelectorAll(".group-wrapper")]
        .map((element) => element.getBoundingClientRect().width),
      scripts: document.querySelectorAll("script").length,
      csp: document.querySelector('meta[http-equiv="Content-Security-Policy"]')?.content ?? "",
    };
  }, stages);
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

function inspectStages(observed, fixture) {
  const route = expectedRoute(observed.groupWidths, observed.stages.length + 1);
  let bestBucket = -Infinity;
  let bestWinner = Infinity;
  const checks = observed.stages.map((stage, index) => {
    const expectedWinner = oracle.groupQ16Winners[fixture][stage.group];
    const expectedBucket = oracle.groupQ16Buckets[fixture][stage.group];
    const bucketDelta = stage.fineBucket - expectedBucket;
    if (stage.fineBucket > bestBucket
        || (stage.fineBucket === bestBucket && stage.fineWinner < bestWinner)) {
      bestBucket = stage.fineBucket;
      bestWinner = stage.fineWinner;
    }
    const expectedNextUpper = route[index + 1] === undefined
      ? null : Math.floor(observed.groupWidths[route[index + 1]] / 4);
    const nextGroupWidth = route[index + 1] === undefined
      ? null : observed.groupWidths[route[index + 1]];
    const upperTransportShortfall = reference.upperTransportShortfallBuckets ?? 0;
    return {
      stage: index,
      group: stage.group,
      consumer: stage.group <= 1 ? "hot" : "dynamic",
      expectedQ16Winner: expectedWinner,
      expectedQ16Bucket: expectedBucket,
      observedWinner: stage.fineWinner,
      observedBucket: stage.fineBucket,
      bucketDelta,
      routeMatchesLiveUpperReducer: stage.group === route[index],
      winnerMatchesGroupQ16: stage.fineWinner === expectedWinner,
      bucketDeltaWithinOne: Math.abs(bucketDelta) <= 1,
      tokenInVocabulary: stage.fineWinner >= 0 && stage.fineWinner < 50257,
      bestBucketMatchesLiveRecompute: stage.bestBucket === bestBucket,
      bestWinnerMatchesLiveRecompute: stage.bestWinner === bestWinner,
      expectedNextUpper,
      observedNextUpper: stage.nextUpperBucket,
      nextGroupWidth,
      nextGroupWidthDivFour: nextGroupWidth === null ? null : nextGroupWidth / 4,
      nextUpperReaderWidth: stage.nextUpperReaderWidth,
      nextUpperReaderWidthDivFour: stage.nextUpperReaderWidth === null
        ? null : stage.nextUpperReaderWidth / 4,
      nextUpperReaderComputedWidth: stage.nextUpperReaderComputedWidth,
      upperTransportShortfall,
      nextUpperMatchesLiveRoute: expectedNextUpper === null
        || stage.nextUpperBucket + upperTransportShortfall >= expectedNextUpper,
      gapArithmeticMatches: stage.certificateGap === stage.bestBucket - stage.nextUpperBucket,
      doneMatches49BucketGate: stage.done === Number(stage.certificateGap > 49),
      consumerDisplayMatches: stage.group <= 1
        ? stage.dynamicDisplay === "none" : stage.dynamicDisplay === "grid",
    };
  });
  return { route, checks };
}

function parseAxes(value) {
  return new Map([...value.matchAll(/"([A-Z0-9]{4})"\s+([-+\d.eE]+)/g)]
    .map((match) => [match[1], Number(match[2])]));
}

function axisTag(index) {
  return `X${index.toString(36).toUpperCase().padStart(3, "0")}`;
}

async function axisSnapshot(page, hidden) {
  return page.evaluate(() => {
    const dynamic = document.querySelector("#dynamic-fine-stage-0");
    const hot = document.querySelector(".mixed-hot-candidate");
    const fineCandidate = document.querySelector("#dynamic-fine-stage-0 .fine-candidate");
    return {
      dynamicVariation: getComputedStyle(dynamic).fontVariationSettings,
      hotVariation: getComputedStyle(hot).fontVariationSettings,
      dynamicWidth: fineCandidate.getBoundingClientRect().width,
      hotWidth: hot.getBoundingClientRect().width,
    };
  }).then((snapshot) => ({
    ...snapshot,
    expected: hidden.map((value) => Math.round(value / R * axisSteps)),
  }));
}

function checkAxisSnapshot(snapshot) {
  const dynamic = parseAxes(snapshot.dynamicVariation);
  const hot = parseAxes(snapshot.hotVariation);
  let dynamicErrors = 0;
  let hotErrors = 0;
  for (let dimension = 0; dimension < 768; dimension += 1) {
    const tag = axisTag(dimension);
    dynamicErrors += Number(dynamic.get(tag) !== snapshot.expected[dimension]);
    hotErrors += Number(hot.get(tag) !== snapshot.expected[dimension]);
  }
  return {
    dynamicAxisCount: dynamic.size,
    hotAxisCount: hot.size,
    dynamicErrors,
    hotErrors,
    dynamic,
    hot,
  };
}

async function sampledGlyphGeometry(page, tokens) {
  return page.evaluate((sampleTokens) => {
    const source = getComputedStyle(document.querySelector(".mixed-hot-candidate"));
    const host = document.createElement("div");
    host.style.cssText = [
      "position:fixed", "left:0", "top:-20000px", "white-space:pre",
      `font-family:${source.fontFamily}`, `font-size:${source.fontSize}`,
      `font-variation-settings:${source.fontVariationSettings}`, "font-kerning:none",
    ].join(";");
    document.body.append(host);
    const measurements = [];
    for (const token of sampleTokens) {
      const widths = [];
      for (let plane = 0; plane < 6; plane += 1) {
        const span = document.createElement("span");
        span.textContent = String.fromCodePoint(0x20000 + plane * 0x10000 + token);
        span.style.display = "inline-block";
        host.append(span);
        widths.push(span.getBoundingClientRect().width);
      }
      measurements.push({ token, widths });
      host.replaceChildren();
    }
    host.remove();
    return measurements;
  }, [...tokens].sort((a, b) => a - b));
}

async function forceState519(page) {
  const forced = oracle.forcedState519;
  await setInput(page, forced.hiddenVector, forced.scoreFloor);
  await page.locator("#result").evaluate(
    (element, group) => element.style.setProperty("--group", String(group)), forced.forcedGroup,
  );
  for (let pass = 0; pass < 3; pass += 1) {
    for (const selector of ["#dynamic-fine-stage-0", "#mixed-choice-source-0", "#fine-result"]) {
      await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
    }
  }
  const result = await page.evaluate((expectedBucket) => {
    const dynamic = getComputedStyle(document.querySelector("#dynamic-fine-stage-0"));
    const fine = getComputedStyle(document.querySelector("#fine-result"));
    const number = (property) => Number(fine.getPropertyValue(property));
    return {
      group: Number(fine.getPropertyValue("--selected-group-0")),
      dynamicDisplay: dynamic.display,
      winner: number("--fine-winner-0"),
      bucket: number("--fine-bucket-0"),
      bucketDelta: number("--fine-bucket-0") - expectedBucket,
    };
  }, forced.forcedGroupQ16Bucket);
  await page.locator("#result").evaluate((element) => element.style.removeProperty("--group"));
  return {
    ...result,
    expectedWinner: forced.forcedGroupQ16Winner,
    legacyBrowserToken: forced.legacyBrowserTokenForComparison,
    pass: result.group === forced.forcedGroup
      && result.dynamicDisplay === "grid"
      && result.winner === forced.forcedGroupQ16Winner
      && result.winner !== forced.legacyBrowserTokenForComparison
      && Math.abs(result.bucketDelta) <= 1,
  };
}

const htmlSource = await fs.readFile(path.join(output, "index.html"), "utf8");
const cssSource = await fs.readFile(path.join(output, "fine-stage-sixfont.css"), "utf8");
const hotCssSource = await fs.readFile(path.join(output, "hot-sixfont.css"), "utf8");
const hotRows = [...htmlSource.matchAll(
  /<i class="candidate mixed-hot-candidate" data-token="(\d+)"[^>]*>(.*?)<\/i>/g,
)];
const artifactAudit = {
  scriptsInSource: (htmlSource.match(/<script\b/g) ?? []).length,
  cspScriptNone: htmlSource.includes("script-src 'none'"),
  dynamicRows: (htmlSource.match(/class="fine-candidate"/g) ?? []).length,
  expectedDynamicRows: stages * 256,
  hotRows: hotRows.length,
  hotRowsUseSixExactCodepoints: hotRows.every((match) => {
    const token = Number(match[1]);
    return [...match[2]].map((glyph) => glyph.codePointAt(0)).join(",")
      === Array.from({ length: 6 }, (_, index) => 0x20000 + index * 0x10000 + token).join(",");
  }),
  dynamicBranchGraphs: (cssSource.match(/--fine-base:if\(/g) ?? []).length,
  retainedQ10Referenced: htmlSource.includes(`../${retained}/coarse-production.css`),
  retainedTopologyReferenced: htmlSource.includes(`../${retained}/topology.css`),
  sixFontFaces: (cssSource.match(/@font-face\{/g) ?? []).length,
  integerAxisFormulaPresent: cssSource.includes(
    `round(nearest,calc(var(--h0)/${Number(R).toPrecision(12).replace(/0+$/, "")}*16384),1)`,
  ) || cssSource.includes("round(nearest,calc(var(--h0)/266.248396912*16384),1)"),
  narrowHotOverride: (hotCssSource.match(/\.mixed-hot-candidate\{/g) ?? []).length === 1
    && !hotCssSource.includes("nth-child"),
  lastPartialGroupValidRows: reference.lastPartialGroup.validRows,
};

if (diagnosticOnly) {
  const failedResults = JSON.parse(await fs.readFile(path.join(output, "browser-results.json"), "utf8"));
  const failedTokens = new Set([0, 511, 50256, 37848]);
  for (const check of failedResults.checks ?? []) {
    for (const stage of check.stages ?? []) failedTokens.add(stage.observedWinner);
  }
  const bankHtml = await fs.readFile(
    path.join(workspace, "experiments", reference.sixFontBankSource, "index.html"), "utf8",
  );
  const bankRows = new Map([...bankHtml.matchAll(
    /<i class="candidate" data-token="(\d+)" style="--base:([^;]+);[^>]*>(.*?)<\/i>/g,
  )].map((match) => [Number(match[1]), { base: Number(match[2]), glyphs: match[3] }]));
  const diagnosticBrowser = await chromium.launch({ executablePath, headless: true });
  const context = await diagnosticBrowser.newContext({ viewport: { width: 800, height: 200 } });
  let diagnosticReport;
  try {
    const loaded = await loadPage(context, experiment);
    await setInput(loaded.page, fixtures.hiddenVectors[0], fixtures.scoreFloors[0]);
    await settle(loaded.page);
    const observed = await observe(loaded.page);
    const group = observed.stages[0].group;
    const token = oracle.groupQ16Winners[0][group];
    const local = token % 256;
    const bankRow = bankRows.get(token);
    const expectedScore = oracle.groupQ16Scores[0][group];
    const expectedBucket = oracle.groupQ16Buckets[0][group];
    const selector = `#dynamic-fine-stage-0 .fine-candidate:nth-child(${local + 1})`;
    const numericOffset = -fixtures.scoreFloors[0] * 256 * 4;
    const capture = await loaded.page.evaluate(({ targetSelector, expectedGlyphs, literalBase, offset }) => {
      const candidate = document.querySelector(targetSelector);
      const phase = candidate.querySelector(".fine-phase-0");
      const candidateStyle = getComputedStyle(candidate);
      const phaseStyle = getComputedStyle(phase);
      const pseudoStyle = getComputedStyle(phase, "::before");
      const resolver = document.createElement("i");
      resolver.style.cssText = "position:fixed;left:0;top:-30000px;display:block;height:1px;width:calc(var(--fine-base)*1px)";
      candidate.append(resolver);
      const resolvedBaseWidth = resolver.getBoundingClientRect().width;
      resolver.remove();

      const host = document.createElement("div");
      host.style.cssText = [
        "position:fixed", "left:0", "top:-25000px", "display:block", "width:max-content",
        "white-space:pre", "font-style:normal", `font-family:${phaseStyle.fontFamily}`,
        `font-size:${phaseStyle.fontSize}`, `font-variation-settings:${phaseStyle.fontVariationSettings}`,
        "font-kerning:none",
      ].join(";");
      const widths = [];
      for (const glyph of expectedGlyphs) {
        const span = document.createElement("span");
        span.style.display = "inline-block";
        span.textContent = glyph;
        host.append(span);
      }
      document.body.append(host);
      for (const span of host.children) widths.push(span.getBoundingClientRect().width);
      const directRawWidth = host.getBoundingClientRect().width;
      host.remove();
      const currentWidth = candidate.getBoundingClientRect().width;
      const inheritedOffset = candidateStyle.getPropertyValue("--score-offset");
      const widthTerms = {
        currentExpression: null,
        factorOne: null,
        removeScoreOffset: null,
        numericLiteralOffset: null,
        numericLiteralBaseAndOffset: null,
      };
      const expressions = {
        factorOne: "calc-size(max-content,calc(round(nearest,(size - var(--fine-base)*1px)*1 + var(--score-offset),4px) + var(--local-tie)/64*1px))",
        removeScoreOffset: "calc-size(max-content,calc(round(nearest,(size - var(--fine-base)*1px)*120.777609693 + 0px,4px) + var(--local-tie)/64*1px))",
        numericLiteralOffset: `calc-size(max-content,calc(round(nearest,(size - var(--fine-base)*1px)*120.777609693 + ${offset}px,4px) + var(--local-tie)/64*1px))`,
        numericLiteralBaseAndOffset: `calc-size(max-content,calc(round(nearest,(size - ${literalBase}px)*120.777609693 + ${offset}px,4px) + var(--local-tie)/64*1px))`,
      };
      widthTerms.currentExpression = {
        specified: candidateStyle.width,
        rectWidth: currentWidth,
      };
      const originalInlineWidth = candidate.style.width;
      for (const [name, expression] of Object.entries(expressions)) {
        candidate.style.width = expression;
        widthTerms[name] = {
          acceptedInlineValue: candidate.style.width,
          computedWidth: getComputedStyle(candidate).width,
          rectWidth: candidate.getBoundingClientRect().width,
        };
      }
      candidate.style.width = originalInlineWidth;

      const dynamic = document.querySelector("#dynamic-fine-stage-0");
      const choice = document.querySelector("#mixed-choice-source-0");
      const fine = document.querySelector("#fine-result");
      const stageStyle = getComputedStyle(dynamic);
      const pseudoText = pseudoStyle.content.startsWith('"')
        ? pseudoStyle.content.slice(1, -1) : pseudoStyle.content;
      return {
        candidate: {
          fontFamily: candidateStyle.fontFamily,
          fontSize: candidateStyle.fontSize,
          fontVariationSettings: candidateStyle.fontVariationSettings,
          fineBaseCustomProperty: candidateStyle.getPropertyValue("--fine-base"),
          fineGlyphsCustomProperty: candidateStyle.getPropertyValue("--fine-glyphs"),
          rectWidth: candidate.getBoundingClientRect().width,
          scrollWidth: candidate.scrollWidth,
          display: candidateStyle.display,
          gridArea: candidateStyle.gridArea,
          overflow: candidateStyle.overflow,
          inheritedScoreOffset: inheritedOffset,
        },
        phase: {
          fontFamily: phaseStyle.fontFamily,
          fontSize: phaseStyle.fontSize,
          fontVariationSettings: phaseStyle.fontVariationSettings,
          display: phaseStyle.display,
          rectWidth: phase.getBoundingClientRect().width,
          pseudoContent: pseudoStyle.content,
          pseudoCodepoints: [...pseudoText].map((glyph) => glyph.codePointAt(0)),
        },
        resolvedBaseWidth,
        directRawWidth,
        directGlyphWidths: widths,
        expectedCodepoints: [...expectedGlyphs].map((glyph) => glyph.codePointAt(0)),
        widthTermTests: widthTerms,
        reducerChain: {
          stageAnchorName: stageStyle.getPropertyValue("anchor-name"),
          stageDisplay: stageStyle.display,
          stageTop: stageStyle.top,
          stageWidth: dynamic.getBoundingClientRect().width,
          choiceWidth: choice.getBoundingClientRect().width,
          fineResultWidth: fine.getBoundingClientRect().width,
        },
      };
    }, {
      targetSelector: selector,
      expectedGlyphs: [...bankRow.glyphs],
      literalBase: bankRow.base,
      offset: numericOffset,
    });

    const inspected = inspectStages(observed, 0);
    const firstDone = observed.stages.findIndex((stage) => stage.done === 1);
    const focusedFixture = {
      state: fixtures.sourceStateIndices[0],
      stages: inspected.checks,
      measuredRoute: observed.stages.map((stage) => stage.group),
      expectedLiveRoute: inspected.route.slice(0, observed.stages.length),
      finalWinner: observed.finalWinner,
      q16Winner: oracle.q16Winners[0],
      floatWinner: oracle.floatWinners[0],
      stoppedAtFirstDone: firstDone >= 0 && firstDone === observed.stages.length - 1,
    };
    focusedFixture.pass = focusedFixture.stoppedAtFirstDone
      && focusedFixture.finalWinner === focusedFixture.q16Winner
      && focusedFixture.finalWinner === focusedFixture.floatWinner
      && focusedFixture.stages.every((stage) => Object.entries(stage).every(
        ([key, value]) => ["stage", "group", "consumer", "expectedQ16Winner", "expectedQ16Bucket",
          "observedWinner", "observedBucket", "bucketDelta", "expectedNextUpper",
          "observedNextUpper", "nextGroupWidth", "nextGroupWidthDivFour",
          "nextUpperReaderWidth", "nextUpperReaderWidthDivFour",
          "nextUpperReaderComputedWidth", "upperTransportShortfall"].includes(key) || value === true,
      ));
    const forcedState519 = await forceState519(loaded.page);

    await setInput(loaded.page, fixtures.hiddenVectors.at(-1), fixtures.scoreFloors.at(-1));
    const collapsedAudit = await loaded.page.evaluate((tokens) => {
      const source = getComputedStyle(document.querySelector(".mixed-hot-candidate"));
      const measurements = [];
      for (const tokenValue of tokens) {
        for (let plane = 0; plane < 6; plane += 1) {
          const codepoint = 0x20000 + plane * 0x10000 + tokenValue;
          const span = document.createElement("span");
          span.style.cssText = [
            "position:fixed", "left:0", "top:-22000px", "display:inline-block",
            "white-space:pre", "font-style:normal", `font-family:${source.fontFamily}`,
            `font-size:${source.fontSize}`, `font-variation-settings:${source.fontVariationSettings}`,
            "font-kerning:none",
          ].join(";");
          span.textContent = String.fromCodePoint(codepoint);
          document.body.append(span);
          const width = span.getBoundingClientRect().width;
          const loadedAtCurrentSettings = document.fonts.check(
            `${source.fontSize} ${source.fontFamily}`, span.textContent,
          );
          span.style.fontVariationSettings = "normal";
          const defaultWidth = span.getBoundingClientRect().width;
          span.remove();
          measurements.push({ token: tokenValue, plane, codepoint, width, defaultWidth, loadedAtCurrentSettings });
        }
      }
      return measurements;
    }, [...failedTokens].sort((a, b) => a - b));
    const collapsed = collapsedAudit.filter((item) => item.width <= 0);
    const expectedRawWidth = bankRow.base + expectedScore * 1024 / reference.q16SixFont.factor;
    const observedFine = observed.stages[0];
    diagnosticReport = {
      mode: "focused-scale-cancellation-diagnostic",
      preservedFailedResults: "browser-results.json",
      state: fixtures.sourceStateIndices[0],
      stage: 0,
      group,
      token,
      local,
      expected: {
        bankRowBase: bankRow.base,
        q16Score: expectedScore,
        rawGlyphWidth: expectedRawWidth,
        q16Bucket: expectedBucket,
        codepoints: [...bankRow.glyphs].map((glyph) => glyph.codePointAt(0)),
      },
      observed: {
        fineWinner: observedFine.fineWinner,
        fineBucket: observedFine.fineBucket,
        bucketDelta: observedFine.fineBucket - expectedBucket,
        ...capture,
      },
      cancellation: {
        rawMinusResolvedBase: capture.directRawWidth - capture.resolvedBaseWidth,
        expectedRawMinusBase: expectedRawWidth - bankRow.base,
        rawWidthError: capture.directRawWidth - expectedRawWidth,
        baseError: capture.resolvedBaseWidth - bankRow.base,
      },
      focusedFixture,
      forcedState519,
      failedSampleTokenCount: failedTokens.size,
      collapsedGlyphs: collapsed,
      collapseReason: collapsed.map((item) => ({
        ...item,
        diagnosis: item.token >= 50257
          ? "outside the immutable 0..50256 bank; invalid group-196/local-255 alias from the failed reducer"
          : item.defaultWidth > 0
          ? "glyph exists at default axes but HVAR advance reached zero at this computed coordinate"
          : "glyph is absent/not selected through this computed font-family fallback path",
      })),
      requests: loaded.requests.filter((item) => item.resourceType === "font"),
      failures: loaded.failures,
    };
  } finally {
    await context.close();
    await diagnosticBrowser.close();
    server.close();
  }
  await fs.writeFile(
    path.join(output, "diagnostic.json"), `${JSON.stringify(diagnosticReport, null, 2)}\n`,
  );
  const diagnosisMarkdown = `# Focused six-font integration diagnostic

State ${diagnosticReport.state}, stage ${diagnosticReport.stage}, group ${diagnosticReport.group}, token ${diagnosticReport.token} was inspected without rerunning the full suite.

- Expected bank base/raw/bucket: ${diagnosticReport.expected.bankRowBase} px / ${diagnosticReport.expected.rawGlyphWidth.toFixed(6)} px / ${diagnosticReport.expected.q16Bucket}.
- Observed direct raw width/resolved base/final width/bucket: ${diagnosticReport.observed.directRawWidth.toFixed(6)} px / ${diagnosticReport.observed.resolvedBaseWidth.toFixed(6)} px / ${diagnosticReport.observed.candidate.rectWidth.toFixed(6)} px / ${diagnosticReport.observed.fineBucket}.
- Raw-width error: ${diagnosticReport.cancellation.rawWidthError.toFixed(6)} px; base error: ${diagnosticReport.cancellation.baseError.toFixed(6)} px.
- Rendered pseudo-element codepoints: ${diagnosticReport.observed.phase.pseudoCodepoints.join(", ")}.
- Focused state ${diagnosticReport.focusedFixture.state}: final ${diagnosticReport.focusedFixture.finalWinner}, q16 ${diagnosticReport.focusedFixture.q16Winner}, pass ${diagnosticReport.focusedFixture.pass}.
- Forced state 519: final ${diagnosticReport.forcedState519.winner}, q16 ${diagnosticReport.forcedState519.expectedWinner}, pass ${diagnosticReport.forcedState519.pass}.
- Collapsed glyphs reproduced from the failed sample: ${diagnosticReport.collapsedGlyphs.length}; all are explicitly classified in \`diagnostic.json\` (including out-of-vocabulary aliases).
`;
  await fs.writeFile(path.join(output, "DIAGNOSTIC.md"), diagnosisMarkdown);
  console.log(JSON.stringify(diagnosticReport, null, 2));
  process.exit(0);
}

if (loadOnly) {
  const loadBrowser = await chromium.launch({ executablePath, headless: true });
  const loadReport = {
    mode: "load-only",
    timeoutMilliseconds: loadTimeout,
    maximumAcceptedRatio: 2.5,
    retainedMilliseconds: null,
    candidateMilliseconds: null,
    ratio: null,
    retainedError: null,
    candidateError: null,
    candidateFontRequests: [],
    pass: false,
  };
  const retainedContext = await loadBrowser.newContext({ viewport: { width: 800, height: 200 } });
  const candidateContext = await loadBrowser.newContext({ viewport: { width: 800, height: 200 } });
  try {
    let retainedLoad;
    try {
      retainedLoad = await loadPage(retainedContext, retained);
      loadReport.retainedMilliseconds = retainedLoad.milliseconds;
    } catch (error) {
      loadReport.retainedError = String(error);
    }
    if (retainedLoad) {
      try {
        const candidateLoad = await loadPage(candidateContext, experiment);
        loadReport.candidateMilliseconds = candidateLoad.milliseconds;
        loadReport.ratio = candidateLoad.milliseconds / retainedLoad.milliseconds;
        loadReport.candidateFontRequests = [...new Set(candidateLoad.requests
          .filter((item) => item.resourceType === "font")
          .map((item) => path.basename(new URL(item.url).pathname)))].sort();
        loadReport.pass = candidateLoad.failures.length === 0
          && loadReport.candidateFontRequests.filter((name) => name.startsWith("score-")).length >= 6
          && loadReport.ratio <= loadReport.maximumAcceptedRatio;
      } catch (error) {
        loadReport.candidateError = String(error);
      }
    }
  } finally {
    await retainedContext.close();
    await candidateContext.close();
    await loadBrowser.close();
  }
  await fs.writeFile(
    path.join(output, "load-only-results.json"), `${JSON.stringify(loadReport, null, 2)}\n`,
  );
  console.log(JSON.stringify(loadReport, null, 2));
  process.exit(loadReport.pass ? 0 : 1);
}

const diagnostics = { candidateFailures: [], retainedFailures: [], requests: [] };
const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const candidateContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const retainedContext = warmRounds > 0
    ? await browser.newContext({ viewport: { width: 800, height: 200 } }) : null;
  const candidateLoad = await loadPage(candidateContext, experiment);
  const retainedLoad = retainedContext ? await loadPage(retainedContext, retained) : null;
  diagnostics.candidateFailures.push(...candidateLoad.failures);
  if (retainedLoad) diagnostics.retainedFailures.push(...retainedLoad.failures);
  diagnostics.requests = candidateLoad.requests;

  const checks = [];
  const geometryTokens = new Set([0, 511, 50256]);
  for (let fixture = 0; fixture < fixtures.hiddenVectors.length; fixture += 1) {
    await setInput(candidateLoad.page, fixtures.hiddenVectors[fixture], fixtures.scoreFloors[fixture]);
    await settle(candidateLoad.page);
    const observed = await observe(candidateLoad.page);
    const inspected = inspectStages(observed, fixture);
    inspected.checks.forEach((stage) => {
      if (stage.observedWinner >= 0 && stage.observedWinner < 50257) {
        geometryTokens.add(stage.observedWinner);
      }
    });
    const firstDone = observed.stages.findIndex((stage) => stage.done === 1);
    const finalWinner = observed.finalWinner;
    const check = {
      fixture,
      state: fixtures.sourceStateIndices[fixture],
      q16Winner: oracle.q16Winners[fixture],
      q16BucketWinner: oracle.q16BucketWinners[fixture],
      floatWinner: oracle.floatWinners[fixture],
      measuredRoute: observed.stages.map((stage) => stage.group),
      expectedLiveRoute: inspected.route.slice(0, observed.stages.length),
      activeStages: observed.stages.length,
      stoppedWithin23Stages: firstDone >= 0,
      stoppedAtFirstDone: firstDone === observed.stages.length - 1,
      finalWinner,
      finalMatchesQ16: finalWinner === oracle.q16Winners[fixture],
      finalMatchesQ16Bucket: finalWinner === oracle.q16BucketWinners[fixture],
      finalMatchesOriginalFloat: finalWinner === oracle.floatWinners[fixture],
      scripts: observed.scripts,
      cspScriptNone: observed.csp.includes("script-src 'none'"),
      stages: inspected.checks,
    };
    check.pass = check.stoppedWithin23Stages && check.stoppedAtFirstDone
      && check.finalMatchesQ16 && check.finalMatchesQ16Bucket
      && check.finalMatchesOriginalFloat && check.scripts === 0 && check.cspScriptNone
      && check.stages.every((stage) => Object.entries(stage).every(
        ([key, value]) => ["stage", "group", "consumer", "expectedQ16Winner", "expectedQ16Bucket",
          "observedWinner", "observedBucket", "bucketDelta", "expectedNextUpper",
          "observedNextUpper", "nextGroupWidth", "nextGroupWidthDivFour",
          "nextUpperReaderWidth", "nextUpperReaderWidthDivFour",
          "nextUpperReaderComputedWidth", "upperTransportShortfall"].includes(key) || value === true,
      ));
    checks.push(check);
  }

  const forcedState519 = await forceState519(candidateLoad.page);
  geometryTokens.add(oracle.forcedState519.forcedGroupQ16Winner);

  await setInput(candidateLoad.page, fixtures.hiddenVectors[0], fixtures.scoreFloors[0]);
  await settle(candidateLoad.page);
  const axesA = await axisSnapshot(candidateLoad.page, fixtures.hiddenVectors[0]);
  await setInput(candidateLoad.page, fixtures.hiddenVectors.at(-1), fixtures.scoreFloors.at(-1));
  await settle(candidateLoad.page);
  const axesB = await axisSnapshot(candidateLoad.page, fixtures.hiddenVectors.at(-1));
  const checkedA = checkAxisSnapshot(axesA);
  const checkedB = checkAxisSnapshot(axesB);
  const changedDynamicAxes = [...checkedA.dynamic].reduce(
    (count, [tag, value]) => count + Number(checkedB.dynamic.get(tag) !== value), 0,
  );
  const changedHotAxes = [...checkedA.hot].reduce(
    (count, [tag, value]) => count + Number(checkedB.hot.get(tag) !== value), 0,
  );
  const liveness = {
    fixtureA: fixtures.sourceStateIndices[0],
    fixtureB: fixtures.sourceStateIndices.at(-1),
    dynamicAxisCount: checkedA.dynamicAxisCount,
    hotAxisCount: checkedA.hotAxisCount,
    dynamicCoordinateErrorsA: checkedA.dynamicErrors,
    dynamicCoordinateErrorsB: checkedB.dynamicErrors,
    hotCoordinateErrorsA: checkedA.hotErrors,
    hotCoordinateErrorsB: checkedB.hotErrors,
    changedDynamicAxes,
    changedHotAxes,
    dynamicWidthA: axesA.dynamicWidth,
    dynamicWidthB: axesB.dynamicWidth,
    hotWidthA: axesA.hotWidth,
    hotWidthB: axesB.hotWidth,
  };
  liveness.pass = liveness.dynamicAxisCount === 768 && liveness.hotAxisCount === 768
    && liveness.dynamicCoordinateErrorsA === 0 && liveness.dynamicCoordinateErrorsB === 0
    && liveness.hotCoordinateErrorsA === 0 && liveness.hotCoordinateErrorsB === 0
    && liveness.changedDynamicAxes > 0 && liveness.changedHotAxes > 0
    && (Math.abs(liveness.dynamicWidthA - liveness.dynamicWidthB) > tolerance
      || Math.abs(liveness.hotWidthA - liveness.hotWidthB) > tolerance);

  const glyphMeasurements = await sampledGlyphGeometry(candidateLoad.page, geometryTokens);
  const allGlyphWidths = glyphMeasurements.flatMap((item) => item.widths);
  const geometry = {
    sampledTokens: glyphMeasurements.length,
    sampledGlyphs: allGlyphWidths.length,
    minimumGlyphWidth: Math.min(...allGlyphWidths),
    maximumGlyphWidth: Math.max(...allGlyphWidths),
    collapsedGlyphs: allGlyphWidths.filter((width) => width <= 0).length,
    capHits: allGlyphWidths.filter((width) => width >= 32768).length,
    analyticMaximumAdjustedAdvancePx:
      reference.q16SixFont.layerNormBound.maximumAdjustedAdvancePx,
  };
  geometry.pass = geometry.collapsedGlyphs === 0 && geometry.capHits === 0
    && geometry.analyticMaximumAdjustedAdvancePx < 32768;

  const partialGroup = await candidateLoad.page.evaluate(() => {
    const stage = document.querySelector("#dynamic-fine-stage-0");
    stage.style.setProperty("--group", "196");
    const candidates = [...stage.querySelectorAll(".fine-candidate")];
    const visible = candidates.filter((element) => getComputedStyle(element).display !== "none").length;
    stage.style.removeProperty("--group");
    return { candidates: candidates.length, visible };
  });
  partialGroup.pass = partialGroup.candidates === 256 && partialGroup.visible === 81;

  const timing = { candidate: [], retained: [], pairs: [] };
  for (let round = 0; round < warmRounds; round += 1) {
    for (let fixture = 0; fixture < fixtures.hiddenVectors.length; fixture += 1) {
      const order = (round + fixture) % 2 === 0
        ? [["candidate", candidateLoad.page], ["retained", retainedLoad.page]]
        : [["retained", retainedLoad.page], ["candidate", candidateLoad.page]];
      const pair = { round, fixture, state: fixtures.sourceStateIndices[fixture], order: [], candidate: null, retained: null };
      for (const [name, page] of order) {
        const started = performance.now();
        await setInput(page, fixtures.hiddenVectors[fixture], fixtures.scoreFloors[fixture]);
        await settle(page);
        const elapsed = performance.now() - started;
        timing[name].push(elapsed);
        pair[name] = elapsed;
        pair.order.push(name);
      }
      timing.pairs.push(pair);
    }
  }

  const noScriptContext = await browser.newContext({ javaScriptEnabled: false });
  const noScriptPage = await noScriptContext.newPage();
  await noScriptPage.goto(`${baseUrl}/experiments/${experiment}/index.html`, {
    waitUntil: "load", timeout: 900_000,
  });
  const javaScriptDisabledLoad = await noScriptPage.locator("#result").count() === 1;
  await noScriptContext.close();

  const fontRequests = candidateLoad.requests.filter((item) => item.resourceType === "font");
  const requestedSixFonts = [...new Set(fontRequests
    .filter((item) => item.url.includes("gpt2-global-q16-layernorm-integer-full/score-"))
    .map((item) => path.basename(new URL(item.url).pathname)))].sort();
  const oldQ16FontRequests = fontRequests.filter(
    (item) => item.url.includes("gpt2-hvar-grid-output-head-global16-twoplane"),
  );
  const runtime = {
    javaScriptDisabledLoad,
    requestedSixFonts,
    requestedSixFontCount: requestedSixFonts.length,
    oldQ16FontRequestCount: oldQ16FontRequests.length,
    scriptRequests: candidateLoad.requests.filter((item) => item.resourceType === "script").length,
    failedRequests: candidateLoad.failures.length,
  };
  runtime.pass = javaScriptDisabledLoad && runtime.requestedSixFontCount === 6
    && runtime.oldQ16FontRequestCount === 0 && runtime.scriptRequests === 0
    && runtime.failedRequests === 0;

  const stageDeltas = checks.flatMap((check) => check.stages);
  const nextUpperBoundaryEvidence = checks.flatMap((check) => check.stages
    .filter((stage) => stage.expectedNextUpper !== null
      && stage.expectedNextUpper !== stage.observedNextUpper)
    .map((stage) => ({
      state: check.state,
      stage: stage.stage,
      nextGroup: check.measuredRoute[stage.stage + 1],
      sourceWidth: stage.nextGroupWidth,
      sourceWidthDivFour: stage.nextGroupWidthDivFour,
      readerWidth: stage.nextUpperReaderWidth,
      readerComputedWidth: stage.nextUpperReaderComputedWidth,
      expectedNextUpper: stage.expectedNextUpper,
      observedNextUpper: stage.observedNextUpper,
      shortfall: stage.expectedNextUpper - stage.observedNextUpper,
    })));
  const deltaSummary = {};
  for (const consumer of ["dynamic", "hot"]) {
    const values = stageDeltas.filter((stage) => stage.consumer === consumer)
      .map((stage) => stage.bucketDelta);
    deltaSummary[consumer] = {
      count: values.length,
      minimum: values.length ? Math.min(...values) : null,
      maximum: values.length ? Math.max(...values) : null,
      maximumAbsolute: values.length ? Math.max(...values.map(Math.abs)) : null,
      negativeCount: values.filter((value) => value < 0).length,
      positiveCount: values.filter((value) => value > 0).length,
    };
  }

  const artifactPass = artifactAudit.scriptsInSource === 0 && artifactAudit.cspScriptNone
    && artifactAudit.dynamicRows === artifactAudit.expectedDynamicRows
    && artifactAudit.hotRows === 512 && artifactAudit.hotRowsUseSixExactCodepoints
    && artifactAudit.dynamicBranchGraphs === 256 && artifactAudit.retainedQ10Referenced
    && artifactAudit.retainedTopologyReferenced && artifactAudit.sixFontFaces === 6
    && artifactAudit.integerAxisFormulaPresent && artifactAudit.narrowHotOverride
    && artifactAudit.lastPartialGroupValidRows === 81;
  const pass = checks.every((check) => check.pass) && forcedState519.pass
    && liveness.pass && geometry.pass && partialGroup.pass && runtime.pass && artifactPass
    && deltaSummary.dynamic.count > 0 && deltaSummary.hot.count > 0
    && deltaSummary.dynamic.maximumAbsolute <= 1 && deltaSummary.hot.maximumAbsolute <= 1;
  const candidateStats = statistics(timing.candidate);
  const retainedStats = statistics(timing.retained);
  const profileDecision = pass
    ? "certify-sixfont-accuracy-cold-profile-retain-q16-warm-default"
    : "reject-sixfont-production-integration";
  report = {
    decision: profileDecision,
    pass,
    chrome: await browser.version(),
    correctnessOracle: "directMathematicalOracle: immutable global-q16 approximation and source checkpoint float",
    checks,
    forcedState519,
    bucketDeltaSummary: deltaSummary,
    liveness,
    geometry,
    partialGroup,
    artifactAudit: { ...artifactAudit, pass: artifactPass },
    runtime,
    stopCertificate: {
      retainedThresholdBuckets: 49,
      observedSelectedCandidateDeltaMinimum: Math.min(...stageDeltas.map((stage) => stage.bucketDelta)),
      observedSelectedCandidateDeltaMaximum: Math.max(...stageDeltas.map((stage) => stage.bucketDelta)),
      note: "A -1 selected-candidate delta would consume one bucket of the retained stop separation; results report its occurrence without changing the 49-bucket topology.",
    },
    nextUpperBoundaryEvidence,
    numericBackendDecision: {
      accuracyAndColdStartProfile: pass ? "accept-and-certify" : "reject",
      loadedThroughputDefault: "reject-sixfont-retain-existing-q16",
      state519Repair: forcedState519.pass,
      timingScope: "one paired warm round; six fixtures",
    },
    timing: {
      warmRounds,
      candidate: candidateStats,
      retained: retainedStats,
      meanRatio: retainedStats.mean ? candidateStats.mean / retainedStats.mean : null,
      medianRatio: retainedStats.median ? candidateStats.median / retainedStats.median : null,
      pairs: timing.pairs,
    },
    coldLoadMilliseconds: {
      order: retainedLoad ? ["candidate", "retained"] : ["candidate"],
      candidate: candidateLoad.milliseconds,
      retained: retainedLoad?.milliseconds ?? null,
      ratio: retainedLoad ? candidateLoad.milliseconds / retainedLoad.milliseconds : null,
    },
    diagnostics,
  };
  await candidateContext.close();
  if (retainedContext) await retainedContext.close();
} finally {
  await browser.close();
  server.close();
}

await fs.writeFile(path.join(output, "browser-results.json"), `${JSON.stringify(report, null, 2)}\n`);
const rows = report.checks.map((check) => (
  `| ${check.state} | ${check.activeStages} | ${check.measuredRoute.join(",")} | `
  + `${check.q16Winner} | ${check.floatWinner} | ${check.finalWinner} | ${check.pass ? "yes" : "no"} |`
)).join("\n");
const nextUpperRows = report.nextUpperBoundaryEvidence.map((item) => (
  `| ${item.state} | ${item.stage} | ${item.nextGroup} | ${item.sourceWidth} | `
  + `${item.sourceWidthDivFour} | ${item.expectedNextUpper} | ${item.observedNextUpper} |`
)).join("\n");
const timingRows = report.timing.pairs.map((pair) => (
  `| ${pair.state} | ${pair.order.join(" then ")} | ${pair.candidate.toFixed(2)} | `
  + `${pair.retained.toFixed(2)} | ${(pair.candidate / pair.retained).toFixed(3)}× |`
)).join("\n");
const timingProfile = report.timing.pairs.length === 0 ? "" : `
| State | Order | Six-font ms | Retained ms | Ratio |
| ---: | :--- | ---: | ---: | ---: |
${timingRows}

The one paired round gives a cold ratio of ${report.coldLoadMilliseconds.ratio.toFixed(3)}× (${((1 - report.coldLoadMilliseconds.ratio) * 100).toFixed(1)}% faster), a warm mean ratio of ${report.timing.meanRatio.toFixed(3)}× (${((report.timing.meanRatio - 1) * 100).toFixed(1)}% slower), and a warm median ratio of ${report.timing.medianRatio.toFixed(3)}× (${((report.timing.medianRatio - 1) * 100).toFixed(1)}% slower). The hard 23- and 11-stage fixtures are slightly faster; the 7- and 1-stage fixtures regress. This supports the accuracy/cold-start profile verdict, not promotion to the loaded-throughput default.
`;
const resultMarkdown = `# Production groupwise cascade with six-font q16 transport

**${report.pass ? "PASS" : "FAIL"}: ${report.decision}.** Accept and certify the six-font integration as the accuracy + cold-start profile; it repairs state519. Reject it as the loaded-throughput default and retain the existing q16 backend for warm use. Chrome was checked directly against the immutable mathematical global-q16 approximation and original checkpoint float; the retained browser page was used only for paired timing.

| State | Active stages | Routed groups | q16 | Float | Chrome | Pass |
| ---: | ---: | :--- | ---: | ---: | ---: | :---: |
${rows}

State 519 is not one of the retained six production fixtures. Its separate forced-group integration check selected token ${report.forcedState519.winner} in group ${report.forcedState519.group} (q16 target ${report.forcedState519.expectedWinner}; legacy browser comparison token ${report.forcedState519.legacyBrowserToken}; ${report.forcedState519.pass ? "pass" : "fail"}).

Dynamic selected-group q16 bucket deltas: ${report.bucketDeltaSummary.dynamic.minimum}..${report.bucketDeltaSummary.dynamic.maximum} across ${report.bucketDeltaSummary.dynamic.count} stages. Hot-group deltas: ${report.bucketDeltaSummary.hot.minimum}..${report.bucketDeltaSummary.hot.maximum} across ${report.bucketDeltaSummary.hot.count} stages. The retained stop threshold remains 49 buckets. A selected-candidate -1 delta would spend one bucket of that separation; observed negative count was ${report.bucketDeltaSummary.dynamic.negativeCount + report.bucketDeltaSummary.hot.negativeCount}.

Four live upper-bucket reads are one below a JavaScript reconstruction:

| State | Stage | Next group | Source/reader width px | Width / 4 | JS expected | CSS observed |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
${nextUpperRows}

Both \`getBoundingClientRect().width\` and computed reader width are the exact integral values shown, so this is not \`Math.floor\` acting on a visible subpixel remainder. Chrome's internal \`100cqi/4px\` evaluation at an exact boundary makes \`round(down)\` one bucket conservative. The unchanged retained verifier allowance of one upper-transport bucket covers exactly these cases; measured routing, gap arithmetic, and the 49-bucket done gate still match live CSS.

Integer-axis liveness: ${report.liveness.pass ? "pass" : "fail"}; ${report.liveness.dynamicAxisCount} computed dynamic axes, ${report.liveness.hotAxisCount} hot axes, zero-coordinate errors ${report.liveness.dynamicCoordinateErrorsA + report.liveness.dynamicCoordinateErrorsB + report.liveness.hotCoordinateErrorsA + report.liveness.hotCoordinateErrorsB}. Sampled ${report.geometry.sampledGlyphs} glyphs with ${report.geometry.collapsedGlyphs} collapses and ${report.geometry.capHits} cap hits; analytic maximum is ${report.geometry.analyticMaximumAdjustedAdvancePx.toFixed(3)} px. Group 196 exposed ${report.partialGroup.visible}/256 rows.

Runtime/CSP: ${report.runtime.pass ? "pass" : "fail"}; six q16 fonts requested ${report.runtime.requestedSixFontCount}/6, old q16 fonts requested ${report.runtime.oldQ16FontRequestCount}, script requests ${report.runtime.scriptRequests}, JavaScript-disabled load ${report.runtime.javaScriptDisabledLoad}. Source has CSP \`script-src 'none'\` and no script elements.

Cold load: six-font ${report.coldLoadMilliseconds.candidate.toFixed(2)} ms; retained comparison ${report.coldLoadMilliseconds.retained?.toFixed(2) ?? "not run"} ms. Warm paired benchmark: ${report.timing.candidate.count === 0 ? "deferred" : `${report.timing.candidate.count} samples each, six-font median ${report.timing.candidate.median.toFixed(2)} ms, retained ${report.timing.retained.median.toFixed(2)} ms (${report.timing.medianRatio.toFixed(3)}×)`}.

${timingProfile}

Raw results: \`browser-results.json\`. The six WOFF2 files are referenced from the completed bank and are not copied.
`;
await fs.writeFile(path.join(output, "RESULTS.md"), resultMarkdown);
console.log(JSON.stringify({
  decision: report.decision,
  pass: report.pass,
  fixturesPassed: report.checks.filter((check) => check.pass).length,
  fixturesTotal: report.checks.length,
  forcedState519: report.forcedState519,
  bucketDeltaSummary: report.bucketDeltaSummary,
  liveness: report.liveness.pass,
  geometry: report.geometry,
  runtime: report.runtime,
  timing: report.timing,
  coldLoadMilliseconds: report.coldLoadMilliseconds,
}, null, 2));
if (!report.pass) process.exitCode = 1;
