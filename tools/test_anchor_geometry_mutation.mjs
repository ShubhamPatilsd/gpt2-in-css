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
const mutations = Number(process.env.ANCHOR_GEOMETRY_MUTATIONS ?? 7);
const requested = (process.env.ANCHOR_GEOMETRY_VARIANTS ?? "768-1-balanced")
  .split(",").filter(Boolean);
const manifestPath = new URL(
  "../experiments/anchor-geometry-chain/manifest.json", import.meta.url,
);
const resultPath = new URL(
  "../experiments/anchor-geometry-chain/mutation-results.json", import.meta.url,
);
const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));
const variants = manifest.filter((item) =>
  requested.includes(`${item.width}-${item.layers}-${item.mode}`)
);

function median(values) {
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
}

const browser = await chromium.launch({ executablePath, headless: true });
const page = await browser.newPage({ viewport: { width: 1024, height: 768 } });
const results = [];
try {
  for (const item of variants) {
    const navigationStarted = performance.now();
    await page.goto(`${baseUrl}/${item.page}?mutation=1`, {
      waitUntil: "load",
      timeout: 120000,
    });
    await page.locator(".result").evaluateAll((nodes) =>
      nodes.map((node) => node.getBoundingClientRect().width)
    );
    const navigationMilliseconds = performance.now() - navigationStarted;
    const samples = [];
    for (let round = 0; round < mutations; round += 1) {
      const alternate = round % 2 === 0;
      const widths = alternate ? item.alternate_input_widths : item.input_widths;
      const expected = alternate ? item.alternate_expected : item.expected;
      const measured = await page.evaluate(({ widths, base, scale }) => {
        const started = performance.now();
        const sources = document.querySelectorAll(".source");
        for (let index = 0; index < sources.length; index += 1) {
          sources[index].style.width = `${widths[index]}px`;
        }
        const actual = [...document.querySelectorAll(".result")].map(
          (node) => (node.getBoundingClientRect().width - base) / scale
        );
        return { milliseconds: performance.now() - started, actual };
      }, { widths, base: item.base, scale: item.scale });
      const errors = measured.actual.map((value, index) => value - expected[index]);
      samples.push({
        round,
        alternate,
        milliseconds: measured.milliseconds,
        rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
        maxError: Math.max(...errors.map(Math.abs)),
      });
    }
    const warm = samples.slice(1);
    results.push({
      width: item.width,
      layers: item.layers,
      mode: item.mode,
      matrixTerms: item.matrix_terms,
      htmlBytes: item.html_bytes,
      navigationMilliseconds,
      mutationMedianMilliseconds: median(warm.map((sample) => sample.milliseconds)),
      maxRmse: Math.max(...samples.map((sample) => sample.rmse)),
      maxError: Math.max(...samples.map((sample) => sample.maxError)),
      samples,
    });
  }
} finally {
  await browser.close();
}

await fs.writeFile(resultPath, `${JSON.stringify({ mutations, results }, null, 2)}\n`);
for (const item of results) {
  console.log(
    `n=${item.width} l=${item.layers} mode=${item.mode} ` +
    `navigate=${item.navigationMilliseconds.toFixed(1)}ms ` +
    `mutate=${item.mutationMedianMilliseconds.toFixed(1)}ms ` +
    `rmse=${item.maxRmse.toExponential(3)}`
  );
}
