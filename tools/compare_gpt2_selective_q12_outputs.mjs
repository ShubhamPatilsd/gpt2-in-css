#!/usr/bin/env node
/* Compare final live outputs of selective-q12 and retained production pages. */

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
const candidateName = "gpt2-groupwise-cauchy-blockflow-production-selective-q12-top32";
const retainedName = "gpt2-groupwise-cauchy-blockflow-production-range";
const output = path.join(workspace, "experiments", candidateName);
const reference = JSON.parse(await fs.readFile(path.join(output, "reference.json"), "utf8"));
const fixtures = reference.certifiedFixtures;
const stages = reference.stages;

function fixtureStyle(fixture) {
  const hidden = fixtures.hiddenVectors[fixture];
  const properties = hidden.map((value, dimension) => `--h${dimension}:${value}`);
  properties.push(`--score-offset:${-fixtures.scoreFloors[fixture] * 256 * 4}px`);
  properties.push(`--query-norm:${Math.sqrt(hidden.reduce((sum, value) => sum + value * value, 0))}`);
  return properties.join(";");
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

async function load(context, name) {
  const page = await context.newPage();
  page.setDefaultTimeout(900_000);
  await page.goto(`${baseUrl}/experiments/${name}/index.html`, {
    waitUntil: "load", timeout: 900_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  return page;
}

async function apply(page, fixture) {
  await page.evaluate((style) => {
    for (const element of [document.querySelector(".cascade"), document.querySelector("#model")]) {
      element.style.cssText = style;
    }
  }, fixtureStyle(fixture));
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
    let finalWinner = null;
    let finalBucket = null;
    let activeStages = 0;
    for (let stage = 0; stage < stageCount; stage += 1) {
      if (getComputedStyle(document.querySelector(`#mixed-stage-${stage}`)).display === "none") break;
      const fine = getComputedStyle(document.querySelector(
        stage === 0 ? "#fine-result" : `#fine-result-${stage}`,
      ));
      finalWinner = Number(fine.getPropertyValue(`--best-winner-${stage}`));
      finalBucket = Number(fine.getPropertyValue(`--best-bucket-${stage}`));
      activeStages += 1;
      const remaining = getComputedStyle(document.querySelector(`#remaining-result-${stage + 1}`));
      if (Number(remaining.getPropertyValue(`--done-${stage}`)) === 1) break;
    }
    return { finalWinner, finalBucket, activeStages };
  }, stages);
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const candidateContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const retainedContext = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const candidate = await load(candidateContext, candidateName);
  const retained = await load(retainedContext, retainedName);
  const rows = [];
  for (let fixture = 0; fixture < fixtures.hiddenVectors.length; fixture += 1) {
    await apply(candidate, fixture);
    await settle(candidate);
    await apply(retained, fixture);
    await settle(retained);
    const candidateOutput = await observe(candidate);
    const retainedOutput = await observe(retained);
    rows.push({
      fixture,
      sourceState: fixtures.sourceStateIndices[fixture],
      mathematicalTarget: fixtures.denseWinners[fixture],
      candidate: candidateOutput,
      retained: retainedOutput,
      sameBackendOutput: candidateOutput.finalWinner === retainedOutput.finalWinner
        && candidateOutput.finalBucket === retainedOutput.finalBucket,
    });
  }
  report = {
    chrome: await browser.version(),
    candidate: candidateName,
    retained: retainedName,
    fixtures: rows,
    allBackendOutputsMatch: rows.every((row) => row.sameBackendOutput),
  };
  await candidateContext.close();
  await retainedContext.close();
} finally {
  await browser.close();
  server.close();
}

await fs.writeFile(path.join(output, "output-comparison.json"), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));

