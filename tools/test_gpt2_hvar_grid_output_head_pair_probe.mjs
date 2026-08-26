import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ javaScriptEnabled: false });
  await page.goto(
    "http://127.0.0.1:4178/experiments/gpt2-hvar-grid-output-head-global16-pair-probe/index.html",
    { waitUntil: "load" },
  );
  await page.evaluate(() => document.fonts.ready);
  const sweeps = [];
  for (const fontSize of [50, 100, 125, 150, 200, 250, 500, 1000]) {
    await page.locator(".stage").evaluate((element, size) => {
      element.style.fontSize = `${size}px`;
    }, fontSize);
    const values = await page.locator(".candidate").evaluateAll(
      (elements, size) => elements.map((element) => {
        const width = element.getBoundingClientRect().width;
        const displayMultiplier = size / 100;
        const base = Number(element.dataset.base) * displayMultiplier;
        const factor = Number(element.dataset.factor) / displayMultiplier;
        return {
          token: Number(element.id.slice("token-".length)),
          width,
          base,
          factor,
          decoded: (width - base) * factor,
        };
      }),
      fontSize,
    );
    sweeps.push({
      fontSize,
      values,
      decodedDifference11Minus13: values[0].decoded - values[1].decoded,
      intrinsicWidthDifference11Minus13: values[0].width - values[1].width,
    });
  }
  console.log(JSON.stringify({
    chrome: await browser.version(),
    sweeps,
  }, null, 2));
} finally {
  await browser.close();
}
