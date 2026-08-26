import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const propertyCount = 768;
const outputCount = 3072;
const rounds = Number(process.env.TRANSPORT_MAGNITUDE_ROUNDS ?? 12);
const declarations = (valueAt) => Array.from(
  { length: propertyCount },
  (_, index) => `--n2-${String(index).padStart(3, "0")}:${valueAt(index)}`,
).join(";");

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 400 } });
  await page.goto(
    "http://127.0.0.1:4178/experiments/gpt2-block-css/view-timeline-fc-timeline-only.html",
    { waitUntil: "load", timeout: 120000 },
  );
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  await page.addStyleTag({ content: [
    `.scope.zero{${declarations(() => "0.000")}}`,
    `.scope.large{${declarations((index) => index % 2 ? "-2.000" : "2.000")}}`,
    `.scope.scrub{${declarations((index) => index % 3 ? "0.375" : "-0.375")}}`,
  ].join("\n") });

  const measure = async (mode) => page.evaluate(async ({ mode, outputCount }) => {
    const scope = document.querySelector(".scope");
    scope.classList.remove("zero", "large", "scrub");
    scope.classList.add("scrub");
    document.body.getBoundingClientRect();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    scope.classList.remove("scrub");
    const started = performance.now();
    scope.classList.add(mode);
    document.body.getBoundingClientRect();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const style = getComputedStyle(document.querySelector("#fc-result"));
    let checksum = 0;
    for (let index = 0; index < outputCount; index += 1) {
      checksum += Number(style.getPropertyValue(`--p${index}`));
    }
    return { milliseconds: performance.now() - started, checksum };
  }, { mode, outputCount });

  for (let index = 0; index < 3; index += 1) {
    await measure("zero");
    await measure("large");
  }

  const samples = { zero: [], large: [] };
  for (let round = 0; round < rounds; round += 1) {
    const order = round % 2 ? ["large", "zero"] : ["zero", "large"];
    for (const mode of order) samples[mode].push(await measure(mode));
  }

  const summarize = (values) => {
    const ordered = values.map(({ milliseconds }) => milliseconds).sort((a, b) => a - b);
    const middle = Math.floor(ordered.length / 2);
    return {
      medianMilliseconds: ordered.length % 2
        ? ordered[middle]
        : (ordered[middle - 1] + ordered[middle]) / 2,
      minimumMilliseconds: ordered[0],
      maximumMilliseconds: ordered.at(-1),
      checksum: values.at(-1).checksum,
    };
  };
  const summary = { zero: summarize(samples.zero), large: summarize(samples.large) };
  console.log(JSON.stringify({
    chrome: await browser.version(),
    rounds,
    propertyCount,
    outputCount,
    method: "Alternating warmed class changes on one identical 3,072-timeline graph; every output forced.",
    summary,
    largeToZeroRatio: summary.large.medianMilliseconds / summary.zero.medianMilliseconds,
    samples,
  }, null, 2));
} finally {
  await browser.close();
}
