import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);

const baseUrl = process.env.SVG_BLOCK_URL ??
  "http://127.0.0.1:4178/experiments/svg-filter-full-block/staged.html";
const referencePath = new URL(
  "../experiments/svg-filter-full-block/reference.json",
  import.meta.url,
);
const reference = JSON.parse(await fs.readFile(referencePath, "utf8"));
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    maxError: Math.max(...errors.map(Math.abs)),
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    actualMin: Math.min(...actual),
    actualMax: Math.max(...actual),
    levels: new Set(actual.map((value) => value.toFixed(8))).size,
  };
}

async function pixels(locator) {
  const buffer = await locator.screenshot({ animations: "disabled" });
  const { data, info } = await sharp(buffer).raw().toBuffer({ resolveWithObject: true });
  const result = [];
  for (let i = 0; i < info.width * info.height; i += 1) {
    const offset = info.channels * i;
    result.push([
      data[offset],
      data[offset + 1],
      data[offset + 2],
      info.channels === 4 ? data[offset + 3] : 255,
    ]);
  }
  return result;
}

function signed(rows, range) {
  return rows.map(([r, g]) => (r - g) * range / 255);
}

function centered(rows, range) {
  return rows.map(([r]) => (r / 255 - reference.surface_center) * 2 * range);
}

const stageOrder = ["ln1-stage", "attention-stage", "ln2-stage", "fc-stage", "projection-stage"];

async function hideLaterStages(page, id) {
  const target = stageOrder.indexOf(id);
  for (const [index, stage] of stageOrder.entries()) {
    await page.locator(`#${stage}-surface`).evaluate(
      (element, visible) => { element.style.display = visible ? "block" : "none"; },
      index <= target,
    );
  }
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 3072, height: 900 } });
  await page.goto(baseUrl, { waitUntil: "load" });

  const stages = [
    ["ln1-stage", "n1", "n1_range", signed],
    ["attention-stage", "residual", "residual_range", centered],
    ["ln2-stage", "n2", "n2_range", signed],
    ["fc-stage", "hidden", "hidden_range", signed],
    ["projection-stage", "expected", "output_range", centered],
  ];
  const accuracy = {};
  for (const [id, expectedKey, rangeKey, decode] of stages) {
    await hideLaterStages(page, id);
    const surface = page.locator(`#${id}-surface`);
    await surface.evaluate((element) => {
      element.style.position = "static";
      element.style.left = "auto";
    });
    const actual = decode(await pixels(page.locator(`#${id}`)), reference[rangeKey]);
    accuracy[id] = summarize(actual, reference[expectedKey]);
    const largestIndex = reference[expectedKey].reduce(
      (best, value, index, values) => Math.abs(value) > Math.abs(values[best]) ? index : best,
      0,
    );
    accuracy[id].largestExpected = {
      index: largestIndex,
      expected: reference[expectedKey][largestIndex],
      actual: actual[largestIndex],
    };
    await surface.evaluate((element) => {
      element.style.position = "absolute";
      element.style.left = "0";
    });
  }

  const attentionDebug = {};
  for (const resultName of [
    "attention-row-scaled",
    "attention-total2",
    "attention-bias",
    "attention-row-signed",
    "attention-scales",
    "attention-common-signed",
    "attention-common",
  ]) {
    await page.reload({ waitUntil: "load" });
    await hideLaterStages(page, "attention-stage");
    await page.locator("#attention-stage-surface").evaluate((element) => {
      element.style.position = "static";
      element.style.left = "auto";
    });
    await page.locator("#attention-filter").evaluate((filter, input) => {
      const primitive = document.createElementNS("http://www.w3.org/2000/svg", "feOffset");
      primitive.setAttribute("in", input);
      primitive.setAttribute("dx", "-255");
      primitive.setAttribute("x", "0");
      primitive.setAttribute("y", "0");
      primitive.setAttribute("width", "1");
      primitive.setAttribute("height", "768");
      filter.append(primitive);
    }, resultName);
    const rows = await pixels(page.locator("#attention-stage"));
    attentionDebug[resultName] = {
      red: [Math.min(...rows.map((row) => row[0])), Math.max(...rows.map((row) => row[0]))],
      green: [Math.min(...rows.map((row) => row[1])), Math.max(...rows.map((row) => row[1]))],
      alpha: [Math.min(...rows.map((row) => row[3])), Math.max(...rows.map((row) => row[3]))],
      atLargestExpected: rows[reference.residual.reduce(
        (best, value, index, values) => Math.abs(value) > Math.abs(values[best]) ? index : best,
        0,
      )],
    };
  }

  const timings = [];
  for (let index = 0; index < 8; index += 1) {
    const run = await browser.newPage({ viewport: { width: 512, height: 900 } });
    const start = performance.now();
    await run.goto(`${baseUrl}?run=${index}-${Date.now()}`, { waitUntil: "load" });
    await run.locator("#projection-stage").screenshot({ animations: "disabled" });
    timings.push(performance.now() - start);
    await run.close();
  }
  const warm = timings.slice(1).sort((a, b) => a - b);
  const median = warm[Math.floor(warm.length / 2)];
  console.log(JSON.stringify({ accuracy, attentionDebug, timings, warmMedianMilliseconds: median }, null, 2));
} finally {
  await browser.close();
}
