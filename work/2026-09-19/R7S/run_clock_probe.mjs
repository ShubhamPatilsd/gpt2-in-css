// R7S clock-latch probe runner (JS harness only; page logic is pure CSS). usage: node run_clock_probe.mjs <page> <out.json>
import { createRequire } from "node:module"; import fs from "node:fs";
const require = createRequire(import.meta.url);
const dep = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dep}/playwright`);
const exe = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const [file, out] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: exe, headless: true, args: ["--allow-file-access-from-files"] });
const results = { version: null, runs: [] };
try {
  results.version = browser.version();
  const read = (page) => page.evaluate(() => {
    const g = (sel, p) => getComputedStyle(document.querySelector(sel)).getPropertyValue(p).trim();
    return { clock: g('.clock', '--clock'), seed: g('.latch', '--seed'), seedT: g('.latch-t', '--seed-t'),
             live: g('.latch-t', '--seed-live'), text: document.querySelector('#out').innerText,
             after: getComputedStyle(document.querySelector('#out'), '::after').content, t: performance.now() };
  });
  for (let run = 0; run < 4; run++) {
    const page = await browser.newPage({ viewport: { width: 800, height: 600 } });
    await page.goto(`file://${file}`, { waitUntil: "load" });
    const delay = 300 + Math.floor(Math.random() * 1500);
    await page.waitForTimeout(delay);
    const before = await read(page);
    await page.click('#run');
    const samples = [];
    for (let i = 0; i < 12; i++) { await page.waitForTimeout(150); samples.push(await read(page)); }
    let override = null;
    if (run === 3) { await page.selectOption('#seed', '17'); await page.waitForTimeout(100); override = await read(page); }
    const seeds = new Set(samples.map(s => s.seed)), seedsT = new Set(samples.map(s => s.seedT));
    results.runs.push({ run, delayMs: delay, before, samples, stableA: seeds.size === 1, stableB: seedsT.size === 1,
                        seedA: [...seeds], seedB: [...seedsT], override });
    console.log(JSON.stringify({ run, delay, seedA: [...seeds], seedB: [...seedsT], liveMoves: new Set(samples.map(s=>s.live)).size, after: samples[0].after, override: override && { seed: override.seed, after: override.after } }));
    await page.close();
  }
} finally { await browser.close(); }
fs.writeFileSync(out, JSON.stringify(results, null, 1));
