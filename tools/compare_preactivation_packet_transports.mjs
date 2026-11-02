import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const origin = process.env.HVAR_ORIGIN ?? "http://127.0.0.1:4178";
const rounds = Number(process.env.PREACTIVATION_PACKET_ROUNDS ?? 8);

const variants = (process.env.PREACTIVATION_PACKET_BITS ?? "3,4,6,8,9,10")
  .split(",")
  .map(Number)
  .map((bits) => ({ bits, suffix: bits === 6 ? "" : `-b${bits}` }))
  .map((variant) => ({
  ...variant,
  stem: `anchor-packed-full-mlp-local-2d${variant.suffix}-hvar-sink`,
}));

function percentile(values, fraction) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor((sorted.length - 1) * fraction)];
}

function error(actual, expected) {
  const delta = actual.map((value, index) => value - expected[index]);
  return {
    rmse: Math.sqrt(delta.reduce((sum, value) => sum + value * value, 0) / delta.length),
    maximum: Math.max(...delta.map(Math.abs)),
  };
}

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 800, height: 200 } });
  for (const variant of variants) {
    variant.reference = JSON.parse(await fs.readFile(
      new URL(`../experiments/gpt2-block-css/${variant.stem}-reference.json`, import.meta.url),
      "utf8",
    ));
    variant.page = await context.newPage();
    const started = performance.now();
    await variant.page.goto(
      `${origin}/experiments/gpt2-block-css/${variant.stem}.xhtml`,
      { waitUntil: "load", timeout: 180_000 },
    );
    await variant.page.evaluate(() => document.fonts.ready);
    variant.loadMilliseconds = performance.now() - started;
    variant.samples = [];
  }

  async function measure(variant, caseIndex) {
    return variant.page.evaluate(({ settings, caseIndex, reference }) => {
      const scope = document.querySelector("#scope");
      const started = performance.now();
      scope.style.setProperty("--fc-settings", settings);
      const widths = [...document.querySelectorAll(".projection-metric")].map(
        (element) => element.getBoundingClientRect().width,
      );
      const actual = widths.map((width, output) =>
        reference.hvarBase[output] +
        (width * reference.hvarUnitsPerPixel - reference.hvarBaseTotal) *
        reference.hvarScales[output]);
      return {
        caseIndex,
        milliseconds: performance.now() - started,
        actual,
      };
    }, {
      settings: variant.reference.settings[caseIndex],
      caseIndex,
      reference: {
        hvarBase: variant.reference.hvarBase,
        hvarUnitsPerPixel: variant.reference.hvarUnitsPerPixel,
        hvarBaseTotal: variant.reference.hvarBaseTotal,
        hvarScales: variant.reference.hvarScales,
      },
    });
  }

  // Prime both cases before the alternating comparison.
  for (const variant of variants) {
    await measure(variant, 1);
    await measure(variant, 0);
  }
  for (let round = 0; round < rounds; round += 1) {
    const ordered = round % 2 ? [...variants].reverse() : variants;
    const caseIndex = (round + 1) % 2;
    for (const variant of ordered) {
      const sample = await measure(variant, caseIndex);
      variant.samples.push({
        round,
        caseIndex,
        milliseconds: sample.milliseconds,
        againstRepresentedHvar: error(
          sample.actual,
          variant.reference.hvarExpected[caseIndex],
        ),
        againstDensePacked: error(
          sample.actual,
          variant.reference.expected[caseIndex],
        ),
        againstFullPrecisionPreactivation: error(
          sample.actual,
          variant.reference.fullPrecisionExpected[caseIndex],
        ),
      });
    }
    console.error(`round ${round + 1}/${rounds}`);
  }

  const report = {
    chrome: await browser.version(),
    runtimeContainsJavaScript: false,
    rounds,
    variants: [],
  };
  for (const variant of variants) {
    const measured = variant.samples.slice(2);
    const times = measured.map(({ milliseconds }) => milliseconds);
    const carriers = await variant.page.locator(".packed-carrier").count();
    report.variants.push({
      bits: variant.bits,
      valuesPerCarrier: 3072 / variant.reference.groups,
      carriers,
      sourceGlyphElements: await variant.page.locator(".source").count(),
      projectionGlyphElements: await variant.page.locator(".projection-metric").count(),
      loadMilliseconds: variant.loadMilliseconds,
      minimumMilliseconds: Math.min(...times),
      medianMilliseconds: percentile(times, 0.5),
      p90Milliseconds: percentile(times, 0.9),
      maximumMilliseconds: Math.max(...times),
      maximumRepresentedHvarRmse: Math.max(
        ...measured.map(({ againstRepresentedHvar }) => againstRepresentedHvar.rmse),
      ),
      maximumDensePackedRmse: Math.max(
        ...measured.map(({ againstDensePacked }) => againstDensePacked.rmse),
      ),
      maximumFullPrecisionRmse: Math.max(
        ...measured.map(
          ({ againstFullPrecisionPreactivation }) =>
            againstFullPrecisionPreactivation.rmse,
        ),
      ),
      maximumFullPrecisionError: Math.max(
        ...measured.map(
          ({ againstFullPrecisionPreactivation }) =>
            againstFullPrecisionPreactivation.maximum,
        ),
      ),
      cssBytes: variant.reference.cssBytes,
      htmlBytes: variant.reference.htmlBytes,
      fontBytes: variant.reference.hvarFontBytes,
      samples: variant.samples,
    });
  }
  await fs.writeFile(
    new URL(
      "../experiments/preactivation-packet-transport/real-mlp-results.json",
      import.meta.url,
    ),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
