import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.REGISTERED_HVAR_MLP_ROUNDS ?? "7", 10);
const mode = process.env.REGISTERED_HVAR_MLP_MODE ?? "full";
const containment = process.env.REGISTERED_HVAR_MLP_CONTAIN ?? "none";
const packBits = Number.parseInt(process.env.REGISTERED_HVAR_MLP_BITS ?? "6", 10);
if (!new Set(["full", "gather", "transport", "propagate", "direct"]).has(mode)) {
  throw new Error("REGISTERED_HVAR_MLP_MODE must be full, gather, transport, propagate, or direct");
}
const bitSuffix = packBits === 6 ? "" : `-b${packBits}`;
const stem = `anchor-packed-full-mlp-local-2d${bitSuffix}-hvar-sink`;
const reference = JSON.parse(await fs.readFile(
  new URL(`../experiments/gpt2-block-css/${stem}-reference.json`, import.meta.url),
  "utf8",
));

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function error(actual, expected) {
  const delta = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(delta.reduce((sum, value) => sum + value * value, 0) / delta.length),
    maximum: Math.max(...delta.map(Math.abs)),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 800, height: 200 } });
  const page = await context.newPage();
  const loadStarted = performance.now();
  await page.goto(
    `http://127.0.0.1:4178/experiments/gpt2-block-css/${stem}.xhtml`,
    { waitUntil: "load", timeout: 180000 },
  );
  await page.evaluate(() => document.fonts.ready);
  if (containment !== "none") {
    await page.addStyleTag({
      content: `.packed-carrier{contain:${containment}}`,
    });
  }
  if (mode !== "full") {
    await page.locator(".projection-metric").evaluateAll((elements) => {
      elements.forEach((element) => { element.style.display = "none"; });
    });
  }
  if (mode === "transport" || mode === "propagate") {
    const widths = mode === "propagate" ? reference.progressCodes : reference.sourceWidths;
    await page.locator(".source").evaluateAll((elements, widths) => {
      elements.forEach((element, index) => {
        element.textContent = "";
        element.style.fontFamily = "serif";
        element.style.setProperty("--source-width-0", widths[0][index]);
        element.style.setProperty(
          "--source-width-delta",
          widths[1][index] - widths[0][index],
        );
        element.style.width = "calc((var(--source-width-0) + var(--case) * var(--source-width-delta)) * 1px)";
      });
    }, widths);
    await page.locator("#scope").evaluate((element) => {
      element.style.setProperty("--case", 0);
    });
  }
  if (mode === "propagate") {
    const radix = 64;
    const valuesPerDimension = 4;
    const decoded = (place) => {
      const local = place % valuesPerDimension;
      const size = place >= valuesPerDimension ? "100cqb" : "100cqi";
      if (local === 0) return `mod(round(nearest,${size}/1px,1),${radix})`;
      if (local === valuesPerDimension - 1) {
        return `round(down,${size}/1px/${radix ** local},1)`;
      }
      return `mod(round(down,${size}/1px/${radix ** local},1),${radix})`;
    };
    const rules = [];
    for (let group = 0; group < 384; group += 1) {
      const start = group * 8;
      const digits = Array.from({ length: 8 }, (_value, place) =>
        `--d${place}:round(nearest,anchor-size(--a${String(start + place).padStart(4, "0")} width),1px)`);
      const progress = Array.from({ length: 8 }, (_value, place) =>
        `--p${String(start + place).padStart(4, "0")}:calc(${decoded(place)}/63)`);
      rules.push(`.pack-${group}{${digits.join(";")}}`);
      rules.push(`.decode-${group}{${progress.join(";")}}`);
    }
    await page.addStyleTag({ content: rules.join("") });
  }
  if (mode === "direct") {
    await page.locator("#scope").evaluate((scope, progress) => {
      scope.style.display = "none";
      const result = document.createElement("output");
      result.id = "direct-result";
      for (let index = 0; index < progress[0].length; index += 1) {
        const initial = progress[0][index];
        const delta = progress[1][index] - initial;
        result.style.setProperty(
          `--p${String(index).padStart(4, "0")}`,
          `calc(${initial} + var(--case) * ${delta})`,
        );
      }
      document.body.append(result);
      document.body.style.setProperty("--case", 0);
    }, reference.progress);
  }
  const loadMilliseconds = performance.now() - loadStarted;

  async function read() {
    if (mode !== "full") {
      return page.locator(mode === "direct" ? "#direct-result" : "#result").evaluate((element) => {
        const style = getComputedStyle(element);
        return Array.from({ length: 3072 }, (_value, index) =>
          Number(style.getPropertyValue(`--p${String(index).padStart(4, "0")}`)));
      });
    }
    const widths = await page.locator(".projection-metric").evaluateAll((elements) =>
      elements.map((element) => element.getBoundingClientRect().width));
    return widths.map((width, output) =>
      reference.hvarBase[output] +
      (width * reference.hvarUnitsPerPixel - reference.hvarBaseTotal) *
      reference.hvarScales[output]);
  }

  const initial = await read();
  const samples = [];
  for (let round = 0; round < rounds; round += 1) {
    const caseIndex = (round + 1) % reference.settings.length;
    const started = performance.now();
    if (mode === "transport" || mode === "propagate" || mode === "direct") {
      await page.locator(mode === "direct" ? "body" : "#scope").evaluate((element, value) => {
        element.style.setProperty("--case", value);
      }, caseIndex);
    } else {
      await page.locator("#scope").evaluate((element, value) => {
        element.style.setProperty("--fc-settings", value);
      }, reference.settings[caseIndex]);
    }
    const actual = await read();
    const expectedProgress = mode === "propagate"
      ? reference.progressCodes[caseIndex].map((value) => value / 63)
      : reference.progress[caseIndex];
    const expectedHvar = mode !== "full"
      ? expectedProgress
      : reference.hvarExpected[caseIndex];
    const expectedDense = mode !== "full"
      ? expectedProgress
      : reference.expected[caseIndex];
    samples.push({
      caseIndex,
      milliseconds: performance.now() - started,
      hvarError: error(actual, expectedHvar),
      denseError: error(actual, expectedDense),
      fullPrecisionError: mode === "full"
        ? error(actual, reference.fullPrecisionExpected[caseIndex])
        : null,
    });
  }
  const initialProgress = mode === "propagate"
    ? reference.progressCodes[0].map((value) => value / 63)
    : reference.progress[0];
  const initialHvarError = error(
    initial,
    mode !== "full" ? initialProgress : reference.hvarExpected[0],
  );
  const initialDenseError = error(
    initial,
    mode !== "full" ? initialProgress : reference.expected[0],
  );
  const initialFullPrecisionError = mode === "full"
    ? error(initial, reference.fullPrecisionExpected[0])
    : null;
  const report = {
    mode,
    containment,
    loadMilliseconds,
    mutationMedianMilliseconds: median(samples.map((sample) => sample.milliseconds)),
    settledMutationMedianMilliseconds: median(
      samples.slice(2).map((sample) => sample.milliseconds),
    ),
    hvarRmseMaximum: Math.max(
      initialHvarError.rmse,
      ...samples.map((sample) => sample.hvarError.rmse),
    ),
    hvarMaximumError: Math.max(
      initialHvarError.maximum,
      ...samples.map((sample) => sample.hvarError.maximum),
    ),
    denseRmseMaximum: Math.max(
      initialDenseError.rmse,
      ...samples.map((sample) => sample.denseError.rmse),
    ),
    denseMaximumError: Math.max(
      initialDenseError.maximum,
      ...samples.map((sample) => sample.denseError.maximum),
    ),
    fullPrecisionRmseMaximum: mode === "full" ? Math.max(
      initialFullPrecisionError.rmse,
      ...samples.map((sample) => sample.fullPrecisionError.rmse),
    ) : null,
    fullPrecisionMaximumError: mode === "full" ? Math.max(
      initialFullPrecisionError.maximum,
      ...samples.map((sample) => sample.fullPrecisionError.maximum),
    ) : null,
    groups: reference.groups,
    packBits: reference.packBits,
    elements: await page.locator("*").count(),
    cssBytes: reference.cssBytes,
    htmlBytes: reference.htmlBytes,
    hvarFontBytes: reference.hvarFontBytes,
    diagnostics: await page.locator(mode === "direct" ? "#direct-result" : "#result").evaluate((element) => {
      const style = getComputedStyle(element);
      const variation = style.fontVariationSettings;
      return {
        variationCount: [...variation.matchAll(/"X[A-Z0-9]{3}"/g)].length,
        firstProgress: style.getPropertyValue("--p0000").trim(),
        middleProgress: style.getPropertyValue("--p1536").trim(),
        lastProgress: style.getPropertyValue("--p3071").trim(),
      };
    }),
  };
  await fs.writeFile(
    new URL(`../experiments/gpt2-block-css/${stem}-browser-${mode}.json`, import.meta.url),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
