import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/gpt2-block-css/view-timeline-block-reference.json", import.meta.url),
  "utf8",
));
const rounds = Number(process.env.ADDITIVE_GPT2_ROUNDS ?? 6);

function parseSettings(text) {
  return Array.from(
    text.matchAll(/"A\d{3}"\s+(-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)/gi),
    (match) => Number(match[1]),
  );
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

try {
  const page = await browser.newPage();
  const trials = [];
  for (let round = 0; round < rounds; round += 1) {
    const started = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/gpt2-block-css/view-timeline-block-additive-projection.html?r=${round}`,
      { waitUntil: "load", timeout: 120000 },
    );
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const values = parseSettings(await page.locator("#final").evaluate(
      (element) => getComputedStyle(element).fontVariationSettings,
    ));
    const milliseconds = performance.now() - started;
    const differences = values.map((value, index) => value - reference.output[index]);
    trials.push({
      round,
      milliseconds,
      finite: values.filter(Number.isFinite).length,
      rmse: Math.sqrt(differences.reduce((sum, value) => sum + value * value, 0) / differences.length),
      maxError: Math.max(...differences.map(Math.abs)),
      checksum: values.reduce((sum, value) => sum + value, 0),
    });
  }
  const warm = trials.slice(1).map(({ milliseconds }) => milliseconds).sort((a, b) => a - b);
  const report = {
    chrome: await browser.version(),
    rounds,
    cssBytes: (await fs.stat(new URL(
      "../experiments/gpt2-block-css/view-timeline-block-additive-projection.css",
      import.meta.url,
    ))).size,
    trials,
    warmMedianMilliseconds: warm[Math.floor(warm.length / 2)],
    rmse: trials.at(-1).rmse,
    maxError: trials.at(-1).maxError,
  };
  await fs.writeFile(
    new URL("../experiments/packed-activation-precision/additive-projection-browser.json", import.meta.url),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
