import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/font-extra-numeric-probe/ic-height.json", import.meta.url), "utf8"));

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
  await page.goto("http://127.0.0.1:4178/experiments/font-extra-numeric-probe/ic-height.html", {
    waitUntil: "load", timeout: 120000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  const result = await page.evaluate((count) => Array.from({ length: count }, (_, index) => {
    const node = document.querySelector(`#p${index}`);
    const sink = node.querySelector(".sink");
    return {
      fontSizeAdjust: getComputedStyle(node).fontSizeAdjust,
      ch: getComputedStyle(node).width,
      value: Number(getComputedStyle(sink).getPropertyValue("--vheight")),
    };
  }), reference.axis_values.length);
  const errors = result.map((item, index) => item.value - reference.expected[index]);
  console.log(JSON.stringify({
    expected: reference.expected,
    result,
    rmse: Math.sqrt(errors.reduce((sum, error) => sum + error * error, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  }, null, 2));
} finally {
  await browser.close();
}
