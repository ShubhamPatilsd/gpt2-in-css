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
  await page.goto(
    "http://127.0.0.1:4178/experiments/counter-vector-reduction-probe.html",
    { waitUntil: "load", timeout: 30000 },
  );
  const report = await page.locator(".scope").evaluate((scope) => ({
    increments: [...scope.querySelectorAll(".increment")].map((element) => {
      const style = getComputedStyle(element);
      return {
        q: style.getPropertyValue("--q"),
        counterIncrement: style.counterIncrement,
      };
    }),
    pseudoContent: [...scope.querySelectorAll(".result")].map((element) =>
      getComputedStyle(element, "::before").content,
    ),
    resultWidths: [...scope.querySelectorAll(".result")].map((element) =>
      element.getBoundingClientRect().width,
    ),
  }));
  report.accessibility = await page.locator(".scope").ariaSnapshot();
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
