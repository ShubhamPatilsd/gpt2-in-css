// Headless check of transformer/index.html and index.html (MNIST). Harness JS only; pages have no <script>.
import { createRequire } from "node:module";
import fs from "node:fs";
const require = createRequire(import.meta.url);
const dep = "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dep}/playwright`);
const REPO = "/Users/shubhampatil/Documents/programming/gpt2-css";
const OUT = `${REPO}/audit/2026-10-05/T3-scratch`;
const ref = JSON.parse(fs.readFileSync(`${OUT}/reference.json`, "utf8"));
const mref = JSON.parse(fs.readFileSync(`${OUT}/mnist_reference.json`, "utf8"));
const PROMPTS = [" ab", "bcd", "de.", ". a"];
const result = { transformer: {}, mnist: {} };
const t0 = performance.now();
const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
result.chromeVersion = browser.version();
result.launchMs = Math.round(performance.now() - t0);
try {
  const page = await browser.newPage({ viewport: { width: 1200, height: 900 } });
  const errors = []; page.on("console", m => errors.push(`${m.type()}: ${m.text()}`)); page.on("pageerror", e => errors.push(String(e)));
  // ---- transformer ----
  let t = performance.now();
  await page.goto(`file://${REPO}/transformer/index.html`, { waitUntil: "load" });
  const loadMs = performance.now() - t;
  const read = () => page.evaluate(() => {
    const rs = getComputedStyle(document.documentElement);
    const steps = [...document.querySelectorAll(".generated-token")].map(g => {
      const ops = [...g.querySelectorAll(".token-option")].map(o => +getComputedStyle(o).opacity);
      const i = ops.indexOf(Math.max(...ops));
      return { opacities: ops, chosen: i, text: g.querySelectorAll(".token-option")[i].textContent };
    });
    const logits = [0,1,2,3,4,5,6].map(k => +rs.getPropertyValue(`--generation-0-logit-${k}`));
    const prompt = [...document.querySelectorAll(".prompt-value")].find(e => getComputedStyle(e).display !== "none")?.textContent;
    return { prompt, steps, step1Logits: logits, hasScript: !!document.querySelector("script"), visibleText: document.querySelector(".generation").innerText };
  });
  t = performance.now(); const first = await read(); const firstReadMs = performance.now() - t;
  await page.screenshot({ path: `${OUT}/transformer-default.png`, fullPage: true });
  result.transformer.loadMs = Math.round(loadMs); result.transformer.firstStyleReadMs = Math.round(firstReadMs);
  result.transformer.runs = [];
  for (let p = 0; p < 4; p++) {
    t = performance.now();
    if (p > 0) await page.click(`label[for=prompt-${p}]`);
    const r = p === 0 ? first : await read();
    const ms = Math.round(performance.now() - t);
    const r2 = ref[PROMPTS[p]];
    const gen = r.steps.map(s => s.text).join("");
    const refGen = r2.map(s => s.token).join("");
    const maxLogitErr = Math.max(...r.step1Logits.map((v, i) => Math.abs(v - r2[0].logits[i])));
    const oneHot = r.steps.every(s => s.opacities.filter(o => o === 1).length === 1 && s.opacities.filter(o => o === 0).length === 6);
    result.transformer.runs.push({ prompt: PROMPTS[p], shownPrompt: r.prompt, css: gen, ref: refGen, match: gen === refGen, oneHot, cssStep1Logits: r.step1Logits, refStep1Logits: r2[0].logits, maxStep1LogitAbsErr: maxLogitErr, ms, opacities: r.steps.map(s => s.opacities) });
    if (p === 3) await page.screenshot({ path: `${OUT}/transformer-prompt3.png`, fullPage: true });
  }
  result.transformer.hasScript = first.hasScript; result.transformer.visibleText = first.visibleText;
  result.transformer.console = errors.splice(0);
  // ---- MNIST ----
  t = performance.now();
  await page.goto(`file://${REPO}/index.html`, { waitUntil: "load" });
  result.mnist.loadMs = Math.round(performance.now() - t);
  const mread = () => page.evaluate(() => {
    const rows = [...document.querySelectorAll(".score-row")].map(r => +getComputedStyle(r).getPropertyValue("--score"));
    const ref = [...document.querySelectorAll(".reference-detail")].find(e => getComputedStyle(e).display !== "none")?.innerText;
    const detail = [...document.querySelectorAll(".sample-detail")].find(e => getComputedStyle(e).display !== "none")?.innerText;
    const shown = [...document.querySelectorAll(".score-value")].map(e => getComputedStyle(e, "::after").content);
    return { scores: rows, pred: rows.indexOf(Math.max(...rows)), refText: ref, detail, shown, hasScript: !!document.querySelector("script") };
  });
  t = performance.now(); const m0 = await mread(); result.mnist.firstStyleReadMs = Math.round(performance.now() - t);
  await page.screenshot({ path: `${OUT}/mnist-default.png`, fullPage: true });
  const errs = (a, b) => Math.max(...a.map((v, i) => Math.abs(v - b[i])));
  result.mnist.default = { ...m0, refPred: mref["sample-0"].pred, refScores: mref["sample-0"].scores, maxAbsErr: errs(m0.scores, mref["sample-0"].scores) };
  result.mnist.all = [];
  for (let s = 0; s < 10; s++) {
    await page.click(`label[for=sample-${s}]`);
    const m = await mread();
    result.mnist.all.push({ sample: s, cssPred: m.pred, refPred: mref[`sample-${s}`].pred, maxAbsErr: +errs(m.scores, mref[`sample-${s}`].scores).toFixed(6) });
  }
  result.mnist.console = errors.splice(0);
} finally { await browser.close(); }
result.totalMs = Math.round(performance.now() - t0);
fs.writeFileSync(`${OUT}/browser_result.json`, JSON.stringify(result, null, 1));
console.log(JSON.stringify(result, (k, v) => (k === "opacities" || k === "shown") ? undefined : v, 1));
