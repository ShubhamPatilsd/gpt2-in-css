import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const sizes = (process.env.GRID_HIERARCHICAL_ARGMAX_SIZES ?? "256,4096,50257")
  .split(",").map(Number);
const rounds = Number.parseInt(process.env.GRID_HIERARCHICAL_ARGMAX_ROUNDS ?? "7", 10);

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
const reports = [];
try {
  for (const size of sizes) {
    const reference = JSON.parse(await fs.readFile(
      new URL(`../experiments/grid-hierarchical-argmax/${size}/reference.json`, import.meta.url),
      "utf8",
    ));
    const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
    const started = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/grid-hierarchical-argmax/${size}/index.html`,
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
          score: Number(style.getPropertyValue("--score")),
          width: element.getBoundingClientRect().width,
        };
      });
    }

    const initial = await read();
    const samples = [];
    for (let index = 0; index < rounds; index += 1) {
      const mode = (index + 1) % 2;
      const before = performance.now();
      await page.locator("#bank").evaluate((element, value) => {
        element.style.setProperty("--mode", String(value));
      }, mode);
      const output = await read();
      samples.push({
        mode,
        milliseconds: performance.now() - before,
        output,
        expectedWinner: mode ? reference.winnerB : reference.winnerA,
        expectedScore: mode ? reference.scoreB : reference.scoreA,
      });
    }
    reports.push({
      size,
      groups: reference.groups,
      loadMilliseconds,
      initial,
      expectedInitialWinner: reference.winnerA,
      expectedInitialScore: reference.scoreA,
      mutationMedianMilliseconds: median(samples.map(({ milliseconds }) => milliseconds)),
      mutationMaximumMilliseconds: Math.max(...samples.map(({ milliseconds }) => milliseconds)),
      correct: initial.winner === reference.winnerA &&
        initial.score === reference.scoreA &&
        samples.every(({ output, expectedWinner, expectedScore }) =>
          output.winner === expectedWinner && output.score === expectedScore),
      elements: await page.locator("*").count(),
      htmlBytes: (await fs.stat(new URL(
        `../experiments/grid-hierarchical-argmax/${size}/index.html`, import.meta.url,
      ))).size,
      samples,
    });
    await page.close();
  }
  console.log(JSON.stringify(reports, null, 2));
} finally {
  await browser.close();
}
