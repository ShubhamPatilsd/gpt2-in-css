import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.GRID_OUTPUT_HEAD_ROUNDS ?? "7", 10);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/grid-hierarchical-output-head/reference.json", import.meta.url),
  "utf8",
));

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
    "http://127.0.0.1:4178/experiments/grid-hierarchical-output-head/index.html",
    { waitUntil: "load", timeout: 180000 },
  );
  const loadMilliseconds = performance.now() - started;

  async function read() {
    return page.locator("#result").evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        group: Number(style.getPropertyValue("--group")),
        local: Number(style.getPropertyValue("--local")),
        winner: Number(style.getPropertyValue("--winner")),
        bucket: Number(style.getPropertyValue("--bucket")),
        width: element.getBoundingClientRect().width,
      };
    });
  }

  const initial = await read();
  const samples = [];
  for (let index = 0; index < rounds; index += 1) {
    const query = (index + 1) % reference.prompts.length;
    const before = performance.now();
    await page.locator(`#q${query}`).evaluate((element) => { element.checked = true; });
    const output = await read();
    samples.push({
      query,
      milliseconds: performance.now() - before,
      output,
      expectedWinner: reference.winners[query],
      expectedBucket: reference.winnerBuckets[query],
    });
  }
  const report = {
    loadMilliseconds,
    initial,
    expectedInitialWinner: reference.winners[0],
    expectedInitialBucket: reference.winnerBuckets[0],
    mutationMedianMilliseconds: median(samples.map(({ milliseconds }) => milliseconds)),
    mutationMaximumMilliseconds: Math.max(...samples.map(({ milliseconds }) => milliseconds)),
    maximumBucketError: Math.max(
      Math.abs(initial.bucket - reference.winnerBuckets[0]),
      ...samples.map(({ output, expectedBucket }) =>
        Math.abs(output.bucket - expectedBucket)),
    ),
    correct: initial.winner === reference.winners[0] &&
      samples.every(({ output, expectedWinner, expectedBucket }) =>
        output.winner === expectedWinner),
    elements: await page.locator("*").count(),
    htmlBytes: (await fs.stat(new URL(
      "../experiments/grid-hierarchical-output-head/index.html", import.meta.url,
    ))).size,
    cssBytes: (await fs.stat(new URL(
      "../experiments/grid-hierarchical-output-head/index.css", import.meta.url,
    ))).size,
    samples,
  };
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
