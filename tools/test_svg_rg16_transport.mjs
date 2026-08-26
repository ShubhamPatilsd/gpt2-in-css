import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const url = process.env.SVG_RG16_URL ??
  "http://127.0.0.1:4178/experiments/svg-rg16-transport/index.html";

const browser = await chromium.launch({ executablePath, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 200 } });
  const start = performance.now();
  await page.goto(`${url}?run=${Date.now()}`, { waitUntil: "load", timeout: 120000 });
  const expectedBytes = await fs.readFile(new URL(
    "../experiments/svg-rg16-transport/expected-codes.npy", import.meta.url,
  ));
  // NPY v1 header ends at 10 + little-endian header length.
  const headerLength = expectedBytes.readUInt16LE(8);
  const payload = expectedBytes.subarray(10 + headerLength);
  await page.locator("image").evaluate((element) => {
    element.style.filter = "url(#pack)";
  });
  let png = await page.locator("svg").screenshot({ animations: "disabled", timeout: 120000 });
  let decoded = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const packedCodes = Array.from({ length: decoded.info.width }, (_, index) =>
    decoded.data[index * decoded.info.channels] * 256
      + decoded.data[index * decoded.info.channels + 1]
  );
  const expectedCodes = Array.from({ length: decoded.info.width }, (_, index) =>
    payload.readUInt16LE(index * 2)
  );
  const codeErrors = packedCodes.map((value, index) => value - expectedCodes[index]);

  await page.locator("image").evaluate((element) => {
    element.style.filter = "url(#pack) url(#decode)";
  });
  png = await page.locator("svg").screenshot({ animations: "disabled", timeout: 120000 });
  decoded = await sharp(png).raw().toBuffer({ resolveWithObject: true });
  const { data, info } = decoded;
  const actual = Array.from({ length: info.width }, (_, index) => data[index * info.channels]);
  const expected = Array.from({ length: info.width }, (_, index) =>
    payload.readUInt16LE(index * 2) / 257
  );
  const errors = actual.map((value, index) => value - expected[index]);
  console.log(JSON.stringify({
    packedMaxCodeError: Math.max(...codeErrors.map(Math.abs)),
    packedRmseCodes: Math.sqrt(codeErrors.reduce((sum, value) => sum + value * value, 0) / codeErrors.length),
    distinctPackedCodes: new Set(packedCodes).size,
    maxByteError: Math.max(...errors.map(Math.abs)),
    rmseBytes: Math.sqrt(errors.reduce((sum, value) => sum + value * value, 0) / errors.length),
    distinctOutputBytes: new Set(actual).size,
    milliseconds: performance.now() - start,
  }, null, 2));
} finally {
  await browser.close();
}
