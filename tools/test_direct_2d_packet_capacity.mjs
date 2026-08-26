import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const root = path.resolve(import.meta.dirname, "..");
const outputDirectory = path.join(root, "experiments", "direct-2d-packet-capacity");
fs.mkdirSync(outputDirectory, { recursive: true });

function xorshift(seed) {
  let state = seed >>> 0;
  return () => {
    state ^= state << 13; state ^= state >>> 17; state ^= state << 5;
    return state >>> 0;
  };
}

function packetFixture(bits) {
  const radix = 2 ** bits;
  const valuesPerCarrier = Math.floor(48 / bits);
  const registrations = Array.from({ length: valuesPerCarrier }, (_, index) =>
    `@property --d${index}{syntax:"<number>";inherits:true;initial-value:-1}`).join("");
  const declarations = [];
  for (let index = 0; index < valuesPerCarrier; index += 1) {
    const offset = index * bits;
    if (offset + bits <= 24) {
      declarations.push(
        `--d${index}:mod(round(down,var(--packed-x)/${2 ** offset},1),${radix})`,
      );
    } else if (offset >= 24) {
      declarations.push(
        `--d${index}:mod(round(down,var(--packed-y)/${2 ** (offset - 24)},1),${radix})`,
      );
    } else {
      const lowBits = 24 - offset;
      const highBits = bits - lowBits;
      declarations.push(
        `--d${index}:calc(mod(round(down,var(--packed-x)/${2 ** offset},1),${2 ** lowBits}) + ` +
        `${2 ** lowBits} * mod(var(--packed-y),${2 ** highBits}))`,
      );
    }
  }
  return {
    html: '<!doctype html><meta charset="utf-8"><style>' + registrations +
      '.carrier{position:fixed;left:0;top:0;container-type:size;width:1px;height:1px}' +
      '.result{--packed-x:round(nearest,100cqi/1px,1);--packed-y:round(nearest,100cqb/1px,1);' +
      declarations.join(";") + '}</style><div class="carrier"><output class="result"></output></div>',
    radix,
    valuesPerCarrier,
  };
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const chrome = browser.version();
const packetResults = [];
let geometryResult;
try {
  const page = await browser.newPage();
  for (const bits of [6, 7, 8, 9, 10, 11, 12, 16]) {
    const fixture = packetFixture(bits);
    await page.setContent(fixture.html, { waitUntil: "load" });
    const random = xorshift(0x2d0000 + bits);
    const cases = 1024;
    const expected = [];
    for (let caseIndex = 0; caseIndex < cases; caseIndex += 1) {
      const codes = Array.from(
        { length: fixture.valuesPerCarrier },
        () => random() % (2 ** bits),
      );
      let stream = 0n;
      for (let index = 0; index < codes.length; index += 1) {
        stream += BigInt(codes[index]) << BigInt(bits * index);
      }
      const width = Number(stream & ((1n << 24n) - 1n));
      const height = Number(stream >> 24n);
      expected.push({ codes, width, height });
    }
    const result = await page.evaluate((samples) => {
      const carrier = document.querySelector(".carrier");
      const output = document.querySelector(".result");
      let failures = 0;
      let firstFailure = null;
      for (let caseIndex = 0; caseIndex < samples.length; caseIndex += 1) {
        const sample = samples[caseIndex];
        carrier.style.width = `${sample.width}px`;
        carrier.style.height = `${sample.height}px`;
        const style = getComputedStyle(output);
        const actual = sample.codes.map((_, index) => Number(style.getPropertyValue(`--d${index}`)));
        if (actual.some((value, index) => value !== sample.codes[index])) {
          failures += 1;
          firstFailure ??= { caseIndex, expected: sample.codes, actual, width: sample.width, height: sample.height };
        }
      }
      return { failures, firstFailure };
    }, expected);
    packetResults.push({
      bitsPerValue: bits,
      valuesPerCarrier: fixture.valuesPerCarrier,
      payloadBits: bits * fixture.valuesPerCarrier,
      cases,
      decodedValues: cases * fixture.valuesPerCarrier,
      ...result,
    });
  }

  await page.setContent(
    '<!doctype html><style>@property --lo{syntax:"<number>";inherits:true;initial-value:-1}' +
    '@property --hi{syntax:"<number>";inherits:true;initial-value:-1}' +
    '.carrier{position:fixed;container-type:size;width:1px;height:1px}' +
    '.result{--packed:round(nearest,100cqi/1px,1);--lo:mod(var(--packed),4096);' +
    '--hi:round(down,var(--packed)/4096,1)}</style>' +
    '<div class="carrier"><output class="result"></output></div>',
    { waitUntil: "load" },
  );
  const random = xorshift(0x2d24b17);
  const values = [0, 1, 2, 2 ** 23, 2 ** 24 - 2, 2 ** 24 - 1];
  while (values.length < 1024) values.push(random() % (2 ** 24));
  const boundary25 = [2 ** 24, 2 ** 24 + 1, 2 ** 24 + 2, 2 ** 25 - 2, 2 ** 25 - 1];
  while (boundary25.length < 1024) boundary25.push((2 ** 24) + (random() % (2 ** 24)));
  geometryResult = await page.evaluate(({ exactValues, boundaryValues }) => {
    const carrier = document.querySelector(".carrier");
    const output = document.querySelector(".result");
    const run = (samples) => {
      let failures = 0;
      let firstFailure = null;
      for (const expected of samples) {
        carrier.style.width = `${expected}px`;
        carrier.style.height = `${expected}px`;
        const style = getComputedStyle(output);
        const actual = Number(style.getPropertyValue("--lo")) +
          4096 * Number(style.getPropertyValue("--hi"));
        if (actual !== expected) {
          failures += 1;
          firstFailure ??= { expected, actual };
        }
      }
      return { samples: samples.length, failures, firstFailure };
    };
    return { bits24: run(exactValues), bits25: run(boundaryValues) };
  }, { exactValues: values, boundaryValues: boundary25 });
} finally {
  await browser.close();
}

const report = { chrome, packetResults, geometryResult };
fs.writeFileSync(path.join(outputDirectory, "browser-results.json"), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
