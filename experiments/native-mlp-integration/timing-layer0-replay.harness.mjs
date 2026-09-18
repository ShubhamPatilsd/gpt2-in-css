/** Matched live producer -> MLP -> consumer replay. Author JavaScript disabled.
 * The harness selects raw input fixtures and generation only. It never feeds
 * products, intermediate vectors, or answers back into the browser graph.
 */
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
const execFileAsync = promisify(execFile);
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ?? '/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const { chromium } = require(`${modules}/playwright`);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
function option(name, fallback) { const at = process.argv.indexOf(`--${name}`); return at < 0 ? fallback : process.argv[at + 1]; }
const directory = path.resolve(root, option('directory', 'experiments/native-mlp-integration'));
const output = path.resolve(root, option('output', path.join(directory, 'benchmark.json')));
const mode = option('mode', 'gate');
const repeats = Number(option('repeats', '2'));
const schedule = option('schedule', 'replay');
if (!['replay', 'first-visit'].includes(schedule)) throw new Error(`Unknown schedule ${schedule}`);
const warmups = Number(option('warmups', '2'));
const measured = Number(option('measured', schedule === 'first-visit' ? '3' : '8'));
if (schedule === 'first-visit' && (warmups !== 2 || measured !== 3)) throw new Error('First-visit schedule requires two case0 warmups and three distinct measured states');
const updateTimeout = Number(option('update-timeout-ms', '45000'));
const requestedVariants = option('variants', '').split(',').filter(Boolean);
const gatePath = option('gate', null);
const manifestPath = path.join(directory, 'manifest.json');
const manifest = JSON.parse(await fs.readFile(manifestPath, 'utf8'));
const sha256 = buffer => crypto.createHash('sha256').update(buffer).digest('hex');
const manifestHash = sha256(await fs.readFile(manifestPath));
const sourceHash = sha256(await fs.readFile(fileURLToPath(import.meta.url)));
// Normalize the builder's documented interface without changing fixture data.
manifest.readouts = {
  state: { selector: manifest.readout.stateSelector, offset: manifest.readout.stateOffset, scale: manifest.readout.stateScale },
  nextLayerNorm: { selector: manifest.readout.nextLnSelector, offset: manifest.readout.nextLnOffset, scale: manifest.readout.nextLnScale },
};
manifest.terminalHeightScale = manifest.readout.terminalEpochScale;
for (const variant of manifest.variants) {
  const declared = manifest.tolerances[variant.backend];
  variant.tolerances = { state: { maximum: declared.stateMaxAbs ?? null, rmse: declared.stateRmse ?? declared.stateMaxAbs }, nextLayerNorm: { maximum: declared.nextLnMaxAbs, rmse: declared.nextLnRmse ?? declared.nextLnMaxAbs } };
}
const variants = manifest.variants.filter(v => !requestedVariants.length || requestedVariants.includes(v.id));
for (const [relative, asset] of Object.entries(manifest.assets)) {
  if (sha256(await fs.readFile(path.resolve(root, relative))) !== asset.sha256) throw new Error(`Asset changed since compilation: ${relative}`);
}
for (const variant of variants) {
  if (sha256(await fs.readFile(path.resolve(root, variant.page))) !== variant.htmlSha256) throw new Error(`HTML changed since compilation: ${variant.id}`);
}
if (!variants.length) throw new Error('No variants selected');
if (!['smoke', 'gate', 'timing'].includes(mode)) throw new Error(`Unknown mode ${mode}`);
try { await fs.access(output); throw new Error(`Refusing to overwrite ${output}`); } catch (error) { if (error.code !== 'ENOENT') throw error; }
if (mode === 'timing') {
  if (!gatePath) throw new Error('Timing requires --gate path to a passing manifest-matched correctness report');
  const gate = JSON.parse(await fs.readFile(path.resolve(root, gatePath), 'utf8'));
  if (!gate.passed || gate.mode !== 'gate' || gate.manifestSha256 !== manifestHash || gate.harnessSha256 !== sourceHash) throw new Error('Correctness gate is incomplete, failed, or belongs to another fixture');
  for (const variant of variants) {
    if (!gate.runs.some(r => r.variant === variant.id && r.passed)) throw new Error(`No passing gate for ${variant.id}`);
  }
}
const assets = new Map();
const server = http.createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
    const location = path.resolve(root, `.${pathname}`);
    if (!location.startsWith(`${root}/`)) { response.writeHead(403).end(); return; }
    const bytes = await fs.readFile(location);
    assets.set(path.relative(root, location), { sha256: sha256(bytes), bytes: bytes.length });
    const types = { '.html': 'text/html', '.css': 'text/css', '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.json': 'application/json', '.svg': 'image/svg+xml' };
    response.writeHead(200, { 'Content-Type': types[path.extname(location)] ?? 'application/octet-stream', 'Cache-Control': 'no-store' });
    response.end(bytes);
  } catch { response.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const report = {
  schemaVersion: 1, mode, passed: false, startedAt: new Date().toISOString(),
  scope: manifest.scope ?? 'Changed raw residual -> live LayerNorm -> native MLP -> residual/bias -> next-layer LayerNorm; segment replay, not token generation.',
  manifestSha256: manifestHash, harnessSha256: sourceHash,
  protocol: {
    authorJavaScriptEnabled: false, harnessJavaScript: true,
    mutations: 'Select a predeclared raw input fixture and advance generation. No calculated answer injection.',
    timing: 'Browser performance.now elapsed from mutation to generation-tagged final dependent geometry;16ms Node polling and DevTools round-trip gaps are included between reads. All-coordinate numerical serialization follows the timer, and terminal geometry must remain unchanged by verification.',
    correctness: 'Every warmup and measured generation is checked after its completion, not just the timed final scalar.',
    load: 'Navigation + explicit loading of every declared FontFace + document.fonts.ready recorded separately; native gated projection fonts otherwise load late. No other benchmark pages resident.',
    freshProcessPerVariantRun: true, order: 'AB then BA for two variants; alternating reversal otherwise',
    warmups, measured, repeats, updateTimeout, schedule,
    inputReuse: schedule === 'first-visit' ? 'Initial state0 warmed twice; measured states1,2,3 each visited only once per fresh process; reversed3,2,1 in second repetition. Font loading and state0 initialization remain outside timing.' : 'Four real states revisited; font shaping/variation caches are not disabled. Not a stream of unseen token inputs.',
    memory: 'After verification, sum RSS of renderer processes reported by this browser SystemInfo.getProcessInfo; sampled aggregate, not a continuous peak.',
    quantiles: 'Upper-middle median, nearest-rank p90; process medians and paired differences retained. Two pairs are not a precision confidence interval.',
    caveats: ['External16ms polling and DevTools round trips can perturb scheduling and add observation delay; same observer in both variants. Synchronous candidate may complete on its first read.', 'No full-model token runtime may be inferred by multiplying this segment latency.'],
  },
  runs: [], assets: {},
};
await fs.mkdir(path.dirname(output), { recursive: true });
await fs.copyFile(manifestPath, output.replace(/\.json$/, '.manifest.json'));
await fs.copyFile(fileURLToPath(import.meta.url), output.replace(/\.json$/, '.harness.mjs'));
async function persist() {
  report.assets = Object.fromEntries([...assets.entries()].sort());
  await fs.mkdir(path.dirname(output), { recursive: true });
  await fs.writeFile(output, `${JSON.stringify(report, null, 2)}\n`);
}
async function bounded(promise, milliseconds, label) {
  let timer;
  try { return await Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(`${label} exceeded ${milliseconds}ms`)), milliseconds); })]); } finally { clearTimeout(timer); }
}
function median(numbers) { const sorted = [...numbers].sort((a, b) => a - b); return sorted[Math.floor(sorted.length / 2)]; }
function summarize(numbers) { const sorted = [...numbers].sort((a, b) => a - b); return { count: numbers.length, median: median(numbers), minimum: sorted[0], maximum: sorted.at(-1), p90: sorted[Math.ceil(sorted.length * .9) - 1], mean: numbers.reduce((a, b) => a + b, 0) / numbers.length }; }
function expectedFor(variant, caseIndex) {
  const layer = manifest.layers.find(item => item.layer === variant.layer);
  const expected = layer[variant.referenceKey];
  return { state: expected.states[caseIndex], nextLayerNorm: expected.nextLn[caseIndex] };
}
function numerical(actual, expected, tolerance) {
  if (!Array.isArray(expected) || !Array.isArray(actual) || expected.length !== actual.length || !expected.length) return { passed: false, reason: 'Missing or unequal vector lengths', actualLength: actual?.length, expectedLength: expected?.length };
  const errors = actual.map((value, index) => value - expected[index]);
  const finite = actual.every(Number.isFinite) && expected.every(Number.isFinite);
  const max = Math.max(...errors.map(Math.abs));
  const rmse = Math.sqrt(errors.reduce((sum, x) => sum + x * x, 0) / errors.length);
  return { passed: finite && (tolerance.maximum === null || max <= tolerance.maximum) && rmse < tolerance.rmse, finite, count: actual.length, maximumAbsoluteError: max, rmse, tolerance };
}
async function memorySnapshot(client) {
  const { processInfo } = await client.send('SystemInfo.getProcessInfo');
  const ids = processInfo.map(p => p.id);
  const { stdout } = await execFileAsync('ps', ['-o', 'pid=,rss=', '-p', ids.join(',')]);
  const rss = new Map(stdout.trim().split('\n').filter(Boolean).map(line => line.trim().split(/\s+/).map(Number)));
  const renderers = processInfo.filter(p => p.type === 'renderer');
  return { rendererRssMiB: renderers.reduce((sum, p) => sum + (rss.get(p.id) ?? 0), 0) / 1024, browserProcessRssMiB: [...rss.values()].reduce((sum, n) => sum + n, 0) / 1024, rendererProcesses: renderers.length };
}
async function execute(variant, repeat, caseIndices, timing) {
  const run = { variant: variant.id, layer: variant.layer, repeat, passed: false, samples: [] };
  report.runs.push(run); await persist();
  let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, args: manifest.browserArguments ?? [] });
    run.chrome = await browser.version();
    const browserCDP = await browser.newBrowserCDPSession();
    const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 1100, height: 800 } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    const urlPath = variant.page.startsWith('experiments/') ? variant.page : path.relative(root, path.join(directory, variant.page));
    const loadStarted = performance.now();
    await page.goto(`${origin}/${urlPath}`, { waitUntil: 'load', timeout: 120000 });
    await bounded(page.evaluate(async () => { await Promise.all([...document.fonts].map(font => font.load())); await document.fonts.ready; }), 60000, 'Font preload');
    run.loadMilliseconds = performance.now() - loadStarted;
    run.pageAudit = await bounded(page.evaluate(() => {
      const trees = [document];
      for (let i = 0; i < trees.length; i++) for (const node of trees[i].querySelectorAll('*')) if (node.shadowRoot) trees.push(node.shadowRoot);
      return { authorScriptElements: trees.reduce((n, tree) => n + tree.querySelectorAll('script').length, 0), elements: trees.reduce((n, tree) => n + tree.querySelectorAll('*').length, 0), fonts: [...document.fonts].map(f => ({ family: f.family, status: f.status })), csp: document.querySelector('meta[http-equiv="Content-Security-Policy"]')?.content ?? null };
    }), updateTimeout, 'Page audit');
    run.initializationMemory = await memorySnapshot(browserCDP);
    await persist();
    if (run.pageAudit.authorScriptElements !== 0) throw new Error('Author scripts present');
    if (run.pageAudit.fonts.some(f => f.status === 'error')) throw new Error('Font failed to load');
    let epoch = Number(manifest.initialEpoch ?? 1);
    for (let index = 0; index < caseIndices.length; index++) {
      const caseIndex = caseIndices[index];
      epoch += 1;
      const externalStarted = performance.now();
      const observe = ({ caseIndex, epoch, terminal, mutate }) => {
        if (mutate) {
          const control = document.querySelector(`#case-${caseIndex}`);
          if (!control) throw new Error(`Missing raw input fixture ${caseIndex}`);
          const trees = [document];
          let element;
          for (let i = 0; i < trees.length && !element; i++) {
            element = trees[i].querySelector(terminal);
            if (!element) for (const child of trees[i].querySelectorAll('*')) if (child.shadowRoot) trees.push(child.shadowRoot);
          }
          if (!element) throw new Error(`Missing terminal ${terminal}`);
          window.__nativeMLPObserver = { element, started: performance.now(), polls: 0, geometryReadMilliseconds: 0 };
          control.checked = true;
          document.body.style.setProperty('--epoch', String(epoch));
        }
        const observer = window.__nativeMLPObserver;
        const readStarted = performance.now();
        const bounds = observer.element.getBoundingClientRect();
        observer.geometryReadMilliseconds += performance.now() - readStarted;
        observer.polls += 1;
        return { milliseconds: performance.now() - observer.started, width: bounds.width, height: bounds.height, polls: observer.polls, geometryReadMilliseconds: observer.geometryReadMilliseconds };
      };
      let observation = await bounded(page.evaluate(observe, { caseIndex, epoch, terminal: variant.terminal ?? '#terminal', mutate: true }), updateTimeout, 'Initial dependent read');
      while (Math.abs(observation.height - epoch * manifest.terminalHeightScale) > .02 || observation.width <= 0) {
        if (performance.now() - externalStarted > updateTimeout) throw new Error(`Generation ${epoch} timeout: ${JSON.stringify(observation)}`);
        await new Promise(resolve => setTimeout(resolve, 16));
        observation = await bounded(page.evaluate(observe, { mutate: false }), updateTimeout, 'Generation read');
      }
      const externalMilliseconds = performance.now() - externalStarted;
      const readouts = manifest.readouts ?? {
        state: { selector: '.state-value', offset: 4096, scale: 32 },
        nextLayerNorm: { selector: '.next-ln-value', offset: 4096, scale: 256 },
      };
      const verificationStarted = performance.now();
      const actual = await bounded(page.evaluate((readouts) => {
        const trees = [document];
        for (let i = 0; i < trees.length; i++) for (const node of trees[i].querySelectorAll('*')) if (node.shadowRoot) trees.push(node.shadowRoot);
        return Object.fromEntries(Object.entries(readouts).map(([key, readout]) => [key, trees.flatMap(tree => [...tree.querySelectorAll(readout.selector)]).map(node => (node.getBoundingClientRect().width - readout.offset) / readout.scale)]));
      }, readouts), updateTimeout, 'All-coordinate verification');
      const expected = expectedFor(variant, caseIndex);
      if (!expected) throw new Error(`Missing oracle for${variant.id} case${caseIndex}`);
      const terminalAfterVerification = await bounded(page.locator(variant.terminal ?? '#terminal').evaluate(element => { const bounds = element.getBoundingClientRect(); return { width: bounds.width, height: bounds.height }; }), updateTimeout, 'Final endpoint audit');
      const endpointUnchanged = Math.abs(terminalAfterVerification.width - observation.width) <= .001 && Math.abs(terminalAfterVerification.height - observation.height) <= .001;
      const checks = Object.fromEntries(Object.keys(readouts).map(key => [key, numerical(actual[key], expected[key], (variant.tolerances ?? manifest.tolerances)[key])]));
      const common = manifest.layers.find(item => item.layer === variant.layer).commonExactGeluFloatProjection;
      const commonTargetErrors = { state: numerical(actual.state, common.states[caseIndex], { maximum: Infinity, rmse: Infinity }), nextLayerNorm: numerical(actual.nextLayerNorm, common.nextLn[caseIndex], { maximum: Infinity, rmse: Infinity }) };
      for (const value of Object.values(commonTargetErrors)) { delete value.passed; delete value.tolerance; }
      const sample = { terminalAfterVerification, endpointUnchanged, commonTargetErrors, index, caseIndex, epoch, phase: timing && index < warmups ? 'warmup' : timing ? 'measured' : 'correctness', ...observation, externalMilliseconds, verificationMilliseconds: performance.now() - verificationStarted, checks, passed: endpointUnchanged && Object.values(checks).every(x => x.passed) };
      // Persist all values for gates; timing retains scalar checks plus repeatable source fixture/oracles.
      if (!timing || !sample.passed) sample.actual = actual;
      sample.memory = await memorySnapshot(browserCDP);
      run.samples.push(sample);
      await persist();
      if (!sample.passed) throw new Error(`Numerical failure${variant.id} case${caseIndex}: ${JSON.stringify(checks)}`);
      console.log(JSON.stringify({ variant: variant.id, repeat, index, caseIndex, epoch, milliseconds: observation.milliseconds, passed: sample.passed }));
    }
    run.errors = errors;
    if (errors.length) throw new Error(errors.join('\n'));
    if (timing) run.timing = summarize(run.samples.filter(s => s.phase === 'measured').map(s => s.milliseconds));
    run.sampledPeakRendererRssMiB = Math.max(run.initializationMemory.rendererRssMiB, ...run.samples.map(sample => sample.memory.rendererRssMiB));
    run.passed = true;
    await context.close();
  } catch (error) {
    run.error = String(error?.stack ?? error); await persist(); throw error;
  } finally { if (browser) await browser.close(); }
  await persist();
}
try {
  if (mode !== 'timing') {
    for (const variant of variants) {
      const caseIndices = mode === 'smoke' ? [0] : [...manifest.cases.map((_, index) => index), 0, 2, 1, 0];
      await execute(variant, 0, caseIndices, false);
    }
  } else {
    for (let repeat = 0; repeat < repeats; repeat++) {
      const ordered = repeat % 2 ? [...variants].reverse() : variants;
      const caseIndices = schedule === 'first-visit' ? [0, 0, ...(repeat % 2 ? [3, 2, 1] : [1, 2, 3])] : Array.from({ length: warmups + measured }, (_, i) => (i + repeat) % manifest.cases.length);
      for (const variant of ordered) await execute(variant, repeat, caseIndices, true);
    }
    const summaries = variants.map(v => {
      const runs = report.runs.filter(r => r.variant === v.id);
      return { variant: v.id, backend: v.backend, layer: v.layer, processMediansMilliseconds: runs.map(r => r.timing.median), medianOfProcessMediansMilliseconds: median(runs.map(r => r.timing.median)), loadMilliseconds: runs.map(r => r.loadMilliseconds), sampledPeakRendererRssMiB: runs.map(r => r.sampledPeakRendererRssMiB), ownOracleStateMaxAbs: Math.max(...runs.flatMap(r => r.samples.map(s => s.checks.state.maximumAbsoluteError))), ownOracleStateMaxRmse: Math.max(...runs.flatMap(r => r.samples.map(s => s.checks.state.rmse))), commonTargetStateMaxRmse: Math.max(...runs.flatMap(r => r.samples.map(s => s.commonTargetErrors.state.rmse))), nextLayerNormMaxAbs: Math.max(...runs.flatMap(r => r.samples.map(s => s.checks.nextLayerNorm.maximumAbsoluteError))) };
    });
    report.summary = { variants: summaries, pairedLayerComparisons: [...new Set(variants.map(v => v.layer))].flatMap(layer => Array.from({ length: repeats }, (_, repeat) => {
      const baseline = report.runs.find(r => r.layer === layer && r.repeat === repeat && variants.find(v => v.id === r.variant).backend === 'baseline');
      const candidate = report.runs.find(r => r.layer === layer && r.repeat === repeat && variants.find(v => v.id === r.variant).backend === 'candidate');
      if (!baseline || !candidate) return { layer, repeat, paired: false };
      return { layer, repeat, paired: true, order: report.runs.filter(r => r.layer === layer && r.repeat === repeat).map(r => r.variant), baselineMedianMilliseconds: baseline.timing.median, candidateMedianMilliseconds: candidate.timing.median, candidateChangePercent: 100 * (candidate.timing.median / baseline.timing.median - 1), baselineSampledPeakRendererRssMiB: baseline.sampledPeakRendererRssMiB, candidateSampledPeakRendererRssMiB: candidate.sampledPeakRendererRssMiB };
    })), pairs: Array.from({ length: repeats }, (_, repeat) => {
      const runs = report.runs.filter(r => r.repeat === repeat);
      return { repeat, order: runs.map(r => r.variant), mediansMilliseconds: Object.fromEntries(runs.map(r => [r.variant, r.timing.median])) };
    }) };
  }
  report.passed = report.runs.length > 0 && report.runs.every(r => r.passed);
} catch (error) { report.error = String(error?.stack ?? error); process.exitCode = 1; }
finally { report.finishedAt = new Date().toISOString(); await persist(); await new Promise(resolve => server.close(resolve)); }
console.log(JSON.stringify({ output, passed: report.passed, summary: report.summary, error: report.error }, null, 2));
