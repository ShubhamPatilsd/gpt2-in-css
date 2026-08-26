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
    "http://127.0.0.1:4178/experiments/gpt2-hvar-grid-output-head-global16-twoplane/probe.html",
    { waitUntil: "load", timeout: 120000 },
  );
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => {
    const bases = { "token-0": 120344.6, "token-11": 85565, "token-477": 104529.5 };
    for (const [id, base] of Object.entries(bases)) {
      const element = document.getElementById(id);
      element.style.setProperty("--base", String(base));
      element.style.setProperty("--factor", "75.48600606");
    }
  });
  const candidates = await page.locator(".candidate").evaluateAll((elements) =>
    elements.map((element) => {
      const computedWidth = element.getBoundingClientRect().width;
      const previous = element.style.width;
      element.style.setProperty("width", "max-content", "important");
      const intrinsicWidth = element.getBoundingClientRect().width;
      if (previous) element.style.width = previous;
      else element.style.removeProperty("width");
      return {
        id: element.id,
        computedWidth,
        intrinsicWidth,
        base: Number(element.style.getPropertyValue("--base")),
        codePoints: Array.from(element.textContent).map((value) => value.codePointAt(0)),
      };
    }));
  const fontFaces = await page.evaluate(() => [...document.styleSheets[0].cssRules]
    .filter((rule) => rule.constructor.name === "CSSFontFaceRule")
    .map((rule) => ({ family: rule.style.fontFamily, sizeAdjust: rule.style.sizeAdjust })));
  console.log(JSON.stringify({ candidates, fontFaces }, null, 2));
} finally {
  await browser.close();
}
