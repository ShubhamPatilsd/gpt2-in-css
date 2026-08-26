import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.HVAR_LOOKUP_ROUNDS ?? "16", 10);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/hvar-token-embedding-lookup/reference.json", import.meta.url),
  "utf8",
));

function stats(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maximumError: Math.max(...errors.map(Math.abs)),
  };
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 800, height: 200 },
  });
  const page = await context.newPage();
  const started = performance.now();
  await page.goto(
    "http://127.0.0.1:4178/experiments/hvar-token-embedding-lookup/index.html",
    { waitUntil: "load", timeout: 180000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const loadMilliseconds = performance.now() - started;
  async function read() {
    return page.locator(".consumer").evaluateAll((elements) =>
      elements.map((element) => Number(getComputedStyle(element).getPropertyValue("--value"))));
  }
  const initial = await read();
  const samples = [];
  for (let index = 0; index < rounds; index += 1) {
    const query = (index + 1) % reference.tokens.length;
    const before = performance.now();
    await page.locator(`#t${query}`).evaluate((element) => { element.checked = true; });
    const values = await read();
    samples.push({
      query,
      token: reference.tokens[query],
      milliseconds: performance.now() - before,
      error: stats(values, reference.expected[query]),
    });
  }
  const report = {
    loadMilliseconds,
    initialError: stats(initial, reference.expected[0]),
    mutationMedianMilliseconds: median(samples.map(({ milliseconds }) => milliseconds)),
    mutationMaximumMilliseconds: Math.max(...samples.map(({ milliseconds }) => milliseconds)),
    maximumRmse: Math.max(...samples.map(({ error }) => error.rmse)),
    maximumError: Math.max(...samples.map(({ error }) => error.maximumError)),
    finite: samples.every(({ error }) => Number.isFinite(error.rmse)),
    elements: await page.locator("*").count(),
    htmlBytes: reference.htmlBytes,
    fontBytes: reference.fontBytes,
    samples,
  };
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
