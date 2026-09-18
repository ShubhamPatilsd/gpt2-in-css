/** Matched live producer -> MLP -> consumer replay. Author JavaScript disabled.
 * The harness selects raw input fixtures and generation only. It never feeds
 * products, intermediate vectors, or answers back into the browser graph.
 */
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import crypto from 'node:crypto';
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
const warmups = Number(option('warmups', '2'));
const measured = Number(option('measured', '8'));
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
  variant.tolerances = { state: { maximum: declared.stateMaxAbs, rmse: declared.stateMaxAbs }, nextLayerNorm: { maximum: declared.nextLnMaxAbs, rmse: declared.nextLnMaxAbs } };
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
  if (!gate.passed || gate.mode !== 'gate' || gate.manifestSha256 !== manifestHash) throw new Error('Correctness gate is incomplete, failed, or belongs to another fixture');
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
    timing: 'In-browser mutation to first generation-tagged final dependent geometry read; asynchronous completion includes native frame waits. All-coordinate numerical serialization follows the timer.',
    correctness: 'Every warmup and measured generation is checked after its completion, not just the timed final scalar.',
    load: 'Navigation + document.fonts.ready recorded separately; no other benchmark pages resident.',
    freshProcessPerVariantRun: true, order: 'AB then BA for two variants; alternating reversal otherwise',
    warmups, measured, repeats, updateTimeout,
    quantiles: 'Upper-middle median, nearest-rank p90; process medians and paired differences retained. Two pairs are not a precision confidence interval.',
    caveats: ['External rAF completion observation can perturb scheduling; same observer in both variants.', 'No full-model token runtime may be inferred by multiplying this segment latency.'],
  },
  runs: [], assets: {},
};
async function persist() {
  report.assets = Object.fromEntries([...assets.entries()].sort());
  await fs.mkdir(path.dirname(output), { recursive: true });
  await fs.writeFile(output, `${JSON.stringify(report, null, 2)}\n`);
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
  return { passed: finite && max <= tolerance.maximum && rmse <= tolerance.rmse, finite, count: actual.length, maximumAbsoluteError: max, rmse, tolerance };
}
async function execute(variant, repeat, caseIndices, timing) {
  const run = { variant: variant.id, layer: variant.layer, repeat, passed: false, samples: [] };
  report.runs.push(run); await persist();
  let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, args: manifest.browserArguments ?? [] });
    run.chrome = await browser.version();
    const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 1100, height: 800 } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    const urlPath = variant.page.startsWith('experiments/') ? variant.page : path.relative(root, path.join(directory, variant.page));
    const loadStarted = performance.now();
    await page.goto(`${origin}/${urlPath}`, { waitUntil: 'load', timeout: 120000 });
    await page.evaluate(() => document.fonts.ready);
    run.loadMilliseconds = performance.now() - loadStarted;
    run.pageAudit = await page.evaluate(() => {
      const trees = [document];
      for (let i = 0; i < trees.length; i++) for (const node of trees[i].querySelectorAll('*')) if (node.shadowRoot) trees.push(node.shadowRoot);
      return { authorScriptElements: trees.reduce((n, tree) => n + tree.querySelectorAll('script').length, 0), elements: trees.reduce((n, tree) => n + tree.querySelectorAll('*').length, 0), fonts: [...document.fonts].map(f => ({ family: f.family, status: f.status })), csp: document.querySelector('meta[http-equiv="Content-Security-Policy"]')?.content ?? null };
    });
    if (run.pageAudit.authorScriptElements !== 0) throw new Error('Author scripts present');
    if (run.pageAudit.fonts.some(f => f.status === 'error')) throw new Error('Font failed to load');
    let epoch = Number(manifest.initialEpoch ?? 1);
    for (let index = 0; index < caseIndices.length; index++) {
      const caseIndex = caseIndices[index];
      epoch += 1;
      const externalStarted = performance.now();
      const observation = await page.evaluate(async ({ caseIndex, epoch, timeout, terminal, heightScale }) => {
        const control = document.querySelector(`#case-${caseIndex}`);
        if (!control) throw new Error(`Missing raw input fixture${caseIndex}`);
        const find = (selector) => {
          const queue = [document];
          for (let i = 0; i < queue.length; i++) { const found = queue[i].querySelector(selector); if (found) return found; for (const el of queue[i].querySelectorAll('*')) if (el.shadowRoot) queue.push(el.shadowRoot); }
          return null;
        };
        const terminalElement = find(terminal);
        if (!terminalElement) throw new Error(`Missing final terminal${terminal}`);
        const started = performance.now();
        control.checked = true;
        document.body.style.setProperty('--epoch', String(epoch));
        let polls = 0, geometryReadMilliseconds = 0;
        while (true) {
          const readStarted = performance.now();
          const bounds = terminalElement.getBoundingClientRect();
          geometryReadMilliseconds += performance.now() - readStarted;
          polls += 1;
          if (Math.abs(bounds.height - epoch * heightScale) <= .02 && bounds.width > 0) return { milliseconds: performance.now() - started, width: bounds.width, height: bounds.height, polls, geometryReadMilliseconds };
          if (performance.now() - started > timeout) throw new Error(`Generation${epoch} timeout: width${bounds.width}, height${bounds.height}, expectedHeight${epoch * heightScale}`);
          await new Promise(requestAnimationFrame);
        }
      }, { caseIndex, epoch, timeout: updateTimeout, terminal: variant.terminal ?? '#terminal', heightScale: manifest.terminalHeightScale ?? 64 });
      const externalMilliseconds = performance.now() - externalStarted;
      const readouts = manifest.readouts ?? {
        state: { selector: '.state-value', offset: 4096, scale: 32 },
        nextLayerNorm: { selector: '.next-ln-value', offset: 4096, scale: 256 },
      };
      const verificationStarted = performance.now();
      const actual = await page.evaluate((readouts) => {
        const trees = [document];
        for (let i = 0; i < trees.length; i++) for (const node of trees[i].querySelectorAll('*')) if (node.shadowRoot) trees.push(node.shadowRoot);
        return Object.fromEntries(Object.entries(readouts).map(([key, readout]) => [key, trees.flatMap(tree => [...tree.querySelectorAll(readout.selector)]).map(node => (node.getBoundingClientRect().width - readout.offset) / readout.scale)]));
      }, readouts);
      const expected = expectedFor(variant, caseIndex);
      if (!expected) throw new Error(`Missing oracle for${variant.id} case${caseIndex}`);
      const checks = Object.fromEntries(Object.keys(readouts).map(key => [key, numerical(actual[key], expected[key], (variant.tolerances ?? manifest.tolerances)[key])]));
      const common = manifest.layers.find(item => item.layer === variant.layer).commonExactGeluFloatProjection;
      const commonTargetErrors = { state: numerical(actual.state, common.states[caseIndex], { maximum: Infinity, rmse: Infinity }), nextLayerNorm: numerical(actual.nextLayerNorm, common.nextLn[caseIndex], { maximum: Infinity, rmse: Infinity }) };
      for (const value of Object.values(commonTargetErrors)) { delete value.passed; delete value.tolerance; }
      const sample = { commonTargetErrors, index, caseIndex, epoch, phase: timing && index < warmups ? 'warmup' : timing ? 'measured' : 'correctness', ...observation, externalMilliseconds, verificationMilliseconds: performance.now() - verificationStarted, checks, passed: Object.values(checks).every(x => x.passed) };
      // Persist all values for gates; timing retains scalar checks plus repeatable source fixture/oracles.
      if (!timing || !sample.passed) sample.actual = actual;
      run.samples.push(sample);
      await persist();
      if (!sample.passed) throw new Error(`Numerical failure${variant.id} case${caseIndex}: ${JSON.stringify(checks)}`);
      console.log(JSON.stringify({ variant: variant.id, repeat, index, caseIndex, epoch, milliseconds: observation.milliseconds, passed: sample.passed }));
    }
    run.errors = errors;
    if (errors.length) throw new Error(errors.join('\n'));
    if (timing) run.timing = summarize(run.samples.filter(s => s.phase === 'measured').map(s => s.milliseconds));
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
      const caseIndices = mode === 'smoke' ? [0] : manifest.cases.map((_, index) => index);
      await execute(variant, 0, caseIndices, false);
    }
  } else {
    for (let repeat = 0; repeat < repeats; repeat++) {
      const ordered = repeat % 2 ? [...variants].reverse() : variants;
      const caseIndices = Array.from({ length: warmups + measured }, (_, i) => (i + repeat) % manifest.cases.length);
      for (const variant of ordered) await execute(variant, repeat, caseIndices, true);
    }
    const summaries = variants.map(v => ({ variant: v.id, processMediansMilliseconds: report.runs.filter(r => r.variant === v.id).map(r => r.timing.median) }));
    report.summary = { variants: summaries, pairs: Array.from({ length: repeats }, (_, repeat) => {
      const runs = report.runs.filter(r => r.repeat === repeat);
      return { repeat, order: runs.map(r => r.variant), mediansMilliseconds: Object.fromEntries(runs.map(r => [r.variant, r.timing.median])) };
    }) };
  }
  report.passed = report.runs.length > 0 && report.runs.every(r => r.passed);
} catch (error) { report.error = String(error?.stack ?? error); process.exitCode = 1; }
finally { report.finishedAt = new Date().toISOString(); await persist(); await new Promise(resolve => server.close(resolve)); }
console.log(JSON.stringify({ output, passed: report.passed, summary: report.summary, error: report.error }, null, 2));
