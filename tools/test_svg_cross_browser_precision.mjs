import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES
  ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium, firefox } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const root = path.resolve(new URL("..", import.meta.url).pathname);
const experiment = path.join(root, "experiments/svg-cross-browser-precision");
const reference = JSON.parse(await fs.readFile(path.join(experiment, "reference.json"), "utf8"));
const browserName = process.env.SVG_PRECISION_BROWSER ?? "firefox";

const server = http.createServer(async (request, response) => {
  try {
    const filename = path.join(root, decodeURIComponent(new URL(request.url, "http://x").pathname));
    if (!filename.startsWith(`${root}${path.sep}`)) throw new Error("outside workspace");
    const body = await fs.readFile(filename);
    const contentType = path.extname(filename) === ".html" ? "text/html" : "application/octet-stream";
    response.writeHead(200, { "content-type": contentType });
    response.end(body);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const { port } = server.address();

const browserType = browserName === "chromium" ? chromium : firefox;
const launchOptions = browserName === "chromium"
  ? {
      executablePath: process.env.CHROME_PATH
        ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
      headless: true,
    }
  : { headless: true };

let browser;
try {
  browser = await browserType.launch(launchOptions);
  const page = await browser.newPage({
    viewport: { width: reference.samples, height: reference.rows.length },
    javaScriptEnabled: false,
  });
  await page.goto(
    `http://127.0.0.1:${port}/experiments/svg-cross-browser-precision/index.html`,
    { waitUntil: "load", timeout: 120_000 },
  );
  await page.locator("svg").waitFor({ state: "visible" });
  const png = await page.locator("svg").screenshot({ timeout: 120_000 });
  const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const rows = reference.rows.map((metadata) => {
    const values = Array.from({ length: reference.samples }, (_, column) =>
      data[(metadata.row * info.width + column) * info.channels]);
    return {
      ...metadata,
      uniqueLevels: new Set(values).size,
      values,
    };
  });
  const report = {
    browser: browserName,
    version: await browser.version(),
    screenshot: { width: info.width, height: info.height, channels: info.channels },
    rows,
  };
  await fs.mkdir(experiment, { recursive: true });
  await fs.writeFile(
    path.join(experiment, `${browserName}.json`),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  if (browser) await browser.close();
  server.closeAllConnections();
  await new Promise((resolve) => server.close(resolve));
}
