Validated bundle recipe
=======================

The preserved 8-token and 32-token bundles are the historical complete-run references. Their manifests, HTML, CSS, transitive static assets and numerical evidence are pinned in `validated-bundles.json`. This makes the actual evaluated bytes identifiable; it does not imply that today's compiler recreates them.

From the repository root, verify before launching:

```sh
python3 tools/check_validated_browser_gpt2.py --capacity 8
python3 tools/launch_browser_gpt2.py --directory experiments/browser-gpt2/demo-font-vector-twelve --heap-growth-percent 10
```

For the preserved full-causal 32-slot bundle:

```sh
python3 tools/check_validated_browser_gpt2.py --capacity 32
python3 tools/launch_browser_gpt2.py --directory experiments/browser-gpt2/demo-font-vector-context32 --heap-growth-percent 10
```

These launch static assets in a separate stock Chromium profile. The user clicks Run. Serving files does not perform inference or provide token ticks. Do not run `--freeze` again over changed evidence; the checker deliberately refuses to overwrite its manifest.

A current-source build needs explicit flags:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
python3 tools/run_unconventional_isolated.py --label current-source-build -- \
uv run --with numpy --with fonttools --with pillow --with brotli \
python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 32 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output experiments/browser-gpt2/NEW-UNUSED-DIRECTORY
```

Choose a new output directory. Compiler defaults alone do not denote the validated reusable graph. Current source uses the v2 font-vector operators; the historical complete bundles use v1. The follow-up native comparisons therefore compile a fresh current-source baseline and candidates with the same source and assets. They do not compare a new candidate's time directly with a historical v1 run.

Follow-up candidates are compiled by `tools/probe_audit_native_prefix.py compile` using scoped compiler patches. Their generated artifacts and patches are recorded under `native/fixtures/*/audit-provenance.json`. That command also requires a fresh output directory and preserves existing experiments. No production default is changed by the probes.

The prefix observer keeps 12 layers, 32 allocated slots and the 32-token native generation limit. It closes the browser after observing two retained outputs. The observer supplies no tokens or intermediate values. Post-timing checks independently score the retained head input and compare both positions of all 12 K/V banks against the q9 reference. A two-token prefix cannot establish full-occupancy speed or correctness over a complete 32-token run.
