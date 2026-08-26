import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const sharp = require(`${root}/sharp`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/svg-dither-transport/reference.json", import.meta.url), "utf8"));

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 20, height: 300 } });
  const started = performance.now();
  await page.goto("http://127.0.0.1:4178/experiments/svg-dither-transport/index.html", {
    waitUntil: "load",
  });
  const png = await page.locator("svg").screenshot();
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const expected = reference.checkpoints.at(-1);
  const decode = (code) => (code / 255 - reference.center) * 2 * reference.range;
  const ordinary = [];
  const dithered = [];
  for (let row = 0; row < reference.samples; row += 1) {
    const ordinaryPixel = row * info.width * info.channels;
    const ditherPixel = (row * info.width + 1) * info.channels;
    ordinary.push(decode(data[ordinaryPixel]));
    dithered.push((
      decode(data[ditherPixel]) +
      decode(data[ditherPixel + 1]) +
      decode(data[ditherPixel + 2])
    ) / 3);
  }
  const summarize = (values) => {
    const errors = values.map((value, index) => value - expected[index]);
    return {
      rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
      maxError: Math.max(...errors.map(Math.abs)),
      distinctValues: new Set(values.map((value) => value.toFixed(12))).size,
    };
  };
  console.log(JSON.stringify({
    ordinary: summarize(ordinary),
    rgbDithered: summarize(dithered),
    improvement: summarize(ordinary).rmse / summarize(dithered).rmse,
    milliseconds: performance.now() - started,
  }, null, 2));
} finally {
  await browser.close();
}
