"""Read-only decoding of already-captured CSS cache values after measurement.

This is an independent evaluator, never browser inference or an input producer.
Use a restricted AST interpreter, not eval(), on the serialized CSS arithmetic.
"""

import ast
import math
import operator
import re

from browser_gpt2_cache import config, pair_name, scale_name


def expected_integer_packets(properties, slot, codec):
    """Independent retention oracle from the observed live bank inputs.

    The active packet's text is rounded by CSS serialization; it is not a
    valid retention oracle. No values computed here enter the browser.
    """
    bits, lanes, _ = config(codec)
    maximum, radix = 2 ** (bits - 1) - 1, 2**bits
    groups = (64 + lanes - 1) // lanes
    result = {}
    for kind, offset in (("k", 768), ("v", 1536)):
        for head in range(12):
            scale = scale_name(slot, kind, head)
            result[scale] = float(properties[scale])
            for group in range(groups):
                codes = [
                    max(
                        -maximum,
                        min(
                            maximum,
                            math.floor(
                                float(
                                    properties[
                                        f"--qkv-{offset + head * 64 + group * lanes + lane:03d}"
                                    ]
                                )
                                / result[scale]
                                + 0.5
                            ),
                        ),
                    )
                    + maximum
                    for lane in range(min(lanes, 64 - group * lanes))
                ]
                result[pair_name(slot, kind, head * groups + group)] = sum(
                    c * radix**lane for lane, c in enumerate(codes)
                )
    return result


def css_number(text):
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
    }

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return (-1 if isinstance(node.op, ast.USub) else 1) * visit(node.operand)
        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            return operators[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.Name) and node.id in (
            "nearest",
            "down",
            "up",
            "tozero",
        ):
            return node.id
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and not node.keywords
        ):
            values = [visit(n) for n in node.args]
            name = node.func.id
            if name == "calc" and len(values) == 1:
                return values[0]
            if name == "clamp" and len(values) == 3:
                return max(values[0], min(values[1], values[2]))
            if name in ("min", "max"):
                return (min if name == "min" else max)(values)
            if name == "abs" and len(values) == 1:
                return abs(values[0])
            if name == "mod" and len(values) == 2:
                return values[0] % values[1]
            if name == "round" and len(values) == 3:
                mode, value, interval = values
                rounding = {
                    "nearest": lambda x: math.floor(x + 0.5),
                    "down": math.floor,
                    "up": math.ceil,
                    "tozero": math.trunc,
                }
                return rounding[mode](value / interval) * interval
        raise ValueError(f"Unsupported CSS arithmetic: {ast.dump(node)}")

    result = float(visit(ast.parse(text.strip(), mode="eval").body))
    if not math.isfinite(result):
        raise ValueError("Non-finite captured CSS value")
    return result


def decode_cache(properties, slot, codec, active=False):
    if codec == "font-vector":
        values = []
        for kind in ("k", "v"):
            for head in range(12):
                settings = properties[f"--fc-{kind}-{slot}-{head}"]
                fields = re.split(r',\s*(?="[KV][0-9A-F]{3}")', settings)
                if len(fields) != 64:
                    raise ValueError("Incomplete captured font vector")
                scale = css_number(properties[f"--fc-{kind}s-{slot}-{head}"])
                for i, field in enumerate(fields):
                    tag, value = field.strip().split(" ", 1)
                    allowed = {f'"K{i:03d}"'}
                    if kind == "v":
                        allowed.add(f'"V{slot * 64 + i:03X}"')
                    if tag not in allowed:
                        raise ValueError("Out-of-order captured font vector")
                    values.append(css_number(value) * scale)
        return values
    if active and codec.startswith("integer"):
        # Active integer packets deliberately bypass retained storage. Reading
        # their rounded serialized packet would assess data inference never used.
        return [float(properties[f"--qkv-{i:03d}"]) for i in range(768, 2304)]
    if codec == "scalar":
        return [
            float(properties[f"--kv-{kind}{slot}-{i:03d}"])
            for kind in ("k", "v")
            for i in range(768)
        ]
    bits, lanes, _ = config(codec)
    radix, maximum = 1 << bits, (1 << (bits - 1)) - 1
    groups = (64 + lanes - 1) // lanes
    packets = {}
    result = []
    for kind in ("k", "v"):
        for i in range(768):
            head, local = divmod(i, 64)
            group, lane = divmod(local, lanes)
            name = pair_name(slot, kind, head * groups + group)
            if name not in packets:
                packets[name] = css_number(properties[name])
            code = math.floor(packets[name] / radix**lane) % radix
            result.append(
                (code - maximum) * float(properties[scale_name(slot, kind, head)])
            )
    return result
