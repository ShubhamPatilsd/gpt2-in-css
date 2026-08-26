import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const sizes = (process.env.PACKED_HVAR_SIZES ?? "64,128,256,512,768")
  .split(",").map(Number);
const rounds = Number.parseInt(process.env.PACKED_HVAR_ROUNDS ?? "9", 10);
const mode = process.env.PACKED_HVAR_MODE ?? "animation";
if (!new Set(["animation", "registered"]).has(mode)) {
  throw new Error("PACKED_HVAR_MODE must be animation or registered");
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
const reports = [];
try {
  for (const size of sizes) {
    const reference = JSON.parse(await fs.readFile(
      new URL(`../experiments/packed-hvar-transport-scaling/n${size}/reference.json`, import.meta.url),
      "utf8",
    ));
    const context = await browser.newContext({
      javaScriptEnabled: false,
      viewport: { width: 800, height: 200 },
    });
    const page = await context.newPage();
    const loadStarted = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/packed-hvar-transport-scaling/n${size}/${
        mode === "registered" ? "registered.html" : "index.html"}`,
      { waitUntil: "load", timeout: 180000 },
    );
    await page.evaluate(() => document.fonts.ready);
    const loadMilliseconds = performance.now() - loadStarted;

    async function read() {
      return page.locator(".metric").evaluateAll((elements) =>
        elements.map((element) => element.getBoundingClientRect().width));
    }
    const initial = await read();
    const samples = [];
    for (let round = 0; round < rounds; round += 1) {
      const caseIndex = (round + 1) % 2;
      const started = performance.now();
      await page.locator(`#case${caseIndex}`).evaluate((element) => {
        element.checked = true;
      });
      const widths = await read();
      const errors = widths.map(
        (width, output) => width - reference.expectedWidths[caseIndex][output],
      );
      samples.push({
        caseIndex,
        milliseconds: performance.now() - started,
        rmse: Math.sqrt(
          errors.reduce((sum, error) => sum + error * error, 0) / errors.length,
        ),
        maximumError: Math.max(...errors.map(Math.abs)),
      });
    }
    const initialErrors = initial.map(
      (width, output) => width - reference.expectedWidths[0][output],
    );
    const diagnostics = await page.locator(".metric").first().evaluate(
      (element, shardCount) => {
        const text = element.firstChild;
        const partWidths = [];
        for (let shard = 0; shard < shardCount; shard += 1) {
          const range = document.createRange();
          range.setStart(text, shard * 2);
          range.setEnd(text, shard * 2 + 2);
          partWidths.push(range.getBoundingClientRect().width);
        }
        const variation = getComputedStyle(element).fontVariationSettings;
        return {
          partWidths,
          textLength: text.length,
          variationCount: [...variation.matchAll(/"X\d{3}"/g)].length,
          variationHead: variation.slice(0, 120),
          variationTail: variation.slice(-120),
        };
      },
      reference.shards,
    );
    const report = {
      size,
      mode,
      groups: reference.groups,
      shards: reference.shards,
      loadMilliseconds,
      mutationMedianMilliseconds: median(samples.map((sample) => sample.milliseconds)),
      settledMutationMedianMilliseconds: median(
        samples.slice(2).map((sample) => sample.milliseconds),
      ),
      maximumRmse: Math.max(
        Math.sqrt(initialErrors.reduce((sum, error) => sum + error * error, 0) /
          initialErrors.length),
        ...samples.map((sample) => sample.rmse),
      ),
      maximumError: Math.max(
        ...initialErrors.map(Math.abs),
        ...samples.map((sample) => sample.maximumError),
      ),
      elements: await page.locator("*").count(),
      htmlBytes: mode === "registered" ? reference.registeredHtmlBytes : reference.htmlBytes,
      cssBytes: mode === "registered" ? reference.registeredCssBytes : reference.cssBytes,
      sourceFontBytes: reference.sourceFontBytes,
      matrixFontBytes: reference.matrixFontBytes,
      diagnostics,
    };
    reports.push(report);
    console.log(JSON.stringify(report));
    await context.close();
  }
  await fs.writeFile(
    new URL(`../experiments/packed-hvar-transport-scaling/browser-results-${mode}.json`, import.meta.url),
    JSON.stringify(reports, null, 2) + "\n",
  );
} finally {
  await browser.close();
}
