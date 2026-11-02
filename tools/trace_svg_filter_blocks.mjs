import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = process.env.SVG_CHAIN_URL ??
  "http://127.0.0.1:4178/experiments/svg-filter-full-block";
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/svg-filter-full-block/reference.json", import.meta.url,
), "utf8"));

async function decode(png, range) {
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: info.width * info.height }, (_, index) =>
    (data[index * info.channels] / 255 - reference.surface_center) * 2 * range
  );
}

function errors(actual, expected) {
  const values = actual.map((value, index) => value - expected[index]);
  return {
    max: Math.max(...values.map(Math.abs)),
    rmse: Math.sqrt(values.reduce((sum, value) => sum + value * value, 0) / values.length),
    levels: new Set(actual).size,
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 200 } });
  const trace = [];
  for (const item of reference.block_outputs) {
    const file = item.block === 1 ? "chain.html" : `chain-${item.block}blocks.html`;
    await page.goto(`${baseUrl}/${file}?trace=${Date.now()}`, { waitUntil: "load", timeout: 120000 });
    const originalPng = await page.locator("svg").screenshot({ animations: "disabled", timeout: 120000 });
    await page.locator("#chain-ln1 feImage").first().evaluate(
      (element) => element.setAttribute("href", "x-alt.png"),
    );
    const alternatePng = await page.locator("svg").screenshot({ animations: "disabled", timeout: 120000 });
    trace.push({
      block: item.block,
      original: errors(await decode(originalPng, item.range), item.expected),
      alternate: errors(await decode(alternatePng, item.range), item.alternate),
    });
  }
  console.log(JSON.stringify(trace, null, 2));
} finally {
  await browser.close();
}
