import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");
const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
const page = await browser.newPage();
page.on("console", (m) => console.log("console:", m.text()));
page.on("requestfailed", (r) => console.log("requestfailed:", r.url(), r.failure()?.errorText));
page.on("response", (r) => { if (/woff2|ttf/.test(r.url())) console.log("response:", r.status(), r.url()); });
await page.goto(process.env.URL, { waitUntil: "load" });
await page.evaluate(() => document.fonts.ready);
await new Promise((r) => setTimeout(r, 1500));
const out = await page.evaluate(() => ({
  fonts: [...document.fonts].map((f) => `${f.family}:${f.status}`),
  widths: Object.fromEntries(["w1", "w2", "w3", "t1", "t2"].map((id) => [id, document.getElementById(id).getBoundingClientRect().width])),
}));
console.log(JSON.stringify(out));
await browser.close();
