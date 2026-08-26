import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = process.env.MULTITOKEN_ATTENTION_URL ??
  "http://127.0.0.1:4178/experiments/gpt2-block-css/view-timeline-attention-2token.html";
const referencePath = process.env.MULTITOKEN_ATTENTION_REFERENCE ??
  "../experiments/gpt2-block-css/view-timeline-attention-2token-reference.json";
const reference = JSON.parse(await fs.readFile(new URL(
  referencePath,
  import.meta.url,
), "utf8"));

function summarize(actual, expected) {
  const errors = actual.flatMap((row, token) =>
    row.map((value, index) => value - expected[token][index])
  );
  return {
    maxError: Math.max(...errors.map(Math.abs)),
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
  const start = performance.now();
  await page.goto(`${url}?run=${Date.now()}`, { waitUntil: "load", timeout: 180000 });
  const values = await page.locator("#attention-result").evaluate((element) => {
    const styles = getComputedStyle(element);
    return Array.from({ length: 2 }, (_, token) =>
      Array.from({ length: 768 }, (_, index) => Number.parseFloat(
        styles.getPropertyValue(`--r1-${token}-${String(index).padStart(3, "0")}`),
      ))
    );
  });
  if (values.some((row) => row.some((value) => !Number.isFinite(value)))) {
    throw new Error("browser returned a non-finite two-token attention value");
  }
  const error = summarize(values, reference.residual);
  console.log(JSON.stringify({
    ...error,
    milliseconds: performance.now() - start,
    values: values.length * values[0].length,
  }, null, 2));
  if (error.rmse > 0.25) {
    throw new Error(`two-token browser attention RMSE ${error.rmse} exceeds 0.25`);
  }
} finally {
  await browser.close();
}
