import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/feature-metric-readback/reference.json", import.meta.url), "utf8"));

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

const errorStats = (values) => {
  const errors = values.map((value, index) => value - reference.expected[index]);
  return {
    finite: values.filter(Number.isFinite).length,
    rmse: Math.sqrt(errors.reduce((sum, error) => sum + error * error, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
    first: values.slice(0, 8),
  };
};

try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 400 } });
  const records = { metric: [], geometry: [] };
  const order = Array.from({ length: 12 }, (_, iteration) =>
    iteration % 2 === 0 ? ["metric", "geometry"] : ["geometry", "metric"]).flat();
  for (let trial = 0; trial < order.length; trial += 1) {
    const kind = order[trial];
    const file = kind === "metric" ? "index" : "geometry";
    const started = performance.now();
    await page.goto(`http://127.0.0.1:4178/experiments/feature-metric-readback/${file}.html?t=${trial}`, {
      waitUntil: "load", timeout: 120000,
    });
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    let values;
    if (kind === "metric") {
      values = await page.evaluate((outputs) => {
        const style = getComputedStyle(document.querySelector("#result"));
        return Array.from({ length: outputs }, (_, index) =>
          Number(style.getPropertyValue(`--o${String(index).padStart(3, "0")}`)));
      }, reference.expected.length);
    } else {
      values = await page.evaluate(({ pairs, base, font_size: fontSize, units_per_em: unitsPerEm }) => {
        const scale = fontSize / unitsPerEm;
        const outputs = [];
        for (let pair = 0; pair < pairs; pair += 1) {
          for (const kind of ["zero", "water"]) {
            const node = document.querySelector(`.${kind}.p${String(pair).padStart(3, "0")}`);
            outputs.push(node.getBoundingClientRect().width / scale - base);
          }
        }
        return outputs;
      }, reference);
    }
    records[kind].push({ milliseconds: performance.now() - started, ...errorStats(values) });
  }
  const summaries = {};
  for (const kind of ["metric", "geometry"]) {
    const warm = records[kind].slice(1).map((record) => record.milliseconds).sort((a, b) => a - b);
    const latest = records[kind].at(-1);
    summaries[kind] = {
      samples: warm.length,
      medianMilliseconds: warm[Math.floor((warm.length - 1) / 2)],
      minMilliseconds: warm[0],
      maxMilliseconds: warm.at(-1),
      finite: latest.finite,
      rmse: latest.rmse,
      maxError: latest.maxError,
      first: latest.first,
    };
  }
  const html = await fs.readFile(
    new URL("../experiments/feature-metric-readback/index.html", import.meta.url), "utf8");
  console.log(JSON.stringify({ noJavaScript: !html.toLowerCase().includes("<script"), summaries }, null, 2));
} finally {
  await browser.close();
}
