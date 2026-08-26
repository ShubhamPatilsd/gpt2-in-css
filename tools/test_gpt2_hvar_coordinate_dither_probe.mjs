import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const root = new URL("../experiments/gpt2-hvar-coordinate-dither/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", root), "utf8"));

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ javaScriptEnabled: false });
  const started = performance.now();
  await page.goto(
    "http://127.0.0.1:4178/experiments/gpt2-hvar-coordinate-dither/index.html",
    { waitUntil: "load" },
  );
  await page.evaluate(() => document.fonts.ready);
  const loadMilliseconds = performance.now() - started;
  const samples = await page.locator(".sample").evaluateAll((groups) =>
    groups.map((group) => {
      const values = [...group.querySelectorAll(".candidate")].map((element) => {
        const width = element.getBoundingClientRect().width;
        const base = Number(element.dataset.base);
        const factor = Number(element.dataset.factor);
        return {
          token: Number(element.dataset.token),
          width,
          decoded: (width - base) * factor,
        };
      });
      return {
        phases: Number(group.dataset.phases),
        glyphs: Number(group.dataset.phases) * 12 * values.length,
        decodedDifference11Minus13: values[0].decoded - values[1].decoded,
        winner: values[0].decoded >= values[1].decoded ? 11 : 13,
        values,
      };
    }));
  const report = {
    chrome: await browser.version(),
    loadMilliseconds,
    ...reference,
    samples,
  };
  await fs.writeFile(new URL("browser-results.json", root), `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
