#!/usr/bin/env node
// External input/observation harness. The page contains no inference JavaScript.
import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const out = path.join(root, "experiments/gsub-arithmetic-probe");
const reference = JSON.parse(await fs.readFile(path.join(out, "reference.json"), "utf8"));
const report = { startedAt: new Date().toISOString(), reference, correctness: [], timings: [], errors: [], console: [], limitations: ["External harness stimulates inputs and reads layout; this is not autonomous GPT-2.", "Font programs contain only the declared addition/nonlinear/tiny-network tables, not test answers from the harness.", "The tiny network uses two-input lookup tables; this does not establish scalability to dense 768-input neurons."] };
const server = http.createServer(async (request, response) => {
  const file = path.resolve(out, `.${new URL(request.url, "http://localhost").pathname}`);
  if (!file.startsWith(out + path.sep)) { response.writeHead(403).end(); return; }
  try {
    const mime = { ".html": "text/html", ".css": "text/css", ".woff2": "font/woff2" }[path.extname(file)] ?? "application/octet-stream";
    const bytes = await fs.readFile(file);
    response.writeHead(200, { "content-type": mime }); response.end(bytes);
  } catch { response.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
let browser;

function encoded(a, b, operation) {
  const digits = operation === "network" ? [64 + a, 80 + b] : [a % 16, 16 + b % 16, 32 + (a >> 4), 48 + (b >> 4)];
  return String.fromCodePoint(...digits.map(value => reference.inputCodepointBase + value));
}
function expected(a, b, operation) {
  if (operation === "nonlinear") return Math.min(255, Math.floor((a + b - 128) ** 2 / 128));
  if (operation === "network") return Math.max(0, 3 * Math.max(0, 2 * a + b - 16) - 2 * Math.max(0, a - 2 * b + 8) + 5);
  return a + b;
}
function stats(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return { samples: values.length, medianMilliseconds: sorted[Math.floor(sorted.length / 2)], p95Milliseconds: sorted[Math.floor((sorted.length - 1) * .95)], minMilliseconds: sorted[0], maxMilliseconds: sorted.at(-1) };
}

try {
  browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
  report.browserVersion = await browser.version();
  const page = await browser.newPage({ viewport: { width: 900, height: 600 } });
  page.on("console", msg => report.console.push({ type: msg.type(), text: msg.text() }));
  page.on("pageerror", error => report.errors.push(String(error)));
  const start = performance.now();
  await page.goto(`http://127.0.0.1:${server.address().port}/index.html`, { waitUntil: "load" });
  await page.evaluate(async () => { await document.fonts.load('1000px Arithmetic', '\ue000'); await document.fonts.ready; });
  report.loadMilliseconds = performance.now() - start;
  report.capabilities = await page.evaluate(() => ({ fontLoaded: document.fonts.check('1000px Arithmetic', '\ue000'), scripts: document.scripts.length, counterRound: CSS.supports("counter-reset", "x round(down,255/16,1)"), nonlinearWidth: CSS.supports("width", "calc((64 + min(255,round(down,(1 + 2 - 128)*(1 + 2 - 128)/128,1)))*1px)") }));

  async function configure(mode, operation, count) {
    await page.evaluate(({ mode, operation, count }) => {
      const root = document.querySelector("#rows"); root.replaceChildren();
      for (let index = 0; index < count; index++) {
        const node = document.createElement("span");
        node.className = `probe ${operation} ${mode === "generated" ? "encoded" : mode === "css" ? "control" : ""}`;
        root.append(node);
      }
    }, { mode, operation, count });
  }
  async function observe(mode, entries) {
    return page.evaluate(({ mode, entries }) => {
      const nodes = [...document.querySelector("#rows").children];
      for (let index = 0; index < entries.length; index++) {
        const [a, b, text] = entries[index]; const node = nodes[index];
        if (mode === "text") node.textContent = text;
        else if (mode === "split") node.replaceChildren(...[...text].map(char => { const span = document.createElement("span"); span.textContent = char; return span; }));
        else { node.style.setProperty("--a", a); node.style.setProperty("--b", b); }
      }
      return nodes.slice(0, entries.length).map(node => node.getBoundingClientRect().width);
    }, { mode, entries });
  }
  for (const operation of ["sum", "nonlinear", "network"]) {
    const extent = operation === "network" ? 16 : 256;
    for (const mode of ["text", "generated", "css"]) {
      await configure(mode, operation, 256);
      const result = { operation, mode, cases: 0, passed: 0, maxAbsoluteError: 0, failures: [] };
      const began = performance.now();
      for (let offset = 0; offset < extent * extent; offset += 256) {
        const entries = [];
        for (let index = offset; index < Math.min(offset + 256, extent * extent); index++) {
          const a = Math.floor(index / extent), b = index % extent;
          entries.push([a, b, encoded(a, b, operation)]);
        }
        const observed = await observe(mode, entries);
        for (let index = 0; index < observed.length; index++) {
          const [a, b] = entries[index]; const wanted = expected(a, b, operation);
          const actual = observed[index] - reference.outputAdvanceBase;
          const error = Math.abs(actual - wanted); result.cases++;
          result.maxAbsoluteError = Math.max(result.maxAbsoluteError, error);
          if (error < 1e-8) result.passed++;
          else if (result.failures.length < 8) result.failures.push({ a, b, wanted, actual });
        }
        // A native-input failure is decisive; preserve it without spending minutes on repeats.
        if (result.failures.length && mode !== "text") break;
      }
      result.wallMilliseconds = performance.now() - began;
      result.allPassed = result.cases === extent * extent && result.passed === result.cases;
      report.correctness.push(result);
      console.log(JSON.stringify({ stage: "correctness", ...result }));
      await fs.writeFile(path.join(out, "results.json"), JSON.stringify(report, null, 2) + "\n");
      if (mode === "text" && !result.allPassed) throw new Error(`GSUB ${operation} primitive failed; stopped downstream tests`);
    }
  }
  await configure("split", "sum", 1);
  report.atomicSplitControl = { a: 255, b: 1, observedAdvance: (await observe("split", [[255, 1, encoded(255, 1, "sum")]]))[0], expectedUnsplitAdvance: 320, purpose: "Separate inline-blocks deliberately force shaping boundaries; this is an expected negative control." };
  await configure("text", "sum", 1);
  await observe("text", [[255, 1, encoded(255, 1, "sum")]]);
  report.disabledProgramControl = await page.evaluate(() => {
    const node = document.querySelector("#rows").firstElementChild;
    const enabledWidth = node.getBoundingClientRect().width;
    node.style.fontFeatureSettings = '"rlig" 0,"ss01" 0';
    return { enabledWidth, disabledWidth: node.getBoundingClientRect().width, expectedEnabledWidth: 320, expectedDisabledWidth: 0 };
  });
  for (const operation of ["sum", "nonlinear", "network"]) {
    for (const mode of ["text", "generated", "css"]) {
      if (!report.correctness.some(row => row.mode === mode && row.operation === operation && row.allPassed)) continue;
      for (const batch of [1, 64, 256]) {
        await configure(mode, operation, batch);
        const extent = operation === "network" ? 16 : 256;
        const stimuli = Array.from({ length: 40 }, (_, round) => Array.from({ length: batch }, (_, index) => {
          const a = (index * 73 + round * 11) % extent, b = (index * 37 + round * 17) % extent;
          return [a, b, encoded(a, b, operation)];
        }));
        const timing = await page.evaluate(({ mode, stimuli }) => {
          const nodes = [...document.querySelector("#rows").children];
          const times = [], checksums = [];
          for (const entries of stimuli) {
            const start = performance.now();
            for (let index = 0; index < entries.length; index++) {
              const [a, b, text] = entries[index];
              if (mode === "text") nodes[index].textContent = text;
              else { nodes[index].style.setProperty("--a", a); nodes[index].style.setProperty("--b", b); }
            }
            const widths = nodes.map(node => node.getBoundingClientRect().width);
            times.push(performance.now() - start); checksums.push(widths.reduce((a, b) => a + b, 0));
          }
          return { times, checksums };
        }, { mode, stimuli });
        const checks = stimuli.map(entries => entries.reduce((total, [a, b]) => total + reference.outputAdvanceBase + expected(a, b, operation), 0));
        report.timings.push({ operation, mode, batch, ...stats(timing.times.slice(5)), timedSamples: timing.times, checksumPassed: JSON.stringify(timing.checksums) === JSON.stringify(checks), timingIncludes: "Input write / text generation supplied by harness plus synchronous browser style, shaping, layout and final width read; excludes cross-process CDP transport and stimulus preparation." });
      }
    }
  }
  report.allRequiredPassed = report.correctness.every(row => row.allPassed) && report.timings.every(row => row.checksumPassed) && report.capabilities.scripts === 0 && report.disabledProgramControl.enabledWidth === 320 && report.disabledProgramControl.disabledWidth === 0 && report.atomicSplitControl.observedAdvance === 0;
} catch (error) {
  report.errors.push(String(error.stack ?? error)); report.allRequiredPassed = false;
} finally {
  report.completedAt = new Date().toISOString();
  await fs.writeFile(path.join(out, "results.json"), JSON.stringify(report, null, 2) + "\n");
  await browser?.close(); await new Promise(resolve => server.close(resolve));
}
console.log(JSON.stringify({ passed: report.allRequiredPassed, errors: report.errors, timingCases: report.timings.length, report: path.join(out, "results.json") }));
if (!report.allRequiredPassed) process.exitCode = 1;
