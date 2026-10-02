// R7S head mutation harness (JS harness; pages are JS-free). usage: node run_head.mjs <index.html> <expected.json> <out.json> <sample|greedy>
import { createRequire } from "node:module"; import fs from "node:fs";
const require = createRequire(import.meta.url);
const dep = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dep}/playwright`);
const exe = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const [file, expectedPath, out, mode] = process.argv.slice(2);
const meta = JSON.parse(fs.readFileSync(expectedPath, "utf8"));
const ref = JSON.parse(fs.readFileSync("/Users/shubhampatil/Documents/programming/gpt2-css/experiments/browser-gpt2/head-two-pass/reference.json", "utf8"));
const cases = mode === "greedy" ? meta.cases.filter(c => c.kind === "greedy") : meta.cases;
const browser = await chromium.launch({ executablePath: exe, headless: true, args: ["--allow-file-access-from-files"] });
const results = { mode, file, version: browser.version(), samples: [] };
try {
  const ctx = await browser.newContext({ viewport: { width: 800, height: 600 }, bypassCSP: true });
  const page = await ctx.newPage();
  const t0 = Date.now();
  await page.goto(`file://${file}`, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  // force the first full style+layout (cold font instantiation) and wait for output epoch 1
  const cold0 = performance.now();
  await page.evaluate(() => getComputedStyle(document.getElementById("head-result")).getPropertyValue("--winner"));
  results.coldMs = Date.now() - t0;
  console.log(JSON.stringify({ cold: results.coldMs }));
  let epoch = 1;
  for (const c of cases) {
    epoch = (epoch % 15) + 1;
    const hidden = ref.hidden[c.fixtureIndex];
    const decl = hidden.map((v, i) => `--h${i}:${v.toPrecision(12)}`).join(";") +
      (mode === "sample" ? `;--noise-col:${c.col};--temp:${c.T}` : "") + `;--head-input-epoch:${epoch}`;
    const r = await page.evaluate(async ({ decl, epoch }) => {
      const res = document.getElementById("head-result");
      await new Promise(r => requestAnimationFrame(r));
      const t0 = performance.now();
      document.body.style.cssText = decl;
      let got, n = 0;
      for (;;) {
        got = getComputedStyle(res).getPropertyValue("--head-output-epoch").trim();
        if (Number(got) === epoch % 16 || ++n > 40) break;
        await new Promise(r => requestAnimationFrame(r));
      }
      const t1 = performance.now();
      return { ms: t1 - t0, polls: n, outEpoch: got, winner: Number(getComputedStyle(res).getPropertyValue("--winner")),
               groupIndex: getComputedStyle(res).getPropertyValue("--head-group-index"), maxScore: getComputedStyle(res).getPropertyValue("--head-max-score") };
    }, { decl, epoch });
    const sample = { ...c, epoch, ...r, passed: r.winner === c.expected };
    results.samples.push(sample);
    console.log(JSON.stringify({ state: c.state, col: c.col, T: c.T, winner: r.winner, expected: c.expected, passed: sample.passed, ms: Math.round(r.ms), polls: r.polls, maxScore: r.maxScore }));
  }
} finally { await browser.close(); }
fs.writeFileSync(out, JSON.stringify(results, null, 1));
