import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { performance } from 'node:perf_hooks';
import os from 'node:os';

const require = createRequire(import.meta.url);
const modules = process.env.CODEX_NODE_MODULES ?? '/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const { chromium } = require(`${modules}/playwright`);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const label = process.argv[2] ?? 's64';
const rounds = Number(process.argv[3] ?? 8);
const directory = path.join(root, 'experiments/fused-attention-font-probe', label);
const manifest = JSON.parse(await fs.readFile(path.join(directory, 'manifest.json'), 'utf8'));
const output = path.join(directory, `browser-results-r${rounds}.json`);
try { await fs.access(output); throw new Error(`Refusing to replace ${output}`); }
catch (error) { if (error.code !== 'ENOENT') throw error; }
await fs.copyFile(fileURLToPath(import.meta.url), path.join(directory, `harness-source-r${rounds}.mjs`));
const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true,
  args: ['--allow-file-access-from-files', '--enable-experimental-web-platform-features'],
});
const report = { chrome: await browser.version(), platform: `${os.platform()} ${os.release()}`, node: process.version,
  label, rounds, scope: manifest.scope, runtimeContainsJavaScript: false, trials: [], errors: [] };
const summarize = (a, b) => {
  const d = a.map((x, i) => x - b[i]);
  return { rmse: Math.sqrt(d.reduce((s, x) => s + x * x, 0) / d.length), maximum: Math.max(...d.map(Math.abs)), finite: a.every(Number.isFinite) };
};
const median = (values) => { const sorted = values.toSorted((a, b) => a - b); return sorted[Math.floor(sorted.length / 2)]; };
try {
  for (let round = 0; round < rounds; round++) {
    for (const mode of (round % 2 ? ['fused', 'css'] : ['css', 'fused'])) {
      const page = await browser.newPage({ viewport: { width: 100, height: 100 } });
      const consoleMessages = [];
      page.on('console', (message) => consoleMessages.push({ type: message.type(), text: message.text() }));
      const session = await page.context().newCDPSession(page);
      await session.send('Performance.enable');
      const started = performance.now();
      await page.goto(pathToFileURL(path.join(directory, `${mode}.html`)).href, { waitUntil: 'load', timeout: 120000 });
      await page.evaluate(() => document.fonts.ready);
      const fontStates = await page.evaluate(() => [...document.fonts].map((face) => ({ family: face.family, status: face.status })));
      report.fontLoads ??= [];
      report.fontLoads.push({ round, mode, fontStates, consoleMessages, elements: await page.locator('*').count() });
      if (mode === 'fused' && !fontStates.some((face) => face.family === 'FusedAttention' && face.status === 'loaded')) {
        throw new Error(`Fused font did not load: ${JSON.stringify({ fontStates, consoleMessages })}`);
      }
      const loaded = performance.now() - started;
      const read = async (index) => page.evaluate((caseIndex) => {
        // External fixture stimulus and geometry observation only; all model arithmetic is CSS/font.
        document.querySelector('.input').dataset.case = String(caseIndex);
        const values = [...document.querySelectorAll('.answer')].map((e) => e.getBoundingClientRect().width);
        const denominator = document.querySelector('.den-answer').getBoundingClientRect().width;
        return { values, denominator };
      }, index);
      await read(0);
      const sequence = [1, 0, 2, 0, 3, 4, 5, 6, 7, ...Array.from({ length: manifest.cases.length - 8 }, (_, i) => i + 8)];
      for (const index of sequence) {
        const before = Object.fromEntries((await session.send('Performance.getMetrics')).metrics.map(({ name, value }) => [name, value]));
        const tick = performance.now();
        const observed = await read(index);
        const milliseconds = performance.now() - tick;
        const after = Object.fromEntries((await session.send('Performance.getMetrics')).metrics.map(({ name, value }) => [name, value]));
        const ref = manifest.cases[index].reference;
        const actual = observed.values.map((x) => (x - 10000) / 1000);
        const denominator = observed.denominator / 1000;
        const target = mode === 'fused' ? ref.representedContext : ref.context;
        const targetDen = mode === 'fused' ? ref.representedDenominator : ref.denominator;
        const sums = mode === 'fused' ? await page.locator('.sumrow').evaluateAll((elements) => elements.toSorted((a, b) => Number(a.id.slice(4)) - Number(b.id.slice(4))).map((e) => e.getBoundingClientRect().width)) : [];
        const transport = summarize(actual, target);
        report.trials.push({ round, mode, caseIndex: index, name: manifest.cases[index].name, loadedMilliseconds: loaded,
          milliseconds, actual, denominator, transport, truthError: summarize(actual, ref.context),
          denominatorAbsoluteError: Math.abs(denominator - ref.denominator),
          denominatorRelativeError: Math.abs(denominator - ref.denominator) / Math.max(1e-15, ref.denominator),
          denominatorTransportError: Math.abs(denominator - targetDen),
          rawSumError: mode === 'fused' ? summarize(sums, ref.representedSums) : null,
          inputClipped: ref.inputClipped, scoreClipped: ref.scoreClipped,
          expectedFailure: manifest.cases[index].expectedFailure,
          metrics: Object.fromEntries(['RecalcStyleDuration', 'LayoutDuration', 'TaskDuration', 'RecalcStyleCount', 'LayoutCount'].map((key) => [key, (after[key] ?? 0) - (before[key] ?? 0)])),
        });
      }
      await page.close();
    }
  }
  report.summary = {};
  for (const mode of ['css', 'fused']) {
    const measured = report.trials.filter((x) => x.mode === mode && x.round > 0 && x.caseIndex < 3);
    const validated = report.trials.filter((x) => x.mode === mode && !x.expectedFailure);
    report.summary[mode] = { warmCompleteMedianMilliseconds: median(measured.map((x) => x.milliseconds)),
      queryOnlyMedianMilliseconds: median(measured.filter((x) => x.caseIndex === 1).map((x) => x.milliseconds)),
      allInputMedianMilliseconds: median(measured.filter((x) => x.caseIndex === 2).map((x) => x.milliseconds)),
      maximumTransportError: Math.max(...validated.map((x) => x.transport.maximum)),
      maximumTruthRmse: Math.max(...validated.map((x) => x.truthError.rmse)),
      maximumTruthError: Math.max(...validated.map((x) => x.truthError.maximum)),
      maximumDenominatorRelativeError: Math.max(...validated.map((x) => x.denominatorRelativeError)),
      correctnessPass: validated.every((x) => x.transport.finite && x.transport.maximum < 0.01 && x.truthError.maximum < 0.1 && x.denominatorRelativeError < 0.05 && x.inputClipped === 0 && x.scoreClipped === 0),
    };
  }
} catch (error) {
  report.errors.push({ name: error.name, message: error.message, stack: error.stack });
  process.exitCode = 1;
} finally {
  await browser.close();
  await fs.writeFile(output, `${JSON.stringify(report, null, 2)}\n`);
}
console.log(JSON.stringify({ summary: report.summary, errors: report.errors, output }, null, 2));
