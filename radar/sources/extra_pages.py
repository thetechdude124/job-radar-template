"""LLM-backed extractor for AI-lab career pages.

Best-effort: fetches a page, strips it to visible text, and asks an LLM to pull
out internship / fellowship / residency / research roles. Career pages are
often JS-rendered, so this can come back empty; it's off by default and never
blocks the rest of the pipeline. Requires OPENAI_API_KEY.
"""

from __future__ import annotations

import re
from typing import List

import requests

from ..llm import LLM
from ..models import Listing, clean_text

TIMEOUT = 30
_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)
_ANY_TAG_RE = re.compile(r"<[^>]+>")

_SYSTEM = (
    "You extract early-career opportunities from a company's careers page text. "
    "Return strict JSON: {\"roles\": [{\"company\": str, \"role\": str, "
    "\"url\": str, \"employment\": one of [\"Internship\", \"Full-time\", \"Event\"], "
    "\"location\": str}]}. Only include internships, new-grad roles, research "
    "fellowships/residencies, or research scientist/engineer roles. If a role's "
    "URL is not visible, use the page URL. If nothing relevant, return an empty list."
)


def _to_text(html: str) -> str:
    html = _TAG_RE.sub(" ", html)
    text = _ANY_TAG_RE.sub(" ", html)
    return clean_text(text)[:12000]


def fetch(source_cfg: dict) -> List[Listing]:
    name = source_cfg.get("name", "ai_lab_pages")
    pages = source_cfg.get("pages", []) or []
    llm = LLM(model=source_cfg.get("model"))
    if not llm.available():
        print(f"  [warn] {name}: LLM unavailable ({llm.init_error}) - skipping")
        return []

    out: List[Listing] = []
    for page_url in pages:
        try:
            resp = requests.get(page_url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0 job-radar"})
            resp.raise_for_status()
            text = _to_text(resp.text)
        except Exception as exc:
            print(f"  [warn] {name}: {page_url} fetch failed ({exc})")
            continue
        if len(text) < 50:
            print(f"  [warn] {name}: {page_url} produced little text (likely JS-rendered)")
            continue

        data = llm.complete_json(
            _SYSTEM,
            f"Page URL: {page_url}\n\nPage text:\n{text}",
            max_tokens=2000,
        )
        roles = (data or {}).get("roles", []) if isinstance(data, dict) else []
        for r in roles:
            if not isinstance(r, dict):
                continue
            loc = clean_text(r.get("location", ""))
            out.append(
                Listing(
                    source=name,
                    company=clean_text(r.get("company", "")) or _domain(page_url),
                    role=clean_text(r.get("role", "")),
                    url=(r.get("url") or page_url).strip(),
                    locations=[loc] if loc else [],
                    category="AI Lab",
                    employment=_norm_employment(r.get("employment")),
                    term="",
                    active=True,
                )
            )
    print(f"  [ok] {name}: {len(out)} raw listings")
    return out


def _domain(url: str) -> str:
    m = re.search(r"https?://([^/]+)/?", url)
    return m.group(1) if m else url


def _norm_employment(value) -> str:
    v = clean_text(value).lower()
    if "event" in v:
        return "Event"
    if "full" in v:
        return "Full-time"
    return "Internship"
