import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = process.env.SVG_VARIANCE_URL ??
  "http://127.0.0.1:4178/experiments/svg-live-two-complete-blocks/index.html";
const rounds = Number.parseInt(process.env.SVG_VARIANCE_ROUNDS ?? "8", 10);
const mutationMode = process.env.SVG_VARIANCE_MUTATION ?? "unique-url";
const launchArgs = process.env.SVG_VARIANCE_CHROME_ARGS
  ? process.env.SVG_VARIANCE_CHROME_ARGS.split(",").filter(Boolean)
  : [];

function metricMap(payload) {
  return Object.fromEntries(payload.metrics.map(({ name, value }) => [name, value]));
}

function metricDelta(before, after, name) {
  return ((after[name] ?? 0) - (before[name] ?? 0)) * 1000;
}

function processMap(payload) {
  const totals = {};
  for (const process of payload.processInfo) {
    totals[process.type] = (totals[process.type] ?? 0) + process.cpuTime;
  }
  return totals;
}

function processDeltas(before, after) {
  return Object.fromEntries(Object.keys(after).map((type) => [
    type,
    ((after[type] ?? 0) - (before[type] ?? 0)) * 1000,
  ]));
}

const browser = await chromium.launch({ executablePath, headless: true, args: launchArgs });
try {
  const page = await browser.newPage({ viewport: { width: 16, height: 768 } });
  const cdp = await page.context().newCDPSession(page);
  const browserCdp = await browser.newBrowserCDPSession();
  await cdp.send("Performance.enable");
  await page.goto(url, { waitUntil: "load", timeout: 180000 });
  const svg = page.locator("svg");
  await svg.screenshot({ timeout: 180000 });
  const input = page.locator("feImage").first();
  const baseHref = (await input.getAttribute("href")).split("?")[0];
  const arithmetic = page.locator('feComposite[operator="arithmetic"][k1]').first();
  const baseK1 = Number.parseFloat(await arithmetic.getAttribute("k1"));
  if (mutationMode === "toggle-url") {
    await page.evaluate(async ({ href }) => {
      await Promise.all([0, 1].map((suffix) => new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = resolve;
        image.onerror = reject;
        image.src = `${href}?variance-toggle=${suffix}`;
      })));
    }, { href: new URL(baseHref, url).href });
  }
  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    const before = metricMap(await cdp.send("Performance.getMetrics"));
    const processesBefore = processMap(await browserCdp.send("SystemInfo.getProcessInfo"));
    let started = performance.now();
    if (mutationMode === "unique-url") {
      await input.evaluate((image, payload) => {
        image.setAttribute("href", `${payload.baseHref}?variance=${payload.round}`);
      }, { baseHref, round });
    } else if (mutationMode === "toggle-url") {
      await input.evaluate((image, payload) => {
        image.setAttribute("href", `${payload.baseHref}?variance-toggle=${payload.round % 2}`);
      }, { baseHref, round });
    } else if (mutationMode === "coefficient") {
      await arithmetic.evaluate((primitive, payload) => {
        primitive.setAttribute("k1", String(payload.baseK1 + (payload.round % 2) * 0.0001));
      }, { baseK1, round });
    } else {
      throw new Error(`Unknown SVG_VARIANCE_MUTATION mode: ${mutationMode}`);
    }
    const mutationMilliseconds = performance.now() - started;

    started = performance.now();
    await page.evaluate(() => new Promise((resolve) => {
      requestAnimationFrame(() => requestAnimationFrame(resolve));
    }));
    const animationFrameMilliseconds = performance.now() - started;

    started = performance.now();
    await svg.screenshot({ timeout: 180000 });
    const screenshotMilliseconds = performance.now() - started;
    const after = metricMap(await cdp.send("Performance.getMetrics"));
    const processesAfter = processMap(await browserCdp.send("SystemInfo.getProcessInfo"));
    samples.push({
      round,
      mutationMilliseconds,
      animationFrameMilliseconds,
      screenshotMilliseconds,
      totalMilliseconds:
        mutationMilliseconds + animationFrameMilliseconds + screenshotMilliseconds,
      taskMilliseconds: metricDelta(before, after, "TaskDuration"),
      layoutMilliseconds: metricDelta(before, after, "LayoutDuration"),
      styleMilliseconds: metricDelta(before, after, "RecalcStyleDuration"),
      scriptMilliseconds: metricDelta(before, after, "ScriptDuration"),
      processCpuMilliseconds: processDeltas(processesBefore, processesAfter),
    });
  }
  console.log(JSON.stringify({ url, rounds, mutationMode, launchArgs, samples }, null, 2));
} finally {
  await browser.close();
}
