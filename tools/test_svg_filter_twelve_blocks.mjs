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

function surfaceValue(byte) {
  const value = byte / 255;
  if (reference.filter_color !== "linearRGB") return value;
  return value <= 0.04045
    ? value / 12.92
    : ((value + 0.055) / 1.055) ** 2.4;
}

async function decode(png) {
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: info.width * info.height }, (_, index) =>
    (surfaceValue(data[index * info.channels]) - reference.surface_center)
      * 2 * reference.output_range_12blocks
  );
}

async function decodeRange(png, range) {
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: info.width * info.height }, (_, index) =>
    (surfaceValue(data[index * info.channels]) - reference.surface_center) * 2 * range
  );
}

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  const absolute = errors.map(Math.abs).sort((a, b) => a - b);
  return {
    maxError: absolute.at(-1),
    p99Error: absolute[Math.floor(absolute.length * 0.99)],
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    actualRange: [Math.min(...actual), Math.max(...actual)],
    levels: new Set(actual).size,
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 200 } });
  const start = performance.now();
  await page.goto(`${baseUrl}/chain-12blocks.html?run=${Date.now()}`, {
    waitUntil: "load", timeout: 120000,
  });
  let png = await page.locator("svg").screenshot({ animations: "disabled", timeout: 120000 });
  const coldMilliseconds = performance.now() - start;
  const original = summarize(await decode(png), reference.expected_12blocks);

  const timings = [];
  const mutation = {};
  for (const href of ["x-alt.png", "x.png", "x-alt.png", "x.png"]) {
    const mutationStart = performance.now();
    await page.locator("#chain-ln1 feImage").first().evaluate(
      (element, value) => element.setAttribute("href", value), href,
    );
    png = await page.locator("svg").screenshot({ animations: "disabled", timeout: 120000 });
    timings.push(performance.now() - mutationStart);
    mutation[href] = summarize(
      await decode(png),
      href === "x.png" ? reference.expected_12blocks : reference.expected_alt_12blocks,
    );
  }
  const sorted = timings.slice(1).sort((a, b) => a - b);
  await page.goto(`${baseUrl}/chain-12blocks-final-ln.html?ln=${Date.now()}`, {
    waitUntil: "load", timeout: 120000,
  });
  let finalLnPng = await page.locator("svg").screenshot({ animations: "disabled", timeout: 120000 });
  const finalLnOriginal = await decodeRange(finalLnPng, reference.final_ln_range);
  const finalLn = {
    original: summarize(
      finalLnOriginal,
      reference.expected_final_ln,
    ),
  };
  await page.locator("#chain-ln1 feImage").first().evaluate(
    (element) => element.setAttribute("href", "x-alt.png"),
  );
  finalLnPng = await page.locator("svg").screenshot({ animations: "disabled", timeout: 120000 });
  const finalLnAlternate = await decodeRange(finalLnPng, reference.final_ln_range);
  finalLn.alternate = summarize(
    finalLnAlternate,
    reference.expected_alt_final_ln,
  );
  await fs.writeFile(
    "/tmp/svg-filter-final-ln.json",
    JSON.stringify({ original: finalLnOriginal, alternate: finalLnAlternate }),
  );
  console.log(JSON.stringify({
    original,
    mutation,
    finalLn,
    coldMilliseconds,
    mutationTimings: timings,
    warmMedianMilliseconds: sorted[Math.floor(sorted.length / 2)],
  }, null, 2));
} finally {
  await browser.close();
}
