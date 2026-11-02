import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const contexts = (process.env.ATTENTION_CONTEXTS ?? "16,32").split(",").map(Number);
const rounds = Number(process.env.GEOMETRY_PROJECTION_ROUNDS ?? 4);
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);

function median(values) {
  const ordered = values.toSorted((a, b) => a - b);
  return ordered[Math.floor(ordered.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
const trials = [];
try {
  for (const context of contexts) {
    const stem = `attention-context-${context}-geometry-streaming-flat-siblings-projected`;
    const reference = JSON.parse(await fs.readFile(
      new URL(`${stem}-reference.json`, directory), "utf8",
    ));
    const fixedContext = reference.context.map((value, index) =>
      `--context-${String(index).padStart(3, "0")}:${value}`).join(";");
    for (const mode of ["attention-only", "fixed-projection", "full"]) {
      for (let round = 0; round < rounds; round += 1) {
        const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
        if (mode !== "full") {
          await page.route(`**/${stem}.css*`, async (route) => {
            const response = await route.fetch();
            const body = await response.text();
            const override = mode === "attention-only"
              ? ".geometry-projection{display:none!important}"
              : `.geometry-projection{${fixedContext}}`;
            await route.fulfill({ response, body: `${body}${override}` });
          });
        }
        const started = performance.now();
        await page.goto(
          `http://127.0.0.1:4178/experiments/gpt2-block-css/${stem}.html?mode=${mode}&round=${round}`,
          { waitUntil: "load", timeout: 180000 },
        );
        const selector = mode === "attention-only" ? ".geometry-projection" : "#attention-result";
        const prefix = mode === "attention-only" ? "--context-" : "--r1-";
        const values = await page.locator(selector).evaluate((element, propertyPrefix) => {
          const styles = getComputedStyle(element);
          return Array.from({ length: 768 }, (_, index) => Number.parseFloat(
            styles.getPropertyValue(`${propertyPrefix}${String(index).padStart(3, "0")}`),
          ));
        }, prefix);
        if (values.some((value) => !Number.isFinite(value))) {
          throw new Error(`${context}/${mode} returned non-finite values`);
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
  for (const mode of ["attention-only", "fixed-projection", "full"]) {
    const selected = trials.filter((trial) =>
      trial.context === context && trial.mode === mode).slice(1);
    summary[context][mode] = median(selected.map((trial) => trial.milliseconds));
  }
  summary[context].projectionAndConsumption =
    summary[context].full - summary[context]["attention-only"];
  summary[context].isolatedProjection =
    summary[context]["fixed-projection"] - summary[context]["attention-only"];
  summary[context].liveDependencyPremium =
    summary[context].full - summary[context]["fixed-projection"];
}
const report = { chrome: await browser.version(), rounds, trials, summary };
await fs.writeFile(
  new URL("attention-geometry-flat-siblings-projection-profile.json", directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(summary, null, 2));
