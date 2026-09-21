// R4X support probe runner: JS-enabled probe page (measurement fixture, not the model page).
import { createRequire } from "node:module";
import fs from "node:fs";
const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const executablePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const { chromium } = require(`${dependencyRoot}/playwright`);
const file = process.argv[2]; const out = process.argv[3];
const browser = await chromium.launch({ executablePath, headless: true, args: ["--allow-file-access-from-files"] });
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 600 } });
  await page.goto(`file://${file}`, { waitUntil: "load" });
  await page.waitForTimeout(500);
  const r = await page.evaluate(() => window.__r4x);
  fs.writeFileSync(out, JSON.stringify(r, null, 1));
  console.log(JSON.stringify(r, null, 1));
} finally { await browser.close(); }
