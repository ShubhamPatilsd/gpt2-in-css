import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = process.env.SVG_RGB_PRECISION_URL ??
  "http://127.0.0.1:4178/experiments/svg-rgb-precision-transport/index.html";
const referenceUrl = new URL(
  "../experiments/svg-rgb-precision-transport/reference.json", import.meta.url,
);
const resultsUrl = new URL(
  "../experiments/svg-rgb-precision-transport/results.json", import.meta.url,
);
const reference = JSON.parse(await fs.readFile(referenceUrl, "utf8"));

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
    distinct: new Set(actual.map((value) => value.toFixed(12))).size,
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 200 } });
  const started = performance.now();
  await page.goto(`${url}?run=${Date.now()}`, { waitUntil: "load", timeout: 120000 });
  const loadedMilliseconds = performance.now() - started;
  const png = await page.locator("svg").screenshot({ animations: "disabled", timeout: 120000 });
  const finishedMilliseconds = performance.now() - started;
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const channel = (x, y, c) => data[(y * info.width + x) * info.channels + c];
  const measurements = reference.rows.map(({ checkpoint, planes, row }) => {
    const actual = Array.from({ length: reference.width }, (_, x) => {
      let value = 0;
      for (let channelIndex = 0; channelIndex < planes; channelIndex += 1) {
        value += (channel(x, row, channelIndex) / 255 - reference.center)
          * 2 * reference.planeScales[channelIndex];
      }
      return value;
    });
    return {
      checkpoint,
      planes,
      ...summarize(actual, reference.exact[String(checkpoint)]),
    };
  });
  const report = {
    measurements,
    htmlBytes: reference.htmlBytes,
    loadedMilliseconds,
    screenshotMilliseconds: finishedMilliseconds - loadedMilliseconds,
    totalMilliseconds: finishedMilliseconds,
  };
  await fs.writeFile(resultsUrl, `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
