#!/usr/bin/env node
// analyze_r2b.mjs -- medians, fits and decisions for MB6..MB9 from results/*.jsonl.
//   node analyze_r2b.mjs [--results results] [--md results/analysis.md]
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { median } from "./parse_trace.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const opt = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
// --results a,b,c : later dirs supersede earlier ones for the same variant (re-runs)
const RES_DIRS = opt("--results", "results").split(",").map((d) => path.resolve(here, d));
const RES = RES_DIRS.join(",");
const MD = opt("--md", null);
const manifest = JSON.parse(fs.readFileSync(path.join(here, "pages", "manifest.json"), "utf8"));
const params = Object.fromEntries(manifest.pages.map((p) => [p.id, p.params]));

const recsByVariant = new Map();
for (const dir of RES_DIRS) {
  for (const f of fs.readdirSync(dir)) {
    if (!f.endsWith(".jsonl")) continue;
    const rs = fs.readFileSync(path.join(dir, f), "utf8").split("\n").filter((l) => l.trim()).map((l) => JSON.parse(l));
    if (rs.length) recsByVariant.set(rs[0].variant, rs.map((r) => ({ ...r, resultsDir: path.basename(dir) })));
  }
}
const recs = [...recsByVariant.values()].flat();
const byVariant = new Map();
for (const r of recs) { if (!byVariant.has(r.variant)) byVariant.set(r.variant, []); byVariant.get(r.variant).push(r); }

const ev = (t, name) => (t?.eventsByName?.[name]?.selfUs ?? 0) / 1000;
const evIncl = (t, name) => (t?.eventsByName?.[name]?.inclUs ?? 0) / 1000;
const evCount = (t, name) => t?.eventsByName?.[name]?.count ?? 0;

function row(r) {
  const t = r.trace ?? {};
  const frames = Math.max(evCount(t, "ProxyMain::BeginMainFrame"), evCount(t, "Commit"), t.frames?.commit ?? 0) || NaN;
  return {
    ultN: t.updateLayoutTree?.count, ultMs: (t.updateLayoutTree?.totalUs ?? NaN) / 1000,
    elems: (t.updateLayoutTree?.elementCounts ?? []).reduce((a, b) => a + (b ?? 0), 0),
    layN: t.layout?.count, layMs: (t.layout?.totalUs ?? 0) / 1000,
    shapeMs: ev(t, "InlineNode::ShapeTextIncludingFirstLine"),
    perfLayoutSelfMs: ev(t, "LocalFrameView::performLayout"),
    prePaintMs: (t.prePaint?.totalUs ?? 0) / 1000 + ev(t, "Blink.PrePaint.UpdateTime") + ev(t, "LocalFrameView::RunPrePaintLifecyclePhase") + ev(t, "CullRectUpdate"),
    paintMs: (t.paint?.totalUs ?? 0) / 1000,
    paintLifeMs: evIncl(t, "LocalFrameView::RunPaintLifecyclePhase") || evIncl(t, "Blink.Paint.UpdateTime"),
    compInputsMs: ev(t, "Blink.CompositingInputs.UpdateTime") + ev(t, "LocalFrameView::RunCompositingInputsLifecyclePhase"),
    hitMs: (t.hitTest?.totalUs ?? 0) / 1000 + ev(t, "LayoutView::HitTest") + evIncl(t, "EventHandler::handleMouseMoveEvent") + evIncl(t, "EventHandler::HandleMouseMoveEvent"),
    mouseMoveMs: evIncl(t, "EventHandler::handleMouseMoveEvent") + evIncl(t, "EventHandler::HandleMouseMoveEvent") + evIncl(t, "EventHandler::UpdateHoverActiveState") + evIncl(t, "MouseEventManager::FakeMouseMove"),
    animMs: (t.animation?.bucket?.selfUs ?? 0) / 1000,
    busyMs: (t.topLevelBusyUs ?? NaN) / 1000,
    frames,
    activeMs: r.harness?.activeMs,
    rsc: r.metricsDelta?.RecalcStyleCount, rsdMs: r.metricsDelta?.RecalcStyleDurationMs,
    rssMB: r.rssAfterLoad?.maxRendererRssMB, rssMutMB: r.rssAfterMutation?.maxRendererRssMB,
    nodes: r.metricsAfterLoad?.Nodes, layoutObjects: r.metricsAfterLoad?.LayoutObjects,
    verified: r.verify?.changed === true, forced: r.harness?.forced === true, error: !!r.error,
  };
}
const fmt = (v, d = 2) => (Number.isFinite(v) ? v.toFixed(d) : "-");

const S = new Map();
for (const [v, rs] of byVariant) {
  const ok = rs.filter((r) => !r.error);
  const rows = ok.map(row);
  const med = {}; for (const k of Object.keys(rows[0] ?? {})) med[k] = median(rows.map((x) => x[k]));
  const mm = (k) => { const a = rows.map((x) => x[k]).filter(Number.isFinite); return a.length ? [Math.min(...a), Math.max(...a)] : [NaN, NaN]; };
  S.set(v, { variant: v, family: rs[0].family, params: params[v] ?? rs[0].params, bytes: rs[0].bytes, n: ok.length, errors: rs.length - ok.length, med,
    ultMM: mm("ultMs"), layMM: mm("layMs"), busyMM: mm("busyMs"),
    verified: rows.filter((x) => x.verified).length, forced: rows.filter((x) => x.forced).length,
    rss0: rows[0]?.rssMB, top: ok[0]?.trace?.topSelf?.slice(0, 6) ?? [], dir: rs[0].resultsDir });
}
const get = (id) => S.get(id);
const out = []; const P = (s = "") => out.push(s);
const vcol = (s) => `${s.verified}/${s.n}${s.forced ? ` F${s.forced}` : ""}${s.errors ? ` E${s.errors}` : ""}`;

function fit(xs, ys) {
  const n = xs.length; if (n < 2) return null;
  const mx = xs.reduce((a, b) => a + b, 0) / n, my = ys.reduce((a, b) => a + b, 0) / n;
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < n; i++) { sxy += (xs[i] - mx) * (ys[i] - my); sxx += (xs[i] - mx) ** 2; syy += (ys[i] - my) ** 2; }
  const b = sxy / sxx, a = my - b * mx;
  const ssr = xs.reduce((acc, x, i) => acc + (ys[i] - (a + b * x)) ** 2, 0);
  return { a, b, r2: syy ? 1 - ssr / syy : 1, n };
}

P(`# R2B analysis (auto-generated by analyze_r2b.mjs from ${RES})`); P();
P(`${recs.length} trial records, ${byVariant.size} variants. Medians over traced trials; [min–max] where shown. ULT = UpdateLayoutTree ms (style), Layout ms, Shape = InlineNode::ShapeTextIncludingFirstLine self ms, RSS = renderer RSS after load (MB), verified must be n/n.`); P();

// ---------------- MB6 ----------------
P(`## MB6 inherited registration count tax (N=5,000 dirtied descendants, one var() each)`); P();
P(`| variant | K | root inherits | declared on | --q inherits | ULT ms [min–max] | elems | µs/elem | RSS MB (trial 0) | Busy ms | verified | run |`);
P(`|---|---:|---|---|---|---:|---:|---:|---:|---:|---|---|`);
const mb6 = [...S.values()].filter((s) => s.family === "mb6").sort((a, b) => a.variant.localeCompare(b.variant, undefined, { numeric: true }));
for (const s of mb6) {
  P(`| ${s.variant} | ${s.params.K} | ${s.params.root_inherits} | ${s.params.declared ? s.params.declared_on : "(undeclared)"} | ${s.params.q_inherits} | ${fmt(s.med.ultMs)} [${fmt(s.ultMM[0])}–${fmt(s.ultMM[1])}] | ${fmt(s.med.elems, 0)} | ${fmt(s.med.ultMs * 1e3 / s.params.N, 2)} | ${fmt(s.rss0, 0)} | ${fmt(s.med.busyMs)} | ${vcol(s)} | ${s.dir} |`);
}
P();
for (const [label, sel] of [["inh1-onhtml-q1", (s) => s.params.root_inherits && s.params.declared_on === "html" && s.params.q_inherits && s.params.declared],
  ["inh1-onbody-q1", (s) => s.params.root_inherits && s.params.declared_on === "body" && s.params.q_inherits && s.params.declared],
  ["inh0-onhtml-q1", (s) => !s.params.root_inherits && s.params.declared_on === "html"], ["inh0-onbody-q1", (s) => !s.params.root_inherits && s.params.declared_on === "body"]]) {
  const rows = mb6.filter(sel).sort((a, b) => a.params.K - b.params.K);
  if (rows.length >= 2) {
    const f = fit(rows.map((s) => s.params.K), rows.map((s) => s.med.ultMs * 1e3 / s.params.N));
    const fr = fit(rows.map((s) => s.params.K), rows.map((s) => s.rss0));
    P(`- ${label}: µs/element = ${fmt(f.a, 2)} + ${fmt(f.b * 1000, 3)} per 1,000 registrations (R²=${fmt(f.r2, 3)}); RSS = ${fmt(fr.a, 0)} + ${fmt(fr.b * 1000, 1)} MB per 1,000 registrations (R²=${fmt(fr.r2, 3)})`);
  }
}
P();

// ---------------- MB7 ----------------
P(`## MB7 font-variation-settings list evaluation (real 256-axis HVAR fonts, one glyph per font in the stack)`); P();
P(`| variant | spelling | L | M | rule | MB | ULT ms [min–max] | elems | µs/elem | ns/entry/elem | Layout ms [min–max] | Shape self ms | Layout µs/elem | Busy ms | RSS MB | verified |`);
P(`|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|`);
const mb7 = [...S.values()].filter((s) => s.family === "mb7").sort((a, b) => (a.params.L - b.params.L) || (a.params.M - b.params.M) || a.variant.localeCompare(b.variant));
const perElem = (s) => (s.med.ultMs * 1e3) / s.params.M;
for (const s of mb7) {
  P(`| ${s.variant} | ${s.params.spelling} | ${s.params.L} | ${s.params.M} | ${s.params.shared_rule ? "shared" : "uniq"} | ${(s.bytes / 1e6).toFixed(2)} | ${fmt(s.med.ultMs)} [${fmt(s.ultMM[0])}–${fmt(s.ultMM[1])}] | ${fmt(s.med.elems, 0)} | ${fmt(perElem(s), 1)} | ${fmt(perElem(s) * 1e3 / s.params.L, 1)} | ${fmt(s.med.layMs)} [${fmt(s.layMM[0])}–${fmt(s.layMM[1])}] | ${fmt(s.med.shapeMs)} | ${fmt(s.med.layMs * 1e3 / s.params.M, 0)} | ${fmt(s.med.busyMs)} | ${fmt(s.rss0, 0)} | ${vcol(s)} |`);
}
P();
P(`Fits at M=32 (uniq), per element: ULT µs/element = a + b·L (b = ns per list entry):`); P();
const cEntry = {};
for (const sp of ["lit", "var", "round", "hoist"]) {
  const rows = mb7.filter((s) => s.params.spelling === sp && s.params.M === 32 && !s.params.shared_rule).sort((a, b) => a.params.L - b.params.L);
  if (rows.length >= 2) {
    const f = fit(rows.map((s) => s.params.L), rows.map(perElem));
    const fl = fit(rows.map((s) => s.params.L), rows.map((s) => s.med.layMs * 1e3 / s.params.M));
    cEntry[sp] = f.b;
    P(`- ${sp}: style ${fmt(f.a, 1)} µs/element + ${fmt(f.b * 1000, 1)} ns/entry (R²=${fmt(f.r2, 3)}); layout ${fmt(fl.a, 0)} µs/element + ${fmt(fl.b * 1000, 1)} ns/entry (R²=${fmt(fl.r2, 3)})`);
  }
}
P();
P(`M sweep at L=768 (uniq): ULT total ms and Layout total ms vs M (is cost ∝ M? does the shared rule collapse it?):`); P();
P(`| spelling | M=1 ULT / Layout | M=32 ULT / Layout | M=128 ULT / Layout | M=128 shared ULT / Layout | ULT µs/elem M=128 uniq → shared | Layout µs/elem M=128 uniq → shared |`);
P(`|---|---:|---:|---:|---:|---:|---:|`);
for (const sp of ["lit", "var", "round", "hoist"]) {
  const g = (M, shared) => mb7.find((s) => s.params.spelling === sp && s.params.L === 768 && s.params.M === M && !!s.params.shared_rule === shared);
  const m1 = g(1, false), m32 = g(32, false), m128 = g(128, false), sh = g(128, true);
  const c = (s) => s ? `${fmt(s.med.ultMs)} / ${fmt(s.med.layMs)}` : "-";
  P(`| ${sp} | ${c(m1)} | ${c(m32)} | ${c(m128)} | ${c(sh)} | ${m128 && sh ? `${fmt(perElem(m128), 0)} → ${fmt(perElem(sh), 0)}` : "-"} | ${m128 && sh ? `${fmt(m128.med.layMs * 1e3 / 128, 0)} → ${fmt(sh.med.layMs * 1e3 / 128, 0)}` : "-"} |`);
}
P();
// hoist parent cost: M=1 hoist vs var
const h1 = mb7.find((s) => s.variant === "mb7-hoist-L768-M1-uniq"), v1 = mb7.find((s) => s.variant === "mb7-var-L768-M1-uniq"), r1 = mb7.find((s) => s.variant === "mb7-round-L768-M1-uniq");
if (h1 && v1 && r1) P(`Parent-side cost of the hoist (M=1, L=768): hoist ULT ${fmt(h1.med.ultMs)} ms vs var ${fmt(v1.med.ultMs)} ms → the 768 round() on #par cost ≈ ${fmt(h1.med.ultMs - v1.med.ultMs)} ms once; round consumer ${fmt(r1.med.ultMs)} ms.`);
P();

// ---------------- MB8 ----------------
P(`## MB8 dirtied font element whose list does NOT change (L=768, M=128, unrelated inherited write)`); P();
P(`| variant | kind | MB | ULT ms [min–max] | elems | µs/elem | ns/entry/elem | Layout ms [min–max] | Shape ms | Busy ms | verified | run |`);
P(`|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|`);
const mb8 = [...S.values()].filter((s) => s.family === "mb8").sort((a, b) => a.med.ultMs - b.med.ultMs);
const plain = get("mb8-plain-L768-M128");
for (const s of mb8) {
  const d = plain ? (s.med.ultMs - plain.med.ultMs) * 1e3 / 128 : NaN;
  P(`| ${s.variant} | ${s.params.kind} | ${(s.bytes / 1e6).toFixed(2)} | ${fmt(s.med.ultMs)} [${fmt(s.ultMM[0])}–${fmt(s.ultMM[1])}] | ${fmt(s.med.elems, 0)} | ${fmt(s.med.ultMs * 1e3 / 128, 1)} | ${fmt(d * 1e3 / 768, 1)} | ${fmt(s.med.layMs)} [${fmt(s.layMM[0])}–${fmt(s.layMM[1])}] | ${fmt(s.med.shapeMs)} | ${fmt(s.med.busyMs)} | ${vcol(s)} | ${s.dir} |`);
}
P();
const r768 = get("mb7-round-L768-M128-uniq"), rc = get("mb8-round-const-L768-M128"), hc = get("mb8-var-const-L768-M128"), h768 = get("mb7-hoist-L768-M128-uniq");
if (r768 && rc) P(`round: unchanged-list restyle costs ${fmt(rc.med.ultMs / r768.med.ultMs * 100, 0)} % of the changed-list restyle (${fmt(rc.med.ultMs)} vs ${fmt(r768.med.ultMs)} ms); Layout ${fmt(rc.med.layMs)} vs ${fmt(r768.med.layMs)} ms.`);
if (h768 && hc) P(`hoist/var: unchanged-list restyle ${fmt(hc.med.ultMs)} vs changed ${fmt(h768.med.ultMs)} ms; Layout ${fmt(hc.med.layMs)} vs ${fmt(h768.med.layMs)} ms.`);
P();

// ---------------- MB9 ----------------
P(`## MB9 frame overhead knobs (per-frame ms = window total / frames; gate = 1 ms width animation)`); P();
P(`| variant | knob | mouse | dirty | frames | ULT ms | elems | Layout ms | PrePaint ms | Paint ms | paint lifecycle incl ms | compositing inputs ms | hit-test/mousemove ms | Anim ms | Busy ms [min–max] | Busy/frame | LayoutObjects | RSS MB | verified |`);
P(`|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|`);
const mb9 = [...S.values()].filter((s) => s.family === "mb9").sort((a, b) => a.variant.localeCompare(b.variant));
for (const s of mb9) {
  const m = s.med;
  P(`| ${s.variant} | ${s.params.knob} | ${s.params.mouse} | ${s.params.dirty} | ${fmt(m.frames, 0)} | ${fmt(m.ultMs)} | ${fmt(m.elems, 0)} | ${fmt(m.layMs)} | ${fmt(m.prePaintMs)} | ${fmt(m.paintMs)} | ${fmt(m.paintLifeMs)} | ${fmt(m.compInputsMs)} | ${fmt(m.hitMs)} | ${fmt(m.animMs)} | ${fmt(m.busyMs)} [${fmt(s.busyMM[0])}–${fmt(s.busyMM[1])}] | ${fmt(m.busyMs / m.frames)} | ${fmt(m.layoutObjects, 0)} | ${fmt(s.rss0, 0)} | ${vcol(s)} |`);
}
P();
const base9 = get("mb9-default-mouse"), none9 = get("mb9-none-mouse");
if (base9) {
  P(`Δ vs default-mouse (non-style busy = Busy − ULT, per frame), and predicted s/token at 85 frames/token:`); P();
  P(`| knob | non-style busy/frame ms | Δ vs default ms/frame | predicted Δ s/token (×85) |`); P(`|---|---:|---:|---:|`);
  const ns = (s) => (s.med.busyMs - s.med.ultMs) / s.med.frames;
  for (const s of mb9) P(`| ${s.variant} | ${fmt(ns(s))} | ${fmt(ns(s) - ns(base9))} | ${fmt((ns(s) - ns(base9)) * 85 / 1000, 2)} |`);
  P();
}

// ---------------- validity ----------------
P(`## Validity`); P();
for (const s of S.values()) if (s.verified < s.n || s.forced || s.errors) P(`- ${s.variant}: verified ${s.verified}/${s.n}, forced ${s.forced}, errors ${s.errors}`);
P(`- top self-time events, selected: `);
for (const id of ["mb7-round-L3072-M32-uniq", "mb7-hoist-L3072-M32-uniq", "mb8-round-const-L768-M128", "mb9-default-mouse", "mb9-default-mouse-dirty", "mb9-fixedfc-mouse"]) {
  const s = get(id); if (s) P(`  - ${id}: ${s.top.map((r) => `${r.name} ${fmt(r.selfUs / 1000, 1)}ms×${r.count}`).join(", ")}`);
}
const text = out.join("\n") + "\n";
if (MD) fs.writeFileSync(MD, text);
process.stdout.write(text);
