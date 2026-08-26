import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const directory = process.env.HVAR_FULL_MLP_DIR ?? "hvar-parallel-full-mlp";
const pageFile = process.env.HVAR_FULL_MLP_PAGE ?? "index.html";
const url = `http://127.0.0.1:4178/experiments/${directory}/${pageFile}`;
const reference = JSON.parse(await fs.readFile(
  new URL(`../experiments/${directory}/reference.json`, import.meta.url),
  "utf8",
));
const groups = reference.groups;
const groupWidths = reference.groupWidths ?? Array(groups).fill(reference.groupWidth);

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

const variants = [
  {
    name: "fc-only",
    css: ".projection,.combined{display:none!important}",
    probe: `.metric-${groups - 1}-${groupWidths.at(-1) - 1}`,
  },
  ...[...new Set([1, Math.min(3, groups), Math.min(6, groups), groups])].map((visible) => ({
    name: `projection-groups-${visible}`,
    css: [
      ".combined{display:none!important}",
      ...Array.from({ length: groups - visible }, (_, index) =>
        `.group-${visible + index}{display:none!important}`),
    ].join(""),
    probe: `.partial-${visible - 1}-767`,
  })),
  { name: "full-with-anchor-sum", css: "", probe: ".output-767" },
];

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 1000, height: 120 },
  });
  const page = await context.newPage();
  await page.goto(url, { waitUntil: "load", timeout: 120000 });
  await page.evaluate(() => document.fonts.ready);
  const results = [];
  for (const variant of variants) {
    console.error(`profiling ${variant.name}`);
    await page.evaluate((css) => {
      let style = document.querySelector("#profile-override");
      if (!style) {
        style = document.createElement("style");
        style.id = "profile-override";
        document.head.append(style);
      }
      style.textContent = css;
      document.body.getBoundingClientRect();
    }, variant.css);
    const samples = [];
    for (let round = 0; round < 12; round += 1) {
      const mode = (round + 1) % 4;
      const sample = await page.evaluate(({ mode, probe }) => {
        const started = performance.now();
        document.querySelector(`#case-${mode}`).checked = true;
        const element = document.querySelector(probe);
        if (!element) throw new Error(`missing profile probe ${probe}`);
        const width = element.getBoundingClientRect().width;
        return { mode, milliseconds: performance.now() - started, width };
      }, { mode, probe: variant.probe });
      samples.push({ round, ...sample });
    }
    const measured = samples.slice(4);
    results.push({
      name: variant.name,
      medianMilliseconds: median(measured.map(({ milliseconds }) => milliseconds)),
      minimumMilliseconds: Math.min(...measured.map(({ milliseconds }) => milliseconds)),
      maximumMilliseconds: Math.max(...measured.map(({ milliseconds }) => milliseconds)),
      samples,
    });
  }
  const report = {
    chrome: await browser.version(),
    runtimeContainsJavaScript: false,
    results,
  };
  await fs.writeFile(
    new URL(
      `../experiments/${directory}/profile-results${
        pageFile === "index.html" ? "" : `-${pageFile.replace(/\.html$/, "")}`
      }.json`,
      import.meta.url,
    ),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
  await context.close();
} finally {
  await browser.close();
}
