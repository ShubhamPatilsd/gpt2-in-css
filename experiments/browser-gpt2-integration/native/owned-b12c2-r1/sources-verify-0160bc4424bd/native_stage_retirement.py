"""Compile bounded, epoch-aware CSS/SMIL capture and retirement boundaries.

Epoch selection is native CSS state supplied by the enclosing runtime. Signals
are write-once per epoch; resetting a run recreates the document. No JavaScript.
"""

from __future__ import annotations


def retire_stage(html, layer, kind, output_names, epochs=16, whole_block=False):
    stem = f"b{layer}-{kind}"
    stash = [f"--stash-{kind}-{i:03d}" for i in range(len(output_names))]
    registrations = "".join(
        f'@property {name}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for name in stash
    )
    capture = ";".join(f"{dst}:var({src})" for src, dst in zip(output_names, stash))
    restore = ";".join(f"{dst}:var({src})" for dst, src in zip(output_names, stash))
    css = (
        registrations
        + "body{container-name:runtime}"
        + "@keyframes native-handshake{from{opacity:.99}to{opacity:1}}"
        + ".native-signals{position:fixed;left:0;top:0;width:1px;height:1px}"
        + f".{stem}-store{{{capture};transition-property:none}}"
        + f".{stem}-restore{{{restore}}}"
        + f".{stem}-next{{content-visibility:hidden;contain-intrinsic-size:0px 0px}}"
    )
    signals = []
    for epoch in range(1, epochs + 1):
        key = f"{stem}-e{epoch}"
        signals.append(
            f'<g id="{key}-ready"></g><g id="{key}-ack"></g>'
            f'<g id="{key}-hold"><set attributeName="class" to="held" '
            f'begin="{key}-ready.animationend+0.001s" fill="freeze"/></g>'
            f'<g id="{key}-retire"><set attributeName="class" to="retired" '
            f'begin="{key}-ack.animationend+0.001s" fill="freeze"/></g>'
        )
        scope = ".block" if whole_block else f".{stem}"
        held = f"{scope}:has(#{key}-hold.held)"
        retired = f"{scope}:has(#{key}-retire.retired)"
        if whole_block:
            matrix = ":is(" + ",".join(f".b{layer}-{k}" for k in ("qkv", "attn", "fc", "proj")) + ")"
            sources = f"{retired} {matrix}>.scroller"
            consumers = ",".join(
                f'{retired} [class^="b{layer}-{k}-c"],{retired} .b{layer}-{k}-receipt'
                for k in ("qkv", "attn", "fc", "proj")
            )
            open_ancestors = "".join(
                f"{retired} .b{layer}-{k}-gate{{content-visibility:visible;display:block}}"
                for k in ("qkv", "attn", "fc")
            )
        else:
            sources = f"{retired}>.scroller"
            consumers = f'{retired} [class^="{stem}-c"],{retired} .{stem}-receipt'
            open_ancestors = ""
        css += (
            f"@container runtime style(--epoch:{epoch}){{"
            f"@container {stem}-receipt style(--gate-{kind}:1){{"
            f"#{key}-ready{{animation:native-handshake 1ms both}}}}"
            f"{held} .{stem}-store{{transition-property:{','.join(stash)};"
            "transition-duration:1ms;transition-timing-function:steps(1,end);transition-delay:86400s}"
            f"{held} #{key}-ack{{animation:native-handshake 1ms both}}"
            f"{sources}{{display:none}}"
            f"{sources} .metric{{view-timeline-name:none!important}}"
            f'{consumers}{{animation:none!important}}'
            + open_ancestors +
            f"{retired} .{stem}-next{{content-visibility:visible}}"
            "}"
        )
    svg = '<svg xmlns="http://www.w3.org/2000/svg" class="native-signals">' + "".join(signals) + "</svg>"
    needle = f'<div class="{stem}-gate">{{child}}</div>'
    replacement = (
        f'<div class="{stem}-store">{svg}<div class="{stem}-restore">'
        f'<div class="{stem}-next">{{child}}</div></div></div>'
    )
    if html.count(needle) != 1:
        raise ValueError(f"Missing unique generation-gated boundary: {stem}")
    return html.replace(needle, replacement, 1), css
