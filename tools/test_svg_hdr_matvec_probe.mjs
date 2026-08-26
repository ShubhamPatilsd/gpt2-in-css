import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const sharp = require(`${root}/sharp`);
const reference = JSON.parse(await fs.readFile(new URL(
  "../experiments/svg-hdr-matvec/reference.json", import.meta.url,
), "utf8"));
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const profiles = (process.env.SVG_HDR_PROFILES ?? "srgb,scrgb-linear,hdr10").split(",");

function srgbToLinear(value) {
  return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
}

function summarize(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

const profilesResult = [];
for (const profile of profiles) {
  const browser = await chromium.launch({
    executablePath,
    headless: true,
    args: [`--force-color-profile=${profile}`],
  });
  try {
    const page = await browser.newPage({ viewport: { width: 32, height: 128 } });
    await page.goto(
      `http://127.0.0.1:4178/experiments/svg-hdr-matvec/index.html?${Date.now()}`,
      { waitUntil: "load" },
    );
    await page.locator("svg").screenshot();
    const timings = [];
    let png;
    for (let trial = 0; trial < 5; trial += 1) {
      const started = performance.now();
      png = await page.locator("svg").screenshot();
      timings.push(performance.now() - started);
    }
    const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
    const columns = Array.from({ length: 3 }, (_, column) =>
      Array.from({ length: reference.width }, (_, row) => {
        const encoded = data[(row * info.width + column) * info.channels] / 255;
        const filterValue = column === 0 ? encoded : srgbToLinear(encoded);
        return (filterValue - 0.5) * 2 * reference.outputBound;
      }));
    profilesResult.push({
      profile,
      warmScreenshotMilliseconds: timings,
      medianMilliseconds: timings.slice().sort((a, b) => a - b)[Math.floor(timings.length / 2)],
      sdr: {
        versusFloat: summarize(columns[0], reference.expectedFloat),
        computeOnly: summarize(columns[0], reference.expectedSdrEncoded),
      },
      hdr: {
        versusFloat: summarize(columns[1], reference.expectedFloat),
        computeOnly: summarize(columns[1], reference.expectedHdrEncoded),
      },
      hdrDirectKernel: {
        versusFloat: summarize(columns[2], reference.expectedFloat),
        computeOnly: summarize(columns[2], reference.expectedHdrDirect),
      },
    });
  } finally {
    await browser.close();
  }
}

const result = { encoding: {
  hdrLinearRange: reference.hdrLinearRange,
  hdrUniqueCodesInput: reference.hdrUniqueCodesInput,
  hdrUniqueCodesWeights: reference.hdrUniqueCodesWeights,
  sdrUniqueCodesInput: reference.sdrUniqueCodesInput,
  sdrUniqueCodesWeights: reference.sdrUniqueCodesWeights,
}, profiles: profilesResult };
console.log(JSON.stringify(result, null, 2));
await fs.writeFile(
  new URL("../experiments/svg-hdr-matvec/results.json", import.meta.url),
  `${JSON.stringify(result, null, 2)}\n`,
);
