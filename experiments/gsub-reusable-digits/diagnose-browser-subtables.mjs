#!/usr/bin/env node
/** Validator-presence control, explicitly not a repaired weighted-sum test. */
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { createHash } from "node:crypto";
const require=createRequire(import.meta.url);
const {chromium}=require(`${process.env.CODEX_NODE_MODULES??"/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"}/playwright`);
const dir=path.dirname(fileURLToPath(import.meta.url));
const records=JSON.parse(await fs.readFile(path.join(dir,"diagnosis-subtables.json"),"utf8")).records;
const selected=records.filter(r=>["original-w64","original-w256","full-program-pad-262144","pruned-subtables-16383","pruned-subtables-16384"].includes(r.label));
const report={sourceSha256:createHash("sha256").update(await fs.readFile(fileURLToPath(import.meta.url))).digest("hex"),
  purpose:"Observe whether product/publication substitutions exist in Chrome. One seed glyph is used with reduction and dependent arithmetic disabled; width64 means these substitutions ran. Rule-pruned fonts do not implement the original weighted sum.",results:[],errors:[]};
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH??"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",headless:true});
try{
  report.browserVersion=browser.version();const page=await browser.newPage();
  page.on("console",m=>{if(m.type()==="error")report.errors.push(m.text());});
  for(let i=0;i<selected.length;i++){
    const r=selected[i],data=await fs.readFile(path.join(dir,r.path)),family=`Diagnostic${i}`;
    await page.setContent(`<!doctype html><meta http-equiv="Content-Security-Policy" content="script-src 'none'"><style>@font-face{font-family:${family};src:url(data:font/ttf;base64,${data.toString("base64")})}.probe{font:1024px/1 ${family};display:inline-block;white-space:pre;font-feature-settings:"ss01" 1,"ss02" 0,"ss03" 0,"ss04" 1}</style><span class="probe">&#xE800;&#xE008;</span>`);
    const observed=await page.evaluate(async family=>{await document.fonts.load(`1024px ${family}`,"\ue008");await document.fonts.ready;return{fontLoaded:document.fonts.check(`1024px ${family}`),width:document.querySelector(".probe").getBoundingClientRect().width};},family);
    report.results.push({label:r.label,fontSha256:createHash("sha256").update(data).digest("hex"),subtableCount:r.fontToolsTotalReferencedSubtables,arithmeticPreserved:r.arithmeticPreserved??true,...observed});
  }
}finally{await browser.close();}
await fs.writeFile(path.join(dir,"diagnosis-browser-subtables.json"),JSON.stringify(report,null,2)+"\n");
console.log(JSON.stringify(report,null,2));
