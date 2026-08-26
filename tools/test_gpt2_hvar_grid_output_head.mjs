import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const rounds = Number.parseInt(process.env.GPT2_HVAR_GRID_HEAD_ROUNDS ?? "7", 10);
const headDirectory = process.env.GPT2_HVAR_GRID_HEAD_DIR ??
  "gpt2-hvar-grid-output-head";
const referenceUrl = new URL(
  `../experiments/${headDirectory}/reference.json`,
  import.meta.url,
);
const reference = JSON.parse(await fs.readFile(referenceUrl, "utf8"));

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
    `http://127.0.0.1:4178/experiments/${headDirectory}/index.html`,
    { waitUntil: "load", timeout: 180000 },
  );
  await page.evaluate(() => document.fonts.ready);

  const read = () => page.locator("#result").evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      group: Number(style.getPropertyValue("--group")),
      local: Number(style.getPropertyValue("--local")),
      winner: Number(style.getPropertyValue("--winner")),
      bucket: Number(style.getPropertyValue("--bucket")),
      width: element.getBoundingClientRect().width,
    };
  });

  const initial = await read();
  const candidateDiagnostics = await page.locator(
    ".candidate, .group-grid > i",
  ).evaluateAll(
    (elements, tokens) => tokens.map((token) => {
      const element = elements[token];
      const before = element.style.width;
      element.style.setProperty("width", "max-content", "important");
      const intrinsicWidth = element.getBoundingClientRect().width;
      if (before) element.style.width = before;
      else element.style.removeProperty("width");
      const style = getComputedStyle(element);
      return {
        token,
        intrinsicWidth,
        computedWidth: style.width,
        base: element.style.getPropertyValue("--base"),
        factor: element.style.getPropertyValue("--factor"),
        textCodePoints: Array.from(element.textContent).map((value) =>
          value.codePointAt(0)),
      };
    }),
    [0, 11, 477],
  );
  const layoutDiagnostics = await page.evaluate(() => {
    const model = document.querySelector(".model");
    const groups = [0, 1, 196].map((index) => {
      const wrapper = document.querySelectorAll(".group-wrapper")[index];
      const grid = wrapper.querySelector(".group-grid");
      return {
        index,
        wrapperLeft: wrapper.getBoundingClientRect().left,
        wrapperTop: wrapper.getBoundingClientRect().top,
        wrapperGridArea: getComputedStyle(wrapper).gridArea,
        wrapperWidth: wrapper.getBoundingClientRect().width,
        wrapperComputedWidth: getComputedStyle(wrapper).width,
        gridWidth: grid.getBoundingClientRect().width,
        gridComputedWidth: getComputedStyle(grid).width,
      };
    });
    return {
      modelDisplay: getComputedStyle(model).display,
      modelGridTemplateColumns: getComputedStyle(model).gridTemplateColumns,
      modelWidth: model.getBoundingClientRect().width,
      modelComputedWidth: getComputedStyle(model).width,
      groups,
    };
  });
  const loadMilliseconds = performance.now() - started;
  const samples = [];
  for (let round = 0; round < rounds + 2; round += 1) {
    const query = (round + 1) % 2;
    const before = performance.now();
    await page.locator(`#q${query}`).evaluate((element) => { element.checked = true; });
    const output = await read();
    samples.push({
      round,
      query,
      milliseconds: performance.now() - before,
      output,
      expectedWinner: reference.quantizedWinners[query],
      denseWinner: reference.denseWinners[query],
      expectedBucket: reference.winnerBuckets[query],
    });
  }
  const validationSamples = [];
  for (let fixture = 0; fixture < reference.validation.hiddenVectors.length; fixture += 1) {
    const before = performance.now();
    await page.locator("#model").evaluate((element, values) => {
      values.hidden.forEach((value, dimension) => {
        element.style.setProperty(`--h${dimension}`, String(value));
      });
      element.style.setProperty(
        "--score-offset",
        `${-values.floor * values.scoreScale * values.scoreStridePx}px`,
      );
    }, {
      hidden: reference.validation.hiddenVectors[fixture],
      floor: reference.validation.scoreFloors[fixture],
      scoreScale: reference.scoreScale,
      scoreStridePx: reference.scoreStridePx,
    });
    const output = await read();
    validationSamples.push({
      fixture,
      inputToken: reference.validation.tokenIds[fixture],
      milliseconds: performance.now() - before,
      output,
      expectedWinner: reference.validation.quantizedWinners[fixture],
      denseWinner: reference.validation.denseWinners[fixture],
      expectedBucket: reference.validation.winnerBuckets[fixture],
    });
  }
  const measured = samples.slice(2);
  const validationCorrect = validationSamples.every(
    ({ output, expectedWinner }) => output.winner === expectedWinner,
  );
  const validationDenseCorrect = validationSamples.every(
    ({ output, denseWinner }) => output.winner === denseWinner,
  );
  const report = {
    chrome: await browser.version(),
    rounds,
    loadMilliseconds,
    initial,
    candidateDiagnostics,
    layoutDiagnostics,
    expectedInitialWinner: reference.quantizedWinners[0],
    denseInitialWinner: reference.denseWinners[0],
    settledMutationMedianMilliseconds: median(
      measured.map(({ milliseconds }) => milliseconds),
    ),
    settledMutationMinimumMilliseconds: Math.min(
      ...measured.map(({ milliseconds }) => milliseconds),
    ),
    settledMutationMaximumMilliseconds: Math.max(
      ...measured.map(({ milliseconds }) => milliseconds),
    ),
    maximumBucketError: Math.max(
      Math.abs(initial.bucket - reference.winnerBuckets[0]),
      ...samples.map(({ output, expectedBucket }) =>
        Math.abs(output.bucket - expectedBucket)),
      ...validationSamples.map(({ output, expectedBucket }) =>
        Math.abs(output.bucket - expectedBucket)),
    ),
    correct: initial.winner === reference.quantizedWinners[0] &&
      samples.every(({ output, expectedWinner }) => output.winner === expectedWinner) &&
      validationCorrect,
    denseCorrect: initial.winner === reference.denseWinners[0] &&
      samples.every(({ output, denseWinner }) => output.winner === denseWinner) &&
      validationDenseCorrect,
    validationCorrect,
    validationDenseCorrect,
    validationMutationMedianMilliseconds: median(
      validationSamples.map(({ milliseconds }) => milliseconds),
    ),
    elements: await page.locator("*").count(),
    htmlBytes: reference.htmlBytes,
    cssBytes: reference.cssBytes,
    fontBytes: reference.fontBytes,
    totalRuntimeBytes: reference.htmlBytes + reference.cssBytes + reference.fontBytes,
    samples,
    validationSamples,
  };
  await fs.writeFile(
    new URL(
      `../experiments/${headDirectory}/browser-results.json`,
      import.meta.url,
    ),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
