import fs from "node:fs/promises";
import { createRequire } from "node:module";

const stage = process.argv[2] ?? "raw";
if (!new Set(["raw", "calibrated"]).has(stage)) {
  throw new Error("stage must be raw or calibrated");
}
const profile = process.env.SVG_HDR_PROFILE ?? "srgb";
const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const sharp = require(`${root}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: [`--force-color-profile=${profile}`],
});
try {
  const page = await browser.newPage({ viewport: { width: 128, height: 128 } });
  const started = performance.now();
  await page.goto(
    `http://127.0.0.1:4178/experiments/svg-hdr-codebook/${stage}.html?${Date.now()}`,
    { waitUntil: "load" },
  );
  const png = await page.locator("svg").screenshot();
  const milliseconds = performance.now() - started;
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const values = Array.from({ length: 64 }, (_, row) =>
    Array.from({ length: 64 }, (_, column) =>
      data[(row * info.width + column) * info.channels]));
  const result = {
    stage,
    profile,
    milliseconds,
    uniqueLevels: new Set(values.flat()).size,
    range: [Math.min(...values.flat()), Math.max(...values.flat())],
    values,
  };
  console.log(JSON.stringify({ ...result, values: undefined }, null, 2));
  await fs.writeFile(
    new URL(`../experiments/svg-hdr-codebook/${stage}-${profile}.json`, import.meta.url),
    `${JSON.stringify(result, null, 2)}\n`,
  );
} finally {
  await browser.close();
}
