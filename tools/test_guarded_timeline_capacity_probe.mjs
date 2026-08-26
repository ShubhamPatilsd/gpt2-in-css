import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);

const root = path.resolve(import.meta.dirname, "..");
const fixture = path.join(root, "experiments", "guarded-timeline-capacity");
const manifest = JSON.parse(fs.readFileSync(path.join(fixture, "manifest.json"), "utf8"));
const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

const results = [];
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 300 } });
  for (const config of manifest) {
    const started = performance.now();
    await page.goto(pathToFileURL(path.join(fixture, `${config.name}.html`)).href, {
      waitUntil: "load",
      timeout: 120000,
    });
    await page.evaluate(() => new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const measurements = await page.evaluate(() => [...document.querySelectorAll(".result")].map((node) => {
      const style = getComputedStyle(node);
      return {
        expectedLeft: Number(node.dataset.left),
        expectedWidth: Number(node.dataset.width),
        actualLeft: Number(style.getPropertyValue("--left-code")),
        actualWidth: Number(style.getPropertyValue("--width-code")),
      };
    }));
    const errors = measurements.flatMap((sample) => [
      sample.actualLeft - sample.expectedLeft,
      sample.actualWidth - sample.expectedWidth,
    ]);
    const failures = errors.filter((error) => error !== 0).length;
    results.push({
      name: config.name,
      payloadBitsPerCoordinate: config.payload_bits,
      payloadBitsPerTimeline: 2 * config.payload_bits,
      guardBits: config.guard_bits,
      geometryBits: config.payload_bits + config.guard_bits,
      viewport: config.viewport,
      values: errors.length,
      exact: errors.length - failures,
      failures,
      maxAbsoluteError: Math.max(...errors.map(Math.abs)),
      milliseconds: performance.now() - started,
    });
  }
} finally {
  await browser.close();
}

const exact = results.filter((result) => result.failures === 0);
const summary = {
  chrome: browser.version(),
  configurations: results.length,
  highestExactPayloadBitsPerCoordinate: Math.max(...exact.map((result) => result.payloadBitsPerCoordinate)),
  highestExactPayloadBitsPerTimeline: Math.max(...exact.map((result) => result.payloadBitsPerTimeline)),
  results,
};
fs.writeFileSync(path.join(fixture, "browser-results.json"), `${JSON.stringify(summary, null, 2)}\n`);
console.log(JSON.stringify(summary, null, 2));
