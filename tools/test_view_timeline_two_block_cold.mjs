import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const rounds = Number(process.env.VIEW_TIMELINE_TWO_BLOCK_COLD_ROUNDS ?? 5);
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);
const variants = [
  {
    name: "direct",
    file: "view-timeline-two-block-full-exact.html",
    reference: "view-timeline-two-block-full-exact-reference.json",
  },
  {
    name: "ready-gated",
    file: "view-timeline-two-block-full-exact-gated.html",
    reference: "view-timeline-two-block-full-exact-gated-reference.json",
  },
];

function error(actual, expected) {
  const delta = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(delta.reduce((sum, value) => sum + value * value, 0) / delta.length),
    max: Math.max(...delta.map(Math.abs)),
  };
}

const references = Object.fromEntries(await Promise.all(variants.map(async (variant) => [
  variant.name,
  JSON.parse(await fs.readFile(new URL(variant.reference, directory))),
])));
const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

try {
  const page = await browser.newPage();
  const trials = [];
  for (let round = 0; round < rounds; round += 1) {
    const order = round % 2 ? [...variants].reverse() : variants;
    for (const variant of order) {
      const started = performance.now();
      await page.goto(
        `http://127.0.0.1:4178/experiments/gpt2-block-css/${variant.file}?cold=${round}`,
        { waitUntil: "load", timeout: 180000 },
      );
      await page.evaluate(() => document.fonts.ready);
      const states = [];
      for (let frame = 0; frame < 10; frame += 1) {
        const values = await page.evaluate(async () => {
          await new Promise((resolve) => requestAnimationFrame(resolve));
          const style = getComputedStyle(document.getElementById("two-block-full"));
          return Array.from({ length: 768 }, (_, index) => Number(
            style.getPropertyValue(`--b1-final-${String(index).padStart(3, "0")}`),
          ));
        });
        const measured = error(values, references[variant.name].expected);
        states.push({
          frame: frame + 1,
          milliseconds: performance.now() - started,
          ...measured,
        });
        if (measured.rmse < 0.02) break;
      }
      trials.push({ name: variant.name, round, states });
    }
  }
  const summary = {};
  for (const variant of variants) {
    const samples = trials
      .filter(({ name }) => name === variant.name)
      .slice(1)
      .map(({ states }) => states.at(-1).milliseconds)
      .sort((a, b) => a - b);
    summary[variant.name] = {
      warmNavigationMedianMilliseconds: samples[Math.floor(samples.length / 2)],
      samples,
    };
  }
  const report = {
    chrome: await browser.version(),
    rounds,
    summary,
    trials,
  };
  await fs.writeFile(
    new URL("view-timeline-two-block-cold-browser.json", directory),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
