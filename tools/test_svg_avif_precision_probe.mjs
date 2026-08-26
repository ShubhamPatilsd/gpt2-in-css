import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/svg-avif-precision/reference.json", import.meta.url,
), "utf8"));
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const profiles = (process.env.SVG_AVIF_PROFILES ?? "srgb,scrgb-linear,hdr10").split(",");
const all = [];

for (const profile of profiles) {
  const browser = await chromium.launch({
    executablePath,
    headless: true,
    args: [`--force-color-profile=${profile}`],
  });
  try {
    const page = await browser.newPage({ viewport: { width: 128, height: 64 } });
    await page.goto(
      `http://127.0.0.1:4178/experiments/svg-avif-precision/index.html?${Date.now()}`,
      { waitUntil: "load" },
    );
    await page.evaluate(async () => {
      await Promise.all(Array.from(document.images, (image) => image.decode()));
    });
    const png = await page.locator("svg").screenshot();
    const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
    const rows = reference.rows.map((row) => {
      const values = Array.from({ length: reference.width }, (_, x) =>
        data[(row.row * info.width + x) * info.channels]);
      return {
        ...row,
        uniqueLevels: new Set(values).size,
        changes: values.reduce((count, value, index) =>
          count + (index > 0 && value !== values[index - 1] ? 1 : 0), 0),
        range: [Math.min(...values), Math.max(...values)],
        values,
      };
    });
    all.push({ profile, rows });
  } finally {
    await browser.close();
  }
}

const result = { profiles: all };
console.log(JSON.stringify(result, null, 2));
await fs.writeFile(
  new URL("../experiments/svg-avif-precision/results.json", import.meta.url),
  `${JSON.stringify(result, null, 2)}\n`,
);
