import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const layout = process.env.ANCHOR_PACKED_MLP_LAYOUT ?? "local";
const zeroEncoding = process.env.ANCHOR_PACKED_ZERO ?? "shared";
const packBits = Number(process.env.ANCHOR_PACKED_BITS ?? 6);
const sinkMode = process.env.ANCHOR_PACKED_SINK ?? "distributed";
const layoutSuffix = layout === "local" ? "" : `-${layout}`;
const bitSuffix = packBits === 6 ? "" : `-b${packBits}`;
const sinkSuffix = {
  distributed: "",
  single: "-single-sink",
  packet: "-packet-sink",
}[sinkMode];
if (sinkSuffix === undefined) {
  throw new Error("ANCHOR_PACKED_SINK must be distributed, single, or packet");
}
const zeroSuffix = zeroEncoding === "literal" ? "-literal-zero" : "";
const suffix = layoutSuffix + bitSuffix + sinkSuffix + zeroSuffix;
const reference = JSON.parse(await fs.readFile(
  new URL(`../experiments/gpt2-block-css/anchor-packed-full-mlp${suffix}-reference.json`, import.meta.url),
));

function parseVector(text) {
  return [...text.matchAll(/"A[A-Z0-9]{3}"\s+(-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)/gi)]
    .map((match) => Number(match[1]));
}

function error(actual, expected) {
  const delta = actual.map((value, index) => value - expected[index]);
  return {
    count: actual.length,
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
  const loadStarted = performance.now();
  await page.goto(
    `http://127.0.0.1:4178/experiments/gpt2-block-css/anchor-packed-full-mlp${suffix}.xhtml`,
    { waitUntil: "load", timeout: 120000 },
  );
  await page.evaluate(() => document.fonts.ready);
  const loadMilliseconds = performance.now() - loadStarted;
  const initialText = await page.locator("#result").evaluate(
    (element) => getComputedStyle(element).fontVariationSettings,
  );
  const mutationStarted = performance.now();
  const mutatedText = await page.evaluate((settings) => {
    document.getElementById("scope").style.setProperty("--fc-settings", settings);
    return getComputedStyle(document.getElementById("result")).fontVariationSettings;
  }, reference.settings[1]);
  const mutationMilliseconds = performance.now() - mutationStarted;
  const sinkDiagnostics = await page.evaluate(() => {
    const style = getComputedStyle(document.getElementById("result"));
    const names = style.animationName.split(", ");
    const delays = style.animationDelay.split(", ");
    const packet = style.getPropertyValue("--pwl000").trim() !== "";
    return {
      nameCount: names.length,
      delayCount: delays.length,
      nameHead: names.slice(0, 4),
      nameTail: names.slice(-4),
      delayHead: delays.slice(0, 4),
      delayTail: delays.slice(-4),
      progress: Object.fromEntries(
        [0, 511, 512, 1023, 2047, 3071].map((index) => {
          const property = packet
            ? `--sp${String(index).padStart(4, "0")}`
            : `--p${String(index).padStart(4, "0")}`;
          return [index, style.getPropertyValue(property)];
        }),
      ),
    };
  });
  const baseText = await page.evaluate(() => {
    document.querySelectorAll(".contribution,.sink").forEach((element) => {
      element.style.animationName = "none";
    });
    return getComputedStyle(document.getElementById("result")).fontVariationSettings;
  });
  const diagnostics = await page.evaluate(() => ({
    domDepth: (() => {
      let depth = 0;
      for (let node = document.getElementById("result"); node; node = node.parentElement) depth += 1;
      return depth;
    })(),
    sources: document.querySelectorAll(".source").length,
    carriers: document.querySelectorAll(".packed-carrier").length,
    firstWidths: [...document.querySelectorAll(".source")].slice(0, 4)
      .map((element) => getComputedStyle(element).width),
    firstPackedWidth: getComputedStyle(document.querySelector(".pack-0")).width,
    firstContributionDelays: getComputedStyle(
      document.querySelector(".contrib-0") ?? document.querySelector(".decode-0"),
    ).animationDelay,
    resultFontFamily: getComputedStyle(document.getElementById("result")).fontFamily,
    sampledGroups: [0, 127, 128, 255, 256, 511, 512, 767].map((group) => {
      const element = document.querySelector(`.contrib-${group}`) ??
        document.querySelector(`.decode-${group}`);
      const carrier = document.querySelector(`.pack-${group}`);
      return {
        group,
        packedWidth: carrier ? getComputedStyle(carrier).width : null,
        delays: element ? getComputedStyle(element).animationDelay : null,
      };
    }),
  }));
  const initialVector = parseVector(initialText);
  const mutatedVector = parseVector(mutatedText);
  const baseVector = parseVector(baseText);
  const report = {
    chrome: await browser.version(),
    loadMilliseconds,
    mutationMilliseconds,
    cssBytes: reference.cssBytes,
    htmlBytes: reference.htmlBytes,
    diagnostics,
    sinkDiagnostics,
    base: {
      count: baseVector.length,
      actual: baseVector,
      head: baseVector.slice(0, 12),
    },
    initial: {
      ...error(initialVector, reference.expected[0]),
      actual: initialVector,
      actualHead: initialVector.slice(0, 12),
      expectedHead: reference.expected[0].slice(0, 12),
    },
    mutated: {
      ...error(mutatedVector, reference.expected[1]),
      actual: mutatedVector,
      actualHead: mutatedVector.slice(0, 12),
      expectedHead: reference.expected[1].slice(0, 12),
    },
  };
  await fs.writeFile(
    new URL(`../experiments/gpt2-block-css/anchor-packed-full-mlp${suffix}-browser.json`, import.meta.url),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
