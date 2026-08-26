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
  await page.goto("http://127.0.0.1:4178/experiments/anchor-packed-vector/", {
    waitUntil: "load",
  });
  const result = await page.evaluate(() => {
    const packed = document.getElementById("packed");
    const output = document.getElementById("result");
    const read = () => ({
      width: getComputedStyle(packed).width,
      delays: getComputedStyle(output).animationDelay,
      vector: getComputedStyle(output).fontVariationSettings,
    });
    const initial = read();
    document.querySelector(".s0").style.width = "58px";
    document.querySelector(".s1").style.width = "43px";
    document.querySelector(".s2").style.width = "30px";
    document.querySelector(".s3").style.width = "35px";
    const mutated = read();
    return { initial, mutated };
  });
  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
