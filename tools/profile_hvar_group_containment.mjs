import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const origin = process.env.HVAR_ORIGIN ?? "http://127.0.0.1:4178";
const fixture = process.env.HVAR_CONTAINMENT_FIXTURE ??
  "avar2-gelu-linear-hvar-full-mlp-g13/connected-attention-numeric-input.html";

const allVariants = [
  { name: "control", css: "" },
  { name: "group-layout", css: ".group{contain:layout}" },
  { name: "group-style", css: ".group{contain:style}" },
  { name: "group-layout-style", css: ".group{contain:layout style}" },
  { name: "group-size-layout-style", css: ".group{contain:size layout style}" },
  { name: "projection-layout", css: ".projection{contain:layout}" },
  { name: "projection-style", css: ".projection{contain:style}" },
  { name: "projection-layout-style", css: ".projection{contain:layout style}" },
];
const requestedVariants = process.env.HVAR_CONTAINMENT_VARIANTS?.split(",").filter(Boolean);
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
  const rounds = Number(process.env.HVAR_CONTAINMENT_ROUNDS ?? 12);
  let referenceWidths;
  for (const variant of variants) {
    const page = await context.newPage();
    const started = performance.now();
    await page.goto(`${origin}/experiments/${fixture}`, {
      waitUntil: "load",
      timeout: 120000,
    });
    await page.evaluate(() => document.fonts.ready);
    if (variant.css) {
      await page.addStyleTag({ content: variant.css });
    }
    variant.loadMilliseconds = performance.now() - started;
    variant.samples = [];
    variant.widths = [];
    for (let mode = 0; mode < 4; mode += 1) {
      variant.widths.push(await page.evaluate((caseId) => {
        document.querySelector(`#case-${caseId}`).checked = true;
        return document.querySelector(".output-767").getBoundingClientRect().width;
      }, mode));
    }
    referenceWidths ??= variant.widths;
    for (let round = 0; round < rounds; round += 1) {
      const sample = await page.evaluate((caseId) => {
        const started = performance.now();
        document.querySelector(`#case-${caseId}`).checked = true;
        const width = document.querySelector(".output-767").getBoundingClientRect().width;
        return { milliseconds: performance.now() - started, width };
      }, (round + 1) % 4);
      variant.samples.push({ round, ...sample });
    }
    await page.close();
    console.error(`finished ${variant.name}`);
  }

  const report = {
    chrome: await browser.version(),
    fixture,
    runtimeContainsJavaScript: false,
    rounds,
    variants: variants.map(({ name, css, loadMilliseconds, widths, samples }) => {
      const measured = samples.slice(4).map(({ milliseconds }) => milliseconds);
      const maximumWidthError = Math.max(...widths.map(
        (width, index) => Math.abs(width - referenceWidths[index]),
      ));
      return {
        name,
        css,
        loadMilliseconds,
        widths,
        maximumWidthError,
        correct: maximumWidthError < 0.02,
        minimumMilliseconds: Math.min(...measured),
        medianMilliseconds: percentile(measured, 0.5),
        p90Milliseconds: percentile(measured, 0.9),
        maximumMilliseconds: Math.max(...measured),
        samples,
      };
    }),
  };
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
