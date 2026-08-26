import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dependencyRoot = process.env.CODEX_NODE_MODULES ??
  "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sharp = require(`${dependencyRoot}/sharp`);
const executablePath = process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

for (const launch of [
  { name: "default", args: [] },
  { name: "gpu-raster", args: ["--enable-gpu-rasterization"] },
  { name: "scrgb-linear-display", args: ["--force-color-profile=scrgb-linear"] },
  { name: "hdr10-display", args: ["--force-color-profile=hdr10"] },
]) {
  const browser = await chromium.launch({ executablePath, headless: true, args: launch.args });
  try {
    const page = await browser.newPage({ viewport: { width: 80, height: 20 } });
    await page.goto("http://127.0.0.1:4178/experiments/svg-16bit-precision/index.html", {
      waitUntil: "load",
    });
    const modes = {};
    for (const mode of ["sRGB", "linearRGB", "default"]) {
      await page.locator("filter").evaluate((filter, selectedMode) => {
        if (selectedMode === "default") {
          filter.removeAttribute("color-interpolation-filters");
        } else {
          filter.setAttribute("color-interpolation-filters", selectedMode);
        }
      }, mode);
      const png = await page.locator("svg").screenshot();
      const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
      modes[mode] = Array.from({ length: 2 }, (_, y) =>
        Array.from({ length: 10 }, (_, x) => data[(y * info.width + x) * info.channels]));
    }
    const values = [1, 2, 4, 8].map((value) => value / 65535);
    const floods = values.map((value, index) =>
      `<feFlood x="${index}" y="0" width="1" height="1" `
      + `flood-color="color(srgb ${value} 0 0)" result="f${index}"/>`
      + `<feColorMatrix in="f${index}" values="8191.875 0 0 0 0  `
      + `0 8191.875 0 0 0  0 0 8191.875 0 0  0 0 0 0 1" result="s${index}"/>`
    ).join("");
    await page.setContent(`<!doctype html><style>html,body{margin:0;background:black}</style>
      <svg width="4" height="1" viewBox="0 0 4 1" xmlns="http://www.w3.org/2000/svg">
      <defs><filter id="flood-probe" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
      x="0" y="0" width="4" height="1" color-interpolation-filters="sRGB">${floods}
      <feMerge>${values.map((_, index) => `<feMergeNode in="s${index}"/>`).join("")}</feMerge>
      </filter></defs><rect width="4" height="1" filter="url(#flood-probe)"/></svg>`);
    const floodModes = {};
    for (const mode of ["sRGB", "linearRGB"]) {
      await page.locator("filter").evaluate((filter, selectedMode) =>
        filter.setAttribute("color-interpolation-filters", selectedMode), mode);
      const png = await page.locator("svg").screenshot();
      const { data, info } = await sharp(png).raw().toBuffer({ resolveWithObject: true });
      floodModes[mode] = Array.from({ length: 4 }, (_, x) => data[x * info.channels]);
    }
    const tiny = 1 / 65535;
    await page.setContent(`<!doctype html><style>html,body{margin:0;background:black}</style>
      <svg width="5" height="1" viewBox="0 0 5 1" xmlns="http://www.w3.org/2000/svg">
      <defs><filter id="boundary-probe" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
      x="0" y="0" width="5" height="1" color-interpolation-filters="sRGB">
      <feFlood x="0" y="0" width="5" height="1" flood-color="white" result="white"/>
      ${Array.from({ length: 5 }, (_, index) =>
        `<feFlood x="${index}" y="0" width="1" height="1" flood-color="color(srgb ${tiny} 0 0)" result="b${index}"/>`
      ).join("")}
      <feOffset in="b0" dx="0" result="m0"/>
      <feConvolveMatrix in="b1" order="1 1" kernelMatrix="1" divisor="1" result="m1"/>
      <feComponentTransfer in="b2" result="m2"><feFuncR type="identity"/><feFuncG type="identity"/><feFuncB type="identity"/></feComponentTransfer>
      <feComposite in="b3" in2="white" operator="arithmetic" k1="1" result="m3"/>
      <feTile in="b4" x="4" y="0" width="1" height="1" result="m4"/>
      ${Array.from({ length: 5 }, (_, index) =>
        `<feColorMatrix in="m${index}" values="8191.875 0 0 0 0  0 8191.875 0 0 0  0 0 8191.875 0 0  0 0 0 0 1" result="o${index}"/>`
      ).join("")}
      <feMerge>${Array.from({ length: 5 }, (_, index) => `<feMergeNode in="o${index}"/>`).join("")}</feMerge>
      </filter></defs><rect width="5" height="1" filter="url(#boundary-probe)"/></svg>`);
    const boundaryPng = await page.locator("svg").screenshot();
    const { data: boundaryData, info: boundaryInfo } = await sharp(boundaryPng)
      .raw().toBuffer({ resolveWithObject: true });
    const boundaryModes = ["offset", "convolve", "transfer", "composite", "tile"]
      .map((name, x) => ({ name, value: boundaryData[x * boundaryInfo.channels] }));
    console.log(JSON.stringify({ launch: launch.name, modes, floodModes, boundaryModes }, null, 2));
  } finally {
    await browser.close();
  }
}
