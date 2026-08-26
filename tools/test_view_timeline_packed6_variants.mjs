import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);

const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/gpt2-block-css/view-timeline-block-reference.json", import.meta.url),
  "utf8",
));
const allVariants = [
  { name: "packed4", file: "view-timeline-block-hybrid-fc-packed4.html", timelines: 768, totalTimelines: 1536 },
  { name: "packed4-paired-output", file: "view-timeline-block-hybrid-fc-packed4-paired-output.html", timelines: 768, totalTimelines: 1152 },
  { name: "packed4-output-pack4", file: "view-timeline-block-hybrid-packed4-chain.html", timelines: 768, totalTimelines: 960 },
  { name: "packed4-output-channel89", file: "view-timeline-block-hybrid-packed4-chain-channel89.html", timelines: 768, totalTimelines: 960 },
  { name: "packed4-output-channel89-h15", file: "view-timeline-block-hybrid-packed4-chain-channel89-h15.html", timelines: 768, totalTimelines: 960 },
  { name: "packed4-output-channel89-asym-h15", file: "view-timeline-block-hybrid-packed4-chain-channel89asym-h15.html", timelines: 768, totalTimelines: 960 },
  { name: "packed4-output-channel910-h15", file: "view-timeline-block-hybrid-packed4-chain-channel910-h15.html", timelines: 768, totalTimelines: 960 },
  { name: "heterogeneous-5-8", file: "view-timeline-block-hybrid-fc-hetero58.html", timelines: 640, totalTimelines: 1408 },
  { name: "sensitivity-3-4-5-6", file: "view-timeline-block-hybrid-fc-sensitivity3456.html", timelines: 416, totalTimelines: 1184 },
  { name: "packed7-5-6", file: "view-timeline-block-hybrid-fc-packed6-packed7-56.html", timelines: 439, totalTimelines: 1207 },
  { name: "mixed-4-5-7", file: "view-timeline-block-hybrid-fc-packed6.html", timelines: 512, totalTimelines: 1280 },
  { name: "uniform6", file: "view-timeline-block-hybrid-fc-packed6-uniform6.html", timelines: 512, totalTimelines: 1280 },
  { name: "uniform6-asymmetric", file: "view-timeline-block-hybrid-fc-packed6-uniform6asym.html", timelines: 512, totalTimelines: 1280 },
  { name: "log-asymmetric-4", file: "view-timeline-block-hybrid-fc-packed6-logasym4.html", timelines: 512, totalTimelines: 1280 },
  { name: "importance-5-6-6", file: "view-timeline-block-hybrid-fc-packed6-importance566.html", timelines: 512, totalTimelines: 1280 },
  { name: "uniform7", file: "view-timeline-block-hybrid-fc-packed6-uniform7.html", timelines: 512, totalTimelines: 1280 },
];
const selectedNames = new Set(
  (process.env.PACKED6_BENCHMARK_VARIANTS ?? allVariants.map(({ name }) => name).join(","))
    .split(",").map((name) => name.trim()).filter(Boolean),
);
const variants = allVariants.filter(({ name }) => selectedNames.has(name));
if (variants.length === 0) throw new Error("no benchmark variants selected");

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 400 } });
  const trials = [];
  const rounds = Number(process.env.PACKED6_BENCHMARK_ROUNDS ?? 6);
  for (let round = 0; round < rounds; round += 1) {
    const order = variants.map((_, index) => variants[(index + round) % variants.length]);
    for (const variant of order) {
      const started = performance.now();
      await page.goto(
        `http://127.0.0.1:4178/experiments/gpt2-block-css/${variant.file}?run=${round}`,
        { waitUntil: "load", timeout: 120000 },
      );
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      });
      const values = await page.locator("#final").evaluate((element, width) => {
        const style = getComputedStyle(element);
        return Array.from({ length: width }, (_, index) => Number(
          style.getPropertyValue(`--out-${String(index).padStart(3, "0")}`),
        ));
      }, reference.width);
      const firstProjectionSettings = await page.locator(".proj-pack-0").first()
        .evaluate((element) => getComputedStyle(element).fontVariationSettings);
      const transportDebug = variant.name === "uniform6-asymmetric"
        ? await page.evaluate(() => {
          const stage = getComputedStyle(document.querySelector(".projection-stage"));
          return {
            packet340: stage.getPropertyValue("--q6l-340"),
            packet381: stage.getPropertyValue("--q6p-381"),
            digit2Width: getComputedStyle(document.querySelector(".q6d-0002")).width,
            digit3Width: getComputedStyle(document.querySelector(".q6d-0003")).width,
          };
        })
        : variant.name === "packed7-5-6"
          ? await page.evaluate(() => {
            const stage = getComputedStyle(document.querySelector(".projection-stage"));
            const packs = Array.from({ length: 439 }, (_, index) => ({
              index,
              cover: Number(stage.getPropertyValue(`--q6c${index}`)),
              entry: Number(stage.getPropertyValue(`--q6e${index}`)),
            })).map(({ index, cover, entry }) => {
              const recoveredWidth = cover * 16777216 / (entry - cover);
              return {
                index,
                cover,
                entry,
                left: Math.round(16777216 - entry * recoveredWidth - 12777216),
                width: Math.round(recoveredWidth - 4000000),
              };
            });
            const byMagnitude = packs.flatMap(({ index, left, width }) => [
              { index, side: "left", value: left },
              { index, side: "width", value: width },
            ]).sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
            return { largestPacks: byMagnitude.slice(0, 8) };
          })
        : undefined;
      const milliseconds = performance.now() - started;
      const errors = values.map((value, index) => value - reference.output[index]);
      const worstIndex = errors.reduce(
        (best, value, index) => Math.abs(value) > Math.abs(errors[best]) ? index : best,
        0,
      );
      trials.push({
        name: variant.name,
        round,
        milliseconds,
        finite: values.filter(Number.isFinite).length,
        rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
        maxError: Math.max(...errors.map(Math.abs)),
        worstIndex,
        worstActual: values[worstIndex],
        worstExpected: reference.output[worstIndex],
        checksum: values.reduce((sum, value) => sum + value, 0),
        firstProjectionSettingsLength: firstProjectionSettings.length,
        firstProjectionSettingsPrefix: firstProjectionSettings.slice(0, 120),
        transportDebug,
      });
    }
  }

  const summary = {};
  for (const variant of variants) {
    const samples = trials.filter((trial) => trial.name === variant.name);
    const measured = samples.length > 1 ? samples.slice(1) : samples;
    const warm = measured.map((trial) => trial.milliseconds).sort((a, b) => a - b);
    const errors = measured;
    summary[variant.name] = {
      timelines: variant.timelines,
      totalTimelines: variant.totalTimelines,
      warmSamples: warm.length,
      warmMedianMilliseconds: warm[Math.floor(warm.length / 2)],
      warmMinMilliseconds: warm[0],
      warmMaxMilliseconds: warm.at(-1),
      rmseMedian: errors.map((trial) => trial.rmse).sort((a, b) => a - b)[Math.floor(errors.length / 2)],
      maxErrorMaximum: Math.max(...errors.map((trial) => trial.maxError)),
      finite: Math.min(...errors.map((trial) => trial.finite)),
    };
  }

  const report = { chrome: await browser.version(), rounds, trials, summary };
  const outputName = process.env.PACKED6_BENCHMARK_OUTPUT ?? "browser-results.json";
  await fs.writeFile(
    new URL(`../experiments/packed-activation-precision/${outputName}`, import.meta.url),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
