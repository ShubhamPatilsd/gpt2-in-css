import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const contexts = (process.env.ATTENTION_CONTEXTS ?? "2,4,8").split(",").map(Number);
const rounds = Number(process.env.GEOMETRY_STREAMING_ROUNDS ?? 3);
const projected = process.env.GEOMETRY_STREAMING_PROJECTED === "1";
const reduction = process.env.GEOMETRY_STREAMING_REDUCTION ?? "online";
const scoreBackend = process.env.GEOMETRY_STREAMING_SCORE_BACKEND ?? "font";
const featureQueryRangeScale = Number(
  process.env.GEOMETRY_STREAMING_FEATURE_QUERY_RANGE_SCALE ?? 1,
);
const featureQueryChunk = Number(
  process.env.GEOMETRY_STREAMING_FEATURE_QUERY_CHUNK ?? 5,
);
const valueBackend = process.env.GEOMETRY_STREAMING_VALUE_BACKEND ?? "per-source";
const cacheStateTransport = process.env.GEOMETRY_STREAMING_CACHE_STATE_TRANSPORT ?? "embedded";
const liveCurrentKv = process.env.GEOMETRY_STREAMING_LIVE_CURRENT_KV === "1";
const metricMarkup = process.env.GEOMETRY_STREAMING_METRIC_MARKUP ?? "elements";
const sourceTopology = process.env.GEOMETRY_STREAMING_SOURCE_TOPOLOGY ?? "nested";
const graphVariant = process.env.GEOMETRY_STREAMING_GRAPH_VARIANT ?? "";
const projectionTransport = process.env.GEOMETRY_STREAMING_PROJECTION_TRANSPORT ?? "timeline";
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);

function median(values) {
  const ordered = values.toSorted((a, b) => a - b);
  return ordered[Math.floor(ordered.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
const trials = [];
try {
  for (const context of contexts) {
    const reductionSuffix = reduction === "online" ? "" : `-${reduction}`;
    const scoreSuffix = scoreBackend === "css" ? "-css-score"
      : scoreBackend === "css-kv" ? "-css-kv-score"
      : scoreBackend === "feature" ? "-feature-score"
      : scoreBackend === "feature-kv" ? "-projected-kv-score"
      : scoreBackend === "bilinear-kv" ? "-bilinear-kv-score"
      : scoreBackend === "bilinear-sum-kv" ? "-bilinear-sum-kv-score" : "";
    const rangeSuffix = ["feature", "feature-kv"].includes(scoreBackend) && featureQueryRangeScale !== 1
      ? `-range-${String(featureQueryRangeScale).replace(".", "p")}` : "";
    const queryChunkSuffix = ["feature", "feature-kv"].includes(scoreBackend) && featureQueryChunk !== 5
      ? `-qchunk${featureQueryChunk}` : "";
    const valueSuffix = valueBackend === "mixed-input" ? "-mixed-value"
      : valueBackend === "cached-v" ? "-cached-value" : "";
    const liveCurrentKvSuffix = liveCurrentKv ? "-live-current-kv" : "";
    const cacheSuffix = cacheStateTransport === "nested-vars" ? "-nested-cache" : "";
    const metricSuffix = metricMarkup === "pseudo" ? "-pseudo-metrics" : "";
    const topologySuffix = sourceTopology === "siblings" ? "-siblings" : "";
    const graphSuffix = graphVariant ? `-${graphVariant}` : "";
    const projectionSuffix = projected
      ? (projectionTransport.startsWith("packet") ? `-projection-${projectionTransport}` : "-projected")
      : "";
    const stem = `attention-context-${context}-geometry-streaming${reductionSuffix}${scoreSuffix}${rangeSuffix}${queryChunkSuffix}${valueSuffix}${liveCurrentKvSuffix}${cacheSuffix}${metricSuffix}${topologySuffix}${graphSuffix}${projectionSuffix}`;
    const reference = JSON.parse(await fs.readFile(
      new URL(`${stem}-reference.json`, directory), "utf8",
    ));
    for (let round = 0; round < rounds; round += 1) {
      const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
      const started = performance.now();
      await page.goto(
        `http://127.0.0.1:4178/experiments/gpt2-block-css/${stem}.html?round=${round}`,
        { waitUntil: "load", timeout: 180000 },
      );
      const actual = await page.locator("#attention-result").evaluate((element) => {
        const styles = getComputedStyle(element);
        return Array.from({ length: 768 }, (_, index) => Number.parseFloat(
          styles.getPropertyValue(`--r1-${String(index).padStart(3, "0")}`),
        ));
      });
      const errors = actual.map((value, index) => value - reference.residual[index]);
      if (process.env.GEOMETRY_STREAMING_DEBUG === "1" && round === 0) {
        const debug = await page.locator("geometry-stream-attention").evaluate((attention, tokenCount) => {
          const root = attention.shadowRoot;
          const flat = root.querySelector(".geometry-flat-result");
          const context = root.querySelector(".geometry-context-output");
          const firstKey = root.querySelector(
            `.geometry-source-${tokenCount}-0 .metric`,
          );
          const firstScore = root.querySelector(
            `.geometry-source-${tokenCount}-0-score-0`,
          );
          const flatStyles = flat ? getComputedStyle(flat) : null;
          const contextStyles = context ? getComputedStyle(context) : null;
          const readNumber = (name, base = 10000, scale = 100) => {
            const probe = document.createElement("i");
            probe.style.cssText = `position:fixed;display:block;height:1px;width:calc(${base}px + var(${name}) * ${scale}px)`;
            flat.append(probe);
            const value = (probe.getBoundingClientRect().width - base) / scale;
            probe.remove();
            return value;
          };
          const scoreValues = Array.from({ length: tokenCount }, (_, source) =>
            Array.from({ length: 12 }, (_, head) => readNumber(`--score-${source}-${head}`))
          );
          const flatMaximums = Array.from({ length: 12 }, (_, head) =>
            readNumber(`--flat-m-${head}`)
          );
          const flatDenominators = Array.from({ length: 12 }, (_, head) =>
            readNumber(`--flat-l-${head}`)
          );
          return {
            context0: contextStyles?.getPropertyValue("--context-000"),
            query0: flatStyles?.getPropertyValue("--q-000"),
            keyWidth: firstKey ? getComputedStyle(firstKey).width : null,
            scoreWidth: firstScore ? getComputedStyle(firstScore).width : null,
            scoreRectWidth: firstScore ? firstScore.getBoundingClientRect().width : null,
            scoreChunks: firstScore ? Array.from(firstScore.children, (chunk) => {
              const style = getComputedStyle(chunk);
              const featureEntries = style.fontFeatureSettings.match(/"[^"]+"\s+\d+/g) ?? [];
              const measureCharacters = (featureForIndex) => Array.from(chunk.textContent, (character, index) => {
                const probe = document.createElement("span");
                probe.style.cssText = "position:fixed;display:inline-block;white-space:pre";
                probe.style.fontFamily = style.fontFamily;
                probe.style.fontSize = style.fontSize;
                probe.style.fontFeatureSettings = featureForIndex(index);
                probe.style.fontVariationSettings = style.fontVariationSettings;
                probe.textContent = character;
                document.body.append(probe);
                const width = probe.getBoundingClientRect().width;
                probe.remove();
                return width;
              }).reduce((sum, width) => sum + width, 0);
              const isolatedWidth = measureCharacters(() => style.fontFeatureSettings);
              const soloFeatureWidth = measureCharacters((index) => featureEntries[index] ?? "normal");
              return {
                width: chunk.getBoundingClientRect().width,
                isolatedWidth,
                soloFeatureWidth,
                features: style.fontFeatureSettings,
              };
            }) : [],
            scoreProgress0: flatStyles?.getPropertyValue("--geometry-source-16-0-sp-0"),
            attentionFound: true,
            scoreValues,
            flatMaximums,
            flatDenominators,
          };
        }, context);
        const scoreDifferences = debug.scoreValues.flatMap((sourceValues, source) =>
          sourceValues.map((value, head) => value - reference.scores[head][source])
        );
        debug.scoreRmse = Math.sqrt(scoreDifferences.reduce(
          (sum, value) => sum + value * value, 0,
        ) / scoreDifferences.length);
        debug.scoreMaxError = Math.max(...scoreDifferences.map(Math.abs));
        console.log(JSON.stringify({ context, debug }));
      }
      if (actual.some((value) => !Number.isFinite(value))) {
        throw new Error(`${context}-token geometry attention is non-finite`);
      }
      trials.push({
        context,
        round,
        milliseconds: performance.now() - started,
        rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
        maxError: Math.max(...errors.map(Math.abs)),
      });
      await page.close();
    }
  }
} finally {
  await browser.close();
}
const summary = {};
for (const context of contexts) {
  const selected = trials.filter((trial) => trial.context === context);
  summary[context] = {
    warmMedianMilliseconds: median(selected.slice(1).map((trial) => trial.milliseconds)),
    rmseMaximum: Math.max(...selected.map((trial) => trial.rmse)),
    maxErrorMaximum: Math.max(...selected.map((trial) => trial.maxError)),
  };
}
const report = { chrome: await browser.version(), rounds, trials, summary };
await fs.writeFile(
  new URL(`attention-geometry-streaming${reduction === "online" ? "" : `-${reduction}`}${scoreBackend === "css" ? "-css-score" : scoreBackend === "css-kv" ? "-css-kv-score" : scoreBackend === "feature" ? "-feature-score" : scoreBackend === "feature-kv" ? "-projected-kv-score" : scoreBackend === "bilinear-kv" ? "-bilinear-kv-score" : scoreBackend === "bilinear-sum-kv" ? "-bilinear-sum-kv-score" : ""}${["feature", "feature-kv"].includes(scoreBackend) && featureQueryRangeScale !== 1 ? `-range-${String(featureQueryRangeScale).replace(".", "p")}` : ""}${["feature", "feature-kv"].includes(scoreBackend) && featureQueryChunk !== 5 ? `-qchunk${featureQueryChunk}` : ""}${valueBackend === "mixed-input" ? "-mixed-value" : valueBackend === "cached-v" ? "-cached-value" : ""}${liveCurrentKv ? "-live-current-kv" : ""}${cacheStateTransport === "nested-vars" ? "-nested-cache" : ""}${metricMarkup === "pseudo" ? "-pseudo-metrics" : ""}${sourceTopology === "siblings" ? "-siblings" : ""}${graphVariant ? `-${graphVariant}` : ""}${projected ? (projectionTransport.startsWith("packet") ? `-projection-${projectionTransport}` : "-projected") : ""}-browser.json`, directory),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(summary, null, 2));
