"""Small shared helpers."""

from __future__ import annotations

import re

_EXTENSION_RE = re.compile(r"\.(pak|ucas|utoc|zip|exmodz?|rar)$")


def human_size(num: float) -> str:
    n = float(num or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def base_mod_key(filename: str) -> str:
    """Normalize a mod filename so different versions/weeks map to the same key.

    "laanp-WorkshopFree_v1_w253_P.pak" -> "laanp-workshopfree"
    """
    s = _EXTENSION_RE.sub("", filename.strip().lower())
    s = s.replace("_", "-").replace(" ", "-")
    tokens = [token for token in s.split("-") if token]
    marker_re = re.compile(r"^(p|pak|v?\d+(?:\.\d+)*|w\d+)$")
    while tokens and marker_re.match(tokens[-1]):
        tokens.pop()
    if tokens:
        suffix_match = re.match(r"^([a-z]+)\d+(?:\.\d+)*$", tokens[-1])
        if suffix_match:
            tokens[-1] = suffix_match.group(1)
    return "-".join(tokens)
