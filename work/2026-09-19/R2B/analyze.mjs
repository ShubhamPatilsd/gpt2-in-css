#!/usr/bin/env node
// analyze.mjs -- read results/*.jsonl, print per-family median tables and least-squares fits
// (per-element fixed cost in us, per-byte cost in ns/B) for the sweeps where that applies.
//   node analyze.mjs [--results results] [--md results/analysis.md]
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { median } from "./parse_trace.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const opt = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const RES = path.resolve(here, opt("--results", "results"));
const MD = opt("--md", null);

const recs = [];
for (const f of fs.readdirSync(RES)) {
  if (!f.endsWith(".jsonl")) continue;
  for (const line of fs.readFileSync(path.join(RES, f), "utf8").split("\n")) {
    if (line.trim()) recs.push(JSON.parse(line));
  }
}
const byVariant = new Map();
for (const r of recs) { if (!byVariant.has(r.variant)) byVariant.set(r.variant, []); byVariant.get(r.variant).push(r); }

function row(r) {
  const t = r.trace ?? {};
  const ultUs = t.updateLayoutTree?.totalUs ?? NaN;
  return {
    ultN: t.updateLayoutTree?.count, ultMs: ultUs / 1000,
    elems: (t.updateLayoutTree?.elementCounts ?? []).reduce((a, b) => a + (b ?? 0), 0),
    layN: t.layout?.count, layMs: (t.layout?.totalUs ?? 0) / 1000,
    paintMs: ((t.prePaint?.totalUs ?? 0) + (t.paint?.totalUs ?? 0)) / 1000,
    animMs: (t.animation?.bucket?.selfUs ?? 0) / 1000,
    busyMs: (t.topLevelBusyUs ?? NaN) / 1000,
    activeMs: r.harness?.activeMs,
    rsc: r.metricsDelta?.RecalcStyleCount, rsdMs: r.metricsDelta?.RecalcStyleDurationMs,
    threadMs: r.metricsDelta?.ThreadTimeMs,
    verified: r.verify?.changed === true, forced: r.harness?.forced === true, error: !!r.error,
  };
}
const fmt = (v, d = 2) => (Number.isFinite(v) ? v.toFixed(d) : "-");

const summary = new Map(); // variant -> {params, bytes, med, n, verifiedAll, minmax}
for (const [v, rs] of byVariant) {
  const ok = rs.filter((r) => !r.error);
  const rows = ok.map(row);
  const med = {};
  for (const k of Object.keys(rows[0] ?? {})) med[k] = median(rows.map((x) => x[k]));
  const mm = (k) => { const a = rows.map((x) => x[k]).filter(Number.isFinite); return a.length ? [Math.min(...a), Math.max(...a)] : [NaN, NaN]; };
  summary.set(v, { variant: v, family: rs[0].family, params: rs[0].params, bytes: rs[0].bytes, n: ok.length, errors: rs.length - ok.length,
    med, ultMM: mm("ultMs"), busyMM: mm("busyMs"), verified: rows.filter((x) => x.verified).length, forced: rows.filter((x) => x.forced).length,
    reasons: ok[0]?.trace?.invalidation?.styleRecalc?.byReason ?? {}, topSelf: ok[0]?.trace?.topSelf?.slice(0, 8) ?? [] });
}

const out = [];
const P = (s = "") => out.push(s);

function table(fam, filterFn = () => true, extraCols = []) {
  const rows = [...summary.values()].filter((s) => s.family === fam && filterFn(s));
  if (!rows.length) return rows;
  P(`| variant | MB | ULT n | ULT ms [min–max] | elems | Layout n | Layout ms | Paint ms | Anim ms | Busy ms [min–max] | RSC | RSD ms | verified | ${extraCols.map((c) => c[0]).join(" | ")} |`);
  P(`|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|${extraCols.map(() => "---:").join("|")}|`);
  for (const s of rows) {
    const m = s.med;
    P(`| ${s.variant} | ${(s.bytes / 1e6).toFixed(2)} | ${fmt(m.ultN, 0)} | ${fmt(m.ultMs)} [${fmt(s.ultMM[0])}–${fmt(s.ultMM[1])}] | ${fmt(m.elems, 0)} | ${fmt(m.layN, 0)} | ${fmt(m.layMs)} | ${fmt(m.paintMs)} | ${fmt(m.animMs)} | ${fmt(m.busyMs)} [${fmt(s.busyMM[0])}–${fmt(s.busyMM[1])}] | ${fmt(m.rsc, 0)} | ${fmt(m.rsdMs)} | ${s.verified}/${s.n}${s.forced ? ` F${s.forced}` : ""}${s.errors ? ` E${s.errors}` : ""} | ${extraCols.map((c) => c[1](s)).join(" | ")} |`);
  }
  P();
  return rows;
}

/** least squares y = a + b*x ; returns {a,b,r2} */
function fit(xs, ys) {
  const n = xs.length; if (n < 2) return null;
  const mx = xs.reduce((a, b) => a + b, 0) / n, my = ys.reduce((a, b) => a + b, 0) / n;
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < n; i++) { sxy += (xs[i] - mx) * (ys[i] - my); sxx += (xs[i] - mx) ** 2; syy += (ys[i] - my) ** 2; }
  const b = sxy / sxx, a = my - b * mx;
  const ssr = xs.reduce((acc, x, i) => acc + (ys[i] - (a + b * x)) ** 2, 0);
  return { a, b, r2: syy ? 1 - ssr / syy : 1, n };
}
/** two-variable least squares y = a + b1*x1 + b2*x2 (normal equations) */
function fit2(x1, x2, y) {
  const n = y.length; if (n < 3) return null;
  const S = (f) => f.reduce((a, b) => a + b, 0);
  const A = [[n, S(x1), S(x2)], [S(x1), S(x1.map((v) => v * v)), S(x1.map((v, i) => v * x2[i]))], [S(x2), S(x1.map((v, i) => v * x2[i])), S(x2.map((v) => v * v))]];
  const B = [S(y), S(y.map((v, i) => v * x1[i])), S(y.map((v, i) => v * x2[i]))];
  // gaussian elimination
  for (let i = 0; i < 3; i++) {
    let p = i; for (let r = i + 1; r < 3; r++) if (Math.abs(A[r][i]) > Math.abs(A[p][i])) p = r;
    [A[i], A[p]] = [A[p], A[i]]; [B[i], B[p]] = [B[p], B[i]];
    if (Math.abs(A[i][i]) < 1e-12) return null;
    for (let r = 0; r < 3; r++) if (r !== i) { const f = A[r][i] / A[i][i]; for (let c = 0; c < 3; c++) A[r][c] -= f * A[i][c]; B[r] -= f * B[i]; }
  }
  const coef = B.map((v, i) => v / A[i][i]);
  const pred = y.map((_, i) => coef[0] + coef[1] * x1[i] + coef[2] * x2[i]);
  const my = S(y) / n, ssr = S(y.map((v, i) => (v - pred[i]) ** 2)), syy = S(y.map((v) => (v - my) ** 2));
  return { a: coef[0], b1: coef[1], b2: coef[2], r2: syy ? 1 - ssr / syy : 1, n };
}

const get = (id) => summary.get(id);
const ult = (s) => s?.med?.ultMs;
const declBytes = (s) => s.params.decl_bytes_total ?? (s.params.K && s.params.M ? s.bytes : s.params.N * s.params.bytes_per_element);

P(`# M1 analysis (auto-generated by analyze.mjs from ${RES})`);
P();
P(`${recs.length} trial records, ${byVariant.size} variants. ULT = UpdateLayoutTree total ms in the mutation window (median over trials).`);
P();

// ---------------- MB2 ----------------
P(`## MB2 inheritance dirtying`);
P();
const mb2 = table("mb2", () => true, [["N*b MB", (s) => ((s.params.N * s.params.bytes_per_element) / 1e6).toFixed(2)], ["ns/B", (s) => { const base = ult(get("mb2-a-var-N0-b0")) ?? 0; const nb = s.params.N * s.params.bytes_per_element; return nb ? fmt(((ult(s) - base) * 1e6) / nb, 1) : "-"; }], ["us/elem", (s) => { const base = ult(get("mb2-a-var-N0-b0")) ?? 0; return s.params.N ? fmt(((ult(s) - base) * 1e3) / s.params.N, 1) : "-"; }]]);
if (mb2.length) {
  const a = mb2.filter((s) => s.params.variant === "a" && s.params.flavor === "var" && s.params.N > 0);
  const f = fit2(a.map((s) => s.params.N), a.map((s) => s.params.N * s.params.bytes_per_element), a.map(ult));
  if (f) P(`MB2(a,var) fit ULT ms = ${fmt(f.a, 3)} + ${fmt(f.b1 * 1e3, 2)} us/element + ${fmt(f.b2 * 1e6, 2)} ns/byte  (R²=${fmt(f.r2, 3)}, n=${f.n}) -> ${fmt(1 / (f.b2 * 1e6) * 1e3, 1)} MB/s marginal`);
  const lit = mb2.filter((s) => s.params.variant === "a" && s.params.flavor === "lit");
  const fl = fit2(lit.map((s) => s.params.N), lit.map((s) => s.params.N * s.params.bytes_per_element), lit.map(ult));
  if (fl) P(`MB2(a,lit) fit ULT ms = ${fmt(fl.a, 3)} + ${fmt(fl.b1 * 1e3, 2)} us/element + ${fmt(fl.b2 * 1e6, 2)} ns/byte  (R²=${fmt(fl.r2, 3)}, n=${fl.n})`);
  P();
  P(`Isolation ratio vs (a,var) at the same N,b:`);
  for (const v of "bcdef") for (const s of mb2.filter((x) => x.params.variant === v)) {
    const ref = get(`mb2-a-var-N${s.params.N}-b${s.params.bytes_per_element}`);
    if (ref) P(`- ${s.variant}: ULT ${fmt(ult(s))} ms vs ${fmt(ult(ref))} ms = ${fmt(ult(s) / ult(ref), 3)}x ; elems ${fmt(s.med.elems, 0)} vs ${fmt(ref.med.elems, 0)}`);
  }
  P();
}

// ---------------- MB5 ----------------
P(`## MB5 spellings (K=10000, same bytes)`);
P();
const mb5 = table("mb5", () => true, [["decl MB", (s) => (declBytes(s) / 1e6).toFixed(2)], ["ns/B", (s) => fmt((ult(s) * 1e6) / declBytes(s), 1)], ["us/decl", (s) => fmt((ult(s) * 1e3) / s.params.K, 2)], ["x ref", (s) => fmt(ult(s) / ult(get("mb5-calc-var16-K10000")), 2)]]);
P();

// ---------------- MB1 ----------------
P(`## MB1 bytes scaling`);
P();
const mb1 = table("mb1", () => true, [["ns/B", (s) => fmt((ult(s) * 1e6) / s.bytes, 1)], ["us/decl", (s) => fmt((ult(s) * 1e3) / s.params.K, 2)], ["MB/s", (s) => fmt(s.bytes / 1e6 / (ult(s) / 1e3), 1)]]);
if (mb1.length) {
  const a = mb1.filter((s) => s.params.variant === "a");
  const f = fit2(a.map((s) => s.params.K), a.map((s) => s.bytes), a.map(ult));
  if (f) P(`MB1a fit ULT ms = ${fmt(f.a, 3)} + ${fmt(f.b1 * 1e3, 3)} us/declaration + ${fmt(f.b2 * 1e6, 2)} ns/byte (R²=${fmt(f.r2, 3)}, n=${f.n}) -> marginal ${fmt(1 / (f.b2 * 1e6) * 1e3, 1)} MB/s`);
  for (const s of mb1.filter((x) => x.params.variant === "b")) {
    const ref = get(`mb1a-K${s.params.K}-M${s.params.M}`);
    if (ref) P(`- MB1b vs MB1a K=${s.params.K} M=${s.params.M}: ${fmt(ult(s))} vs ${fmt(ult(ref))} ms = ${fmt(ult(s) / ult(ref), 3)}x`);
  }
  for (const s of mb1.filter((x) => x.params.variant === "c" && x.params.mutate === "one-sibling")) {
    const ref = get(`mb1c-parent-K${s.params.K}-M${s.params.M}`);
    if (ref) P(`- MB1c sibling vs parent K=${s.params.K}: ${fmt(ult(s))} vs ${fmt(ult(ref))} ms = ${fmt(ult(s) / ult(ref), 3)}x (1/n = ${fmt(1 / s.params.siblings, 3)}); elems ${fmt(s.med.elems, 0)} vs ${fmt(ref.med.elems, 0)}`);
  }
  P();
}

// ---------------- MB3 ----------------
P(`## MB3 passes per boundary`);
P();
const mb3 = table("mb3", () => true, [["active ms", (s) => fmt(s.med.activeMs, 0)]]);
if (mb3.length) {
  for (const mech of ["style", "container", "anchor", "viewtimeline"]) {
    const s4 = get(`mb3-${mech}-S4`), s12 = get(`mb3-${mech}-S12`), s1 = get(`mb3-${mech}-S1`);
    if (s4 && s12) P(`- ${mech}: per boundary (S12−S4)/8: ULT +${fmt((s12.med.ultN - s4.med.ultN) / 8, 2)} events, +${fmt((s12.med.ultMs - s4.med.ultMs) / 8, 3)} ms; Layout +${fmt((s12.med.layN - s4.med.layN) / 8, 2)} events, +${fmt((s12.med.layMs - s4.med.layMs) / 8, 3)} ms; busy +${fmt((s12.med.busyMs - s4.med.busyMs) / 8, 3)} ms; wall(active) +${fmt((s12.med.activeMs - s4.med.activeMs) / 8, 1)} ms; verified S1/S4/S12 = ${s1?.verified}/${s4.verified}/${s12.verified}`);
  }
  P();
}

// ---------------- MB4 ----------------
P(`## MB4 retained animations`);
P();
const mb4 = table("mb4", () => true, [["vs A0", (s) => { const b = get(`mb4-none-A0-${s.params.scope}`); return b ? fmt(ult(s) - ult(b), 2) + " ms" : "-"; }], ["us/anim", (s) => { const b = get(`mb4-none-A0-${s.params.scope}`); return b && s.params.A ? fmt(((ult(s) - ult(b)) * 1e3) / s.params.A, 2) : "-"; }]]);
P();

// ---------------- verify failures ----------------
P(`## Invalid variants (verify failed / forced / errors)`);
P();
for (const s of summary.values()) if (s.verified < s.n || s.forced || s.errors) P(`- ${s.variant}: verified ${s.verified}/${s.n}, forced ${s.forced}, errors ${s.errors}`);
P();
P(`## Invalidation reasons (trial 0) and top self-time events, selected variants`);
P();
for (const id of ["mb2-a-var-N10000-b2000", "mb2-c-var-N10000-b2000", "mb2-b-var-N10000-b2000", "mb5-calc-var16-K10000", "mb5-lit-calc-K10000", "mb3-container-S12", "mb3-viewtimeline-S12", "mb4-fwd-A100000-sib"]) {
  const s = get(id); if (!s) continue;
  P(`- ${id}: reasons ${JSON.stringify(s.reasons)}; top self: ${s.topSelf.map((r) => `${r.name} ${fmt(r.selfUs / 1000, 1)}ms×${r.count}`).join(", ")}`);
}

const text = out.join("\n") + "\n";
if (MD) fs.writeFileSync(MD, text);
process.stdout.write(text);
