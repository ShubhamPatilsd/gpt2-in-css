import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const directory = "gpt2-hvar-grid-output-head-global11-inline-tie";
const root = new URL(`../experiments/${directory}/`, import.meta.url);
const css = await fs.readFile(new URL("index.css", root), "utf8");
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));
const resultUrl = new URL(
  "../experiments/gpt2-hvar-grid-output-head-containment/browser-results.json",
  import.meta.url,
);
const url = `http://127.0.0.1:4178/experiments/${directory}/index.html`;

const variants = [
  { name: "control", override: "" },
  { name: "group-layout", override: ".group-wrapper{contain:layout}" },
  { name: "group-layout-style", override: ".group-wrapper{contain:layout style}" },
];

async function metrics(session) {
  const result = await session.send("Performance.getMetrics");
  return Object.fromEntries(result.metrics.map(({ name, value }) => [name, value]));
}

async function runVariant(variant) {
  const browser = await chromium.launch({ executablePath, headless: true });
  try {
    const context = await browser.newContext({
      javaScriptEnabled: false,
      viewport: { width: 800, height: 200 },
    });
    const page = await context.newPage();
    page.setDefaultTimeout(180000);
    await page.route("**/index.css", async (route) => {
      await route.fulfill({
        body: `${css}\n${variant.override}\n`,
        contentType: "text/css",
      });
    });
    const session = await context.newCDPSession(page);
    await session.send("Performance.enable");
    const before = await metrics(session);
    const started = performance.now();
    await page.goto(url, { waitUntil: "load", timeout: 180000 });
    await page.evaluate(() => document.fonts.ready);
    for (let pass = 0; pass < 4; pass += 1) {
      await page.locator("#result").evaluate((element) => element.getBoundingClientRect().width);
    }
    const output = await page.locator("#result").evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        group: Number(style.getPropertyValue("--group")),
        local: Number(style.getPropertyValue("--local")),
        winner: Number(style.getPropertyValue("--winner")),
        width: element.getBoundingClientRect().width,
      };
    });
    const elapsedMilliseconds = performance.now() - started;
    const after = await metrics(session);
    await context.close();
    return {
      name: variant.name,
      override: variant.override,
      elapsedMilliseconds,
      output,
      expected: reference.quantizedWinners[0],
      correct: output.winner === reference.quantizedWinners[0],
      layoutCount: (after.LayoutCount ?? 0) - (before.LayoutCount ?? 0),
      layoutDurationMilliseconds:
        ((after.LayoutDuration ?? 0) - (before.LayoutDuration ?? 0)) * 1000,
      recalcStyleCount: (after.RecalcStyleCount ?? 0) - (before.RecalcStyleCount ?? 0),
      recalcStyleDurationMilliseconds:
        ((after.RecalcStyleDuration ?? 0) - (before.RecalcStyleDuration ?? 0)) * 1000,
      taskDurationMilliseconds:
        ((after.TaskDuration ?? 0) - (before.TaskDuration ?? 0)) * 1000,
      chrome: await browser.version(),
    };
  } finally {
    await browser.close();
  }
}

const samples = [];
for (const variant of variants) {
  console.error(`starting ${variant.name}`);
  samples.push(await runVariant(variant));
  await fs.mkdir(new URL(".", resultUrl), { recursive: true });
  await fs.writeFile(resultUrl, `${JSON.stringify({ samples }, null, 2)}\n`);
  console.error(`finished ${variant.name} in ${samples.at(-1).elapsedMilliseconds.toFixed(1)}ms`);
}

const report = { allCorrect: samples.every(({ correct }) => correct), samples };
await fs.writeFile(resultUrl, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
