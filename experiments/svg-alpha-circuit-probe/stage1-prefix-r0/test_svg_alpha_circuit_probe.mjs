import fs from "node:fs/promises";
import path from "node:path";
import http from "node:http";
import os from "node:os";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const execFileAsync = promisify(execFile);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const label = process.argv[2];
if (!label || !/^[\w-]+$/.test(label)) throw new Error("Supply immutable build label");
const directory = path.join(root, "experiments/svg-alpha-circuit-probe", label);
const reference = JSON.parse(await fs.readFile(path.join(directory, "reference.json"), "utf8"));
const resultPath = path.join(directory, "browser-results.json");
try { await fs.access(resultPath); throw new Error("Refusing to overwrite browser-results.json"); } catch (error) { if (error.code !== "ENOENT") throw error; }
const trials = Number(process.env.ALPHA_ROUNDS ?? 7);
const server = http.createServer(async (request, response) => {
  try {
    const requested = decodeURIComponent(new URL(request.url, "http://localhost").pathname).replace(/^\//, "");
    const filename = path.resolve(directory, requested);
    if (!filename.startsWith(`${directory}${path.sep}`)) throw new Error("Path outside experiment");
    const data = await fs.readFile(filename);
    response.setHeader("Content-Type", filename.endsWith(".png") ? "image/png" : "text/html");
    response.end(data);
  } catch { response.writeHead(404).end(); }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const result = { label, startedAt: new Date().toISOString(), command: process.argv, platform: os.platform(), release: os.release(), arch: os.arch(), rounds: trials, fixtures: [], passed: false,
  methodology: "Input delivery is external href-only mutation of pre-generated alpha PNGs. Measured warm latency includes mutation, browser rendering, and PNG screenshot readback. No page inference JavaScript. Cached screenshots measure readback/synchronization floor. RSS is sampled process RSS, not physical footprint. Named SVG primitives do not prove distinct physical allocations." };
let browser;
let timer;
try {
  browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
  result.browserVersion = browser.version();
  const browserSession = await browser.newBrowserCDPSession();
  const initialProcesses = (await browserSession.send("SystemInfo.getProcessInfo")).processInfo;
  const browserPid = initialProcesses.find((entry) => entry.type === "browser")?.id;
  const memory = [];
  let sampling = false;
  async function sample() {
    if (sampling) return;
    sampling = true;
    try {
      const { stdout } = await execFileAsync("ps", ["-axo", "pid=,ppid=,rss="]);
      const records = stdout.trim().split("\n").map((line) => line.trim().split(/\s+/).map(Number));
      const ids = new Set([browserPid]);
      for (let pass = 0; pass < 5; pass += 1) for (const [pid, parent] of records) if (ids.has(parent)) ids.add(pid);
      const subtree = records.filter(([pid]) => ids.has(pid));
      memory.push({ at: performance.now(), rssKiB: subtree.reduce((total, row) => total + row[2], 0), processes: subtree.length });
    } catch (error) { result.memoryError = String(error); }
    sampling = false;
  }
  timer = setInterval(sample, 200);
  await sample();
  for (const fixture of reference.fixtures) {
    const record = { name: fixture.name, primitives: fixture.filterPrimitives, htmlBytes: fixture.htmlBytes, trials: [], cachedReadMilliseconds: [], passed: false };
    result.fixtures.push(record);
    const page = await browser.newPage({ viewport: { width: Math.max(32, fixture.width), height: Math.max(100, fixture.height) }, deviceScaleFactor: 1 });
    const session = await page.context().newCDPSession(page);
    await session.send("Performance.enable");
    const metrics = async () => Object.fromEntries((await session.send("Performance.getMetrics")).metrics.map((item) => [item.name, item.value]));
    const requests = [];
    page.on("requestfailed", (request) => requests.push({ url: request.url(), failure: request.failure() }));
    const warmStart = performance.now();
    await page.goto(`${base}/${fixture.file}`, { waitUntil: "networkidle", timeout: 120000 });
    const cold = await page.locator("svg").screenshot({ timeout: 120000 });
    record.coldNavigationAndReadMilliseconds = performance.now() - warmStart;
    async function verify(png, variant, outputPath) {
      const { data, info } = await sharp(png).removeAlpha().raw().toBuffer({ resolveWithObject: true });
      const expected = fixture.expectedVariants[variant];
      const errors = [];
      const actual = [];
      for (let y = 0; y < fixture.height; y += 1) {
        const row = [];
        for (let x = 0; x < fixture.width; x += 1) {
          const color = data[(y * info.width + x) * info.channels];
          row.push(color);
          if (color !== expected[y][x] * 255) errors.push({ x, y, actual: color, expected: expected[y][x] * 255 });
        }
        actual.push(row);
      }
      if (outputPath) await fs.writeFile(outputPath, png);
      return { passed: errors.length === 0, mismatches: errors.length, sampleErrors: errors.slice(0, 20), actualBytes: actual };
    }
    record.initialCorrectness = await verify(cold, 0, path.join(directory, `${fixture.name}-initial.png`));
    if (!record.initialCorrectness.passed) throw new Error(`${fixture.name}: initial exactness failed`);
    // Preload every input resource before timing, without changing the circuit values.
    await page.evaluate(async (urls) => { await Promise.all(urls.map((url) => fetch(url).then((response) => response.arrayBuffer()))); }, fixture.inputs.flatMap((item) => item.files));
    for (let index = 0; index < 3; index += 1) {
      const started = performance.now();
      await page.locator("svg").screenshot({ timeout: 120000 });
      record.cachedReadMilliseconds.push(performance.now() - started);
    }
    const memoryStart = memory.length;
    for (let trial = 0; trial < trials; trial += 1) {
      const variant = (trial + 1) % fixture.expectedVariants.length;
      const before = await metrics();
      const started = performance.now();
      await page.evaluate((updates) => { for (const item of updates) document.getElementById(item.id).setAttribute("href", item.file); }, fixture.inputs.map((item) => ({ id: item.id, file: item.files[variant] })));
      const delivered = performance.now();
      const png = await page.locator("svg").screenshot({ timeout: 120000 });
      const elapsed = performance.now() - started;
      const after = await metrics();
      const correctness = await verify(png, variant, trial === 0 ? path.join(directory, `${fixture.name}-variant.png`) : undefined);
      const counters = {};
      for (const key of ["TaskDuration", "RecalcStyleDuration", "LayoutDuration", "ScriptDuration", "RecalcStyleCount", "LayoutCount"]) counters[key] = after[key] - before[key];
      record.trials.push({ variant, milliseconds: elapsed, inputDeliveryMilliseconds: delivered - started, counters, correctness });
      if (!correctness.passed) throw new Error(`${fixture.name}: changed input exactness failed`);
    }
    record.failedRequests = requests;
    const samples = memory.slice(memoryStart);
    record.peakSubtreeRssMiB = samples.length ? Math.max(...samples.map((item) => item.rssKiB)) / 1024 : null;
    record.memorySamples = samples.length;
    record.medianMilliseconds = record.trials.map((item) => item.milliseconds).sort((a, b) => a - b)[Math.floor(trials / 2)];
    record.medianCachedReadMilliseconds = record.cachedReadMilliseconds.slice().sort((a, b) => a - b)[1];
    record.passed = true;
    await page.close();
    console.log(JSON.stringify({ name: record.name, medianMilliseconds: record.medianMilliseconds, cached: record.medianCachedReadMilliseconds, primitives: record.primitives, passed: true }));
  }
  result.memorySamples = memory;
  result.passed = result.fixtures.every((item) => item.passed);
} catch (error) {
  result.error = error.stack ?? String(error);
  process.exitCode = 1;
} finally {
  if (timer) clearInterval(timer);
  if (browser) await browser.close();
  await new Promise((resolve) => server.close(resolve));
  result.finishedAt = new Date().toISOString();
  await fs.writeFile(resultPath, `${JSON.stringify(result, null, 2)}\n`);
  console.log(JSON.stringify({ resultPath, passed: result.passed, error: result.error }));
}
