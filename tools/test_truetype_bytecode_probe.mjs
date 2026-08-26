import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const sharp = require(`${modules}/sharp`);

async function inkBounds(locator) {
  const png = await locator.screenshot({ omitBackground: true });
  const { data, info } = await sharp(png).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  let left = info.width;
  let right = -1;
  let top = info.height;
  let bottom = -1;
  for (let y = 0; y < info.height; y += 1) {
    for (let x = 0; x < info.width; x += 1) {
      const offset = (y * info.width + x) * info.channels;
      const darkness = 255 - Math.min(data[offset], data[offset + 1], data[offset + 2]);
      if (darkness < 24) continue;
      left = Math.min(left, x);
      right = Math.max(right, x);
      top = Math.min(top, y);
      bottom = Math.max(bottom, y);
    }
  }
  return {
    left,
    right,
    top,
    bottom,
    inkWidth: right < left ? 0 : right - left + 1,
    inkHeight: bottom < top ? 0 : bottom - top + 1,
  };
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
  args: ["--font-render-hinting=full"],
});
let report;
try {
  const page = await browser.newPage({ viewport: { width: 480, height: 420 } });
  const fontErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") fontErrors.push(message.text());
  });
  await page.goto("http://127.0.0.1:4178/experiments/truetype-bytecode/index.html", {
    waitUntil: "load",
    timeout: 120000,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  const rows = [];
  const cases = page.locator(".case");
  for (let index = 0; index < await cases.count(); index += 1) {
    const row = cases.nth(index);
    rows.push({
      size: Number(await row.getAttribute("data-size")),
      axis: Number(await row.getAttribute("data-axis")),
      plain: await inkBounds(row.locator(".plain")),
      constant: await inkBounds(row.locator(".constant")),
      computed: await inkBounds(row.locator(".computed")),
    });
  }
  const size64 = rows.filter((row) => row.size === 64);
  const constantHintingExecuted = size64.some(
    (row) => row.constant.inkWidth >= row.plain.inkWidth + 6,
  );
  const computedWidths = size64.map((row) => row.computed.inkWidth);
  const variationBytecodeExecuted =
    Math.max(...computedWidths) >= Math.min(...computedWidths) + 8;
  report = {
    fontReady: await page.evaluate(() => document.fonts.check("64px TTBytecodeProbe")),
    fontErrors,
    constantHintingExecuted,
    variationBytecodeExecuted,
    rows,
  };
} finally {
  await browser.close();
}
await fs.writeFile(
  new URL("../experiments/truetype-bytecode/browser-results.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
