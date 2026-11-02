import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const base = "http://127.0.0.1:4178/experiments/gpt2-block-css";
const cases = [
  {
    name: "block0",
    file: "view-timeline-block-hybrid-packed4-chain-channel89asym-h15.html",
  },
  {
    name: "block1-isolated",
    file: "view-timeline-block1-full-packed4-isolated.html",
  },
  {
    name: "two-block-connected",
    file: "view-timeline-two-block-full-packed4.html",
  },
];

function aggregate(events) {
  const complete = events.filter((event) => event.ph === "X" && event.dur > 0);
  const byName = new Map();
  for (const event of complete) {
    const current = byName.get(event.name) ?? { microseconds: 0, count: 0, maximum: 0 };
    current.microseconds += event.dur;
    current.count += 1;
    current.maximum = Math.max(current.maximum, event.dur);
    byName.set(event.name, current);
  }
  return [...byName.entries()]
    .map(([name, value]) => ({
      name,
      milliseconds: value.microseconds / 1000,
      count: value.count,
      maximumMilliseconds: value.maximum / 1000,
    }))
    .sort((a, b) => b.milliseconds - a.milliseconds)
    .slice(0, 40);
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 400 } });
  for (const testCase of cases) {
    await page.goto(`${base}/${testCase.file}?warm=1`, { waitUntil: "load", timeout: 120000 });
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
  }

  const results = [];
  for (const [index, testCase] of cases.entries()) {
    const session = await page.context().newCDPSession(page);
    const events = [];
    session.on("Tracing.dataCollected", ({ value }) => events.push(...value));
    let completeTrace;
    const traceComplete = new Promise((resolve) => { completeTrace = resolve; });
    session.on("Tracing.tracingComplete", completeTrace);
    await session.send("Tracing.start", {
      transferMode: "ReportEvents",
      categories: [
        "devtools.timeline",
        "blink",
        "blink.animations",
        "blink.user_timing",
        "disabled-by-default-devtools.timeline",
        "disabled-by-default-devtools.timeline.frame",
      ].join(","),
    });
    const started = performance.now();
    await page.goto(`${base}/${testCase.file}?trace=${index}`, {
      waitUntil: "load",
      timeout: 120000,
    });
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const wallMilliseconds = performance.now() - started;
    await session.send("Tracing.end");
    await traceComplete;
    results.push({
      ...testCase,
      wallMilliseconds,
      traceEvents: events.length,
      topCompleteEvents: aggregate(events),
    });
    await session.detach();
  }
  const report = { chrome: await browser.version(), results };
  await fs.writeFile(
    new URL("../experiments/packed-activation-precision/dependency-trace.json", import.meta.url),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
