import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = process.env.SVG_CHAIN_URL ??
  "http://127.0.0.1:4178/experiments/svg-filter-full-block";
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/svg-filter-full-block/reference.json", import.meta.url,
), "utf8"));

async function decode(png) {
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: info.width * info.height }, (_, index) =>
    (data[index * info.channels] / 255 - reference.surface_center)
      * 2 * reference.grouped_ln_range
  );
}

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  const largestIndex = errors.reduce(
    (best, value, index) => Math.abs(value) > Math.abs(errors[best]) ? index : best, 0,
  );
  return {
    maxError: Math.max(...errors.map(Math.abs)),
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    levels: new Set(actual).size,
    largest: {
      index: largestIndex,
      actual: actual[largestIndex],
      expected: expected[largestIndex],
    },
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 200 } });
  await page.goto(`${baseUrl}/grouped-layernorm.html?run=${Date.now()}`, { waitUntil: "load" });
  let png = await page.locator("svg").screenshot({ animations: "disabled" });
  const original = summarize(await decode(png), reference.grouped_ln_expected);
  const debug = {};
  for (const name of ["grouped-ln-mean", "grouped-ln-variance"]) {
    await page.goto(`${baseUrl}/grouped-layernorm.html?debug=${name}-${Date.now()}`, { waitUntil: "load" });
    await page.locator("filter").evaluate((filter, input) => {
      const primitive = document.createElementNS("http://www.w3.org/2000/svg", "feOffset");
      primitive.setAttribute("in", input);
      primitive.setAttribute("dx", "-255");
      primitive.setAttribute("x", "0");
      primitive.setAttribute("y", "0");
      primitive.setAttribute("width", "1");
      primitive.setAttribute("height", "1");
      filter.append(primitive);
    }, name);
    await page.locator("svg").evaluate((svg) => {
      svg.setAttribute("width", "1");
      svg.setAttribute("height", "1");
      svg.setAttribute("viewBox", "0 0 1 1");
    });
    const { data } = await sharp(await page.locator("svg").screenshot({ animations: "disabled" }))
      .raw().toBuffer({ resolveWithObject: true });
    debug[name] = Array.from(data);
  }
  for (const name of [
    "grouped-ln-outlier-diff",
    "grouped-ln-outlier-normalized-signed",
    "grouped-ln-normalized-signed",
    "grouped-ln-scaled-signed",
  ]) {
    await page.goto(`${baseUrl}/grouped-layernorm.html?debug=${name}-${Date.now()}`, { waitUntil: "load" });
    await page.locator("filter").evaluate((filter, input) => {
      const primitive = document.createElementNS("http://www.w3.org/2000/svg", "feOffset");
      primitive.setAttribute("in", input);
      primitive.setAttribute("dy", "-255");
      primitive.setAttribute("x", "0");
      primitive.setAttribute("y", "0");
      primitive.setAttribute("width", "768");
      primitive.setAttribute("height", "1");
      filter.append(primitive);
    }, name);
    const { data, info } = await sharp(
      await page.locator("svg").screenshot({ animations: "disabled" }),
    ).raw().toBuffer({ resolveWithObject: true });
    debug[name] = [138, 447].map((index) =>
      Array.from(data.slice(index * info.channels, (index + 1) * info.channels))
    );
  }
  await page.goto(`${baseUrl}/grouped-layernorm.html?alternate=${Date.now()}`, { waitUntil: "load" });
  await page.locator('feImage[href="grouped-ln-x.png"]').evaluate(
    (element) => element.setAttribute("href", "grouped-ln-x-alt.png"),
  );
  png = await page.locator("svg").screenshot({ animations: "disabled" });
  const alternate = summarize(await decode(png), reference.grouped_ln_expected_alt);
  console.log(JSON.stringify({ original, alternate, debug }, null, 2));
  if (original.rmse > 0.15 || alternate.rmse > 0.15) {
    throw new Error("two-scale grouped layer normalization missed its accuracy gate");
  }
} finally {
  await browser.close();
}
