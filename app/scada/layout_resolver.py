from __future__ import annotations

import re
from typing import Final

DEFAULT_SCADA_LAYOUT: Final[str] = "layout1"
SCADA_LAYOUT_ALIASES: Final[dict[str, str]] = {
    "layout_small": "layout3",
}
LAYOUT_ID_SANITIZER = re.compile(r"[^a-z0-9._-]+")


def normalize_scada_layout(layout_name: str | None) -> str:
    if not isinstance(layout_name, str):
        return DEFAULT_SCADA_LAYOUT

    normalized = layout_name.strip().lower()
    if not normalized:
        return DEFAULT_SCADA_LAYOUT

    normalized = normalized.replace("\\", "/").rsplit("/", 1)[-1]
    normalized = normalized.replace(".tsx", "").replace(".ts", "")
    normalized = normalized.replace(".jsx", "").replace(".js", "")
    normalized = normalized.replace(".json", "")

    normalized = SCADA_LAYOUT_ALIASES.get(normalized, normalized)
    normalized = LAYOUT_ID_SANITIZER.sub("_", normalized).strip("._-")

    return normalized or DEFAULT_SCADA_LAYOUT
