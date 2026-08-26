import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = process.env.SVG_CHAIN_URL ??
  "http://127.0.0.1:4178/experiments/svg-filter-full-block";
const casesPath = process.env.SVG_PROMPT_CASES ?? "/tmp/gpt2-css-prompt-cases/cases.json";
const outputPath = process.env.SVG_PROMPT_OUTPUT ?? "/tmp/svg-filter-prompt-robustness.json";
const referencePath = process.env.SVG_CHAIN_REFERENCE ?? new URL(
  "../experiments/svg-filter-full-block/reference.json", import.meta.url,
);
const cases = JSON.parse(await fs.readFile(casesPath, "utf8"));
const reference = JSON.parse(await fs.readFile(referencePath, "utf8"));

async function decode(png) {
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: info.width * info.height }, (_, index) =>
    (data[index * info.channels] / 255 - reference.surface_center) *
      2 * reference.bucket_final_ln_scales[index]
  );
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 200 } });
  await page.goto(`${baseUrl}/bucket-chain-12blocks-final-ln.html?robust=${Date.now()}`, {
    waitUntil: "load", timeout: 180000,
  });
  await page.locator('feImage[href^="bucket-x"]').first().evaluate(
    (element) => element.setAttribute("id", "robustness-input"),
  );
  const outputs = [];
  for (const item of cases.cases) {
    const imagePath = path.join(path.dirname(casesPath), item.image);
    const encoded = (await fs.readFile(imagePath)).toString("base64");
    await page.locator("#robustness-input").evaluate(
      (element, href) => element.setAttribute("href", href),
      `data:image/png;base64,${encoded}`,
    );
    await page.evaluate(() => new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve))
    ));
    const start = performance.now();
    const png = await page.locator("svg").screenshot({ animations: "disabled", timeout: 180000 });
    outputs.push({
      token_id: item.token_id,
      token: item.token,
      milliseconds: performance.now() - start,
      final: await decode(png),
    });
  }
  await fs.writeFile(outputPath, JSON.stringify({ outputs }));
  console.log(JSON.stringify({
    outputPath,
    cases: outputs.length,
    milliseconds: outputs.map((item) => item.milliseconds),
  }, null, 2));
} finally {
  await browser.close();
}
