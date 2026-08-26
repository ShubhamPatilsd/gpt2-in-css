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
const outputPath = process.env.SVG_BUCKET_ISOLATED_PROFILE_OUTPUT ??
  "/tmp/svg-bucket-stage-isolated-profile.json";
const trials = Math.max(4, Number(process.env.SVG_BUCKET_PROFILE_TRIALS ?? 7));
const stageNames = ["ln1", "attention", "ln2", "fc", "projection"];

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function geometry(block, stage, fullBoundary = false) {
  const horizontal = block % 2 === 0;
  if (!fullBoundary) {
    if (stage === "ln1") return horizontal ? [768, 1] : [1, 768];
    if (stage === "fc") return horizontal ? [3072, 1] : [1, 3072];
    return horizontal ? [1, 768] : [768, 1];
  }
  if (stage === "ln1") return horizontal ? [768, 2] : [2, 768];
  if (stage === "attention") return horizontal ? [1, 768] : [768, 1];
  if (stage === "ln2") return horizontal ? [2, 768] : [768, 2];
  if (stage === "fc") return horizontal ? [3073, 768] : [768, 3073];
  return horizontal ? [1, 768] : [768, 1];
}

function dataUrl(buffer) {
  return `data:image/png;base64,${buffer.toString("base64")}`;
}

function checksum(buffer) {
  return buffer.reduce((sum, value) => (sum + value) >>> 0, 0);
}

async function sizeSvg(page, [width, height]) {
  await page.locator("svg").evaluate((element, size) => {
    element.setAttribute("width", String(size.width));
    element.setAttribute("height", String(size.height));
    element.setAttribute("viewBox", `0 0 ${size.width} ${size.height}`);
  }, { width, height });
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 3200, height: 3200 } });
  const url = `${baseUrl}/bucket-chain-12blocks-final-ln.html?isolated=${Date.now()}`;
  await page.goto(url, { waitUntil: "load", timeout: 180_000 });
  const metadata = await page.locator("filter").evaluateAll((filters) =>
    filters.filter((filter) => /^bucket-k\d+-/.test(filter.id)).map((filter) => ({
      id: filter.id,
      primitiveCount: filter.children.length,
      width: Number(filter.getAttribute("width")),
      height: Number(filter.getAttribute("height")),
    })),
  );
  if (metadata.length !== 60) {
    throw new Error(`expected 60 bucket filters, found ${metadata.length}`);
  }

  const originalInput = page.locator('feImage[href="bucket-x.png"]');
  await originalInput.evaluate((element) => element.setAttribute("id", "profile-model-input"));
  const modelInput = page.locator("#profile-model-input");
  await page.locator("rect").evaluate((rect) => {
    const source = document.createElementNS("http://www.w3.org/2000/svg", "image");
    source.setAttribute("id", "profile-stage-source");
    source.setAttribute("x", "0");
    source.setAttribute("y", "0");
    source.setAttribute("preserveAspectRatio", "none");
    rect.replaceWith(source);
  });
  const source = page.locator("#profile-stage-source");
  await source.evaluate(
    (element) => element.setAttribute("href", "bucket-x.png"),
  );

  let state = [null, null];
  let sourceSize = [768, 1];
  const measurements = [];
  for (let index = 0; index < metadata.length; index += 1) {
    const filter = metadata[index];
    const block = Math.floor(index / stageNames.length);
    const stage = stageNames[index % stageNames.length];
    const first = index === 0;
    await source.evaluate((element, setup) => {
      element.setAttribute("width", String(setup.width));
      element.setAttribute("height", String(setup.height));
      element.style.filter = "none";
    }, { width: sourceSize[0], height: sourceSize[1] });

    if (!first) {
      await source.evaluate(
        (element, href) => element.setAttribute("href", href),
        dataUrl(state[0]),
      );
    }
    await sizeSvg(page, geometry(block, stage));
    await page.locator("svg").screenshot({ animations: "disabled", timeout: 180_000 });

    const baselineSamples = [];
    for (let trial = 0; trial < trials; trial += 1) {
      const variant = trial % 2;
      const href = first
        ? (variant ? "bucket-x.png" : "bucket-x-alt.png")
        : dataUrl(state[variant]);
      const start = performance.now();
      await source.evaluate(
        (element, nextHref) => element.setAttribute("href", nextHref),
        href,
      );
      await page.locator("svg").screenshot({
        animations: "disabled",
        timeout: 180_000,
      });
      baselineSamples.push(performance.now() - start);
    }

    let matrixOnlySamples = null;
    if (stage === "fc") {
      const matrixFilterId = `${filter.id}-matrix-only`;
      await page.locator(`#${filter.id}`).evaluate((fullFilter, setup) => {
        const clone = fullFilter.cloneNode(true);
        clone.id = setup.matrixFilterId;
        const resultName = `k${setup.block}-fc-common`;
        const boundary = [...clone.children].find(
          (child) => child.getAttribute("result") === resultName,
        );
        if (!boundary) throw new Error(`missing ${resultName}`);
        while (boundary.nextSibling) boundary.nextSibling.remove();
        const crop = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "feOffset",
        );
        crop.setAttribute("in", resultName);
        crop.setAttribute("x", "0");
        crop.setAttribute("y", "0");
        crop.setAttribute("width", String(setup.width));
        crop.setAttribute("height", String(setup.height));
        crop.setAttribute(setup.horizontal ? "dy" : "dx", "-255");
        clone.append(crop);
        fullFilter.parentNode.append(clone);
      }, {
        matrixFilterId,
        block,
        horizontal: block % 2 === 0,
        width: geometry(block, stage)[0],
        height: geometry(block, stage)[1],
      });
      await source.evaluate(
        (element, filterId) => { element.style.filter = `url(#${filterId})`; },
        matrixFilterId,
      );
      await page.locator("svg").screenshot({ animations: "disabled", timeout: 180_000 });
      matrixOnlySamples = [];
      for (let trial = 0; trial < trials; trial += 1) {
        const variant = trial % 2;
        const href = first
          ? (variant ? "bucket-x.png" : "bucket-x-alt.png")
          : dataUrl(state[variant]);
        const start = performance.now();
        await source.evaluate(
          (element, nextHref) => element.setAttribute("href", nextHref),
          href,
        );
        await page.locator("svg").screenshot({
          animations: "disabled",
          timeout: 180_000,
        });
        matrixOnlySamples.push(performance.now() - start);
      }
    }

    await source.evaluate(
      (element, filterId) => { element.style.filter = `url(#${filterId})`; },
      filter.id,
    );
    await page.locator("svg").screenshot({ animations: "disabled", timeout: 180_000 });

    const samples = [];
    for (let trial = 0; trial < trials; trial += 1) {
      const variant = trial % 2;
      const start = performance.now();
      if (first) {
        await modelInput.evaluate(
          (element, href) => element.setAttribute("href", href),
          variant ? "bucket-x.png" : "bucket-x-alt.png",
        );
      } else {
        await source.evaluate(
          (element, href) => element.setAttribute("href", href),
          dataUrl(state[variant]),
        );
      }
      await page.locator("svg").screenshot({
        animations: "disabled",
        timeout: 180_000,
      });
      samples.push(performance.now() - start);
    }

    const nextState = [];
    const boundarySize = geometry(block, stage, true);
    await sizeSvg(page, boundarySize);
    for (let variant = 0; variant < 2; variant += 1) {
      if (first) {
        await modelInput.evaluate(
          (element, href) => element.setAttribute("href", href),
          variant ? "bucket-x.png" : "bucket-x-alt.png",
        );
      } else {
        await source.evaluate(
          (element, href) => element.setAttribute("href", href),
          dataUrl(state[variant]),
        );
      }
      nextState.push(await page.locator("svg").screenshot({
        animations: "disabled",
        timeout: 180_000,
      }));
    }
    state = nextState;
    sourceSize = boundarySize;
    measurements.push({
      block: block + 1,
      stage,
      filterId: filter.id,
      primitiveCount: filter.primitiveCount,
      workingPixels: filter.width * filter.height,
      visiblePixels: geometry(block, stage).reduce((a, b) => a * b),
      boundaryPixels: boundarySize.reduce((a, b) => a * b),
      baselineSamples,
      baselineWarmMedianMilliseconds: median(baselineSamples.slice(1)),
      samples,
      warmMedianMilliseconds: median(samples.slice(1)),
      netWarmMedianMilliseconds: Math.max(
        0,
        median(samples.slice(1)) - median(baselineSamples.slice(1)),
      ),
      matrixOnlySamples,
      matrixOnlyWarmMedianMilliseconds: matrixOnlySamples
        ? median(matrixOnlySamples.slice(1))
        : null,
      matrixOnlyNetWarmMedianMilliseconds: matrixOnlySamples
        ? Math.max(
          0,
          median(matrixOnlySamples.slice(1)) - median(baselineSamples.slice(1)),
        )
        : null,
      geluIncrementWarmMedianMilliseconds: matrixOnlySamples
        ? Math.max(0, median(samples.slice(1)) - median(matrixOnlySamples.slice(1)))
        : null,
      outputChecksums: state.map(checksum),
    });
  }

  const byStage = Object.fromEntries(stageNames.map((stage) => {
    const rows = measurements.filter((item) => item.stage === stage);
    const values = rows.map((item) => item.netWarmMedianMilliseconds);
    const total = values.reduce((sum, value) => sum + value, 0);
    return [stage, {
      medianMilliseconds: median(values),
      summedMilliseconds: total,
      shareOfSummedStageTime: 0,
      primitiveCount: rows.reduce((sum, item) => sum + item.primitiveCount, 0),
    }];
  }));
  const total = Object.values(byStage).reduce(
    (sum, item) => sum + item.summedMilliseconds, 0,
  );
  for (const item of Object.values(byStage)) {
    item.shareOfSummedStageTime = item.summedMilliseconds / total;
  }
  const result = { source: url, trials, byStage, measurements };
  await fs.writeFile(outputPath, JSON.stringify(result, null, 2));
  console.log(JSON.stringify({ outputPath, byStage }, null, 2));
} finally {
  await browser.close();
}
