import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
  const results = {};
  for (const mode of ["unpacked", "packed"]) {
    const loads = [];
    for (let trial = 0; trial < 12; trial += 1) {
      const started = performance.now();
      await page.goto(`http://127.0.0.1:4178/experiments/font-packed-metrics/${mode}-scale.html?t=${trial}`, {
        waitUntil: "load", timeout: 120000,
      });
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      });
      const values = await page.evaluate(() => {
        const style = getComputedStyle(document.querySelector("#result"));
        return Array.from({ length: 1024 }, (_, index) =>
          Number(style.getPropertyValue(`--o${String(index).padStart(4, "0")}`)));
      });
      loads.push({ milliseconds: performance.now() - started, finite: values.every(Number.isFinite) });
    }
    const updates = await page.evaluate(() => {
      const root = document.querySelector("#root");
      const target = document.querySelector("#result");
      const samples = [];
      for (let iteration = 0; iteration < 100; iteration += 1) {
        root.style.setProperty("--flip", iteration % 2 ? "1" : "-1");
        const started = performance.now();
        const style = getComputedStyle(target);
        let checksum = 0;
        for (let index = 0; index < 1024; index += 1) {
          checksum += (index + 1) * Number(
            style.getPropertyValue(`--o${String(index).padStart(4, "0")}`));
        }
        samples.push({ milliseconds: performance.now() - started, checksum });
      }
      return samples;
    });
    const warm = loads.slice(2).map((item) => item.milliseconds).sort((a, b) => a - b);
    const updateTimes = updates.slice(10).map((item) => item.milliseconds).sort((a, b) => a - b);
    results[mode] = {
      nodes: mode === "packed" ? 256 : 512,
      outputs: 1024,
      allFinite: loads.every((item) => item.finite),
      warmMedianMilliseconds: warm[Math.floor(warm.length / 2)],
      updateMedianMilliseconds: updateTimes[Math.floor(updateTimes.length / 2)],
      checksumChanges: new Set(updates.map((item) => item.checksum)).size,
      loadSamples: loads.map((item) => item.milliseconds),
    };
  }
  results.speedup = {
    warm: results.unpacked.warmMedianMilliseconds / results.packed.warmMedianMilliseconds,
    update: results.unpacked.updateMedianMilliseconds / results.packed.updateMedianMilliseconds,
  };
  console.log(JSON.stringify(results, null, 2));
} finally {
  await browser.close();
}
