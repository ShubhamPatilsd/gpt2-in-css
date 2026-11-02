import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";
import fs from "node:fs/promises";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const contexts = (process.env.ATTENTION_CONTEXTS ?? "8,16").split(",").map(Number);
const rounds = Number(process.env.GEOMETRY_SHAPING_ROUNDS ?? 3);
const variant = process.env.GEOMETRY_SHAPING_VARIANT ?? "";
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);
const modes = {
  normal: "",
  "axes-off": 'div[class^="geometry-source-"]{font-variation-settings:normal!important}',
  "system-font": 'div[class^="geometry-source-"]{font-family:monospace!important;font-variation-settings:normal!important}',
};

function median(values) {
  const ordered = values.toSorted((a, b) => a - b);
  return ordered[Math.floor(ordered.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
const trials = [];
try {
  for (const context of contexts) {
    const variantSuffix = variant ? `-${variant}` : "";
    const stem = `attention-context-${context}-geometry-streaming${variantSuffix}-projected`;
    for (const [mode, override] of Object.entries(modes)) {
      for (let round = 0; round < rounds; round += 1) {
        const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
        if (override) {
          await page.route(`**/${stem}-shadow.css*`, async (route) => {
            const response = await route.fetch();
            const body = await response.text();
            await route.fulfill({ response, body: `${body}${override}` });
          });
        }
        const started = performance.now();
        await page.goto(
          `http://127.0.0.1:4178/experiments/gpt2-block-css/${stem}.html?mode=${mode}&round=${round}`,
          { waitUntil: "load", timeout: 180000 },
        );
        const values = await page.locator("#attention-result").evaluate((element) => {
          const styles = getComputedStyle(element);
          return Array.from({ length: 768 }, (_, index) => Number.parseFloat(
            styles.getPropertyValue(`--r1-${String(index).padStart(3, "0")}`),
          ));
        });
        if (values.some((value) => !Number.isFinite(value))) {
          throw new Error(`${context}/${mode} returned non-finite output`);
        }
        trials.push({ context, mode, round, milliseconds: performance.now() - started });
        await page.close();
      }
    }
  }
} finally {
  await browser.close();
}

const summary = {};
for (const context of contexts) {
  summary[context] = {};
  for (const mode of Object.keys(modes)) {
    const selected = trials
      .filter((trial) => trial.context === context && trial.mode === mode)
      .slice(1).map((trial) => trial.milliseconds);
    summary[context][mode] = median(selected);
  }
  summary[context].axisOverhead = summary[context].normal - summary[context]["axes-off"];
  summary[context].customFontOverhead =
    summary[context]["axes-off"] - summary[context]["system-font"];
}
const report = { chrome: await browser.version(), rounds, trials, summary };
await fs.writeFile(
  new URL(`attention-geometry-shaping-profile${variant ? `-${variant}` : ""}.json`, directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(summary, null, 2));
