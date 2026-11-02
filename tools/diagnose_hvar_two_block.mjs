import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const directory = process.env.HVAR_TWO_BLOCK_DIR ??
  "avar2-gelu-linear-hvar-full-mlp-g13";
const pageFile = process.env.HVAR_TWO_BLOCK_PAGE ?? "connected-two-block.html";
const fixtureMode = Number(process.env.HVAR_TWO_BLOCK_MODE ?? 0);
const reference = JSON.parse(await fs.readFile(
  new URL(`../experiments/${directory}/reference.json`, import.meta.url),
  "utf8",
));

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 1000, height: 120 },
  });
  const page = await context.newPage();
  await page.goto(
    `http://127.0.0.1:4178/experiments/${directory}/${pageFile}`,
    { waitUntil: "load", timeout: 120000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const report = await page.evaluate(({
    baseAdvance, outputScale, expected, fixtureMode, groups,
  }) => {
    const depth = (element) => {
      let value = 0;
      for (let current = element; current; current = current.parentElement) value += 1;
      return value;
    };
    document.querySelector(`#case-${fixtureMode}`).checked = true;
    const mlpHost = document.querySelector(".b1-mlp");
    const root = mlpHost.shadowRoot;
    const outputs = [...root.querySelectorAll(".b1-output")].map((element) =>
      (element.getBoundingClientRect().width - baseAdvance) / outputScale);
    const errors = outputs.map((value, index) => Math.abs(value - expected[index]));
    const maximumIndex = errors.indexOf(Math.max(...errors));
    const ln2 = document.querySelector(".b1-ln2-stage");
    const mlpStyle = getComputedStyle(mlpHost);
    const ln2Style = getComputedStyle(ln2);
    return {
      maximumIndex,
      maximumError: errors[maximumIndex],
      actual: outputs[maximumIndex],
      expected: expected[maximumIndex],
      width: root.querySelector(`.b1-output-${maximumIndex}`).getBoundingClientRect().width,
      partialWidths: Array.from({ length: groups }, (_, group) => {
        const element = root.querySelector(`.b1-partial-${group}-${maximumIndex}`);
        return {
          group,
          width: element.getBoundingClientRect().width,
          anchorName: getComputedStyle(element).anchorName,
          fontFamily: getComputedStyle(element).fontFamily,
          parentClass: element.parentElement?.className,
          projectionAncestor: element.closest(".b1-projection")?.className,
        };
      }),
      outputComputedWidth: getComputedStyle(
        root.querySelector(`.b1-output-${maximumIndex}`),
      ).width,
      rootAnchorScope: getComputedStyle(root.querySelector(".b1-root")).anchorScope,
      partial138Depth: depth(root.querySelector(".b1-partial-0-138")),
      partial138ClosestProjection: root.querySelector(".b1-partial-0-138")
        .closest(".b1-projection")?.className ?? null,
      attentionMetric767Parent: document.querySelector(".b1-attention").shadowRoot
        .querySelector(".metric-767")?.parentElement?.className ?? null,
      firstOutputs: outputs.slice(0, 8),
      firstExpected: expected.slice(0, 8),
      state0: getComputedStyle(document.querySelector(".state-values, .b1-attention"))
        .getPropertyValue("--state-000"),
      nextLn0: getComputedStyle(document.querySelector(".next-layernorm, .b1-attention"))
        .getPropertyValue("--next-ln-000"),
      b1Raw0: ln2Style.getPropertyValue("--raw-000"),
      b1Residual0: ln2Style.getPropertyValue("--b1-r1-000"),
      b1Input0: ln2Style.getPropertyValue("--b1-input-000"),
      b1AxisSettings: mlpStyle.fontVariationSettings.slice(0, 240),
      b1ProjectionSettings: getComputedStyle(
        root.querySelector(".b1-projection-0"),
      ).fontVariationSettings.slice(0, 240),
      b1ProjectionFamily: getComputedStyle(
        root.querySelector(".b1-projection-0"),
      ).fontFamily,
      fontsStatus: document.fonts.status,
    };
  }, {
    baseAdvance: reference.baseAdvance,
    outputScale: reference.block1OutputScale,
    expected: reference.block1RepresentedOutputs[fixtureMode],
    fixtureMode,
    groups: reference.groups,
  });
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
