import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const rounds = Number(process.env.VIEW_TIMELINE_BLOCK_MUTATION_ROUNDS ?? 5);
const file = process.env.VIEW_TIMELINE_BLOCK_FILE ?? "view-timeline-block.html";
const resultName = process.env.VIEW_TIMELINE_BLOCK_RESULT ??
  "view-timeline-block-mutation-browser.json";
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/gpt2-block-css/view-timeline-block-reference.json", import.meta.url),
));

function error(actual, expected) {
  const delta = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(delta.reduce((sum, value) => sum + value * value, 0) / delta.length),
    max: Math.max(...delta.map(Math.abs)),
  };
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

try {
  const page = await browser.newPage();
  await page.goto(
    `http://127.0.0.1:4178/experiments/gpt2-block-css/${file}`,
    { waitUntil: "load", timeout: 120000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const result = await page.evaluate(async (count) => {
    const scope = document.querySelector(".block-scope") ??
      document.querySelector(".norm1");
    const frameCount = scope.classList.contains("block-scope") ? 3 : 2;
    const final = document.getElementById("final");
    const initialStyle = getComputedStyle(scope);
    const original = Array.from({ length: 768 }, (_, index) =>
      Number(initialStyle.getPropertyValue(`--x-${String(index).padStart(3, "0")}`)),
    );
    // Keep the layer-normalized values inside the fixed HVAR axis ranges used
    // by this generated fixture while still changing the residual materially.
    const mutated = original.map((value) => value * 0.8);
    const timings = [];
    const outputs = [];
    for (let round = 0; round < count; round += 1) {
      const values = round % 2 ? original : mutated;
      const started = performance.now();
      values.forEach((value, index) => {
        scope.style.setProperty(
          `--x-${String(index).padStart(3, "0")}`,
          String(value),
        );
      });
      // The all-timeline fixture needs three frames. Hybrid fixtures expose
      // attention directly and only cross FC/projection timeline boundaries.
      for (let frame = 0; frame < frameCount; frame += 1) {
        await new Promise((resolve) => requestAnimationFrame(resolve));
      }
      const style = getComputedStyle(final);
      outputs.push(Array.from({ length: 768 }, (_, index) =>
        Number(style.getPropertyValue(`--out-${String(index).padStart(3, "0")}`)),
      ));
      timings.push(performance.now() - started);
    }
    return { timings, outputs, mutated, frameCount };
  }, rounds);
  const sorted = [...result.timings].sort((a, b) => a - b);
  const report = {
    chrome: await browser.version(),
    file,
    frameCount: result.frameCount,
    rounds,
    timings: result.timings,
    medianMilliseconds: sorted[Math.floor(sorted.length / 2)],
    outputChecksums: result.outputs.map((output) =>
      output.reduce((sum, value) => sum + value, 0)),
    mutatedInput: result.mutated,
    mutatedOutput: result.outputs[0],
    mutatedHead: result.outputs[0].slice(0, 12),
    restored: result.outputs
      .map((output, round) => round % 2 ? error(output, reference.output) : null)
      .filter(Boolean),
  };
  await fs.writeFile(
    new URL(`../experiments/gpt2-block-css/${resultName}`, import.meta.url),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(JSON.stringify({
    ...report,
    mutatedInput: undefined,
    mutatedOutput: undefined,
  }, null, 2));
} finally {
  await browser.close();
}
