import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const reference = JSON.parse(await fs.readFile(
  new URL("../experiments/feature-selected-metric-pair/reference.json", import.meta.url),
  "utf8",
));

function expected(inputs) {
  return reference.weights.map((pair) => pair.map((row) =>
    row.reduce((sum, weight, index) => sum + weight * inputs[index], 0)
  ));
}

function errorSummary(actual, wanted) {
  const errors = actual.flatMap((pair, pairIndex) =>
    pair.map((value, channel) => value - wanted[pairIndex][channel])
  );
  return {
    rmse: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    maxError: Math.max(...errors.map(Math.abs)),
  };
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
let report;
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
  await page.goto(
    "http://127.0.0.1:4178/experiments/feature-selected-metric-pair/index.html",
    { waitUntil: "load", timeout: 120000 },
  );
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  const scale = reference.unitsPerEm / reference.fontSize;
  const read = () => page.locator(".pair").evaluateAll((elements, [factor, base]) =>
    elements.map((element) => {
      const rect = element.getBoundingClientRect();
      return [rect.width * factor - base, rect.height * factor - base];
    }), [scale, reference.base]);
  const initial = await read();
  const faceValues = await page.locator(".face-pair").evaluateAll(
    (elements, [factor, base]) => elements.map((element) => {
      const rect = element.getBoundingClientRect();
      return [rect.width * factor - base, rect.height * factor - base];
    }),
    [scale, reference.base],
  );
  const glyphSums = await page.locator(".glyph-check").evaluateAll(
    (elements, [factor, base]) => elements.map((element) =>
      element.getBoundingClientRect().width * factor - 2 * base
    ),
    [scale, reference.base],
  );
  const wantedInitial = expected(reference.inputs);
  const glyphSumErrors = glyphSums.map((value, index) =>
    value - wantedInitial[index][0] - wantedInitial[index][1]
  );
  const dynamicSelections = [];
  for (let choice = 1; choice <= reference.pairs; choice += 1) {
    const selected = choice - 1;
    const wanted = wantedInitial[selected][0] + wantedInitial[selected][1];
    await page.locator("#dynamic-var").evaluate(
      (element, value) => { element.style.setProperty("--choice", `${value}`); },
      choice,
    );
    await page.locator("#dynamic-round").evaluate(
      (element, value) => { element.style.setProperty("--choice-number", `${value + 0.2}`); },
      choice,
    );
    const [variable, rounded] = await Promise.all([
      page.locator("#dynamic-var").evaluate(
        (element, [factor, base]) => element.getBoundingClientRect().width * factor - 2 * base,
        [scale, reference.base],
      ),
      page.locator("#dynamic-round").evaluate(
        (element, [factor, base]) => element.getBoundingClientRect().width * factor - 2 * base,
        [scale, reference.base],
      ),
    ]);
    dynamicSelections.push({
      choice,
      variable,
      rounded,
      variableError: variable - wanted,
      roundedError: rounded - wanted,
    });
  }
  const mutations = [];
  for (let sample = 0; sample < 20; sample += 1) {
    const inputs = [...reference.inputs];
    inputs[0] = sample % 2 === 0 ? -1 : 1;
    const settings = inputs.map((value, index) =>
      `"X${String(index).padStart(3, "0")}" ${value}`
    ).join(",");
    const started = performance.now();
    await page.locator(".producer").evaluate(
      (element, value) => { element.style.fontVariationSettings = value; },
      settings,
    );
    const actual = await read();
    mutations.push({
      milliseconds: performance.now() - started,
      ...errorSummary(actual, expected(inputs)),
    });
  }
  const warmTimes = mutations.slice(2).map(({ milliseconds }) => milliseconds)
    .toSorted((left, right) => left - right);
  report = {
    runtimeJavaScript: false,
    initial: errorSummary(initial, expected(reference.inputs)),
    faceDescriptor: errorSummary(faceValues, expected(reference.inputs)),
    renderedGlyphSumMaxError: Math.max(...glyphSumErrors.map(Math.abs)),
    renderedGlyphSums: glyphSums,
    dynamicVariableMaxError: Math.max(...dynamicSelections.map(({ variableError }) => Math.abs(variableError))),
    dynamicRoundedMaxError: Math.max(...dynamicSelections.map(({ roundedError }) => Math.abs(roundedError))),
    dynamicSelections,
    mutationRmseMaximum: Math.max(...mutations.map(({ rmse }) => rmse)),
    mutationMaxErrorMaximum: Math.max(...mutations.map(({ maxError }) => maxError)),
    warmMutationMedianMilliseconds: warmTimes[Math.floor(warmTimes.length / 2)],
    initialValues: initial,
    faceDescriptorValues: faceValues,
  };
} finally {
  await browser.close();
}
await fs.writeFile(
  new URL("../experiments/feature-selected-metric-pair/browser.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
