#!/usr/bin/env node
/** Controlled browser gates and shared-vector comparisons for partitioned GSUB. */
import fs from "node:fs/promises";
import path from "node:path";
import http from "node:http";
import os from "node:os";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
const require = createRequire(import.meta.url);
const { chromium } = require(`${process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"}/playwright`);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const out = path.join(root, "experiments/gsub-partitioned-digits");
const args = process.argv.slice(2), arg = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const mode = arg("--mode", "correctness"), widths = arg("--widths", "4,16,64").split(",").map(Number);
const selected = arg("--variants", "").split(",").filter(Boolean), batch = Number(arg("--batch", "64"));
if (!["smoke", "correctness", "timing"].includes(mode) || batch % 16) throw new Error("Bad mode or batch (must be divisible by16)");
const destination = path.resolve(out, arg("--output", `results-${mode}.json`));
const reference = JSON.parse(await fs.readFile(path.join(out, "reference.json"), "utf8"));
const retained = JSON.parse(await fs.readFile(path.join(root, "experiments/gsub-weighted-sum-probe/reference.json"), "utf8"));
const reusable = JSON.parse(await fs.readFile(path.join(root, "experiments/gsub-reusable-digits/reference.json"), "utf8"));
const hvar = JSON.parse(await fs.readFile(path.join(out, "hvar-reference.json"), "utf8"));
const staticReference = JSON.parse(await fs.readFile(path.join(out, "static-reference.json"), "utf8"));
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const report = { startedAt: new Date().toISOString(), mode, batch, reference, harnessSha256: sha(await fs.readFile(fileURLToPath(import.meta.url))), environment: { node: process.version, cpu: os.cpus()[0]?.model, platform: process.platform, arch: process.arch }, fontSha256: {}, correctness: [], controls: [], timings: [], skipped: [], errors: [], methodology: {
  arithmetic: "F=2*sum_i([3,-2,5,1][i%4]*x_i)+1, signed integer inputs[-8,7]; external oracle supplies no intermediate products or answers to the page",
  endpoints: "Raw CSS properties once per vector parent; native font width -> CSS anchor/container numerical readback -> width=commonOffset+3*F. DirectCSS consumes numeric F directly.",
  matrix: "N64,M16 uses16 REPEATED coefficient rows as causal isolation, not distinct learned outputs. Parents share raw inputs. Each GSUB row shapes its own text with row-shifted nonce; HVAR uses one font with16 output glyphs and shared parent axis settings. Individual GSUB strings differ across rows.",
  static: "Static-advance control folds the affine expression into fixed per-input glyph advances; normal text layout sums them. It has no GSUB and no internal dependent arithmetic stage.",
  samples: "3 fresh browsers, independent seed for every repetition/configuration;5 warmups+20 measured samples; cyclic backend order and rotated configuration order. Upper median of20 samples, then median of3 repetition medians.",
  timing: "Parent property writes through forced dependent width reads, including harness loop overhead; excludes stimulus generation, external oracle, font load and protocol transport",
  limits: "Synthetic small-integer circuits, not GPT-2. Fixed total outputs=batch; single-row vectors=batch, shared16-row vectors=batch/16. Source and consumed output checked exactly.",
  budget: "Correctness evaluations have a45s deadline and each configuration has a180s budget; each complete timing configuration has a90s deadline. Failures preserved; timing requires exact passed font hashes.",
  sharedCorrectness: "After the original512-vector shared gate exceeded180s with zero mismatches, the repaired gate uses64 vectors:20 extrema/cancellation/carry cases,12 spread coordinate probes,32 seeded random cases. Single-row arithmetic gates remain unchanged; every timed output is also checked.",
} };
function rng(seed) { let s = seed >>> 0; return () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return s >>> 0; }; }
const oracle = (input, weights) => 2 * input.reduce((s, x, i) => s + x * weights[i], 0) + 1;
function casesFor(n, exhaustive) {
  if (n === 4 && exhaustive) return Array.from({ length: 65536 }, (_, code) => [0, 4, 8, 12].map(shift => (code >>> shift & 15) - 8));
  const weights = Array.from({ length: n }, (_, i) => [3, -2, 5, 1][i % 4]);
  const cases = [-8, -7, -1, 0, 1, 6, 7].map(x => Array(n).fill(x));
  cases.push(weights.map(w => w > 0 ? -8 : 7), weights.map(w => w > 0 ? 7 : -8), weights.map((_, i) => [2, 3, 0, 0][i % 4]), weights.map((_, i) => [-2, -3, 0, 0][i % 4]));
  // Explicit reachable boundaries of the nonnegative internal sum P.
  const order = weights.map((_, i) => i).sort((a, b) => Math.abs(weights[b]) - Math.abs(weights[a]));
  for (const target of [15, 16, 17, 31, 32, 33, 255, 256, 257, 4095, 4096, 4097, 16383, 16384, 16385]) {
    let remaining = target; const input = weights.map(w => w > 0 ? -8 : 7);
    for (const i of order) { const steps = Math.min(15, Math.floor(remaining / Math.abs(weights[i]))); input[i] += weights[i] > 0 ? steps : -steps; remaining -= steps * Math.abs(weights[i]); }
    if (!remaining) cases.push(input);
  }
  for (let i = 0; i < n; i++) for (const x of [-8, -1, 1, 7]) { const v = Array(n).fill(0); v[i] = x; cases.push(v); }
  const random = rng(0x91a30 ^ n);
  for (let i = 0; i < 1024; i++) cases.push(Array.from({ length: n }, () => random() % 16 - 8));
  return cases;
}
async function bounded(promise, label, milliseconds = 45000) { let timer; try { return await Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(`${label}: exceeded${milliseconds}ms deadline`)), milliseconds); })]); } finally { clearTimeout(timer); } }
async function save() { await fs.writeFile(destination, JSON.stringify(report, null, 2) + "\n"); }
const configs = [];
for (const n of widths) {
  const candidates = reference.variants.filter(v => v.width === n && (!selected.length || selected.includes(v.id)));
  if (!candidates.length) { report.skipped.push({ width: n, reason: "No selected candidate built" }); continue; }
  const fonts = candidates.map(v => ({ ...v, kind: "gsub", file: path.join(out, v.fontFile) }));
  const old = retained.variants.find(v => v.width === n && v.topology === "sequential");
  if (old) fonts.unshift({ ...old, id: `retained-w${n}`, kind: "gsub", file: path.join(root, "experiments/gsub-weighted-sum-probe", old.fontFile) });
  else report.skipped.push({ width: n, backend: "retained", reason: "Position-specific baseline absent at this width; no extrapolated timing" });
  const global = n <= 64 ? reusable.variants.find(v => v.width === n) : null;
  if (global) fonts.splice(old ? 1 : 0, 0, { ...global, id: `global-reuse-w${n}`, kind: "gsub", file: path.join(root, "experiments/gsub-reusable-digits", global.fontFile) });
  const staticFont = staticReference.variants.find(v => v.width === n);
  if (staticFont) fonts.push({ ...staticFont, kind: "static", file: path.join(out, staticFont.fontFile) });
  const hm = hvar.matrices.find(m => m.width === n);
  if (!hm) throw new Error(`Missing HVAR control for N${n}`);
  const hv = hm.hvar;
  fonts.push({ id: `hvar-w${n}`, kind: "hvar", width: n, weights: hm.weights[0], fontFamily: hv.fontFamily, file: path.isAbsolute(hv.fontFile) ? hv.fontFile : path.join(out, hv.fontFile), features: [], codepoints: hv.codepoints, axes: hv.axes, nonceCodepoint: hv.nonceCodepoint, nonces: hv.nonces, output: { offset: hv.outputOffset, unitsPerEm: 1024, fontSize: 1024 } });
  fonts.push({ id: `css-w${n}`, kind: "css", width: n, weights: candidates[0].weights });
  for (const f of fonts) {
    if (f.weights.length !== n || f.weights.some((w, i) => w !== [3, -2, 5, 1][i % 4])) throw new Error(`Unexpected row weights ${f.id}`);
    if (f.file) report.fontSha256[f.id] = sha(await fs.readFile(f.file));
  }
  configs.push({ n, fonts, m: 1, vectors: mode === "correctness" ? 256 : batch });
  if (n === 64) configs.push({ n, fonts, m: 16, vectors: batch / 16 });
}
if (!configs.length) throw new Error("No configurations selected");
let activeCss = "", files = new Map();
const server = http.createServer(async (request, response) => {
  const url = new URL(request.url, "http://localhost");
  if (url.pathname === "/page") { response.writeHead(200, { "content-type": "text/html", "cache-control": "no-store", "content-security-policy": "script-src 'none';object-src 'none'" }).end(`<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/style${url.search}"><main id="fixtures"></main>`); return; }
  if (url.pathname === "/style") { response.writeHead(200, { "content-type": "text/css", "cache-control": "no-store" }).end(activeCss); return; }
  if (url.pathname === "/favicon.ico") { response.writeHead(204).end(); return; }
  const file = files.get(url.pathname); if (!file) { response.writeHead(404).end(); return; }
  try { const bytes = await fs.readFile(file); response.writeHead(200, { "content-type": "font/woff2" }).end(bytes); } catch { response.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
function css(config) {
  const { n, fonts, m } = config, weights = fonts[0].weights;
  const offset = 64 + 3 * (2 * 8 * weights.reduce((s, w) => s + Math.abs(w), 0) + 1);
  const rules = ["body{margin:0}.group{position:relative;contain:layout}.vector{display:inline-block;position:relative;font-size:1024px;font-kerning:none;line-height:1px;height:1px;vertical-align:top;white-space:nowrap}.item{position:relative;display:inline-block;width:1px;height:1px;vertical-align:top}.source{display:inline-block;font-size:inherit;font-kerning:inherit;line-height:1;height:1px;white-space:pre}.receiver{position:absolute;left:0;top:0;container-type:inline-size}.decoded{position:absolute;height:1px}", '@property --nonce{syntax:"<integer>";inherits:true;initial-value:0}@property --y{syntax:"<number>";inherits:false;initial-value:-99999}@property --sum{syntax:"<number>";inherits:false;initial-value:-99999}', `.decoded,.css .source{width:calc((${offset} + 3 * var(--y))*1px)}`];
  for (let i = 0; i < n; i++) rules.push(`@property --x-${i}{syntax:"<integer>";inherits:true;initial-value:0}`);
  files = new Map();
  for (let b = 0; b < fonts.length; b++) {
    const f = fonts[b], prefix = `#b${b}`;
    if (f.kind === "css") { rules.push(`${prefix} .source{--sum:calc(${weights.map((w, i) => `(${w} * var(--x-${i}))`).join(" + ")});--y:calc(2 * var(--sum) + 1)}`); continue; }
    files.set(`/font${b}`, f.file);
    rules.push(`@font-face{font-family:F${b};src:url("/font${b}")}${prefix} .vector{font-family:F${b};${f.kind === "hvar" ? `font-variation-settings:${f.axes.map((tag, i) => `"${tag}" var(--x-${i})`).join(",")}` : `font-feature-settings:${f.features.map(tag => `"${tag}" 1`).join(",")}`}}`);
    rules.push(`${prefix} .decoded{--y:calc(100cqw / 1px - ${f.output.offset})}`);
    rules.push(`@counter-style nonce${b}{system:fixed 0;symbols:${Array.from({ length: f.nonces }, (_, j) => `"\\${(f.nonceCodepoint + j).toString(16)}"`).join(" ")};suffix:""}`);
    if (f.kind === "gsub" || f.kind === "static") for (let i = 0; i < n; i++) rules.push(`@counter-style x${b}i${i}{system:fixed 0;symbols:${Array.from({ length: 16 }, (_, j) => `"\\${(f.inputCodepoints[i] + j).toString(16)}"`).join(" ")};suffix:""}`);
    for (let r = 0; r < m; r++) {
      const resets = [`nc calc(mod(var(--nonce) + ${r},${f.nonces}))`], text = [`counter(nc,nonce${b})`];
      if (f.kind === "gsub" || f.kind === "static") for (let i = 0; i < n; i++) { resets.push(`i${i} calc(var(--x-${i}) + 8)`); text.push(`counter(i${i},x${b}i${i})`); }
      else text.push(`"\\${f.codepoints[r].toString(16)}"`);
      rules.push(`${prefix} .r${r} .source::before{counter-reset:${resets.join(" ")};content:${text.join(" ")}}`);
    }
  }
  return { rules: rules.join("\n"), offset };
}
async function setup(page, config, label) {
  const c = css(config); activeCss = c.rules;
  await page.goto(`http://127.0.0.1:${server.address().port}/page?${encodeURIComponent(label)}`, { waitUntil: "load" });
  await bounded(page.evaluate(async config => {
    const loads = await Promise.allSettled(config.fonts.map((f, b) => f.kind === "css" ? null : document.fonts.load(`1024px F${b}`, String.fromCodePoint(f.kind === "hvar" ? f.codepoints[0] : f.inputCodepoints[0]))));
    const failed = loads.flatMap((load, i) => load.status === "rejected" ? [`${config.fonts[i].id}: ${String(load.reason)}`] : []);
    if (failed.length) throw new Error(`Font loading failed: ${failed.join("; ")}`);
    await document.fonts.ready;
    const fixtures = document.querySelector("#fixtures");
    config.fonts.forEach((f, b) => {
      const group = document.createElement("div"); group.className = `group ${f.kind}`; group.id = `b${b}`;
      for (let v = 0; v < config.vectors; v++) {
        const parent = document.createElement("div"); parent.className = "vector";
        for (let r = 0; r < config.m; r++) {
          const item = document.createElement("div"); item.className = `item r${r}`;
          const source = document.createElement("span"); source.className = "source"; item.append(source);
          if (f.kind !== "css") { source.style.anchorName = `--a${b}-${v}-${r}`; const receiver = document.createElement("div"); receiver.className = "receiver"; receiver.style.width = `anchor-size(--a${b}-${v}-${r} inline)`; const decoded = document.createElement("div"); decoded.className = "decoded"; receiver.append(decoded); item.append(receiver); }
          parent.append(item);
        }
        group.append(parent);
      }
      fixtures.append(group);
    });
  }, config), `setup ${label}`);
  const structure = await page.evaluate(() => ({ scripts: document.scripts.length, nodes: [...document.querySelectorAll(".group")].map(node => node.querySelectorAll("*").length) }));
  if (structure.scripts) throw new Error("Unexpected page script");
  return { offset: c.offset, structure };
}
async function observe(page, config, inputs, nonce = 0) {
  return bounded(page.evaluate(({ config, inputs, nonce }) => {
    const result = [];
    config.fonts.forEach((f, b) => {
      const parents = [...document.querySelectorAll(`#b${b} .vector`)];
      inputs.forEach((input, v) => { input.forEach((x, i) => parents[v].style.setProperty(`--x-${i}`, x)); parents[v].style.setProperty("--nonce", nonce); });
      const outputs = [...document.querySelectorAll(`#b${b} ${f.kind === "css" ? ".source" : ".decoded"}`)], sources = [...document.querySelectorAll(`#b${b} .source`)];
      result.push(outputs.slice(0, inputs.length * config.m).map((node, i) => ({ width: node.getBoundingClientRect().width, y: Number(getComputedStyle(node).getPropertyValue("--y")), source: sources[i].getBoundingClientRect().width })));
    });
    return result;
  }, { config, inputs, nonce }), `observe N${config.n}`);
}
function check(config, actual, inputs, offset, records) {
  config.fonts.forEach((f, b) => {
    const record = records[b]; record.vectors += inputs.length;
    for (let v = 0; v < inputs.length; v++) for (let r = 0; r < config.m; r++) {
      const expected = oracle(inputs[v], f.weights), got = actual[b][v * config.m + r]; record.outputChecks++;
      if (got.y !== expected || got.width !== offset + 3 * expected || (f.kind !== "css" && got.source !== f.output.offset + expected)) {
        record.mismatches++; if (record.failures.length < 8) record.failures.push({ input: inputs[v], row: r, expected, got, expectedConsumer: offset + 3 * expected, expectedSource: f.output?.offset + expected });
      }
    }
  });
}
let browser;
try {
  if (mode === "timing") {
    const gates = await Promise.all(arg("--correctness-reports", "results-correctness.json").split(",").map(async name => JSON.parse(await fs.readFile(path.resolve(out, name), "utf8"))));
    for (const config of configs) for (const f of config.fonts) if (!gates.some(g => g.passed && g.mode === "correctness" && (f.kind === "css" || g.fontSha256[f.id] === report.fontSha256[f.id]) && g.correctness.some(c => c.id === f.id && c.m === config.m && c.passed))) throw new Error(`Missing passed exact-font gate for ${f.id},M${config.m}`);
    report.correctnessGateFiles = arg("--correctness-reports", "results-correctness.json").split(",");
  }
  for (let repetition = 0; repetition < (mode === "timing" ? 3 : 1); repetition++) {
    browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
    report.browserVersion = await browser.version(); const page = await browser.newPage();
    page.on("pageerror", error => report.errors.push(String(error)));
    page.on("console", message => { if (message.type() === "error") (report.browserConsoleErrors ??= []).push(message.text()); else if (/font|OTS/i.test(message.text())) (report.browserFontMessages ??= []).push(message.text()); });
    const ordered = configs.slice(repetition % configs.length).concat(configs.slice(0, repetition % configs.length));
    for (const config of ordered) {
      const { offset, structure } = await setup(page, config, `${mode}-${repetition}-n${config.n}-m${config.m}`);
      const preInput = Array.from({ length: config.n }, (_, i) => (3 * i + 5) % 16 - 8);
      const precheck = await observe(page, config, [preInput]);
      const preRecords = config.fonts.map(f => ({ id: f.id, vectors: 0, outputChecks: 0, mismatches: 0, failures: [] })); check(config, precheck, [preInput], offset, preRecords);
      if (preRecords.some(r => r.mismatches)) { report.correctness.push(...preRecords.map(r => ({ ...r, n: config.n, m: config.m, passed: false, stage: "precheck" }))); throw new Error(`Fixed precheck failed N${config.n} M${config.m}`); }
      if (mode !== "timing") {
        let inputs = casesFor(config.n, mode === "correctness" && config.m === 1);
        if (mode === "smoke") inputs = inputs.slice(0, 64);
        if (config.m === 16) {
          const all = casesFor(config.n, false), randomStart = all.length - 1024;
          inputs = [...all.slice(0, 20), ...Array.from({ length: 12 }, (_, i) => all[20 + Math.floor(i * (randomStart - 21) / 11)]), ...all.slice(randomStart, randomStart + 32)];
        }
        const records = config.fonts.map(f => ({ id: f.id, kind: f.kind, n: config.n, m: config.m, vectors: 0, outputChecks: 0, mismatches: 0, failures: [], structure })); report.correctness.push(...records);
        const started = performance.now();
        for (let at = 0; at < inputs.length; at += config.vectors) {
          const part = inputs.slice(at, at + config.vectors); check(config, await observe(page, config, part, Math.floor(at / config.vectors) % 65), part, offset, records);
          if (records.some(r => r.mismatches)) break;
          if (performance.now() - started > 180000) throw new Error(`Correctness budget exceeded N${config.n} M${config.m}`);
          if (at % (config.m === 16 ? 16 : 8192) === 0) { console.log(JSON.stringify({ n: config.n, m: config.m, checked: at + part.length, total: inputs.length })); await save(); }
        }
        records.forEach(r => r.passed = !r.mismatches && r.vectors === inputs.length);
        await save(); if (records.some(r => !r.passed)) throw new Error(`Exactness failed N${config.n} M${config.m}`);
        const controls = await bounded(page.evaluate(config => {
          const controls = [];
          config.fonts.forEach((f, b) => {
            if (f.kind !== "gsub") return;
            const parent = document.querySelector(`#b${b} .vector`), source = parent.querySelector(".source");
            for (let i = 0; i < config.n; i++) parent.style.setProperty(`--x-${i}`, [7, -8, 7, 7][i % 4]);
            const intact = source.getBoundingClientRect().width;
            for (const tag of f.features) { parent.style.fontFeatureSettings = f.features.map(t => `"${t}" ${t === tag ? 0 : 1}`).join(","); controls.push({ id: f.id, m: config.m, feature: tag, intact, broken: source.getBoundingClientRect().width }); }
            parent.style.removeProperty("font-feature-settings");
          }); return controls;
        }, config), "controls");
        report.controls.push(...controls); if (controls.some(c => c.intact === c.broken)) throw new Error("A disabled stage did not affect output");
        console.log(JSON.stringify({ n: config.n, m: config.m, passed: true, vectors: inputs.length }));
      } else {
        const index = configs.indexOf(config), seed = (0x91fb73 ^ Math.imul(repetition + 1, 0x27d4eb2d) ^ Math.imul(index + 1, 0x9e3779b1)) >>> 0, random = rng(seed);
        const stimuli = Array.from({ length: 25 }, (_, round) => ({ nonce: round + 1, inputs: Array.from({ length: config.vectors }, () => Array.from({ length: config.n }, () => random() % 16 - 8)) }));
        const orders = Array.from({ length: 25 }, (_, round) => Array.from({ length: config.fonts.length }, (_, i) => (i + round + repetition + index) % config.fonts.length));
        const measured = await bounded(page.evaluate(({ config, stimuli, orders }) => {
          const nodes = config.fonts.map((f, b) => ({ parents: [...document.querySelectorAll(`#b${b} .vector`)], outputs: [...document.querySelectorAll(`#b${b} ${f.kind === "css" ? ".source" : ".decoded"}`)] }));
          const times = config.fonts.map(() => []), widths = config.fonts.map(() => []);
          for (let round = 0; round < stimuli.length; round++) for (const b of orders[round]) {
            const start = performance.now(); stimuli[round].inputs.forEach((input, v) => { input.forEach((x, i) => nodes[b].parents[v].style.setProperty(`--x-${i}`, x)); nodes[b].parents[v].style.setProperty("--nonce", stimuli[round].nonce); });
            widths[b].push(nodes[b].outputs.map(node => node.getBoundingClientRect().width)); times[b].push(performance.now() - start);
          } return { times, widths };
        }, { config, stimuli, orders }), `timing N${config.n} M${config.m}`, 90000);
        config.fonts.forEach((f, b) => {
          let mismatches = 0, checksum = 0;
          for (let round = 0; round < 25; round++) for (let v = 0; v < config.vectors; v++) for (let r = 0; r < config.m; r++) { const value = measured.widths[b][round][v * config.m + r]; checksum += value; if (value !== offset + 3 * oracle(stimuli[round].inputs[v], f.weights)) mismatches++; }
          const sorted = measured.times[b].slice(5).sort((a, b) => a - b), median = sorted[10];
          report.timings.push({ id: f.id, kind: f.kind, n: config.n, m: config.m, vectors: config.vectors, outputs: config.vectors * config.m, repetition, seed, medianMilliseconds: median, millisecondsPerVector: median / config.vectors, millisecondsPerOutput: median / (config.vectors * config.m), rawMilliseconds: measured.times[b], backendOrders: orders, backendIds: config.fonts.map(f => f.id), parentInputWrites: config.n * config.vectors, parentNonceWrites: config.vectors, observerReads: config.vectors * config.m, checkedOutputs: 25 * config.vectors * config.m, mismatches, checksum, structure });
          if (mismatches) throw new Error(`Timed mismatch ${f.id}`);
        });
        console.log(JSON.stringify({ repetition, n: config.n, m: config.m, results: report.timings.slice(-config.fonts.length).map(t => ({ id: t.id, milliseconds: t.medianMilliseconds })) }));
      }
      await save();
    }
    await browser.close(); browser = null;
  }
  report.passed = !report.errors.length && !report.browserConsoleErrors?.length && report.correctness.every(r => r.passed) && report.timings.every(t => !t.mismatches);
} catch (error) { report.errors.push(String(error.stack ?? error)); report.passed = false; }
finally { report.completedAt = new Date().toISOString(); await save(); await browser?.close(); await new Promise(resolve => server.close(resolve)); }
console.log(JSON.stringify({ passed: report.passed, errors: report.errors, report: destination }));
if (!report.passed) process.exitCode = 1;
