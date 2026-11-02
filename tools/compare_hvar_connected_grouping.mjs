import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const origin = process.env.HVAR_ORIGIN ?? "http://127.0.0.1:4178";

const groupingVariants = [
  {
    name: "12x256-direct-input",
    path: "avar2-gelu-linear-hvar-full-mlp/index.html",
  },
  {
    name: "12x256-three-shard-connector",
    path: "avar2-gelu-linear-hvar-full-mlp/connected-sharded-input.html",
  },
  {
    name: "13x236-238-deep-connector",
    path: "avar2-gelu-linear-hvar-full-mlp-g13/connected-input.html",
  },
  {
    name: "16x192-deep-connector",
    path: "avar2-gelu-linear-hvar-full-mlp-g16/connected-input.html",
  },
];
const layernormVariants = [
  {
    name: "13x236-238-direct-n2",
    path: "avar2-gelu-linear-hvar-full-mlp-g13/connected-input.html",
  },
  {
    name: "13x236-238-live-layernorm-n2",
    path: "avar2-gelu-linear-hvar-full-mlp-g13/connected-layernorm-input.html",
  },
  {
    name: "13x236-238-live-attention-layernorm-n2",
    path: "avar2-gelu-linear-hvar-full-mlp-g13/connected-attention-input.html",
  },
];
const numericVariants = [
  {
    name: "13x236-238-attention-geometry-roundtrip",
    path: "avar2-gelu-linear-hvar-full-mlp-g13/connected-attention-input.html",
  },
  {
    name: "13x236-238-attention-direct-numeric",
    path: "avar2-gelu-linear-hvar-full-mlp-g13/connected-attention-numeric-input.html",
  },
  {
    name: "12x256-attention-direct-numeric",
    path: "avar2-gelu-linear-hvar-full-mlp/connected-attention-numeric-input.html",
  },
  {
    name: "16x192-attention-direct-numeric",
    path: "avar2-gelu-linear-hvar-full-mlp-g16/connected-attention-numeric-input.html",
  },
];
const variants = process.env.HVAR_COMPARE_SET === "layernorm"
  ? layernormVariants
  : process.env.HVAR_COMPARE_SET === "numeric"
    ? numericVariants
    : groupingVariants;

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
      `${origin}/experiments/${variant.path}`,
      { waitUntil: "load", timeout: 120000 },
    );
    await variant.page.evaluate(() => document.fonts.ready);
    variant.loadMilliseconds = performance.now() - started;
    variant.samples = [];
  }

  const rounds = Number(process.env.HVAR_COMPARE_ROUNDS ?? 20);
  for (let round = 0; round < rounds; round += 1) {
    const ordered = variants.map((_, offset) =>
      variants[(round + offset) % variants.length]);
    for (const variant of ordered) {
      const sample = await variant.page.evaluate((mode) => {
        const started = performance.now();
        document.querySelector(`#case-${mode}`).checked = true;
        const width = document.querySelector(".output-767").getBoundingClientRect().width;
        return { milliseconds: performance.now() - started, width };
      }, (round + 1) % 4);
      variant.samples.push({ round, ...sample });
    }
    console.error(`round ${round + 1}/${rounds}`);
  }

  const report = {
    chrome: await browser.version(),
    runtimeContainsJavaScript: false,
    rounds,
    variants: variants.map(({ name, path, loadMilliseconds, samples }) => {
      const measured = samples.slice(4).map(({ milliseconds }) => milliseconds);
      return {
        name,
        path,
        loadMilliseconds,
        minimumMilliseconds: Math.min(...measured),
        p25Milliseconds: percentile(measured, 0.25),
        medianMilliseconds: percentile(measured, 0.5),
        p75Milliseconds: percentile(measured, 0.75),
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
