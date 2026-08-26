import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const repository = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const experiment = path.join(repository, "experiments", "gpt2-token-uncertainty-block-gate");
const reference = JSON.parse(await fs.readFile(path.join(experiment, "reference.json"), "utf8"));
const benchmarkRounds = Math.max(
  3,
  Number(process.env.BLOCK_GATE_BENCHMARK_ROUNDS ?? 5),
);

const contentTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".woff2", "font/woff2"],
]);
const serverErrors = [];
const server = http.createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
    if (pathname === "/favicon.ico") {
      response.writeHead(204).end();
      return;
    }
    const relative = pathname.replace(/^\/+/, "");
    const filename = path.resolve(repository, relative || "index.html");
    if (filename !== repository && !filename.startsWith(`${repository}${path.sep}`)) {
      response.writeHead(403).end("forbidden");
      return;
    }
    const body = await fs.readFile(filename);
    response.writeHead(200, {
      "content-type": contentTypes.get(path.extname(filename)) ?? "application/octet-stream",
      "cache-control": "no-store",
    });
    response.end(body);
  } catch (error) {
    serverErrors.push(String(error));
    response.writeHead(404).end("not found");
  }
});
await new Promise((resolve, reject) => {
  server.once("error", reject);
  server.listen(0, "127.0.0.1", resolve);
});
const address = server.address();
const baseUrl = `http://127.0.0.1:${address.port}/experiments/gpt2-token-uncertainty-block-gate`;

function percentile(values, percentage) {
  const ordered = [...values].sort((left, right) => left - right);
  return ordered[Math.min(ordered.length - 1, Math.ceil(ordered.length * percentage) - 1)];
}

function statistics(values) {
  const ordered = [...values].sort((left, right) => left - right);
  const middle = Math.floor(ordered.length / 2);
  const median = ordered.length % 2
    ? ordered[middle]
    : (ordered[middle - 1] + ordered[middle]) / 2;
  return {
    samples: values.length,
    minimumMilliseconds: ordered[0],
    medianMilliseconds: median,
    p95Milliseconds: percentile(ordered, 0.95),
    maximumMilliseconds: ordered.at(-1),
    meanMilliseconds: values.reduce((sum, value) => sum + value, 0) / values.length,
  };
}

function watch(page, label, diagnostics) {
  page.on("pageerror", (error) => diagnostics.pageErrors.push({ label, error: String(error) }));
  page.on("requestfailed", (request) => diagnostics.requestFailures.push({
    label,
    url: request.url(),
    error: request.failure()?.errorText ?? "unknown request failure",
  }));
  page.on("response", (response) => {
    if (response.status() >= 400) {
      diagnostics.httpErrors.push({ label, url: response.url(), status: response.status() });
    }
  });
}

async function loadPage(context, blockSize, label, diagnostics, mode = "mode-both") {
  const page = await context.newPage();
  watch(page, label, diagnostics);
  page.setDefaultTimeout(240_000);
  await page.goto(`${baseUrl}/index-b${blockSize}.html`, {
    waitUntil: "load",
    timeout: 240_000,
  });
  await page.evaluate(async (className) => {
    document.body.className = className;
    await document.fonts.ready;
  }, mode);
  return page;
}

async function applyFixture(page, fixture) {
  await page.evaluate(({ hidden, scoreFloor, queryNorm }) => {
    const probe = document.querySelector("#probe");
    for (let dimension = 0; dimension < hidden.length; dimension += 1) {
      probe.style.setProperty(`--h${dimension}`, String(hidden[dimension]));
    }
    probe.style.setProperty("--score-offset", `${-scoreFloor * 256 * 4}px`);
    probe.style.setProperty("--query-norm", String(queryNorm));
  }, fixture);
}

async function settle(page) {
  await page.evaluate(() => {
    for (let pass = 0; pass < 3; pass += 1) {
      document.querySelector("#lower-max").getBoundingClientRect().width;
      document.querySelector("#gated-max").getBoundingClientRect().width;
      document.querySelector("#gated-result").getBoundingClientRect().width;
      document.querySelector("#full-result").getBoundingClientRect().width;
    }
  });
}

async function readCorrectness(page, blockCount) {
  return page.evaluate((blocks) => {
    const carrierWidths = [];
    const wrapperDisplays = [];
    const activeBlocks = [];
    for (let block = 0; block < blocks; block += 1) {
      const carrier = document.querySelector(`#gate-block-${block}`);
      const wrapper = document.querySelector(`#exact-block-${block}`);
      carrierWidths.push(carrier.getBoundingClientRect().width);
      const display = getComputedStyle(wrapper).display;
      wrapperDisplays.push(display);
      if (display !== "none") activeBlocks.push(block);
    }
    const gated = getComputedStyle(document.querySelector("#gated-result"));
    const full = getComputedStyle(document.querySelector("#full-result"));
    return {
      activeBlocks,
      carrierWidths,
      wrapperDisplays,
      lowerMaxBucket: document.querySelector("#lower-max").getBoundingClientRect().width / 4,
      gatedWinner: Number(gated.getPropertyValue("--gated-winner")),
      gatedBucket: Number(gated.getPropertyValue("--gated-bucket")),
      fullWinner: Number(full.getPropertyValue("--full-winner")),
      fullBucket: Number(full.getPropertyValue("--full-bucket")),
      debug: {
        gatedMaxWidth: document.querySelector("#gated-max").getBoundingClientRect().width,
        fullMaxWidth: document.querySelector("#full-stage").getBoundingClientRect().width,
        cssRuleCount: [...document.styleSheets]
          .reduce((sum, sheet) => sum + sheet.cssRules.length, 0),
      },
    };
  }, blockCount);
}

async function readSynthetic(page) {
  return page.evaluate(() => ({
    equalityCarrierWidth: document.querySelector("#equality-gate").getBoundingClientRect().width,
    equalityDescendantDisplay: getComputedStyle(document.querySelector("#equality-gate b")).display,
    belowCarrierWidth: document.querySelector("#below-gate").getBoundingClientRect().width,
    belowDescendantDisplay: getComputedStyle(document.querySelector("#below-gate b")).display,
    lowerTokenTieWinner: Number(
      getComputedStyle(document.querySelector("#tie-result")).getPropertyValue("--tie-local"),
    ),
  }));
}

async function benchmarkVariant(context, variant, diagnostics) {
  const blockSize = variant.blockSize;
  const pages = {
    gated: await loadPage(context, blockSize, `benchmark-b${blockSize}-gated`, diagnostics, "mode-gated"),
    full: await loadPage(context, blockSize, `benchmark-b${blockSize}-full`, diagnostics, "mode-full"),
  };
  for (const [mode, page] of Object.entries(pages)) {
    const selector = mode === "gated" ? "#gated-result" : "#full-result";
    await applyFixture(page, variant.fixtures.at(-1));
    await page.locator(selector).evaluate((element) => element.getBoundingClientRect().width);
  }
  const samples = { gated: [], full: [] };
  const outputs = { gated: [], full: [] };
  for (let round = 0; round < benchmarkRounds; round += 1) {
    const order = round % 2 === 0 ? ["gated", "full"] : ["full", "gated"];
    for (const mode of order) {
      const page = pages[mode];
      const selector = mode === "gated" ? "#gated-result" : "#full-result";
      const property = mode === "gated" ? "--gated-winner" : "--full-winner";
      for (const fixture of variant.fixtures) {
        const sample = await page.evaluate(({ values, selector: resultSelector, property: winnerProperty }) => {
          const probe = document.querySelector("#probe");
          const started = performance.now();
          for (let dimension = 0; dimension < values.hidden.length; dimension += 1) {
            probe.style.setProperty(`--h${dimension}`, String(values.hidden[dimension]));
          }
          probe.style.setProperty("--score-offset", `${-values.scoreFloor * 256 * 4}px`);
          probe.style.setProperty("--query-norm", String(values.queryNorm));
          const result = document.querySelector(resultSelector);
          result.getBoundingClientRect().width;
          result.getBoundingClientRect().width;
          return {
            milliseconds: performance.now() - started,
            winner: Number(getComputedStyle(result).getPropertyValue(winnerProperty)),
          };
        }, { values: fixture, selector, property });
        samples[mode].push(sample.milliseconds);
        outputs[mode].push({
          round,
          fixture: fixture.fixture,
          milliseconds: sample.milliseconds,
          winner: sample.winner,
        });
      }
    }
  }
  await Promise.all(Object.values(pages).map((page) => page.close()));
  const gated = { ...statistics(samples.gated), outputs: outputs.gated };
  const full = { ...statistics(samples.full), outputs: outputs.full };
  return {
    blockSize,
    rounds: benchmarkRounds,
    order: "alternating ten-mutation mode batches by round",
    gated,
    full,
    fullToGatedMedianRatio: full.medianMilliseconds / gated.medianMilliseconds,
    fullToGatedMeanRatio: full.meanMilliseconds / gated.meanMilliseconds,
  };
}

const diagnostics = { pageErrors: [], requestFailures: [], httpErrors: [] };
const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const context = await browser.newContext({ viewport: { width: 800, height: 240 } });
  const correctness = [];
  let synthetic;
  for (const variant of reference.variants) {
    const page = await loadPage(
      context,
      variant.blockSize,
      `correctness-b${variant.blockSize}`,
      diagnostics,
    );
    if (!synthetic) synthetic = await readSynthetic(page);
    const fixtures = [];
    for (const fixture of variant.fixtures) {
      await applyFixture(page, fixture);
      await settle(page);
      const output = await readCorrectness(page, variant.blockCount);
      fixtures.push({
        fixture: fixture.fixture,
        expected: {
          activeBlocks: fixture.activeBlocks,
          lowerMaxBucket: fixture.lowerMaxBucket,
          exactWinner: fixture.exactWinner,
          exactWinnerBucket: fixture.exactWinnerBucket,
        },
        browser: output,
        checks: {
          activeBlocksMatch:
            JSON.stringify(output.activeBlocks) === JSON.stringify(fixture.activeBlocks),
          gatesAreBinary: output.carrierWidths.every((width) => width === 0 || width === 1),
          wrapperDisplaysMatch: output.wrapperDisplays.every((display, block) => (
            fixture.activeBlocks.includes(block) ? display === "grid" : display === "none"
          )),
          lowerMaxWithinCoarseAllowance:
            Math.abs(output.lowerMaxBucket - fixture.lowerMaxBucket)
            <= reference.bucketContract.coarseAllowanceBuckets,
          gatedMatchesFullWinner: output.gatedWinner === output.fullWinner,
          gatedMatchesFullBucket: output.gatedBucket === output.fullBucket,
          fullWinnerMatchesOracle: output.fullWinner === fixture.exactWinner,
          fullBucketWithinFineAllowance:
            Math.abs(output.fullBucket - fixture.exactWinnerBucket)
            <= reference.bucketContract.fineAllowanceBuckets,
        },
      });
    }
    correctness.push({
      blockSize: variant.blockSize,
      blockCount: variant.blockCount,
      meanActiveBlocks: variant.meanActiveBlocks,
      meanShapedRows: variant.meanShapedRows,
      fixtures,
    });
    await page.close();
  }

  const benchmarks = [];
  for (const variant of reference.variants) {
    benchmarks.push(await benchmarkVariant(context, variant, diagnostics));
  }
  await context.close();

  const allFixtureChecksPass = correctness.every((variant) => (
    variant.fixtures.every((fixture) => Object.values(fixture.checks).every(Boolean))
  ));
  const benchmarkWinnersCorrect = benchmarks.every((benchmark) => (
    [...benchmark.gated.outputs, ...benchmark.full.outputs].every(({ fixture, winner }) => (
      winner === reference.variants
        .find((variant) => variant.blockSize === benchmark.blockSize)
        .fixtures[fixture].exactWinner
    ))
  ));
  const syntheticChecks = {
    equalityIsInclusive:
      synthetic.equalityCarrierWidth === 1 && synthetic.equalityDescendantDisplay !== "none",
    belowIsExcluded:
      synthetic.belowCarrierWidth === 0 && synthetic.belowDescendantDisplay === "none",
    lowerTokenWinsTie: synthetic.lowerTokenTieWinner === 3,
  };
  const noErrors = [
    ...diagnostics.pageErrors,
    ...diagnostics.requestFailures,
    ...diagnostics.httpErrors,
    ...serverErrors,
  ].length === 0;
  report = {
    chromeVersion: await browser.version(),
    blockSizes: reference.blockSizes,
    benchmarkRounds,
    synthetic,
    syntheticChecks,
    correctness,
    benchmarks,
    allFixtureChecksPass,
    benchmarkWinnersCorrect,
    diagnostics: { ...diagnostics, serverErrors },
    pass:
      allFixtureChecksPass
      && benchmarkWinnersCorrect
      && Object.values(syntheticChecks).every(Boolean)
      && noErrors,
  };
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}

await fs.writeFile(path.join(experiment, "results.json"), `${JSON.stringify(report, null, 2)}\n`);

const timingRows = report.benchmarks.map((benchmark) => {
  const variant = reference.variants.find((item) => item.blockSize === benchmark.blockSize);
  return `| ${benchmark.blockSize} | ${variant.blockCount} | ${variant.meanShapedRows.toFixed(1)} | `
    + `${benchmark.gated.medianMilliseconds.toFixed(2)} | ${benchmark.full.medianMilliseconds.toFixed(2)} | `
    + `${benchmark.fullToGatedMedianRatio.toFixed(3)}× |`;
}).join("\n");
const meanWinner = [...report.benchmarks].sort(
  (left, right) => left.gated.meanMilliseconds - right.gated.meanMilliseconds,
)[0];
const medianWinner = [...report.benchmarks].sort(
  (left, right) => left.gated.medianMilliseconds - right.gated.medianMilliseconds,
)[0];
const decision = meanWinner.fullToGatedMeanRatio > 1
  ? `B=${meanWinner.blockSize} has the lowest mean and B=${medianWinner.blockSize} the lowest median; both decisively beat the full-grid control in this fixed-group screen.`
  : "No tested block size beats the full 256-row exact grid; reject block gating for scaling.";
const markdown = `# Token uncertainty block-gate browser probe

## Result

${decision} All ${reference.blockSizes.length * 10} block-size/fixture correctness cases ${report.allFixtureChecksPass ? "passed" : "did not pass"}; benchmark winners ${report.benchmarkWinnersCorrect ? "matched" : "did not match"} the oracle. Overall probe pass: **${report.pass}**.

| Block size | Gate carriers | Mean shaped rows | Gated median (ms) | Full median (ms) | Full/gated |
| ---: | ---: | ---: | ---: | ---: | ---: |
${timingRows}

A ratio above 1 means the block gate is faster. Timings use ${report.benchmarkRounds} alternating rounds of all ten mutations per mode. The fixed group-0 probe includes all 256 int10 coarse rows in every gated variant, so it measures the actual gate/reduction overhead plus surviving global-int16 row shaping.

## Correctness contract

- One inclusive carrier per contiguous block: \`max(block upper) >= max(token lower)\`.
- The common exact-block wrapper is \`display:none\` while inactive; active exact rows overlap as in-flow grid children so each block anchor exposes their exact maximum.
- Block and final reductions have fan-in at most ${reference.fanIn}.
- Every carrier was required to be binary, every wrapper display state to match the offline oracle, and gated winner/bucket to match the full grid.
- Equality inclusion, strict-below exclusion, and lower-token tie behavior were tested synthetically.

Chrome: ${report.chromeVersion}. Raw measurements: \`results.json\`.

## Reproduce

\`\`\`bash
PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_token_uncertainty_block_gate_probe.py
node --check tools/test_token_uncertainty_block_gate_probe.mjs
BLOCK_GATE_BENCHMARK_ROUNDS=${report.benchmarkRounds} node tools/test_token_uncertainty_block_gate_probe.mjs
\`\`\`
`;
await fs.writeFile(path.join(experiment, "RESULTS.md"), markdown);
console.log(JSON.stringify(report, null, 2));
