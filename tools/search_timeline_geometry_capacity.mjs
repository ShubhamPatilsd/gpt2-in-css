import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);

const root = path.resolve(import.meta.dirname, "..");
const output = path.join(root, "experiments", "guarded-timeline-capacity", "geometry-search.json");
const fractions = [0.25, 0.5, 1, 2];
const layouts = [];
for (const distanceMargin of fractions) {
  for (const leftMargin of fractions) {
    for (const entryMargin of fractions) {
      layouts.push({ distanceMargin, leftMargin, entryMargin });
    }
  }
}

function samples(bits) {
  const maximum = (2 ** bits) - 1;
  const middle = 2 ** (bits - 1);
  const values = [
    [0, 0], [maximum, maximum], [0, maximum], [maximum, 0],
    [1, maximum - 1], [maximum - 1, 1], [middle, middle - 1], [middle - 1, middle],
  ];
  let state = (0x9e3779b9 ^ bits) >>> 0;
  const random = () => {
    state ^= state << 13; state ^= state >>> 17; state ^= state << 5;
    return (state >>> 0) / 2 ** 32;
  };
  while (values.length < 128) {
    values.push([Math.floor(random() * (maximum + 1)), Math.floor(random() * (maximum + 1))]);
  }
  return values;
}

function fixture(bits, layout) {
  const maximum = (2 ** bits) - 1;
  const distanceMinimum = Math.ceil(layout.distanceMargin * maximum);
  const distanceMaximum = distanceMinimum + maximum;
  const leftOffset = Math.ceil(layout.leftMargin * maximum) + 1;
  const viewport = leftOffset + distanceMaximum;
  const widthOffset = distanceMaximum + Math.ceil(layout.entryMargin * maximum) + 1;
  const trackWidth = leftOffset + maximum + widthOffset + maximum + 2;
  const cases = samples(bits);
  const rules = [];
  const markup = [];
  for (let index = 0; index < cases.length; index += 1) {
    const [leftPayload, widthPayload] = cases[index];
    rules.push(
      `.s${index}{timeline-scope:--t${index}}` +
      `.v${index}{view-timeline-name:--t${index};left:${leftOffset + leftPayload}px;` +
      `width:${widthOffset + widthPayload}px}` +
      `.r${index}{animation-timeline:--t${index}}`,
    );
    markup.push(
      `<div class="scope s${index}"><div class="scroller"><div class="track">` +
      `<i class="subject v${index}"></i></div></div><output class="result r${index}" ` +
      `data-left="${leftPayload}" data-width="${widthPayload}"></output></div>`,
    );
  }
  const css =
    '@property --cover{syntax:"<number>";inherits:true;initial-value:-1}' +
    '@property --entry{syntax:"<number>";inherits:true;initial-value:-1}' +
    '@property --left-code{syntax:"<number>";inherits:true;initial-value:-1}' +
    '@property --width-code{syntax:"<number>";inherits:true;initial-value:-1}' +
    '@keyframes read{cover 0%{--cover:0;--entry:0}entry 100%{--entry:1}' +
    'cover 100%{--cover:1;--entry:1}}' +
    `.scroller{position:fixed;left:0;top:-20000px;width:${viewport}px;height:1px;overflow-x:scroll}` +
    `.track{position:relative;width:${trackWidth}px;height:1px}` +
    '.subject{position:absolute;top:0;height:1px;display:block;view-timeline-axis:inline}' +
    '.result{animation-name:read;animation-duration:1s;animation-timing-function:linear;' +
    'animation-fill-mode:both;' +
    `--rw:calc(var(--cover)*${viewport}/(var(--entry) - var(--cover)));` +
    `--width-code:calc(round(nearest,var(--rw) - ${widthOffset},1));` +
    `--left-code:calc(round(nearest,${viewport} - var(--entry)*var(--rw) - ${leftOffset},1))}` +
    rules.join('');
  return {
    html: `<!doctype html><meta charset="utf-8"><style>${css}</style>${markup.join('')}`,
    geometry: { viewport, widthOffset, leftOffset, trackWidth },
  };
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const chrome = browser.version();
const results = [];
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 300 } });
  for (const bits of [15, 16, 17, 18]) {
    for (let layoutIndex = 0; layoutIndex < layouts.length; layoutIndex += 1) {
      const built = fixture(bits, layouts[layoutIndex]);
      await page.setContent(built.html, { waitUntil: "load", timeout: 120000 });
      await page.evaluate(() => new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const errors = await page.evaluate(() => [...document.querySelectorAll(".result")].flatMap((node) => {
        const style = getComputedStyle(node);
        return [
          Number(style.getPropertyValue("--left-code")) - Number(node.dataset.left),
          Number(style.getPropertyValue("--width-code")) - Number(node.dataset.width),
        ];
      }));
      results.push({
        bits,
        layoutIndex,
        ...layouts[layoutIndex],
        ...built.geometry,
        values: errors.length,
        failures: errors.filter((error) => error !== 0).length,
        maxAbsoluteError: Math.max(...errors.map(Math.abs)),
      });
    }
  }
} finally {
  await browser.close();
}

const summary = [15, 16, 17, 18].map((bits) => {
  const matching = results.filter((result) => result.bits === bits);
  const exact = matching.filter((result) => result.failures === 0);
  const best = [...matching].sort((a, b) =>
    a.failures - b.failures || a.viewport - b.viewport)[0];
  return { bitsPerCoordinate: bits, bitsPerTimeline: bits * 2, exactLayouts: exact.length, best };
});
fs.writeFileSync(output, `${JSON.stringify({ chrome, layouts: layouts.length, summary, results }, null, 2)}\n`);
console.log(JSON.stringify({ chrome, layouts: layouts.length, summary }, null, 2));
