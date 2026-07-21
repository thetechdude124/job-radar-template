"""Unified data model shared across every stage of the pipeline."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

# Column order for the Google Sheet / CSV. The pipeline never reorders or
# rewrites the user-owned Status column.
HEADERS = [
    "Date Added",
    "Source",
    "Company",
    "Role",
    "Role Type",
    "Employment",
    "Location",
    "Work Auth",
    "Priority",
    "Posted",
    "Link",
    "Relevance",
    "Status",
    "Notes",
]


def canonicalize_url(url: str) -> str:
    """Normalize a URL for dedupe: strip query/fragment, trailing slash, case."""
    if not url:
        return ""
    u = url.strip()
    u = u.split("#", 1)[0]
    u = u.split("?", 1)[0]
    u = u.rstrip("/")
    return u.lower()


def dedupe_key_for(url: str, company: str = "", role: str = "") -> str:
    """Stable key used to detect whether a listing is already in the sheet."""
    base = canonicalize_url(url)
    if not base:
        base = f"{company.strip().lower()}|{role.strip().lower()}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


@dataclass
class Listing:
    source: str
    company: str
    role: str
    url: str = ""
    locations: List[str] = field(default_factory=list)
    category: str = ""            # raw category/label from the source
    employment: str = "Internship"  # Internship | Full-time | Event
    posted: Optional[int] = None    # unix timestamp
    active: bool = True
    sponsorship: str = ""           # raw sponsorship string from source, if any
    term: str = ""

    # Populated by the filter agent:
    role_type: str = ""
    priority: str = "Normal"
    relevance: str = ""
    work_auth: str = ""
    notes: str = ""

    @property
    def canonical_url(self) -> str:
        return canonicalize_url(self.url)

    @property
    def dedupe_key(self) -> str:
        return dedupe_key_for(self.url, self.company, self.role)

    @property
    def location_str(self) -> str:
        return "; ".join(self.locations) if self.locations else ""

    @property
    def posted_str(self) -> str:
        if not self.posted:
            return ""
        try:
            return datetime.fromtimestamp(int(self.posted), tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OSError, OverflowError):
            return ""

    def to_row(self) -> List[str]:
        """Serialize to a sheet row. Status is intentionally left blank for new
        rows so the user owns it; the pipeline seeds it with 'New'."""
        return [
            datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            self.source,
            self.company,
            self.role,
            self.role_type,
            self.employment,
            self.location_str,
            self.work_auth,
            self.priority,
            self.posted_str,
            self.url,
            self.relevance,
            "New",
            self.notes,
        ]


_WS_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    if not text:
        return ""
    return _WS_RE.sub(" ", str(text)).strip()
