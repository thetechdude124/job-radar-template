"""Dedupe against what's already in the sheet."""

from __future__ import annotations

from typing import Iterable, List, Set

from .models import Listing


def split_new(listings: List[Listing], existing_keys: Set[str]) -> List[Listing]:
    return [lst for lst in listings if lst.dedupe_key not in existing_keys]
