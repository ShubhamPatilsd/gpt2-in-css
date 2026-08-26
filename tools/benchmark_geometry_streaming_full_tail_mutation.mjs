import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const contexts = (process.env.GEOMETRY_FULL_TAIL_MUTATION_CONTEXTS ?? "8,16")
  .split(",").map(Number);
const rounds = Number(process.env.GEOMETRY_FULL_TAIL_MUTATION_ROUNDS ?? 7);
const requestedVariants = new Set(
  (process.env.GEOMETRY_FULL_TAIL_MUTATION_VARIANTS ?? "")
    .split(",").map((name) => name.trim()).filter(Boolean),
);
const requestedKinds = (process.env.GEOMETRY_FULL_TAIL_MUTATION_KINDS ??
  "query,source,query+source").split(",").map((name) => name.trim()).filter(Boolean);
const graphVariants = (process.env.GEOMETRY_FULL_TAIL_MUTATION_GRAPH_VARIANTS ?? "")
  .split(",").map((name) => name.trim()).filter(Boolean);
const resultFilename = process.env.GEOMETRY_FULL_TAIL_MUTATION_RESULT ??
  "geometry-streaming-full-tail-mutation.json";
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);

function median(values) {
  const ordered = values.toSorted((left, right) => left - right);
  return ordered[Math.floor(ordered.length / 2)];
}

function maximumDifference(left, right) {
  return Math.max(...left.map((value, index) => Math.abs(value - right[index])));
}

async function settleAndRead(page, selector, prefix) {
  return page.locator(selector).evaluate(async (element, [propertyPrefix]) => {
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const styles = getComputedStyle(element);
    return Array.from({ length: 768 }, (_, index) => Number.parseFloat(
      styles.getPropertyValue(`${propertyPrefix}${String(index).padStart(3, "0")}`),
    ));
  }, [prefix]);
}

const browser = await chromium.launch({ executablePath, headless: true });
const trials = [];
try {
  for (const context of contexts) {
    const stem = `attention-context-${context}-geometry-streaming-flat-siblings-projected`;
    const isolatedStem = `attention-context-${context}-geometry-streaming-flat-siblings-q-isolated-projected`;
    const splitStem = `attention-context-${context}-geometry-streaming-flat-siblings-split-cache-projected`;
    const featureMixedStem = `attention-context-${context}-geometry-streaming-flat-feature-score-mixed-value-siblings-projected`;
    const featureMixedRangeStem = `attention-context-${context}-geometry-streaming-flat-feature-score-range-0p6-mixed-value-siblings-projected`;
    const featureNestedStem = `attention-context-${context}-geometry-streaming-flat-feature-score-mixed-value-nested-cache-siblings-projected`;
    const projectedKvStem = `attention-context-${context}-geometry-streaming-flat-projected-kv-score-cached-value-siblings-projected`;
    const projectedKvNestedStem = `attention-context-${context}-geometry-streaming-flat-projected-kv-score-cached-value-nested-cache-siblings-projected`;
    const projectedKvLiveCurrentStem = `attention-context-${context}-geometry-streaming-flat-projected-kv-score-cached-value-live-current-kv-siblings-projected`;
    const projectedKvLiveCurrentPacketStem = `attention-context-${context}-geometry-streaming-flat-projected-kv-score-cached-value-live-current-kv-siblings-projection-packet12`;
    const bilinearKvLiveCurrentPacketStem = `attention-context-${context}-geometry-streaming-flat-bilinear-kv-score-cached-value-live-current-kv-siblings-projection-packet12`;
    const bilinearSumKvLiveCurrentPacketStem = `attention-context-${context}-geometry-streaming-flat-bilinear-sum-kv-score-cached-value-live-current-kv-siblings-projection-packet12`;
    const cssKvLiveCurrentPacketStem = `attention-context-${context}-geometry-streaming-flat-css-kv-score-cached-value-live-current-kv-siblings-projection-packet12`;
    const allVariants = [
      { name: "attention", file: `${stem}.html`, selector: "#attention-result", prefix: "--r1-" },
      { name: "connected", file: `${stem}-full-tail.html`, selector: "#two-block-full", prefix: "--b1-final-" },
      { name: "attention-q-isolated", file: `${isolatedStem}.html`, selector: "#attention-result", prefix: "--r1-" },
      { name: "connected-q-isolated", file: `${isolatedStem}-full-tail.html`, selector: "#two-block-full", prefix: "--b1-final-" },
      { name: "attention-split-cache", file: `${splitStem}.html`, selector: "#attention-result", prefix: "--r1-" },
      { name: "connected-split-cache", file: `${splitStem}-full-tail.html`, selector: "#two-block-full", prefix: "--b1-final-" },
      { name: "attention-feature-mixed", file: `${featureMixedStem}.html`, selector: "#attention-result", prefix: "--r1-" },
      { name: "attention-feature-mixed-range-0p6", file: `${featureMixedRangeStem}.html`, selector: "#attention-result", prefix: "--r1-" },
      { name: "attention-feature-nested-cache", file: `${featureNestedStem}.html`, selector: "#attention-result", prefix: "--r1-" },
      { name: "attention-projected-kv", file: `${projectedKvStem}.html`, selector: "#attention-result", prefix: "--r1-" },
      { name: "attention-projected-kv-nested-cache", file: `${projectedKvNestedStem}.html`, selector: "#attention-result", prefix: "--r1-" },
      { name: "attention-projected-kv-live-current", file: `${projectedKvLiveCurrentStem}.html`, selector: "#attention-result", prefix: "--r1-" },
      { name: "attention-projected-kv-live-current-packet12", file: `${projectedKvLiveCurrentPacketStem}.html`, selector: "#attention-result", prefix: "--r1-" },
      { name: "qkv-only-projected-kv-live-current-packet12", file: `${projectedKvLiveCurrentPacketStem}.html`, selector: "geometry-stream-attention", prefix: "--q-" },
      { name: "attention-bilinear-kv-live-current-packet12", file: `${bilinearKvLiveCurrentPacketStem}.html`, selector: "#attention-result", prefix: "--r1-" },
      { name: "attention-bilinear-sum-kv-live-current-packet12", file: `${bilinearSumKvLiveCurrentPacketStem}.html`, selector: "#attention-result", prefix: "--r1-" },
      { name: "attention-css-kv-live-current-packet12", file: `${cssKvLiveCurrentPacketStem}.html`, selector: "#attention-result", prefix: "--r1-" },
      ...graphVariants.map((graph) => ({
        name: `attention-${graph}`,
        file: `attention-context-${context}-geometry-streaming-flat-siblings-${graph}-projected.html`,
        selector: "#attention-result",
        prefix: "--r1-",
      })),
    ];
    const variants = requestedVariants.size
      ? allVariants.filter(({ name }) => requestedVariants.has(name))
      : allVariants;
    if (!variants.length) throw new Error("no mutation variants selected");
    for (const variant of variants) {
      let sourceIndex = context - 1;
      if (variant.name === "attention-projected-kv-nested-cache") {
        const reference = JSON.parse(await fs.readFile(
          new URL(variant.file.replace(/\.html$/, "-reference.json"), directory),
          "utf8",
        ));
        sourceIndex = reference.probabilities[0].reduce(
          (best, value, index, values) => value > values[best] ? index : best,
          0,
        );
      }
      const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
      await page.goto(
        `http://127.0.0.1:4178/experiments/gpt2-block-css/${variant.file}`,
        { waitUntil: "load", timeout: 180000 },
      );
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      });
      const handles = await page.evaluateHandle(([tokenCount, variantName, cacheSource]) => {
        const query = document.querySelector(`geometry-stream-q-${tokenCount}`);
        const attention = document.querySelector("geometry-stream-attention");
        const source = [
          "attention-feature-nested-cache",
          "attention-projected-kv-nested-cache",
        ].includes(variantName)
          ? attention.shadowRoot.querySelector(`.state-cache-${cacheSource}`)
          : attention.shadowRoot.querySelector(
            `.geometry-source-${tokenCount}-${tokenCount - 1}`,
          );
        return { query, source, attention };
      }, [context, variant.name, sourceIndex]);
      const query = await handles.getProperty("query");
      const source = await handles.getProperty("source");
      const attention = await handles.getProperty("attention");
      const queryProperty = `--geometry-stream-q-${context}-i-000`;
      const sourceProperty = variant.name === "attention-feature-nested-cache"
        ? `--cache-${sourceIndex}-000`
        : variant.name === "attention-projected-kv-nested-cache"
        ? `--vcache-${sourceIndex}-000`
        : `--geometry-source-${context}-${sourceIndex}-i-000`;
      const [queryBase, sourceBase, directQueryBase] = await page.evaluate(
        ([queryElement, sourceElement, attentionElement, qProperty, sProperty]) => [
          Number.parseFloat(getComputedStyle(queryElement).getPropertyValue(qProperty)),
          Number.parseFloat(getComputedStyle(sourceElement).getPropertyValue(sProperty)),
          Number.parseFloat(getComputedStyle(attentionElement).getPropertyValue("--q-000")),
        ],
        [query, source, attention, queryProperty, sourceProperty],
      );
      const baseline = await settleAndRead(page, variant.selector, variant.prefix);
      for (const kind of requestedKinds) {
        for (let round = 0; round < rounds; round += 1) {
          const magnitude = kind === "direct-query" ? 0.2 : kind === "source" ? 0.05 : 0.01;
          const delta = round % 2 === 0 ? magnitude : -magnitude;
          const started = performance.now();
          await page.evaluate(
            ([queryElement, sourceElement, attentionElement, qProperty, sProperty, qValue, sValue, directQValue, mutationKind]) => {
              if (mutationKind === "query" || mutationKind === "query+source") {
                queryElement.style.setProperty(qProperty, `${qValue}`);
              }
              if (mutationKind === "direct-query") {
                attentionElement.style.setProperty("--q-000", `${directQValue}`);
              }
              if (mutationKind === "source" || mutationKind === "query+source") {
                sourceElement.style.setProperty(sProperty, `${sValue}`);
              }
            },
            [query, source, attention, queryProperty, sourceProperty, queryBase + delta, sourceBase + delta, directQueryBase + delta, kind],
          );
          const output = await settleAndRead(page, variant.selector, variant.prefix);
          const milliseconds = performance.now() - started;
          trials.push({
            context,
            variant: variant.name,
            kind,
            round,
            milliseconds,
            finite: output.every(Number.isFinite),
            maximumOutputChange: maximumDifference(output, baseline),
          });
        }
        await page.evaluate(
          ([queryElement, sourceElement, attentionElement, qProperty, sProperty]) => {
            queryElement.style.removeProperty(qProperty);
            sourceElement.style.removeProperty(sProperty);
            attentionElement.style.removeProperty("--q-000");
          },
          [query, source, attention, queryProperty, sourceProperty],
        );
        await settleAndRead(page, variant.selector, variant.prefix);
      }
      await query.dispose();
      await source.dispose();
      await attention.dispose();
      await handles.dispose();
      await page.close();
    }
  }
} finally {
  await browser.close();
}

const summary = {};
for (const context of contexts) {
  summary[context] = {};
  const variantNames = [...new Set(
    trials.filter((trial) => trial.context === context).map(({ variant }) => variant),
  )];
  for (const variant of variantNames) {
    summary[context][variant] = {};
    for (const kind of requestedKinds) {
      const selected = trials.filter((trial) =>
        trial.context === context && trial.variant === variant && trial.kind === kind
      );
      summary[context][variant][kind] = {
        medianMilliseconds: median(selected.map(({ milliseconds }) => milliseconds)),
        maximumMilliseconds: Math.max(...selected.map(({ milliseconds }) => milliseconds)),
        finite: selected.every(({ finite }) => finite),
        minimumOutputChange: Math.min(...selected.map(({ maximumOutputChange }) => maximumOutputChange)),
      };
    }
  }
}

const report = {
  chrome: await browser.version(),
  contexts,
  rounds,
  runtimeJavaScript: false,
  summary,
  trials,
};
await fs.writeFile(
  new URL(resultFilename, directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(summary, null, 2));
