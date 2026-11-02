import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${modules}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/feature-selected-qk/reference.json", import.meta.url),
  "utf8",
));
const rounds = Number(process.env.FEATURE_QK_MUTATION_ROUNDS ?? 21);

function median(values) {
  const ordered = values.toSorted((left, right) => left - right);
  return ordered[Math.floor(ordered.length / 2)];
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
const trials = [];
try {
  await page.goto(
    "http://127.0.0.1:4178/experiments/feature-selected-qk/chunked.html",
    { waitUntil: "load", timeout: 180000 },
  );
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  for (let round = 0; round < rounds; round += 1) {
    const result = await page.evaluate(({ choices, ranges, round }) => {
      const scores = document.querySelector(".scores");
      const started = performance.now();
      for (let coordinate = 0; coordinate < choices.length; coordinate += 1) {
        const choice = (
          choices[coordinate] + round * (1 + coordinate % 11)
        ) % 32;
        const query = -ranges[coordinate] + choice * 2 * ranges[coordinate] / 31;
        scores.style.setProperty(
          `--q-${String(coordinate).padStart(3, "0")}`,
          String(query),
        );
      }
      let checksum = 0;
      for (const score of document.querySelectorAll(".score")) {
        checksum += score.getBoundingClientRect().width;
      }
      return { milliseconds: performance.now() - started, checksum };
    }, {
      choices: reference.queryChoices,
      ranges: reference.queryRanges,
      round,
    });
    trials.push({ round, ...result });
  }
} finally {
  await page.close();
  await browser.close();
}

const report = {
  chrome: await browser.version(),
  rounds,
  context: reference.context,
  head: reference.head,
  queryBits: reference.queryBits,
  featureChunkSize: reference.featureChunkSize,
  runtimeJavaScript: false,
  medianMilliseconds: median(trials.slice(1).map(({ milliseconds }) => milliseconds)),
  minimumMilliseconds: Math.min(...trials.slice(1).map(({ milliseconds }) => milliseconds)),
  maximumMilliseconds: Math.max(...trials.slice(1).map(({ milliseconds }) => milliseconds)),
  checksumsDiffer: new Set(trials.map(({ checksum }) => checksum)).size > 1,
  trials,
};
await fs.writeFile(
  new URL("../experiments/feature-selected-qk/mutation-browser.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
