import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);

const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = process.env.SVG_BUCKET_PROFILE_URL ??
  "http://127.0.0.1:4178/experiments/svg-filter-full-block";
const outputPath = process.env.SVG_BUCKET_PROFILE_OUTPUT ??
  "/tmp/svg-bucket-stage-profile.json";
const trials = Math.max(4, Number(process.env.SVG_BUCKET_PROFILE_TRIALS ?? 7));
const stages = ["ln1", "attention", "ln2", "fc", "projection"];

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function visibleSize(block, stage) {
  const horizontal = block % 2 === 0;
  if (stage === "ln1") return horizontal ? [768, 1] : [1, 768];
  if (stage === "fc") return horizontal ? [3072, 1] : [1, 3072];
  return horizontal ? [1, 768] : [768, 1];
}

function summarizeIncrements(measurements) {
  let previous = 0;
  const increments = measurements.map((measurement) => {
    const milliseconds = measurement.warmMedianMilliseconds - previous;
    previous = measurement.warmMedianMilliseconds;
    return {
      block: measurement.block,
      stage: measurement.stage,
      milliseconds,
      primitiveCount: measurement.primitiveCount,
      workingPixels: measurement.workingPixels,
    };
  });
  const byStage = Object.fromEntries(stages.map((stage) => {
    const rows = increments.filter((item) => item.stage === stage);
    const positive = rows.map((item) => Math.max(0, item.milliseconds));
    return [stage, {
      estimatedTotalMilliseconds: positive.reduce((sum, value) => sum + value, 0),
      estimatedMedianBlockMilliseconds: median(positive),
      primitiveCount: rows.reduce((sum, item) => sum + item.primitiveCount, 0),
      workingPixels: rows.reduce((sum, item) => sum + item.workingPixels, 0),
    }];
  }));
  const estimatedTotal = Object.values(byStage).reduce(
    (sum, item) => sum + item.estimatedTotalMilliseconds, 0,
  );
  for (const item of Object.values(byStage)) {
    item.estimatedShare = estimatedTotal
      ? item.estimatedTotalMilliseconds / estimatedTotal
      : 0;
  }
  return { increments, byStage };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 3200, height: 3200 } });
  const url = `${baseUrl}/bucket-chain-12blocks-final-ln.html?profile=${Date.now()}`;
  await page.goto(url, { waitUntil: "load", timeout: 180_000 });

  const filterMetadata = await page.locator("filter").evaluateAll((filters) =>
    filters.map((filter) => ({
      id: filter.id,
      primitiveCount: filter.children.length,
      width: Number(filter.getAttribute("width")),
      height: Number(filter.getAttribute("height")),
    })),
  );
  const chain = filterMetadata.filter((item) => /^bucket-k\d+-/.test(item.id));
  if (chain.length !== 60) {
    throw new Error(`expected 60 bucket filters, found ${chain.length}`);
  }
  const initialInput = page.locator('feImage[href="bucket-x.png"]');
  if (await initialInput.count() !== 1) {
    throw new Error(`expected one mutable bucket input, found ${await initialInput.count()}`);
  }
  await initialInput.evaluate((element) => element.setAttribute("id", "profile-input"));
  const input = page.locator("#profile-input");

  const measurements = [];
  for (let cutoff = 1; cutoff <= chain.length; cutoff += 1) {
    const block = Math.floor((cutoff - 1) / stages.length);
    const stage = stages[(cutoff - 1) % stages.length];
    const [width, height] = visibleSize(block, stage);
    await page.locator("rect").evaluate((element, ids) => {
      element.style.filter = ids.map((id) => `url(#${id})`).join(" ");
    }, chain.slice(0, cutoff).map((item) => item.id));
    await page.locator("svg").evaluate((element, size) => {
      element.setAttribute("width", String(size.width));
      element.setAttribute("height", String(size.height));
      element.setAttribute("viewBox", `0 0 ${size.width} ${size.height}`);
    }, { width, height });

    await page.locator("svg").screenshot({ animations: "disabled", timeout: 180_000 });
    const samples = [];
    for (let trial = 0; trial < trials; trial += 1) {
      const href = trial % 2 === 0 ? "bucket-x-alt.png" : "bucket-x.png";
      const start = performance.now();
      await input.evaluate(
        (element, nextHref) => element.setAttribute("href", nextHref),
        href,
      );
      await page.locator("svg").screenshot({
        animations: "disabled",
        timeout: 180_000,
      });
      samples.push(performance.now() - start);
    }
    const warm = samples.slice(1);
    const filter = chain[cutoff - 1];
    measurements.push({
      cutoff,
      block: block + 1,
      stage,
      filterId: filter.id,
      primitiveCount: filter.primitiveCount,
      workingPixels: filter.width * filter.height,
      visiblePixels: width * height,
      samples,
      warmMedianMilliseconds: median(warm),
    });
  }

  const full = measurements.at(-1).warmMedianMilliseconds;
  const result = {
    source: url,
    trials,
    fullChainWarmMedianMilliseconds: full,
    ...summarizeIncrements(measurements),
    measurements,
  };
  await fs.writeFile(outputPath, JSON.stringify(result, null, 2));
  console.log(JSON.stringify({
    outputPath,
    fullChainWarmMedianMilliseconds: full,
    byStage: result.byStage,
  }, null, 2));
} finally {
  await browser.close();
}
