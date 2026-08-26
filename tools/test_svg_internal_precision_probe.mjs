import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/svg-internal-precision/reference.json", import.meta.url,
), "utf8"));
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const colorProfile = process.env.SVG_COLOR_PROFILE ?? "srgb";

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: [`--force-color-profile=${colorProfile}`],
});
try {
  const page = await browser.newPage({ viewport: { width: 256, height: 128 } });
  await page.goto(
    `http://127.0.0.1:4178/experiments/svg-internal-precision/index.html?${Date.now()}`,
    { waitUntil: "load" },
  );
  const png = await page.locator("svg").screenshot();
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const rows = reference.rows.map((metadata) => {
    const values = Array.from({ length: reference.samples }, (_, column) =>
      data[(metadata.row * info.width + column) * info.channels]);
    const unique = [...new Set(values)];
    const changes = values.reduce((count, value, index) =>
      count + (index > 0 && value !== values[index - 1] ? 1 : 0), 0);
    return { ...metadata, uniqueLevels: unique.length, changes, values };
  });
  const result = {
    chromeColorProfile: colorProfile,
    screenshot: { width: info.width, height: info.height, channels: info.channels },
    rows,
  };
  console.log(JSON.stringify(result, null, 2));
  await fs.writeFile(
    new URL(`../experiments/svg-internal-precision/results-${colorProfile}.json`, import.meta.url),
    `${JSON.stringify(result, null, 2)}\n`,
  );
} finally {
  await browser.close();
}
