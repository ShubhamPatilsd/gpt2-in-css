import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const contexts = (process.env.GEOMETRY_FULL_TAIL_CONTEXTS ?? "2,8,16")
  .split(",").map(Number);
const rounds = Number(process.env.GEOMETRY_FULL_TAIL_ROUNDS ?? 5);
const requestedVariants = new Set(
  (process.env.GEOMETRY_FULL_TAIL_VARIANTS ?? "")
    .split(",").map((name) => name.trim()).filter(Boolean),
);
const resultFilename = process.env.GEOMETRY_FULL_TAIL_RESULT ??
  "geometry-streaming-full-tail-browser.json";
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);

function median(values) {
  const ordered = values.toSorted((a, b) => a - b);
  return ordered[Math.floor(ordered.length / 2)];
}

function errors(actual, expected) {
  const differences = actual.map((value, index) => value - expected[index]);
  return {
    finite: actual.every(Number.isFinite),
    rmse: Math.sqrt(
      differences.reduce((sum, value) => sum + value * value, 0) / differences.length,
    ),
    maxError: Math.max(...differences.map(Math.abs)),
  };
}

async function readVector(page, selector, prefix) {
  return page.locator(selector).evaluate((element, propertyPrefix) => {
    const styles = getComputedStyle(element);
    return Array.from({ length: 768 }, (_, index) => Number.parseFloat(
      styles.getPropertyValue(`${propertyPrefix}${String(index).padStart(3, "0")}`),
    ));
  }, prefix);
}

async function readPackedHidden(page, reference) {
  const widths = await page.evaluate(() => {
    return Array.from({ length: 3072 }, (_, output) => Number.parseFloat(
      getComputedStyle(document.querySelector(`.b1q4d-${String(output).padStart(4, "0")}`)).width,
    ));
  });
  const hidden = Array(3072).fill(Number.NaN);
  const span = reference.packedMaximum - reference.packedMinimum;
  for (const outputs of reference.packedGroups) {
    for (let slot = 0; slot < outputs.length; slot += 1) {
      const output = outputs[slot];
      const lowImportance = slot % 2 === 0;
      const levels = lowImportance ? 255 : 511;
      const multiplier = lowImportance ? 1 : 512;
      const offset = lowImportance ? 128 : 0;
      const digit = widths[output] / multiplier - offset;
      hidden[output] = (digit / levels) ** 2 * span + reference.packedMinimum;
    }
  }
  return hidden;
}

const browser = await chromium.launch({ executablePath, headless: true });
const trials = [];
try {
  for (const context of contexts) {
    const stem = `attention-context-${context}-geometry-streaming-flat-siblings-projected`;
    const reference = JSON.parse(await fs.readFile(
      new URL(`${stem}-reference.json`, directory), "utf8",
    ));
    const tailReference = JSON.parse(await fs.readFile(
      new URL(`${stem}-full-tail-reference.json`, directory), "utf8",
    ));
    const allVariants = [
      { name: "attention", file: `${stem}.html`, selector: "#attention-result", prefix: "--r1-" },
      { name: "tail-isolated", file: `${stem}-full-tail-isolated.html`, selector: "#two-block-full", prefix: "--b1-final-" },
      { name: "connected", file: `${stem}-full-tail.html`, selector: "#two-block-full", prefix: "--b1-final-" },
      { name: "gated", file: `${stem}-full-tail-gated.html`, selector: "#two-block-full", prefix: "--b1-final-" },
      { name: "display-gated", file: `${stem}-full-tail-display-gated.html`, selector: "#two-block-full", prefix: "--b1-final-" },
      { name: "boundary", file: `${stem}-full-tail-boundary.html`, selector: "#two-block-full", prefix: "--b1-final-" },
      { name: "packed-boundary", file: `${stem}-full-tail-packed-boundary.html`, selector: "#two-block-full", prefix: "--b1-final-" },
      { name: "pair-boundary", file: `${stem}-full-tail-pair-boundary.html`, selector: "#two-block-full", prefix: "--b1-final-" },
      { name: "dual-boundary", file: `${stem}-full-tail-dual-boundary.html`, selector: "#two-block-full", prefix: "--b1-final-" },
    ];
    const variants = requestedVariants.size
      ? allVariants.filter(({ name }) => requestedVariants.has(name))
      : allVariants;
    if (!variants.length || (variants.some(({ name }) => name !== "attention") &&
      !variants.some(({ name }) => name === "tail-isolated"))) {
      throw new Error("selected connected variants require tail-isolated");
    }
    const vectors = new Map();
    for (let round = 0; round < rounds; round += 1) {
      const order = variants.map((_, index) => variants[(index + round) % variants.length]);
      for (const variant of order) {
        const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
        const started = performance.now();
        await page.goto(
          `http://127.0.0.1:4178/experiments/gpt2-block-css/${variant.file}?round=${round}`,
          { waitUntil: "load", timeout: 180000 },
        );
        await page.evaluate(async () => {
          await document.fonts.ready;
          await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        });
        const vector = await readVector(page, variant.selector, variant.prefix);
        const milliseconds = performance.now() - started;
        const trial = { context, round, name: variant.name, milliseconds };
        if (variant.name === "attention") {
          Object.assign(trial, errors(vector, reference.residual));
        } else {
          Object.assign(trial, errors(vector, tailReference.expected));
          const normalized = await readVector(page, ".b1q4-stage", "--b1-n2-");
          trial.normalized = errors(normalized, tailReference.normalized);
          const packedHidden = await readPackedHidden(page, tailReference);
          trial.packedHidden = errors(packedHidden, tailReference.packedHidden);
        }
        vectors.set(`${context}:${round}:${variant.name}`, vector);
        trials.push(trial);
        await page.close();
      }
      const isolated = vectors.get(`${context}:${round}:tail-isolated`);
      if (isolated) {
        for (const name of ["connected", "gated", "display-gated", "boundary", "packed-boundary", "pair-boundary", "dual-boundary"]) {
          const candidate = vectors.get(`${context}:${round}:${name}`);
          if (!candidate) continue;
          const comparison = errors(candidate, isolated);
          Object.assign(
            trials.find((trial) => trial.context === context && trial.round === round && trial.name === name),
            { isolatedRmse: comparison.rmse, isolatedMaxError: comparison.maxError },
          );
        }
      }
    }
  }
} finally {
  await browser.close();
}

const summary = {};
for (const context of contexts) {
  const names = [...new Set(trials.filter((trial) => trial.context === context).map(({ name }) => name))];
  const byName = Object.fromEntries(names.map((name) => {
    const selected = trials.filter((trial) => trial.context === context && trial.name === name);
    const warm = selected.slice(1);
    return [name, {
      warmMedianMilliseconds: median(warm.map((trial) => trial.milliseconds)),
      finite: selected.every((trial) => trial.finite),
      rmseMaximum: name === "attention" ? Math.max(...selected.map((trial) => trial.rmse)) : undefined,
      modelRmseMaximum: name !== "attention" ? Math.max(...selected.map((trial) => trial.rmse)) : undefined,
      modelMaxErrorMaximum: name !== "attention" ? Math.max(...selected.map((trial) => trial.maxError)) : undefined,
      normalizedRmseMaximum: name !== "attention"
        ? Math.max(...selected.map((trial) => trial.normalized.rmse)) : undefined,
      normalizedMaxErrorMaximum: name !== "attention"
        ? Math.max(...selected.map((trial) => trial.normalized.maxError)) : undefined,
      packedHiddenRmseMaximum: name !== "attention"
        ? Math.max(...selected.map((trial) => trial.packedHidden.rmse)) : undefined,
      packedHiddenMaxErrorMaximum: name !== "attention"
        ? Math.max(...selected.map((trial) => trial.packedHidden.maxError)) : undefined,
      isolatedRmseMaximum: ["connected", "gated", "display-gated", "boundary", "packed-boundary", "pair-boundary", "dual-boundary"].includes(name)
        ? Math.max(...selected.map((trial) => trial.isolatedRmse)) : undefined,
      isolatedMaxErrorMaximum: ["connected", "gated", "display-gated", "boundary", "packed-boundary", "pair-boundary", "dual-boundary"].includes(name)
        ? Math.max(...selected.map((trial) => trial.isolatedMaxError)) : undefined,
    }];
  }));
  const contextSummary = { ...byName };
  const attention = byName.attention?.warmMedianMilliseconds;
  const tail = byName["tail-isolated"]?.warmMedianMilliseconds;
  const direct = byName.connected?.warmMedianMilliseconds;
  const comparisons = [
    ["connected", "connected"],
    ["gated", "gated"],
    ["display-gated", "displayGated"],
    ["boundary", "boundary"],
    ["packed-boundary", "packedBoundary"],
    ["pair-boundary", "pairBoundary"],
    ["dual-boundary", "dualBoundary"],
  ];
  if (attention !== undefined && tail !== undefined) {
    for (const [name, prefix] of comparisons) {
      const value = byName[name]?.warmMedianMilliseconds;
      if (value === undefined) continue;
      contextSummary[`${prefix}MinusAttentionMilliseconds`] = value - attention;
      contextSummary[`${prefix}DependencyPremiumMilliseconds`] = value - attention - tail;
      contextSummary[`${prefix}OverSeparateRatio`] = value / (attention + tail);
      if (direct !== undefined && name !== "connected") {
        contextSummary[`${prefix}VersusDirectMilliseconds`] = value - direct;
      }
    }
  }
  summary[context] = contextSummary;
}

const runtimeSources = await Promise.all(contexts.flatMap((context) => {
  const stem = `attention-context-${context}-geometry-streaming-flat-siblings-projected`;
  return [
    `${stem}-full-tail.html`,
    `${stem}-full-tail-gated.html`,
    `${stem}-full-tail-display-gated.html`,
    `${stem}-full-tail-boundary.html`,
    `${stem}-full-tail-packed-boundary.html`,
    `${stem}-full-tail-pair-boundary.html`,
    `${stem}-full-tail-dual-boundary.html`,
    `${stem}-full-tail-isolated.html`,
  ].map(
    (file) => fs.readFile(new URL(file, directory), "utf8"),
  );
}));
const report = {
  chrome: await browser.version(),
  contexts,
  rounds,
  runtimeJavaScript: runtimeSources.some((source) => /<script|javascript:/i.test(source)),
  summary,
  trials,
};
await fs.writeFile(
  new URL(resultFilename, directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(summary, null, 2));
