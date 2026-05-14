from __future__ import annotations

from typing import Final

LAGOON_ID_ALIASES: Final[dict[str, str]] = {
    "central_district_dubai": "central_hub_dubai",
}


def normalize_lagoon_id(lagoon_id: str | None) -> str:
    candidate = str(lagoon_id or "").strip()
    if not candidate:
        return ""

    return LAGOON_ID_ALIASES.get(candidate.lower(), candidate)
