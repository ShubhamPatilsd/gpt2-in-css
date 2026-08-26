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
  await page.goto("http://127.0.0.1:4178/experiments/css-axis-list-pingpong-probe.html");
  const result = await page.locator("#result").evaluate((node) => {
    const style = getComputedStyle(node);
    return {
      a: style.getPropertyValue("--a").trim(),
      b: style.getPropertyValue("--b").trim(),
      fontVariationSettings: style.fontVariationSettings,
    };
  });
  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
