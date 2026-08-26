import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/ttc-metric-bank/reference.json", import.meta.url), "utf8"));
const staticReference = JSON.parse(await fs.readFile(
  new URL("../experiments/ttc-metric-bank/static-reference.json", import.meta.url), "utf8"));

async function readStaticControl(page) {
  await page.goto("http://127.0.0.1:4178/experiments/ttc-metric-bank/static.html", {
    waitUntil: "load", timeout: 120000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  return page.evaluate((expected) => {
    const style = getComputedStyle(document.querySelector("#result"));
    const values = expected.map((_, index) =>
      Number(style.getPropertyValue(`--s${String(index).padStart(3, "0")}`)));
    const errors = values.map((value, index) => value - expected[index]);
    return {
      expected: expected.slice(0, 8),
      values: values.slice(0, 8),
      rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
      maxError: Math.max(...errors.map(Math.abs)),
    };
  }, staticReference.expected);
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 400 } });
  const staticControl = await readStaticControl(page);
  const trials = [];
  for (let trial = 0; trial < 10; trial += 1) {
    const started = performance.now();
    await page.goto(`http://127.0.0.1:4178/experiments/ttc-metric-bank/index.html?t=${trial}`, {
      waitUntil: "load", timeout: 120000,
    });
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const values = await page.evaluate((count) => {
      const style = getComputedStyle(document.querySelector("#result"));
      return Array.from({ length: count }, (_, index) =>
        Number(style.getPropertyValue(`--o${String(index).padStart(3, "0")}`)));
    }, reference.expected.length);
    trials.push({ milliseconds: performance.now() - started, values });
  }
  const errors = trials.at(-1).values.map((value, index) => value - reference.expected[index]);
  const geometry = await page.evaluate(({ inputs, fontSize }) => {
    const settings = inputs.map((value, index) =>
      `"X${String(index).padStart(3, "0")}" ${value}`).join(",");
    return Array.from({ length: 4 }, (_, pair) => {
      const zero = document.createElement("span");
      const water = document.createElement("span");
      for (const [node, text] of [[zero, "0"], [water, "水"]]) {
        node.textContent = text;
        node.style.cssText = `position:fixed;display:inline-block;font-family:F${pair};` +
          `font-size:${fontSize}px;font-variation-settings:${settings}`;
        document.body.append(node);
      }
      const values = [zero.getBoundingClientRect().width, water.getBoundingClientRect().width];
      zero.remove();
      water.remove();
      return values;
    });
  }, { inputs: reference.inputs, fontSize: reference.font_size });
  const warm = trials.slice(1).map((trial) => trial.milliseconds).sort((a, b) => a - b);
  console.log(JSON.stringify({
    finite: trials.at(-1).values.filter(Number.isFinite).length,
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
    warmMedianMilliseconds: warm[Math.floor(warm.length / 2)],
    trials: trials.map((trial) => trial.milliseconds),
    first: trials.at(-1).values.slice(0, 8),
    geometry,
    staticControl,
  }, null, 2));
} finally {
  await browser.close();
}
