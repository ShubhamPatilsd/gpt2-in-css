#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPERIMENT="$ROOT/experiments/gpt2-hnsw-trace"
BUILD="$EXPERIMENT/build"
SOURCE="$BUILD/hnswlib-0.8.0"
LIB="$BUILD/lib"
PATCH_FILE="$EXPERIMENT/instrumentation.patch"
UV_CACHE_ROOT="${UV_CACHE_DIR:-$HOME/.cache/uv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CXX_BIN="${CXX:-clang++}"

cached_binding="$(find "$UV_CACHE_ROOT/sdists-v8/pypi/hnswlib/0.8.0" \
  -type f -path '*/src/python_bindings/bindings.cpp' -print 2>/dev/null \
  | LC_ALL=C sort | head -n 1)"
if [[ -z "$cached_binding" ]]; then
  echo "cached hnswlib 0.8.0 sdist source was not found under $UV_CACHE_ROOT" >&2
  exit 1
fi
cached_source="$(cd "$(dirname "$cached_binding")/.." && pwd)"
if ! grep -q "Version: 0.8.0" "$cached_source/PKG-INFO"; then
  echo "cached source does not identify itself as hnswlib 0.8.0" >&2
  exit 1
fi

pybind_header="$(find "$UV_CACHE_ROOT/archive-v0" \
  -type f -path '*/pybind11/include/pybind11/pybind11.h' -print 2>/dev/null \
  | LC_ALL=C sort | head -n 1)"
if [[ -z "$pybind_header" ]]; then
  echo "cached pybind11 headers were not found; refusing to mutate the uv cache" >&2
  exit 1
fi
pybind_include="$(cd "$(dirname "$pybind_header")/.." && pwd)"

python_include="$($PYTHON_BIN -c 'import sysconfig; print(sysconfig.get_path("include"))')"
numpy_include="$($PYTHON_BIN -c 'import numpy; print(numpy.get_include())')"
extension_suffix="$($PYTHON_BIN -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')"

mkdir -p "$BUILD" "$LIB"
if [[ -e "$SOURCE" ]]; then
  rm -rf "$SOURCE"
fi
cp -R "$cached_source" "$SOURCE"
(cd "$SOURCE" && patch -p1 --forward --batch < "$PATCH_FILE")

output="$LIB/hnswlib$extension_suffix"
compile_args=(
  -O3 -DNDEBUG -std=c++14 -fPIC -fvisibility=hidden -pthread
  '-DVERSION_INFO="0.8.0-instrumented"'
  -I"$python_include" -I"$numpy_include" -I"$pybind_include"
  -I"$SOURCE/hnswlib"
  "$SOURCE/python_bindings/bindings.cpp"
  -o "$output"
)
if [[ "$(uname -s)" == "Darwin" ]]; then
  compile_args+=( -bundle -undefined dynamic_lookup )
else
  compile_args+=( -shared )
fi
"$CXX_BIN" "${compile_args[@]}"

PYTHONPATH="$LIB" "$PYTHON_BIN" - <<'PY'
import hnswlib
index = hnswlib.Index(space="ip", dim=2)
index.init_index(max_elements=1, M=2, ef_construction=2)
index.reset_metrics()
assert index.get_metrics() == {"distance_computations": 0, "hops": 0}
assert len(index.get_layer0_adjacency()) == 3
print(hnswlib.__version__)
print(hnswlib.__file__)
PY
