import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const pageName = process.env.SVG_BLUR_REDUCTION_PAGE ?? "blur.html";

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 128, height: 64 } });
  await page.goto(
    `http://127.0.0.1:4178/experiments/svg-fragment-reduction-probe/${pageName}`,
    { waitUntil: "load" },
  );
  const png = await page.locator("body > svg").screenshot();
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const sample = (x) => data[
    ((Math.floor(info.height / 2) * info.width) + x) * info.channels
  ];
  if (pageName === "blur768.html") {
    const samples = [];
    for (const sigma of [64, 128, 256, 384, 500, 512, 768, 1024, 2048, 3072]) {
      await page.locator("feGaussianBlur").evaluate(
        (element, value) => element.setAttribute("stdDeviation", `0 ${value}`),
        sigma,
      );
      const nextPng = await page.locator("body > svg").screenshot();
      const next = await sharp(nextPng).raw().toBuffer({ resolveWithObject: true });
      const offset = ((Math.floor(next.info.height / 2) * next.info.width)
        + Math.floor(next.info.width / 2)) * next.info.channels;
      samples.push({ sigma, blurredOnes: next.data[offset] });
    }
    console.log(JSON.stringify({ samples }, null, 2));
  } else {
    const blurredValues = sample(Math.floor(info.width / 4));
    const blurredOnes = sample(Math.floor(3 * info.width / 4));
    const normalized = blurredOnes ? blurredValues / blurredOnes * 255 : 0;
    console.log(JSON.stringify({
      blurredValues,
      blurredOnes,
      normalized,
      expected: 112,
      error: normalized - 112,
    }, null, 2));
  }
} finally {
  await browser.close();
}
