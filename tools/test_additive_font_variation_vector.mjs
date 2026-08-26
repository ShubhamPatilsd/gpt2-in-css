import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

try {
  const page = await browser.newPage();
  await page.goto(
    "http://127.0.0.1:4178/experiments/additive-font-variation-vector/index.html",
    { waitUntil: "load" },
  );
  const result = await page.evaluate(() => Object.fromEntries(
    ["replace", "add", "accumulate", "sparse", "nested"].map((id) => [
      id,
      getComputedStyle(document.getElementById(id)).fontVariationSettings,
    ]),
  ));
  console.log(JSON.stringify({ chrome: await browser.version(), result }, null, 2));
} finally {
  await browser.close();
}
