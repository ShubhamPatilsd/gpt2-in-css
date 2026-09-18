#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
const require = createRequire(import.meta.url);
const {chromium} = require(`${process.env.CODEX_NODE_MODULES ?? '/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'}/playwright`);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'experiments/aat-support-probe');
const reference = JSON.parse(await fs.readFile(path.join(out, 'reference.json'), 'utf8'));
const browser = await chromium.launch({executablePath: process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true});
const report = {browser: browser.version(), harnessSha256: createHash('sha256').update(await fs.readFile(fileURLToPath(import.meta.url))).digest('hex'),
  referenceSha256: createHash('sha256').update(await fs.readFile(path.join(out, 'reference.json'))).digest('hex'),
  purpose: 'Downloaded-font substitution support gate; no timing, no arithmetic.', records: [], errors: []};
try {
  const page = await browser.newPage();
  page.on('console', msg => {if (msg.type() === 'error') report.errors.push(msg.text());});
  for (const record of reference.records) for (const ext of ['ttf', 'woff2']) {
    const data = await fs.readFile(path.join(out, `${record.kind}.${ext}`));
    const hash = createHash('sha256').update(data).digest('hex');
    if (hash !== record.files[`${record.kind}.${ext}`].sha256) throw Error('Font hash mismatch');
    await page.setContent(`<!doctype html><meta http-equiv="Content-Security-Policy" content="script-src 'none'"><style>@font-face{font-family:Probe;src:url(data:font/${ext};base64,${data.toString('base64')})}span{display:inline-block;font:1024px/1 Probe;font-feature-settings:"liga" 1}</style><span id="input">&#xE000;</span><span id="sentinel">&#xE001;</span>`);
    const observed = await page.evaluate(async () => {let loadError = null; try {await document.fonts.load('1024px Probe', '\ue000\ue001'); await document.fonts.ready;} catch (error) {loadError = String(error);} return {
      fontLoaded: document.fonts.check('1024px Probe', '\ue000\ue001'), inputWidth: document.querySelector('#input').getBoundingClientRect().width,
      sentinelWidth: document.querySelector('#sentinel').getBoundingClientRect().width, scripts: document.scripts.length, loadError};});
    report.records.push({kind: record.kind, format: ext, fontSha256: hash, ...observed});
  }
} finally { await browser.close(); }
report.controlsPass = report.records.every(r => r.fontLoaded && r.sentinelWidth === 700 && r.scripts === 0 &&
  (r.kind !== 'plain' || r.inputWidth === 100) && (r.kind !== 'gsub' || r.inputWidth === 700));
report.aatSupportedInThisProbe = report.records.filter(r => r.kind === 'morx').every(r => r.inputWidth === 700);
await fs.writeFile(path.join(out, 'browser-results.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
if (!report.controlsPass) process.exitCode = 1;
