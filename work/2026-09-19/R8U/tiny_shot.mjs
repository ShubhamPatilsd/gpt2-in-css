// R8U: screenshots of the TinyStories reference pages (UX study only). env: T_URL T_OUT T_CLICK (css selector to click after load) T_WAIT_S
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require(`${process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"}/playwright`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: false, args: ["--force-device-scale-factor=1", "--window-size=1100,790"] });
const page = await (await browser.newContext({ viewport: { width: 1100, height: 700 } })).newPage();
await page.goto(process.env.T_URL, { waitUntil: "load", timeout: 300000 }); await sleep(4000);
await page.screenshot({ path: `${process.env.T_OUT}-idle.png` });
if (process.env.T_CLICK) { await page.click(process.env.T_CLICK).catch((e) => console.log("click failed", String(e).slice(0, 200)));
  for (const s of (process.env.T_WAIT_S ?? "10,30").split(",").map(Number)) { await sleep(s * 1000); await page.screenshot({ path: `${process.env.T_OUT}-run-${s}s.png` }); } }
console.log(JSON.stringify(await page.evaluate(() => ({ title: document.title, text: document.body.innerText.slice(0, 600) }))));
await browser.close();
