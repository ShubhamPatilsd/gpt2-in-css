import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/font-packed-metrics/reference.json", import.meta.url), "utf8"));

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 300 } });
  await page.goto("http://127.0.0.1:4178/experiments/font-packed-metrics/index.html", {
    waitUntil: "load", timeout: 120000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  const result = await page.evaluate(({ inputs, weights, outputs }) => {
    const producer = document.querySelector(".producer");
    const target = document.querySelector("#result");
    const axis = (index) => `X${String(index).padStart(3, "0")}`;
    const samples = [];
    for (let iteration = 0; iteration < 400; iteration += 1) {
      const next = inputs.map((value, index) =>
        index === iteration % inputs.length ? -value : value);
      producer.style.fontVariationSettings = next.map((value, index) =>
        `"${axis(index)}" ${value}`).join(",");
      const started = performance.now();
      const style = getComputedStyle(target);
      const packed = [Number(style.getPropertyValue("--p0")),
        Number(style.getPropertyValue("--p1"))];
      const actual = Array.from({ length: outputs }, (_, index) =>
        Number(style.getPropertyValue(`--o${index}`)));
      const milliseconds = performance.now() - started;
      const expected = weights.map((row) =>
        row.reduce((sum, weight, index) => sum + weight * next[index], 0));
      samples.push({ actual, expected, packed, milliseconds });
    }
    return samples;
  }, reference);
  const errors = result.flatMap((sample) =>
    sample.actual.map((value, index) => value - sample.expected[index]));
  const times = result.slice(20).map((sample) => sample.milliseconds).sort((a, b) => a - b);
  console.log(JSON.stringify({
    samples: result.length,
    finite: result.every((sample) => sample.actual.every(Number.isFinite)),
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
    medianReadMilliseconds: times[Math.floor(times.length / 2)],
    first: result[0],
    last: result.at(-1),
  }, null, 2));
} finally {
  await browser.close();
}
