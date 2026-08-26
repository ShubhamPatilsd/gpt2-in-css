import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const context = Number(process.env.ATTENTION_CONTEXT ?? 16);
const rounds = Number(process.env.GEOMETRY_CONTAINMENT_ROUNDS ?? 4);
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);
const stem = `attention-context-${context}-geometry-streaming-flat-siblings-projected`;
const reference = JSON.parse(await fs.readFile(
  new URL(`${stem}-reference.json`, directory), "utf8",
));
const modes = {
  none: "",
  size: "contain:size",
  layout: "contain:layout",
  style: "contain:style",
  "size-layout-style": "contain:size layout style",
};

function median(values) {
  const ordered = values.toSorted((a, b) => a - b);
  return ordered[Math.floor(ordered.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
const trials = [];
try {
  for (const [mode, declaration] of Object.entries(modes)) {
    for (let round = 0; round < rounds; round += 1) {
      const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
      if (declaration) {
        await page.route(`**/${stem}-shadow.css*`, async (route) => {
          const response = await route.fetch();
          const body = await response.text();
          await route.fulfill({
            response,
            body: `${body}div[class^="geometry-source-"]{${declaration}}`,
          });
        });
      }
      const started = performance.now();
      await page.goto(
        `http://127.0.0.1:4178/experiments/gpt2-block-css/${stem}.html?mode=${mode}&round=${round}`,
        { waitUntil: "load", timeout: 180000 },
      );
      const actual = await page.locator("#attention-result").evaluate((element) => {
        const styles = getComputedStyle(element);
        return Array.from({ length: 768 }, (_, index) => Number.parseFloat(
          styles.getPropertyValue(`--r1-${String(index).padStart(3, "0")}`),
        ));
      });
      const errors = actual.map((value, index) => value - reference.residual[index]);
      trials.push({
        mode,
        round,
        milliseconds: performance.now() - started,
        finite: actual.every(Number.isFinite),
        rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
      });
      await page.close();
    }
  }
} finally {
  await browser.close();
}

const summary = {};
for (const mode of Object.keys(modes)) {
  const selected = trials.filter((trial) => trial.mode === mode);
  summary[mode] = {
    warmMedianMilliseconds: median(selected.slice(1).map((trial) => trial.milliseconds)),
    rmseMaximum: Math.max(...selected.map((trial) => trial.rmse)),
    allFinite: selected.every((trial) => trial.finite),
  };
}
const report = { chrome: await browser.version(), context, rounds, trials, summary };
await fs.writeFile(
  new URL(`attention-geometry-containment-${context}.json`, directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(summary, null, 2));
