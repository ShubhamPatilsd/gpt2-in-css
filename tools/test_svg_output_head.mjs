import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = process.env.SVG_OUTPUT_HEAD_URL ??
  "http://127.0.0.1:4178/experiments/svg-filter-output-head";
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/svg-filter-output-head/reference.json", import.meta.url,
), "utf8"));

async function readScores(page) {
  const png = await page.locator("svg").screenshot({
    animations: "disabled", timeout: 180000,
  });
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const scores = new Float64Array(reference.vocabulary);
  for (let token = 0; token < reference.vocabulary; token += 1) {
    const x = Math.floor(token / reference.rows_per_column);
    const y = token % reference.rows_per_column;
    scores[token] = (data[(y * info.width + x) * info.channels] / 255
      - reference.surface_center) * 2 * reference.output_range;
  }
  return scores;
}

function topIds(scores, count = 5) {
  return Array.from(scores, (score, token) => ({ score, token }))
    .sort((left, right) => right.score - left.score)
    .slice(0, count)
    .map(({ token }) => reference.token_order?.[token] ?? token);
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 100, height: 2200 } });
  const coldStart = performance.now();
  await page.goto(`${baseUrl}/index.html?run=${Date.now()}`, {
    waitUntil: "load", timeout: 180000,
  });
  const original = await readScores(page);
  const coldMilliseconds = performance.now() - coldStart;
  await page.locator('feImage[href="input.png"]').evaluate((element) => {
    element.setAttribute("href", "input-alt.png");
  });
  const warmStart = performance.now();
  const alternate = await readScores(page);
  const warmMilliseconds = performance.now() - warmStart;
  const originalTop5 = topIds(original);
  const alternateTop5 = topIds(alternate);
  const connectedColdStart = performance.now();
  await page.goto(`${baseUrl}/connected.html?run=${Date.now()}`, {
    waitUntil: "load", timeout: 180000,
  });
  const connectedOriginal = await readScores(page);
  const connectedColdMilliseconds = performance.now() - connectedColdStart;
  await page.locator('feImage[href$="/bucket-x.png"]').first().evaluate((element) => {
    element.setAttribute("href", "../svg-filter-full-block/bucket-x-alt.png");
  });
  const connectedWarmStart = performance.now();
  const connectedAlternate = await readScores(page);
  const connectedWarmMilliseconds = performance.now() - connectedWarmStart;
  const connectedOriginalTop5 = topIds(connectedOriginal);
  const connectedAlternateTop5 = topIds(connectedAlternate);
  const result = {
    originalTop5,
    alternateTop5,
    expectedOriginalTop5: reference.original_top5,
    expectedAlternateTop5: reference.alternate_top5,
    originalWinnerCorrect: originalTop5[0] === reference.original_winner,
    alternateWinnerCorrect: alternateTop5[0] === reference.alternate_winner,
    connectedOriginalTop5,
    connectedAlternateTop5,
    connectedOriginalWinnerCorrect:
      connectedOriginalTop5[0] === reference.original_winner,
    connectedAlternateWinnerCorrect:
      connectedAlternateTop5[0] === reference.alternate_winner,
    distinctOriginalScores: new Set(Array.from(original, (value) => value.toFixed(8))).size,
    distinctAlternateScores: new Set(Array.from(alternate, (value) => value.toFixed(8))).size,
    coldMilliseconds,
    warmMilliseconds,
    connectedColdMilliseconds,
    connectedWarmMilliseconds,
  };
  console.log(JSON.stringify(result, null, 2));
  if (!result.originalWinnerCorrect || !result.alternateWinnerCorrect
      || !result.connectedOriginalWinnerCorrect
      || !result.connectedAlternateWinnerCorrect) {
    process.exitCode = 1;
  }
} finally {
  await browser.close();
}
