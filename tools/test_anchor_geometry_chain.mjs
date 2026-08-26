import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = process.env.ANCHOR_GEOMETRY_BASE_URL ??
  "http://127.0.0.1:4178/experiments/anchor-geometry-chain";
const rounds = Number(process.env.ANCHOR_GEOMETRY_ROUNDS ?? 5);
const manifestPath = new URL(
  "../experiments/anchor-geometry-chain/manifest.json", import.meta.url,
);
const resultPath = new URL(
  "../experiments/anchor-geometry-chain/results.json", import.meta.url,
);
const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));
const requested = process.env.ANCHOR_GEOMETRY_VARIANTS?.split(",").filter(Boolean);
const variantsToRun = requested?.length
  ? manifest.filter((item) => requested.includes(`${item.width}-${item.layers}-${item.mode}`))
  : manifest;

function median(values) {
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
}

const browser = await chromium.launch({ executablePath, headless: true });
const page = await browser.newPage({ viewport: { width: 1024, height: 768 } });
const samples = new Map(
  variantsToRun.map((item) => [`${item.width}-${item.layers}-${item.mode}`, []])
);
try {
  for (let round = 0; round < rounds; round += 1) {
    const order = round % 2 ? [...variantsToRun].reverse() : variantsToRun;
    for (const item of order) {
      const key = `${item.width}-${item.layers}-${item.mode}`;
      const started = performance.now();
      await page.goto(`${baseUrl}/${item.page}?r=${round}`, {
        waitUntil: "load",
        timeout: 120000,
      });
      const measured = await page.locator(".result").evaluateAll((nodes) =>
        nodes.map((node) => node.getBoundingClientRect().width)
      );
      const elapsed = performance.now() - started;
      const actual = measured.map((value) => (value - item.base) / item.scale);
      const errors = actual.map((value, index) => value - item.expected[index]);
      samples.get(key).push({
        round,
        elapsedMilliseconds: elapsed,
        rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
        maxError: Math.max(...errors.map(Math.abs)),
        finite: actual.every(Number.isFinite),
      });
    }
  }
} finally {
  await browser.close();
}

const variants = variantsToRun.map((item) => {
  const key = `${item.width}-${item.layers}-${item.mode}`;
  const all = samples.get(key);
  const warm = all.slice(1);
  return {
    ...item,
    warmMedianMilliseconds: median(warm.map((sample) => sample.elapsedMilliseconds)),
    maxRmse: Math.max(...all.map((sample) => sample.rmse)),
    maxError: Math.max(...all.map((sample) => sample.maxError)),
    finite: all.every((sample) => sample.finite),
    samples: all,
  };
});
const report = { chrome: await chromium.launch({ executablePath, headless: true }).then(async (b) => {
  const version = b.version();
  await b.close();
  return version;
}), rounds, variants };
await fs.writeFile(resultPath, `${JSON.stringify(report, null, 2)}\n`);
for (const item of variants) {
  console.log(
    `n=${item.width} l=${item.layers} mode=${item.mode} terms=${item.matrix_terms} ` +
    `warm=${item.warmMedianMilliseconds.toFixed(1)}ms ` +
    `rmse=${item.maxRmse.toExponential(3)} max=${item.maxError.toExponential(3)}`
  );
}
