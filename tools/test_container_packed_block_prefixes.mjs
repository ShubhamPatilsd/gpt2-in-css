import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const rounds = Number(process.env.CONTAINER_PACKED_PREFIX_ROUNDS ?? 7);
const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

const report = {};
try {
  for (let prefix = 1; prefix <= 4; prefix += 1) {
    const page = await browser.newPage({ viewport: { width: 64, height: 64 } });
    const loadStarted = performance.now();
    await page.goto(
      `http://127.0.0.1:4178/experiments/gpt2-block-css/container-packed-block-prefix-${prefix}.html`,
      { waitUntil: "load", timeout: 180000 },
    );
    await page.evaluate(() => document.fonts.ready);
    const result = await page.evaluate(async ({ prefix, rounds }) => {
      const scope = document.querySelector(".norm1");
      const final = document.getElementById("final");
      const style = getComputedStyle(scope);
      const input = Array.from({ length: 768 }, (_, index) => Number(
        style.getPropertyValue(`--x-${String(index).padStart(3, "0")}`),
      ));
      const forceNames = ["--n2-767", "--hidden-1535", "--hidden-3071", "--out-767"];
      const timings = [];
      const values = [];
      for (let round = 0; round < rounds; round += 1) {
        const factor = round % 2 ? 1 : 0.98;
        const started = performance.now();
        input.forEach((value, index) => scope.style.setProperty(
          `--x-${String(index).padStart(3, "0")}`, String(value * factor),
        ));
        await new Promise((resolve) => requestAnimationFrame(resolve));
        values.push(Number(getComputedStyle(final).getPropertyValue(forceNames[prefix - 1])));
        timings.push(performance.now() - started);
      }
      return { timings, values };
    }, { prefix, rounds });
    const warm = result.timings.slice(1).toSorted((a, b) => a - b);
    report[`prefix${prefix}`] = {
      loadMilliseconds: performance.now() - loadStarted,
      warmMedianMilliseconds: warm[Math.floor(warm.length / 2)],
      timings: result.timings,
      values: result.values,
    };
    await page.close();
  }
} finally {
  await browser.close();
}
console.log(JSON.stringify(report, null, 2));
