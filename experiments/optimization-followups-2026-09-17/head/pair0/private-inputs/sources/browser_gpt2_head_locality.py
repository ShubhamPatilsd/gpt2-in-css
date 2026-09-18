"""Opt-in vocabulary input ownership without changing scores or candidates.

The full vocabulary and both reduction passes remain intact. The native input
bank continues to retain its 768 actual normalized values for feedback/audit.
Only their downstream representation and inheritance can change.
"""

import re

from build_gpt2_groupwise_production_q16_sixfont import font_settings

MODES = ("baseline", "settings", "private-inputs")


def transform_head(html, css, mode, owner_selector=".head-input-bank"):
    """Substitute raw inputs into an owned axis bundle; optionally privatize h.

    CSS arithmetic may still be evaluated at the two font-settings consumers.
    The distinct experiment removes inheritance of the 768 raw input numbers.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown vocabulary locality mode: {mode}")
    metadata = {
        "mode": mode,
        "vocabularyRows": html.count('class="head-row"'),
        "privateInputCount": 0,
        "fontSettingsDeclarationsReplaced": 0,
        "ownerSelector": owner_selector,
    }
    if metadata["vocabularyRows"] != 50257:
        raise ValueError("Expected the complete 50,257-row vocabulary")
    if mode == "baseline":
        return html, css, metadata

    settings = font_settings()
    declaration = f"font-variation-settings:{settings};"
    count = css.count(declaration)
    if count != 2:
        raise ValueError(f"Expected coarse and fine font settings, found {count}")
    css = css.replace(declaration, "font-variation-settings:var(--owned-head-axes);")
    # In a complete runtime the bank's transition list and assignments remain;
    # numeric reads of these exact h names must occur only in the axis bundle.
    if re.search(r"var\(--h\d+(?:[,\)])", css):
        raise ValueError("Unexpected raw head input consumer outside font settings")
    css += f"{owner_selector}{{--owned-head-axes:{settings}}}"
    metadata["fontSettingsDeclarationsReplaced"] = count
    if mode == "private-inputs":
        changed = set()

        def private(match):
            index, declarations = int(match[1]), match[2]
            if index not in range(768) or "inherits:true" not in declarations:
                raise ValueError("Unexpected vocabulary input registration")
            if index in changed:
                raise ValueError(f"Duplicate vocabulary input registration: {index}")
            changed.add(index)
            return match[0].replace("inherits:true", "inherits:false")

        # Bounded flat registration bodies; never scan huge CSS with .* loops.
        css = re.sub(r"@property --h(\d+)\{([^{}]*)\}", private, css)
        if changed != set(range(768)):
            raise ValueError(f"Expected 768 input registrations, found {len(changed)}")
        metadata["privateInputCount"] = len(changed)
    return html, css, metadata
