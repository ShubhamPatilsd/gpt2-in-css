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

const allVariants = [
  {
    name: "one-complete-block",
    pageFile: "connected-attention-full-block.html",
    selector: ".output-767",
    base: reference.baseAdvance,
    scale: reference.outputScale,
    expected: reference.attentionBlockRepresentedOutputs,
  },
  {
    name: "two-complete-blocks-shadow-staged",
    pageFile: "connected-two-block-shadow-staged.html",
    selector: ".b1-output-767",
    base: reference.baseAdvance,
    scale: reference.block1OutputScale,
    expected: reference.block1RepresentedOutputs,
  },
  {
    name: "two-complete-blocks-shadow-staged-layoutless",
    pageFile: "connected-two-block-shadow-staged-layoutless.html",
    selector: ".b1-output-767",
    base: reference.baseAdvance,
    scale: reference.block1OutputScale,
    expected: reference.block1RepresentedOutputs,
  },
  {
    name: "two-complete-blocks-serial-projection",
    pageFile: "connected-two-block-serial-projection.html",
    selector: ".serial-output-767",
    base: reference.block1SerialProjectionBase,
    scale: reference.block1OutputScale,
    expected: reference.block1RepresentedOutputs,
  },
  {
    name: "two-complete-blocks-serial-projection-contents",
    pageFile: "connected-two-block-serial-projection-contents.html",
    selector: ".serial-output-767",
    base: reference.block1SerialProjectionBase,
    scale: reference.block1OutputScale,
    expected: reference.block1RepresentedOutputs,
  },
  {
    name: "two-complete-blocks-serial-projection-layoutless",
    pageFile: "connected-two-block-serial-projection-layoutless.html",
    selector: ".serial-output-767",
    base: reference.block1SerialProjectionBase,
    scale: reference.block1OutputScale,
    expected: reference.block1RepresentedOutputs,
  },
  {
    name: "two-complete-blocks-fully-serial",
    pageFile: "connected-two-block-fully-serial.html",
    selector: ".serial-output-767",
    base: reference.block1SerialProjectionBase,
    scale: reference.block1OutputScale,
    expected: reference.block1RepresentedOutputs,
  },
  {
    name: "two-complete-blocks-fully-serial-contents",
    pageFile: "connected-two-block-fully-serial-contents.html",
    selector: ".serial-output-767",
    base: reference.block1SerialProjectionBase,
    scale: reference.block1OutputScale,
    expected: reference.block1RepresentedOutputs,
  },
  {
    name: "two-complete-blocks-fully-serial-layoutless",
    pageFile: "connected-two-block-fully-serial-layoutless.html",
    selector: ".serial-output-767",
    base: reference.block1SerialProjectionBase,
    scale: reference.block1OutputScale,
    expected: reference.block1RepresentedOutputs,
  },
];
const requestedVariants = process.env.HVAR_BLOCK_SCALING_VARIANTS
  ?.split(",").filter(Boolean);
const variants = requestedVariants
  ? allVariants.filter(({ name }) => requestedVariants.includes(name))
  : allVariants;

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

  const rounds = Number(process.env.HVAR_BLOCK_SCALING_ROUNDS ?? 12);
  for (let round = 0; round < rounds; round += 1) {
    const ordered = variants.map((_, offset) =>
      variants[(round + offset) % variants.length]);
    for (const variant of ordered) {
      const mode = (round + 1) % reference.tokenIds.length;
      const sample = await variant.page.evaluate(({ caseId, selector }) => {
        const started = performance.now();
        document.querySelector(`#case-${caseId}`).checked = true;
        const width = document.querySelector(selector)?.getBoundingClientRect().width
          ?? [...document.querySelectorAll("css-stage")]
            .map((host) => host.shadowRoot?.querySelector(selector))
            .find(Boolean)?.getBoundingClientRect().width;
        return { milliseconds: performance.now() - started, width };
      }, { caseId: mode, selector: variant.selector });
      const output = (sample.width - variant.base) / variant.scale;
      variant.samples.push({
        round,
        mode,
        ...sample,
        output,
        error: Math.abs(output - variant.expected[mode][767]),
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
    new URL(`../experiments/${directory}/block-scaling-comparison.json`, import.meta.url),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
