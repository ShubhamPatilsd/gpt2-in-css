"""F5 (2026-09-19): narrow the inherited write points of the reused runtime.

Every change is behind an environment flag (default ON) so it can be reverted
independently when building:

  F5_SCOPED_HANDSHAKE=0  keep --loop-ready/--loop-ack/--native-pass/--position inherited
  F5_SCOPED_EPOCH=0      keep the token --epoch inherited from body
  F5_SCOPED_FEEDBACK=0   keep --feedback-*/--feedback-p-*/--frozen-prompt/--token inherited
  F5_INLINE_FORWARD=0    keep the 1,538 `.loop-metric:nth-child(N){--saved:inherit}` rules
  F5_BANK_FILLED_ALIASES=0  alias all 48*capacity KV fields instead of only filled slots
  F5_BANK_LITERAL_LISTS=0   keep `transition-property:var(--fvs-*)` instead of literal lists

Mechanism (audit/2026-09-18/SYNTHESIS.md §8.1-8.2): a registered custom property
written with inherits:true restyles every non-locked descendant of the element
it is written on; inherits:false restyles one element. Readers get an explicit
republish (`inherit`, or a container-query stamp of the same value).
"""

import os
import re


def flag(name):
    return os.environ.get(name, "1") not in ("0", "false", "no", "off")


SCOPED_HANDSHAKE = flag("F5_SCOPED_HANDSHAKE")
SCOPED_EPOCH = flag("F5_SCOPED_EPOCH")
SCOPED_FEEDBACK = flag("F5_SCOPED_FEEDBACK")
INLINE_FORWARD = flag("F5_INLINE_FORWARD")
BANK_FILLED_ALIASES = flag("F5_BANK_FILLED_ALIASES")
BANK_LITERAL_LISTS = flag("F5_BANK_LITERAL_LISTS")

_PROPERTY = re.compile(r"@property (--[\w-]+)\{[^{}]+\}")


def make_private(css, names):
    """Re-register the given custom properties with inherits:false."""
    names = set(names)

    def swap(match):
        if match[1] in names:
            return match[0].replace("inherits:true", "inherits:false")
        return match[0]

    return _PROPERTY.sub(swap, css)


def make_private_prefix(css, prefixes):
    prefixes = tuple(prefixes)

    def swap(match):
        if match[1].startswith(prefixes):
            return match[0].replace("inherits:true", "inherits:false")
        return match[0]

    return _PROPERTY.sub(swap, css)


_TAG = re.compile(r"<(i|span|div|output)\b([^>]*?)>")


def tag_inline_readers(html, needle, cls, skip_class=None):
    """Add `cls` to every element whose inline style contains `needle`.

    Elements that already carry `skip_class` are left alone (they were tagged
    by an inner compiler stage with a different republish source).
    """
    count = 0

    def visit(match):
        nonlocal count
        attrs = match[2]
        style = re.search(r'style="([^"]*)"', attrs)
        if not style or needle not in style[1]:
            return match[0]
        existing = re.search(r'class="([^"]*)"', attrs)
        if existing:
            classes = existing[1].split()
            if cls in classes or (skip_class and skip_class in classes):
                return match[0]
            attrs = attrs.replace(existing[0], f'class="{existing[1]} {cls}"', 1)
        else:
            attrs = f' class="{cls}"' + attrs
        count += 1
        return f"<{match[1]}{attrs}>"

    return _TAG.sub(visit, html), count
