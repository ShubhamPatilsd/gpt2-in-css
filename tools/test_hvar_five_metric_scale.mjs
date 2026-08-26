import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const experiment = new URL("../experiments/hvar-five-metric-scale/", import.meta.url);
const ref = JSON.parse(await fs.readFile(new URL("reference.json", experiment), "utf8"));
const baseUrl = "http://127.0.0.1:4178/experiments/hvar-five-metric-scale";

function summarize(samples, channels) {
  const squared = Array(channels).fill(0);
  const maxima = Array(channels).fill(0);
  let count = 0;
  for (const errors of samples) {
    for (let index = 0; index < errors.length; index++) {
      const channel = index % channels;
      squared[channel] += errors[index] ** 2;
      maxima[channel] = Math.max(maxima[channel], Math.abs(errors[index]));
      count++;
    }
  }
  const perChannelCount = count / channels;
  return {
    rmse: Math.sqrt(squared.reduce((sum, value) => sum + value, 0) / count),
    maxError: Math.max(...maxima),
    perChannelRmse: squared.map((value) => Math.sqrt(value / perChannelCount)),
    perChannelMaxError: maxima,
  };
}

async function measureMode(mode) {
  const metadata = ref.modes[mode];
  const channels = metadata.channels.length;
  const browser = await chromium.launch({
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: true,
  });
  try {
    const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
    page.setDefaultTimeout(120_000);
    const readOutputs = async () => page.evaluate(({ channels, outputs }) => {
      const values = [];
      for (const result of document.querySelectorAll(".result")) {
        const style = getComputedStyle(result);
        for (let channel = 0; channel < channels && values.length < outputs; channel++) {
          values.push(Number(style.getPropertyValue(`--o${channel}`)));
        }
      }
      return values;
    }, { channels, outputs: 768 });
    const navigate = async (suffix) => {
      const started = performance.now();
      await page.goto(`${baseUrl}/${mode}.html?run=${suffix}`, {
        waitUntil: "load",
        timeout: 120_000,
      });
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      });
      const actual = await readOutputs();
      return { milliseconds: performance.now() - started, actual };
    };

    const cold = await navigate("cold");
    const warm = [];
    for (let index = 0; index < 3; index++) warm.push(await navigate(`warm-${index}`));
    const warmTimes = warm.map((run) => run.milliseconds).sort((a, b) => a - b);
    const initialTrueErrors = cold.actual.map(
      (value, index) => value - ref.expected_true[0][index]);
    const initialQuantizedErrors = cold.actual.map(
      (value, index) => value - ref.expected_quantized[0][index]);

    const mutation = await page.evaluate(
      ({ channels, vectors, expectedTrue, expectedQuantized, oneAxis }) => {
        const root = document.querySelector(".root");
        const read = () => {
          const values = [];
          for (const result of document.querySelectorAll(".result")) {
            const style = getComputedStyle(result);
            for (let channel = 0; channel < channels && values.length < 768; channel++) {
              values.push(Number(style.getPropertyValue(`--o${channel}`)));
            }
          }
          return values;
        };

        const oneAxisTrueErrors = [];
        const oneAxisQuantizedErrors = [];
        const oneAxisStarted = performance.now();
        for (let trial = 0; trial < 10; trial++) {
          const value = trial % 2 ? -0.8 : 0.8;
          root.style.setProperty("--v000", value);
          const actual = read();
          const expected = oneAxis[String(value)];
          oneAxisTrueErrors.push(actual.map((observed, index) => observed - expected.true[index]));
          oneAxisQuantizedErrors.push(
            actual.map((observed, index) => observed - expected.quantized[index]));
        }
        const oneAxisMilliseconds = (performance.now() - oneAxisStarted) / 10;

        const vectorTrueErrors = [];
        const vectorQuantizedErrors = [];
        const times = [];
        for (let trial = 0; trial < vectors.length; trial++) {
          const started = performance.now();
          root.style.cssText = vectors[trial].map((value, index) =>
            `--v${String(index).padStart(3, "0")}:${value}`).join(";");
          const actual = read();
          times.push(performance.now() - started);
          vectorTrueErrors.push(
            actual.map((observed, index) => observed - expectedTrue[trial][index]));
          vectorQuantizedErrors.push(
            actual.map((observed, index) => observed - expectedQuantized[trial][index]));
        }
        return {
          oneAxisTrueErrors,
          oneAxisQuantizedErrors,
          oneAxisMilliseconds,
          vectorTrueErrors,
          vectorQuantizedErrors,
          fullVectorTimes: times,
        };
      },
      {
        channels,
        vectors: ref.normalized_vectors,
        expectedTrue: ref.expected_true,
        expectedQuantized: ref.expected_quantized,
        oneAxis: ref.one_axis,
      },
    );

    const cdp = await browser.newBrowserCDPSession();
    const processInfo = await cdp.send("SystemInfo.getProcessInfo");
    const pids = processInfo.processInfo.map((process) => String(process.id));
    let chromeRssBytes = null;
    try {
      const rss = execFileSync("ps", ["-o", "rss=", "-p", pids.join(",")], { encoding: "utf8" });
      chromeRssBytes = rss.trim().split(/\s+/).filter(Boolean)
        .reduce((sum, kibibytes) => sum + Number(kibibytes) * 1024, 0);
    } catch {
      // RSS is best-effort.
    }
    const session = await page.context().newCDPSession(page);
    const dom = await session.send("Memory.getDOMCounters");
    const pageFacts = await page.evaluate(() => ({
      elements: document.querySelectorAll("*").length,
      groups: document.querySelectorAll(".group").length,
      results: document.querySelectorAll(".result").length,
      loadedFonts: document.fonts.size,
    }));
    const fullVectorTimes = [...mutation.fullVectorTimes].sort((a, b) => a - b);
    const realIndices = ref.vector_kinds
      .map((kind, index) => kind.startsWith("token-") ? index : -1).filter((index) => index >= 0);
    const randomIndices = ref.vector_kinds
      .map((kind, index) => kind.startsWith("random-") ? index : -1).filter((index) => index >= 0);
    return {
      channels: metadata.channels,
      groups: metadata.groups,
      fontCount: metadata.font_count,
      noJavaScript: !(await fs.readFile(new URL(`${mode}.html`, experiment), "utf8"))
        .toLowerCase().includes("<script"),
      coldNavigationMilliseconds: cold.milliseconds,
      warmNavigationMedianMilliseconds: warmTimes[Math.floor(warmTimes.length / 2)],
      oneAxisMutationAndReadAllMilliseconds: mutation.oneAxisMilliseconds,
      fullVectorMutationAndReadAllMedianMilliseconds:
        fullVectorTimes[Math.floor(fullVectorTimes.length / 2)],
      accuracyAgainstTrue: {
        initial: summarize([initialTrueErrors], channels),
        oneAxis: summarize(mutation.oneAxisTrueErrors, channels),
        realVectors: summarize(realIndices.map((index) => mutation.vectorTrueErrors[index]), channels),
        randomVectors: summarize(randomIndices.map((index) => mutation.vectorTrueErrors[index]), channels),
      },
      browserRoundingAgainstQuantized: {
        initial: summarize([initialQuantizedErrors], channels),
        oneAxis: summarize(mutation.oneAxisQuantizedErrors, channels),
        allVectors: summarize(mutation.vectorQuantizedErrors, channels),
      },
      webFontBytes: metadata.web_font_bytes,
      expandedSfntBytes: metadata.sfnt_bytes,
      htmlBytes: metadata.html_bytes,
      chromeRssBytes,
      domCounters: dom,
      page: pageFacts,
    };
  } finally {
    await browser.close();
  }
}

const results = {
  matrix: ref.matrix,
  weightQuantizationRmse: ref.weight_quantization_rmse,
  weightQuantizationMaxError: ref.weight_quantization_max_error,
  five: await measureMode("five"),
  four: await measureMode("four"),
};
await fs.writeFile(
  new URL("browser-results.json", experiment),
  `${JSON.stringify(results, null, 2)}\n`,
);
console.log(JSON.stringify(results, null, 2));
