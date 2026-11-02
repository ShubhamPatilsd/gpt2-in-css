import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = process.env.HVAR_CONNECTED_URL ??
  "http://127.0.0.1:4178/experiments/avar2-gelu-linear-hvar-full-mlp/connected-input.html";

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 1000, height: 120 },
  });
  const page = await context.newPage();
  await page.goto(url, { waitUntil: "load", timeout: 120000 });
  await page.evaluate(() => document.fonts.ready);
  if (process.env.HVAR_FORCE_FONT_LOAD === "1") {
    await page.evaluate(async () => {
      await Promise.all(Array.from({ length: 12 }, (_, group) =>
        document.fonts.load(`1000px GeluProjection${group}`)));
    });
  }
  const report = await page.evaluate(() => {
    const output = document.querySelector(".output-0");
    const root = document.querySelector(".root");
    const layernorm = document.querySelector(".layernorm-stage");
    const attentionHost = document.querySelector(".attention-host");
    const attentionRoot = attentionHost?.shadowRoot;
    const attentionSlot = attentionRoot?.querySelector('slot[name="next"]');
    const partial = (group) =>
      document.querySelector(`.partial-${group}-0`).getBoundingClientRect().width;
    const groupZeroMetrics = [...document.querySelectorAll('[class*="metric-0-"]')]
      .filter((element) => !element.classList.contains("partial"));
    const groupZeroProbes = [...document.querySelectorAll(".group-0 .probe")];
    const lastMetric = groupZeroMetrics.length - 1;
    const lastProbe = groupZeroProbes.length - 1;
    const ancestry = (element) => {
      const classes = [];
      while (element) {
        classes.push(element.className || element.tagName);
        element = element.parentElement;
      }
      return { depth: classes.length, tail: classes.slice(0, 8), head: classes.slice(-8) };
    };
    const measure = (label, width, positionAnchor = "") => {
      output.style.width = width;
      output.style.positionAnchor = positionAnchor;
      return {
        label,
        acceptedWidth: output.style.width,
        acceptedPositionAnchor: output.style.positionAnchor,
        measuredWidth: output.getBoundingClientRect().width,
      };
    };
    const before = {
      outputWidth: output.getBoundingClientRect().width,
      computedWidth: getComputedStyle(output).width,
      partials: [0, 1, 11].map(partial),
      metrics: [0, 1, lastMetric].map((index) =>
        document.querySelector(`.metric-0-${index}`).getBoundingClientRect().width),
      probes: [0, 1, lastProbe].map((index) => {
        const probe = document.querySelector(`.probe-0-${index}`);
        return [probe.getBoundingClientRect().width, probe.getBoundingClientRect().height];
      }),
      z: [0, 1, Math.max(0, 2 * lastProbe), Math.max(1, 2 * lastProbe + 1)].map((index) =>
        getComputedStyle(document.querySelector(".projection-0"))
          .getPropertyValue(`--z${index}`).trim()),
      x: [0, 1, 255, 256, 767].map((index) =>
        getComputedStyle(root).getPropertyValue(`--x${index}`).trim()),
      rootFontSettings: getComputedStyle(root).fontVariationSettings.slice(0, 180),
      projectionFont: getComputedStyle(document.querySelector(".projection-0")).fontFamily,
      projectionFontSettings: getComputedStyle(document.querySelector(".projection-0"))
        .fontVariationSettings.slice(0, 180),
      projectionFontLoaded: document.fonts.check("1000px GeluProjection0"),
      layernorm: layernorm ? {
        mean: getComputedStyle(layernorm).getPropertyValue("--ln-mean").trim().slice(0, 160),
        variance: getComputedStyle(layernorm).getPropertyValue("--ln-variance").trim().slice(0, 160),
        r1: getComputedStyle(layernorm).getPropertyValue("--r1-0").trim(),
        input: getComputedStyle(layernorm).getPropertyValue("--input-0").trim().slice(0, 240),
        sourceWidths: [0, 1, 767].map((index) =>
          document.querySelector(`.input-metric-${index}`).getBoundingClientRect().width),
      } : null,
      attention: attentionHost ? {
        hasShadowRoot: Boolean(attentionRoot),
        styleSheets: attentionRoot?.styleSheets.length ?? 0,
        slotRaw0: attentionSlot
          ? getComputedStyle(attentionSlot).getPropertyValue("--raw-0").trim()
          : "",
        slotRaw000: attentionSlot
          ? getComputedStyle(attentionSlot).getPropertyValue("--raw-000").trim()
          : "",
        assigned: attentionSlot?.assignedElements().map((element) => element.className) ?? [],
        firstMetricWidth: attentionRoot?.querySelector(".metric")
          ?.getBoundingClientRect().width ?? null,
      } : null,
      projectionAncestry: ancestry(document.querySelector(".projection-0")),
      rootAncestry: ancestry(root),
      deepestProbeAncestry: ancestry(groupZeroProbes.at(-1)),
    };
    const variants = [
      measure("one-anchor", "anchor-size(--g0o0 width)"),
      measure("one-anchor-positioned", "anchor-size(--g0o0 width)", "--g0o0"),
      measure(
        "two-anchors",
        "calc(anchor-size(--g0o0 width) + anchor-size(--g1o0 width))",
      ),
      measure(
        "two-anchors-positioned",
        "calc(anchor-size(--g0o0 width) + anchor-size(--g1o0 width))",
        "--g0o0",
      ),
    ];
    return { before, variants };
  });
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
