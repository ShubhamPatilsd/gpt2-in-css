import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = "http://127.0.0.1:4178/experiments/avar2-gelu-linear-hvar-full-mlp-g13/connected-two-block-shadow-staged.html";

const variants = [
  { name: "block0-final", documentCss: ".b1-attention{display:none}", probe: "b0" },
  { name: "block0-state-capture", documentCss: ".b1-ln2-stage{display:none}", probe: "state" },
  { name: "block1-attention", documentCss: ".b1-mlp{display:none}", probe: "attention" },
  {
    name: "block1-fc-only",
    shadowCss: ".b1-projection,.b1-combined{display:none!important}",
    probe: "fc",
  },
  ...[1, 3, 6, 13].map((visible) => ({
    name: `block1-projection-groups-${visible}`,
    shadowCss: [
      ".b1-combined{display:none!important}",
      ...Array.from({ length: 13 - visible }, (_, index) =>
        `.b1-group-${visible + index}{display:none!important}`),
    ].join(""),
    probe: `projection:${visible - 1}`,
  })),
  { name: "block1-full-anchor-sum", probe: "full" },
];

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 1000, height: 120 },
  });
  const page = await context.newPage();
  await page.goto(url, { waitUntil: "load", timeout: 120000 });
  await page.evaluate(() => document.fonts.ready);
  const rounds = Number(process.env.HVAR_TWO_BLOCK_PROFILE_ROUNDS ?? 8);
  const results = [];

  for (const variant of variants) {
    await page.evaluate(({ documentCss, shadowCss }) => {
      let documentStyle = document.querySelector("#stage-profile-document");
      if (!documentStyle) {
        documentStyle = document.createElement("style");
        documentStyle.id = "stage-profile-document";
        document.head.append(documentStyle);
      }
      documentStyle.textContent = documentCss ?? "";
      const b1Root = document.querySelector(".b1-mlp").shadowRoot;
      let shadowStyle = b1Root.querySelector("#stage-profile-shadow");
      if (!shadowStyle) {
        shadowStyle = document.createElement("style");
        shadowStyle.id = "stage-profile-shadow";
        b1Root.append(shadowStyle);
      }
      shadowStyle.textContent = shadowCss ?? "";
      document.body.getBoundingClientRect();
    }, variant);
    const samples = [];
    for (let round = 0; round < rounds; round += 1) {
      const mode = (round + 1) % 4;
      const sample = await page.evaluate(({ mode, probe }) => {
        const started = performance.now();
        document.querySelector(`#case-${mode}`).checked = true;
        const b0Root = document.querySelector(".b0-mlp").shadowRoot;
        const b1Root = document.querySelector(".b1-mlp").shadowRoot;
        let value;
        if (probe === "b0") {
          value = b0Root.querySelector(".output-767").getBoundingClientRect().width;
        } else if (probe === "state") {
          value = getComputedStyle(document.querySelector(".b1-attention"))
            .getPropertyValue("--state-767");
        } else if (probe === "attention") {
          value = getComputedStyle(document.querySelector(".b1-ln2-stage"))
            .getPropertyValue("--raw-767");
        } else if (probe === "fc") {
          value = b1Root.querySelector(".b1-metric-12-235")
            .getBoundingClientRect().width;
        } else if (probe.startsWith("projection:")) {
          const group = Number(probe.split(":")[1]);
          value = b1Root.querySelector(`.b1-partial-${group}-767`)
            .getBoundingClientRect().width;
        } else {
          value = b1Root.querySelector(".b1-output-767").getBoundingClientRect().width;
        }
        return { milliseconds: performance.now() - started, value };
      }, { mode, probe: variant.probe });
      samples.push({ round, mode, ...sample });
    }
    const measured = samples.slice(4).map(({ milliseconds }) => milliseconds);
    results.push({
      name: variant.name,
      medianMilliseconds: median(measured),
      minimumMilliseconds: Math.min(...measured),
      maximumMilliseconds: Math.max(...measured),
      samples,
    });
    console.error(`finished ${variant.name}`);
  }

  console.log(JSON.stringify({
    chrome: await browser.version(),
    runtimeContainsJavaScript: false,
    rounds,
    results,
  }, null, 2));
  await context.close();
} finally {
  await browser.close();
}
