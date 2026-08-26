import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = process.env.SVG_REDUCER_BASELINE_URL ??
  "http://127.0.0.1:4178/experiments/svg-live-two-complete-blocks/index.html";
const candidateUrl = process.env.SVG_REDUCER_CANDIDATE_URL ??
  "http://127.0.0.1:4178/experiments/svg-live-two-complete-blocks-gaussian-all/index.html";
const rounds = Number.parseInt(process.env.SVG_REDUCER_ROUNDS ?? "10", 10);

function stats(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return {
    minimum: sorted[0],
    median: sorted[Math.floor(sorted.length / 2)],
    mean: values.reduce((sum, value) => sum + value, 0) / values.length,
    maximum: sorted.at(-1),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 16, height: 768 } });
  async function prepare(name, url) {
    const page = await context.newPage();
    await page.goto(url, { waitUntil: "load", timeout: 180000 });
    const svg = page.locator("svg").first();
    const input = page.locator("feImage").first();
    const baseHref = (await input.getAttribute("href")).split("?")[0];
    const absoluteHref = new URL(baseHref, url).href;
    await page.evaluate(async ({ href }) => {
      await Promise.all([0, 1].map((suffix) => new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = resolve;
        image.onerror = reject;
        image.src = `${href}?paired=${suffix}`;
      })));
    }, { href: absoluteHref });
    await svg.screenshot({ timeout: 180000 });
    return { name, url, page, svg, input, baseHref, samples: [] };
  }

  const baseline = await prepare("baseline", baseUrl);
  const candidate = await prepare("candidate", candidateUrl);
  async function measure(target, round) {
    const started = performance.now();
    await target.input.evaluate((image, payload) => {
      image.setAttribute("href", `${payload.baseHref}?paired=${payload.suffix}`);
    }, { baseHref: target.baseHref, suffix: round % 2 });
    await target.svg.screenshot({ timeout: 180000 });
    target.samples.push(performance.now() - started);
  }

  for (let round = 0; round < rounds; round += 1) {
    const order = round % 2 ? [candidate, baseline] : [baseline, candidate];
    for (const target of order) await measure(target, round);
  }
  console.log(JSON.stringify({
    rounds,
    baseline: { url: baseline.url, timing: stats(baseline.samples), samples: baseline.samples },
    candidate: { url: candidate.url, timing: stats(candidate.samples), samples: candidate.samples },
    medianSpeedup: stats(baseline.samples).median / stats(candidate.samples).median,
  }, null, 2));
} finally {
  await browser.close();
}
