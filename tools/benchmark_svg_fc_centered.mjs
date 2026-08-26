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
const rounds = Number.parseInt(process.env.SVG_FC_BENCH_ROUNDS ?? "10", 10);
const stage = process.env.SVG_FC_BENCH_STAGE ?? "fc";
if (!new Set(["fc", "full"]).has(stage)) {
  throw new Error("SVG_FC_BENCH_STAGE must be fc or full");
}
const variants = process.env.SVG_FC_BENCH_VARIANTS
  ? process.env.SVG_FC_BENCH_VARIANTS.split(",").map((entry) => {
    const separator = entry.indexOf(":");
    if (separator < 1 || separator === entry.length - 1) {
      throw new Error("SVG_FC_BENCH_VARIANTS entries must be name:directory");
    }
    return {
      name: entry.slice(0, separator),
      directory: entry.slice(separator + 1),
    };
  })
  : [
    { name: "split-sign", directory: "svg-filter-gpt2-fc-split" },
    { name: "centered-dot", directory: "svg-filter-gpt2-fc-centered" },
  ];
if (process.env.SVG_FC_BENCH_ORDER === "centered-first") variants.reverse();

function stats(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return {
    minimum: sorted[0],
    median: sorted[Math.floor(sorted.length / 2)],
    mean: values.reduce((sum, value) => sum + value, 0) / values.length,
    maximum: sorted.at(-1),
  };
}

const result = { rounds, stage, variants: {} };
for (const variant of variants) {
  const referencePath = new URL(
    `../experiments/${variant.directory}/${stage === "full" ? "full-reference" : "reference"}.json`,
    import.meta.url,
  );
  const reference = JSON.parse(await fs.readFile(referencePath, "utf8"));
  const browser = await chromium.launch({ executablePath, headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 16, height: 3072 } });
    await page.goto(
      `http://127.0.0.1:4178/experiments/${variant.directory}/${stage === "full" ? "full" : "index"}.html`,
      { waitUntil: "load", timeout: 180000 },
    );
    await page.locator("svg").evaluate((svg, payload) => {
      if (payload.stage === "full") {
        svg.setAttribute("width", "768");
        svg.setAttribute("height", "1");
        svg.setAttribute("viewBox", `0 ${payload.readRow} 768 1`);
        svg.style.width = "768px";
        svg.style.height = "1px";
      } else {
        svg.setAttribute("width", "1");
        svg.setAttribute("height", "3072");
        svg.setAttribute("viewBox", `${payload.readColumn} 0 1 3072`);
        svg.style.width = "1px";
        svg.style.height = "3072px";
      }
    }, { stage, readColumn: reference.read_column, readRow: reference.read_row });
    await page.locator("svg").screenshot({ timeout: 180000 });
    const input = page.locator("feImage").first();
    const baseHref = (await input.getAttribute("href")).split("?")[0];
    const samples = [];
    for (let round = 0; round < rounds; round += 1) {
      const started = performance.now();
      await input.evaluate((image, payload) => {
        image.setAttribute("href", `${payload.baseHref}?recompute=${payload.round}`);
      }, { baseHref, round });
      const png = await page.locator("svg").screenshot({ timeout: 180000 });
      const milliseconds = performance.now() - started;
      const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
      const actual = stage === "full"
        ? reference.expected.map((_, column) =>
          (data[column * info.channels] / 255 - reference.surface_center)
            * 2 * reference.projection_divisor * reference.projection_units[column])
        : reference.expected.map((_, row) =>
          (data[row * info.channels] / 255 - reference.surface_center)
            * 2 * reference.divisor * reference.units[row]);
      const errors = actual.map((value, row) => value - reference.expected[row]);
      samples.push({
        milliseconds,
        rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0)
          / errors.length),
        maxError: Math.max(...errors.map(Math.abs)),
      });
    }
    const html = await fs.readFile(new URL(
      `../experiments/${variant.directory}/${stage === "full" ? "full" : "index"}.html`,
      import.meta.url,
    ), "utf8");
    result.variants[variant.name] = {
      timing: stats(samples.map((sample) => sample.milliseconds)),
      rmse: stats(samples.map((sample) => sample.rmse)),
      maxError: Math.max(...samples.map((sample) => sample.maxError)),
      htmlBytes: Buffer.byteLength(html),
      primitiveCount: [...html.matchAll(/<fe[A-Za-z]+/g)].length,
      samples,
    };
  } finally {
    await browser.close();
  }
}
if (result.variants["split-sign"] && result.variants["centered-dot"]) {
  result.centeredSpeedup =
    result.variants["split-sign"].timing.median
    / result.variants["centered-dot"].timing.median;
}
console.log(JSON.stringify(result, null, 2));
