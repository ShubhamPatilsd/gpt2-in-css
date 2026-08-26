import fs from "node:fs/promises";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const directory = new URL(
  "../experiments/gpt2-four-block-event-scheduler/",
  import.meta.url,
);
const reference = JSON.parse(await fs.readFile(
  new URL("view-timeline-four-block-reference.json", directory),
  "utf8",
));
const rounds = Number(process.env.FOUR_BLOCK_COLD_ROUNDS ?? 1);
const baseUrl = process.env.FOUR_BLOCK_BASE_URL ?? "http://127.0.0.1:4178";

const boundaries = [
  { layer: 0, selector: "#four-block-boundary-h0", prefix: "--out-" },
  { layer: 1, selector: "#four-block-boundary-h1", prefix: "--b1-final-" },
  { layer: 2, selector: "#four-block-boundary-h2", prefix: "--b2-final-" },
  { layer: 3, selector: "#four-block-boundary-h3", prefix: "--b3-final-" },
];
const variants = [
  { name: "connected", file: "view-timeline-four-block-connected.html" },
  { name: "staged", file: "view-timeline-four-block-staged.html" },
];

function errorSummary(actual, expected) {
  const delta = actual.map((value, index) => value - expected[index]);
  return {
    finite: actual.every(Number.isFinite),
    rmse: Math.sqrt(delta.reduce((sum, value) => sum + value * value, 0) / delta.length),
    maxError: Math.max(...delta.map(Math.abs)),
  };
}

function maxDifference(left, right) {
  return Math.max(...left.map((value, index) => Math.abs(value - right[index])));
}

async function readVector(page, selector, prefix) {
  return page.locator(selector).evaluate((element, propertyPrefix) => {
    const style = getComputedStyle(element);
    return Array.from({ length: 768 }, (_, index) => Number(
      style.getPropertyValue(`${propertyPrefix}${String(index).padStart(3, "0")}`),
    ));
  }, prefix);
}

async function settle(page, staged = false) {
  if (staged) {
    await page.waitForFunction(
      () => document.querySelector("#four-block-signal-b3")?.classList.contains("ready"),
      null,
      { timeout: 180000 },
    );
  }
  await page.evaluate(async () => {
    await document.fonts.ready;
    for (let frame = 0; frame < 6; frame += 1) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
    }
  });
}

async function ensureServer() {
  try {
    const response = await fetch(`${baseUrl}/`, { signal: AbortSignal.timeout(1500) });
    if (response.ok) return null;
  } catch {
    // Start a local static server below.
  }
  const server = spawn(
    "python3",
    ["-m", "http.server", "4178", "--bind", "127.0.0.1"],
    { cwd: root, stdio: "ignore" },
  );
  for (let attempt = 0; attempt < 30; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 100));
    try {
      const response = await fetch(`${baseUrl}/`, { signal: AbortSignal.timeout(500) });
      if (response.ok) return server;
    } catch {
      // Retry while the server starts.
    }
  }
  server.kill();
  throw new Error("could not start the four-block fixture server");
}

const server = await ensureServer();
const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

const report = {
  diagnostic: reference.diagnostic,
  chrome: await browser.version(),
  rounds,
  isolated: {},
  trials: [],
  gates: {},
};

try {
  // Build an isolated per-layer browser reference while preserving propagated
  // browser error: h.0 browser output feeds isolated h.1, then h.2, then h.3.
  const isolatedPage = await browser.newPage({ viewport: { width: 1000, height: 400 } });
  await isolatedPage.goto(
    `${baseUrl}/experiments/gpt2-block-css/view-timeline-block-hybrid-global-projection-easing.html`,
    { waitUntil: "load", timeout: 180000 },
  );
  await isolatedPage.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  let prior = await readVector(isolatedPage, "#final", "--out-");
  report.isolated["h.0"] = errorSummary(prior, reference.boundaries["h.0"]);
  for (let layer = 1; layer <= 3; layer += 1) {
    await isolatedPage.goto(
      `${baseUrl}/experiments/gpt2-four-block-event-scheduler/` +
        `view-timeline-four-block-isolated-h${layer}.html?isolated=${layer}`,
      { waitUntil: "load", timeout: 180000 },
    );
    const sourcePrefix = layer === 1 ? "--out-" : `--b${layer - 1}-final-`;
    await isolatedPage.locator("body > div").evaluate(
      (element, { values, prefix }) => {
        values.forEach((value, index) => element.style.setProperty(
          `${prefix}${String(index).padStart(3, "0")}`,
          String(value),
        ));
      },
      { values: prior, prefix: sourcePrefix },
    );
    await settle(isolatedPage);
    prior = await readVector(
      isolatedPage,
      `#four-block-boundary-h${layer}`,
      `--b${layer}-final-`,
    );
    report.isolated[`h.${layer}`] = errorSummary(
      prior,
      reference.boundaries[`h.${layer}`],
    );
  }
  await isolatedPage.close();

  for (let round = 0; round < rounds; round += 1) {
    const vectors = {};
    for (const variant of (round % 2 ? [...variants].reverse() : variants)) {
      const page = await browser.newPage({ viewport: { width: 1000, height: 400 } });
      const started = performance.now();
      await page.goto(
        `${baseUrl}/experiments/gpt2-four-block-event-scheduler/${variant.file}?cold=${round}`,
        { waitUntil: "domcontentloaded", timeout: 180000 },
      );
      const preSignal = await page.evaluate(() => ({
        ready: [1, 2, 3].map((layer) =>
          document.querySelector(`#four-block-signal-b${layer}`)?.classList.contains("ready") ?? false
        ),
        rects: [1, 2, 3].map((layer) =>
          document.querySelector(`[data-four-block-stage="b${layer}"]`)?.getClientRects().length ?? -1
        ),
      }));
      await settle(page, variant.name === "staged");
      const measured = [];
      vectors[variant.name] = [];
      for (const boundary of boundaries) {
        const values = await readVector(page, boundary.selector, boundary.prefix);
        vectors[variant.name].push(values);
        measured.push({
          layer: boundary.layer,
          ...errorSummary(values, reference.boundaries[`h.${boundary.layer}`]),
        });
      }
      report.trials.push({
        variant: variant.name,
        round,
        readyMilliseconds: performance.now() - started,
        preSignal,
        boundaries: measured,
      });
      await page.close();
    }

    const pairDifferences = boundaries.map((boundary, index) => ({
      layer: boundary.layer,
      maxDifference: maxDifference(vectors.connected[index], vectors.staged[index]),
    }));
    report.trials.push({ round, comparison: "staged-vs-connected", pairDifferences });
  }

  const measuredTrials = report.trials.filter(({ variant }) => variant);
  const comparisons = report.trials.filter(({ comparison }) => comparison);
  const finite = measuredTrials.every(({ boundaries: values }) =>
    values.every(({ finite: value }) => value)
  );
  const identical = comparisons.every(({ pairDifferences }) =>
    pairDifferences.every(({ maxDifference: value }) => value <= 1e-6)
  );
  const isolatedBounds = measuredTrials.every(({ boundaries: values }) =>
    values.every(({ layer, rmse }) =>
      rmse <= 1.25 * report.isolated[`h.${layer}`].rmse + 1e-9
    )
  );
  const stagingDoesNotWorsen = Array.from({ length: rounds }, (_, round) => {
    const connected = measuredTrials.find((trial) =>
      trial.round === round && trial.variant === "connected"
    ).boundaries.at(-1).rmse;
    const staged = measuredTrials.find((trial) =>
      trial.round === round && trial.variant === "staged"
    ).boundaries.at(-1).rmse;
    return staged <= connected + 1e-9;
  }).every(Boolean);
  report.gates = {
    finiteOutputs: finite,
    stagedConnectedMaximumDifferenceAtMost1e6: identical,
    boundaryRmseWithin1p25xIsolated: isolatedBounds,
    stagingDoesNotWorsenFinalRmse: stagingDoesNotWorsen,
  };
  report.pass = Object.values(report.gates).every(Boolean);
  await fs.writeFile(
    new URL("view-timeline-four-block-correctness-smoke.json", directory),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  if (!report.pass) process.exitCode = 1;
} finally {
  await browser.close();
  if (server) server.kill();
}
