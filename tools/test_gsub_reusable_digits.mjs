#!/usr/bin/env node
/** External test driver. The generated browser document contains no scripts. */
import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import os from "node:os";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const out = path.join(root, "experiments/gsub-reusable-digits");
const args = process.argv.slice(2);
const arg = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const seedBase = Number(arg("--seed", "13661381")) >>> 0;
const sampleCount = 25;
const warmupCount = 5;
const profileWarmups = Number(arg("--profile-warmups", "5"));
const profileRounds = Number(arg("--profile-rounds", "20"));
const phases = arg("--phases", "stable-nonce,unique-text").split(",");
if (phases.some(p => !["stable-nonce", "unique-text"].includes(p))) throw new Error("--phases accepts stable-nonce and/or unique-text");
const mode = arg("--mode", "correctness");
if (!["correctness", "timing", "smoke", "profile"].includes(mode)) throw new Error("--mode must be correctness, timing, smoke, or profile");
const batch = Number(arg("--batch", "256"));
if (!Number.isInteger(batch) || batch < 1 || batch > 1024) throw new Error("--batch must be in [1,1024]");
const selectedIds = arg("--variants", "").split(",").filter(Boolean);
const destination = path.resolve(out, arg("--output", `results-${mode}.json`));
const referenceFile = path.resolve(out, arg("--reference", "reference.json"));
const reference = JSON.parse(await fs.readFile(referenceFile, "utf8"));
const variants = reference.variants.filter(v => !selectedIds.length || selectedIds.includes(v.id));
if (args.includes("--reverse-variants")) variants.reverse();
if (!variants.length) throw new Error("No selected variants");
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
const report = {
  startedAt: new Date().toISOString(), mode, batch, seedBase, sampleCount, warmupCount, phases, reversedVariants: args.includes("--reverse-variants"), referenceFile, reference,
  harnessSha256: hash(await fs.readFile(fileURLToPath(import.meta.url))),
  environment: { node: process.version, cpu: os.cpus()[0]?.model, platform: process.platform, arch: process.arch },
  methodology: {
    formula: "S = sum_i (variant.weights[i] * x_i); y = 2*S + 1; x_i integers [-8,7]. Standard weights repeat [3,-2,5,1]; fanout effective weights [9,1,6,5].",
    oracle: "Independent arithmetic in external Node driver; browser receives only raw inputs and nonce, never an answer or product",
    nativePath: "CSS signed input properties -> CSS counters -> GSUB product/reduction/dependent/publish -> glyph advance -> CSS anchor-size/container units -> decoded numeric y -> width(consumerOffset + 3*y)",
    hvarControlPath: "For kind:hvar only: raw CSS input properties -> variable-font axes -> one HVAR advance for affine y (weights folded) -> same anchor/container reader and dependent width consumer. This control has no internal GSUB reduction or continuation.",
    directCssPath: "Same input properties -> direct CSS calc weighted sum and dependent expression -> width(consumerOffset + 3*y); no font/anchor/container return trip",
    timedRegion: "Raw input and nonce style writes through forced final dependent width reads, including JavaScript mutation/read loop overhead; stimulus generation, oracle, CDP transport and font loading excluded",
    order: "Alternates GSUB-first and direct-CSS-first each sample; 25 samples, first5 warmups excluded",
    cachePhases: "stable-nonce uses nonce0 while inputs change; unique-text changes a zero-advance nonce each round and uses a different deterministic input seed. The latter prevents identical full text reuse across rounds; duplicate vectors within a batch and other internal font caches remain possible. Seeds are equal across implementations at a given width/phase.",
    scope: "Synthetic signed integer weighted sums and affine continuation; not GPT-2 inference or a full model speedup",
  },
  fontSha256: {}, correctness: [], disabledStageControls: [], splitRunControls: [], markerControls: [], timings: [], profiles: [], errors: [],
};

function expected(input, weights) {
  const sum = input.reduce((s, x, i) => s + weights[i] * x, 0);
  return { sum, y: 2 * sum + 1 };
}
function rng(seed) {
  let state = seed >>> 0;
  return () => { state ^= state << 13; state ^= state >>> 17; state ^= state << 5; return state >>> 0; };
}
function casesFor(width, exhaustive, weights) {
  if (width === 4 && exhaustive) {
    return Array.from({ length: 65536 }, (_, code) => ({ category: "exhaustive", input: [0, 4, 8, 12].map(shift => ((code >>> shift) & 15) - 8) }));
  }
  const cases = [];
  const add = (category, input) => cases.push({ category, input });
  for (const value of [-8, -7, -1, 0, 1, 6, 7]) add("constant", Array(width).fill(value));
  add("minimum-sum", weights.map(w => w > 0 ? -8 : 7));
  add("maximum-sum", weights.map(w => w > 0 ? 7 : -8));
  add("alternating", weights.map((_, i) => i % 2 ? 7 : -8));
  add("cancellation", weights.map((_, i) => [2, 3, 0, 0][i % 4]));
  add("cancellation-negative", weights.map((_, i) => [-2, -3, 0, 0][i % 4]));
  // Every input is independently changed over its whole domain against zero.
  const coordinateValues = width >= 128 ? [-8, 7] : Array.from({ length: 16 }, (_, i) => i - 8);
  for (let i = 0; i < width; i++) for (const value of coordinateValues) {
    const input = Array(width).fill(0); input[i] = value; add("individual-coordinate", input);
  }
  const random = rng(0x6b91ef ^ width);
  const targets = new Set([-257, -256, -255, -17, -16, -15, -1, 0, 1, 15, 16, 17, 255, 256, 257]);
  if (width >= 128) {
    const offset = -weights.reduce((sum, w) => sum + Math.min(-8*w, 7*w), 0);
    for (const radixPower of [16, 256, 4096]) {
      const boundary = Math.round(offset / radixPower) * radixPower - offset;
      for (const delta of [-1, 0, 1]) targets.add(boundary + delta);
    }
  }
  for (let i = 0; i < (width >= 128 ? 256 : 4096); i++) {
    const input = Array.from({ length: width }, () => random() % 16 - 8);
    add("seeded-random", input);
    if (targets.has(expected(input, weights).sum)) { add("signed-sum-boundary", input); targets.delete(expected(input, weights).sum); }
  }
  // Construct reachable carry/borrow boundary sums using the weight-1 coordinate.
  for (const target of targets) {
    if (width >= 128) {
      const input = weights.map(w => w > 0 ? -8 : 7);
      let remainder = target - expected(input, weights).sum;
      if (remainder < 0) continue;
      const order = weights.map((w, i) => ({ i, magnitude: Math.abs(w) })).sort((a, b) => b.magnitude - a.magnitude);
      for (const { i, magnitude } of order) {
        const steps = Math.min(15, Math.floor(remainder / magnitude));
        input[i] += (weights[i] > 0 ? 1 : -1) * steps;
        remainder -= magnitude * steps;
      }
      if (remainder === 0) add("signed-sum-boundary", input);
      continue;
    }
    for (let attempt = 0; attempt < (width >= 128 ? 1024 : 16384); attempt++) {
      const input = Array.from({ length: width }, () => random() % 16 - 8);
      input[3] = 0;
      const need = (target - expected(input, weights).sum) / weights[3];
      if (Number.isInteger(need) && need >= -8 && need <= 7) { input[3] = need; add("signed-sum-boundary", input); break; }
    }
  }
  return cases;
}
function summarize(times) {
  const sorted = [...times].sort((a, b) => a - b);
  return { samples: times.length, medianMilliseconds: sorted[Math.floor(sorted.length / 2)], p95Milliseconds: sorted[Math.floor((sorted.length - 1) * .95)], minMilliseconds: sorted[0], maxMilliseconds: sorted.at(-1) };
}
function variantCss(v) {
  const family = v.fontFamily ?? `GSUBWeighted${v.id}`;
  const codepoints = v.inputCodepoints;
  const features = v.features.map(tag => `"${tag}" 1`).join(",");
  const styles = [
    `@font-face{font-family:"${family}";src:url("/${v.fontFile}")}`,
    `.source.gsub{font-family:"${family}";font-size:${v.output.fontSize}px;font-feature-settings:${features}}`,
  ];
  const counters = [`nonce var(--nonce)`], contents = ["counter(nonce,nc)"];
  for (let i = 0; i < v.width; i++) {
    styles.push(`@property --x-${i}{syntax:"<integer>";inherits:true;initial-value:0}`);
    if (v.kind !== "hvar") styles.push(`@counter-style x${i}{system:fixed 0;symbols:${Array.from({ length: 16 }, (_, x) => `"\\${(codepoints[i] + x).toString(16)}"`).join(" ")};suffix:""}`);
    counters.push(`x${i} calc(var(--x-${i}) + 8)`); contents.push(`counter(x${i},x${i})`);
  }
  styles.push(`@counter-style nc{system:fixed 0;symbols:${Array.from({ length: v.nonces }, (_, i) => `"\\${(v.nonceCodepoint + i).toString(16)}"`).join(" ")};suffix:""}`);
  if (v.kind === "hvar") {
    styles.push(`.source.gsub{font-variation-settings:${v.axes.map((axis, i) => `"${axis}" var(--x-${i})`).join(",")}}`);
    styles.push(`.source.gsub::before{counter-reset:nonce var(--nonce);content:counter(nonce,nc) "\\${(v.glyphCodepoint ?? v.codepoint ?? 0xe000).toString(16)}"}`);
  } else styles.push(`.source.gsub::before{counter-reset:${counters.join(" ")};content:${contents.join(" ")}}`);
  const sum = Array.from({ length: v.width }, (_, i) => `(${v.weights[i]} * var(--x-${i}))`).join(" + ");
  const maxAbsY = 2 * 8 * v.weights.reduce((s, w) => s + Math.abs(w), 0) + 1;
  const consumerOffset = 3 * maxAbsY + 64;
  styles.push(`.source.direct-css{--sum:calc(${sum});--y:calc(2 * var(--sum) + 1);width:calc((${consumerOffset} + 3 * var(--y))*1px);height:1px}`);
  styles.push(`.decoded{--y:calc(100cqw / 1px - ${v.output.offset});width:calc((${consumerOffset} + 3 * var(--y))*1px);height:1px}`);
  return { css: styles.join("\n"), consumerOffset };
}
const baseCss = `body{margin:0}.group{position:relative;contain:layout}.item{display:inline-block;position:relative;width:1px;height:1px;vertical-align:top}.source{display:inline-block;white-space:pre;font-kerning:none;line-height:1;height:1px}.receiver{position:absolute;left:0;top:0;container-type:inline-size}.decoded{position:absolute;left:0;top:0}@property --nonce{syntax:"<integer>";inherits:true;initial-value:0}@property --sum{syntax:"<number>";inherits:false;initial-value:-99999}@property --y{syntax:"<number>";inherits:false;initial-value:-99999}`;
let activeCss = "";
const server = http.createServer(async (request, response) => {
  const pathname = new URL(request.url, "http://localhost").pathname;
  if (pathname === "/harness.html") {
    response.writeHead(200, { "content-type": "text/html", "content-security-policy": "script-src 'none';object-src 'none'" }).end(`<!doctype html><meta charset="utf-8"><title>GSUB connected weighted sum validation</title><link rel="stylesheet" href="/harness.css"><main id="fixtures"></main>`); return;
  }
  if (pathname === "/harness.css") { response.writeHead(200, { "content-type": "text/css" }).end(baseCss + activeCss); return; }
  if (pathname === "/favicon.ico") { response.writeHead(204).end(); return; }
  const file = path.resolve(out, `.${pathname}`);
  if (!file.startsWith(out + path.sep)) { response.writeHead(403).end(); return; }
  try { const bytes = await fs.readFile(file); response.writeHead(200, { "content-type": "font/woff2" }).end(bytes); }
  catch { response.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
let browser;
async function save() { await fs.writeFile(destination, JSON.stringify(report, null, 2) + "\n"); }
try {
  for (const v of variants) {
    const expectedWeights = v.id.includes("fanout") ? [9, 1, 6, 5] : Array.from({ length: v.width }, (_, i) => [3, -2, 5, 1][i % 4]);
    if (v.width % 4 || v.weights.length !== expectedWeights.length || v.weights.some((w, i) => w !== expectedWeights[i])) throw new Error(`Unexpected weights for ${v.id}`);
    if (v.kind !== "hvar" && (v.dependent.kind !== "affine" || v.dependent.multiplier !== 2 || v.dependent.bias !== 1)) throw new Error(`Unexpected dependent operation for ${v.id}`);
    if (v.output.fontSize !== v.output.unitsPerEm) throw new Error("Harness requires 1 pixel per font unit");
    report.fontSha256[v.id] = hash(await fs.readFile(path.join(out, v.fontFile)));
  }
  if (mode === "timing" || mode === "profile") {
    const gates = await Promise.all(arg("--correctness-report", "results-correctness.json").split(",").map(async name => JSON.parse(await fs.readFile(path.resolve(out, name), "utf8"))));
    if (gates.some(g => !g.passed || g.mode !== "correctness") || variants.some(v => !gates.some(g => g.fontSha256[v.id] === report.fontSha256[v.id] && g.correctness.some(c => c.variant === v.id && c.passed)))) throw new Error("Timing requires passed full correctness reports for these exact fonts");
    report.correctnessGate = gates.map(g => ({ completedAt: g.completedAt, fontSha256: g.fontSha256 }));
  }
  browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
  report.browserVersion = await browser.version();
  const page = await browser.newPage({ viewport: { width: 1000, height: 600 } });
  const cdp = mode === "profile" ? await page.context().newCDPSession(page) : null;
  if (cdp) await cdp.send("Performance.enable");
  page.on("pageerror", e => report.errors.push(String(e)));
  page.on("console", message => { if (message.type() === "error") (report.browserConsoleErrors ??= []).push(message.text()); });
  page.on("requestfailed", request => (report.failedRequests ??= []).push({ url: request.url(), error: request.failure()?.errorText }));
  for (const v of variants) {
    const { css, consumerOffset } = variantCss(v); activeCss = css;
    await page.goto(`http://127.0.0.1:${server.address().port}/harness.html`, { waitUntil: "load" });
    await page.evaluate(async v => {
      await document.fonts.load(`${v.output.fontSize}px "${v.fontFamily ?? `GSUBWeighted${v.id}`}"`, String.fromCodePoint(v.kind === "hvar" ? (v.glyphCodepoint ?? v.codepoint ?? 0xe000) : v.inputCodepoints[0]));
      await document.fonts.ready;
    }, v);
    await page.evaluate(({ batch, width }) => {
      const fixtures = document.querySelector("#fixtures");
      for (const mode of ["gsub", "direct-css"]) {
        const group = document.createElement("div"); group.id = mode; group.className = "group";
        for (let i = 0; i < batch; i++) {
          const item = document.createElement("div"); item.className = "item";
          const source = document.createElement("span"); source.className = `source ${mode}`;
          if (mode === "gsub") {
            source.style.anchorName = `--weighted-${i}`;
            const receiver = document.createElement("div"); receiver.className = "receiver";
            receiver.style.width = `anchor-size(--weighted-${i} inline)`;
            const decoded = document.createElement("div"); decoded.className = "decoded";
            receiver.append(decoded); item.append(source, receiver);
          } else item.append(source);
          group.append(item);
        }
        fixtures.append(group);
      }
    }, { batch, width: v.width });
    const scripts = await page.evaluate(() => document.scripts.length);
    if (scripts !== 0) throw new Error(`Unexpected runtime script in ${v.id}`);
    const cases = casesFor(v.width, mode === "correctness", v.weights);
    const chosen = mode === "correctness" ? cases : mode === "smoke" && v.width >= 128
      ? cases.filter(c => c.category !== "seeded-random" && (c.category !== "individual-coordinate" || [0, Math.floor(v.width / 2), v.width - 1].includes(c.input.findIndex(x => x !== 0)))).slice(0, 48).concat(cases.filter(c => c.category === "seeded-random").slice(0, 16))
      : cases.slice(0, Math.min(512, cases.length));
    const checks = Object.fromEntries(["gsub", "direct-css"].map(backend => [backend, { variant: v.id, width: v.width, topology: v.topology, backend: backend === "gsub" && v.kind === "hvar" ? "hvar" : backend, cases: 0, categories: {}, minimumSum: Infinity, maximumSum: -Infinity, mismatches: 0, failures: [], runtimeScripts: scripts }]));
    for (let start = 0; start < chosen.length; start += batch) {
      const rows = chosen.slice(start, start + batch);
      const actual = await page.evaluate(rows => {
        const result = {};
        for (const mode of ["gsub", "direct-css"]) {
          const sources = [...document.querySelectorAll(`#${mode} .source`)];
          rows.forEach(({ input }, index) => { input.forEach((x, i) => sources[index].style.setProperty(`--x-${i}`, x)); sources[index].style.setProperty("--nonce", 0); });
          const outputs = [...document.querySelectorAll(`#${mode} ${mode === "gsub" ? ".decoded" : ".source"}`)];
          result[mode] = rows.map((_, i) => ({ width: outputs[i].getBoundingClientRect().width, y: Number(getComputedStyle(outputs[i]).getPropertyValue("--y")), sourceWidth: sources[i].getBoundingClientRect().width }));
        }
        return result;
      }, rows);
      for (const backend of ["gsub", "direct-css"]) for (let i = 0; i < rows.length; i++) {
        const { input, category } = rows[i], oracle = expected(input, v.weights), value = actual[backend][i], check = checks[backend];
        check.cases++; check.categories[category] = (check.categories[category] ?? 0) + 1;
        check.minimumSum = Math.min(check.minimumSum, oracle.sum); check.maximumSum = Math.max(check.maximumSum, oracle.sum);
        if (value.y !== oracle.y || value.width !== consumerOffset + 3 * oracle.y || (backend === "gsub" && value.sourceWidth !== v.output.offset + oracle.y)) {
          check.mismatches++; if (check.failures.length < 8) check.failures.push({ input, category, expected: oracle, actual: value, expectedSourceWidth: v.output.offset + oracle.y, expectedConsumerWidth: consumerOffset + 3 * oracle.y });
        }
      }
      if (Object.values(checks).some(c => c.mismatches)) break;
      if (start % 8192 === 0 && mode === "correctness") console.log(JSON.stringify({ variant: v.id, checked: Math.min(start + rows.length, chosen.length), total: chosen.length }));
    }
    for (const check of Object.values(checks)) { check.passed = check.mismatches === 0 && check.cases === chosen.length; report.correctness.push(check); }
    await save();
    if (Object.values(checks).some(c => !c.passed)) throw new Error(`Correctness failed: ${v.id}`);
    const controls = v.kind === "hvar" ? [] : await page.evaluate(v => {
      const source = document.querySelector("#gsub .source");
      const rows = [];
      const inputs = [-8, 0, 7].map(value => ({ label: `constant-${value}`, input: Array(v.width).fill(value) }));
      inputs.push({ label: "maximum-signed-sum", input: v.weights.map(w => w >= 0 ? 7 : -8) });
      for (const { label, input } of inputs) {
        for (let i = 0; i < v.width; i++) source.style.setProperty(`--x-${i}`, input[i]);
        source.style.removeProperty("font-feature-settings");
        const intactWidth = source.getBoundingClientRect().width;
        for (const feature of v.features) {
          source.style.fontFeatureSettings = v.features.map(tag => `"${tag}" ${tag === feature ? 0 : 1}`).join(",");
          rows.push({ variant: v.id, disabledFeature: feature, inputLabel: label, input, intactWidth, brokenWidth: source.getBoundingClientRect().width });
        }
        source.style.fontFeatureSettings = v.features.map(tag => `"${tag}" 0`).join(",");
        rows.push({ variant: v.id, disabledFeature: "all", inputLabel: label, input, intactWidth, brokenWidth: source.getBoundingClientRect().width });
      }
      source.style.removeProperty("font-feature-settings");
      return rows;
    }, v);
    report.disabledStageControls.push(...controls);
    if (v.kind !== "hvar" && [...v.features, "all"].some(tag => !controls.some(c => c.disabledFeature === tag && c.brokenWidth !== c.intactWidth))) throw new Error(`Disabled stage fails to change any control output: ${v.id}`);
    const split = v.kind === "hvar" ? null : await page.evaluate(v => {
      const original = document.querySelector("#gsub .source");
      const source = document.createElement("span"); source.className = "source"; source.style.fontFamily = getComputedStyle(original).fontFamily;
      source.style.fontSize = `${v.output.fontSize}px`; source.style.fontFeatureSettings = v.features.map(tag => `"${tag}" 1`).join(",");
      source.textContent = v.inputCodepoints.map(cp => String.fromCodePoint(cp + 8)).join("");
      document.querySelector("#gsub").append(source);
      const intactWidth = source.getBoundingClientRect().width;
      source.replaceChildren();
      for (let i = 0; i < v.width; i++) { const atom = document.createElement("span"); atom.style.display = "inline-block"; atom.textContent = String.fromCodePoint(v.inputCodepoints[i] + 8); source.append(atom); }
      const width = source.getBoundingClientRect().width; source.remove(); return { variant: v.id, splitInputAtoms: v.width, intactSameCharactersWidth: intactWidth, sourceWidth: width };
    }, v);
    if (split) report.splitRunControls.push(split);
    if (split && (split.sourceWidth === split.intactSameCharactersWidth || split.intactSameCharactersWidth <= 0)) throw new Error(`Atomic shaping boundary control failed: ${v.id}`);
    if (v.id.startsWith("reusable-")) {
      const marker = await page.evaluate(v => {
        const original = document.querySelector("#gsub .source"), source = document.createElement("span");
        source.className = "source"; source.style.fontFamily = getComputedStyle(original).fontFamily;
        source.style.fontSize = `${v.output.fontSize}px`; source.style.fontFeatureSettings = v.features.map(tag => `"${tag}" 1`).join(",");
        const chars = v.inputCodepoints.map(cp => String.fromCodePoint(cp + 8));
        source.textContent = chars.join(""); document.querySelector("#gsub").append(source);
        const intactWidth = source.getBoundingClientRect().width;
        // Same first input and same weight3, but its product emits an operand
        // marker instead of the one active-accumulator marker.
        chars[0] = String.fromCodePoint(0xe010 + 8); source.textContent = chars.join("");
        const withoutAccumulatorWidth = source.getBoundingClientRect().width;
        source.remove(); return { variant: v.id, input: Array(v.width).fill(0), intactWidth, withoutAccumulatorWidth };
      }, v);
      report.markerControls.push(marker);
      if (marker.withoutAccumulatorWidth !== 0 || marker.intactWidth <= 0) throw new Error(`Accumulator marker control failed: ${v.id}`);
    }
    if (mode === "timing") {
      for (const phase of phases) {
        const seed = (seedBase ^ v.width ^ (phase === "unique-text" ? 0x27d4eb2d : 0)) >>> 0;
        const random = rng(seed);
        const stimuli = Array.from({ length: sampleCount }, (_, round) => Array.from({ length: batch }, () => ({ input: Array.from({ length: v.width }, () => random() % 16 - 8), nonce: phase === "unique-text" ? round + 1 : 0 })));
        const measured = await page.evaluate(({ stimuli, phase }) => {
          const nodes = Object.fromEntries(["gsub", "direct-css"].map(mode => [mode, { sources: [...document.querySelectorAll(`#${mode} .source`)], outputs: [...document.querySelectorAll(`#${mode} ${mode === "gsub" ? ".decoded" : ".source"}`)] }]));
          const times = { gsub: [], "direct-css": [] }, widths = { gsub: [], "direct-css": [] }, orders = [];
          for (let round = 0; round < stimuli.length; round++) {
            const order = (round + (phase === "unique-text" ? 1 : 0)) % 2 ? ["direct-css", "gsub"] : ["gsub", "direct-css"]; orders.push(order);
            for (const mode of order) {
              const start = performance.now();
              stimuli[round].forEach(({ input, nonce }, index) => {
                const source = nodes[mode].sources[index]; input.forEach((x, i) => source.style.setProperty(`--x-${i}`, x)); source.style.setProperty("--nonce", nonce);
              });
              widths[mode].push(nodes[mode].outputs.map(node => node.getBoundingClientRect().width));
              times[mode].push(performance.now() - start);
            }
          }
          return { times, widths, orders };
        }, { stimuli, phase });
        let changedCoordinates = 0;
        const uniqueInputVectors = new Set(stimuli.flatMap(round => round.map(row => row.input.join(",")))).size;
        for (let r = 1; r < stimuli.length; r++) for (let i = 0; i < batch; i++) for (let k = 0; k < v.width; k++) if (stimuli[r][i].input[k] !== stimuli[r - 1][i].input[k]) changedCoordinates++;
        for (const backend of ["gsub", "direct-css"]) {
          let mismatches = 0, checksum = 0;
          for (let round = 0; round < stimuli.length; round++) for (let i = 0; i < batch; i++) {
            const oracle = expected(stimuli[round][i].input, v.weights), value = measured.widths[backend][round][i]; checksum += value;
            if (value !== consumerOffset + 3 * oracle.y) mismatches++;
          }
          report.timings.push({ variant: v.id, width: v.width, topology: v.topology, backend: backend === "gsub" && v.kind === "hvar" ? "hvar" : backend, phase, seed, batch, ...summarize(measured.times[backend].slice(warmupCount)), mismatches, checksum, inputCases: sampleCount * batch, uniqueInputVectors, changedCoordinatesAfterFirstRound: changedCoordinates, rawMilliseconds: measured.times[backend], measurementOrders: measured.orders });
        }
        if (report.timings.some(t => t.mismatches)) throw new Error(`Timed output correctness failure: ${v.id}`);
        console.log(JSON.stringify({ variant: v.id, phase, timings: report.timings.filter(t => t.variant === v.id && t.phase === phase).map(({ backend, medianMilliseconds, mismatches }) => ({ backend, medianMilliseconds, mismatches })) }));
      }
    }
    if (mode === "profile") {
      const seed = (0xb8e617 ^ v.width) >>> 0, random = rng(seed);
      const stimuli = Array.from({ length: profileWarmups + profileRounds }, (_, round) => Array.from({ length: batch }, () => ({ input: Array.from({ length: v.width }, () => random() % 16 - 8), nonce: round + 1 })));
      const run = async (backend, rows) => page.evaluate(({ backend, rows }) => {
        const sources = [...document.querySelectorAll(`#${backend} .source`)];
        const outputs = [...document.querySelectorAll(`#${backend} ${backend === "gsub" ? ".decoded" : ".source"}`)];
        const result = [];
        const start = performance.now();
        for (const row of rows) {
          row.forEach(({ input, nonce }, i) => { input.forEach((x, k) => sources[i].style.setProperty(`--x-${k}`, x)); sources[i].style.setProperty("--nonce", nonce); });
          result.push(outputs.map(node => node.getBoundingClientRect().width));
        }
        return { elapsedMilliseconds: performance.now() - start, widths: result };
      }, { backend, rows });
      for (const backend of ["gsub", "direct-css"]) {
        const warm = await run(backend, stimuli.slice(0, profileWarmups));
        const before = Object.fromEntries((await cdp.send("Performance.getMetrics")).metrics.map(m => [m.name, m.value]));
        const measured = await run(backend, stimuli.slice(profileWarmups));
        const after = Object.fromEntries((await cdp.send("Performance.getMetrics")).metrics.map(m => [m.name, m.value]));
        const metrics = Object.fromEntries(["RecalcStyleDuration", "LayoutDuration", "TaskDuration", "ScriptDuration", "RecalcStyleCount", "LayoutCount"].map(name => [name, after[name] - before[name]]));
        let mismatches = 0;
        const widths = [...warm.widths, ...measured.widths];
        for (let r = 0; r < stimuli.length; r++) for (let i = 0; i < batch; i++) if (widths[r][i] !== consumerOffset + 3 * expected(stimuli[r][i].input, v.weights).y) mismatches++;
        report.profiles.push({ variant: v.id, width: v.width, topology: v.topology, backend: backend === "gsub" && v.kind === "hvar" ? "hvar" : backend, seed, batch, measuredRounds: profileRounds, warmupRounds: profileWarmups, inputCases: (profileWarmups + profileRounds) * batch, mismatches, elapsedMilliseconds: measured.elapsedMilliseconds, metrics, description: `Separate CDP Performance metric deltas across ${profileRounds} updates of ${batch} outputs; durations in seconds. Browser style/layout/task categories include multiple activities and do not isolate font CPU. CDP command overhead can enter TaskDuration.` });
        if (mismatches) throw new Error(`Profile output correctness failure: ${v.id}`);
        console.log(JSON.stringify(report.profiles.at(-1)));
      }
    }
    console.log(JSON.stringify({ variant: v.id, passed: true, cases: chosen.length, controls: controls.length + Number(Boolean(split)) }));
    await save();
  }
  report.passed = report.correctness.every(c => c.passed) && variants.every(v => v.kind === "hvar" || [...v.features, "all"].every(tag => report.disabledStageControls.some(c => c.variant === v.id && c.disabledFeature === tag && c.brokenWidth !== c.intactWidth))) && report.splitRunControls.every(c => c.sourceWidth !== c.intactSameCharactersWidth) && report.markerControls.every(c => c.withoutAccumulatorWidth === 0) && report.timings.every(t => t.mismatches === 0) && report.profiles.every(t => t.mismatches === 0) && report.errors.length === 0;
} catch (error) { report.errors.push(String(error.stack ?? error)); report.passed = false; }
finally { report.completedAt = new Date().toISOString(); await save(); await browser?.close(); await new Promise(resolve => server.close(resolve)); }
console.log(JSON.stringify({ passed: report.passed, errors: report.errors, report: destination }));
if (!report.passed) process.exitCode = 1;
