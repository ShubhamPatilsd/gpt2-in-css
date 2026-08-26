import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 300 } });
  const trials = [];
  for (let round = 0; round < 8; round += 1) {
    const names = round % 2 ? ["fourd", "paired"] : ["paired", "fourd"];
    for (const name of names) {
      const started = performance.now();
      await page.goto(
        `http://127.0.0.1:4178/experiments/view-timeline-4d-scale/${name}.html?r=${round}`,
        { waitUntil: "load", timeout: 120000 },
      );
      await page.evaluate(() => new Promise(
        (resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ));
      const values = await page.evaluate(() => {
        const results = [...document.querySelectorAll(".result")].map(getComputedStyle);
        const last = results.at(-1);
        return [
          Number(results[0].getPropertyValue("--v0")),
          Number(results[0].getPropertyValue("--v1")),
          Number(last.getPropertyValue("--v3070")),
          Number(last.getPropertyValue("--v3071")),
        ];
      });
      trials.push({ name, milliseconds: performance.now() - started, values });
    }
  }
  const summary = Object.fromEntries(["paired", "fourd"].map((name) => {
    const values = trials.filter((trial) => trial.name === name).slice(1)
      .map((trial) => trial.milliseconds).sort((a, b) => a - b);
    return [name, { samples: values.length, median: values[Math.floor(values.length / 2)] }];
  }));
  console.log(JSON.stringify({ trials, summary }, null, 2));
} finally {
  await browser.close();
}
