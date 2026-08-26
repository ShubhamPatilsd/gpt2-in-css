#!/usr/bin/env node
/** External experiment driver; served browser pages have script-src 'none'. */
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import os from 'node:os';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const out=path.join(root,'experiments/gsub-reader-isolation');
const old=path.join(root,'experiments/gsub-weighted-sum-probe');
const require=createRequire(import.meta.url);
const {chromium}=require(`${process.env.CODEX_NODE_MODULES ?? '/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'}/playwright`);
const args=process.argv.slice(2);
const arg=(n,d)=>args.includes(n)?args[args.indexOf(n)+1]:d;
const smoke=args.includes('--smoke');
const reps=Number(arg('--repetitions',smoke?'1':'3'));
const rounds=Number(arg('--rounds',smoke?'7':'25'));
const warmup=5, batch=Number(arg('--batch',smoke?'32':'256'));
const widths=arg('--widths',smoke?'4':'4,16,64').split(',').map(Number);
const destination=path.join(out,arg('--output',smoke?'smoke.json':'results.json'));
const hash=x=>createHash('sha256').update(x).digest('hex');
const reference=JSON.parse(await fs.readFile(path.join(old,'reference.json'),'utf8'));
const hv=JSON.parse(await fs.readFile(path.join(old,'hvar-control/reference.json'),'utf8'));
const control=JSON.parse(await fs.readFile(path.join(out,'reference.json'),'utf8'));
const report={startedAt:new Date().toISOString(),smoke,repetitions:reps,rounds,warmup,batch,widths,
  harnessSha256:hash(await fs.readFile(fileURLToPath(import.meta.url))),
  environment:{cpu:os.cpus()[0]?.model,node:process.version,platform:os.platform(),arch:os.arch()},
  methodology:{formula:'F=2*sum(w*x)+1, repeated weights [3,-2,5,1], x integers[-8,7]',
    endpoints:'source: force source width; full: anchor-size -> container units -> decoded CSS number -> offset+3*F dependent width; direct: direct CSS arithmetic to same dependent width',
    conditions:'Each source/full pair lives in separate browser contexts/pages, with matched input/nonce writes and one forced geometry read per output.',
    diagnostics:'precomputed-font and precomputed-css receive externally prepared answers AND all raw input writes. They cannot be claimed as native arithmetic. Compare their own source/full pair; subtraction from GSUB is not an exact cost decomposition.',
    timing:'Input writes through forced geometry reads; stimuli, oracle, font loading, correctness comparisons and browser protocol excluded. Mutation/read loops included.',
    replication:'Exhaustive/full correctness uses a separate browser before timing. Each timed repetition starts a fresh browser and the same small precheck. Different deterministic seed per repetition and width, shared across conditions. Width order rotates and backend blocks rotate by two positions; source/full order alternates each round. Five warmups excluded.',
    profiles:'Separate pass with independently seeded inputs, five warmups then ten measured rounds; metrics broad browser categories, not pure font CPU. Each profiled output checked.',
    inference:'Matched source/full difference is the effect of adding reader DOM and dependencies under these fixtures, not an isolated CSS instruction.'},
  fonts:{},correctness:[],timings:[],profiles:[],errors:[]};
await fs.mkdir(out,{recursive:true});
const save=()=>fs.writeFile(destination,JSON.stringify(report,null,2)+'\n');
const rng=seed=>{let s=seed>>>0;return()=>{s^=s<<13;s^=s>>>17;s^=s<<5;return s>>>0;};};
const expected=(x,w)=>2*x.reduce((s,v,i)=>s+v*w[i],0)+1;
const stats=xs=>{const s=[...xs].sort((a,b)=>a-b);return{median:s[Math.floor(s.length/2)],min:s[0],max:s.at(-1),p95:s[Math.floor((s.length-1)*.95)]};};
const escapeCp=cp=>`"\\${cp.toString(16)}"`;
const styleCounter=(name,start,count)=>`@counter-style ${name}{system:fixed 0;symbols:${Array.from({length:count},(_,i)=>escapeCp(start+i)).join(' ')};suffix:""}`;
const documents=new Map();
const server=http.createServer(async(req,res)=>{
  const pathname=new URL(req.url,'http://localhost').pathname;
  if(documents.has(pathname)){res.writeHead(200,{'Content-Type':'text/html','Content-Security-Policy':"script-src 'none';object-src 'none'"}).end(documents.get(pathname));return;}
  if(pathname==='/favicon.ico'){res.writeHead(204).end();return;}
  const font=report.fonts[pathname];
  if(font){res.writeHead(200,{'Content-Type':'font/woff2'}).end(await fs.readFile(font.path));return;}
  res.writeHead(404).end();
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin=`http://127.0.0.1:${server.address().port}`;
const kinds=['sequential','tree','hvar','precomputed-font','precomputed-css','direct-css'];
function caseSet(n,weights,exhaustive){
  if(n===4&&exhaustive) return Array.from({length:65536},(_,code)=>[0,4,8,12].map(shift=>((code>>>shift)&15)-8));
  const cases=[...[-8,-7,-1,0,1,6,7].map(v=>Array(n).fill(v)),weights.map(w=>w>0?-8:7),weights.map(w=>w>0?7:-8),Array.from({length:n},(_,i)=>i%2?7:-8),Array.from({length:n},(_,i)=>[2,3,0,0][i%4])];
  for(let i=0;i<n;i++)for(let v=-8;v<=7;v++){const x=Array(n).fill(0);x[i]=v;cases.push(x);}
  const random=rng(0x84a137^n);for(let i=0;i<(smoke?32:2048);i++)cases.push(Array.from({length:n},()=>random()%16-8));
  return cases;
}
async function makeFixture(browser,n,kind,endpoint,tag){
  const weights=Array.from({length:n},(_,i)=>[3,-2,5,1][i%4]);
  const isGsub=['sequential','tree'].includes(kind), isFont=isGsub||['hvar','precomputed-font'].includes(kind);
  const v=isGsub?reference.variants.find(v=>v.id===`w${n}-${kind}`):kind==='hvar'?hv.variants.find(v=>v.width===n):null;
  const offset=v?.output.offset??8192;
  const consumerOffset=3*(2*8*weights.reduce((s,w)=>s+Math.abs(w),0)+1)+64;
  const props=weights.map((_,i)=>`@property --x-${i}{syntax:"<integer>";inherits:true;initial-value:0}`).join('\n');
  let css=`${props}
@property --nonce{syntax:"<integer>";inherits:true;initial-value:0}
@property --provided{syntax:"<integer>";inherits:true;initial-value:1}
@property --sum{syntax:"<number>";inherits:false;initial-value:-99999}
@property --y{syntax:"<number>";inherits:false;initial-value:-99999}
body{margin:0}.group{position:relative;contain:layout}.item{display:inline-block;position:relative;width:1px;height:1px;vertical-align:top}.source{display:inline-block;white-space:pre;font-kerning:none;line-height:1;height:1px}.receiver{position:absolute;left:0;top:0;container-type:inline-size}.decoded{position:absolute;left:0;top:0;--y:calc(100cqw / 1px - ${offset});width:calc((${consumerOffset} + 3*var(--y))*1px);height:1px}
`;
  let family,loadCharacter;
  if(isFont){
    family=v?.fontFamily??control.family;
    const filename=v?path.join(old,v.fontFile):path.join(out,control.fontFile);
    const url=`/font-${n}-${kind}.woff2`;
    report.fonts[url]={path:filename,sha256:hash(await fs.readFile(filename))};
    css+=`@font-face{font-family:"${family}";src:url("${url}")}.source{font-family:"${family}";font-size:1024px}`;
    const nonceCp=v?.nonceCodepoint??control.nonceCodepoint;
    css+=styleCounter('nc',nonceCp,65);
    if(isGsub){
      css+=`.source{font-feature-settings:${v.features.map(f=>`"${f}" 1`).join(',')}}`;
      css+=weights.map((_,i)=>styleCounter(`x${i}`,v.inputCodepoints[i],16)).join('\n');
      css+=`.source::before{counter-reset:nonce var(--nonce) ${weights.map((_,i)=>`x${i} calc(var(--x-${i}) + 8)`).join(' ')};content:counter(nonce,nc) ${weights.map((_,i)=>`counter(x${i},x${i})`).join(' ')}}`;
      loadCharacter=String.fromCodePoint(v.inputCodepoints[0]);
    }else if(kind==='hvar'){
      css+=`.source{font-variation-settings:${v.axes.map((axis,i)=>`"${axis}" var(--x-${i})`).join(',')}}.source::before{counter-reset:nonce var(--nonce);content:counter(nonce,nc) ${escapeCp(v.codepoint)}}`;
      loadCharacter=String.fromCodePoint(v.codepoint);
    }else{
      css+=styleCounter('answer',control.codepoint,(control.maximumAnswer-control.minimumAnswer)/2+1);
      css+=`.source::before{counter-reset:nonce var(--nonce) answer calc((var(--provided) - ${control.minimumAnswer})/2);content:counter(nonce,nc) counter(answer,answer)}`;
      loadCharacter=String.fromCodePoint(control.codepoint);
    }
  }else if(kind==='precomputed-css'){
    css+=`.source{width:calc((${offset} + var(--provided))*1px)}`;
  }else{
    const sum=weights.map((w,i)=>`(${w}*var(--x-${i}))`).join(' + ');
    css+=`.source{--sum:calc(${sum});--y:calc(2*var(--sum) + 1);width:calc((${consumerOffset} + 3*var(--y))*1px)}`;
  }
  const url=`/case-${tag}.html`;
  const elements=Array.from({length:batch},(_,i)=>`<div class="item"><span class="source"${endpoint==='full'?` style="anchor-name:--a${i}"`:''}></span>${endpoint==='full'?`<div class="receiver" style="width:anchor-size(--a${i} inline)"><div class="decoded"></div></div>`:''}</div>`).join('');
  documents.set(url,`<!doctype html><meta charset="utf-8"><title>Reader isolation diagnostic</title><style>${css}</style><main class="group">${elements}</main>`);
  const context=await browser.newContext({viewport:{width:1000,height:600}});
  const page=await context.newPage();
  page.on('pageerror',e=>report.errors.push(`${tag}: ${e}`));
  page.on('console',m=>{if(m.type()==='error')report.errors.push(`${tag}: ${m.text()}`)});
  await page.goto(origin+url);
  if(isFont)await page.evaluate(async({family,loadCharacter})=>{await document.fonts.load(`1024px "${family}"`,loadCharacter);await document.fonts.ready;},{family,loadCharacter});
  if(await page.evaluate(()=>document.scripts.length)!==0)throw new Error('Page script found');
  return{page,context,n,kind,endpoint,weights,offset,consumerOffset,provided:kind.startsWith('precomputed-'),id:tag};
}
async function update(f,rows,observeAll=false){
  return f.page.evaluate(({rows,endpoint,provided,observeAll})=>{
    const sources=[...document.querySelectorAll('.source')];
    const targets=endpoint==='full'?[...document.querySelectorAll('.decoded')]:sources;
    const start=performance.now();
    for(let j=0;j<rows.length;j++){
      const {input,nonce,y}=rows[j];
      for(let i=0;i<input.length;i++)sources[j].style.setProperty(`--x-${i}`,input[i]);
      sources[j].style.setProperty('--nonce',nonce);
      if(provided)sources[j].style.setProperty('--provided',y);
    }
    const values=rows.map((_,i)=>targets[i].getBoundingClientRect().width);
    const elapsed=performance.now()-start;
    const details=observeAll?rows.map((_,i)=>({source:sources[i].getBoundingClientRect().width,y:Number(getComputedStyle(targets[i]).getPropertyValue('--y'))})):null;
    return{elapsed,values,details};
  },{rows,endpoint:f.endpoint,provided:f.provided,observeAll});
}
function check(f,rows,actual,all=false){
  for(let i=0;i<rows.length;i++){
    const y=expected(rows[i].input,f.weights);
    const wanted=f.endpoint==='source'?f.offset+y:f.consumerOffset+3*y;
    if(actual.values[i]!==wanted)throw new Error(JSON.stringify({fixture:f.id,input:rows[i].input,y,wanted,actual:actual.values[i]}));
    if(all&&f.endpoint==='full'&&(actual.details[i].source!==f.offset+y||actual.details[i].y!==y))throw new Error(`Reader decode mismatch ${f.id}`);
  }
}
let browser;
try{
  // rep=-1 is a wholly separate correctness browser: exhaustive validation
  // must not warm the first timed repetition differently from later ones.
  for(let rep=-1;rep<reps;rep++){
    browser=await chromium.launch({executablePath:process.env.CHROME_PATH??'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
    report.browserVersion=await browser.version();
    const widthStart=Math.max(rep,0)%widths.length;
    const orderedWidths=[...widths.slice(widthStart),...widths.slice(0,widthStart)];
    for(const n of orderedWidths){
      const weights=Array.from({length:n},(_,i)=>[3,-2,5,1][i%4]);
      const seed=(0x193c783^n^(rep*0x9e3779b9))>>>0;
      const random=rng(seed);
      const stimuli=Array.from({length:rounds},(_,round)=>Array.from({length:batch},()=>{const input=Array.from({length:n},()=>random()%16-8);return{input,nonce:round+1,y:expected(input,weights)}}));
      const kindStart=(Math.max(rep,0)*2)%kinds.length;
      const ordered=[...kinds.slice(kindStart),...kinds.slice(0,kindStart)];
      for(const kind of ordered){
        const endpoints=kind==='direct-css'?['direct']:['source','full'];
        const fixtures=[];
        for(const endpoint of endpoints)fixtures.push(await makeFixture(browser,n,kind,endpoint,`${rep}-${n}-${kind}-${endpoint}`));
        // Correctness is outside all measured intervals. Retained fonts also have earlier exhaustive gates.
        const cases=rep<0?caseSet(n,weights,!smoke):caseSet(n,weights,false).slice(0,smoke?32:128);
        for(const f of fixtures){
          for(let start=0;start<cases.length;start+=batch){
            const rows=cases.slice(start,start+batch).map(input=>({input,nonce:0,y:expected(input,weights)}));
            check(f,rows,await update(f,rows,true),true);
          }
          report.correctness.push({rep,correctnessOnly:rep<0,width:n,kind,endpoint:f.endpoint,cases:cases.length,exhaustive:n===4&&rep<0&&!smoke,passed:true});
        }
        if(rep<0){
          for(const f of fixtures)await f.context.close();
          await save();console.log(JSON.stringify({mode:'correctness',n,kind,cases:cases.length,passed:true}));continue;
        }
        const samples=Object.fromEntries(endpoints.map(e=>[e,[]]));
        const orders=[];
        for(let r=0;r<rounds;r++){
          const order=(r+rep)%2?[...fixtures].reverse():fixtures;orders.push(order.map(f=>f.endpoint));
          for(const f of order){const actual=await update(f,stimuli[r]);check(f,stimuli[r],actual);samples[f.endpoint].push(actual.elapsed);}
        }
        for(const f of fixtures)report.timings.push({rep,width:n,kind,endpoint:f.endpoint,seed,batch,checkedOutputs:rounds*batch,rawMilliseconds:samples[f.endpoint],warmup,statistics:stats(samples[f.endpoint].slice(warmup)),orders,passed:true});
        if(!smoke&&rep===0&&n===64){
          const profileSeed=(seed^0x4e74dc13)>>>0;
          const profileRandom=rng(profileSeed);
          const profileStimuli=Array.from({length:15},(_,r)=>Array.from({length:batch},()=>{const input=Array.from({length:n},()=>profileRandom()%16-8);return{input,nonce:41+r,y:expected(input,weights)}}));
          for(const f of fixtures){
            for(const rows of profileStimuli.slice(0,5))check(f,rows,await update(f,rows));
            const cdp=await f.context.newCDPSession(f.page);await cdp.send('Performance.enable');
            const before=Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map(m=>[m.name,m.value]));
            let elapsed=0;const count=10;
            for(const rows of profileStimuli.slice(5)){const actual=await update(f,rows);check(f,rows,actual);elapsed+=actual.elapsed;}
            const after=Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map(m=>[m.name,m.value]));
            const metrics=Object.fromEntries(['RecalcStyleDuration','LayoutDuration','TaskDuration','RecalcStyleCount','LayoutCount'].map(k=>[k,after[k]-before[k]]));
            report.profiles.push({width:n,kind,endpoint:f.endpoint,batch,seed:profileSeed,warmup:5,rounds:count,elapsedMilliseconds:elapsed,metrics,passed:true});
            await cdp.detach();
          }
        }
        for(const f of fixtures)await f.context.close();
        await save();
        console.log(JSON.stringify({rep,n,kind,medians:Object.fromEntries(endpoints.map(e=>[e,stats(samples[e].slice(warmup)).median]))}));
      }
    }
    await browser.close();browser=null;
  }
  report.passed=report.errors.length===0;
}catch(e){report.errors.push(String(e.stack??e));report.passed=false;process.exitCode=1;}
finally{await browser?.close();server.close();report.completedAt=new Date().toISOString();await save();}
console.log(JSON.stringify({passed:report.passed,output:destination,errors:report.errors}));
