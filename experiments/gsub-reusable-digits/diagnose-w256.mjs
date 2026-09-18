#!/usr/bin/env node
/** Bounded browser/CLI diagnosis. Does not modify a font or benchmark report. */
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
const require = createRequire(import.meta.url);
const { chromium } = require(`${process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"}/playwright`);
const dir = path.dirname(fileURLToPath(import.meta.url));
const v = JSON.parse(await fs.readFile(path.join(dir, "reusable-w256/reference.json"), "utf8"));
const font = await fs.readFile(path.join(dir, v.fontFile));
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
const features = v.features.map(tag => `"${tag}" 1`).join(",");
const css = [`@font-face{font-family:${v.fontFamily};src:url(data:font/woff2;base64,${font.toString("base64")})}`,
  `.source{display:inline-block;white-space:pre;font-family:${v.fontFamily};font-size:1024px;line-height:1;height:1px;font-kerning:none;font-feature-settings:${features}}`,
  `@property --nonce{syntax:"<integer>";inherits:true;initial-value:0}`];
const counters = ["nonce var(--nonce)"], content = ["counter(nonce,nc)"];
for (let i = 0; i < v.width; i++) {
  css.push(`@property --x-${i}{syntax:"<integer>";inherits:true;initial-value:0}`);
  css.push(`@counter-style x${i}{system:fixed 0;symbols:${Array.from({length:16},(_,x)=>`"\\${(v.inputCodepoints[i]+x).toString(16)}"`).join(" ")};suffix:""}`);
  counters.push(`x${i} calc(var(--x-${i}) + 8)`); content.push(`counter(x${i},x${i})`);
}
css.push(`@counter-style nc{system:fixed 0;symbols:${Array.from({length:65},(_,i)=>`"\\${(v.nonceCodepoint+i).toString(16)}"`).join(" ")};suffix:""}`);
css.push(`.encoded::before{counter-reset:${counters.join(" ")};content:${content.join(" ")}}`);
const cases = [
  {label:"all-zero", input:Array(256).fill(0)},
  {label:"minimum-sum", input:v.weights.map(w=>w>0?-8:7)},
  {label:"maximum-sum", input:v.weights.map(w=>w>0?7:-8)},
];
const report = {fontSha256:hash(font), sourceSha256:hash(await fs.readFile(fileURLToPath(import.meta.url))), browserConsoleErrors:[], browserResults:[], cliResults:[]};
const browser = await chromium.launch({executablePath:process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",headless:true});
try {
  report.browserVersion = browser.version();
  const page = await browser.newPage();
  page.on("console",m=>{if(m.type()==="error")report.browserConsoleErrors.push(m.text());});
  await page.setContent(`<!doctype html><meta http-equiv="Content-Security-Policy" content="script-src 'none';object-src 'none'"><style>${css.join("\n")}</style><main id="rows"></main>`);
  report.browserResults = await page.evaluate(async ({v,cases}) => {
    await document.fonts.load(`1024px ${v.fontFamily}`, String.fromCodePoint(v.inputCodepoints[0]));
    await document.fonts.ready;
    const result=[];
    for (const test of cases) {
      const encoded = document.createElement("span"); encoded.className="source encoded";
      test.input.forEach((x,i)=>encoded.style.setProperty(`--x-${i}`,x)); document.querySelector("#rows").append(encoded);
      const style=getComputedStyle(encoded,"::before");
      const sum=test.input.reduce((s,x,i)=>s+x*v.weights[i],0);
      const row={label:test.label,expectedSourceWidth:v.output.offset+2*sum+1,fontLoaded:document.fonts.check(`1024px ${v.fontFamily}`),encodedWidth:encoded.getBoundingClientRect().width,computedContent:style.content,computedCounterReset:style.counterReset,literal:[]};
      for(const padding of [0,64,256,1024]) {
        const literal=document.createElement("span");literal.className="source";
        literal.textContent=String.fromCodePoint(v.nonceCodepoint).repeat(padding+1)+test.input.map((x,i)=>String.fromCodePoint(v.inputCodepoints[i]+x+8)).join("");
        document.querySelector("#rows").append(literal);
        const widths={padding,allFeatures:literal.getBoundingClientRect().width};
        if(padding===0) {
          for(const tag of ["ss02","ss03"]){literal.style.fontFeatureSettings=v.features.map(t=>`"${t}" ${t===tag?0:1}`).join(",");widths[`disabled_${tag}`]=literal.getBoundingClientRect().width;}
        }
        row.literal.push(widths);literal.remove();
      }
      encoded.remove();result.push(row);
    }
    return result;
  }, {v,cases});
} finally {await browser.close();}
const ttfPath=path.join(dir,v.fontFile.replace(/\.woff2$/,".ttf"));
report.ttfSha256=hash(await fs.readFile(ttfPath));
report.harfbuzzVersion=spawnSync("/opt/homebrew/bin/hb-shape",["--version"],{encoding:"utf8"}).stdout.trim();
for(const test of cases) for(const padding of [0,256]) {
  const input=String.fromCodePoint(v.nonceCodepoint).repeat(padding+1)+test.input.map((x,i)=>String.fromCodePoint(v.inputCodepoints[i]+x+8)).join("")+"\n";
  const shaped=spawnSync("/opt/homebrew/bin/hb-shape",[ttfPath,"--shapers=ot","--features=ss01=1,ss02=1,ss03=1,ss04=1","--output-format=json","--no-clusters"],{input,encoding:"utf8",maxBuffer:8*1024*1024});
  let glyphs=[];try{glyphs=JSON.parse(shaped.stdout.trim());}catch{}
  const counts={};for(const g of glyphs){const kind=g.g.replace(/\d+.*$/,"#");counts[kind]=(counts[kind]??0)+1;}
  report.cliResults.push({label:test.label,padding,status:shaped.status,stderr:shaped.stderr,glyphCount:glyphs.length,glyphKinds:counts,advance:glyphs.reduce((s,g)=>s+g.ax,0),firstGlyphs:glyphs.slice(0,12),lastGlyphs:glyphs.slice(-12)});
}
await fs.writeFile(path.join(dir,"diagnosis-w256.json"),JSON.stringify(report,null,2)+"\n");
console.log(JSON.stringify({browser:report.browserResults.map(({label,expectedSourceWidth,encodedWidth,literal,computedContent})=>({label,expectedSourceWidth,encodedWidth,literal,contentPrefix:computedContent.slice(0,60)})),cli:report.cliResults.map(({label,padding,status,glyphCount,glyphKinds,advance})=>({label,padding,status,glyphCount,glyphKinds,advance}))},null,2));
