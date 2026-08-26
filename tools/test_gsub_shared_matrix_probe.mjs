#!/usr/bin/env node
/** Three native backends receive one set of inherited inputs per vector. */
import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import os from "node:os";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const out = path.join(root, "experiments/gsub-shared-matrix-probe");
const args = process.argv.slice(2), option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const mode = option("--mode", "correctness");
if (!["correctness", "smoke", "timing"].includes(mode)) throw new Error("Expected --mode correctness|smoke|timing");
const selectedWidths = option("--widths", "4,16,64").split(",").map(Number);
const outputCounts = option("--outputs", "1,4,16").split(",").map(Number);
const reps = Number(option("--repetitions", "3"));
const correctnessVectors = Number(option("--correctness-vectors", "64"));
const destination = path.resolve(out, option("--output", `results-${mode}.json`));
const reference = JSON.parse(await fs.readFile(path.join(out, "reference.json"), "utf8"));
const matrices = reference.matrices.filter(m => selectedWidths.includes(m.width));
if (matrices.length !== selectedWidths.length) throw new Error("Not all requested matrices have been built");
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
const report = {
  startedAt: new Date().toISOString(), mode, reference,
  harnessSha256: hash(await fs.readFile(fileURLToPath(import.meta.url))),
  environment: { node: process.version, cpu: os.cpus()[0]?.model, platform: process.platform, arch: process.arch },
  methodology: {
    inputs: "Every vector parent receives N signed raw input properties and one nonce once; all M outputs inherit them. Same parent writes in every backend.",
    gsub: "Separate fixed font and shaping run per row. Shared inherited inputs do not imply shared multiplication or reduction work.",
    hvar: "One N-axis font contains all output glyphs. A single parent font-variation-settings value is inherited by every output.",
    css: "Each row directly computes its weighted sum and affine continuation on the final width element; no unnecessary font readback.",
    observer: "Font advances decode to CSS numbers through anchor-size/container units. Every backend is consumed by width=commonOffset+3*result. The external oracle never supplies answers to the browser.",
    batches: "Fixed-output cases hold256 outputs using256/M vectors. One-vector cases have M total outputs. Time per vector/output is reported, without treating those different workloads as equal latency.",
    timing: "Three fresh browser repetitions, distinct seed per configuration and repetition, five warmups plus20 reported samples; six backend permutations balanced over the three repetitions. Configuration order rotates by one third per repetition. One-vector samples aggregate32 changing updates on the same DOM, forcing each output after every update; reported latency divides elapsed sample time by32. Fixed-output samples have one update.",
    timedRegion: "Parent property writes through forced final width reads. Stimulus generation, CDP transport, numerical oracle and font loading excluded; external JavaScript mutation/read overhead included.",
    nonce: "Changes each update and cycles through65 glyphs. The exact number of unique input+nonce states is recorded; this does not disable all font/browser caches. Per-configuration seeds differ to avoid replaying previous sample sequences.",
    scope: "Synthetic distinct dense integer weight rows, not a trained model. Aggregated one-vector measurements estimate steady repeated-update latency, not isolated cold latency.",
  },
  fontSha256: {}, correctness: [], controls: [], timings: [], errors: [],
};
function rng(seed) { let s = seed >>> 0; return () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return s >>> 0; }; }
function oracle(input, weights) { return 2 * input.reduce((sum, value, i) => sum + value * weights[i], 0) + 1; }
function stats(values) { const a = [...values].sort((x, y) => x - y); return { samples: a.length, medianMilliseconds: a[Math.floor(a.length / 2)], p95Milliseconds: a[Math.floor((a.length - 1) * .95)], minMilliseconds: a[0], maxMilliseconds: a.at(-1) }; }
function vectorsFor(matrix, exhaustive) {
  const n = matrix.width;
  if (n === 4 && exhaustive) return Array.from({ length: 65536 }, (_, code) => [0, 4, 8, 12].map(shift => ((code >>> shift) & 15) - 8));
  const vectors = [-8, -7, -1, 0, 1, 6, 7].map(value => Array(n).fill(value));
  for (const row of matrix.weights) { vectors.push(row.map(w => w > 0 ? 7 : -8)); vectors.push(row.map(w => w > 0 ? -8 : 7)); }
  for (let coordinate = 0; coordinate < n; coordinate++) for (const value of [-8, -1, 1, 7]) { const vector = Array(n).fill(0); vector[coordinate] = value; vectors.push(vector); }
  vectors.push(Array.from({ length: n }, (_, i) => i % 2 ? 7 : -8));
  const random = rng(0x1583c7 ^ n);
  for (let i = 0; i < 1024; i++) vectors.push(Array.from({ length: n }, () => random() % 16 - 8));
  return vectors;
}
function buildCss(matrix) {
  const n = matrix.width;
  const consumerOffset = 3 * (2 * 8 * Math.max(...matrix.weights.map(row => row.reduce((s, w) => s + Math.abs(w), 0))) + 1) + 64;
  const lines = [
    "body{margin:0}.group{position:relative;contain:layout}.vector{position:relative;display:inline-block;vertical-align:top;white-space:nowrap;font-size:1024px;font-kerning:none;line-height:1px;height:1px}.item{position:relative;display:inline-block;width:1px;height:1px;vertical-align:top}.source{display:inline-block;white-space:pre;font-size:inherit;font-kerning:inherit;line-height:1;height:1px}.receiver{position:absolute;left:0;top:0;container-type:inline-size}.decoded{position:absolute;left:0;top:0;height:1px}",
    '@property --nonce{syntax:"<integer>";inherits:true;initial-value:0}@property --sum{syntax:"<number>";inherits:false;initial-value:-99999}@property --y{syntax:"<number>";inherits:false;initial-value:-99999}',
  ];
  const counters = ["nonce var(--nonce)"], content = ["counter(nonce,gsubnonce)"];
  for (let i = 0; i < n; i++) {
    lines.push(`@property --x-${i}{syntax:"<integer>";inherits:true;initial-value:0}`);
    const cp = matrix.gsub[0].inputCodepoints[i];
    lines.push(`@counter-style input${i}{system:fixed 0;symbols:${Array.from({ length: 16 }, (_, v) => `"\\${(cp + v).toString(16)}"`).join(" ")};suffix:""}`);
    counters.push(`x${i} calc(var(--x-${i}) + 8)`); content.push(`counter(x${i},input${i})`);
  }
  for (const [name, cp] of [["gsubnonce", matrix.gsub[0].nonceCodepoint], ["hvarnonce", matrix.hvar.nonceCodepoint]]) {
    lines.push(`@counter-style ${name}{system:fixed 0;symbols:${Array.from({ length: 65 }, (_, v) => `"\\${(cp + v).toString(16)}"`).join(" ")};suffix:""}`);
  }
  lines.push(`.gsub .source::before{counter-reset:${counters.join(" ")};content:${content.join(" ")}}`);
  lines.push(`.gsub .vector{font-feature-settings:${matrix.gsub[0].features.map(tag => `"${tag}" 1`).join(",")}}`);
  lines.push(`@font-face{font-family:"${matrix.hvar.fontFamily}";src:url("/${matrix.hvar.fontFile}")}`);
  lines.push(`.hvar .vector{font-family:"${matrix.hvar.fontFamily}";font-variation-settings:${matrix.hvar.axes.map((tag, i) => `"${tag}" var(--x-${i})`).join(",")}}`);
  lines.push(`.decoded,.css .source{width:calc((${consumerOffset} + 3 * var(--y))*1px)}`);
  for (let r = 0; r < matrix.outputRows; r++) {
    const font = matrix.gsub[r], weighted = matrix.weights[r].map((w, i) => `(${w} * var(--x-${i}))`).join(" + ");
    lines.push(`@font-face{font-family:"${font.fontFamily}";src:url("/${font.fontFile}")}`);
    lines.push(`.gsub .row${r} .source{font-family:"${font.fontFamily}"}.gsub .row${r} .decoded{--y:calc(100cqw / 1px - ${font.outputOffset})}`);
    lines.push(`.hvar .row${r} .source::before{counter-reset:nonce var(--nonce);content:counter(nonce,hvarnonce) "\\${matrix.hvar.codepoints[r].toString(16)}"}`);
    lines.push(`.hvar .row${r} .decoded{--y:calc(100cqw / 1px - ${matrix.hvar.outputOffset})}`);
    lines.push(`.css .row${r} .source{--sum:calc(${weighted});--y:calc(2 * var(--sum) + 1)}`);
  }
  return { css: lines.join("\n"), consumerOffset };
}
let activeCss = "";
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  if (url.pathname === "/harness.html") { res.writeHead(200, { "content-type": "text/html", "cache-control": "no-store", "content-security-policy": "script-src 'none';object-src 'none'" }).end(`<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/harness.css${url.search}"><title>Shared vector matrix experiment</title><main id="fixtures"></main>`); return; }
  if (url.pathname === "/harness.css") { res.writeHead(200, { "content-type": "text/css", "cache-control": "no-store" }).end(activeCss); return; }
  if (url.pathname === "/favicon.ico") { res.writeHead(204).end(); return; }
  const file = path.resolve(out, `.${url.pathname}`);
  if (!file.startsWith(out + path.sep)) { res.writeHead(403).end(); return; }
  try { const bytes = await fs.readFile(file); res.writeHead(200, { "content-type": "font/woff2" }).end(bytes); }
  catch { res.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
let browser;
async function save() { await fs.writeFile(destination, JSON.stringify(report, null, 2) + "\n"); }
async function setup(page, matrix, m, vectorCount, key) {
  const { css, consumerOffset } = buildCss(matrix); activeCss = css;
  await page.goto(`http://127.0.0.1:${server.address().port}/harness.html?${encodeURIComponent(key)}`, { waitUntil: "load" });
  await page.evaluate(async ({ matrix, m, vectorCount }) => {
    await Promise.all([document.fonts.load(`1024px "${matrix.hvar.fontFamily}"`, String.fromCodePoint(matrix.hvar.codepoints[0])), ...matrix.gsub.slice(0, m).map(font => document.fonts.load(`1024px "${font.fontFamily}"`, String.fromCodePoint(font.inputCodepoints[0])))]);
    await document.fonts.ready;
    const fixtures = document.querySelector("#fixtures");
    for (const backend of ["gsub", "hvar", "css"]) {
      const group = document.createElement("div"); group.className = `group ${backend}`; group.id = backend;
      for (let v = 0; v < vectorCount; v++) {
        const vector = document.createElement("div"); vector.className = "vector";
        for (let r = 0; r < m; r++) {
          const item = document.createElement("div"); item.className = `item row${r}`;
          const source = document.createElement("span"); source.className = "source";
          item.append(source);
          if (backend !== "css") {
            source.style.anchorName = `--a-${backend}-${v}-${r}`;
            const receiver = document.createElement("div"); receiver.className = "receiver"; receiver.style.width = `anchor-size(--a-${backend}-${v}-${r} inline)`;
            const decoded = document.createElement("div"); decoded.className = "decoded"; receiver.append(decoded); item.append(receiver);
          }
          vector.append(item);
        }
        group.append(vector);
      }
      fixtures.append(group);
    }
  }, { matrix, m, vectorCount });
  const structure = await page.evaluate(() => ({ runtimeScripts: document.scripts.length, domNodes: Object.fromEntries(["gsub", "hvar", "css"].map(mode => [mode, document.querySelectorAll(`#${mode} *`).length])), vectors: document.querySelectorAll("#gsub .vector").length, hvarSettingsOwners: document.querySelectorAll("#hvar .vector").length, outputs: document.querySelectorAll("#gsub .source").length }));
  if (structure.runtimeScripts !== 0 || structure.vectors !== vectorCount || structure.outputs !== m * vectorCount) throw new Error("Unexpected page structure");
  const precheckInput = Array.from({ length: matrix.width }, (_, i) => (3 * i + 5) % 16 - 8);
  const precheck = await page.evaluate(input => {
    const result = {};
    for (const backend of ["gsub", "hvar", "css"]) {
      for (const parent of document.querySelectorAll(`#${backend} .vector`)) { input.forEach((x, i) => parent.style.setProperty(`--x-${i}`, x)); parent.style.setProperty("--nonce", 0); }
      result[backend] = [...document.querySelectorAll(`#${backend} ${backend === "css" ? ".source" : ".decoded"}`)].map(node => node.getBoundingClientRect().width);
    }
    return result;
  }, precheckInput);
  for (const backend of ["gsub", "hvar", "css"]) for (let v = 0; v < vectorCount; v++) for (let r = 0; r < m; r++) if (precheck[backend][v * m + r] !== consumerOffset + 3 * oracle(precheckInput, matrix.weights[r])) throw new Error(`Small fixed precheck failed: ${key} ${backend} row${r}`);
  structure.fixedPrecheckOutputs = 3 * vectorCount * m;
  return { consumerOffset, structure };
}
async function correctness(page, matrix, exhaustive) {
  const m = matrix.outputRows, vectorCount = correctnessVectors;
  const { consumerOffset, structure } = await setup(page, matrix, m, vectorCount, `correctness-${matrix.width}`);
  const all = vectorsFor(matrix, exhaustive), vectors = mode === "smoke" ? all.slice(0, 128) : all;
  const checks = Object.fromEntries(["gsub", "hvar", "css"].map(backend => [backend, { width: matrix.width, outputRows: m, backend, vectors: 0, outputChecks: 0, failures: [], mismatches: 0, structure }]));
  report.correctness.push(...Object.values(checks));
  for (let start = 0; start < vectors.length; start += vectorCount) {
    const inputs = vectors.slice(start, start + vectorCount);
    const actual = await page.evaluate(({ inputs, m }) => {
      const result = {};
      for (const backend of ["gsub", "hvar", "css"]) {
        const parents = [...document.querySelectorAll(`#${backend} .vector`)];
        inputs.forEach((input, v) => { input.forEach((x, i) => parents[v].style.setProperty(`--x-${i}`, x)); parents[v].style.setProperty("--nonce", 0); });
        const outputs = [...document.querySelectorAll(`#${backend} ${backend === "css" ? ".source" : ".decoded"}`)];
        const sources = [...document.querySelectorAll(`#${backend} .source`)];
        result[backend] = outputs.slice(0, inputs.length * m).map((node, i) => ({ width: node.getBoundingClientRect().width, y: Number(getComputedStyle(node).getPropertyValue("--y")), sourceWidth: sources[i].getBoundingClientRect().width }));
      }
      return result;
    }, { inputs, m });
    for (const backend of ["gsub", "hvar", "css"]) {
      const check = checks[backend]; check.vectors += inputs.length;
      for (let v = 0; v < inputs.length; v++) for (let r = 0; r < m; r++) {
        const y = oracle(inputs[v], matrix.weights[r]), got = actual[backend][v * m + r];
        const expectedSource = backend === "gsub" ? matrix.gsub[r].outputOffset + y : matrix.hvar.outputOffset + y;
        check.outputChecks++;
        if (got.y !== y || got.width !== consumerOffset + 3 * y || (backend !== "css" && got.sourceWidth !== expectedSource)) {
          check.mismatches++; if (check.failures.length < 8) check.failures.push({ input: inputs[v], row: r, weights: matrix.weights[r], expectedY: y, expectedSource, expectedConsumer: consumerOffset + 3 * y, actual: got });
        }
      }
    }
    if (Object.values(checks).some(c => c.mismatches)) break;
    if (start % 8192 === 0) {
      report.progress = { width: matrix.width, checkedVectors: start + inputs.length, totalVectors: vectors.length, outputRows: m };
      console.log(JSON.stringify(report.progress)); await save();
    }
  }
  for (const check of Object.values(checks)) check.passed = !check.mismatches && check.vectors === vectors.length;
  await save();
  if (Object.values(checks).some(c => !c.passed)) throw new Error(`Matrix correctness failed at N${matrix.width}`);
  const controls = await page.evaluate(matrix => {
    const parent = document.querySelector("#gsub .vector");
    for (let i = 0; i < matrix.width; i++) parent.style.setProperty(`--x-${i}`, i % 2 ? -8 : 7);
    const sources = [...parent.querySelectorAll(".source")];
    const intact = sources.map(node => node.getBoundingClientRect().width), result = [];
    for (const feature of matrix.gsub[0].features) {
      parent.style.fontFeatureSettings = matrix.gsub[0].features.map(tag => `"${tag}" ${tag === feature ? 0 : 1}`).join(",");
      sources.forEach((node, row) => result.push({ width: matrix.width, row, disabledFeature: feature, intact: intact[row], broken: node.getBoundingClientRect().width }));
    }
    parent.style.removeProperty("font-feature-settings");
    return result;
  }, matrix);
  report.controls.push(...controls);
  if (controls.some(c => c.intact === c.broken)) throw new Error(`A disabled GSUB stage did not alter row output at N${matrix.width}`);
  console.log(JSON.stringify({ width: matrix.width, correctness: "passed", vectors: vectors.length, outputRows: m }));
}
const permutations = [["gsub", "hvar", "css"], ["gsub", "css", "hvar"], ["hvar", "gsub", "css"], ["hvar", "css", "gsub"], ["css", "gsub", "hvar"], ["css", "hvar", "gsub"]];
try {
  for (const matrix of matrices) {
    if (new Set(matrix.weights.map(row => row.join(","))).size !== matrix.outputRows || matrix.weights.some(row => row.length !== matrix.width || row.some(w => !Number.isInteger(w) || !w))) throw new Error("Weight row distinctness/nonzero check failed");
    for (const font of [...matrix.gsub, matrix.hvar]) {
      const actual = hash(await fs.readFile(path.join(out, font.fontFile)));
      if (actual !== font.fontSha256) throw new Error(`Font changed after manifest: ${font.fontFile}`);
      report.fontSha256[font.fontFile] = actual;
    }
  }
  if (mode === "timing") {
    const gate = JSON.parse(await fs.readFile(path.resolve(out, option("--correctness-report", "results-correctness.json")), "utf8"));
    if (!gate.passed || gate.mode !== "correctness" || Object.entries(report.fontSha256).some(([file, sha]) => gate.fontSha256[file] !== sha) || matrices.some(m => !["gsub", "hvar", "css"].every(backend => gate.correctness.some(c => c.width === m.width && c.backend === backend && c.passed && c.outputRows >= Math.max(...outputCounts))))) throw new Error("Timing needs a full passed gate for these exact fonts and rows");
    report.correctnessGate = { completedAt: gate.completedAt, fontSha256: gate.fontSha256 };
  }
  const configurations = matrices.flatMap(matrix => outputCounts.flatMap(m => ["fixed-256-outputs", "one-vector"].map(batchKind => ({ matrix, m, batchKind, vectorCount: batchKind === "one-vector" ? 1 : 256 / m }))));
  for (let repetition = 0; repetition < (mode === "timing" ? reps : 1); repetition++) {
    browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
    report.browserVersion = await browser.version();
    const page = await browser.newPage({ viewport: { width: 1100, height: 700 } });
    page.on("pageerror", e => report.errors.push(String(e)));
    page.on("console", msg => { if (msg.type() === "error") (report.browserConsoleErrors ??= []).push(msg.text()); });
    if (mode !== "timing") { for (const matrix of matrices) await correctness(page, matrix, mode === "correctness"); }
    else {
      const shift = Math.floor(configurations.length / 3) * repetition;
      const ordered = configurations.slice(shift).concat(configurations.slice(0, shift));
      for (const config of ordered) {
        const { matrix, m, batchKind, vectorCount } = config, configIndex = configurations.indexOf(config);
        if (!Number.isInteger(vectorCount) || m > matrix.outputRows) throw new Error("Invalid output/vector count");
        const key = `rep${repetition}-n${matrix.width}-m${m}-${batchKind}`;
        const { consumerOffset, structure } = await setup(page, matrix, m, vectorCount, key);
        const seed = (0x28b513 ^ Math.imul(repetition + 1, 0x27d4eb2d) ^ Math.imul(configIndex + 1, 0x9e3779b1)) >>> 0;
        const random = rng(seed);
        const updatesPerSample = batchKind === "one-vector" ? 32 : 1;
        const stimuli = Array.from({ length: 25 }, (_, round) => Array.from({ length: updatesPerSample }, (_, update) => ({ nonce: (round * updatesPerSample + update + 1) % 65, inputs: Array.from({ length: vectorCount }, () => Array.from({ length: matrix.width }, () => random() % 16 - 8)) })));
        const orders = Array.from({ length: 25 }, (_, round) => permutations[(round + 2 * repetition + configIndex) % permutations.length]);
        const measured = await page.evaluate(({ stimuli, orders }) => {
          const nodes = Object.fromEntries(["gsub", "hvar", "css"].map(backend => [backend, { parents: [...document.querySelectorAll(`#${backend} .vector`)], outputs: [...document.querySelectorAll(`#${backend} ${backend === "css" ? ".source" : ".decoded"}`)] }]));
          const times = { gsub: [], hvar: [], css: [] }, widths = { gsub: [], hvar: [], css: [] };
          for (let round = 0; round < stimuli.length; round++) for (const backend of orders[round]) {
            const start = performance.now();
            const sample = [];
            for (const update of stimuli[round]) {
              update.inputs.forEach((input, v) => { const parent = nodes[backend].parents[v]; input.forEach((x, i) => parent.style.setProperty(`--x-${i}`, x)); parent.style.setProperty("--nonce", update.nonce); });
              sample.push(nodes[backend].outputs.map(node => node.getBoundingClientRect().width));
            }
            widths[backend].push(sample);
            times[backend].push(performance.now() - start);
          }
          return { times, widths };
        }, { stimuli, orders });
        const uniqueInputNonceStates = new Set(stimuli.flatMap(sample => sample.flatMap(update => update.inputs.map(input => `${update.nonce}:${input.join(",")}`)))).size;
        for (const backend of ["gsub", "hvar", "css"]) {
          let mismatches = 0, checksum = 0;
          for (let round = 0; round < 25; round++) for (let update = 0; update < updatesPerSample; update++) for (let v = 0; v < vectorCount; v++) for (let r = 0; r < m; r++) {
            const observed = measured.widths[backend][round][update][v * m + r], expected = consumerOffset + 3 * oracle(stimuli[round][update].inputs[v], matrix.weights[r]); checksum += observed;
            if (observed !== expected) mismatches++;
          }
          const perUpdateMilliseconds = measured.times[backend].map(time => time / updatesPerSample), summary = stats(perUpdateMilliseconds.slice(5));
          report.timings.push({ repetition, configurationOrderIndex: ordered.indexOf(config), configIndex, width: matrix.width, outputsPerVector: m, vectorCount, totalOutputs: vectorCount * m, batchKind, backend, seed, structure, updatesPerSample, uniqueInputNonceStates, parentInputWritesPerUpdate: vectorCount * matrix.width, parentNonceWritesPerUpdate: vectorCount, observerReadsPerUpdate: vectorCount * m, ...summary, medianMillisecondsPerVector: summary.medianMilliseconds / vectorCount, medianMillisecondsPerOutput: summary.medianMilliseconds / (vectorCount * m), mismatches, checksum, checkedOutputs: 25 * updatesPerSample * vectorCount * m, rawMilliseconds: perUpdateMilliseconds, rawAggregateSampleMilliseconds: measured.times[backend], backendOrders: orders });
          if (mismatches) throw new Error(`Timed output mismatch in ${key} ${backend}`);
        }
        console.log(JSON.stringify({ repetition, width: matrix.width, m, batchKind, vectorCount, times: report.timings.slice(-3).map(t => ({ backend: t.backend, medianMilliseconds: t.medianMilliseconds })) }));
        await save();
      }
    }
    await browser.close(); browser = null;
  }
  if (mode === "timing") {
    const groups = new Map();
    for (const row of report.timings) {
      const key = [row.width, row.outputsPerVector, row.batchKind, row.backend].join(":");
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(row);
    }
    report.summary = [...groups.values()].map(rows => {
      const first = rows[0], medians = rows.map(row => row.medianMilliseconds), sorted = [...medians].sort((a, b) => a - b);
      return { width: first.width, outputsPerVector: first.outputsPerVector, vectorCount: first.vectorCount, totalOutputs: first.totalOutputs, batchKind: first.batchKind, backend: first.backend, repetitions: rows.length, repetitionMediansMilliseconds: medians, medianOfRepetitionMediansMilliseconds: sorted[Math.floor(sorted.length / 2)], minimumRepetitionMedianMilliseconds: sorted[0], maximumRepetitionMedianMilliseconds: sorted.at(-1), medianMillisecondsPerVector: sorted[Math.floor(sorted.length / 2)] / first.vectorCount, medianMillisecondsPerOutput: sorted[Math.floor(sorted.length / 2)] / first.totalOutputs };
    });
  }
  report.passed = report.errors.length === 0 && !(report.browserConsoleErrors?.length) && report.correctness.every(c => c.passed) && report.timings.every(t => !t.mismatches);
} catch (error) { report.errors.push(String(error.stack ?? error)); report.passed = false; }
finally { report.completedAt = new Date().toISOString(); await save(); await browser?.close(); await new Promise(resolve => server.close(resolve)); }
console.log(JSON.stringify({ passed: report.passed, errors: report.errors, report: destination }));
if (!report.passed) process.exitCode = 1;
