import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 600 } });
  await page.goto(
    "http://127.0.0.1:4178/experiments/orthogonal-container-2d-probe.html",
    { waitUntil: "load" },
  );
  const read = () => page.locator(".probe").evaluateAll((elements) =>
    Object.fromEntries(elements.map((element) => [
      [...element.classList].find((name) => name !== "probe"),
      element.getBoundingClientRect().width,
    ])));
  const initial = await read();
  const changed = await page.locator(".outer").evaluate((outer) => {
    outer.style.width = "149px";
    const inner = outer.querySelector(".inner");
    inner.style.height = "71px";
    return Object.fromEntries(Array.from(outer.querySelectorAll(".probe"), (element) => [
      [...element.classList].find((name) => name !== "probe"),
      element.getBoundingClientRect().width,
    ]));
  });
  console.log(JSON.stringify({ initial, changed }, null, 2));
} finally {
  await browser.close();
}
