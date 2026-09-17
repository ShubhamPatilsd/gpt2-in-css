#!/usr/bin/env python3
"""Build exact alpha-bit SVG gate, adder, and connected matvec fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import struct
import zlib
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/svg-alpha-circuit-probe"
ADDER = "ripple"


def png(path: Path, rows: list[list[int]]) -> None:
    """Write lossless RGBA with black RGB and binary alpha, using stdlib only."""
    height, width = len(rows), len(rows[0])
    raw = b"".join(b"\0" + b"".join(bytes((0, 0, 0, 255 * x)) for x in row) for row in rows)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    )


class Circuit:
    def __init__(self, directory: Path, name: str, width: int, height: int):
        self.directory, self.name = directory, name
        self.width, self.height = width, height
        self.nodes: list[str] = []
        self.operations: dict[str, int] = {}
        self.inputs: list[dict[str, object]] = []
        self.maximum_live_results = 0
        self.output_nodes: list[str] = []
        self.zero = self.emit("feFlood", 'flood-color="black" flood-opacity="0"')
        self.one = self.emit("feFlood", 'flood-color="black" flood-opacity="1"')

    def emit(self, tag: str, attrs: str, bounds: tuple[int, int, int, int] | None = None) -> str:
        name = f"n{len(self.nodes)}"
        x, y, w, h = bounds or (0, 0, self.width, self.height)
        self.nodes.append(f'<{tag} {attrs} x="{x}" y="{y}" width="{w}" height="{h}" result="{name}"/>')
        self.operations[tag] = self.operations.get(tag, 0) + 1
        return name

    def image(self, label: str, variants: list[list[list[int]]], tile: bool = False) -> str:
        filenames = []
        for index, rows in enumerate(variants):
            filename = f"{self.name}-{label}-v{index}.png"
            png(self.directory / filename, rows)
            filenames.append(filename)
        rows = variants[0]
        selector = f"input-{label}"
        result = self.emit("feImage", f'id="{selector}" href="{filenames[0]}" preserveAspectRatio="none"', (0, 0, len(rows[0]), len(rows)))
        if len(variants) > 1:
            self.inputs.append({"id": selector, "files": filenames})
        if tile:
            result = self.emit("feTile", f'in="{result}"')
        return result

    def gate(self, operation: str, a: str, b: str | None = None) -> str:
        if operation == "not":
            a, b, operation = self.one, a, "out"
        return self.emit("feComposite", f'in="{a}" in2="{b}" operator="{operation}"')

    def shift(self, a: str, dx: int = 0, dy: int = 0) -> str:
        return self.emit("feOffset", f'in="{a}" dx="{dx}" dy="{dy}"')

    def crop(self, a: str, bounds: tuple[int, int, int, int]) -> str:
        return self.emit("feOffset", f'in="{a}" dx="0" dy="0"', bounds)

    def add(self, a: list[str], b: list[str], carry: str | None = None) -> list[str]:
        if ADDER == "prefix":
            original = [self.gate("xor", x, y) for x, y in zip(a, b, strict=True)]
            propagate = original[:]
            generate = [self.gate("in", x, y) for x, y in zip(a, b, strict=True)]
            stride = 1
            while stride < len(a):
                previous_p, previous_g = propagate[:], generate[:]
                for index in range(stride, len(a)):
                    generate[index] = self.gate("over", previous_g[index], self.gate("in", previous_p[index], previous_g[index - stride]))
                    propagate[index] = self.gate("in", previous_p[index], previous_p[index - stride])
                stride *= 2
            carries = [self.zero if carry is None else carry]
            for index in range(len(a) - 1):
                value = generate[index]
                if carry is not None:
                    value = self.gate("over", value, self.gate("in", propagate[index], carry))
                carries.append(value)
            return [self.gate("xor", value, incoming) for value, incoming in zip(original, carries, strict=True)]
        carry = self.zero if carry is None else carry
        result = []
        for x, y in zip(a, b, strict=True):
            different = self.gate("xor", x, y)
            result.append(self.gate("xor", different, carry))
            carry = self.gate("over", self.gate("in", x, y), self.gate("in", different, carry))
        return result

    def increment(self, a: list[str], carry: str) -> list[str]:
        if ADDER == "prefix":
            propagate = a[:]
            stride = 1
            while stride < len(a):
                previous = propagate[:]
                for index in range(stride, len(a)):
                    propagate[index] = self.gate("in", previous[index], previous[index - stride])
                stride *= 2
            return [self.gate("xor", value, carry if index == 0 else self.gate("in", propagate[index - 1], carry)) for index, value in enumerate(a)]
        result = []
        for value in a:
            result.append(self.gate("xor", value, carry))
            carry = self.gate("in", value, carry)
        return result

    def negate(self, a: list[str]) -> list[str]:
        return self.increment([self.gate("not", x) for x in a], self.one)

    def output(self, bits: list[str], row: int = 0) -> None:
        for index, value in enumerate(bits):
            cropped = self.crop(value, (0, 0, self.width, 1))
            moved = self.emit("feOffset", f'in="{cropped}" dx="0" dy="{row + index}"', (0, 0, self.width, row + len(bits)))
            self.output_nodes.append(moved)

    def write(self, expected: list[list[int]], extra: dict[str, object]) -> dict[str, object]:
        height = len(expected)
        merged = "".join(f'<feMergeNode in="{value}"/>' for value in self.output_nodes)
        self.nodes.append(f'<feMerge x="0" y="0" width="{self.width}" height="{height}" result="final-bits">{merged}</feMerge>')
        # Convert alpha to visible opaque monochrome only after the circuit ends.
        self.nodes.append(f'<feColorMatrix in="final-bits" x="0" y="0" width="{self.width}" height="{height}" type="matrix" values="0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 0 1"/>')
        html = (
            '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'; object-src \'none\'">'
            '<style>html,body{margin:0;padding:0;background:#fff}svg{display:block}</style>'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{height}">'
            f'<defs><filter id="circuit" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" x="0" y="0" width="{self.width}" height="{max(height, self.height)}" color-interpolation-filters="sRGB">'
            + "".join(self.nodes) + '</filter></defs>'
            f'<rect x="0" y="0" width="{self.width}" height="{height}" fill="black" filter="url(#circuit)"/></svg>'
        )
        if len(self.nodes) > 12000 or len(html) > 5_000_000:
            raise RuntimeError("Circuit exceeds bounded experiment graph budget")
        filename = f"{self.name}.html"
        (self.directory / filename).write_text(html)
        return {"name": self.name, "file": filename, "width": self.width, "height": height,
                "inputs": self.inputs, "expectedVariants": expected, "filterPrimitives": len(self.nodes),
                "operations": self.operations, "htmlBytes": len(html.encode()),
                "surfacePixelUpperBound": self.width * max(height, self.height) * len(self.nodes),
                "surfaceBoundNote": "Conservative area times primitive count, not measured allocation or simultaneous live surfaces",
                "sha256": hashlib.sha256(html.encode()).hexdigest(), **extra}


def bit_rows(values: list[int], bits: int) -> list[list[int]]:
    return [[(value >> bit) & 1 for value in values] for bit in range(bits)]


def stage_one(directory: Path) -> list[dict[str, object]]:
    results = []
    values = [([0, 0, 1, 1], [0, 1, 0, 1]), ([1, 0, 1, 0], [0, 1, 1, 0])]
    c = Circuit(directory, "gates", 4, 1)
    c.output_nodes = []
    a = c.image("a", [[[x for x in pair[0]]] for pair in values])
    b = c.image("b", [[[x for x in pair[1]]] for pair in values])
    outputs = [c.gate("in", a, b), c.gate("xor", a, b), c.gate("not", a), c.gate("over", a, b)]
    for _ in range(64):
        a = c.gate("not", a)
        b = c.gate("xor", c.gate("xor", b, a), a)
    outputs.extend([a, b])
    c.output(outputs)
    expected = []
    for aa, bb in values:
        expected.append([[x & y for x, y in zip(aa, bb)], [x ^ y for x, y in zip(aa, bb)],
                         [1 - x for x in aa], [x | y for x, y in zip(aa, bb)], aa, bb])
    fixture = c.write(expected[0], {"kind": "truth-tables-and-repeated-gates", "repeatDepth": 64})
    fixture["expectedVariants"] = expected
    results.append(fixture)
    for bits in (8, 16, 32):
        maximum = (1 << bits) - 1
        pairs = [(maximum, 1), ((1 << (bits - 1)) - 1, 1), (1, maximum),
                 (maximum, maximum), (0, 0), (0x55 & maximum, 0xAA & maximum),
                 ((1 << (bits - 1)), (1 << (bits - 1))), (maximum - 1, 2)]
        variants = [pairs, [(y ^ 1, x ^ 1) for x, y in reversed(pairs)]]
        c = Circuit(directory, f"add{bits}", len(pairs), 1)
        c.output_nodes = []
        a, b = [], []
        for bit in range(bits):
            a.append(c.image(f"a-{bit}", [[[(x >> bit) & 1 for x, _ in v]] for v in variants]))
            b.append(c.image(f"b-{bit}", [[[(y >> bit) & 1 for _, y in v]] for v in variants]))
        total = c.add(a, b)
        cancellation = c.add(a, c.negate(a))
        c.output(total)
        c.output(cancellation, bits)
        expected = [bit_rows([(x + y) & maximum for x, y in v], bits) + [[0] * len(pairs) for _ in range(bits)] for v in variants]
        fixture = c.write(expected[0], {"kind": "ripple-carry-and-cancellation", "bits": bits,
                                       "integerInputs": variants, "additionSemantics": f"modulo 2**{bits}"})
        fixture["expectedVariants"] = expected
        results.append(fixture)
    return results


def matvec(c: Circuit, inputs: list[str], weights: list[list[int]], axis: str, label: str, width: int) -> list[str]:
    size = len(weights)
    inputs = inputs + [inputs[-1]] * (width - len(inputs))
    # Weight image has output on rows for horizontal reduction, columns for vertical.
    matrix = weights if axis == "x" else [list(x) for x in zip(*weights, strict=True)]
    nonzero = c.image(f"{label}-nonzero", [[[int(x != 0) for x in row] for row in matrix]])
    negative = c.image(f"{label}-negative", [[[int(x < 0) for x in row] for row in matrix]])
    # Conditional two's-complement negation, then mask exact zero weights.
    products = c.increment([c.gate("xor", x, negative) for x in inputs], negative)
    products = [c.gate("in", x, nonzero) for x in products]
    stride = 1
    while stride < size:
        other = [c.shift(x, dx=-stride if axis == "x" else 0, dy=-stride if axis == "y" else 0) for x in products]
        products = c.add(products, other)
        stride *= 2
    return products


def stage_two(directory: Path, size: int) -> list[dict[str, object]]:
    rng = random.Random(9314 + size)
    first = [[rng.choice((-1, 0, 1)) for _ in range(size)] for _ in range(size)]
    second = [[rng.choice((-1, 0, 1)) for _ in range(size)] for _ in range(size)]
    # Explicit difficult cancellation and all-negative rows, in addition to random dense rows.
    first[0] = [1 if i % 2 == 0 else -1 for i in range(size)]
    first[1] = [-1] * size
    second[0] = [1 if i % 2 == 0 else -1 for i in range(size)]
    values = [[rng.randint(-127, 127) for _ in range(size)], [127 if i % 2 == 0 else -127 for i in range(size)]]
    input_bits = 8
    width_one = input_bits + math.ceil(math.log2(size)) + 1
    width_two = width_one + math.ceil(math.log2(size)) + 1
    c = Circuit(directory, f"matvec{size}", size, size)
    c.output_nodes = []
    inputs = [c.image(f"x-{bit}", [[[(x >> bit) & 1 for x in v]] for v in values], tile=True) for bit in range(input_bits)]
    first_outputs = matvec(c, inputs, first, "x", "first", width_one)
    positive = c.gate("not", first_outputs[-1])
    relu = [c.gate("in", value, positive) for value in first_outputs]
    columns = [c.crop(value, (0, 0, 1, size)) for value in relu]
    second_inputs = [c.emit("feTile", f'in="{value}"') for value in columns]
    outputs = matvec(c, second_inputs, second, "y", "second", width_two)
    c.output(outputs)
    expected, stage_values = [], []
    for v in values:
        y = [sum(x * w for x, w in zip(v, row, strict=True)) for row in first]
        activated = [max(0, x) for x in y]
        z = [sum(x * w for x, w in zip(activated, row, strict=True)) for row in second]
        expected.append(bit_rows(z, width_two))
        stage_values.append({"input": v, "firstMatvec": y, "relu": activated, "secondMatvec": z})
    fixture = c.write(expected[0], {"kind": "signed-matvec-relu-matvec", "size": size, "inputBits": input_bits,
                                  "firstAccumulatorBits": width_one, "outputBits": width_two,
                                  "weights": [first, second], "integerReference": stage_values,
                                  "weightDomain": [-1, 0, 1], "nonlinearity": "ReLU, not GPT-2 GELU",
                                  "overflow": "None in reference; accumulator bounds cover all signed 8-bit inputs"})
    fixture["expectedVariants"] = expected
    return [fixture]


def audit_fixture(directory: Path, fixture: dict[str, object]) -> dict[str, object]:
    """Independently interpret the emitted, bounded alpha graph in exact integers."""
    html = (directory / str(fixture["file"])).read_text()
    tree = ET.fromstring(html[html.index("<svg"):])
    filter_element = tree.find(".//{http://www.w3.org/2000/svg}filter")
    assert filter_element is not None
    width, height = int(filter_element.attrib["width"]), int(filter_element.attrib["height"])
    variants = []
    for variant, expected in enumerate(fixture["expectedVariants"]):
        assets = {item["id"]: item["files"][variant] for item in fixture["inputs"]}
        images: dict[str, list[list[int]]] = {}
        regions: dict[str, tuple[int, int, int, int]] = {}
        final = None
        for node in filter_element:
            kind = node.tag.rsplit("}", 1)[-1]
            attrs = node.attrib
            x0, y0, w, h = (int(attrs[key]) for key in ("x", "y", "width", "height"))
            output = [[0] * width for _ in range(height)]
            source = images.get(attrs.get("in", ""))
            second = images.get(attrs.get("in2", ""))
            if kind == "feImage":
                content = (directory / assets.get(attrs.get("id"), attrs["href"])).read_bytes()
                at, compressed = 8, b""
                while at < len(content):
                    length = struct.unpack(">I", content[at:at + 4])[0]
                    chunk = content[at + 4:at + 8]
                    if chunk == b"IHDR":
                        iw, ih = struct.unpack(">II", content[at + 8:at + 16])
                    elif chunk == b"IDAT":
                        compressed += content[at + 8:at + 8 + length]
                    at += 12 + length
                raw = zlib.decompress(compressed)
                assert (iw, ih) == (w, h)
                pixels = [[raw[y * (1 + 4 * iw) + 1 + 4 * x + 3] // 255 for x in range(iw)] for y in range(ih)]
            for y in range(y0, min(height, y0 + h)):
                for x in range(x0, min(width, x0 + w)):
                    if kind == "feFlood":
                        value = int(attrs["flood-opacity"])
                    elif kind == "feImage":
                        value = pixels[y - y0][x - x0]
                    elif kind == "feComposite":
                        assert source is not None and second is not None
                        a, b = source[y][x], second[y][x]
                        value = {"in": a & b, "out": a & (1 - b), "xor": a ^ b, "over": a | b}[attrs["operator"]]
                    elif kind == "feOffset":
                        assert source is not None
                        sx, sy = x - int(attrs["dx"]), y - int(attrs["dy"])
                        value = source[sy][sx] if 0 <= sx < width and 0 <= sy < height else 0
                    elif kind == "feTile":
                        assert source is not None
                        tx, ty, tw, th = regions[attrs["in"]]
                        value = source[ty + (y - ty) % th][tx + (x - tx) % tw]
                    elif kind == "feMerge":
                        value = max(images[child.attrib["in"]][y][x] for child in node)
                    elif kind == "feColorMatrix":
                        assert source is not None
                        value = source[y][x]
                    else:
                        raise ValueError(f"Unsupported audit operation {kind}")
                    output[y][x] = value
            if "result" in attrs:
                images[attrs["result"]] = output
                regions[attrs["result"]] = (x0, y0, w, h)
            else:
                final = output
        assert final is not None
        mismatches = [{"x": x, "y": y, "actual": final[y][x], "expected": bit} for y, row in enumerate(expected) for x, bit in enumerate(row) if final[y][x] != bit]
        variants.append({"variant": variant, "passed": not mismatches, "mismatches": len(mismatches), "sampleErrors": mismatches[:20]})
    return {"name": fixture["name"], "passed": all(x["passed"] for x in variants), "variants": variants,
            "scope": "Independent exact-bit interpretation of generated primitive graph, image alpha, bounds and offsets; not a browser execution or physical-allocation audit"}


def main() -> None:
    global ADDER
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--size", type=int, choices=(2, 4, 8, 16, 32, 64))
    parser.add_argument("--adder", choices=("ripple", "prefix"), default="ripple")
    parser.add_argument("--audit-existing", action="store_true")
    args = parser.parse_args()
    ADDER = args.adder
    if not args.label.replace("-", "").replace("_", "").isalnum():
        parser.error("Label must contain letters, numbers, dashes or underscores")
    directory = OUT / args.label
    if args.audit_existing:
        reference = json.loads((directory / "reference.json").read_text())
        report = {"fixtures": [audit_fixture(directory, fixture) for fixture in reference["fixtures"]]}
        report["passed"] = all(x["passed"] for x in report["fixtures"])
        (directory / "offline-graph-audit.json").write_text(json.dumps(report, indent=2) + "\n")
        (directory / "executed-audit-builder.py").write_bytes(Path(__file__).read_bytes())
        print(json.dumps(report))
        return
    directory.mkdir(parents=True, exist_ok=False)
    fixtures = stage_two(directory, args.size) if args.size else stage_one(directory)
    sources = {}
    for filename in ("build_svg_alpha_circuit_probe.py", "test_svg_alpha_circuit_probe.mjs"):
        path = ROOT / "tools" / filename
        if path.exists():
            data = path.read_bytes()
            (directory / filename).write_bytes(data)
            sources[filename] = hashlib.sha256(data).hexdigest()
    reference = {"fixtures": fixtures, "sources": sources, "noPageJavaScript": True,
                 "adder": ADDER,
                 "noRuntimeFontCanvasOrShader": True, "buildCommand": __import__("sys").argv,
                 "boundaries": "Every gate is an explicitly named two-input compositing primitive; physical intermediate allocation/fusion is not instrumented"}
    (directory / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({"directory": str(directory), "fixtures": [{"name": x["name"], "primitives": x["filterPrimitives"], "htmlBytes": x["htmlBytes"]} for x in fixtures]}))


if __name__ == "__main__":
    main()
