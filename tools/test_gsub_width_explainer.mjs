#!/usr/bin/env node
// Functional checks of the explainer, not performance measurements.
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';
const require = createRequire(import.meta.url);
let playwright;
try { playwright = require('playwright'); }
catch { playwright = require('/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'); }
const base = process.env.EXPLAINER_URL || 'http://127.0.0.1:8765/experiments/gsub-width-explainer/index.html';
const output = resolve('experiments/gsub-width-explainer/verification');
await mkdir(output, {recursive:true});
const browser = await playwright.chromium.launch({
  executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless:true,
});
const page = await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
const errors = [], failedRequests = [];
page.on('pageerror', e => errors.push(e.message));
page.on('requestfailed', r => failedRequests.push({url:r.url(),error:r.failure()?.errorText}));
const report = {browser:await browser.version(),scope:'Explainer correctness and rendering; not a speed benchmark',errors,failedRequests};
try {
  await page.goto(base);
  await page.waitForFunction(() => document.querySelector('#live-source').dataset.verified === 'true', {timeout:15000});
  report.initialNative = await page.locator('#native-status').textContent();
  report.exhaustive = await page.evaluate(async () => {
    await document.fonts.ready;
    const source=document.querySelector('#live-source'), decoder=document.querySelector('#live-decoded'), failures=[];
    for(let a=0;a<16;a++)for(let b=0;b<16;b++){
      source.style.setProperty('--gw-a',a);source.style.setProperty('--gw-b',b);
      let x=a,y=b;
      for(let step=0;step<16;step++){const next=(x+y*y+3*y+step+1)%16;x=y;y=next;}
      const width=source.getBoundingClientRect().width, css=getComputedStyle(decoder);
      const dx=Number(css.getPropertyValue('--gw-dx')),dy=Number(css.getPropertyValue('--gw-dy')),consumer=decoder.getBoundingClientRect().width;
      if(width!==64+16*x+y||dx!==x||dy!==y||consumer!==width) failures.push({a,b,x,y,width,dx,dy,consumer});
    }
    return {cases:256,failures};
  });
  assert.equal(report.exhaustive.failures.length,0,'Actual font/native decoder must match every input state');
  await page.locator('#input-x').fill('3');await page.locator('#input-y').fill('5');
  await page.locator('#input-x').dispatchEvent('input');
  assert.match(await page.locator('#literal-rules').textContent(), /p0v53 → x1v5 \+ y1v12/);
  await page.locator('#disable-step').check();
  await page.waitForFunction(()=>document.querySelector('#native-width').textContent==='0');
  assert.equal(await page.locator('#native-x').textContent(),'—');
  report.disabledStep = await page.locator('#native-status').textContent();
  await page.locator('#disable-step').uncheck();
  await page.waitForFunction(()=>document.querySelector('#native-status').textContent.startsWith('Exact match.'));
  await page.getByRole('button',{name:'Inspect transition 16',exact:true}).click();
  assert.match(await page.locator('#transition-math').textContent(),/Step 16:/);
  await page.getByRole('button',{name:'Inspect transition 1',exact:true}).click();
  await page.locator('[data-width="768"]').click();
  assert.match(await page.locator('#lookup-expression').textContent(),/3,072/);
  report.lookup768 = await page.locator('#lookup-value').textContent();
  assert.match(report.lookup768,/10924/);
  await page.locator('#lookup-bits').selectOption('16');
  assert.match(await page.locator('#lookup-expression').textContent(),/12,288/);
  await page.locator('#lookup-bits').selectOption('4');
  report.realNeuron = await page.evaluate(()=>{
    const n=JSON.parse(document.querySelector('#evidence-data').textContent).neuron;
    const sum=n.input.reduce((s,x,i)=>s+x*n.weights[i],n.bias);
    return {inputs:n.input.length,nonzeroWeights:n.weights.filter(x=>x!==0).length,sum,reference:n.preactivationFloat64,displayed:document.querySelector('#neuron-sum').textContent};
  });
  assert.equal(report.realNeuron.inputs,768);assert.equal(report.realNeuron.nonzeroWeights,768);
  assert.ok(Math.abs(report.realNeuron.sum-report.realNeuron.reference)<1e-12);
  assert.equal(report.realNeuron.displayed,'−0.105234006');
  await page.locator('[data-count="2"]').click();
  assert.equal(await page.locator('.coordinate.excluded').count(),766);
  await page.locator('[data-count="768"]').click();
  await page.locator('#coordinate-index').fill('767');
  assert.equal(await page.locator('#coordinate-label').textContent(),'767');
  await page.locator('#coordinate-index').fill('0');
  await page.locator('#timing-phase').selectOption('repeated-state');
  assert.match(await page.locator('#timing-verdict').textContent(),/6.5 ms.*36%/);
  await page.locator('#timing-phase').selectOption('unique-text');
  assert.match(await page.locator('#timing-verdict').textContent(),/7.0 ms.*31%/);
  await page.locator('[data-copies="1"]').click();
  assert.equal(await page.locator('.copy:not(.dim)').count(),1);
  await page.locator('[data-copies="256"]').click();
  const localUrls = await page.evaluate(()=>[...new Set([...document.querySelectorAll('a[href]')].map(a=>a.href).filter(h=>h.startsWith(location.origin)&&!h.includes('#')))]);
  report.localLinks = await Promise.all(localUrls.map(async url=>({url,status:(await page.request.head(url)).status()})));
  assert.ok(report.localLinks.every(x=>x.status===200),'All repository evidence links must resolve');
  report.layouts=[];
  for(const width of [1440,1024,768,390,320]){
    await page.setViewportSize({width,height:1000});
    const layout=await page.evaluate(()=>({viewport:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth}));
    report.layouts.push(layout);assert.ok(layout.scroll<=width,`Horizontal overflow at ${width}: ${layout.scroll}`);
  }
  await page.setViewportSize({width:1440,height:1000});await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:resolve(output,'desktop-hero.png')});
  const screenshotStyle='.topbar{visibility:hidden}';
  await page.locator('#circuit-demo').screenshot({path:resolve(output,'live-circuit.png'),style:screenshotStyle});
  await page.locator('#gpt2 .figure').screenshot({path:resolve(output,'real-neuron.png'),style:screenshotStyle});
  await page.locator('#tables .figure').screenshot({path:resolve(output,'lookup-count.png'),style:screenshotStyle});
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:resolve(output,'mobile-hero.png')});
  await page.locator('#circuit-demo').screenshot({path:resolve(output,'mobile-circuit.png'),style:screenshotStyle});
  await page.locator('#gpt2 .figure').screenshot({path:resolve(output,'mobile-neuron.png'),style:screenshotStyle});
  const offline = await browser.newPage();
  await offline.context().setOffline(true);
  await offline.goto(new URL('../experiments/gsub-width-explainer/index.html',import.meta.url).href);
  await offline.waitForFunction(()=>document.querySelector('#live-source').dataset.verified==='true');
  report.standaloneOffline=await offline.locator('#native-status').textContent();
  await offline.close();
  assert.equal(errors.length,0);assert.equal(failedRequests.length,0);
  report.passed=true;
} catch(error){report.passed=false;report.failure=String(error);await page.screenshot({path:resolve(output,'failure.png'),fullPage:false});process.exitCode=1;}
finally {await writeFile(resolve(output,'results.json'),JSON.stringify(report,null,2)+'\n');await browser.close();console.log(JSON.stringify(report,null,2));}
