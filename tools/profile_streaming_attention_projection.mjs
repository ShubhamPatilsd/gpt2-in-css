import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number(process.env.ATTENTION_PROJECTION_ROUNDS ?? 3);
const contexts = (process.env.ATTENTION_CONTEXTS ?? "8,16").split(",").map(Number);
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);

function median(values) {
  const sorted = values.toSorted((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
const trials = [];
try {
  for (const context of contexts) {
    const stem = `attention-context-${context}-qkv-streaming-key-anchor`;
    const source = await fs.readFile(new URL(`${stem}.html`, directory), "utf8");
    for (const mode of ["attention-only", "full"]) {
      for (let round = 0; round < rounds; round += 1) {
        const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
        const started = performance.now();
        if (mode === "attention-only") {
          const base = `<base href="http://127.0.0.1:4178/experiments/gpt2-block-css/">`;
          const override = "<style>.projection-stage{display:none!important}</style>";
          await page.setContent(`${base}${override}${source}`, {
            waitUntil: "load", timeout: 180000,
          });
          const bank = (context - 1) % 2 === 0 ? "a" : "b";
          const values = await page.locator(".finalize").evaluate((element, activeBank) => {
            const styles = getComputedStyle(element);
            return Array.from({ length: 768 }, (_, index) => Number.parseFloat(
              styles.getPropertyValue(`--acc-${activeBank}-${String(index).padStart(3, "0")}`),
            ));
          }, bank);
          if (values.some((value) => !Number.isFinite(value))) {
            throw new Error(`${context}-token attention state is non-finite`);
          }
        } else {
          await page.goto(
            `http://127.0.0.1:4178/experiments/gpt2-block-css/${stem}.html?profile=${round}`,
            { waitUntil: "load", timeout: 180000 },
          );
          const values = await page.locator("#attention-result").evaluate((element) => {
            const styles = getComputedStyle(element);
            return Array.from({ length: 768 }, (_, index) => Number.parseFloat(
              styles.getPropertyValue(`--r1-${String(index).padStart(3, "0")}`),
            ));
          });
          if (values.some((value) => !Number.isFinite(value))) {
            throw new Error(`${context}-token projected state is non-finite`);
          }
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
  for (const mode of ["attention-only", "full"]) {
    const values = trials
      .filter((trial) => trial.context === context && trial.mode === mode)
      .slice(1).map((trial) => trial.milliseconds);
    summary[context][mode] = median(values);
  }
  summary[context].projectionAndConsumption =
    summary[context].full - summary[context]["attention-only"];
}
const report = { chrome: await browser.version(), rounds, trials, summary };
await fs.writeFile(
  new URL("attention-streaming-projection-profile.json", directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(summary, null, 2));
