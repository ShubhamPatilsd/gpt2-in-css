import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const origin = process.env.HVAR_ORIGIN ?? "http://127.0.0.1:4178";

const variants = [
  { name: "12x256", directory: "avar2-gelu-linear-hvar-full-mlp" },
  { name: "13x236-238", directory: "avar2-gelu-linear-hvar-full-mlp-g13" },
];
for (const variant of variants) {
  variant.reference = JSON.parse(await fs.readFile(
    new URL(`../experiments/${variant.directory}/reference.json`, import.meta.url),
    "utf8",
  ));
}

function percentile(values, fraction) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor((sorted.length - 1) * fraction)];
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 1000, height: 120 },
  });
  for (const variant of variants) {
    variant.page = await context.newPage();
    const started = performance.now();
    await variant.page.goto(
      `${origin}/experiments/${variant.directory}/connected-two-block-shadow-staged.html`,
      { waitUntil: "load", timeout: 120000 },
    );
    await variant.page.evaluate(() => document.fonts.ready);
    variant.loadMilliseconds = performance.now() - started;
    variant.samples = [];
  }

  const rounds = Number(process.env.HVAR_GROUP_COUNT_ROUNDS ?? 12);
  for (let round = 0; round < rounds; round += 1) {
    const ordered = round % 2 ? [...variants].reverse() : variants;
    for (const variant of ordered) {
      const mode = (round + 1) % variant.reference.tokenIds.length;
      const sample = await variant.page.evaluate((caseId) => {
        const started = performance.now();
        document.querySelector(`#case-${caseId}`).checked = true;
        const host = document.querySelector(".b1-mlp");
        const width = host.shadowRoot.querySelector(".b1-output-767")
          .getBoundingClientRect().width;
        return { milliseconds: performance.now() - started, width };
      }, mode);
      const output = (
        sample.width - variant.reference.baseAdvance
      ) / variant.reference.block1OutputScale;
      variant.samples.push({
        round,
        mode,
        ...sample,
        output,
        error: Math.abs(output - variant.reference.block1RepresentedOutputs[mode][767]),
      });
    }
    console.error(`round ${round + 1}/${rounds}`);
  }

  const report = {
    chrome: await browser.version(),
    runtimeContainsJavaScript: false,
    rounds,
    variants: variants.map(({ name, directory, reference, loadMilliseconds, samples }) => {
      const measured = samples.slice(4).map(({ milliseconds }) => milliseconds);
      return {
        name,
        directory,
        groups: reference.groups,
        elements: null,
        htmlBytes: reference.connectedTwoBlockShadowStagedHtmlBytes,
        projectionFontBytes: reference.block1ProjectionFontBytes,
        loadMilliseconds,
        minimumMilliseconds: Math.min(...measured),
        medianMilliseconds: percentile(measured, 0.5),
        p90Milliseconds: percentile(measured, 0.9),
        maximumMilliseconds: Math.max(...measured),
        maximumProbeError: Math.max(...samples.map(({ error }) => error)),
        samples,
      };
    }),
  };
  for (let index = 0; index < variants.length; index += 1) {
    report.variants[index].elements = await variants[index].page.locator("*").count();
  }
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
