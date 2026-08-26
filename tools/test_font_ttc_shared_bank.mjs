import fs from "node:fs/promises";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const { chromium } = require(`${modules}/playwright`);
const reference = JSON.parse(await fs.readFile(new URL("../experiments/font-ttc-shared-bank/reference.json", import.meta.url), "utf8"));
const browser = await chromium.launch({executablePath:"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",headless:true});
try {
  const page = await browser.newPage({viewport:{width:900,height:300}}); const trials=[];
  for(let trial=0;trial<10;trial++){
    const started=performance.now();
    await page.goto(`http://127.0.0.1:4178/experiments/font-ttc-shared-bank/index.html?t=${trial}`,{waitUntil:"load",timeout:120000});
    await page.evaluate(async()=>{await document.fonts.ready;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))});
    const values=await page.evaluate(count=>{const s=getComputedStyle(document.querySelector("#result"));return Array.from({length:count},(_,i)=>Number(s.getPropertyValue(`--o${String(i).padStart(3,"0")}`)))},reference.expected.length);
    trials.push({milliseconds:performance.now()-started,values});
  }
  const values=trials.at(-1).values;const errors=values.map((v,i)=>v-reference.expected[i]);
  const warm=trials.slice(1).map(x=>x.milliseconds).sort((a,b)=>a-b);
  console.log(JSON.stringify({finite:values.filter(Number.isFinite).length,rmse:Math.sqrt(errors.reduce((s,e)=>s+e*e,0)/errors.length),maxError:Math.max(...errors.map(Math.abs)),first:values.slice(0,8),warmMedianMilliseconds:warm[Math.floor((warm.length-1)/2)],collectionBytes:reference.collection_bytes,standaloneBytes:reference.standalone_bytes,sharingRatio:reference.collection_bytes/reference.standalone_bytes},null,2));
} finally {await browser.close()}
