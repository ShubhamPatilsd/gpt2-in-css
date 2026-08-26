import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/gpt2-block-css/view-timeline-two-block-attention-probe-reference.json", import.meta.url),
  "utf8",
));
const rounds = Number(process.env.TWO_BLOCK_PROBE_ROUNDS ?? 6);
const variants = [
  {
    name: "block0",
    file: "view-timeline-block-hybrid-packed4-chain-channel89asym-h15.html",
    selector: "#final",
    outputPrefix: "--out-",
    expected: reference.block0_packed,
  },
  {
    name: "connected", file: "view-timeline-two-block-attention-probe.html",
    selector: "#two-block-probe", outputPrefix: "--b1-out-",
    expected: reference.expected,
  },
  {
    name: "isolated", file: "view-timeline-block1-attention-isolated.html",
    selector: "#two-block-probe", outputPrefix: "--b1-out-",
    expected: reference.expected,
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
      const values = await page.locator(variant.selector).evaluate((element, { width, prefix }) => {
        const style = getComputedStyle(element);
        return Array.from({ length: width }, (_, index) => Number(
          style.getPropertyValue(`${prefix}${String(index).padStart(3, "0")}`),
        ));
      }, { width: reference.width, prefix: variant.outputPrefix });
      const inputValues = variant.name === "block0"
        ? reference.block0_packed
        : await page.locator(".b1-norm").evaluate((element, width) => {
          const style = getComputedStyle(element);
          return Array.from({ length: width }, (_, index) => Number(
            style.getPropertyValue(`--out-${String(index).padStart(3, "0")}`),
          ));
        }, reference.width);
      const errors = values.map((value, index) => value - variant.expected[index]);
      const inputErrors = inputValues.map(
        (value, index) => value - reference.block0_packed[index],
      );
      trials.push({
        name: variant.name,
        round,
        milliseconds: performance.now() - started,
        finite: values.filter(Number.isFinite).length,
        rmse: Math.sqrt(errors.reduce((sum, error) => sum + error * error, 0) / errors.length),
        maxError: Math.max(...errors.map(Math.abs)),
        inputRmse: Math.sqrt(
          inputErrors.reduce((sum, error) => sum + error * error, 0) / inputErrors.length,
        ),
        inputMaxError: Math.max(...inputErrors.map(Math.abs)),
      });
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
      inputRmse: samples[0].inputRmse,
      inputMaxError: samples[0].inputMaxError,
      finite: Math.min(...samples.map(({ finite }) => finite)),
    };
  }
  const report = {
    chrome: await browser.version(),
    noJavaScript: !(await fs.readFile(
      new URL("../experiments/gpt2-block-css/view-timeline-two-block-attention-probe.html", import.meta.url),
      "utf8",
    )).toLowerCase().includes("<script"),
    rounds,
    summary,
    trials,
  };
  await fs.writeFile(
    new URL("../experiments/packed-activation-precision/two-block-attention-browser.json", import.meta.url),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
