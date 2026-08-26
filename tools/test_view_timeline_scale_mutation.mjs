import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const file = process.env.VIEW_TIMELINE_SCALE_FILE ??
  "view-timeline-three-block-structural-scale.html";
const outputId = process.env.VIEW_TIMELINE_SCALE_OUTPUT_ID ?? "three-block-full";
const outputPrefix = process.env.VIEW_TIMELINE_SCALE_OUTPUT_PREFIX ?? "b1-final";
const frames = Number(process.env.VIEW_TIMELINE_SCALE_FRAMES ?? 6);
const rounds = Number(process.env.VIEW_TIMELINE_SCALE_ROUNDS ?? 7);
const resultName = process.env.VIEW_TIMELINE_SCALE_RESULT ??
  "view-timeline-three-block-structural-scale-browser.json";

function error(left, right) {
  const delta = left.map((value, index) => value - right[index]);
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
    { waitUntil: "load", timeout: 180000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const result = await page.evaluate(async ({ count, frameCount, id, prefix }) => {
    const scope = document.querySelector(".norm1");
    const final = document.getElementById(id);
    const style = getComputedStyle(scope);
    const original = Array.from({ length: 768 }, (_, index) => Number(
      style.getPropertyValue(`--x-${String(index).padStart(3, "0")}`),
    ));
    const mutated = original.map((value) => value * 0.999);
    const timings = [];
    const outputs = [];
    for (let round = 0; round < count; round += 1) {
      const values = round % 2 ? original : mutated;
      const started = performance.now();
      values.forEach((value, index) => scope.style.setProperty(
        `--x-${String(index).padStart(3, "0")}`,
        String(value),
      ));
      for (let frame = 0; frame < frameCount; frame += 1) {
        await new Promise((resolve) => requestAnimationFrame(resolve));
      }
      const outputStyle = getComputedStyle(final);
      outputs.push(Array.from({ length: 768 }, (_, index) => Number(
        outputStyle.getPropertyValue(
          `--${prefix}-${String(index).padStart(3, "0")}`,
        ),
      )));
      timings.push(performance.now() - started);
    }
    return { timings, outputs };
  }, { count: rounds, frameCount: frames, id: outputId, prefix: outputPrefix });
  const sorted = [...result.timings].sort((a, b) => a - b);
  const report = {
    chrome: await browser.version(),
    file,
    rounds,
    frames,
    timings: result.timings,
    medianMilliseconds: sorted[Math.floor(sorted.length / 2)],
    outputChecksums: result.outputs.map((values) =>
      values.reduce((sum, value) => sum + value, 0)),
    finite: result.outputs.every((values) => values.every(Number.isFinite)),
    adjacentChanges: result.outputs.slice(1).map((values, index) =>
      error(values, result.outputs[index])),
  };
  await fs.writeFile(
    new URL(`../experiments/gpt2-block-css/${resultName}`, import.meta.url),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
