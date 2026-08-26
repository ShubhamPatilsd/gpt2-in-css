import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const origin = process.env.HVAR_ORIGIN ?? "http://127.0.0.1:4178";
const directory = "avar2-gelu-linear-hvar-full-mlp-g13";
const reference = JSON.parse(await fs.readFile(
  new URL(`../experiments/${directory}/reference.json`, import.meta.url),
  "utf8",
));

const variants = [
  {
    name: "complete-block-width",
    pageFile: "connected-attention-full-block.html",
    selector: ".output-767",
    decode: (width) => (width - reference.baseAdvance) / reference.outputScale,
    expected: (mode) => reference.attentionBlockRepresentedOutputs[mode][767],
  },
  {
    name: "complete-block-768-state-capture",
    pageFile: "connected-attention-full-block-captured.html",
    selector: ".state-value-767",
    decode: (width) => (width - reference.stateOffset) / reference.stateScale,
    expected: (mode) => reference.attentionBlockRepresentedOutputs[mode][767],
  },
  {
    name: "captured-state-plus-block1-layernorm",
    pageFile: "connected-attention-full-block-next-layernorm.html",
    selector: ".next-ln-value-767",
    decode: (width) => (
      width - reference.nextLayernormOffset
    ) / reference.nextLayernormScale,
    expected: (mode) => reference.nextLayernormOutputs[mode][767],
  },
];

function percentile(values, fraction) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor((sorted.length - 1) * fraction)];
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 1000, height: 120 },
  });
  for (const variant of variants) {
    variant.page = await context.newPage();
    const started = performance.now();
    await variant.page.goto(
      `${origin}/experiments/${directory}/${variant.pageFile}`,
      { waitUntil: "load", timeout: 120000 },
    );
    await variant.page.evaluate(() => document.fonts.ready);
    variant.loadMilliseconds = performance.now() - started;
    variant.samples = [];
  }

  const rounds = Number(process.env.HVAR_BLOCK_CAPTURE_ROUNDS ?? 16);
  for (let round = 0; round < rounds; round += 1) {
    const ordered = variants.map((_, offset) =>
      variants[(round + offset) % variants.length]);
    for (const variant of ordered) {
      const mode = (round + 1) % reference.tokenIds.length;
      const sample = await variant.page.evaluate(({ caseId, selector }) => {
        const started = performance.now();
        document.querySelector(`#case-${caseId}`).checked = true;
        const width = document.querySelector(selector).getBoundingClientRect().width;
        return { milliseconds: performance.now() - started, width };
      }, { caseId: mode, selector: variant.selector });
      const output = variant.decode(sample.width);
      variant.samples.push({
        round,
        mode,
        ...sample,
        output,
        error: Math.abs(output - variant.expected(mode)),
      });
    }
    console.error(`round ${round + 1}/${rounds}`);
  }

  const report = {
    chrome: await browser.version(),
    runtimeContainsJavaScript: false,
    rounds,
    variants: variants.map(({ name, pageFile, loadMilliseconds, samples }) => {
      const measured = samples.slice(4).map(({ milliseconds }) => milliseconds);
      return {
        name,
        pageFile,
        loadMilliseconds,
        minimumMilliseconds: Math.min(...measured),
        medianMilliseconds: percentile(measured, 0.5),
        p90Milliseconds: percentile(measured, 0.9),
        maximumMilliseconds: Math.max(...measured),
        maximumError: Math.max(...samples.map(({ error }) => error)),
        samples,
      };
    }),
  };
  await fs.writeFile(
    new URL(`../experiments/${directory}/block-capture-comparison.json`, import.meta.url),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
