#!/usr/bin/env python3
"""R3L: verify the carrier widths read back by run.mjs (record.verifyAll, trial 0) against a Python model of the
same CSS expressions. After the traced mutation (odd pass -> phase 0): bank 1 holds the WARM-UP values (latched),
bank 0 shows the TRACED values live. lat-none: bank 1 reverted to 0 (no latch). Also reports the max |width delta|
between lat-769 (today) and each packed variant on identical inputs. usage: check.py <results-dir>"""
import glob, json, os, re, struct, sys
from gen import M26, MAXQ26, S26, OFF, M17, MAXQ17, S17, M34, W

res = sys.argv[1]
man = {p["id"]: p for p in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages", "manifest.json")))["pages"]}


def f32(x):
    return struct.unpack("f", struct.pack("f", x))[0]


def lu(px):  # LayoutUnit: Blink truncates a float towards zero at 1/64 px
    return int(px * 64) / 64 if px >= 0 else -int(-px * 64) / 64


def sig6(x):
    return float(f"{x:.5e}") if x else 0.0   # var() substitutes a registered <number> as 6-significant-digit text


def widths_today(vals, epoch):
    return [lu(f32(262144 + sig6(v) * 128)) for v in vals] + [lu(f32(262144 + epoch * 128))]


def widths_font(vals, epoch):
    out = []
    for v in vals:
        s = (sig6(v) + OFF) * 2
        khi = min(max(int(s // 1), 0), 16383)
        klo = min(max(int(((s - khi) * 4096) // 1), 0), 4095)
        out.append(64 * khi + klo / 64)
    return out + [lu(f32(262144 + epoch * 128))]


def q(v, s, mx):
    return min(max(round((v + OFF) * s), 0), mx)


def widths_p2(vals, epoch):
    out = []
    for j in range(W // 2):
        p = q(vals[2 * j], S26, MAXQ26) * M26 + q(vals[2 * j + 1], S26, MAXQ26)
        hi = p // M26
        out += [lu(f32(hi * 0.015625)), lu(f32((p - hi * M26) * 0.015625))]
    return out + [lu(f32(262144 + epoch * 128))]


def widths_p3(vals, epoch):
    out = []
    for j in range(W // 3):
        qs = [q(vals[3 * j + k], S17, MAXQ17) for k in range(3)]
        p = qs[0] * M34 + qs[1] * M17 + qs[2]
        hi = p // M34
        mid = (p - hi * M34) // M17
        lo = p - hi * M34 - mid * M17
        out += [lu(f32(hi * 8)), lu(f32(mid * 8)), lu(f32(lo * 8))]
    return out + [lu(f32(262144 + epoch * 128))]


MODEL = {"769": widths_today, "none": widths_today, "split8": widths_today, "p2": widths_p2, "p3": widths_p3, "font": widths_font}
parse = lambda s: float(s[:-2]) if s and s.endswith("px") else float("nan")
by_variant = {}
for path in sorted(glob.glob(os.path.join(res, "*.jsonl"))):
    for line in open(path):
        r = json.loads(line)
        if "verifyAll" not in r or r.get("error"):
            continue
        page = man[r["variant"]]
        kind = page["params"]["kind"]
        consts = page["consts"]
        va = r["verifyAll"]
        got = [parse(v) for v in va["values"]]
        # inputs: warm-up mutation wrote bank 1 (even pass), traced wrote bank 0 (odd pass)
        def inputs(m):
            pas = int(re.search(r"--pass:(\d+)", m["value"])[1]); inn = float(re.search(r"--in:([\d.]+)", m["value"])[1])
            return pas, [inn + c for c in consts]
        wpass, wvals = inputs(va["warmup"][0]); tpass, tvals = inputs(va["mutation"])
        exp1 = MODEL[kind](wvals, wpass) if kind != "none" else [0.0] * W + [lu(f32(262144 + 0 * 128))]
        exp0 = MODEL[kind](tvals, tpass)
        # DOM order: bank 1 carriers first (outer), then bank 0
        if va["count"] > 2 * (W + 1):
            # font-mode diagnostics: DOM order = P0, P1, P2 (fixed probes), then bank-1 carriers, then P3 (in bank-0 track), bank-0 carriers
            p0, p1, p2 = got[:3]; rest = got[3:]
            got = rest[: W + 1] + rest[W + 2:]; p3 = rest[W + 1]
            print(f"   probes: default-axes hi glyph {p0} px (expect 0: zero base), 'H000' 1000 x2 glyphs -> {p1} (expect 4000), 'L000' 4095 -> {p2} (expect 63.984), in-track var(--lst-0) hi glyph -> {p3}")
        assert len(got) == 2 * (W + 1), len(got)
        got1, got0 = got[: W + 1], got[W + 1:]
        exp1 = [sig6(x) for x in exp1]; exp0 = [sig6(x) for x in exp0]
        d1 = max(abs(a - b) for a, b in zip(got1, exp1)); d0 = max(abs(a - b) for a, b in zip(got0, exp0))
        n1 = sum(1 for a, b in zip(got1, exp1) if a != b); n0 = sum(1 for a, b in zip(got0, exp0) if a != b)
        by_variant[r["variant"]] = {"kind": kind, "got1": got1, "got0": got0, "wvals": wvals, "tvals": tvals, "wpass": wpass, "tpass": tpass}
        print(f"{r['variant']:16s} bank1 (latched warm-up values): max|Δ| vs model {d1:.6f} px, {n1} mismatches; "
              f"bank0 (live traced values): max|Δ| {d0:.6f} px, {n0} mismatches; sample bank1[3]={got1[3]} exp={exp1[3]}")
        if n1 or n0:
            bad = [(i, a, b) for i, (a, b) in enumerate(zip(got1, exp1)) if a != b][:5]
            print("   first bank1 mismatches (i, got, expected):", bad)
ref = by_variant.get("lat-769")
if ref:
    for v, d in by_variant.items():
        if v == "lat-769" or d["kind"] == "none":
            continue
        deltas = [abs(a - b) for a, b in zip(d["got1"][:W], ref["got1"][:W])]
        print(f"{v:16s} vs lat-769 on identical inputs (bank 1, 768 values): max |Δwidth| = {max(deltas):.6f} px "
              f"(= {max(deltas) / 128:.3e} in value units), mean {sum(deltas) / len(deltas):.6f} px, {sum(1 for x in deltas if x)} differ")
