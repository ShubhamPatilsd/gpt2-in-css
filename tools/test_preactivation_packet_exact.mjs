import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const origin = process.env.HVAR_ORIGIN ?? "http://127.0.0.1:4178";
const cases = [
  [3, 17, 42, 61, 0, 9, 33, 63],
  [63, 48, 21, 1, 57, 36, 12, 5],
];

function gelu(value) {
  const inner = Math.sqrt(2 / Math.PI) * (value + 0.044715 * value ** 3);
  return 0.5 * value * (1 + Math.tanh(inner));
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage();
  await page.goto(
    `${origin}/experiments/preactivation-packet-transport/exact-proof.html`,
    { waitUntil: "load" },
  );
  const results = [];
  for (let caseIndex = 0; caseIndex < cases.length; caseIndex += 1) {
    const actual = await page.evaluate((index) => {
      document.querySelector(`#case-${index}`).checked = true;
      const style = getComputedStyle(document.querySelector("#result"));
      return {
        digits: Array.from({ length: 8 }, (_, place) =>
          Number(style.getPropertyValue(`--d${place}`))),
        preactivations: Array.from({ length: 8 }, (_, place) =>
          Number(style.getPropertyValue(`--z${place}`))),
        hidden: Array.from({ length: 8 }, (_, place) =>
          Number(style.getPropertyValue(`--h${place}`))),
        width: document.querySelector(".carrier").getBoundingClientRect().width,
        height: document.querySelector(".carrier").getBoundingClientRect().height,
      };
    }, caseIndex);
    const expectedPre = cases[caseIndex].map((code) => -8 + code * 16 / 63);
    const expectedHidden = expectedPre.map(gelu);
    results.push({
      caseIndex,
      ...actual,
      exactDigits: actual.digits.every((value, index) => value === cases[caseIndex][index]),
      preactivationMaximumError: Math.max(...actual.preactivations.map(
        (value, index) => Math.abs(value - expectedPre[index]),
      )),
      geluMaximumError: Math.max(...actual.hidden.map(
        (value, index) => Math.abs(value - expectedHidden[index]),
      )),
    });
  }
  const report = {
    chrome: await browser.version(),
    runtimeContainsJavaScript: false,
    bitsPerValue: 6,
    valuesPerCarrier: 8,
    payloadBitsPerDimension: 24,
    results,
  };
  await fs.writeFile(
    new URL(
      "../experiments/preactivation-packet-transport/exact-proof-results.json",
      import.meta.url,
    ),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
