import fs from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = require("playwright"));
} catch {
  ({ chromium } = require(
    "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright",
  ));
}

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const directory = path.join(root, "experiments", "cross-shard-font-composition");
const reference = JSON.parse(await fs.readFile(path.join(directory, "reference.json")));
const browser = await chromium.launch({
  headless: true,
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
});
const page = await browser.newPage({ viewport: { width: 800, height: 400 } });
await page.goto(pathToFileURL(path.join(directory, "index.html")).href);
await page.evaluate(async () => {
  await document.fonts.ready;
  return document.fonts.status;
});

const measurements = [];
for (let index = 0; index < reference.cases.length; index += 1) {
  await page.evaluate((caseIndex) => {
    document.querySelector(`#case-${caseIndex}`).checked = true;
  }, index);
  const measured = await page.evaluate(() => ({
    fallbackRunWidth: document.querySelector("#sum").getBoundingClientRect().width,
    chWidth: document.querySelector("#single-face-metric").getBoundingClientRect().width,
    bridgeWidth: document.querySelector("#bridge").getBoundingClientRect().width,
    bridgeFontSize: Number.parseFloat(getComputedStyle(document.querySelector("#bridge-value")).fontSize),
  }));
  measurements.push({ ...reference.cases[index], measured });
}

const support = await page.evaluate(() => ({
  fontSizeFromAnchor: CSS.supports("font-size", "anchor-size(--sum width)"),
  variationFromAnchor: CSS.supports(
    "font-variation-settings",
    '"opsz" calc(anchor-size(--sum width) / 1px)',
  ),
  fontSizeFromCalcSize: CSS.supports("font-size", "calc-size(max-content, size)"),
  widthFromCalcSize: CSS.supports("width", "calc-size(max-content, size)"),
}));

for (const row of measurements) {
  for (const key of ["fallbackRunWidth", "chWidth"]) {
    if (Math.abs(row[key] - row.measured[key]) > 0.05) {
      throw new Error(`${key} mismatch: ${JSON.stringify(row)}`);
    }
  }
  if (Math.abs(row.measured.bridgeWidth - row.measured.fallbackRunWidth) > 0.05) {
    throw new Error(`bridge did not copy the fallback width: ${JSON.stringify(row)}`);
  }
  if (Math.abs(row.measured.bridgeFontSize - row.measured.fallbackRunWidth) > 0.05) {
    throw new Error(`container unit did not expose the bridge width: ${JSON.stringify(row)}`);
  }
}

console.log(JSON.stringify({ measurements, support }, null, 2));
await browser.close();
