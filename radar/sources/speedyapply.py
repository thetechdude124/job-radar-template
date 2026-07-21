"""Fetcher for SpeedyApply README tables (2027-SWE / 2027-AI college jobs).

Rows look like:
| <a href="company"><strong>NVIDIA</strong></a> | Performance Engineer Intern - Fall 2026 | St. Louis, MO | $62/hr | <a href="APPLY_URL"><img .../></a> | 14d |

We put the year/term inside the role title so the term filter can still drop
off-cycle roles. Salary (when present) is captured into Notes.
"""

from __future__ import annotations

import re
from typing import List

import requests

from ..models import Listing, clean_text

TIMEOUT = 30

_STRONG_RE = re.compile(r"<strong>(.*?)</strong>", re.I | re.S)
_HREF_RE = re.compile(r'href="([^"]+)"')
_TAG_RE = re.compile(r"<[^>]+>")


def _strip(cell: str) -> str:
    return clean_text(_TAG_RE.sub(" ", cell))


def fetch(source_cfg: dict) -> List[Listing]:
    name = source_cfg.get("name", "speedyapply")
    url = source_cfg["url"]
    default_category = source_cfg.get("category", "Software")
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
    last_company = ""
    for line in md.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        if cells[0].lower() in ("company", "") or set(cells[0]) <= set("-: "):
            continue

        strong = _STRONG_RE.search(cells[0])
        company = _strip(strong.group(1)) if strong else _strip(cells[0])
        # SpeedyApply uses ↳ to repeat the previous company on grouped rows.
        if company in ("", "↳") and last_company:
            company = last_company
        elif company:
            last_company = company

        role = _strip(cells[1])
        location = _strip(cells[2])
        salary = _strip(cells[3]) if len(cells) >= 6 else ""
        apply_cell = cells[4] if len(cells) >= 6 else cells[3]
        href = _HREF_RE.search(apply_cell)
        if not href or not role:
            continue

        out.append(
            Listing(
                source=name,
                company=company,
                role=role,
                url=href.group(1).strip(),
                locations=[location] if location else [],
                category=default_category,
                employment="Internship",
                # Keep any year in the title so the term filter still applies.
                term=role,
                active=True,
                notes=f"Salary: {salary}" if salary and "/" in salary else "",
            )
        )
    print(f"  [ok] {name}: {len(out)} raw listings")
    return out
