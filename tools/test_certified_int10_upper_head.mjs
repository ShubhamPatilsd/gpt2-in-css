import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const directory = process.env.GPT2_CERTIFIED_HEAD_DIR
  ?? "gpt2-hvar-grid-output-head-certified-upper-int10";
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
  const context = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const page = await context.newPage();
  page.setDefaultTimeout(180000);
  const session = await context.newCDPSession(page);
  await session.send("Performance.enable");
  const before = await metrics(session);
  const started = performance.now();
  await page.goto(url, { waitUntil: "load", timeout: 180000 });
  await page.evaluate(() => document.fonts.ready);
  const loadedMilliseconds = performance.now() - started;

  const samples = [];
  for (let fixture = 0; fixture < reference.allFixtures.hiddenVectors.length; fixture += 1) {
    const fixtureStarted = performance.now();
    await page.locator("#model").evaluate((element, values) => {
      values.hidden.forEach((value, dimension) => {
        element.style.setProperty(`--h${dimension}`, String(value));
      });
      element.style.setProperty(
        "--score-offset",
        `${-values.floor * values.scoreScale * values.scoreStridePx}px`,
      );
    }, {
      hidden: reference.allFixtures.hiddenVectors[fixture],
      floor: reference.allFixtures.scoreFloors[fixture],
      scoreScale: reference.scoreScale,
      scoreStridePx: reference.scoreStridePx,
    });
    for (let pass = 0; pass < 3; pass += 1) {
      await page.locator("#result").evaluate((element) => element.getBoundingClientRect().width);
    }
    const output = await page.locator("#result").evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        group: Number(style.getPropertyValue("--group")),
        winner: Number(style.getPropertyValue("--winner")),
        queryNorm: Number(getComputedStyle(document.querySelector(".group-scroller"))
          .getPropertyValue("--query-norm")),
      };
    });
    samples.push({
      fixture,
      milliseconds: performance.now() - fixtureStarted,
      output,
      expectedUpperWinner: reference.allFixtures.upperWinners[fixture],
      expectedUpperGroup: reference.allFixtures.upperGroups[fixture],
      denseWinner: reference.allFixtures.denseWinners[fixture],
      denseGroup: reference.allFixtures.denseGroups[fixture],
      expectedQueryNorm: reference.allFixtures.queryNorms[fixture],
      upperWinnerCorrect: output.winner === reference.allFixtures.upperWinners[fixture],
      upperGroupCorrect: output.group === reference.allFixtures.upperGroups[fixture],
      queryNormAbsoluteError: Math.abs(
        output.queryNorm - reference.allFixtures.queryNorms[fixture]
      ),
      firstGroupContainsDenseWinner:
        output.group === reference.allFixtures.denseGroups[fixture],
    });
  }
  const after = await metrics(session);
  report = {
    chrome: await browser.version(),
    loadMilliseconds: loadedMilliseconds,
    loadAndFirstEvaluationMilliseconds: loadedMilliseconds + samples[0].milliseconds,
    elapsedMilliseconds: performance.now() - started,
    allUpperWinnersCorrect: samples.every(({ upperWinnerCorrect }) => upperWinnerCorrect),
    allUpperGroupsCorrect: samples.every(({ upperGroupCorrect }) => upperGroupCorrect),
    maximumQueryNormAbsoluteError: Math.max(
      ...samples.map(({ queryNormAbsoluteError }) => queryNormAbsoluteError),
    ),
    firstGroupContainsDenseWinner: samples.filter(
      ({ firstGroupContainsDenseWinner }) => firstGroupContainsDenseWinner
    ).length,
    fixtures: samples.length,
    layoutCount: (after.LayoutCount ?? 0) - (before.LayoutCount ?? 0),
    layoutDurationMilliseconds:
      ((after.LayoutDuration ?? 0) - (before.LayoutDuration ?? 0)) * 1000,
    recalcStyleDurationMilliseconds:
      ((after.RecalcStyleDuration ?? 0) - (before.RecalcStyleDuration ?? 0)) * 1000,
    taskDurationMilliseconds:
      ((after.TaskDuration ?? 0) - (before.TaskDuration ?? 0)) * 1000,
    samples,
  };
  await context.close();
} finally {
  await browser.close();
}

await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
