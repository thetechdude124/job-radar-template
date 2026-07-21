"""Normalize + in-run dedupe of raw listings from all sources."""

from __future__ import annotations

from typing import List

from .models import Listing, clean_text


def normalize(listings: List[Listing]) -> List[Listing]:
    seen = set()
    out: List[Listing] = []
    for lst in listings:
        lst.company = clean_text(lst.company)
        lst.role = clean_text(lst.role)
        if not lst.company and not lst.role:
            continue
        key = lst.dedupe_key
        if key in seen:
            continue
        seen.add(key)
        out.append(lst)
    return out
