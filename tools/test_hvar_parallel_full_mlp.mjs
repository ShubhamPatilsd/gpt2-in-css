import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const directory = process.env.HVAR_FULL_MLP_DIR ?? "hvar-parallel-full-mlp";
const pageFile = process.env.HVAR_FULL_MLP_PAGE ?? "index.html";
const root = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));
const fullBlock = pageFile.includes("full-block");
const capturedState = pageFile.includes("full-block-captured");
const nextLayernorm = pageFile.includes("next-layernorm");
const twoBlock = pageFile.includes("two-block");
const serialProjection = pageFile.includes("serial-projection") ||
  pageFile.includes("fully-serial");
const representedOutputs = twoBlock
  ? reference.block1RepresentedOutputs
  : nextLayernorm
  ? reference.nextLayernormOutputs
  : fullBlock
  ? reference.attentionBlockRepresentedOutputs
  : pageFile.includes("attention")
    ? reference.attentionRepresentedOutputs
    : reference.representedOutputs;
const exactOutputs = twoBlock
  ? reference.block1ExactOutputs
  : nextLayernorm
  ? reference.nextLayernormOutputs
  : fullBlock
  ? reference.attentionBlockExactOutputs
  : pageFile.includes("attention")
    ? reference.attentionExactOutputs
    : reference.exactOutputs;

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
    `http://127.0.0.1:4178/experiments/${directory}/${pageFile}`,
    { waitUntil: "load", timeout: 120000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const loadMilliseconds = performance.now() - loadStarted;
  const samples = [];
  const rounds = Number(process.env.HVAR_FULL_MLP_TEST_ROUNDS ?? 12);
  for (let round = 0; round < rounds; round += 1) {
    const mode = (round + 1) % reference.tokenIds.length;
    const started = performance.now();
    await page.locator(`#case-${mode}`).evaluate((element) => {
      element.checked = true;
    });
    const outputSelector = serialProjection
      ? ".serial-output"
      : twoBlock
      ? ".b1-output"
      : nextLayernorm
      ? ".next-ln-value"
      : capturedState
        ? ".state-value"
        : ".output";
    const widths = await page.locator(outputSelector)
      .evaluateAll((elements) =>
      elements.map((element) => element.getBoundingClientRect().width));
    const milliseconds = performance.now() - started;
    const outputs = widths.map((width) => serialProjection
      ? (width - reference.block1SerialProjectionBase) / reference.block1OutputScale
      : twoBlock
      ? (width - reference.baseAdvance) / reference.block1OutputScale
      : nextLayernorm
      ? (width - reference.nextLayernormOffset) / reference.nextLayernormScale
      : capturedState
        ? (width - reference.stateOffset) / reference.stateScale
        : (width - reference.baseAdvance) / reference.outputScale);
    const represented = representedOutputs[mode];
    const exact = exactOutputs[mode];
    samples.push({
      round,
      mode,
      milliseconds,
      maximumRepresentationError: Math.max(...outputs.map((value, index) =>
        Math.abs(value - represented[index]))),
      outputRmse: Math.sqrt(outputs.reduce((sum, value, index) =>
        sum + (value - exact[index]) ** 2, 0) / outputs.length),
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
    maximumOutputRmse: Math.max(...samples.map(({ outputRmse }) => outputRmse)),
    projectionFontBytes: reference.projectionFontBytes,
    htmlBytes: reference.htmlBytes,
    elements: await page.locator("*").count(),
    correct: samples.every(({ maximumRepresentationError }) =>
      maximumRepresentationError <= 0.3),
    samples,
  };
  const resultFile = pageFile === "index.html"
    ? "browser-results.json"
    : `browser-results-${pageFile.replace(/\.html$/, "")}.json`;
  await fs.writeFile(new URL(resultFile, root), `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
  if (!report.correct) process.exitCode = 1;
  await context.close();
} finally {
  await browser.close();
}
