import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/gpt2-block-css/anchor-packed-real-fc-reference.json", import.meta.url),
));

function parseVector(text) {
  return [...text.matchAll(/"A\d{3}"\s+(-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)/gi)]
    .map((match) => Number(match[1]));
}

function error(actual, expected) {
  const delta = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(delta.reduce((sum, value) => sum + value * value, 0) / delta.length),
    max: Math.max(...delta.map(Math.abs)),
  };
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

try {
  const page = await browser.newPage();
  await page.goto(
    "http://127.0.0.1:4178/experiments/gpt2-block-css/anchor-packed-real-fc.html",
    { waitUntil: "load" },
  );
  await page.evaluate(() => document.fonts.ready);
  const anchorDiagnostics = await page.evaluate(() => ({
    rules: [...document.styleSheets[0].cssRules]
      .filter((rule) => rule.cssText.startsWith("#packed"))
      .map((rule) => rule.cssText.slice(0, 500)),
    packed: {
      position: getComputedStyle(document.getElementById("packed")).position,
      positionAnchor: getComputedStyle(document.getElementById("packed")).positionAnchor,
      containingWidth: getComputedStyle(document.getElementById("scope")).width,
    },
    sources: [...document.querySelectorAll(".source")].map((element) => ({
      anchorName: getComputedStyle(element).anchorName,
      position: getComputedStyle(element).position,
      width: getComputedStyle(element).width,
      offsetWidth: element.offsetWidth,
      rectWidth: element.getBoundingClientRect().width,
    })),
  }));
  const parserDiagnostics = await page.evaluate(async () => {
    const text = await (await fetch("anchor-packed-real-fc.css")).text();
    const start = text.indexOf("#packed{");
    const end = text.indexOf("#result{", start);
    const rule = text.slice(start, end);
    const sheet = new CSSStyleSheet();
    let error = null;
    try {
      sheet.insertRule(rule);
    } catch (caught) {
      error = String(caught);
    }
    return { rule, error, parsed: [...sheet.cssRules].map((item) => item.cssText) };
  });
  const widthDiagnostics = await page.evaluate(() => {
    const packed = document.getElementById("packed");
    const original = packed.style.width;
    packed.style.position = "absolute";
    packed.style.positionAnchor = "--a0";
    packed.style.containerType = "inline-size";
    packed.style.height = "1px";
    const candidates = [
      "anchor-size(--a0 width)",
      "calc(anchor-size(--a0 width) * 1000 / 512)",
      "calc(round(nearest, clamp(0px, ((anchor-size(--a0 width) * 1000 / 512 - 60044px) * .004229138 + .039619479px + .64231879px) * 63 / .90750378, 63px), 1px))",
    ];
    const results = candidates.map((candidate) => {
      packed.style.width = candidate;
      return {
        candidate,
        accepted: packed.style.width,
        computed: getComputedStyle(packed).width,
      };
    });
    packed.style.width = original;
    return results;
  });
  const readings = await page.evaluate((secondSettings) => {
    const scope = document.getElementById("scope");
    const read = () => ({
      widths: [...document.querySelectorAll(".source")].map(
        (element) => getComputedStyle(element).width,
      ),
      packedWidth: getComputedStyle(document.getElementById("packed")).width,
      delays: getComputedStyle(document.getElementById("result")).animationDelay,
      vector: getComputedStyle(document.getElementById("result")).fontVariationSettings,
    });
    const initial = read();
    scope.style.fontVariationSettings = secondSettings;
    const mutated = read();
    return [initial, mutated];
  }, reference.settings[1]);
  const cases = readings.map((reading, index) => ({
    ...reading,
    expectedCodes: reference.codes[index],
    expectedProgress: reference.progress[index],
    error: error(parseVector(reading.vector), reference.progress[index]),
  }));
  console.log(JSON.stringify({ ranges: reference.ranges, anchorDiagnostics, parserDiagnostics, widthDiagnostics, cases }, null, 2));
} finally {
  await browser.close();
}
