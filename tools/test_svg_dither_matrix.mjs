import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const sharp = require(`${root}/sharp`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/svg-dither-matrix/reference.json", import.meta.url), "utf8"));

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 128, height: 40 } });
  const runs = {};
  for (const name of ["ordinary", "dithered", "distributed"]) {
    const started = performance.now();
    await page.goto(`http://127.0.0.1:4178/experiments/svg-dither-matrix/${name}.html`, {
      waitUntil: "load",
    });
    const png = await page.locator("svg").screenshot();
    const elapsed = performance.now() - started;
    const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
    const values = [];
    for (let column = 0; column < reference.width; column += 1) {
      const offset = column * info.channels;
      const channels = [data[offset], data[offset + 1], data[offset + 2]];
      const normalized = name !== "ordinary"
        ? channels.reduce((sum, value) => sum + value / 255, 0) / 3
        : channels[0] / 255;
      values.push((normalized - reference.center) * 2 * reference.ranges[2]);
    }
    const errors = values.map((value, index) => value - reference.expected2[index]);
    runs[name] = {
      rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
      maxError: Math.max(...errors.map(Math.abs)),
      milliseconds: elapsed,
      distinctValues: new Set(values.map((value) => value.toFixed(12))).size,
      samples: values.slice(0, 6),
    };
  }
  console.log(JSON.stringify({
    ...runs,
    improvement: runs.ordinary.rmse / runs.dithered.rmse,
  }, null, 2));
} finally {
  await browser.close();
}
