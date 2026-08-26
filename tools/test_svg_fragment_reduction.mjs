import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const pageName = process.env.SVG_FRAGMENT_REDUCTION_PAGE ?? "index.html";

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 64, height: 64 } });
  await page.goto(
    `http://127.0.0.1:4178/experiments/svg-fragment-reduction-probe/${pageName}`,
    { waitUntil: "load" },
  );
  const png = await page.locator("body > svg").screenshot();
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const center = ((Math.floor(info.height / 2) * info.width)
    + Math.floor(info.width / 2)) * info.channels;
  const actual = data[center];
  const expected = 112;
  console.log(JSON.stringify({ actual, expected, error: actual - expected }, null, 2));
} finally {
  await browser.close();
}
