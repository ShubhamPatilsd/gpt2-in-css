import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = process.env.SVG_CONTIGUOUS_TRACE_URL ??
  "http://127.0.0.1:4178/experiments/svg-contiguous-qkv-batched-native-part/index.html";

const contiguousProbes = [
  ["live-t1-q-common", 0, 255, 768, 1],
  ["t1-q-signed", 0, 255, 768, 1],
  ["live-t0-k-common", 0, 255, 768, 1],
  ["t0-k-signed", 0, 255, 768, 1],
  ["score0-same", 0, 255, 768, 1],
  ["score0-signed", 0, 255, 768, 1],
  ["difference-terms", 0, 255, 768, 1],
  ["difference-common", 0, 255, 768, 1],
  ["prob0", 0, 255, 768, 1],
  ["prob0-tile", 0, 255, 768, 1],
  ["prob1-tile", 0, 255, 768, 1],
  ["live-t0-v-common", 0, 255, 768, 1],
  ["t0-v-signed", 0, 255, 768, 1],
  ["weighted0", 0, 255, 768, 1],
  ["weighted1", 0, 255, 768, 1],
  ["context1-signed", 0, 255, 768, 1],
  ["context1-common", 0, 255, 768, 1],
];
const rgbProbes = [
  ["live-t1-q-h0-common", 0, 255, 64, 1],
  ["t1-h0-q", 0, 0, 64, 1],
  ["t1-h0-q-signed", 0, 0, 64, 1],
  ["h0-t1-s0-product", 0, 0, 64, 1],
  ["h0-t1-s0-product-scale", 0, 0, 64, 1],
  ["h0-t1-s0-product-scaled", 0, 0, 64, 1],
  ["h0-t1-s0-product-sum", 63, 0, 1, 1],
  ["h0-t1-s0-product-score", 63, 0, 1, 1],
  ["h0-difference", 63, 0, 1, 1],
  ["h0-prob0", 63, 0, 1, 1],
  ["h0-prob0-tile", 0, 0, 64, 1],
  ["t0-h0-v-signed", 0, 0, 64, 1],
  ["h0-weighted0", 0, 0, 64, 1],
  ["h0-context-common", 0, 0, 64, 1],
];
const mixedProbes = [
  ["mixed-context-signed", 0, 0, 768, 1],
  ["mixed-cproj-0-b0-g0-h0-values", 0, 0, 64, 64],
  ["mixed-cproj-0-b0-g0-input-positive-2", 0, 0, 64, 64],
  ["mixed-cproj-0-b0-g0-weights-positive", 0, 0, 64, 64],
  ["mixed-cproj-0-b0-g0-pp", 0, 0, 64, 64],
  ["mixed-cproj-0-b0-g0-positive", 0, 0, 64, 64],
  ["mixed-cproj-0-b0-g0-positive-sum", 63, 0, 1, 64],
  ["mixed-cproj-0-b0-g0-negative-sum", 63, 0, 1, 64],
  ["mixed-cproj-0-b0-g0-positive-routed", 63, 0, 1, 64],
  ["mixed-cproj-0-b0-g0-negative-routed", 63, 0, 1, 64],
  ["mixed-cproj-0-b0-g0-encoded", 63, 0, 1, 64],
  ["mixed-cproj-0-b0-g1-encoded", 63, 0, 1, 64],
  ["mixed-cproj-0-b0-g2-encoded", 63, 0, 1, 64],
  ["mixed-cproj-0-b0-g3-encoded", 63, 0, 1, 64],
  ["mixed-cproj-0-b0-average01", 63, 0, 1, 64],
  ["mixed-cproj-0-b0-average23", 63, 0, 1, 64],
  ["mixed-cproj-0-b0-average-all", 63, 0, 1, 64],
  ["mixed-cproj-0-b0-total", 63, 0, 1, 64],
  ["mixed-cproj-0-b0-biased", 63, 0, 1, 64],
  ["mixed-cproj-0-b0-signed", 63, 0, 1, 64],
  ["mixed-cproj-0-b0-scaled", 63, 0, 1, 64],
  ["mixed-cproj-0-b0-common", 63, 0, 1, 64],
  ["mixed-residual-0-common", 63, 0, 1, 64],
];
const traceKind = process.env.SVG_CONTIGUOUS_TRACE_KIND;
const selectedProbes = traceKind === "rgb"
  ? rgbProbes
  : traceKind === "mixed"
    ? mixedProbes
    : contiguousProbes;
const probeNames = process.env.SVG_CONTIGUOUS_TRACE_PROBE?.split(",");
const probes = probeNames
  ? selectedProbes.filter(([name]) => probeNames.includes(name))
  : selectedProbes;
if (probes.length === 0) {
  throw new Error(`Unknown trace probe: ${probeNames?.join(",")}`);
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 100 } });
  const results = [];
  for (const [name, x, y, width, height] of probes) {
    await page.goto(`${url}?probe=${name}-${performance.now()}`, {
      waitUntil: "load",
      timeout: 180000,
    });
    await page.locator("filter").last().evaluate((filter, resultName) => {
      const output = filter.lastElementChild;
      output.innerHTML = `<feMergeNode in="${resultName}"/>`;
    }, name);
    await page.locator("svg").evaluate((svg, bounds) => {
      svg.setAttribute("width", String(bounds.width));
      svg.setAttribute("height", String(bounds.height));
      svg.setAttribute(
        "viewBox",
        `${bounds.x} ${bounds.y} ${bounds.width} ${bounds.height}`,
      );
    }, { x, y, width, height });
    const png = await page.locator("svg").screenshot({ timeout: 180000 });
    const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
    const channelStats = Array.from({ length: Math.min(info.channels, 4) }, (_, channel) => {
      const values = [];
      for (let offset = channel; offset < data.length; offset += info.channels) {
        values.push(data[offset]);
      }
      return {
        minimum: Math.min(...values),
        maximum: Math.max(...values),
        mean: values.reduce((sum, value) => sum + value, 0) / values.length,
        nonzero: values.filter((value) => value !== 0).length,
      };
    });
    const channelValues = process.env.SVG_CONTIGUOUS_TRACE_VALUES === "1"
      ? Array.from({ length: Math.min(info.channels, 4) }, (_, channel) => {
        const values = [];
        for (let offset = channel; offset < data.length; offset += info.channels) {
          values.push(data[offset]);
        }
        return values;
      })
      : undefined;
    results.push({ name, channelStats, ...(channelValues ? { channelValues } : {}) });
  }
  console.log(JSON.stringify(results, null, 2));
} finally {
  await browser.close();
}
