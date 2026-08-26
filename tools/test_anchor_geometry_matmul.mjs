import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rootUrl = process.env.ANCHOR_GEOMETRY_URL ??
  "http://127.0.0.1:4178/experiments/anchor-geometry-matmul";
const experimentDir = new URL(
  "../experiments/anchor-geometry-matmul/", import.meta.url,
);
const manifest = JSON.parse(await fs.readFile(new URL("manifest.json", experimentDir), "utf8"));

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
const results = [];
try {
  for (const item of manifest) {
    const reference = JSON.parse(await fs.readFile(
      new URL(`${item.size}.json`, experimentDir), "utf8",
    ));
    const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
    const started = performance.now();
    let failure = null;
    try {
      await page.goto(`${rootUrl}/${item.size}.html?run=${Date.now()}`, {
        waitUntil: "load",
        timeout: 120000,
      });
      const loadMilliseconds = performance.now() - started;
      const widths = await page.locator(".v").evaluateAll((elements) =>
        elements.map((element) => element.getBoundingClientRect().width));
      const measuredMilliseconds = performance.now() - started;
      const stages = {};
      for (const [stageIndex, stage] of ["x", "y", "z"].entries()) {
        const encoded = widths.slice(stageIndex * item.size, (stageIndex + 1) * item.size);
        const decoded = encoded.map((value) => (value - reference.base) / reference.scale);
        stages[stage] = summarize(decoded, reference[stage]);
      }
      results.push({
        ...item,
        loadMilliseconds,
        measureMilliseconds: measuredMilliseconds - loadMilliseconds,
        totalMilliseconds: measuredMilliseconds,
        stages,
      });
    } catch (error) {
      failure = String(error?.stack ?? error);
      results.push({ ...item, failure, totalMilliseconds: performance.now() - started });
    } finally {
      await page.close();
    }
    console.log(JSON.stringify(results.at(-1)));
  }
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("results.json", experimentDir), `${JSON.stringify(results, null, 2)}\n`,
);
