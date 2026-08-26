#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib>=3.9,<4"]
# ///
"""Plot saved scaling evidence; --data-only needs only the standard library.

The figure compares no end-to-end token timings. Data collection verifies that
each plotted configuration passed, uses the same recorded sources/browser, and
has the expected pair of independent process repetitions. Every input file is
identified by SHA-256 in plots/scaling-data.json.
"""

import argparse
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "experiments/browser-gpt2-scaling"
VARIANTS = ("baseline", "widths", "empty", "lean")
COLORS = {
    "baseline": "#334155",
    "widths": "#2563eb",
    "empty": "#d97706",
    "lean": "#0d9488",
}
LABELS = {
    "baseline": "Baseline",
    "widths": "Rendered-width reuse",
    "empty": "Empty-slot gating",
    "lean": "Lean combination",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


ENVIRONMENT_KEYS = ("pythonVersion", "platform", "packages", "fixtureSeed")


def source_identity(report, *, require_environment=False):
    sources = {
        k: v
        for k, v in report.get("sourceHashes", {}).items()
        if Path(k).name not in {"attention.css", "index.html", "style.css"}
    }
    browser = report.get("browser", {})
    environment = {k: report.get(k) for k in ENVIRONMENT_KEYS}
    if require_environment and any(v is None for v in environment.values()):
        raise ValueError(
            "Attention result lacks required top-level environment metadata"
        )
    return json.dumps(
        {
            "sources": sources,
            "browser": browser.get("product"),
            "revision": browser.get("revision"),
            "arguments": report.get("browserArguments"),
            "environment": environment,
        },
        sort_keys=True,
    )


def aggregate(series):
    if not series or len({len(s) for s in series}) != 1:
        raise ValueError("Expected equal-length repeat series")
    columns = list(zip(*series, strict=True))
    return {
        "median": [statistics.median(v) for v in columns],
        "minimum": [min(v) for v in columns],
        "maximum": [max(v) for v in columns],
    }


def load_data(root):
    sources = []

    def read(path):
        report = json.loads(path.read_text())
        if report.get("passed") is not True:
            raise ValueError(f"Refusing to plot a failed/incomplete case: {path}")
        sources.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha(path),
                "sourceHashes": report.get("sourceHashes", {}),
                "browser": report.get("browser", {}),
                "recordedEnvironment": {k: report.get(k) for k in ENVIRONMENT_KEYS},
            }
        )
        return report

    attention, identities = [], set()
    positions = list(range(2, 33))
    for variant in VARIANTS:
        repeats = []
        for repeat in (0, 1):
            path = root / "runs" / f"{variant}-c32-l1-p32-r{repeat}" / "results.json"
            report = read(path)
            if (
                report["variant"],
                report["capacity"],
                report["positions"],
                report["layers"],
                report["repeat"],
            ) != (variant, 32, 32, 1, repeat):
                raise ValueError(f"Unexpected attention design: {path}")
            identities.add(source_identity(report, require_environment=True))
            rows = [r for r in report["samples"][1:] if r["kind"] == "append"]
            if [r["position"] for r in rows] != positions or not all(
                r["passed"] for r in rows
            ):
                raise ValueError(f"Missing/failed warm append positions: {path}")
            repeats.append(
                {
                    "repeat": repeat,
                    "wallMilliseconds": [r["milliseconds"] for r in rows],
                }
            )
        attention.append(
            {
                "variant": variant,
                "label": LABELS[variant],
                "positions": positions,
                "processes": repeats,
                **aggregate([r["wallMilliseconds"] for r in repeats]),
            }
        )
    if len(identities) != 1:
        raise ValueError(
            "Attention comparison mixes recorded source/browser/environment revisions"
        )

    locality, identities, active_inputs = [], set(), set()
    heads = [1, 4, 12]
    for mode in ("broadcast", "local"):
        repeats = []
        for repeat in (0, 1):
            values = []
            for count in heads:
                path = (
                    root
                    / "locality"
                    / f"{mode}-h{count}-s8-n0-r{repeat}"
                    / "results.json"
                )
                report = read(path)
                if (
                    report["heads"],
                    report["slots"],
                    report["spectatorsPerHead"],
                    report["mode"],
                    report["repeat"],
                ) != (count, 8, 0, mode, repeat):
                    raise ValueError(f"Unexpected locality design: {path}")
                identities.add(source_identity(report))
                active_inputs.add(report["activeInputHash"])
                if len(report["samples"]) != 4:
                    raise ValueError(f"Expected four query mutations: {path}")
                values.append(
                    statistics.mean(
                        r["rendererDelta"]["RecalcStyleDuration"] * 1000
                        for r in report["samples"]
                    )
                )
            repeats.append({"repeat": repeat, "meanStyleMilliseconds": values})
        locality.append(
            {
                "mode": mode,
                "heads": heads,
                "repeatGroups": repeats,
                **aggregate([r["meanStyleMilliseconds"] for r in repeats]),
            }
        )
    if len(identities) != 1 or len(active_inputs) != 1:
        raise ValueError(
            "Locality comparison mixes recorded revisions or changes the active input"
        )
    return {
        "schemaVersion": 1,
        "scope": "Two separate externally driven component experiments; no end-to-end token throughput",
        "statistics": "Median and min/max across two independent processes per condition; locality first averages four mutations within each process; no confidence interval",
        "environmentCoverage": {
            "attention": "All four top-level environment keys are required, non-null and compared across all eight cases.",
            "locality": "Earlier locality records lack Python/platform/package/fixture-seed metadata; matching source hashes, browser/version/arguments and active-input hash are checked. Missing environment metadata is not evidence of environment identity.",
        },
        "attentionDesign": {
            "capacity": 32,
            "layers": 1,
            "positions": positions,
            "operation": "append",
            "initialSampleExcluded": True,
        },
        "localityDesign": {
            "heads": heads,
            "slotsPerHead": 8,
            "spectatorsPerHead": 0,
            "operation": "change head-0 query and tick",
        },
        "attention": attention,
        "locality": locality,
        "sources": sources,
        "scriptSha256": sha(Path(__file__)),
    }


def render(data, output):
    # Imported only for rendering so data extraction never installs/imports a
    # plotting stack during an active benchmark.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "axes.labelsize": 11,
            "axes.edgecolor": "#cbd5e1",
            "axes.labelcolor": "#334155",
            "text.color": "#0f172a",
            "xtick.color": "#475569",
            "ytick.color": "#475569",
            "svg.fonttype": "none",
        }
    )
    figure, (left, right) = plt.subplots(
        1, 2, figsize=(13.8, 6.4), gridspec_kw={"width_ratios": [1.6, 1]}
    )
    figure.patch.set_facecolor("#ffffff")
    figure.suptitle(
        "Browser scaling: two controlled component experiments",
        fontsize=19,
        fontweight="bold",
        x=0.065,
        y=0.97,
        ha="left",
    )
    figure.text(
        0.065,
        0.915,
        "Lines show medians; bands and error bars show the range across two independent processes.",
        fontsize=11,
        color="#475569",
    )
    for axis in (left, right):
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", color="#e2e8f0", linewidth=0.8)
        axis.set_axisbelow(True)
        axis.tick_params(length=0, pad=7)
    for series in data["attention"]:
        color = COLORS[series["variant"]]
        style = "--" if series["variant"] == "empty" else "-"
        left.fill_between(
            series["positions"],
            series["minimum"],
            series["maximum"],
            color=color,
            alpha=0.14,
            linewidth=0,
        )
        left.plot(
            series["positions"],
            series["median"],
            color=color,
            linewidth=2.2,
            linestyle=style,
            label=series["label"],
        )
    left.set_title("A  Attention append cost", loc="left", pad=32)
    left.text(
        0,
        1.025,
        "32 allocated slots · one layer · new QKV for every head",
        transform=left.transAxes,
        fontsize=10,
        color="#64748b",
    )
    left.set_xlabel("Populated cache positions", labelpad=10)
    left.set_ylabel("Observed component update (ms)", labelpad=10)
    left.set_xticks([2, 8, 16, 24, 32])
    left.set_xlim(1, 33)
    left.set_ylim(0, 1600)
    left.set_yticks([0, 400, 800, 1200, 1600])
    left.legend(loc="upper left", frameon=False, fontsize=10)
    for series in data["locality"]:
        color = "#334155" if series["mode"] == "broadcast" else "#0d9488"
        errors = [
            [m - lo for m, lo in zip(series["median"], series["minimum"], strict=True)],
            [hi - m for hi, m in zip(series["maximum"], series["median"], strict=True)],
        ]
        right.errorbar(
            series["heads"],
            series["median"],
            yerr=errors,
            color=color,
            linewidth=2.2,
            marker="o",
            markersize=6,
            capsize=4,
            label="Update on body"
            if series["mode"] == "broadcast"
            else "Update inside head 0",
        )
    right.set_title("B  Collateral style work", loc="left", pad=32)
    right.text(
        0,
        1.025,
        "8 static KV positions per head · no spectator nodes",
        transform=right.transAxes,
        fontsize=10,
        color="#64748b",
    )
    right.set_xlabel("Total attention heads", labelpad=10)
    right.set_ylabel("Renderer style time (ms)", labelpad=10)
    right.set_xticks([1, 4, 12])
    right.set_xlim(0.4, 12.7)
    right.set_ylim(0, 20)
    right.set_yticks([0, 5, 10, 15, 20])
    right.legend(loc="upper left", frameon=False, fontsize=10)
    right.annotate(
        f"{data['locality'][0]['median'][-1]:.2f} ms",
        (12, data["locality"][0]["median"][-1]),
        xytext=(-7, 11),
        textcoords="offset points",
        ha="right",
        fontsize=11,
        fontweight="bold",
        color="#334155",
    )
    right.annotate(
        f"{data['locality'][1]['median'][-1]:.2f} ms",
        (12, data["locality"][1]["median"][-1]),
        xytext=(-7, 10),
        textcoords="offset points",
        ha="right",
        fontsize=11,
        fontweight="bold",
        color="#0d9488",
    )
    figure.subplots_adjust(left=0.065, right=0.985, top=0.78, bottom=0.23, wspace=0.31)
    figure.text(
        0.065,
        0.115,
        "A: wall time includes CDP observation and settling; the first sample is excluded. B: each process mean covers four head-0 query updates.",
        fontsize=9.5,
        color="#475569",
    )
    figure.text(
        0.065,
        0.072,
        "Different workloads and metrics: these plots do not measure generated-token throughput. Ranges are descriptive, not confidence intervals.",
        fontsize=9.5,
        color="#475569",
    )
    figure.text(
        0.065,
        0.03,
        "Chromium 153.0.8010.48 · saved inputs, scripts and source hashes: plots/scaling-data.json",
        fontsize=9,
        color="#64748b",
    )
    png, svg = (
        output / "scaling-investigation.png",
        output / "scaling-investigation.svg",
    )
    figure.savefig(png, dpi=180, facecolor="white")
    figure.savefig(svg, facecolor="white", metadata={"Date": None})
    plt.close(figure)
    return {
        "matplotlibVersion": matplotlib.__version__,
        "outputs": {p.name: sha(p) for p in (png, svg)},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT)
    parser.add_argument("--data-only", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    output = root / "plots"
    output.mkdir(parents=True, exist_ok=True)
    data = load_data(root)
    path = output / "scaling-data.json"
    path.write_text(json.dumps(data, indent=2) + "\n")
    if args.data_only:
        print(
            f"Saved checked plot data from {len(data['sources'])} result files to {path}"
        )
        return
    result = render(data, output)
    result["dataSha256"] = sha(path)
    result["scriptSha256"] = sha(Path(__file__))
    (output / "render-manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
