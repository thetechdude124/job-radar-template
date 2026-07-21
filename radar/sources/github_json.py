"""Fetcher for repos exposing the Simplify/vansh listings.json schema.

Handles both the Simplify shape (``terms`` list, ``category``) and the vansh
shape (``season`` string). Tolerates a 404 (e.g. a cycle repo that doesn't
exist yet) by returning an empty list with a warning.
"""

from __future__ import annotations

from typing import List

import requests

from ..models import Listing, clean_text

TIMEOUT = 30


def fetch(source_cfg: dict) -> List[Listing]:
    name = source_cfg.get("name", "github")
    url = source_cfg["url"]
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "job-radar"})
        if resp.status_code == 404:
            print(f"  [warn] {name}: 404 at {url} (repo/branch may not exist yet) - skipping")
            return []
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"  [warn] {name}: fetch failed ({exc}) - skipping")
        return []

    if not isinstance(data, list):
        print(f"  [warn] {name}: unexpected payload shape - skipping")
        return []

    out: List[Listing] = []
    for it in data:
        if not isinstance(it, dict):
            continue
        terms = it.get("terms")
        term = ", ".join(terms) if isinstance(terms, list) and terms else clean_text(it.get("season", ""))
        active = bool(it.get("active", True)) and bool(it.get("is_visible", True))
        out.append(
            Listing(
                source=name,
                company=clean_text(it.get("company_name", "")),
                role=clean_text(it.get("title", "")),
                url=(it.get("url") or "").strip(),
                locations=[clean_text(loc) for loc in (it.get("locations") or []) if loc],
                category=clean_text(it.get("category", "")),
                employment="Internship",
                posted=it.get("date_posted"),
                active=active,
                sponsorship=clean_text(it.get("sponsorship", "")),
                term=term,
            )
        )
    print(f"  [ok] {name}: {len(out)} raw listings")
    return out
