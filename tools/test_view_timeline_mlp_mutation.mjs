import { createRequire } from "node:module";
import fs from "node:fs/promises";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const rounds = Number(process.env.VIEW_TIMELINE_MLP_MUTATION_ROUNDS ?? 4);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/gpt2-block-css/view-timeline-mlp-reference.json", import.meta.url),
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
    "http://127.0.0.1:4178/experiments/gpt2-block-css/view-timeline-mlp.html",
    { waitUntil: "load", timeout: 120000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const result = await page.evaluate(async (count) => {
    const scope = document.querySelector(".scope");
    const final = document.getElementById("final");
    const initialStyle = getComputedStyle(scope);
    const original = Array.from({ length: 768 }, (_, index) =>
      Number(initialStyle.getPropertyValue(`--n2-${String(index).padStart(3, "0")}`)),
    );
    const mutated = original.map((_, index) => original[(index + 1) % original.length] * 0.8);
    const timings = [];
    const outputs = [];
    for (let round = 0; round < count; round += 1) {
      const values = round % 2 ? original : mutated;
      const started = performance.now();
      values.forEach((value, index) => {
        scope.style.setProperty(`--n2-${String(index).padStart(3, "0")}`, String(value));
      });
      // Named view-timeline progress is refreshed asynchronously. The first
      // frame lays out the changed glyph widths; the second exposes the new
      // progress values to the dependent projection.
      await new Promise((resolve) => requestAnimationFrame(resolve));
      await new Promise((resolve) => requestAnimationFrame(resolve));
      const style = getComputedStyle(final);
      const output = [];
      for (let index = 0; index < 768; index += 1) {
        output.push(Number(style.getPropertyValue(`--out-${String(index).padStart(3, "0")}`)));
      }
      timings.push(performance.now() - started);
      outputs.push(output);
    }
    return { timings, outputs, original, mutated };
  }, rounds);
  const sorted = [...result.timings].sort((a, b) => a - b);
  const adjacentChanges = result.outputs.slice(1).map((output, index) =>
    error(output, result.outputs[index]));
  const report = {
    chrome: await browser.version(),
    rounds,
    timings: result.timings,
    medianMilliseconds: sorted[Math.floor(sorted.length / 2)],
    outputChecksums: result.outputs.map((output) =>
      output.reduce((sum, value) => sum + value, 0)),
    mutatedInput: result.mutated,
    mutatedOutput: result.outputs[0],
    mutatedHead: result.outputs[0].slice(0, 12),
    restoredHead: result.outputs[1]?.slice(0, 12) ?? null,
    adjacentChanges,
    restored: result.outputs
      .map((output, round) => round % 2 ? error(output, reference.output) : null)
      .filter(Boolean),
  };
  await fs.writeFile(
    new URL("../experiments/gpt2-block-css/view-timeline-mlp-mutation-browser.json", import.meta.url),
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
