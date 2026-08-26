import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const root = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${root}/playwright`);

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 300 } });
  await page.goto("http://127.0.0.1:4178/experiments/view-timeline-4d-probe.html", {
    waitUntil: "load",
  });
  await page.evaluate(() => new Promise(
    (resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)),
  ));
  const actual = await page.evaluate(() => {
    const style = getComputedStyle(document.querySelector("#result"));
    return Object.fromEntries(
      ["x", "y", "w", "h", "xc", "xe", "yc", "ye"].map(
        (name) => [name, Number(style.getPropertyValue(`--${name}`))],
      ),
    );
  });
  const expected = { x: 23, y: 29, w: 37, h: 41 };
  const errors = Object.fromEntries(
    Object.entries(expected).map(([name, value]) => [name, actual[name] - value]),
  );
  console.log(JSON.stringify({ expected, actual, errors }, null, 2));
  if (Object.values(errors).some((error) => Math.abs(error) > 0.01)) process.exitCode = 1;
} finally {
  await browser.close();
}
