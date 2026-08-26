import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const workspace = path.resolve(new URL("..", import.meta.url).pathname);
const directory = path.join(workspace, "experiments/gpt2-mincontent-word-argmax/scaling");
const reference = JSON.parse(await fs.readFile(path.join(directory, "reference.json"), "utf8"));
const timeoutMilliseconds = Number(process.env.MINCONTENT_CURVE_TIMEOUT_MS ?? 45_000);
const maximumGroups = Number(process.env.MINCONTENT_CURVE_MAX_GROUPS ?? 197);

const types = new Map([[".html", "text/html"], [".css", "text/css"], [".woff2", "font/woff2"]]);
const server = http.createServer(async (request, response) => {
  try {
    const filename = path.join(workspace, decodeURIComponent(new URL(request.url, "http://x").pathname));
    if (!filename.startsWith(`${workspace}${path.sep}`)) throw new Error("outside workspace");
    const body = await fs.readFile(filename);
    response.writeHead(200, { "content-type": types.get(path.extname(filename)) ?? "application/octet-stream" });
    response.end(body);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const { port } = server.address();

function vectorStyle(vector) {
  return vector.map((value, dimension) => `--h${dimension}:${value}`).join(";");
}

async function bounded(promise, label) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(
      () => reject(new Error(`${label} timed out after ${timeoutMilliseconds}ms`)),
      timeoutMilliseconds,
    )),
  ]);
}

async function measure(context, kind, groups) {
  const page = await context.newPage();
  const started = performance.now();
  const url = `http://127.0.0.1:${port}/experiments/gpt2-mincontent-word-argmax/scaling/${kind}-${groups}.html`;
  try {
    await bounded(page.goto(url, { waitUntil: "domcontentloaded", timeout: timeoutMilliseconds }), `${kind}-${groups} navigation`);
    await bounded(page.evaluate(() => document.fonts.ready), `${kind}-${groups} fonts`);
    const selector = kind === "word" ? ".word-run" : ".control";
    const initial = await bounded(page.locator(selector).evaluateAll((elements) => ({
      count: elements.length,
      maximumWidth: Math.max(...elements.map((element) => element.getBoundingClientRect().width)),
      textNodesAllOne: elements.every((element) => (
        [...element.childNodes].filter((node) => node.nodeType === Node.TEXT_NODE).length === 1
      )),
    })), `${kind}-${groups} initial layout`);
    const coldMilliseconds = performance.now() - started;
    const mutationStarted = performance.now();
    await page.locator("main").evaluate((element, style) => { element.style.cssText = style; }, vectorStyle(reference.fixtures[1]));
    const mutatedMaximumWidth = await bounded(page.locator(selector).evaluateAll((elements) => (
      Math.max(...elements.map((element) => element.getBoundingClientRect().width))
    )), `${kind}-${groups} mutation layout`);
    return {
      kind, groups, status: "complete", coldMilliseconds,
      mutationMilliseconds: performance.now() - mutationStarted,
      mutatedMaximumWidth,
      ...initial,
    };
  } catch (error) {
    return {
      kind, groups, status: "timeout-or-error",
      elapsedMilliseconds: performance.now() - started,
      symptom: String(error),
    };
  } finally {
    await page.close({ runBeforeUnload: false }).catch(() => {});
  }
}

const browser = await chromium.launch({ executablePath, headless: true });
const results = [];
const chrome = await browser.version();
try {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 800, height: 200 } });
  for (const groups of reference.counts.filter((count) => count <= maximumGroups)) {
    results.push(await measure(context, "word", groups));
    await fs.writeFile(path.join(directory, "browser-scaling-progress.json"), `${JSON.stringify(results, null, 2)}\n`);
  }
  for (const groups of reference.controlCounts.filter((count) => count <= maximumGroups)) {
    results.push(await measure(context, "control", groups));
    await fs.writeFile(path.join(directory, "browser-scaling-progress.json"), `${JSON.stringify(results, null, 2)}\n`);
  }
  await context.close();
} finally {
  await browser.close();
  server.closeAllConnections();
  await new Promise((resolve) => server.close(resolve));
}

const report = {
  chrome,
  timeoutMilliseconds,
  fullAttemptSymptom: reference.fullAttemptSymptom,
  results,
};
await fs.writeFile(path.join(directory, "browser-scaling-curve.json"), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
