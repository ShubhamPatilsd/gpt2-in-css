import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
const require=createRequire(import.meta.url);
const {chromium}=require('/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const out=path.dirname(fileURLToPath(import.meta.url));
const report={purpose:'Separate HVAR256 font packaging from axis/arithmetic validity. Default-axis smoke only.',harnessSha256:createHash('sha256').update(await fs.readFile(fileURLToPath(import.meta.url))).digest('hex'),results:[],messages:[]};
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
try {
 report.browser=browser.version();const page=await browser.newPage();page.on('console',m=>{if(m.type()==='error')report.messages.push(m.text());});
 for(const ext of ['ttf','woff2']) {
  const bytes=await fs.readFile(path.join(out,`hvar/n256.${ext}`));
  await page.setContent(`<!doctype html><meta http-equiv="Content-Security-Policy" content="script-src 'none'"><style>@font-face{font-family:Control;src:url(data:font/${ext};base64,${bytes.toString('base64')})}span{display:inline-block;font:1024px/1 Control}</style><span>&#xE000;</span>`);
  const observed=await page.evaluate(async()=>{let error=null;try{await document.fonts.load('1024px Control','\ue000');await document.fonts.ready;}catch(e){error=String(e);}return{loaded:document.fonts.check('1024px Control','\ue000'),width:document.querySelector('span').getBoundingClientRect().width,error};});
  report.results.push({format:ext,sha256:createHash('sha256').update(bytes).digest('hex'),...observed});
 }
} finally {await browser.close();}
await fs.writeFile(path.join(out,'diagnosis-hvar256.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
