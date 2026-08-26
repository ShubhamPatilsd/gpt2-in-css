import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH
  ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const workspace = path.resolve(new URL("..", import.meta.url).pathname);
const directory = path.join(workspace, "experiments/inline-attention-reducer");
const reference = JSON.parse(await fs.readFile(path.join(directory, "reference.json"), "utf8"));
const rounds = Number(process.env.INLINE_ATTENTION_ROUNDS ?? 7);
const pageTimeoutMilliseconds = Number(process.env.INLINE_ATTENTION_PAGE_TIMEOUT_MS ?? 60_000);
const primitiveOnly = process.env.INLINE_ATTENTION_PRIMITIVE_ONLY === "1";
const constants = reference.constants;

const types = new Map([
  [".html", "text/html"], [".woff2", "font/woff2"], [".ttf", "font/ttf"],
]);
const server = http.createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, "http://x").pathname);
    const filename = path.join(workspace, pathname);
    if (!filename.startsWith(`${workspace}${path.sep}`)) throw new Error("outside workspace");
    const body = await fs.readFile(filename);
    response.writeHead(200, { "content-type": types.get(path.extname(filename)) ?? "application/octet-stream" });
    response.end(body);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const { port } = server.address();

function median(values) {
  const ordered = [...values].sort((a, b) => a - b);
  return ordered[Math.floor(ordered.length / 2)];
}

function bounded(promise, label) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error(`${label} timed out after ${pageTimeoutMilliseconds}ms`)),
      pageTimeoutMilliseconds,
    );
    promise.then(
      (value) => { clearTimeout(timer); resolve(value); },
      (error) => { clearTimeout(timer); reject(error); },
    );
  });
}

function metrics(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(errors.reduce((sum, error) => sum + error * error, 0) / errors.length),
    maximumAbsoluteError: Math.max(...errors.map(Math.abs)),
  };
}

function softmax(scores) {
  const maximum = Math.max(...scores);
  const weights = scores.map((score) => Math.exp(score - maximum));
  const denominator = weights.reduce((sum, value) => sum + value, 0);
  return weights.map((value) => value / denominator);
}

function primitiveExpected(scoreCase, valueCase) {
  const probabilities = softmax(scoreCase.scores[0]);
  return Array.from({ length: 4 }, (_, dimension) =>
    probabilities.reduce((sum, probability, source) => (
      sum + probability * valueCase.values[source][0][dimension]
    ), 0));
}

function inputStyle(scoreCase, valueCase, localWidth) {
  const declarations = [];
  for (let head = 0; head < scoreCase.scores.length; head += 1) {
    for (let source = 0; source < scoreCase.scores[head].length; source += 1) {
      declarations.push(`--s-${head}-${source}:${scoreCase.scores[head][source]}`);
      for (let local = 0; local < localWidth; local += 1) {
        declarations.push(`--v-${head}-${source}-${local}:${valueCase.normalizedValues[source][head][local]}`);
      }
    }
  }
  return declarations.join(";");
}

async function readOutputs(page, selector = ".output") {
  const widths = await bounded(
    page.locator(selector).evaluateAll((elements) =>
      elements.map((element) => element.getBoundingClientRect().width)),
    `read ${selector}`,
  );
  return widths.map((width) => (
    (width - constants.outputBasePx) / constants.outputScalePx
  ));
}

async function openPage(browserContext, filename) {
  const page = await browserContext.newPage();
  await bounded(page.goto(
    `http://127.0.0.1:${port}/experiments/inline-attention-reducer/${filename}`,
    { waitUntil: "domcontentloaded", timeout: pageTimeoutMilliseconds },
  ), `${filename} navigation`);
  await bounded(page.evaluate(() => document.fonts.ready), `${filename} fonts`);
  return page;
}

async function primitiveGate(browserContext) {
  const page = await openPage(browserContext, "primitive.html");
  const primitive = reference.primitive;
  const modes = [
    ["initial", primitive.cases[0], primitive.cases[0]],
    ["score-only", primitive.cases[1], primitive.cases[0]],
    ["value-only", primitive.cases[0], primitive.cases[1]],
    ["both", primitive.cases[1], primitive.cases[1]],
  ];
  const observations = [];
  try {
    const support = await page.evaluate(() => ({
      calcSize: CSS.supports("width", "calc-size(max-content, size)"),
      zoomVariable: CSS.supports("zoom", "var(--p)"),
      scriptElements: document.scripts.length,
    }));
    for (const [mode, scoreCase, valueCase] of modes) {
      await page.locator("#fixture").evaluate(
        (element, style) => { element.style.cssText = style; },
        inputStyle(scoreCase, valueCase, 4),
      );
      const expected = primitiveExpected(scoreCase, valueCase);
      const variants = {};
      for (const variant of ["control", "font-size", "zoom"]) {
        const actual = await readOutputs(page, `.output[data-variant="${variant}"]`);
        variants[variant] = { actual, ...metrics(actual, expected) };
      }
      observations.push({ mode, expected, variants });
    }
    const viable = ["font-size", "zoom"].filter((variant) =>
      observations.every((row) => (
        row.variants[variant].rmse <= 0.001
        && row.variants[variant].maximumAbsoluteError <= 0.005
      ))
      && observations.some((row, index) => index > 0 && (
        Math.max(...row.variants[variant].actual.map((value, dimension) =>
          Math.abs(value - observations[0].variants[variant].actual[dimension]))) > 0.001
      ))
    );
    return { support, observations, viable, pass: viable.length > 0 };
  } finally {
    await page.close({ runBeforeUnload: false }).catch(() => {});
  }
}

async function measureVariant(browserContext, variant, contextLength, measuredRounds) {
  const contextReference = reference.contexts[String(contextLength)];
  const cases = contextReference.cases;
  const page = await openPage(browserContext, `${variant}-${contextLength}.html`);
  const initialActual = await readOutputs(page);
  const initialAccuracy = metrics(initialActual, cases[0].expected);
  const samples = [];
  const accuracy = [initialAccuracy];
  try {
    // Two unmeasured mutations warm the exact dependency path in both directions.
    for (const caseIndex of [1, 0]) {
      await page.locator("#fixture").evaluate(
        (element, style) => { element.style.cssText = style; },
        inputStyle(cases[caseIndex], cases[caseIndex], 64),
      );
      await readOutputs(page);
    }
    for (let round = 0; round < measuredRounds; round += 1) {
      const caseIndex = round % 2 === 0 ? 1 : 0;
      const started = performance.now();
      await page.locator("#fixture").evaluate(
        (element, style) => { element.style.cssText = style; },
        inputStyle(cases[caseIndex], cases[caseIndex], 64),
      );
      const actual = await readOutputs(page);
      samples.push(performance.now() - started);
      accuracy.push(metrics(actual, cases[caseIndex].expected));
    }
    return {
      variant,
      context: contextLength,
      rounds: measuredRounds,
      samplesMilliseconds: samples,
      medianMilliseconds: median(samples),
      maximumRmse: Math.max(...accuracy.map((row) => row.rmse)),
      maximumAbsoluteError: Math.max(...accuracy.map((row) => row.maximumAbsoluteError)),
      elements: await page.locator("*").count(),
      outputElements: await page.locator(".output").count(),
      valueSpans: await page.locator(".output span").count(),
    };
  } finally {
    await page.close({ runBeforeUnload: false }).catch(() => {});
  }
}

const browser = await chromium.launch({ executablePath, headless: true });
let report;
try {
  const browserContext = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 900, height: 900 },
  });
  const primitive = await primitiveGate(browserContext);
  process.stderr.write(`primitive pass=${primitive.pass} viable=${primitive.viable.join(",")}\n`);
  const measurements = [];
  const requestedVariants = process.env.INLINE_ATTENTION_VARIANTS
    ? process.env.INLINE_ATTENTION_VARIANTS.split(",").filter(Boolean)
    : primitive.viable;
  const selectedVariants = requestedVariants.filter((variant) => primitive.viable.includes(variant));
  if (primitive.pass && !primitiveOnly) {
    for (const contextLength of [8, 16, 32]) {
      const measuredRounds = contextLength === 32 ? 1 : rounds;
      for (const variant of ["control", ...selectedVariants]) {
        process.stderr.write(`measure ${variant} context=${contextLength}\n`);
        try {
          const measurement = await measureVariant(
            browserContext, variant, contextLength, measuredRounds,
          );
          measurements.push({ status: "complete", ...measurement });
          process.stderr.write(`complete ${variant} context=${contextLength} median=${measurement.medianMilliseconds.toFixed(3)}ms\n`);
        } catch (error) {
          measurements.push({
            status: "timeout-or-error", variant, context: contextLength,
            symptom: String(error),
          });
          process.stderr.write(`failed ${variant} context=${contextLength}: ${String(error)}\n`);
        }
        await fs.writeFile(
          path.join(directory, "browser-progress.json"),
          `${JSON.stringify({ primitive, measurements }, null, 2)}\n`,
        );
      }
    }
  }
  const comparisons = [8, 16, 32].map((contextLength) => {
    const control = measurements.find((row) => row.context === contextLength && row.variant === "control");
    if (!control || control.status !== "complete") {
      return {
        context: contextLength,
        status: control?.status ?? "not-run",
        symptom: control?.symptom,
      };
    }
    const candidates = selectedVariants.map((variant) => {
      const candidate = measurements.find((row) => row.context === contextLength && row.variant === variant);
      if (!candidate || candidate.status !== "complete") {
        return { variant, status: candidate?.status ?? "not-run", symptom: candidate?.symptom };
      }
      return {
        variant,
        status: "complete",
        speedRatioVsControl: candidate.medianMilliseconds / control.medianMilliseconds,
        candidateMilliseconds: candidate.medianMilliseconds,
        controlMilliseconds: control.medianMilliseconds,
      };
    });
    return { context: contextLength, candidates };
  });
  const bestAt32 = comparisons.find((row) => row.context === 32)?.candidates
    ?.filter((row) => row.status === "complete")
    ?.toSorted((a, b) => a.speedRatioVsControl - b.speedRatioVsControl)[0];
  const accepted = Boolean(
    primitive.pass
    && bestAt32
    && bestAt32.speedRatioVsControl <= 0.5
    && measurements.filter((row) => row.variant === bestAt32.variant)
      .every((row) => row.maximumRmse <= 0.001 && row.maximumAbsoluteError <= 0.005)
  );
  report = {
    chrome: await browser.version(),
    rounds,
    primitiveOnly,
    pageTimeoutMilliseconds,
    primitive,
    measurements,
    comparisons,
    acceptanceGate: {
      context32AtLeastTwoTimesFaster: true,
      maximumRmse: 0.001,
      maximumAbsoluteError: 0.005,
    },
    decision: accepted ? "retain" : "reject",
    accepted,
  };
  await browserContext.close();
} finally {
  await browser.close();
  server.closeAllConnections();
  await new Promise((resolve) => server.close(resolve));
}

await fs.writeFile(
  path.join(directory, "browser-results.json"),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
