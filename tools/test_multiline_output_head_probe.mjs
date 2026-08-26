import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const directory = "gpt2-hvar-grid-output-head-multiline";
const root = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));
const url = `http://127.0.0.1:4178/experiments/${directory}/index.html`;

async function metrics(session) {
  const result = await session.send("Performance.getMetrics");
  return Object.fromEntries(result.metrics.map(({ name, value }) => [name, value]));
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 800, height: 200 },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(180000);
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
  const diagnostics = await page.locator(".group-grid").evaluateAll((elements) => (
    [0, 5].map((group) => {
      const element = elements[group];
      const widths = [...element.childNodes]
        .filter((node) => node.nodeType === Node.TEXT_NODE)
        .map((text) => {
        const range = document.createRange();
        range.selectNodeContents(text);
        return range.getBoundingClientRect().width;
      });
      const maximum = Math.max(...widths);
      return {
        group,
        fontFamily: getComputedStyle(element).fontFamily,
        fontSize: getComputedStyle(element).fontSize,
        elementWidth: element.getBoundingClientRect().width,
        wrapperWidth: element.parentElement.getBoundingClientRect().width,
        maximumLineWidth: maximum,
        maximumLine: widths.indexOf(maximum),
        firstLineWidth: widths[0],
        lines: widths.length,
      };
    })
  ));
  const after = await metrics(session);
  const expectedGroup = Math.floor(reference.quantizedWinners[0] / 256);
  report = {
    chrome: await browser.version(),
    elapsedMilliseconds: performance.now() - started,
    expectedWinner: reference.quantizedWinners[0],
    expectedGroup,
    output,
    diagnostics,
    groupCorrect: output.group === expectedGroup,
    elements: await page.locator("*").count(),
    textRuns: await page.locator(".group-grid").count(),
    layoutCount: (after.LayoutCount ?? 0) - (before.LayoutCount ?? 0),
    layoutDurationMilliseconds:
      ((after.LayoutDuration ?? 0) - (before.LayoutDuration ?? 0)) * 1000,
    recalcStyleDurationMilliseconds:
      ((after.RecalcStyleDuration ?? 0) - (before.RecalcStyleDuration ?? 0)) * 1000,
    taskDurationMilliseconds:
      ((after.TaskDuration ?? 0) - (before.TaskDuration ?? 0)) * 1000,
  };
  await context.close();
} finally {
  await browser.close();
}

await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
