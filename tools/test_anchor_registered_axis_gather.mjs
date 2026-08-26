import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(
    "http://127.0.0.1:4178/experiments/anchor-registered-axis-gather-probe.html",
    { waitUntil: "load" },
  );
  const result = await page.locator("#consumer").evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      a0: style.getPropertyValue("--a0").trim(),
      a1: style.getPropertyValue("--a1").trim(),
      width: style.width,
      fontVariationSettings: style.fontVariationSettings,
    };
  });
  result.confirmedRejected = result.a0 === "-999" && result.a1 === "-999";
  console.log(JSON.stringify({
    chrome: await browser.version(),
    runtimeContainsJavaScript: false,
    ...result,
  }, null, 2));
  if (!result.confirmedRejected) process.exitCode = 1;
  await context.close();
} finally {
  await browser.close();
}
