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
const casesPath = process.env.SVG_PROMPT_CASES ??
  "/tmp/gpt2-css-prompt-cases/cases.json";
const outputPath = process.env.SVG_BOUNDARY_OUTPUT ??
  "/tmp/svg-filter-prompt-boundaries.json";
const referencePath = process.env.SVG_CHAIN_REFERENCE ?? new URL(
  "../experiments/svg-filter-full-block/reference.json", import.meta.url,
);
const selected = new Set(
  (process.env.SVG_BOUNDARY_TOKEN_IDS ?? "40,257,770,1212,1310")
    .split(",").filter(Boolean).map(Number),
);
const cases = JSON.parse(await fs.readFile(casesPath, "utf8"));
const reference = JSON.parse(await fs.readFile(referencePath, "utf8"));

async function decode(png, scales) {
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  return Array.from({ length: 768 }, (_, index) =>
    (data[index * info.channels] / 255 - 128 / 255) * 2 * scales[index]
  );
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 900 } });
  await page.goto(`${baseUrl}/bucket-chain-12blocks-final-ln.html?boundaries=${Date.now()}`, {
    waitUntil: "load", timeout: 180000,
  });
  await page.locator('feImage[href^="bucket-x"]').first().evaluate(
    (element) => element.setAttribute("id", "boundary-input"),
  );
  const filterUrls = await page.locator("rect").evaluate((element) =>
    [...(element.getAttribute("style") ?? "").matchAll(/url\([^)]*\)/g)].map(
      (match) => match[0],
    )
  );
  if (filterUrls.length < 60) {
    throw new Error(`Expected at least 60 block filters, found ${filterUrls.length}`);
  }

  const outputs = [];
  for (const item of cases.cases.filter((entry) => selected.has(entry.token_id))) {
    const imagePath = path.join(path.dirname(casesPath), item.image);
    const encoded = (await fs.readFile(imagePath)).toString("base64");
    await page.locator("#boundary-input").evaluate(
      (element, href) => element.setAttribute("href", href),
      `data:image/png;base64,${encoded}`,
    );
    const blocks = [];
    for (let block = 1; block <= 12; block += 1) {
      const vertical = block % 2 === 1;
      await page.locator("rect").evaluate(
        (element, filter) => element.style.filter = filter,
        filterUrls.slice(0, block * 5).join(" "),
      );
      await page.locator("svg").evaluate((element, dimensions) => {
        element.setAttribute("width", String(dimensions.width));
        element.setAttribute("height", String(dimensions.height));
        element.setAttribute("viewBox", `0 0 ${dimensions.width} ${dimensions.height}`);
      }, { width: vertical ? 1 : 768, height: vertical ? 768 : 1 });
      await page.evaluate(() => new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve))
      ));
      const start = performance.now();
      const png = await page.locator("svg").screenshot({
        animations: "disabled", timeout: 180000,
      });
      blocks.push({
        block,
        milliseconds: performance.now() - start,
        state: await decode(
          png,
          reference.bucket_block_specs?.[block - 1]?.projection_output_scales ??
            cases.block_output_scales[block - 1],
        ),
      });
    }
    outputs.push({ token_id: item.token_id, token: item.token, blocks });
  }
  await fs.writeFile(outputPath, JSON.stringify({ outputs }));
  console.log(JSON.stringify({ outputPath, cases: outputs.length }, null, 2));
} finally {
  await browser.close();
}
