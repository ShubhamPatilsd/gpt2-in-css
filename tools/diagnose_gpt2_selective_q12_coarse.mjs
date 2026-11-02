#!/usr/bin/env node
/* Compare live mixed coarse group widths with the mathematical width oracle. */

import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.PLAYWRIGHT_NODE_MODULES
  ?? new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const workspace = path.resolve(new URL("..", import.meta.url).pathname);
const experiment = "gpt2-groupwise-cauchy-blockflow-production-selective-q12-top32";
const output = path.join(workspace, "experiments", experiment);
const reference = JSON.parse(await fs.readFile(path.join(output, "reference.json"), "utf8"));
const fixtures = reference.certifiedFixtures;
const predicted = reference.groupwiseFixtures.predictedCoarseWidths;
const selected = new Set(reference.selectivePrecision.groups);

function fixtureStyle(fixture) {
  const properties = fixtures.hiddenVectors[fixture]
    .map((value, dimension) => `--h${dimension}:${value}`);
  properties.push(`--score-offset:${-fixtures.scoreFloors[fixture] * 256 * 4}px`);
  properties.push(`--query-norm:${Math.sqrt(fixtures.hiddenVectors[fixture]
    .reduce((sum, value) => sum + value * value, 0))}`);
  return properties.join(";");
}

function statistics(values) {
  const sorted = [...values].sort((a, b) => a.delta - b.delta);
  return {
    minimum: sorted[0].delta,
    maximum: sorted.at(-1).delta,
    negativeCount: values.filter((value) => value.delta < -0.03).length,
    positiveCount: values.filter((value) => value.delta > 0.03).length,
    worstNegative: sorted.slice(0, 5),
    worstPositive: sorted.slice(-5).reverse(),
  };
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

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
  page.setDefaultTimeout(900_000);
  await page.goto(`${baseUrl}/experiments/${experiment}/control.html`, {
    waitUntil: "load", timeout: 900_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  const rows = [];
  for (let fixture = 0; fixture < fixtures.hiddenVectors.length; fixture += 1) {
    await page.evaluate((style) => {
      for (const element of [document.querySelector(".cascade"), document.querySelector("#model")]) {
        element.style.cssText = style;
      }
    }, fixtureStyle(fixture));
    for (let pass = 0; pass < 3; pass += 1) {
      await page.locator("#result").evaluate((element) => element.getBoundingClientRect().width);
    }
    const widths = await page.locator(".group-wrapper").evaluateAll(
      (elements) => elements.map((element) => element.getBoundingClientRect().width),
    );
    const q10 = [];
    const q12 = [];
    for (let group = 2; group < reference.groups; group += 1) {
      const value = {
        group,
        delta: widths[group] - predicted[fixture][group],
        liveWidth: widths[group],
        predictedWidth: predicted[fixture][group],
      };
      (selected.has(group) ? q12 : q10).push(value);
    }
    rows.push({ fixture, q10: statistics(q10), q12: statistics(q12) });
  }
  report = { experiment, chrome: await browser.version(), fixtures: rows };
  await page.close();
} finally {
  await browser.close();
  server.close();
}

await fs.writeFile(path.join(output, "coarse-diagnostics.json"), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
