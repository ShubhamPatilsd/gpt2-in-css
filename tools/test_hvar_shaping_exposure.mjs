import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const rounds = Number(process.env.HVAR_SHAPING_ROUNDS ?? 8);
const variants = [
  {
    name: "three-font-runs",
    file: "view-timeline-fc-font-three-runs.html",
    objects: 3,
    timelines: 0,
    force: "runs",
  },
  {
    name: "shared-output-spans",
    file: "view-timeline-fc-font-shared-spans.html",
    objects: 3072,
    timelines: 0,
    force: "metrics",
  },
  {
    name: "separate-output-containers",
    file: "view-timeline-fc-font-only.html",
    objects: 9216,
    timelines: 0,
    force: "metrics",
  },
  {
    name: "timeline-exposure",
    file: "view-timeline-fc-timeline-only.html",
    objects: 9216,
    timelines: 3072,
    force: "progress",
  },
  {
    name: "timeline-plus-css-math",
    file: "view-timeline-fc-shared-scroller.html",
    objects: 3072,
    timelines: 3072,
    force: "hidden",
  },
];

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
        { waitUntil: "load", timeout: 120000 },
      );
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      });
      const forceStarted = performance.now();
      const checksum = await page.evaluate((force) => {
        if (force === "runs") {
          let sum = 0;
          for (const element of document.querySelectorAll(".font-run")) {
            for (const rect of element.getClientRects()) sum += rect.width + rect.height;
          }
          return sum;
        }
        if (force === "metrics") {
          let sum = 0;
          for (const element of document.querySelectorAll(".metric")) {
            const rect = element.getBoundingClientRect();
            sum += rect.width + rect.left;
          }
          return sum;
        }
        const element = document.querySelector("#fc-result");
        const style = getComputedStyle(element);
        let sum = 0;
        const prefix = force === "progress" ? "--p" : "--hidden-";
        for (let index = 0; index < 3072; index += 1) {
          sum += Number(style.getPropertyValue(
            `${prefix}${force === "progress" ? index : String(index).padStart(3, "0")}`,
          ));
        }
        return sum;
      }, variant.force);
      const forcedMilliseconds = performance.now() - forceStarted;
      const milliseconds = performance.now() - started;
      trials.push({
        name: variant.name,
        round,
        milliseconds,
        forcedMilliseconds,
        checksum,
      });
      console.error(
        `${variant.name} r${round}: ${milliseconds.toFixed(1)}ms ` +
        `(force ${forcedMilliseconds.toFixed(1)}ms)`,
      );
    }
  }

  const summary = {};
  for (const variant of variants) {
    const allSamples = trials.filter(({ name }) => name === variant.name);
    const samples = allSamples.length > 1 ? allSamples.slice(1) : allSamples;
    const totals = samples.map(({ milliseconds }) => milliseconds).sort((a, b) => a - b);
    const forces = samples.map(({ forcedMilliseconds }) => forcedMilliseconds).sort((a, b) => a - b);
    summary[variant.name] = {
      glyphs: 9216,
      objects: variant.objects,
      timelines: variant.timelines,
      warmMedianMilliseconds: totals[Math.floor(totals.length / 2)],
      medianForcedMilliseconds: forces[Math.floor(forces.length / 2)],
      finiteChecksum: samples.every(({ checksum }) => Number.isFinite(checksum)),
    };
  }
  const sources = await Promise.all(variants.map(({ file }) => fs.readFile(
    new URL(`../experiments/gpt2-block-css/${file}`, import.meta.url),
    "utf8",
  )));
  const report = {
    chrome: await browser.version(),
    noJavaScript: sources.every((source) => !source.toLowerCase().includes("<script")),
    method: "Rotated warm navigations; document.fonts.ready; two frames; force every exposed result.",
    rounds,
    summary,
    trials,
  };
  await fs.writeFile(
    new URL("../experiments/gpt2-block-css/hvar-shaping-exposure-results.json", import.meta.url),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
