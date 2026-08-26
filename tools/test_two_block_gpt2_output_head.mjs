import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.TWO_BLOCK_HEAD_ROUNDS ?? "5", 10);
const frames = Number.parseInt(process.env.TWO_BLOCK_HEAD_FRAMES ?? "7", 10);
const headFrames = Number.parseInt(process.env.TWO_BLOCK_HEAD_SCORE_FRAMES ?? "2", 10);
const staged = process.env.TWO_BLOCK_HEAD_STAGED === "1";
const reference = JSON.parse(await fs.readFile(
  new URL(
    "../experiments/gpt2-block-css/view-timeline-two-block-with-gpt2-output-head-reference.json",
    import.meta.url,
  ),
  "utf8",
));

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function vectorError(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maximum: Math.max(...errors.map(Math.abs)),
  };
}

async function waitFrames(page, count = frames) {
  await page.evaluate((count) => new Promise((resolve) => {
    const next = (remaining) => {
      if (remaining === 0) resolve();
      else requestAnimationFrame(() => next(remaining - 1));
    };
    next(count);
  }), count);
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 900, height: 240 } });
  const page = await context.newPage();
  const loadStarted = performance.now();
  await page.goto(
    "http://127.0.0.1:4178/experiments/gpt2-block-css/view-timeline-two-block-with-gpt2-output-head.html",
    { waitUntil: "load", timeout: 240000 },
  );
  await page.evaluate(() => document.fonts.ready);
  await waitFrames(page);

  const readWinner = () => page.locator("#result").evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      winner: Number(style.getPropertyValue("--winner")),
      group: Number(style.getPropertyValue("--group")),
      local: Number(style.getPropertyValue("--local")),
      bucket: Number(style.getPropertyValue("--bucket")),
    };
  });
  const actualHidden = await page.locator("#model").evaluate((element, width) => {
    const style = getComputedStyle(element);
    return Array.from({ length: width }, (_value, index) =>
      Number(style.getPropertyValue(`--h${index}`)));
  }, reference.width);
  const initial = await readWinner();
  const loadMilliseconds = performance.now() - loadStarted;
  const originalInput = await page.locator(".norm1").evaluate((element) => Number(
    getComputedStyle(element).getPropertyValue("--x-000"),
  ));

  const samples = [];
  for (let round = 0; round < rounds + 2; round += 1) {
    const perturbed = round % 2 === 0;
    const started = performance.now();
    let hiddenMilliseconds = 0;
    let blockMilliseconds = 0;
    let headMilliseconds = 0;
    if (staged) {
      await page.locator("#head-run").evaluate((element) => { element.checked = false; });
      await waitFrames(page, 1);
      hiddenMilliseconds = performance.now() - started;
    }
    await page.locator(".norm1").evaluate((element, values) => {
      if (values.perturbed) element.style.setProperty("--x-000", values.input + 0.125);
      else element.style.removeProperty("--x-000");
    }, { perturbed, input: originalInput });
    await waitFrames(page);
    blockMilliseconds = performance.now() - started - hiddenMilliseconds;
    if (staged) {
      const headStarted = performance.now();
      await page.locator("#head-run").evaluate((element) => { element.checked = true; });
      await waitFrames(page, headFrames);
      headMilliseconds = performance.now() - headStarted;
    }
    const output = await readWinner();
    samples.push({
      round,
      perturbed,
      milliseconds: performance.now() - started,
      hiddenMilliseconds,
      blockMilliseconds,
      headMilliseconds,
      output,
      resetCorrect: perturbed ? null : output.winner === reference.quantizedWinner,
    });
  }
  const measured = samples.slice(2);
  const resetSamples = measured.filter(({ perturbed }) => !perturbed);
  const report = {
    chrome: await browser.version(),
    rounds,
    frames,
    headFrames,
    staged,
    loadMilliseconds,
    initial,
    expectedDenseWinner: reference.denseWinner,
    expectedQuantizedWinner: reference.quantizedWinner,
    initialCorrect: initial.winner === reference.quantizedWinner,
    denseCorrect: initial.winner === reference.denseWinner,
    hiddenError: vectorError(actualHidden, reference.finalHidden),
    settledMedianMilliseconds: median(measured.map(({ milliseconds }) => milliseconds)),
    settledMinimumMilliseconds: Math.min(...measured.map(({ milliseconds }) => milliseconds)),
    settledMaximumMilliseconds: Math.max(...measured.map(({ milliseconds }) => milliseconds)),
    resetCorrect: resetSamples.length > 0 &&
      resetSamples.every(({ resetCorrect }) => resetCorrect),
    samples,
  };
  await fs.writeFile(
    new URL(
      "../experiments/gpt2-block-css/view-timeline-two-block-with-gpt2-output-head-browser.json",
      import.meta.url,
    ),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
