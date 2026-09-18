"""Experimental packed KV storage, entirely native CSS at runtime.

The expression codec retains three 16-bit codes as one unevaluated expression
in a universal-syntax registered property with a discrete delayed transition.
Avoiding a computed <number> packet preserves its integer digits. It is still
lossy KV quantization and must not silently replace the continuous cache.
The numeric12 codec is retained as a reproducible precision-failure control.
"""

WIDTH = 768


def config(mode):
    if mode in ("integer6", "integer10"):
        bits = int(mode.removeprefix("integer"))
        return bits, 30 // bits, False
    if mode == "numeric9":
        return 9, 2, False
    if mode in ("expression8", "expression10", "expression12"):
        bits = int(mode.removeprefix("expression"))
        return bits, 52 // bits, True
    if mode == "expression16":
        return 16, 3, True
    if mode in (True, "numeric12"):
        return 12, 2, False
    raise ValueError(f"Unknown packed cache mode: {mode}")


def scale_name(slot, kind, head):
    return f"--ks-{kind}{slot}-{head}"


def pair_name(slot, kind, index):
    return f"--kp-{kind}{slot}-{index:03d}"


def storage_names(slot, mode=True):
    _, lanes, _ = config(mode)
    count = 12 * ((64 + lanes - 1) // lanes)
    return [
        scale_name(slot, kind, head) for kind in ("k", "v") for head in range(12)
    ] + [pair_name(slot, kind, pair) for kind in ("k", "v") for pair in range(count)]


def registrations(slot, mode):
    _, _, expression = config(mode)
    integer = isinstance(mode, str) and mode.startswith("integer")
    return "".join(
        f'@property {name}{{syntax:"{("*" if expression else "<integer>" if integer else "<number>") if name.startswith("--kp-") else "<number>"}";inherits:true;initial-value:0}}'
        for name in storage_names(slot, mode)
    )


def declarations(slot, mode=True):
    bits, lanes, _ = config(mode)
    radix, maximum = 1 << bits, (1 << (bits - 1)) - 1
    groups = (64 + lanes - 1) // lanes
    rules = []
    for kind, offset in (("k", WIDTH), ("v", 2 * WIDTH)):
        for head in range(12):
            scale = scale_name(slot, kind, head)
            bounds = ",".join(
                f"abs(var(--qkv-{offset + head * 64 + i:03d}))" for i in range(64)
            )
            rules.append(f"{scale}:calc(max(.000000001,{bounds}) / {maximum})")
            for group in range(groups):
                codes = [
                    f"{radix**lane} * (clamp(-{maximum},round(nearest,calc(var(--qkv-{offset + head * 64 + group * lanes + lane:03d}) / var({scale})),1),{maximum}) + {maximum})"
                    for lane in range(min(lanes, 64 - group * lanes))
                ]
                rules.append(
                    f"{pair_name(slot, kind, head * groups + group)}:calc({' + '.join(codes)})"
                )
    return ";".join(rules) + ";"


def read(slot, kind, coordinate, mode=True):
    bits, lanes, _ = config(mode)
    radix, maximum = 1 << bits, (1 << (bits - 1)) - 1
    groups = (64 + lanes - 1) // lanes
    head, local = divmod(coordinate, 64)
    group, lane = divmod(local, lanes)
    packet = f"var({pair_name(slot, kind, head * groups + group)})"
    shifted = packet if lane == 0 else f"round(down,calc({packet} / {radix**lane}),1)"
    code = f"mod({shifted},{radix})"
    return f"((({code}) - {maximum}) * var({scale_name(slot, kind, head)}))"
