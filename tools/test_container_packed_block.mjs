import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/gpt2-block-css/container-packed-block-reference.json", import.meta.url,
), "utf8"));
const rounds = Number(process.env.CONTAINER_PACKED_BLOCK_ROUNDS ?? 7);

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maximumError: Math.max(...errors.map(Math.abs)),
  };
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
let report;
try {
  const page = await browser.newPage({ viewport: { width: 64, height: 64 } });
  const started = performance.now();
  await page.goto(
    "http://127.0.0.1:4178/experiments/gpt2-block-css/container-packed-block.html",
    { waitUntil: "load", timeout: 180000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const result = await page.evaluate(async ({ count, input }) => {
    const scope = document.querySelector(".norm1");
    const final = document.getElementById("final");
    const read = () => {
      const style = getComputedStyle(final);
      return Array.from({ length: 768 }, (_, index) => Number(
        style.getPropertyValue(`--out-${String(index).padStart(3, "0")}`),
      ));
    };
    const initial = read();
    const timings = [];
    const outputs = [];
    for (let round = 0; round < count; round += 1) {
      const factor = round % 2 ? 1 : 0.98;
      const before = performance.now();
      input.forEach((value, index) => scope.style.setProperty(
        `--x-${String(index).padStart(3, "0")}`, String(value * factor),
      ));
      await new Promise((resolve) => requestAnimationFrame(resolve));
      outputs.push(read());
      timings.push(performance.now() - before);
    }
    return { initial, outputs, timings };
  }, { count: rounds, input: reference.input });
  const warm = result.timings.slice(1).toSorted((a, b) => a - b);
  report = {
    chrome: await browser.version(),
    rounds,
    loadMilliseconds: performance.now() - started,
    initialAgainstPacked: summarize(result.initial, reference.packed),
    initialAgainstBaseline: summarize(result.initial, reference.baseline),
    warmMedianMilliseconds: warm[Math.floor(warm.length / 2)],
    timings: result.timings,
    restored: result.outputs
      .filter((_, round) => round % 2)
      .map((output) => summarize(output, reference.packed)),
    changedChecksum: result.outputs[0].reduce((sum, value) => sum + value, 0),
    restoredChecksum: result.outputs[1].reduce((sum, value) => sum + value, 0),
  };
} finally {
  await browser.close();
}
await fs.writeFile(
  new URL("../experiments/gpt2-block-css/container-packed-block-browser.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
