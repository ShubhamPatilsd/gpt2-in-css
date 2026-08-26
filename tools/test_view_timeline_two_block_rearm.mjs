import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);
const rounds = Number(process.env.VIEW_TIMELINE_TWO_BLOCK_REARM_ROUNDS ?? 7);
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);
const file = process.env.VIEW_TIMELINE_TWO_BLOCK_REARM_FILE ??
  "view-timeline-two-block-full-exact-gated-rearm.html";
const referenceFile = process.env.VIEW_TIMELINE_TWO_BLOCK_REARM_REFERENCE ??
  "view-timeline-two-block-full-exact-gated-rearm-reference.json";
const resultFile = process.env.VIEW_TIMELINE_TWO_BLOCK_REARM_RESULT ??
  "view-timeline-two-block-full-exact-gated-rearm-browser.json";
const reference = JSON.parse(await fs.readFile(
  new URL(referenceFile, directory),
));

function error(actual, expected) {
  const delta = actual.map((value, index) => value - expected[index]);
  return {
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
  await page.goto(
    "http://127.0.0.1:4178/experiments/gpt2-block-css/" +
      file,
    { waitUntil: "load", timeout: 180000 },
  );
  const report = await page.evaluate(async (count) => {
    const run = document.getElementById("b1-run");
    const scope = document.querySelector(".norm1");
    const gate = document.querySelector(".b1-norm");
    const final = document.getElementById("two-block-full");
    const initialStyle = getComputedStyle(scope);
    const original = Array.from({ length: 768 }, (_, index) => Number(
      initialStyle.getPropertyValue(`--x-${String(index).padStart(3, "0")}`),
    ));
    const mutated = original.map((value) => value * 0.999);
    const trials = [];

    async function frameState() {
      await new Promise((resolve) => requestAnimationFrame(resolve));
      const style = getComputedStyle(final);
      const output = Array.from({ length: 768 }, (_, index) => Number(
        style.getPropertyValue(`--b1-final-${String(index).padStart(3, "0")}`),
      ));
      return {
        output,
        checksum: output.reduce((sum, value) => sum + value, 0),
        gateVisibility: getComputedStyle(gate).contentVisibility,
        hostVisibility: getComputedStyle(scope).contentVisibility,
      };
    }

    for (let round = 0; round < count; round += 1) {
      run.checked = false;
      await frameState();
      await frameState();
      const values = round % 2 ? original : mutated;
      values.forEach((value, index) => scope.style.setProperty(
        `--x-${String(index).padStart(3, "0")}`,
        String(value),
      ));
      const started = performance.now();
      run.checked = true;
      const states = [];
      let stable = null;
      for (let frame = 0; frame < 12; frame += 1) {
        const state = await frameState();
        states.push({
          frame: frame + 1,
          milliseconds: performance.now() - started,
          checksum: state.checksum,
          gateVisibility: state.gateVisibility,
          hostVisibility: state.hostVisibility,
        });
        const previous = states.at(-2);
        if (
          state.gateVisibility === "visible" &&
          previous?.gateVisibility === "visible" &&
          Math.abs(previous.checksum - state.checksum) < 1e-9
        ) {
          stable = { ...state, milliseconds: performance.now() - started };
          break;
        }
      }
      trials.push({ states, stable });
    }
    return { trials };
  }, rounds);

  const completed = report.trials.filter(({ stable }) => stable);
  const warm = completed.slice(1).map(({ stable }) => stable.milliseconds).sort((a, b) => a - b);
  const outputChecksums = report.trials.map(({ stable }) => stable?.checksum ?? null);
  const restored = report.trials.map(({ stable }, round) =>
    round % 2 && stable ? error(stable.output, reference.expected) : null,
  ).filter(Boolean);
  const result = {
    chrome: await browser.version(),
    file,
    rounds,
    completed: completed.length,
    warmMedianMilliseconds: warm[Math.floor(warm.length / 2)] ?? null,
    outputChecksums,
    restored,
    states: report.trials.map(({ states }) => states),
  };
  await fs.writeFile(
    new URL(resultFile, directory),
    `${JSON.stringify(result, null, 2)}\n`,
  );
  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
