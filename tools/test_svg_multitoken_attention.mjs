import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = process.env.SVG_MULTITOKEN_URL ??
  "http://127.0.0.1:4178/experiments/svg-multitoken-attention";
const referencePath = process.env.SVG_MULTITOKEN_REFERENCE_PATH
  ? new URL(process.env.SVG_MULTITOKEN_REFERENCE_PATH, `file://${process.cwd()}/`)
  : new URL(
    "../experiments/svg-multitoken-attention/reference.json",
    import.meta.url,
  );
const reference = JSON.parse(await fs.readFile(referencePath, "utf8"));

function summarize(actual, expected) {
  const errors = actual.flatMap((row, token) =>
    row.map((value, index) => value - expected[token][index]));
  return {
    maxError: Math.max(...errors.map(Math.abs)),
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0)
      / errors.length),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 100 } });
  async function evaluate(file) {
    const started = performance.now();
    await page.goto(`${baseUrl}/${file}?run=${Date.now()}`, {
      waitUntil: "load", timeout: 180000,
    });
    const png = await page.locator("svg").screenshot({
      animations: "disabled", timeout: 180000,
    });
    const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
    const actual = Array.from({ length: 2 }, (_, token) =>
      Array.from({ length: reference.width }, (_, index) =>
        (data[(token * info.width + index) * info.channels] / 255
        - reference.surface_center) * 2 * reference.value_scales[index]));
    const probabilities = Array.from({ length: reference.heads }, (_, head) =>
      data[(2 * info.width + head) * info.channels] / 255);
    return {
      ...summarize(actual, reference.expected_context),
      perToken: actual.map((row, token) => ({
        ...summarize([row], [reference.expected_context[token]]),
        minimum: Math.min(...row),
        maximum: Math.max(...row),
      })),
      probabilityMaxError: Math.max(...probabilities.map((value, head) =>
        Math.abs(value - reference.expected_probabilities[head]))),
      probabilities,
      milliseconds: performance.now() - started,
      values: 2 * reference.width,
    };
  }
  async function evaluateQkv(file = "qkv-debug.html") {
    const started = performance.now();
    await page.goto(`${baseUrl}/${file}?run=${Date.now()}`, {
      waitUntil: "load", timeout: 180000,
    });
    const png = await page.locator("svg").screenshot({ timeout: 180000 });
    const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
    const actual = Array.from({ length: 2 }, (_, token) => {
      const values = [];
      for (let part = 0; part < 3; part += 1) {
        for (let head = 0; head < reference.heads; head += 1) {
          const row = token * 36 + part * reference.heads + head;
          for (let offset = 0; offset < 64; offset += 1) {
            const index = part * reference.width + head * 64 + offset;
            values[index] = (data[(row * info.width + offset) * info.channels] / 255
              - reference.surface_center) * 2 * reference.qkv_scales[index];
          }
        }
      }
      return values;
    });
    return {
      ...summarize(actual, reference.expected_qkv),
      worst: actual.flatMap((row, token) => row.map((value, index) => ({
        token, index, value, expected: reference.expected_qkv[token][index],
        error: Math.abs(value - reference.expected_qkv[token][index]),
      }))).sort((a, b) => b.error - a.error).slice(0, 8),
      parts: ["query", "key", "value"].map((name, part) => ({
        name,
        ...summarize(
          actual.map((row) => row.slice(part * reference.width, (part + 1) * reference.width)),
          reference.expected_qkv.map((row) =>
            row.slice(part * reference.width, (part + 1) * reference.width)),
        ),
      })),
      milliseconds: performance.now() - started,
    };
  }
  async function evaluateChunked(file, expected, scales, resultName) {
    const started = performance.now();
    await page.goto(`${baseUrl}/${file}?run=${Date.now()}`, {
      waitUntil: "load", timeout: 180000,
    });
    const actual = [];
    for (let chunk = 0; chunk < 12; chunk += 1) {
      await page.locator("filter").last().evaluate((filter, name) => {
        const output = filter.lastElementChild;
        output.innerHTML = `<feMergeNode in="${name}"/>`;
      }, resultName(chunk));
      await page.locator("svg").evaluate((svg, y) => {
        svg.setAttribute("width", "1");
        svg.setAttribute("height", "64");
        svg.setAttribute("viewBox", `63 ${y} 1 64`);
      }, chunk * 64);
      const png = await page.locator("svg").screenshot({ timeout: 180000 });
      const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
      for (let offset = 0; offset < 64; offset += 1) {
        const index = chunk * 64 + offset;
        actual[index] = (data[offset * info.channels] / 255
          - reference.surface_center) * 2 * scales[index];
      }
    }
    return {
      ...summarize([actual], [expected[1]]),
      chunks: Array.from({ length: 12 }, (_, chunk) => ({
        chunk,
        ...summarize(
          [actual.slice(chunk * 64, (chunk + 1) * 64)],
          [expected[1].slice(chunk * 64, (chunk + 1) * 64)],
        ),
      })),
      milliseconds: performance.now() - started,
    };
  }
  const qkv = await evaluateQkv(process.env.SVG_QKV_FILE ?? "qkv-debug.html");
  if (process.env.SVG_RESIDUAL_ONLY === "1") {
    const attentionResidual = await evaluateChunked(
      process.env.SVG_RESIDUAL_FILE ?? "connected-attention-residual.html",
      reference.expected_residual,
      reference.residual_scales,
      (chunk) => `p1-residual-c${chunk}-common`,
    );
    console.log(JSON.stringify({ attentionResidual }, null, 2));
    if (!Number.isFinite(attentionResidual.rmse)
        || attentionResidual.rmse > 0.03) process.exitCode = 1;
  } else if (process.env.SVG_CONNECTED_ONLY === "1") {
    const connected = await evaluate(
      process.env.SVG_CONNECTED_FILE ?? "connected-qkv.html",
    );
    console.log(JSON.stringify({ connected }, null, 2));
    if (!Number.isFinite(connected.rmse) || connected.rmse > 0.03) {
      process.exitCode = 1;
    }
  } else if (process.env.SVG_QKV_ONLY === "1") {
    console.log(JSON.stringify({ qkv }, null, 2));
    if (!Number.isFinite(qkv.rmse) || qkv.rmse > 0.04) process.exitCode = 1;
  } else {
  const qkvHandoff = await evaluateQkv("qkv-handoff-debug.html");
  const standalone = await evaluate("index.html");
  const connectedQkv = await evaluate("connected-qkv.html");
  const attentionProjection = await evaluateChunked(
    "attention-projection-debug.html",
    reference.expected_projected,
    reference.projected_scales,
    (chunk) => `p1-cproj-${chunk}-common`,
  );
  const exactInputProjection = await evaluateChunked(
    "attention-projection-exact-input.html",
    reference.expected_projected,
    reference.projected_scales,
    (chunk) => `p1-cproj-${chunk}-common`,
  );
  const attentionResidual = await evaluateChunked(
    "connected-attention-residual.html",
    reference.expected_residual,
    reference.residual_scales,
    (chunk) => `p1-residual-c${chunk}-common`,
  );
  const result = {
    qkv, qkvHandoff, standalone, connectedQkv, attentionProjection,
    exactInputProjection, attentionResidual,
  };
  console.log(JSON.stringify(result, null, 2));
  if ([qkv, qkvHandoff].some((entry) =>
    !Number.isFinite(entry.rmse) || entry.rmse > 0.04)
    || [standalone, connectedQkv, attentionProjection, exactInputProjection,
      attentionResidual].some((entry) =>
      !Number.isFinite(entry.rmse) || entry.rmse > 0.03)) process.exitCode = 1;
  }
} finally {
  await browser.close();
}
