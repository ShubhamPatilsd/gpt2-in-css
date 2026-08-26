import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ??
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

try {
  const page = await browser.newPage();
  await page.goto(
    "http://127.0.0.1:4178/experiments/sparse-additive-font-settings-probe.html",
    { waitUntil: "load" },
  );
  const computed = await page.locator("#probe").evaluate(
    (element) => getComputedStyle(element).fontVariationSettings,
  );
  console.log(JSON.stringify({ computed }));
} finally {
  await browser.close();
}
