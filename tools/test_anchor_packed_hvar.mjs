import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/anchor-packed-hvar/reference.json", import.meta.url),
));
const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

try {
  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:4178/experiments/anchor-packed-hvar/", {
    waitUntil: "load",
  });
  await page.evaluate(() => document.fonts.ready);
  const result = await page.evaluate((secondSettings) => {
    const scope = document.getElementById("scope");
    const packed = document.getElementById("packed");
    const output = document.getElementById("result");
    const read = () => ({
      sources: [...document.querySelectorAll(".source")].map(
        (element) => getComputedStyle(element).width,
      ),
      packedWidth: getComputedStyle(packed).width,
      delays: getComputedStyle(output).animationDelay,
      vector: getComputedStyle(output).fontVariationSettings,
    });
    const initial = read();
    scope.style.fontVariationSettings = secondSettings;
    const mutated = read();
    return { initial, mutated };
  }, reference.settings[1]);
  console.log(JSON.stringify({ reference, result }, null, 2));
} finally {
  await browser.close();
}
