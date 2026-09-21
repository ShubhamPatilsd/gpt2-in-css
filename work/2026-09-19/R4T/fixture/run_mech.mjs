// R4T mechanism fixture runner: per variant page, fresh context (no JS), load -> quiescent -> 6 mutations of --in via <html class="go-k"> ->
// per mutation: RecalcStyleDuration / RecalcStyleCount / LayoutDuration / TaskDuration deltas until quiescent (RecalcStyleCount stable 400 ms).
import fs from "node:fs"; import path from "node:path"; import { execFileSync } from "node:child_process"; import { createRequire } from "node:module"; import { fileURLToPath } from "node:url";
const here = path.dirname(fileURLToPath(import.meta.url)); const require = createRequire(import.meta.url); const argv = process.argv.slice(2);
const opt = (k, d) => { const i = argv.indexOf(k); return i >= 0 && argv[i + 1] != null ? argv[i + 1] : d; };
const TAG = opt("--tag", "mech"); const TRIALS = Number(opt("--trials", 2)); const OUT = path.resolve(here, opt("--out", "results")); const VARIANTS = opt("--variants", "").split(",").filter(Boolean);
const dependencyRoot = process.env.CODEX_NODE_MODULES ?? "/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const executablePath = process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const { chromium } = require(`${dependencyRoot}/playwright`);
const sh = (c, a) => { try { return execFileSync(c, a, { encoding: "utf8" }).trim(); } catch { return ""; } };
const batt = sh("/usr/bin/pmset", ["-g", "batt"]); if (!/AC Power/.test(batt) && !argv.includes("--allow-battery")) { console.error("not on AC"); process.exit(2); }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms)); const mm = (r) => Object.fromEntries(r.metrics.map(({ name, value }) => [name, value]));
const log = (...a) => console.log(JSON.stringify({ t: Math.round(performance.now()), ...Object.assign({}, ...a) }));
const metas = JSON.parse(fs.readFileSync(path.join(here, "pages", "mech-variants.json"), "utf8")); const variants = VARIANTS.length ? VARIANTS : Object.keys(metas);
async function quiet(cdp, base, minRecalc) { let last = base, changed = performance.now(), t0 = changed; for (;;) { await sleep(50); const now = mm(await cdp.send("Performance.getMetrics")); if (now.RecalcStyleCount !== last.RecalcStyleCount || now.LayoutCount !== last.LayoutCount) changed = performance.now(); last = now; const ok = now.RecalcStyleCount - base.RecalcStyleCount >= minRecalc; if ((ok && performance.now() - changed >= 400) || performance.now() - t0 > 60000) return last; } }
async function trial(browser, name, t) {
  const meta = metas[name]; const ctx = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 800, height: 600 } }); const pw = await ctx.newPage(); const cdp = await ctx.newCDPSession(pw);
  await cdp.send("Performance.enable", { timeDomain: "timeTicks" }); await cdp.send("DOM.enable"); await cdp.send("CSS.enable");
  const tl = performance.now(); await pw.goto(`file://${path.join(here, "pages", `mech-${name}.html`)}`, { waitUntil: "load", timeout: 600000 }); const loadMs = performance.now() - tl;
  let m = await quiet(cdp, mm(await cdp.send("Performance.getMetrics")), 0);
  const { root } = await cdp.send("DOM.getDocument", { depth: 1 }); const htmlId = (root.children.find((c) => c.localName === "html") ?? root.children[0]).nodeId;
  const readerId = (await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: "#reader" })).nodeId;
  const K = meta.anim || 64; const prop = `--o-${meta.M - 1}-${K - 1}`;
  const readVal = async () => { const { computedStyle } = await cdp.send("CSS.getComputedStyleForNode", { nodeId: readerId }); const p = computedStyle.find((x) => x.name === prop); return p ? Number(p.value) : null; };
  const muts = [];
  for (let k = 1; k <= 6; k++) {
    const b = mm(await cdp.send("Performance.getMetrics")); const w0 = performance.now();
    await cdp.send("DOM.setAttributeValue", { nodeId: htmlId, name: "class", value: `go-${k}` });
    const a = await quiet(cdp, b, 1); const v = await readVal();
    muts.push({ k, styleMs: (a.RecalcStyleDuration - b.RecalcStyleDuration) * 1000, recalcs: a.RecalcStyleCount - b.RecalcStyleCount, layoutMs: (a.LayoutDuration - b.LayoutDuration) * 1000, layouts: a.LayoutCount - b.LayoutCount, taskMs: (a.TaskDuration - b.TaskDuration) * 1000, wallMs: performance.now() - w0, value: v, expected: meta.anim ? null : (k * 7) * 1.0001 + (meta.M - 1) * K + K - 1 });
  }
  const med = (xs) => { const s = [...xs].sort((x, y) => x - y); return s[s.length >> 1]; };
  const steady = muts.slice(1); const rec = { tag: TAG, name, trial: t, meta, loadMs, nodes: m.Nodes, muts, styleMsMed: med(steady.map((x) => x.styleMs)), taskMsMed: med(steady.map((x) => x.taskMs)), recalcsMed: med(steady.map((x) => x.recalcs)), layoutMsMed: med(steady.map((x) => x.layoutMs)), rssKb: Number(sh("/bin/sh", ["-c", "ps -o rss= -p $(pgrep -f '^/Applications/.*Google Chrome .*--type=renderer' | head -1) 2>/dev/null"])) || null };
  await ctx.close(); log({ name, t, loadMs: +loadMs.toFixed(0), styleMsMed: +rec.styleMsMed.toFixed(1), taskMsMed: +rec.taskMsMed.toFixed(1), recalcs: rec.recalcsMed, layoutMsMed: +rec.layoutMsMed.toFixed(1), value: muts[5].value, expected: muts[5].expected, first: +muts[0].styleMs.toFixed(1) }); return rec;
}
const browser = await chromium.launch({ executablePath, headless: true, args: ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows"] });
log({ launched: await browser.version(), variants, trials: TRIALS }); const out = fs.createWriteStream(path.join(OUT, `${TAG}.jsonl`), { flags: "a" });
for (let t = 0; t < TRIALS; t++) for (const name of variants) { try { out.write(JSON.stringify(await trial(browser, name, t)) + "\n"); } catch (e) { log({ name, t, error: String(e).slice(0, 300) }); } }
out.end(); await browser.close(); log({ done: true });
