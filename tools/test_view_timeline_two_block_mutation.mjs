import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(
  process.env.VIEW_TIMELINE_TWO_BLOCK_MUTATION_ROUNDS ??
    process.env.TWO_BLOCK_MUTATION_ROUNDS ?? "7",
  10,
);
const frames = Number.parseInt(process.env.VIEW_TIMELINE_TWO_BLOCK_FRAMES ?? "4", 10);
const file = process.env.VIEW_TIMELINE_TWO_BLOCK_FILE ??
  process.env.TWO_BLOCK_MUTATION_FILE ??
  "view-timeline-two-block-full-packed4.html";
const referenceFile = process.env.VIEW_TIMELINE_TWO_BLOCK_REFERENCE ??
  "view-timeline-two-block-full-reference.json";

const reference = JSON.parse(await fs.readFile(
  new URL(
    `../experiments/gpt2-block-css/${referenceFile}`,
    import.meta.url,
  ),
  "utf8",
));
const expected = reference.expected ?? reference.expected_packed;

async function waitFrames(page) {
  await page.evaluate((count) => new Promise((resolve) => {
    const next = (remaining) => {
      if (remaining === 0) resolve();
      else requestAnimationFrame(() => next(remaining - 1));
    };
    next(count);
  }), frames);
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function error(actual, expected) {
  const delta = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(delta.reduce((sum, value) => sum + value * value, 0) / delta.length),
    maximum: Math.max(...delta.map(Math.abs)),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 900, height: 240 } });
  const page = await context.newPage();
  const loadStarted = performance.now();
  await page.goto(
    `http://127.0.0.1:4178/experiments/gpt2-block-css/${file}`,
    { waitUntil: "load", timeout: 180000 },
  );
  await page.evaluate(() => document.fonts.ready);
  await waitFrames(page);

  const originalInput = await page.locator(".norm1").evaluate((element) => Number(
    getComputedStyle(element).getPropertyValue("--x-000"),
  ));
  const read = () => page.locator("#two-block-full").evaluate((element, width) => {
    const style = getComputedStyle(element);
    return Array.from({ length: width }, (_value, index) => Number(
      style.getPropertyValue(`--b1-final-${String(index).padStart(3, "0")}`),
    ));
  }, reference.width);
  const initial = await read();
  const loadMilliseconds = performance.now() - loadStarted;
  const samples = [];
  for (let round = 0; round < rounds + 2; round += 1) {
    const perturbed = round % 2 === 0;
    const started = performance.now();
    await page.locator(".norm1").evaluate(
      (element, { value, remove }) => {
        if (remove) element.style.removeProperty("--x-000");
        else element.style.setProperty("--x-000", value);
      },
      { value: originalInput + 0.125, remove: !perturbed },
    );
    await waitFrames(page);
    const actual = await read();
    samples.push({
      round,
      perturbed,
      milliseconds: performance.now() - started,
      checksum: actual.reduce((sum, value) => sum + value, 0),
      resetError: perturbed ? null : error(actual, expected),
    });
  }
  const measured = samples.slice(2);
  const report = {
    chrome: await browser.version(),
    file,
    rounds,
    frames,
    originalInput,
    loadMilliseconds,
    initialError: error(initial, expected),
    settledMedianMilliseconds: median(measured.map(({ milliseconds }) => milliseconds)),
    settledMinimumMilliseconds: Math.min(...measured.map(({ milliseconds }) => milliseconds)),
    settledMaximumMilliseconds: Math.max(...measured.map(({ milliseconds }) => milliseconds)),
    resetRmseMaximum: Math.max(
      ...measured.filter(({ resetError }) => resetError).map(({ resetError }) => resetError.rmse),
    ),
    samples,
  };
  const outputFile = process.env.VIEW_TIMELINE_TWO_BLOCK_RESULT ??
    "view-timeline-two-block-mutation-browser.json";
  await fs.writeFile(
    new URL(
      `../experiments/gpt2-block-css/${outputFile}`,
      import.meta.url,
    ),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
