import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
  await page.goto(
    "http://127.0.0.1:4178/experiments/gpt2-hvar-grid-output-head-global11/probe.html",
    { waitUntil: "load", timeout: 60000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const report = await page.evaluate(() => {
    const elements = [...document.querySelectorAll(".group-grid > i")];
    const values = elements.map((element) => {
      const style = getComputedStyle(element);
      const computedWidth = style.width;
      const before = element.style.cssText;
      element.style.setProperty("width", "max-content", "important");
      const intrinsicWidth = element.getBoundingClientRect().width;
      element.style.cssText = before;
      return {
        id: element.id,
        width: computedWidth,
        rectWidth: element.getBoundingClientRect().width,
        intrinsicWidth,
        base: style.getPropertyValue("--base"),
        factor: style.getPropertyValue("--factor"),
        offset: style.getPropertyValue("--score-offset"),
        tie: style.getPropertyValue("--local-tie"),
      };
    });
    const rules = [...document.styleSheets].flatMap((sheet) => [...sheet.cssRules]);
    const matchingRules = rules
      .filter((rule) => rule.selectorText?.includes(".group-grid"))
      .slice(0, 8)
      .map((rule) => rule.cssText);
    return {
      values,
      matchingRules,
      ruleCount: rules.length,
      lastRules: rules.slice(-5).map((rule) => rule.cssText.slice(0, 500)),
      nthRuleCount: rules.filter((rule) =>
        rule.selectorText?.includes("nth-child")).length,
      supportsLiteral: CSS.supports(
        "width",
        "calc-size(max-content, calc(round(nearest, (size - 80558 * 1px) * 241.78396486 + 53248px, 4px) + 255 / 64 * 1px))",
      ),
      supportsVariable: CSS.supports(
        "width",
        "calc-size(max-content, calc(round(nearest, (size - var(--base) * 1px) * var(--factor) + var(--score-offset), 4px) + var(--local-tie) / 64 * 1px))",
      ),
    };
  });
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
