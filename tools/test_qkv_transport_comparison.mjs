import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/gpt2-block-css/qkv-transport-reference.json", import.meta.url,
), "utf8"));
const rounds = Number(process.env.QKV_TRANSPORT_ROUNDS ?? 5);

function median(values) {
  const ordered = values.toSorted((a, b) => a - b);
  return ordered[Math.floor(ordered.length / 2)];
}

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
let report;
try {
  const variants = {};
  for (const name of [
    "direct", "hvar", "hvar-easing", "hvar-packed7x2", "hvar-packed6x3",
    "hvar-container8x3", "hvar-container10x3f64", "hvar-container12x2",
  ]) {
    const page = await browser.newPage({ viewport: { width: 64, height: 64 } });
    const started = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/gpt2-block-css/qkv-transport-${name}.html`,
      { waitUntil: "load", timeout: 180000 },
    );
    const result = page.locator("#result");
    const read = () => result.evaluate((element, count) => {
      const style = getComputedStyle(element);
      const digits = "0123456789abcdefghijklmnopqrstuvwxyz";
      const base36 = (value) => {
        if (value === 0) return "0";
        let result = "";
        while (value) {
          result = digits[value % 36] + result;
          value = Math.floor(value / 36);
        }
        return result;
      };
      return Array.from({ length: count }, (_, index) => Number.parseFloat(
        style.getPropertyValue(`--o${base36(index)}`),
      ));
    }, reference.outputs);
    if (name.startsWith("hvar")) {
      await page.evaluate(() => new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve))));
    }
    const initial = await read();
    const loadMilliseconds = performance.now() - started;
    const stage = page.locator(name === "direct" ? ".model" : ".stage");
    const trials = [];
    for (let round = 0; round < rounds; round += 1) {
      const caseIndex = round % 2 ? 0 : 1;
      const mutationStarted = performance.now();
      await stage.evaluate((element, values) => {
        const digits = "0123456789abcdefghijklmnopqrstuvwxyz";
        const base36 = (value) => {
          if (value === 0) return "0";
          let result = "";
          while (value) {
            result = digits[value % 36] + result;
            value = Math.floor(value / 36);
          }
          return result;
        };
        values.forEach((value, index) => element.style.setProperty(`--i${base36(index)}`, `${value}`));
      }, reference.inputs[caseIndex]);
      if (name.startsWith("hvar")) {
        await page.evaluate(() => new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve))));
      }
      const actual = await read();
      trials.push({
        round,
        caseIndex,
        milliseconds: performance.now() - mutationStarted,
        ...summarize(actual, reference.expected[caseIndex]),
      });
    }
    variants[name] = {
      page,
      loadMilliseconds,
      initial: summarize(initial, reference.expected[0]),
      trials,
      warmMedianMilliseconds: median(trials.slice(1).map((trial) => trial.milliseconds)),
      rmseMaximum: Math.max(...trials.map((trial) => trial.rmse)),
      maxErrorMaximum: Math.max(...trials.map((trial) => trial.maxError)),
    };
  }
  report = {
    chrome: await browser.version(),
    rounds,
    direct: { ...variants.direct, page: undefined },
    hvar: { ...variants.hvar, page: undefined },
    hvarEasing: { ...variants["hvar-easing"], page: undefined },
    hvarPacked7x2: { ...variants["hvar-packed7x2"], page: undefined },
    hvarPacked6x3: { ...variants["hvar-packed6x3"], page: undefined },
    hvarContainer8x3: { ...variants["hvar-container8x3"], page: undefined },
    hvarContainer10x3F64: { ...variants["hvar-container10x3f64"], page: undefined },
    hvarContainer12x2: { ...variants["hvar-container12x2"], page: undefined },
    directSpeedup: variants.hvar.warmMedianMilliseconds / variants.direct.warmMedianMilliseconds,
    easingSpeedup: variants.hvar.warmMedianMilliseconds /
      variants["hvar-easing"].warmMedianMilliseconds,
    packed7x2Speedup: variants.hvar.warmMedianMilliseconds /
      variants["hvar-packed7x2"].warmMedianMilliseconds,
    packed6x3Speedup: variants.hvar.warmMedianMilliseconds /
      variants["hvar-packed6x3"].warmMedianMilliseconds,
    container8x3Speedup: variants.hvar.warmMedianMilliseconds /
      variants["hvar-container8x3"].warmMedianMilliseconds,
    container10x3F64Speedup: variants.hvar.warmMedianMilliseconds /
      variants["hvar-container10x3f64"].warmMedianMilliseconds,
    container12x2Speedup: variants.hvar.warmMedianMilliseconds /
      variants["hvar-container12x2"].warmMedianMilliseconds,
  };
} finally {
  await browser.close();
}

await fs.writeFile(
  new URL("../experiments/gpt2-block-css/qkv-transport-browser.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
