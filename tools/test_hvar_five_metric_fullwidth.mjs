import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const experiment = new URL("../experiments/hvar-five-metric-fullwidth/", import.meta.url);
const ref = JSON.parse(await fs.readFile(new URL("reference.json", experiment), "utf8"));

function errorStats(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    actual,
    expected,
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

try {
  const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
  const navigationTimes = [];
  let actual = [];
  for (let index = 0; index < 10; index++) {
    const started = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/hvar-five-metric-fullwidth/index.html?t=${index}`,
      { waitUntil: "load", timeout: 120_000 },
    );
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    actual = await page.evaluate(() => {
      const style = getComputedStyle(document.querySelector("#result"));
      return Array.from({ length: 5 }, (_, index) =>
        Number(style.getPropertyValue(`--o${index}`)));
    });
    navigationTimes.push(performance.now() - started);
  }

  const mutation = await page.evaluate(({ inputs, weights }) => {
    const root = document.querySelector(".root");
    const target = document.querySelector("#result");
    const read = () => {
      const style = getComputedStyle(target);
      return Array.from({ length: 5 }, (_, index) =>
        Number(style.getPropertyValue(`--o${index}`)));
    };

    let checksum = 0;
    const started = performance.now();
    for (let index = 0; index < 1_000; index++) {
      root.style.setProperty("--v000", index % 2 ? "-0.8" : "0.8");
      checksum += read()[index % 5];
    }
    const oneAxisMilliseconds = (performance.now() - started) / 1_000;
    const next = [...inputs];
    next[0] = -0.8;
    const oneAxisExpected = weights.map((row) =>
      row.reduce((sum, weight, index) => sum + weight * next[index], 0));
    const oneAxisActual = read();

    let randomState = 0x51f15e;
    const random = () => {
      randomState = (Math.imul(randomState, 1_664_525) + 1_013_904_223) >>> 0;
      return randomState / 0x1_0000_0000;
    };
    const channelSquared = Array(5).fill(0);
    const channelMax = Array(5).fill(0);
    const trials = 32;
    const fullStarted = performance.now();
    for (let trial = 0; trial < trials; trial++) {
      const vector = Array.from({ length: inputs.length }, () => random() * 1.8 - 0.9);
      root.style.cssText = vector
        .map((value, index) => `--v${String(index).padStart(3, "0")}:${value}`)
        .join(";");
      const observed = read();
      for (let channel = 0; channel < 5; channel++) {
        const expected = weights[channel].reduce(
          (sum, weight, index) => sum + weight * vector[index], 0);
        const error = observed[channel] - expected;
        channelSquared[channel] += error * error;
        channelMax[channel] = Math.max(channelMax[channel], Math.abs(error));
      }
    }
    const fullVectorMilliseconds = (performance.now() - fullStarted) / trials;
    return {
      oneAxisActual,
      oneAxisExpected,
      oneAxisMilliseconds,
      fullVectorMilliseconds,
      checksum,
      randomTrials: trials,
      perChannelRmse: channelSquared.map((sum) => Math.sqrt(sum / trials)),
      perChannelMaxError: channelMax,
    };
  }, ref);

  const warm = navigationTimes.slice(1).sort((left, right) => left - right);
  const runtimeHtml = await fs.readFile(new URL("index.html", experiment), "utf8");
  const results = {
    noJavaScript: !runtimeHtml.toLowerCase().includes("<script"),
    channels: ref.channels,
    initial: errorStats(actual, ref.expected),
    oneAxisMutation: errorStats(mutation.oneAxisActual, mutation.oneAxisExpected),
    randomVectors: {
      trials: mutation.randomTrials,
      perChannelRmse: mutation.perChannelRmse,
      perChannelMaxError: mutation.perChannelMaxError,
    },
    warmNavigationMedianMilliseconds: warm[Math.floor((warm.length - 1) / 2)],
    oneAxisMutationMilliseconds: mutation.oneAxisMilliseconds,
    fullVectorMutationMilliseconds: mutation.fullVectorMilliseconds,
    webFontBytes: ref.font_bytes,
    sfntBytes: ref.sfnt_bytes,
    htmlBytes: ref.html_bytes,
  };
  await fs.writeFile(
    new URL("browser-results.json", experiment),
    `${JSON.stringify(results, null, 2)}\n`,
  );
  console.log(JSON.stringify(results, null, 2));
} finally {
  await browser.close();
}
