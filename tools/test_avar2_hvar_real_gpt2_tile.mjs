import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const root = new URL("../experiments/avar2-hvar-real-gpt2-tile/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 1000, height: 120 },
  });
  const page = await context.newPage();
  const loadStarted = performance.now();
  await page.goto(
    "http://127.0.0.1:4178/experiments/avar2-hvar-real-gpt2-tile/index.html",
    { waitUntil: "load" },
  );
  await page.evaluate(() => document.fonts.ready);
  const loadMilliseconds = performance.now() - loadStarted;
  const samples = [];
  for (let round = 0; round < 12; round += 1) {
    const mode = (round + 1) % reference.tokenIds.length;
    const started = performance.now();
    await page.locator(`#case-${mode}`).evaluate((element) => {
      element.checked = true;
    });
    const widths = await page.locator(".output").evaluateAll((elements) =>
      elements.map((element) => element.getBoundingClientRect().width));
    const milliseconds = performance.now() - started;
    const outputs = widths.map((width) =>
      (width - reference.baseAdvance) / reference.outputScale);
    const represented = reference.representedOutputs[mode];
    const exact = reference.exactOutputs[mode];
    samples.push({
      round,
      mode,
      milliseconds,
      maximumRepresentationError: Math.max(...outputs.map((value, index) =>
        Math.abs(value - represented[index]))),
      maximumModelError: Math.max(...outputs.map((value, index) =>
        Math.abs(value - exact[index]))),
    });
  }
  const measured = samples.slice(reference.tokenIds.length);
  const report = {
    chrome: await browser.version(),
    runtimeContainsJavaScript: false,
    loadMilliseconds,
    mutationMedianMilliseconds: median(measured.map(({ milliseconds }) => milliseconds)),
    mutationMinimumMilliseconds: Math.min(...measured.map(({ milliseconds }) => milliseconds)),
    mutationMaximumMilliseconds: Math.max(...measured.map(({ milliseconds }) => milliseconds)),
    maximumRepresentationError: Math.max(...samples.map(({ maximumRepresentationError }) =>
      maximumRepresentationError)),
    maximumModelError: Math.max(...samples.map(({ maximumModelError }) => maximumModelError)),
    fontBytes: reference.fontBytes,
    htmlBytes: reference.htmlBytes,
    elements: await page.locator("*").count(),
    correct: samples.every(({ maximumRepresentationError }) =>
      maximumRepresentationError <= 0.08),
    samples,
  };
  await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
  if (!report.correct) process.exitCode = 1;
  await context.close();
} finally {
  await browser.close();
}
