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
const referencePath = process.env.SVG_CHAIN_REFERENCE ?? new URL(
  "../experiments/svg-filter-full-block/reference.json", import.meta.url,
);
const outputPath = process.env.SVG_STAGE_OUTPUT ??
  "/tmp/svg-filter-prompt-stages.json";
const targets = new Map(
  (process.env.SVG_STAGE_TARGETS ?? "40:1,257:8,770:1,1212:1,1310:5")
    .split(",").filter(Boolean).map((entry) => entry.split(":").map(Number)),
);
const cases = JSON.parse(await fs.readFile(casesPath, "utf8"));
const reference = JSON.parse(await fs.readFile(referencePath, "utf8"));

function dimensions(horizontalInput, stage) {
  if (stage === 1) return horizontalInput ? [768, 2] : [2, 768];
  if (stage === 2 || stage === 5) return horizontalInput ? [1, 768] : [768, 1];
  if (stage === 3) return horizontalInput ? [2, 768] : [768, 2];
  return horizontalInput ? [3073, 768] : [768, 3073];
}

async function pixels(png) {
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const at = (x, y) => data[(y * info.width + x) * info.channels] / 255;
  return { width: info.width, height: info.height, at };
}

function decode(values, scales) {
  return values.map((value, index) =>
    (value - 128 / 255) * 2 * scales[index]
  );
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 3200, height: 3200 } });
  await page.goto(`${baseUrl}/bucket-chain-12blocks-final-ln.html?stages=${Date.now()}`, {
    waitUntil: "load", timeout: 180000,
  });
  await page.locator('feImage[href^="bucket-x"]').first().evaluate(
    (element) => element.setAttribute("id", "stage-input"),
  );
  const filterUrls = await page.locator("rect").evaluate((element) =>
    [...(element.getAttribute("style") ?? "").matchAll(/url\([^)]*\)/g)].map(
      (match) => match[0],
    )
  );
  const outputs = [];
  for (const item of cases.cases.filter((entry) => targets.has(entry.token_id))) {
    const targetBlock = targets.get(item.token_id);
    const blockIndex = targetBlock - 1;
    const horizontalInput = blockIndex % 2 === 0;
    const specs = reference.bucket_block_specs[blockIndex];
    const inputScales = blockIndex === 0
      ? reference.bucket_input_scales
      : reference.bucket_block_specs[blockIndex - 1].projection_output_scales;
    const imagePath = path.join(path.dirname(casesPath), item.image);
    const encoded = (await fs.readFile(imagePath)).toString("base64");
    await page.locator("#stage-input").evaluate(
      (element, href) => element.setAttribute("href", href),
      `data:image/png;base64,${encoded}`,
    );
    const stages = [];
    for (let stage = 1; stage <= 5; stage += 1) {
      const [width, height] = dimensions(horizontalInput, stage);
      await page.locator("rect").evaluate(
        (element, filter) => element.style.filter = filter,
        filterUrls.slice(0, blockIndex * 5 + stage).join(" "),
      );
      await page.locator("svg").evaluate((element, size) => {
        element.setAttribute("width", String(size.width));
        element.setAttribute("height", String(size.height));
        element.setAttribute("viewBox", `0 0 ${size.width} ${size.height}`);
      }, { width, height });
      await page.evaluate(() => new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve))
      ));
      const png = await page.locator("svg").screenshot({
        animations: "disabled", timeout: 180000,
      });
      const image = await pixels(png);
      let values;
      if (stage === 1) {
        const normal = Array.from({ length: 768 }, (_, i) =>
          horizontalInput ? image.at(i, 0) : image.at(0, i));
        const input = Array.from({ length: 768 }, (_, i) =>
          horizontalInput ? image.at(i, 1) : image.at(1, i));
        values = {
          normalized: decode(normal, specs.ln1_scales),
          input: decode(input, inputScales),
        };
      } else if (stage === 2 || stage === 5) {
        const vector = Array.from({ length: 768 }, (_, i) =>
          horizontalInput ? image.at(0, i) : image.at(i, 0));
        values = {
          [stage === 2 ? "residual" : "output"]: decode(
            vector,
            stage === 2
              ? specs.attention_residual_scales
              : specs.projection_output_scales,
          ),
        };
      } else if (stage === 3) {
        const normal = Array.from({ length: 768 }, (_, i) =>
          horizontalInput ? image.at(0, i) : image.at(i, 0));
        const residual = Array.from({ length: 768 }, (_, i) =>
          horizontalInput ? image.at(1, i) : image.at(i, 1));
        values = {
          normalized: decode(normal, specs.ln2_scales),
          residual: decode(residual, specs.attention_residual_scales),
        };
      } else {
        const hidden = Array.from({ length: 3072 }, (_, i) =>
          horizontalInput ? image.at(i, 0) : image.at(0, i));
        const residual = Array.from({ length: 768 }, (_, i) =>
          horizontalInput ? image.at(3072, i) : image.at(i, 3072));
        values = {
          hidden: decode(hidden, specs.fc_hidden_scales),
          residual: decode(residual, specs.attention_residual_scales),
        };
      }
      stages.push({ stage, values });
    }
    outputs.push({
      token_id: item.token_id,
      token: item.token,
      target_block: targetBlock,
      stages,
    });
  }
  await fs.writeFile(outputPath, JSON.stringify({ outputs }));
  console.log(JSON.stringify({ outputPath, cases: outputs.length }, null, 2));
} finally {
  await browser.close();
}
