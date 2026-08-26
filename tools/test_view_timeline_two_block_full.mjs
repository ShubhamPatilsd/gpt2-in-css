import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const experimentUrl = new URL(
  "../experiments/gpt2-block-css/",
  import.meta.url,
);
const reference = JSON.parse(await fs.readFile(
  new URL("view-timeline-two-block-full-reference.json", experimentUrl),
  "utf8",
));
const rounds = Number(process.env.TWO_BLOCK_FULL_ROUNDS ?? 4);
const resultFilename = process.env.TWO_BLOCK_FULL_RESULT ?? "two-block-full-browser.json";
const allVariants = [
  {
    name: "block0",
    file: "view-timeline-block-hybrid-packed4-chain-channel89asym-h15.html",
    selector: "#final",
    outputPrefix: "--out-",
    expected: reference.block0_packed,
  },
  {
    name: "attention-connected",
    file: "view-timeline-two-block-attention-probe.html",
    selector: "#two-block-probe",
    outputPrefix: "--b1-out-",
    expected: reference.block1_attention_residual,
  },
  {
    name: "attention-isolated",
    file: "view-timeline-block1-attention-isolated.html",
    selector: "#two-block-probe",
    outputPrefix: "--b1-out-",
    expected: reference.block1_attention_residual,
  },
  {
    name: "full-connected",
    file: "view-timeline-two-block-full.html",
    selector: "#two-block-full",
    outputPrefix: "--b1-final-",
    expected: reference.expected,
    checkpoints: "materialized",
  },
  {
    name: "full-isolated",
    file: "view-timeline-block1-full-isolated.html",
    selector: "#two-block-full",
    outputPrefix: "--b1-final-",
    expected: reference.expected,
    checkpoints: "materialized",
  },
  {
    name: "packed-connected",
    file: "view-timeline-two-block-full-packed4.html",
    selector: "#two-block-full",
    outputPrefix: "--b1-final-",
    expected: reference.expected_packed,
    modelExpected: reference.expected,
    checkpoints: "packed",
  },
  {
    name: "packed-isolated",
    file: "view-timeline-block1-full-packed4-isolated.html",
    selector: "#two-block-full",
    outputPrefix: "--b1-final-",
    expected: reference.expected_packed,
    modelExpected: reference.expected,
    checkpoints: "packed",
  },
  {
    name: "packed-cached-connected",
    file: "view-timeline-two-block-full-packed4-cached.html",
    selector: "#two-block-full",
    outputPrefix: "--b1-final-",
    expected: reference.expected_packed,
    modelExpected: reference.expected,
    checkpoints: "cached",
  },
  {
    name: "packed-cached-isolated",
    file: "view-timeline-block1-full-packed4-cached-isolated.html",
    selector: "#two-block-full",
    outputPrefix: "--b1-final-",
    expected: reference.expected_packed,
    modelExpected: reference.expected,
    checkpoints: "cached",
  },
];
const requestedVariants = new Set(
  (process.env.TWO_BLOCK_FULL_VARIANTS ?? "")
    .split(",")
    .map((name) => name.trim())
    .filter(Boolean),
);
const variants = requestedVariants.size
  ? allVariants.filter(({ name }) => requestedVariants.has(name))
  : allVariants;
if (!variants.length) {
  throw new Error("TWO_BLOCK_FULL_VARIANTS did not match a known variant");
}

function errorSummary(actual, expected) {
  const errors = actual.map((value, index) => value - expected[index]);
  return {
    finite: actual.filter(Number.isFinite).length,
    rmse: Math.sqrt(
      errors.reduce((sum, error) => sum + error * error, 0) / errors.length,
    ),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

async function readVector(page, selector, prefix, width, digits) {
  return page.locator(selector).evaluate(
    (element, { prefix: propertyPrefix, width: vectorWidth, digits: padDigits }) => {
      const style = getComputedStyle(element);
      return Array.from({ length: vectorWidth }, (_, index) => Number(
        style.getPropertyValue(`${propertyPrefix}${String(index).padStart(padDigits, "0")}`),
      ));
    },
    { prefix, width, digits },
  );
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 400 } });
  const trials = [];
  for (let round = 0; round < rounds; round += 1) {
    const order = variants.map((_, index) => variants[(index + round) % variants.length]);
    for (const variant of order) {
      const started = performance.now();
      await page.goto(
        `http://127.0.0.1:4178/experiments/gpt2-block-css/${variant.file}?r=${round}`,
        { waitUntil: "load", timeout: 180000 },
      );
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      });
      const values = await readVector(
        page,
        variant.selector,
        variant.outputPrefix,
        reference.width,
        3,
      );
      const milliseconds = performance.now() - started;
      const trial = {
        name: variant.name,
        round,
        milliseconds,
        ...errorSummary(values, variant.expected),
      };
      if (variant.modelExpected) {
        const modelError = errorSummary(values, variant.modelExpected);
        trial.modelRmse = modelError.rmse;
        trial.modelMaxError = modelError.maxError;
      }
      if (variant.checkpoints) {
        const attention = await readVector(
          page, ".b1-ln2", "--b1-out-", reference.width, 3,
        );
        const normalized = await readVector(
          page,
          variant.checkpoints === "materialized" ? ".b1fc-stage" : ".b1q4-stage",
          "--b1-n2-",
          reference.width,
          3,
        );
        trial.checkpoints = {
          attention: errorSummary(attention, reference.block1_attention_residual),
          normalized: errorSummary(normalized, reference.block1_n2),
        };
        if (variant.checkpoints !== "packed") {
          const hidden = await readVector(
            page, ".b1proj-stage", "--b1-hidden-", reference.mlp_width, 4,
          );
          trial.checkpoints.hidden = errorSummary(
            hidden,
            variant.checkpoints === "cached"
              ? reference.block1_hidden_packed
              : reference.block1_hidden,
          );
        }
      }
      trials.push(trial);
      console.error(
        `${variant.name} r${round}: ${milliseconds.toFixed(1)}ms ` +
        `rmse=${trial.rmse.toFixed(6)} max=${trial.maxError.toFixed(6)}`,
      );
    }
  }

  const summary = {};
  for (const variant of variants) {
    const allSamples = trials.filter(({ name }) => name === variant.name);
    const samples = allSamples.length > 1 ? allSamples.slice(1) : allSamples;
    const times = samples.map(({ milliseconds }) => milliseconds).sort((a, b) => a - b);
    summary[variant.name] = {
      warmMedianMilliseconds: times[Math.floor(times.length / 2)],
      rmse: samples[0].rmse,
      maxError: samples[0].maxError,
      modelRmse: samples[0].modelRmse,
      modelMaxError: samples[0].modelMaxError,
      finite: Math.min(...samples.map(({ finite }) => finite)),
      checkpoints: samples[0].checkpoints,
    };
  }
  const runtimeFiles = variants.map(({ file }) => file);
  const runtimeSources = await Promise.all(runtimeFiles.map(
    (file) => fs.readFile(new URL(file, experimentUrl), "utf8"),
  ));
  const report = {
    chrome: await browser.version(),
    noJavaScript: runtimeSources.every((source) => !source.toLowerCase().includes("<script")),
    rounds,
    assets: {
      htmlBytes: reference.html_bytes,
      cssBytes: reference.css_bytes,
      fontBytes: reference.font_bytes,
      timelines: reference.timelines,
      packed: reference.packed,
    },
    summary,
    trials,
  };
  await fs.writeFile(
    new URL(`../packed-activation-precision/${resultFilename}`, experimentUrl),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
