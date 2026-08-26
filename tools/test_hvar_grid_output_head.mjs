import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.HVAR_GRID_OUTPUT_HEAD_ROUNDS ?? "7", 10);
const includeEmbedding = process.env.HVAR_GRID_OUTPUT_HEAD_EMBEDDING !== "0";
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/hvar-grid-output-head/reference.json", import.meta.url),
  "utf8",
));

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 800, height: 200 },
  });
  const page = await context.newPage();
  const started = performance.now();
  await page.goto(
    "http://127.0.0.1:4178/experiments/hvar-grid-output-head/index.html",
    { waitUntil: "load", timeout: 180000 },
  );
  await page.evaluate(() => document.fonts.ready);
  if (!includeEmbedding) {
    await page.locator(".feedback-carrier").first().evaluate((element) => {
      element.style.display = "none";
    });
    await page.locator(".feedback-source").evaluateAll((elements) => {
      elements.forEach((element) => { element.style.display = "none"; });
    });
  }
  const loadMilliseconds = performance.now() - started;

  async function read() {
    const token = await page.locator("#result").evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        group: Number(style.getPropertyValue("--group")),
        local: Number(style.getPropertyValue("--local")),
        winner: Number(style.getPropertyValue("--winner")),
        bucket: Number(style.getPropertyValue("--bucket")),
        width: element.getBoundingClientRect().width,
      };
    });
    const embedding = includeEmbedding
      ? await page.locator(".feedback-source").evaluateAll((elements) =>
        elements.map((element) =>
          (element.getBoundingClientRect().width - 20000) / 4096))
      : [];
    const qkv = includeEmbedding
      ? (await page.locator(".qkv-metric").evaluateAll((elements) =>
        elements.map((element) => element.getBoundingClientRect().width)))
        .map((width, dimension) =>
          reference.qkvBase[dimension] +
          (width - 20000) * reference.qkvRowScale[dimension])
      : [];
    return { ...token, embedding, qkv };
  }

  const initial = await read();
  const samples = [];
  for (let index = 0; index < rounds; index += 1) {
    const query = (index + 1) % reference.prompts.length;
    const before = performance.now();
    await page.locator(`#q${query}`).evaluate((element) => { element.checked = true; });
    const output = await read();
    samples.push({
      query,
      milliseconds: performance.now() - before,
      output,
      expectedWinner: reference.quantizedWinners[query],
      denseWinner: reference.denseWinners[query],
      expectedBucket: reference.winnerBuckets[query],
      expectedEmbedding: reference.winnerEmbeddings[query],
    });
  }
  const report = {
    loadMilliseconds,
    includeEmbedding,
    initial,
    expectedInitialWinner: reference.quantizedWinners[0],
    denseInitialWinner: reference.denseWinners[0],
    expectedInitialBucket: reference.winnerBuckets[0],
    mutationMedianMilliseconds: median(samples.map(({ milliseconds }) => milliseconds)),
    settledMutationMedianMilliseconds: median(
      samples.slice(2).map(({ milliseconds }) => milliseconds),
    ),
    mutationMaximumMilliseconds: Math.max(...samples.map(({ milliseconds }) => milliseconds)),
    maximumBucketError: Math.max(
      Math.abs(initial.bucket - reference.winnerBuckets[0]),
      ...samples.map(({ output, expectedBucket }) =>
        Math.abs(output.bucket - expectedBucket)),
    ),
    maximumEmbeddingError: includeEmbedding ? Math.max(
      ...initial.embedding.map((value, dimension) =>
        Math.abs(value - reference.winnerEmbeddings[0][dimension])),
      ...samples.flatMap(({ output, expectedEmbedding }) =>
        output.embedding.map((value, dimension) =>
          Math.abs(value - expectedEmbedding[dimension]))),
    ) : null,
    maximumQkvTransportError: includeEmbedding ? Math.max(
      ...initial.qkv.map((value, dimension) =>
        Math.abs(value - reference.winnerTransportedQkv[0][dimension])),
      ...samples.flatMap(({ output, query }) =>
        output.qkv.map((value, dimension) =>
          Math.abs(value - reference.winnerTransportedQkv[query][dimension]))),
    ) : null,
    maximumQkvDenseError: includeEmbedding ? Math.max(
      ...initial.qkv.map((value, dimension) =>
        Math.abs(value - reference.winnerQkv[0][dimension])),
      ...samples.flatMap(({ output, query }) =>
        output.qkv.map((value, dimension) =>
          Math.abs(value - reference.winnerQkv[query][dimension]))),
    ) : null,
    correct: initial.winner === reference.quantizedWinners[0] &&
      samples.every(({ output, expectedWinner }) => output.winner === expectedWinner),
    denseCorrect: initial.winner === reference.denseWinners[0] &&
      samples.every(({ output, denseWinner }) => output.winner === denseWinner),
    elements: await page.locator("*").count(),
    htmlBytes: (await fs.stat(new URL(
      "../experiments/hvar-grid-output-head/index.html", import.meta.url,
    ))).size,
    cssBytes: (await fs.stat(new URL(
      "../experiments/hvar-grid-output-head/index.css", import.meta.url,
    ))).size,
    fontBytes: reference.fontBytes,
    lookupFontBytes: (await fs.stat(new URL(
      "../experiments/hvar-token-embedding-lookup/embedding-lookup.woff2", import.meta.url,
    ))).size,
    qkvFontBytes: (await fs.stat(new URL(
      "../experiments/hvar-embedding-qkv-chain/qkv.woff2", import.meta.url,
    ))).size,
    samples,
  };
  report.totalRuntimeBytes = report.htmlBytes + report.cssBytes + report.fontBytes +
    report.lookupFontBytes + report.qkvFontBytes;
  await fs.writeFile(
    new URL("../experiments/hvar-grid-output-head/browser-results.json", import.meta.url),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
