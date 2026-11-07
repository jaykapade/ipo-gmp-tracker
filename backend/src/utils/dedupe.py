"""Read-only duplicate detection across stored IPOs.

The database identity is ``normalize_name``; that catches most repeats but not
typos, abbreviations or suffixes it does not know about. This module surfaces
*possible* duplicates for review. It never merges rows automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz


@dataclass(frozen=True)
class DuplicatePair:
    """Two IPOs whose names look suspiciously similar."""

    first_id: int
    first_name: str
    second_id: int
    second_name: str
    score: float


def similarity(first: str, second: str) -> float:
    """Return a 0–100 name similarity score.

    ``token_set_ratio`` ignores word order and repeated tokens, which suits
    company names such as "Acme Industries Ltd" vs "Acme Industries".
    """

    return float(fuzz.token_set_ratio(first, second))


def find_duplicate_pairs(
    ipos: list[dict[str, Any]],
    *,
    threshold: float = 90.0,
) -> list[DuplicatePair]:
    """Return pairs at or above ``threshold``, highest score first.

    Passing the rows explicitly keeps this pure and testable; callers decide
    which rows to scan (for example, the current candidate set).
    """

    pairs: list[DuplicatePair] = []

    for index, first in enumerate(ipos):
        first_name = str(first.get("name") or "").strip()
        if not first_name:
            continue

        for second in ipos[index + 1 :]:
            second_name = str(second.get("name") or "").strip()
            if not second_name:
                continue

            score = similarity(first_name, second_name)
            if score >= threshold:
                pairs.append(
                    DuplicatePair(
                        first_id=int(first["id"]),
                        first_name=first_name,
                        second_id=int(second["id"]),
                        second_name=second_name,
                        score=round(score, 2),
                    )
                )

    return sorted(pairs, key=lambda pair: pair.score, reverse=True)
