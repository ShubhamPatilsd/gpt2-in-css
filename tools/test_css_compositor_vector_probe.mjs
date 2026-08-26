import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.COMPOSITOR_VECTOR_ROUNDS ?? "7", 10);

const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/css-compositor-vector/reference.json", import.meta.url),
  "utf8",
));

async function redPixel(locator) {
  const screenshot = await locator.screenshot({ animations: "disabled", timeout: 180000 });
  const { data, info } = await sharp(screenshot).raw().toBuffer({ resolveWithObject: true });
  const x = Math.floor(info.width / 2);
  const y = Math.floor(info.height / 2);
  return data[(y * info.width + x) * info.channels];
}

const browser = await chromium.launch({ executablePath, headless: true });
const results = [];
try {
  for (const count of reference.counts) {
    const page = await browser.newPage({ viewport: { width: 160, height: 100 } });
    const started = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/css-compositor-vector/n${count}.html`,
      { waitUntil: "load", timeout: 180000 },
    );
    const locator = page.locator("#case");
    const initialRed = await redPixel(locator);
    const loadAndFirstPaintMilliseconds = performance.now() - started;
    const samples = [];
    for (let round = 0; round < rounds; round += 1) {
      const gain = round % 2 === 0 ? 0.8 : 1;
      const expected = gain === 1
        ? reference.expectedRedAtGain1
        : reference.expectedRedAtGain08;
      const mutationStarted = performance.now();
      await page.locator("html").evaluate((element, value) => {
        element.style.setProperty("--gain", String(value));
      }, gain);
      const red = await redPixel(locator);
      samples.push({
        gain,
        red,
        expected,
        error: red - expected,
        milliseconds: performance.now() - mutationStarted,
      });
    }
    const timings = samples.map(({ milliseconds }) => milliseconds).sort((a, b) => a - b);
    results.push({
      count,
      initialRed,
      expectedInitialRed: reference.expectedRedAtGain1,
      loadAndFirstPaintMilliseconds,
      mutationMedianMilliseconds: timings[Math.floor(timings.length / 2)],
      mutationMaximumMilliseconds: timings.at(-1),
      samples,
      elements: await page.locator("*").count(),
    });
    await page.close();
  }
} finally {
  await browser.close();
}

const report = { chrome: await (async () => "system")(), rounds, results };
await fs.writeFile(
  new URL("../experiments/css-compositor-vector/browser-results.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
