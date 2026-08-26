import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:4178/experiments/anchor-axis-gather-probe.html");
  await page.evaluate(() => document.fonts.ready);
  console.log(await page.locator(".sample").evaluateAll((elements) =>
    Object.fromEntries(elements.map((element) => [element.id, {
      width: element.getBoundingClientRect().width,
      settings: getComputedStyle(element).fontVariationSettings,
    }]))));
} finally {
  await browser.close();
}
