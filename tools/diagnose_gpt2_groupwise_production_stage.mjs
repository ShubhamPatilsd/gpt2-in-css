#!/usr/bin/env node
/* Focused production-range diagnostic for remaining-upper bucket transport. */

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
const experiment = "gpt2-groupwise-cauchy-blockflow-production-range";
const output = path.join(workspace, "experiments", experiment);
const reference = JSON.parse(await fs.readFile(path.join(output, "reference.json"), "utf8"));
const fixtures = reference.certifiedFixtures;
const fixture = Number(process.env.GROUPWISE_DIAGNOSTIC_FIXTURE ?? 1);
const stages = reference.stages;

function fixtureStyle() {
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
    response.writeHead(200, { "content-type": types.get(path.extname(filename)) ?? "application/octet-stream" });
    response.end(body);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const baseUrl = `http://127.0.0.1:${server.address().port}`;

async function load(context, filename) {
  const page = await context.newPage();
  page.setDefaultTimeout(900_000);
  await page.goto(`${baseUrl}/experiments/${experiment}/${filename}`, {
    waitUntil: "load", timeout: 900_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  return page;
}

async function setInput(page) {
  await page.evaluate((style) => {
    for (const element of [document.querySelector(".cascade"), document.querySelector("#model")]) {
      element.style.cssText = style;
    }
  }, fixtureStyle());
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
      ]) await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
      const done = await page.locator(`#remaining-result-${stage + 1}`).evaluate(
        (element, property) => Number(getComputedStyle(element).getPropertyValue(property)),
        `--done-${stage}`,
      );
      if (done === 1) break;
    }
  }
}

function expectedRoute(widths) {
  const remaining = new Set(widths.map((_, group) => group));
  const route = [];
  for (let stage = 0; stage < stages; stage += 1) {
    let selected = -1;
    let maximum = -Infinity;
    for (const group of remaining) {
      if (widths[group] > maximum + 0.03) {
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
try {
  const candidateContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const controlContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const [candidate, control] = await Promise.all([
    load(candidateContext, "index.html"), load(controlContext, "control.html"),
  ]);
  await Promise.all([setInput(candidate), setInput(control)]);
  await Promise.all([settle(candidate), settle(control)]);
  const controlWidths = await control.locator(".group-wrapper").evaluateAll(
    (elements) => elements.map((element) => element.getBoundingClientRect().width),
  );
  const composed = controlWidths.map(
    (width, group) => width + reference.groupwiseFixtures.predictedBoundWidths[fixture][group],
  );
  const route = expectedRoute(composed);
  const observed = await candidate.evaluate(({ count }) => {
    const number = (style, property) => Number(style.getPropertyValue(property));
    let group = number(getComputedStyle(document.querySelector("#result")), "--group");
    const result = [];
    for (let stage = 0; stage < count; stage += 1) {
      const wrapper = getComputedStyle(document.querySelector(`#mixed-stage-${stage}`));
      if (wrapper.display === "none") break;
      const fine = getComputedStyle(document.querySelector(
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
      ));
      const remaining = getComputedStyle(document.querySelector(`#remaining-result-${stage + 1}`));
      const item = {
        stage,
        group,
        fineBucket: number(fine, `--fine-bucket-${stage}`),
        bestBucket: number(fine, `--best-bucket-${stage}`),
        nextUpperBucket: number(remaining, `--upper-bucket-${stage + 1}`),
        gap: number(remaining, `--certificate-gap-${stage}`),
        done: number(remaining, `--done-${stage}`),
      };
      result.push(item);
      if (item.done === 1) break;
      group = number(remaining, `--remaining-group-${stage + 1}`);
    }
    return result;
  }, { count: stages });
  console.log(JSON.stringify({
    fixture,
    sourceStateIndex: fixtures.sourceStateIndices[fixture],
    requiredOffline: fixtures.requiredGroupsAtCalibratedStop[fixture],
    stages: observed.map((item, index) => ({
      ...item,
      expectedGroup: route[index],
      expectedNextGroup: route[index + 1],
      expectedNextUpperBucket: Math.floor(composed[route[index + 1]] / 4),
      nextUpperDelta: item.nextUpperBucket - Math.floor(composed[route[index + 1]] / 4),
    })),
  }, null, 2));
  await candidateContext.close();
  await controlContext.close();
} finally {
  await browser.close();
  server.close();
}
