import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");
const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
const page = await browser.newPage();
page.on("console", (m) => console.log("console:", m.text().slice(0, 200)));
page.on("requestfailed", (r) => console.log("requestfailed:", r.url(), r.failure()?.errorText));
page.on("response", (r) => { if (/loop-carrier/.test(r.url())) console.log("response:", r.status(), r.url().split("/").pop()); });
await page.goto(process.env.URL, { waitUntil: "load", timeout: 300000 });
await page.evaluate(() => document.fonts.ready);
await new Promise((r) => setTimeout(r, 4000));
const out = await page.evaluate(() => {
  const w = (el) => el ? el.getBoundingClientRect().width : null;
  const witnesses = [...document.querySelectorAll(".font-witness")].filter((e) => /LoopCarrier/.test(e.style.fontFamily)).map((e) => `${e.style.fontFamily}:${w(e)}`);
  const proofs = [...document.querySelectorAll(".font-proof")].map((e) => w(e));
  return {
    loopFonts: [...document.fonts].filter((f) => /LoopCarrier/.test(f.family)).map((f) => `${f.family}:${f.status}`),
    otherNotLoaded: [...document.fonts].filter((f) => f.status !== "loaded").length,
    witnesses, proofsBelow1: proofs.map((p, i) => [i, p]).filter(([, p]) => p < 0.99),
    fontStatusWidth: w(document.querySelector(".font-status")), fontsLoaded: document.getElementById("fonts-loaded")?.getAttribute("class"),
  };
});
console.log(JSON.stringify(out));
await browser.close();
