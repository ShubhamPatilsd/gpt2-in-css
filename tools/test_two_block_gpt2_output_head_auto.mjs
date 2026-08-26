import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.TWO_BLOCK_HEAD_AUTO_ROUNDS ?? "3", 10);
const timeoutMilliseconds = Number.parseInt(
  process.env.TWO_BLOCK_HEAD_AUTO_TIMEOUT ?? "120000",
  10,
);
const navigationTimeoutMilliseconds = Number.parseInt(
  process.env.TWO_BLOCK_HEAD_AUTO_NAV_TIMEOUT ?? "240000",
  10,
);
const stem = "view-timeline-two-block-with-gpt2-output-head-auto";
const reference = JSON.parse(await fs.readFile(
  new URL(`../experiments/gpt2-block-css/${stem}-reference.json`, import.meta.url),
  "utf8",
));
const url = `http://127.0.0.1:4178/experiments/gpt2-block-css/${stem}.html`;

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

async function runOnce(context, cold) {
  const page = await context.newPage();
  const started = performance.now();
  await page.goto(url, {
    waitUntil: "domcontentloaded",
    timeout: navigationTimeoutMilliseconds,
  });
  const outcome = await page.evaluate(async ({ expected, timeout }) => {
    const gate = document.querySelector(".head-gate");
    const result = document.querySelector("#result");
    const started = performance.now();
    let gateMilliseconds = null;
    let frames = 0;
    while (performance.now() - started < timeout) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
      frames += 1;
      const gateStyle = getComputedStyle(gate);
      const ready = Number(gateStyle.getPropertyValue("--head-ready"));
      if (ready === 1 && gateMilliseconds === null) {
        gateMilliseconds = performance.now() - started;
      }
      if (ready === 1) {
        const style = getComputedStyle(result);
        const winner = Number(style.getPropertyValue("--winner"));
        const bucket = Number(style.getPropertyValue("--bucket"));
        if (winner === expected.winner &&
            Math.abs(bucket - expected.bucket) <= expected.bucketTolerance) {
          return {
            ready,
            winner,
            group: Number(style.getPropertyValue("--group")),
            local: Number(style.getPropertyValue("--local")),
            bucket,
            gateMilliseconds,
            resultMilliseconds: performance.now() - started,
            frames,
          };
        }
      }
    }
    const gateStyle = getComputedStyle(gate);
    const resultStyle = getComputedStyle(result);
    return {
      ready: Number(gateStyle.getPropertyValue("--head-ready")),
      winner: Number(resultStyle.getPropertyValue("--winner")),
      group: Number(resultStyle.getPropertyValue("--group")),
      local: Number(resultStyle.getPropertyValue("--local")),
      bucket: Number(resultStyle.getPropertyValue("--bucket")),
      gateMilliseconds,
      resultMilliseconds: performance.now() - started,
      frames,
      timedOut: true,
    };
  }, {
    expected: {
      winner: reference.quantizedWinner,
      bucket: reference.winnerBucket,
      bucketTolerance: 8,
    },
    timeout: timeoutMilliseconds,
  });
  const navigationToResultMilliseconds = performance.now() - started;
  await page.close();
  return {
    cold,
    navigationToResultMilliseconds,
    ...outcome,
    correct: outcome.winner === reference.quantizedWinner,
    denseCorrect: outcome.winner === reference.denseWinner,
    bucketCorrect: Math.abs(outcome.bucket - reference.winnerBucket) <= 8,
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 900, height: 240 } });
  const cold = await runOnce(context, true);
  const warm = [];
  for (let round = 0; round < rounds; round += 1) {
    warm.push(await runOnce(context, false));
  }
  const report = {
    chrome: await browser.version(),
    gateMode: reference.gateMode,
    rounds,
    expectedDenseWinner: reference.denseWinner,
    expectedQuantizedWinner: reference.quantizedWinner,
    cold,
    warmMedianMilliseconds: median(
      warm.map(({ navigationToResultMilliseconds }) => navigationToResultMilliseconds),
    ),
    warmMinimumMilliseconds: Math.min(
      ...warm.map(({ navigationToResultMilliseconds }) => navigationToResultMilliseconds),
    ),
    warmMaximumMilliseconds: Math.max(
      ...warm.map(({ navigationToResultMilliseconds }) => navigationToResultMilliseconds),
    ),
    allCorrect: cold.correct && cold.bucketCorrect &&
      warm.every(({ correct, bucketCorrect }) => correct && bucketCorrect),
    allDenseCorrect: cold.denseCorrect && warm.every(({ denseCorrect }) => denseCorrect),
    warm,
  };
  await fs.writeFile(
    new URL(`../experiments/gpt2-block-css/${stem}-browser.json`, import.meta.url),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
