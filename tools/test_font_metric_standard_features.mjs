import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/font-metric-standard-features/reference.json", import.meta.url), "utf8"));

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 1200, height: 500 } });
  await page.goto("http://127.0.0.1:4178/experiments/font-metric-standard-features/index.html", {
    waitUntil: "load", timeout: 120000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  const rows = await page.evaluate(({ cases, font_size, units_per_em, base, expected }) => {
    const scale = font_size / units_per_em;
    return cases.map(({ name, pair }) => {
      const root = document.querySelector(`#${name}`);
      const selectors = { ch: ".ch", ic: ".ic", zero: ".glyph-zero", water: ".glyph-water" };
      const widths = Object.fromEntries(Object.entries(selectors).map(([kind, selector]) => [
        kind, root.querySelector(selector).getBoundingClientRect().width / scale - base,
      ]));
      return {
        name,
        pair,
        expected: pair === null ? [0, 0] : expected.slice(pair * 2, pair * 2 + 2),
        unit: [widths.ch, widths.ic],
        glyph: [widths.zero, widths.water],
      };
    });
  }, reference);
  console.log(JSON.stringify({
    rows,
    unitSelectorsWorking: rows.filter((row) => row.pair !== null).filter((row) =>
      row.unit.some((value) => Math.abs(value) > 0.1)).map((row) => row.name),
    glyphSelectorsWorking: rows.filter((row) => row.pair !== null).filter((row) =>
      row.glyph.some((value) => Math.abs(value) > 0.1)).map((row) => row.name),
  }, null, 2));
} finally {
  await browser.close();
}
