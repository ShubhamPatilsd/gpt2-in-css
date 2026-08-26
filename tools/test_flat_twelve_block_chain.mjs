import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number(process.env.FLAT_12BLOCK_ROUNDS ?? 3);
const maximumFrames = Number(process.env.FLAT_12BLOCK_MAX_FRAMES ?? 48);
const baseUrl = process.env.FLAT_12BLOCK_URL ??
  "http://127.0.0.1:4178/experiments/gpt2-flat-12block-chain/index.html";
const experiment = new URL("../experiments/gpt2-flat-12block-chain/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", experiment), "utf8"));

function error(actual, expected) {
  const delta = actual.map((value, index) => value - expected[index]);
  return {
    finite: actual.filter(Number.isFinite).length,
    rmse: Math.sqrt(delta.reduce((sum, value) => sum + value * value, 0) / delta.length),
    maximum: Math.max(...delta.map(Math.abs)),
  };
}

function median(values) {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.floor(sorted.length / 2)];
}

async function readFinal(page) {
  return page.locator("#block11-full").evaluate((element) => {
    const style = getComputedStyle(element);
    return Array.from({ length: 768 }, (_, index) => Number(
      style.getPropertyValue(`--b11-final-${String(index).padStart(3, "0")}`),
    ));
  });
}

async function waitUntilStable(page) {
  let previous = null;
  let stableFrames = 0;
  let actual = null;
  for (let frame = 1; frame <= maximumFrames; frame += 1) {
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));
    actual = await readFinal(page);
    const signature = actual.map((value) => value.toFixed(7)).join(",");
    if (signature === previous) stableFrames += 1;
    else stableFrames = 0;
    previous = signature;
    if (stableFrames >= 2) return { actual, frames: frame, settled: true };
  }
  return { actual, frames: maximumFrames, settled: false };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 300 } });
  const coldStarted = performance.now();
  await page.goto(`${baseUrl}?cold=${Date.now()}`, {
    waitUntil: "load",
    timeout: 300000,
  });
  await page.evaluate(() => document.fonts.ready);
  const coldSettled = await waitUntilStable(page);
  const coldMilliseconds = performance.now() - coldStarted;
  const initialError = error(coldSettled.actual, reference.baselineTrace.at(-1));

  const samples = [];
  for (let round = 0; round < rounds + 2; round += 1) {
    const alternate = round % 2 === 0;
    const started = performance.now();
    await page.locator(".norm1").evaluate((element, { useAlternate, value }) => {
      if (useAlternate) element.style.setProperty("--x-000", value);
      else element.style.removeProperty("--x-000");
    }, { useAlternate: alternate, value: reference.alternateInput[0] });
    const settled = await waitUntilStable(page);
    const milliseconds = performance.now() - started;
    samples.push({
      round,
      alternate,
      milliseconds,
      frames: settled.frames,
      settled: settled.settled,
      error: error(
        settled.actual,
        (alternate ? reference.alternateTrace : reference.baselineTrace).at(-1),
      ),
    });
    console.error(
      `r${round} ${alternate ? "alternate" : "baseline"}: ` +
      `${milliseconds.toFixed(1)}ms, frames=${settled.frames}, ` +
      `rmse=${samples.at(-1).error.rmse.toFixed(6)}`,
    );
  }
  const measured = samples.slice(2);
  const report = {
    chrome: await browser.version(),
    context: reference.context,
    blocks: reference.blocks,
    runtimeJavaScript: false,
    harnessStages: false,
    coldMilliseconds,
    coldFrames: coldSettled.frames,
    coldSettled: coldSettled.settled,
    initialError,
    warmMedianMilliseconds: median(measured.map(({ milliseconds }) => milliseconds)),
    warmMinimumMilliseconds: Math.min(...measured.map(({ milliseconds }) => milliseconds)),
    warmMaximumMilliseconds: Math.max(...measured.map(({ milliseconds }) => milliseconds)),
    samples,
  };
  await fs.writeFile(new URL("browser-results.json", experiment), `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
