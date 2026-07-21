"""Fetcher for the Northwestern FinTech quant README.

Structure (per firm):

    ## Firm Name
    **Website**: [Firm](url)
    **Locations**: NYC
    **Notes**: ...
    |Role|Links|
    |-------|-------|
    |SWE|[✅ ](https://...)|
    |QR|[✅ Algo Dev](https://...)   [✅ ](https://...)|

Each table row can contain multiple links; we emit one Listing per link.
"""

from __future__ import annotations

import re
from typing import List

import requests

from ..models import Listing, clean_text

TIMEOUT = 30

_SKIP_SECTIONS = {
    "summer 2027 quant internships",
    "summer 2026 quant internships",
    "contributing",
    "using this repository",
    "table of contents",
    "legend",
}

_LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)]+)\)")
_LOC_RE = re.compile(r"\*\*Locations?\*\*:\s*(.+)")
_NOTES_RE = re.compile(r"\*\*Notes?\*\*:\s*(.+)")
_ROW_RE = re.compile(r"^\|([^|]+)\|(.+?)\|\s*$", re.M)


def _clean_role_label(raw: str) -> str:
    # role label cells look like "✅ Algo Dev" or just "✅"
    lbl = raw.replace("✅", "").replace("🔒", "").strip()
    return clean_text(lbl)


def fetch(source_cfg: dict) -> List[Listing]:
    name = source_cfg.get("name", "nufintech_quant")
    url = source_cfg["url"]
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "job-radar"})
        if resp.status_code == 404:
            print(f"  [warn] {name}: 404 at {url} - skipping")
            return []
        resp.raise_for_status()
        md = resp.text
    except Exception as exc:
        print(f"  [warn] {name}: fetch failed ({exc}) - skipping")
        return []

    out: List[Listing] = []
    # Split into per-firm sections on level-2 headings.
    sections = re.split(r"(?m)^##\s+", md)
    for section in sections:
        lines = section.splitlines()
        if not lines:
            continue
        firm = clean_text(lines[0])
        if not firm or firm.lower() in _SKIP_SECTIONS:
            continue

        loc_match = _LOC_RE.search(section)
        locations = []
        if loc_match:
            locations = [clean_text(p) for p in re.split(r"[,/]", loc_match.group(1)) if clean_text(p)]

        notes_match = _NOTES_RE.search(section)
        firm_note = clean_text(notes_match.group(1)) if notes_match else ""

        for row in _ROW_RE.finditer(section):
            role_cell = row.group(1).strip()
            links_cell = row.group(2)
            if role_cell.lower() in ("role", "links") or set(role_cell) <= set("- "):
                continue  # header / separator row
            found = _LINK_RE.findall(links_cell)
            if not found:
                continue
            for link_label, link_url in found:
                sub = _clean_role_label(link_label)
                role_name = f"{role_cell} - {sub}" if sub else role_cell
                out.append(
                    Listing(
                        source=name,
                        company=firm,
                        role=f"{role_name} (Quant)",
                        url=link_url.strip(),
                        locations=locations,
                        category="Quantitative Finance",
                        employment="Internship",
                        term="Summer 2027",
                        active=True,
                        notes=firm_note,
                    )
                )

    print(f"  [ok] {name}: {len(out)} raw listings")
    return out
