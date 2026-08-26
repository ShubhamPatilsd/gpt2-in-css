import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const experiment = new URL("../experiments/font-metric-chain-probe/", import.meta.url);
const ref = JSON.parse(await fs.readFile(new URL("reference.json", experiment), "utf8"));
const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

const base = "http://127.0.0.1:4178/experiments/font-metric-chain-probe";
const pages = ["registered", "unregistered", "direct", "font-size", "calc-size"];
const results = {};
const next = [0.2, -0.5, 0.9, 0.1, -0.3];
const nextIntermediate = ref.first_weights.map((row) =>
  row.reduce((sum, weight, index) => sum + weight * next[index], 0));
const nextExpected = ref.second_weights.reduce(
  (sum, weight, index) => sum + weight * nextIntermediate[index], 0);
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 300 } });
  for (const name of pages) {
    const started = performance.now();
    await page.goto(`${base}/${name}.html`, { waitUntil: "load" });
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    results[name] = await page.evaluate(() => {
      const result = document.querySelector("#result");
      const style = getComputedStyle(result);
      return {
        z: Number(style.getPropertyValue("--z")),
        metrics: Array.from({ length: 5 }, (_, index) =>
          style.getPropertyValue(`--m${index}`).trim()),
        fontVariationSettings: style.fontVariationSettings,
        fontSize: style.fontSize,
      };
    });
    results[name].navigationMilliseconds = performance.now() - started;
    if (["registered", "unregistered", "direct"].includes(name)) {
      results[name].afterMutation = await page.evaluate((values) => {
        const root = document.querySelector(".root");
        values.forEach((value, index) => root.style.setProperty(`--x${index}`, value));
        const style = getComputedStyle(document.querySelector("#result"));
        return {
          z: Number(style.getPropertyValue("--z")),
          fontVariationSettings: style.fontVariationSettings,
        };
      }, next);
      results[name].afterMutation.expected = nextExpected;
      results[name].afterMutation.error = results[name].afterMutation.z - nextExpected;
    }
  }

  await page.goto(`${base}/registered.html`, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  const mutation = await page.evaluate((values) => {
    const root = document.querySelector(".root");
    const result = document.querySelector("#result");
    const started = performance.now();
    let checksum = 0;
    for (let trial = 0; trial < 1_000; trial++) {
      for (let index = 0; index < values.length; index++) {
        root.style.setProperty(`--x${index}`, trial % 2 ? values[index] : -values[index]);
      }
      checksum += Number(getComputedStyle(result).getPropertyValue("--z"));
    }
    for (let index = 0; index < values.length; index++) {
      root.style.setProperty(`--x${index}`, values[index]);
    }
    return {
      millisecondsPerUpdate: (performance.now() - started) / 1_000,
      actual: Number(getComputedStyle(result).getPropertyValue("--z")),
      metrics: Array.from({ length: 5 }, (_, index) =>
        Number(getComputedStyle(result).getPropertyValue(`--m${index}`))),
      checksum,
    };
  }, next);
  results.registered.expected = ref.expected;
  results.registered.error = results.registered.z - ref.expected;
  results.registered.mutation = {
    ...mutation,
    expected: nextExpected,
    error: mutation.actual - nextExpected,
    expectedIntermediate: nextIntermediate,
  };
  results["font-size"].expected = ref.font_size_expected_input;
  results["font-size"].error = results["font-size"].z - ref.font_size_expected_input;
  for (const name of pages) {
    const html = await fs.readFile(new URL(`${name}.html`, experiment), "utf8");
    results[name].noJavaScript = !html.toLowerCase().includes("<script");
  }
  await fs.writeFile(
    new URL("browser-results.json", experiment),
    `${JSON.stringify(results, null, 2)}\n`,
  );
  console.log(JSON.stringify(results, null, 2));
} finally {
  await browser.close();
}
