import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");
const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
const ctx = await browser.newContext({ javaScriptEnabled: false }); const page = await ctx.newPage(); const cdp = await ctx.newCDPSession(page);
await cdp.send("DOM.enable"); await cdp.send("CSS.enable");
await page.goto(`file://${process.cwd()}/pages/mb5-calc-varw-K10000.html`, { waitUntil: "load" });
const { root } = await cdp.send("DOM.getDocument", { depth: 1 });
async function cs(sel, props) { const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: sel }); const { computedStyle } = await cdp.send("CSS.getComputedStyleForNode", { nodeId }); return Object.fromEntries(computedStyle.filter((p) => props.includes(p.name)).map((p) => [p.name, p.value])); }
console.log("body", await cs("body", ["--w0_0", "--w0_1", "--w9999_15", "--c2"]));
console.log("target", await cs("#target", ["--p0", "--p1", "--p9999", "--in", "--w0_0"]));
await browser.close();
