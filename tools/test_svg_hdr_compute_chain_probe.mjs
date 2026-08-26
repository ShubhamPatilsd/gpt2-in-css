import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const sharp = require(`${root}/sharp`);
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/svg-hdr-compute-chain/reference.json", import.meta.url,
), "utf8"));
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const profiles = (process.env.SVG_HDR_PROFILES ?? "srgb,scrgb-linear,hdr10").split(",");
const profilesResult = [];

for (const profile of profiles) {
  const browser = await chromium.launch({
    executablePath,
    headless: true,
    args: [`--force-color-profile=${profile}`],
  });
  try {
    const page = await browser.newPage({ viewport: { width: 128, height: 64 } });
    const started = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/svg-hdr-compute-chain/index.html?${Date.now()}`,
      { waitUntil: "load" },
    );
    const png = await page.locator("svg").screenshot();
    const elapsed = performance.now() - started;
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
        monotonic: values.every((value, index) => index === 0 || value >= values[index - 1]),
        values,
      };
    });
    profilesResult.push({ profile, milliseconds: elapsed, rows });
  } finally {
    await browser.close();
  }
}

const result = { profiles: profilesResult };
console.log(JSON.stringify(result, null, 2));
await fs.writeFile(
  new URL("../experiments/svg-hdr-compute-chain/results.json", import.meta.url),
  `${JSON.stringify(result, null, 2)}\n`,
);
