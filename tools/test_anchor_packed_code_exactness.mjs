import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const origin = process.env.HVAR_ORIGIN ?? "http://127.0.0.1:4178";
const testedBits = (process.env.ANCHOR_PACKED_CODE_BITS ?? "8,9,10")
  .split(",").map(Number);

function decoder(bits, place) {
  const inline = "round(nearest,100cqi/1px,1)";
  const block = "round(nearest,100cqb/1px,1)";
  if (bits === 9) {
    const offset = place * bits;
    if (offset + bits <= 24) {
      return `mod(round(down,(${inline})/${2 ** offset},1),${2 ** bits})`;
    }
    if (offset >= 24) {
      return `mod(round(down,(${block})/${2 ** (offset - 24)},1),${2 ** bits})`;
    }
    const lowBits = 24 - offset;
    const highBits = bits - lowBits;
    return `calc(mod(round(down,(${inline})/${2 ** offset},1),${2 ** lowBits}) + ` +
      `${2 ** lowBits} * mod(${block},${2 ** highBits}))`;
  }
  const planeBits = bits / 2;
  const radix = 2 ** planeBits;
  const divisor = radix ** place;
  const plane = (packed) => `mod(round(down,(${packed})/${divisor},1),${radix})`;
  return `calc(${plane(inline)} + ${radix} * ${plane(block)})`;
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const chrome = browser.version();
const variants = [];
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 200 } });
  for (const bits of testedBits) {
    const suffix = bits === 6 ? "" : `-b${bits}`;
    const stem = `anchor-packed-full-mlp-local-2d${suffix}-hvar-sink`;
    const reference = JSON.parse(await fs.readFile(
      new URL(`../experiments/gpt2-block-css/${stem}-reference.json`, import.meta.url),
      "utf8",
    ));
    await page.goto(`${origin}/experiments/gpt2-block-css/${stem}.xhtml`, {
      waitUntil: "load",
      timeout: 180000,
    });
    await page.evaluate(() => document.fonts.ready);
    const valuesPerCarrier = Math.ceil(3072 / reference.groups);
    const registrations = Array.from({ length: valuesPerCarrier }, (_, place) =>
      `@property --probe${place}{syntax:"<number>";inherits:true;initial-value:-1}`).join("");
    const declarations = Array.from({ length: valuesPerCarrier }, (_, place) =>
      `--probe${place}:${decoder(bits, place)}`).join(";");
    await page.addStyleTag({ content: `${registrations}.packed-carrier,.sink{${declarations}}` });

    const cases = [];
    for (let caseIndex = 0; caseIndex < reference.settings.length; caseIndex += 1) {
      const expected = reference.codes[caseIndex];
      const measured = await page.evaluate(({ settings, groups, valuesPerCarrier, bits, expectedCodes }) => {
        document.querySelector("#scope").style.setProperty("--fc-settings", settings);
        for (let group = 0; group < groups; group += 1) {
          const carrier = document.querySelector(`.pack-${group}`);
          for (let place = 0; place < valuesPerCarrier; place += 1) {
            carrier.style.setProperty(
              `--d${place}`,
              `${expectedCodes[group * valuesPerCarrier + place] ?? 0}px`,
            );
          }
        }
        const geometryCodes = [];
        const decoded = [];
        for (let group = 0; group < groups; group += 1) {
          const rect = document.querySelector(`.pack-${group}`).getBoundingClientRect();
          const decodedStyle = getComputedStyle(document.querySelector(`.decode-${group}`));
          for (let place = 0; place < valuesPerCarrier; place += 1) {
            let code;
            if (bits === 9) {
              const stream = rect.width + rect.height * (2 ** 24);
              code = Math.floor(stream / (2 ** (bits * place))) % (2 ** bits);
            } else {
              const planeBits = bits / 2;
              const radix = 2 ** planeBits;
              const divisor = radix ** place;
              code = Math.floor(rect.width / divisor) % radix +
                radix * (Math.floor(rect.height / divisor) % radix);
            }
            geometryCodes.push(code);
            decoded.push(Number(decodedStyle.getPropertyValue(`--probe${place}`)));
          }
        }
        return { geometryCodes: geometryCodes.slice(0, 3072), decoded: decoded.slice(0, 3072) };
      }, {
        settings: reference.settings[caseIndex],
        groups: reference.groups,
        valuesPerCarrier,
        bits,
        expectedCodes: expected,
      });
      const transportFailures = [];
      const geometryFailures = [];
      for (let index = 0; index < expected.length; index += 1) {
        if (measured.decoded[index] !== measured.geometryCodes[index]) {
          transportFailures.push({
            index,
            geometryCode: measured.geometryCodes[index],
            decoded: measured.decoded[index],
          });
        }
        if (measured.geometryCodes[index] !== expected[index]) {
          geometryFailures.push({
            index,
            expected: expected[index],
            geometryCode: measured.geometryCodes[index],
          });
        }
      }
      cases.push({
        caseIndex,
        decoded: measured.decoded.length,
        transportFailures: transportFailures.length,
        firstTransportFailures: transportFailures.slice(0, 5),
        geometryFailures: geometryFailures.length,
        firstGeometryFailures: geometryFailures.slice(0, 5),
      });
    }
    variants.push({ bits, valuesPerCarrier, groups: reference.groups, cases });
  }
} finally {
  await browser.close();
}

const report = { chrome, variants };
await fs.writeFile(
  new URL("../experiments/direct-2d-packet-capacity/real-mlp-code-results.json", import.meta.url),
  `${JSON.stringify(report, null, 2)}\n`,
);
console.log(JSON.stringify(report, null, 2));
