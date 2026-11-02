import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.SVG_QKV_BENCH_ROUNDS ?? "5", 10);
const rootUrl = process.env.SVG_QKV_BENCH_ROOT ?? "http://127.0.0.1:4178";
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/svg-multitoken-attention/reference.json", import.meta.url,
), "utf8"));

const layoutVariants = [
  {
    name: "head-local",
    path: "experiments/svg-multitoken-attention",
  },
  ...[2, 3, 4, 6].map((heads) => ({
    name: `group-${heads}`,
    path: `experiments/svg-multitoken-attention-group${heads}`,
  })),
  {
    name: "part-contiguous",
    path: "experiments/svg-multitoken-attention-partized",
  },
  {
    name: "vector-born",
    path: "experiments/svg-multitoken-attention-vectorized",
  },
];
const shardVariants = [128, 192, 256, 384].map((shard) => ({
  name: `shard-${shard}`,
  path: shard === 256
    ? "experiments/svg-multitoken-attention"
    : `experiments/svg-multitoken-attention-shard${shard}`,
}));
const benchmarkSet = process.env.SVG_QKV_BENCH_SET ?? "layouts";
const rgbVariants = [
  { name: "head-local", path: "experiments/svg-multitoken-attention" },
  { name: "rgb-packed", path: "experiments/svg-multitoken-attention-rgb" },
  {
    name: "rgb-staged",
    path: "experiments/svg-multitoken-attention-rgb",
    connectedFile: "connected-qkv-staged.html",
  },
];
const rgbTileVariants = [
  { name: "head-local", path: "experiments/svg-multitoken-attention" },
  {
    name: "rgb-staged-tile",
    path: "experiments/svg-multitoken-attention-rgb-tile",
    connectedFile: "connected-qkv-staged.html",
  },
];
const rgbBatchVariants = [
  {
    name: "rgb-token-separate",
    path: "experiments/svg-multitoken-attention-rgb-tile",
    connectedFile: "connected-qkv-staged.html",
  },
  {
    name: "rgb-token-batched",
    path: "experiments/svg-multitoken-attention-rgb-token-batch",
    connectedFile: "connected-qkv-staged.html",
  },
];
const rgbCenteredVariants = [
  {
    name: "rgb-split-sign",
    path: "experiments/svg-multitoken-attention-rgb-tile",
    connectedFile: "connected-qkv-staged.html",
  },
  {
    name: "rgb-centered-dot",
    path: "experiments/svg-multitoken-attention-rgb-centered",
    connectedFile: "connected-qkv-staged.html",
  },
];
const variants = benchmarkSet === "shards"
  ? shardVariants
  : benchmarkSet === "rgb"
    ? rgbVariants
    : benchmarkSet === "rgbtile"
      ? rgbTileVariants
      : benchmarkSet === "rgbbatch"
        ? rgbBatchVariants
        : benchmarkSet === "rgbcentered"
          ? rgbCenteredVariants
    : layoutVariants;

function summarize(actual, expected) {
  const errors = actual.flatMap((row, token) =>
    row.map((value, index) => value - expected[token][index]));
  return {
    maxError: Math.max(...errors.map(Math.abs)),
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0)
      / errors.length),
  };
}

function stats(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return {
    minimum: sorted[0],
    median: sorted[Math.floor(sorted.length / 2)],
    mean: values.reduce((sum, value) => sum + value, 0) / values.length,
    maximum: sorted.at(-1),
  };
}

async function screenshotSvg(page, variant, file) {
  const started = performance.now();
  await page.goto(`${rootUrl}/${variant.path}/${file}?run=${performance.now()}`, {
    waitUntil: "load",
    timeout: 180000,
  });
  const png = await page.locator("svg").screenshot({
    animations: "disabled",
    timeout: 180000,
  });
  return { png, milliseconds: performance.now() - started };
}

async function connectedResult(page, variant) {
  const { png, milliseconds } = await screenshotSvg(
    page,
    variant,
    variant.connectedFile ?? "connected-qkv.html",
  );
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const actual = Array.from({ length: 2 }, (_, token) =>
    Array.from({ length: reference.width }, (_, index) =>
      (data[(token * info.width + index) * info.channels] / 255
      - reference.surface_center) * 2 * reference.value_scales[index]));
  const probabilities = Array.from({ length: reference.heads }, (_, head) =>
    data[(2 * info.width + head) * info.channels] / 255);
  return {
    milliseconds,
    ...summarize(actual, reference.expected_context),
    probabilityMaxError: Math.max(...probabilities.map((value, head) =>
      Math.abs(value - reference.expected_probabilities[head]))),
  };
}

async function qkvResult(page, variant) {
  const { png, milliseconds } = await screenshotSvg(page, variant, "qkv-debug.html");
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const actual = Array.from({ length: 2 }, (_, token) => {
    const values = [];
    for (let part = 0; part < 3; part += 1) {
      for (let head = 0; head < reference.heads; head += 1) {
        const row = token * 36 + part * reference.heads + head;
        for (let offset = 0; offset < 64; offset += 1) {
          const index = part * reference.width + head * 64 + offset;
          values[index] = (data[(row * info.width + offset) * info.channels] / 255
            - reference.surface_center) * 2 * reference.qkv_scales[index];
        }
      }
    }
    return values;
  });
  return { milliseconds, ...summarize(actual, reference.expected_qkv) };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const pages = new Map();
  for (const variant of variants) {
    pages.set(variant.name, await browser.newPage({ viewport: { width: 800, height: 100 } }));
    await connectedResult(pages.get(variant.name), variant);
    await qkvResult(pages.get(variant.name), variant);
  }

  const samples = Object.fromEntries(variants.map((variant) => [variant.name, {
    connected: [],
    qkv: [],
  }]));
  for (let round = 0; round < rounds; round += 1) {
    const ordered = round % 2 === 0 ? variants : [...variants].reverse();
    for (const variant of ordered) {
      const page = pages.get(variant.name);
      samples[variant.name].connected.push(await connectedResult(page, variant));
      samples[variant.name].qkv.push(await qkvResult(page, variant));
    }
  }

  const result = { rounds, variants: {} };
  for (const variant of variants) {
    const variantSamples = samples[variant.name];
    result.variants[variant.name] = {
      connectedHtmlBytes: (await fs.stat(new URL(
        `../${variant.path}/${variant.connectedFile ?? "connected-qkv.html"}`,
        import.meta.url,
      ))).size,
      qkvHtmlBytes: (await fs.stat(new URL(
        `../${variant.path}/qkv-debug.html`, import.meta.url,
      ))).size,
      connected: {
        timing: stats(variantSamples.connected.map((sample) => sample.milliseconds)),
        rmse: stats(variantSamples.connected.map((sample) => sample.rmse)),
        maxError: Math.max(...variantSamples.connected.map((sample) => sample.maxError)),
        probabilityMaxError: Math.max(...variantSamples.connected.map(
          (sample) => sample.probabilityMaxError)),
      },
      qkv: {
        timing: stats(variantSamples.qkv.map((sample) => sample.milliseconds)),
        rmse: stats(variantSamples.qkv.map((sample) => sample.rmse)),
        maxError: Math.max(...variantSamples.qkv.map((sample) => sample.maxError)),
      },
    };
  }
  if (benchmarkSet === "rgbcentered") {
    const baseline = result.variants["rgb-split-sign"];
    const candidate = result.variants["rgb-centered-dot"];
    result.rgbCenteredDotRelativeToSplitSign = {
      connectedSpeedup:
        baseline.connected.timing.median / candidate.connected.timing.median,
      qkvSpeedup: baseline.qkv.timing.median / candidate.qkv.timing.median,
      connectedHtmlReduction:
        baseline.connectedHtmlBytes / candidate.connectedHtmlBytes,
      qkvHtmlReduction: baseline.qkvHtmlBytes / candidate.qkvHtmlBytes,
    };
  } else if (benchmarkSet === "rgbbatch") {
    const baseline = result.variants["rgb-token-separate"];
    const candidate = result.variants["rgb-token-batched"];
    result.rgbTokenBatchRelativeToSeparate = {
      connectedSpeedup:
        baseline.connected.timing.median / candidate.connected.timing.median,
      qkvSpeedup: baseline.qkv.timing.median / candidate.qkv.timing.median,
      connectedHtmlReduction:
        baseline.connectedHtmlBytes / candidate.connectedHtmlBytes,
      qkvHtmlReduction: baseline.qkvHtmlBytes / candidate.qkvHtmlBytes,
    };
  } else if (benchmarkSet === "rgbtile") {
    const baseline = result.variants["head-local"];
    const candidate = result.variants["rgb-staged-tile"];
    result.rgbStagedTileRelativeToHeadLocal = {
      connectedSpeedup:
        baseline.connected.timing.median / candidate.connected.timing.median,
      qkvSpeedup: baseline.qkv.timing.median / candidate.qkv.timing.median,
      connectedHtmlReduction:
        baseline.connectedHtmlBytes / candidate.connectedHtmlBytes,
      qkvHtmlReduction: baseline.qkvHtmlBytes / candidate.qkvHtmlBytes,
    };
  } else if (benchmarkSet === "rgb") {
    const baseline = result.variants["head-local"];
    result.rgbRelativeToHeadLocal = Object.fromEntries(
      ["rgb-packed", "rgb-staged"].map((name) => {
        const candidate = result.variants[name];
        return [name, {
          connectedSpeedup:
            baseline.connected.timing.median / candidate.connected.timing.median,
          qkvSpeedup: baseline.qkv.timing.median / candidate.qkv.timing.median,
          connectedHtmlReduction:
            baseline.connectedHtmlBytes / candidate.connectedHtmlBytes,
          qkvHtmlReduction: baseline.qkvHtmlBytes / candidate.qkvHtmlBytes,
        }];
      }),
    );
  } else if (benchmarkSet === "shards") {
    const baseline = result.variants["shard-256"];
    result.relativeToShard256 = Object.fromEntries(
      [128, 192, 384].map((shard) => {
        const candidate = result.variants[`shard-${shard}`];
        return [shard, {
          connectedSpeedup:
            baseline.connected.timing.median / candidate.connected.timing.median,
          qkvSpeedup: baseline.qkv.timing.median / candidate.qkv.timing.median,
          connectedHtmlRatio:
            candidate.connectedHtmlBytes / baseline.connectedHtmlBytes,
        }];
      }),
    );
  } else {
    const head = result.variants["head-local"];
    const part = result.variants["part-contiguous"];
    const vector = result.variants["vector-born"];
    result.partContiguousRelativeToHeadLocal = {
      connectedSpeedup: head.connected.timing.median / part.connected.timing.median,
      qkvSpeedup: head.qkv.timing.median / part.qkv.timing.median,
      connectedHtmlReduction: head.connectedHtmlBytes / part.connectedHtmlBytes,
      qkvHtmlReduction: head.qkvHtmlBytes / part.qkvHtmlBytes,
    };
    result.vectorBornRelativeToHeadLocal = {
      connectedSpeedup: head.connected.timing.median / vector.connected.timing.median,
      qkvSpeedup: head.qkv.timing.median / vector.qkv.timing.median,
      connectedHtmlReduction: head.connectedHtmlBytes / vector.connectedHtmlBytes,
      qkvHtmlReduction: head.qkvHtmlBytes / vector.qkvHtmlBytes,
    };
    result.groupsRelativeToHeadLocal = Object.fromEntries(
      [2, 3, 4, 6].map((heads) => {
        const group = result.variants[`group-${heads}`];
        return [heads, {
          connectedSpeedup: head.connected.timing.median / group.connected.timing.median,
          qkvSpeedup: head.qkv.timing.median / group.qkv.timing.median,
          connectedHtmlReduction: head.connectedHtmlBytes / group.connectedHtmlBytes,
          qkvHtmlReduction: head.qkvHtmlBytes / group.qkvHtmlBytes,
        }];
      }),
    );
  }
  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
