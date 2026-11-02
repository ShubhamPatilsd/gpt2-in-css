import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.PLAYWRIGHT_NODE_MODULES ??
  new URL("../node_modules", import.meta.url).pathname;
const { chromium } = require(`${dependencyRoot}/playwright`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const context = Number(process.env.ATTENTION_CONTEXT ?? 2);
const stem = `attention-context-${context}-qkv-streaming-key-anchor`;
const directory = new URL("../experiments/gpt2-block-css/", import.meta.url);
const reference = JSON.parse(await fs.readFile(
  new URL(`${stem}-reference.json`, directory), "utf8",
));

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 300 } });
  await page.goto(
    `http://127.0.0.1:4178/experiments/gpt2-block-css/${stem}.html`,
    { waitUntil: "load", timeout: 180000 },
  );
  const actual = await page.locator("#attention-result").evaluate((element, contextLength) => {
    const styles = getComputedStyle(element);
    const bank = (contextLength - 1) % 2 === 0 ? "a" : "b";
    return {
      scores: Array.from({ length: 12 }, (_, head) =>
        Number.parseFloat(styles.getPropertyValue(`--score-${head}`))),
      maxima: Array.from({ length: 12 }, (_, head) =>
        Number.parseFloat(styles.getPropertyValue(`--m-${bank}-${head}`))),
      denominators: Array.from({ length: 12 }, (_, head) =>
        Number.parseFloat(styles.getPropertyValue(`--l-${bank}-${head}`))),
      context: Array.from({ length: 8 }, (_, index) =>
        Number.parseFloat(styles.getPropertyValue(`--context-${String(index).padStart(3, "0")}`))),
      scoreProgress: Array.from({ length: 12 }, (_, head) =>
        styles.getPropertyValue(`--stream-ka-v-${contextLength}-${contextLength - 1}-sp-${head}`).trim()),
    };
  }, context);
  const shadowMetrics = await page.locator(`stream-ka-v-${context}-${context - 1}`).evaluate((host, contextLength) => ({
    scoreWidths: Array.from(host.shadowRoot.querySelectorAll(".score-metric"), (element) =>
      getComputedStyle(element).width),
    keyWidths: Array.from(host.shadowRoot.querySelectorAll(".metric")).slice(0, 4).map((element) =>
      getComputedStyle(element).width),
    slotAnimations: host.shadowRoot.querySelector("slot").getAnimations().slice(0, 3).map((animation) => ({
      currentTime: String(animation.currentTime),
      timeline: animation.timeline?.constructor?.name,
    })),
    slotAnimationTimeline: getComputedStyle(host.shadowRoot.querySelector("slot")).animationTimeline,
    slotProgress: Array.from({ length: 3 }, (_, head) =>
      getComputedStyle(host.shadowRoot.querySelector("slot")).getPropertyValue(
        `--stream-ka-v-${contextLength}-${contextLength - 1}-sp-${head}`
      ).trim()),
  }), context);
  console.log(JSON.stringify({
    expectedLastScores: reference.scores.map((head) => head.at(-1)),
    expectedContext: reference.context.slice(0, 8),
    actual,
    shadowMetrics,
  }, null, 2));
} finally {
  await browser.close();
}
