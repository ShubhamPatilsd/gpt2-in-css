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
  const page = await browser.newPage();
  await page.setContent(`<!doctype html><meta charset="utf-8"><style>
    .carrier { position:absolute; display:inline-flex; font:10px monospace }
    .child { display:inline-block }
    #plain { width:max-content }
    #contained { width:max-content; container-type:inline-size }
    #calculated { width:calc-size(max-content,size); container-type:inline-size }
    #weighted { width:calc-size(max-content,size); container-type:inline-size }
    #weighted .a { width:calc-size(max-content,size * 2) }
    #weighted .b { width:calc-size(max-content,size * 4) }
  </style>
  <div id="plain" class="carrier"><i class="child">xxxx</i><i class="child">xxxxxx</i></div>
  <div id="contained" class="carrier"><i class="child">xxxx</i><i class="child">xxxxxx</i></div>
  <div id="calculated" class="carrier"><i class="child">xxxx</i><i class="child">xxxxxx</i></div>
  <div id="weighted" class="carrier"><i class="child a">xxxx</i><i class="child b">xxxxxx</i></div>`);
  const result = await page.evaluate(() => ({
    support: {
      calcSize: CSS.supports("width", "calc-size(max-content, size)"),
      weighted: CSS.supports("width", "calc-size(max-content, size * 4)"),
    },
    widths: Object.fromEntries(
      ["plain", "contained", "calculated", "weighted"].map((id) => [
        id,
        {
          width: getComputedStyle(document.getElementById(id)).width,
          scrollWidth: document.getElementById(id).scrollWidth,
          childWidths: [...document.getElementById(id).children]
            .map((element) => getComputedStyle(element).width),
        },
      ]),
    ),
  }));
  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
