import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const experiment = new URL("../experiments/counter-matrix/", import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("n4.json", experiment), "utf8"));
const base = "http://127.0.0.1:4178/experiments/counter-matrix";
const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const results = {};
try {
  const page = await browser.newPage();
  for (const [name, extension] of [["flat", "html"], ["nested", "xhtml"]]) {
    await page.goto(`${base}/n4.${extension}`, { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
    results[name] = [];
    for (let caseIndex = 0; caseIndex < 2; caseIndex += 1) {
      results[name].push(await page.evaluate((index) => {
        document.querySelector(`#case-${index}`).checked = true;
        const increment = document.querySelector(".increment");
        return {
          widths: [...document.querySelectorAll(".result")].map(
            (element) => element.getBoundingClientRect().width,
          ),
          bridgeWidth: document.querySelector(".bridge").getBoundingClientRect().width,
          firstCounterIncrement: getComputedStyle(increment).counterIncrement,
        };
      }, caseIndex));
    }
  }
} finally {
  await browser.close();
}

const scale = 10 / 1000;
const resetWidth = reference.counterResets[0] * scale;
if (Math.abs(results.flat[0].widths[0] - resetWidth) > 0.03
    || Math.abs(results.flat[1].widths[0] - resetWidth) > 0.03) {
  throw new Error(`flat child increments unexpectedly escaped: ${JSON.stringify(results.flat)}`);
}
if (results.flat[0].firstCounterIncrement === results.flat[1].firstCounterIncrement) {
  throw new Error("container-derived counter increment did not update");
}
if (Math.abs(results.nested[0].widths[0] - reference.expectedWidths[0][0]) < 0.1) {
  throw new Error("nested size containment unexpectedly preserved the outer counter scope");
}

await fs.writeFile(
  new URL("scope-browser-results.json", experiment),
  `${JSON.stringify(results, null, 2)}\n`,
);
console.log(JSON.stringify(results, null, 2));
