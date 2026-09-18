#!/usr/bin/env node
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
const out = path.join(root, "experiments/gsub-arithmetic-depth-probe");
const reference = JSON.parse(await fs.readFile(path.join(out, "reference.json"), "utf8"));
const report = { startedAt: new Date().toISOString(), reference, environment: { node: process.version, cpu: os.cpus()[0]?.model, platform: process.platform }, correctness: [], disabledLayerControls: [], timings: [], errors: [] };
report.harnessSha256 = createHash("sha256").update(await fs.readFile(fileURLToPath(import.meta.url))).digest("hex");
const server = http.createServer(async (request, response) => {
  const file = path.resolve(out, `.${new URL(request.url, "http://localhost").pathname}`);
  if (!file.startsWith(out + path.sep)) { response.writeHead(403).end(); return; }
  try {
    const bytes = await fs.readFile(file);
    response.writeHead(200, { "content-type": { ".html": "text/html", ".css": "text/css", ".woff2": "font/woff2" }[path.extname(file)] ?? "application/octet-stream" }).end(bytes);
  } catch { response.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
let browser;
function expected(a, b, depth) {
  let x = a, y = b;
  for (let layer = 0; layer < depth; layer++) [x, y] = [y, (x + y * y + 3 * y + layer + 1) % 16];
  return [x, y];
}
function summarize(times) {
  const sorted = [...times].sort((a, b) => a - b);
  return { samples: times.length, medianMilliseconds: sorted[Math.floor(sorted.length / 2)], p95Milliseconds: sorted[Math.floor((sorted.length - 1) * .95)], minMilliseconds: sorted[0], maxMilliseconds: sorted.at(-1) };
}
try {
  browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
  report.browserVersion = await browser.version();
  const page = await browser.newPage({ viewport: { width: 900, height: 500 } });
  page.on("pageerror", error => report.errors.push(String(error)));
  await page.goto(`http://127.0.0.1:${server.address().port}/index.html`, { waitUntil: "load" });
  await page.evaluate(async depths => { for (const depth of depths) await document.fonts.load(`1024px Depth${depth}`, "\ue000"); await document.fonts.ready; }, reference.depths);
  report.runtimeScripts = await page.evaluate(() => document.scripts.length);
  for (const depth of reference.depths) {
    await page.evaluate(depth => {
      const fixtures = document.querySelector("#fixtures"); fixtures.replaceChildren();
      for (const mode of ["gsub", "control"]) {
        const group = document.createElement("div"); group.className = "group"; group.id = mode;
        for (let index = 0; index < 256; index++) {
          const item = document.createElement("div"); item.className = "item"; item.style.width = "1px"; item.style.height = "1px";
          const source = document.createElement("span"); source.className = `source d${depth} ${mode}`;
          source.style.anchorName = `--depth-${mode}-${index}`;
          const receiver = document.createElement("div"); receiver.className = "receiver"; receiver.style.width = `anchor-size(--depth-${mode}-${index} inline)`;
          const decoded = document.createElement("div"); decoded.className = "decoded";
          receiver.append(decoded); item.append(source, receiver); group.append(item);
        }
        fixtures.append(group);
      }
    }, depth);
    const check = await page.evaluate(() => {
      const result = {};
      for (const mode of ["gsub", "control"]) {
        const sources = [...document.querySelectorAll(`#${mode} .source`)];
        sources.forEach((source, index) => { source.style.setProperty("--a", index >> 4); source.style.setProperty("--b", index & 15); source.style.setProperty("--nonce", 0); });
        result[mode] = [...document.querySelectorAll(`#${mode} .decoded`)].map(node => {
          const width = node.getBoundingClientRect().width;
          const style = getComputedStyle(node);
          return { width, x: Number(style.getPropertyValue("--dx")), y: Number(style.getPropertyValue("--dy")) };
        });
      }
      return result;
    });
    for (const mode of ["gsub", "control"]) {
      const failures = [];
      for (let index = 0; index < 256; index++) {
        const [x, y] = expected(index >> 4, index & 15, depth), actual = check[mode][index];
        if (actual.x !== x || actual.y !== y || actual.width !== 64 + 16 * x + y) failures.push({ input: index, actual, expected: [x, y] });
      }
      report.correctness.push({ depth, mode, states: 256, uniqueFinalStates: new Set(check[mode].map(row => `${row.x},${row.y}`)).size, passed: !failures.length, failures: failures.slice(0, 8) });
      if (failures.length) throw new Error(`Depth${depth} ${mode} correctness failed`);
    }
    report.disabledLayerControls.push(...await page.evaluate(depth => {
      const source = document.querySelector("#gsub .source"), rows = [];
      const all = Array.from({ length: depth }, (_, i) => `"ss${String(i + 1).padStart(2, "0")}" 1`);
      for (let layer = 0; layer < depth; layer++) {
        const features = [...all]; features[layer] = `"ss${String(layer + 1).padStart(2, "0")}" 0`;
        source.style.fontFeatureSettings = [...features, '"ss20" 1'].join(",");
        rows.push({ depth, disabledLayer: layer + 1, sourceWidth: source.getBoundingClientRect().width });
      }
      source.style.removeProperty("font-feature-settings");
      return rows;
    }, depth));
    for (const phase of ["repeated-state", "unique-text"]) {
      const stimuli = Array.from({ length: 40 }, (_, round) => Array.from({ length: 256 }, (_, index) => {
        const code = (index * 73 + round * 29) % 256;
        return [code >> 4, code & 15, phase === "unique-text" ? round + 1 : 0];
      }));
      const measured = await page.evaluate(({ stimuli, phase }) => {
        const nodes = Object.fromEntries(["gsub", "control"].map(mode => [mode, { sources: [...document.querySelectorAll(`#${mode} .source`)], outputs: [...document.querySelectorAll(`#${mode} .decoded`)] }]));
        const times = { gsub: [], control: [] }, widths = { gsub: [], control: [] }, orders = [];
        for (let round = 0; round < stimuli.length; round++) {
          const order = (round + (phase === "unique-text" ? 1 : 0)) % 2 ? ["control", "gsub"] : ["gsub", "control"];
          orders.push(order);
          for (const mode of order) {
            const start = performance.now();
            stimuli[round].forEach(([a, b, nonce], index) => {
              const source = nodes[mode].sources[index];
              source.style.setProperty("--a", a); source.style.setProperty("--b", b); source.style.setProperty("--nonce", nonce);
            });
            widths[mode].push(nodes[mode].outputs.map(node => node.getBoundingClientRect().width));
            times[mode].push(performance.now() - start);
          }
        }
        return { times, widths, orders };
      }, { stimuli, phase });
      for (const mode of ["gsub", "control"]) {
        let mismatches = 0;
        for (let round = 0; round < stimuli.length; round++) {
          for (let index = 0; index < 256; index++) {
            const [a, b] = stimuli[round][index], [x, y] = expected(a, b, depth);
            if (measured.widths[mode][round][index] !== 64 + 16 * x + y) mismatches++;
          }
        }
        report.timings.push({ depth, mode, phase, batch: 256, ...summarize(measured.times[mode].slice(5)), mismatches, rawMilliseconds: measured.times[mode], measurementOrders: measured.orders, inputCases: 40 * 256 });
      }
    }
    console.log(JSON.stringify({ depth, checks: report.correctness.filter(row => row.depth === depth), timing: report.timings.filter(row => row.depth === depth).map(({ mode, phase, medianMilliseconds, mismatches }) => ({ mode, phase, medianMilliseconds, mismatches })) }));
    await fs.writeFile(path.join(out, "results.json"), JSON.stringify(report, null, 2) + "\n");
  }
  report.passed = report.correctness.every(row => row.passed && row.uniqueFinalStates === 256) && report.disabledLayerControls.every(row => row.sourceWidth === 0) && report.timings.every(row => row.mismatches === 0) && report.runtimeScripts === 0;
} catch (error) { report.errors.push(String(error.stack ?? error)); report.passed = false; }
finally {
  report.completedAt = new Date().toISOString();
  await fs.writeFile(path.join(out, "results.json"), JSON.stringify(report, null, 2) + "\n");
  await browser?.close(); await new Promise(resolve => server.close(resolve));
}
console.log(JSON.stringify({ passed: report.passed, errors: report.errors, report: path.join(out, "results.json") }));
if (!report.passed) process.exitCode = 1;
