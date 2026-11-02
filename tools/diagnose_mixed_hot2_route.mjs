import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const server = process.env.MIXED_HOT2_SERVER ?? "http://127.0.0.1:4189";
const directory = process.env.MIXED_HOT2_DIRECTORY ??
  "gpt2-mixed-hot2-reused-upper-block-gate-b4";
const fixture = Number.parseInt(process.env.MIXED_HOT2_FIXTURE ?? "0", 10);
const artifactRoot = new URL(`../experiments/${directory}/`, import.meta.url);
const reference = JSON.parse(await fs.readFile(new URL("reference.json", artifactRoot), "utf8"));
const hidden = reference.certifiedFixtures.hiddenVectors[fixture];
const scoreFloor = reference.certifiedFixtures.scoreFloors[fixture];
const style = hidden.map((value, dimension) => `--h${dimension}:${value}`);
style.push(`--score-offset:${-scoreFloor * 256 * 4}px`);
style.push(`--query-norm:${Math.sqrt(hidden.reduce((sum, value) => sum + value * value, 0))}`);

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage();
  page.setDefaultTimeout(900_000);
  await page.goto(`${server}/experiments/${directory}/index.html`, {
    waitUntil: "load",
    timeout: 900_000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  await page.evaluate((cssText) => {
    for (const selector of [".cascade", "#model"]) {
      document.querySelector(selector).style.cssText = cssText;
    }
  }, style.join(";"));
  const result = await page.evaluate(() => {
    const inspect = (selector) => {
      const element = document.querySelector(selector);
      if (!element) return null;
      const computed = getComputedStyle(element);
      return {
        rectWidth: element.getBoundingClientRect().width,
        computedWidth: computed.width,
        display: computed.display,
        anchorName: computed.anchorName,
        parent: element.parentElement?.className ?? null,
        bucket: computed.getPropertyValue("--bucket").trim(),
        chunk: computed.getPropertyValue("--chunk").trim(),
        slot: computed.getPropertyValue("--slot").trim(),
        group: computed.getPropertyValue("--group").trim(),
      };
    };
    for (let pass = 0; pass < 3; pass += 1) {
      for (const selector of [
        ".hot-exact-max-0", ".hot-exact-max-1",
        ".hot-route-proxy-0", ".hot-route-proxy-1", "#result",
      ]) document.querySelector(selector)?.getBoundingClientRect();
    }
    return {
      resultGroup: Number(getComputedStyle(document.querySelector("#result")).getPropertyValue("--group")),
      route: Object.fromEntries([
        ".direct-outer-max", ".outer-reader", ".selection",
        ".outer-max-chunk-0", ".chunk-match-0", ".group-choice",
        ".group-choice-reader", ".group-selection", ".slot-carrier-0",
        ".selected", ".selected-reader", "#result",
      ].map((selector) => [selector, inspect(selector)])),
      groups: [0, 1].map((group) => ({
        group,
        exactMax: inspect(`.hot-exact-max-${group}`),
        routeProxy: inspect(`.hot-route-proxy-${group}`),
        wrapper: inspect(`.group-wrapper:has(>.group-${group})`),
      })),
    };
  });
  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
