"""Filter agent: decide what to keep, tag role type / priority / work auth /
relevance. Deterministic by default; optional LLM refinement for borderline
roles."""

from __future__ import annotations

import re
from typing import List, Optional

from .llm import LLM
from .models import Listing

# Map raw source categories -> role_type when the title alone doesn't match.
CATEGORY_MAP = {
    "software": "big_tech_swe",
    "quant": "quant",
    "quantitative": "quant",
    "data science": "ai_research",
    "ai/ml": "ai_research",
    "machine learning": "ai_research",
    "ai lab": "ai_research",
    "product": "product_management",
    "hardware": "hardware_mecheng",
    "mechanical": "hardware_mecheng",
}

_YEAR_RE = re.compile(r"20\d{2}")


def _accepted_years(term_cfg: dict) -> set:
    accepted = " ".join(term_cfg.get("accepted_keywords", []))
    years = set(_YEAR_RE.findall(accepted))
    return years or {"2027"}


def role_type_for(listing: Listing, profile: dict) -> Optional[str]:
    search = f" {listing.role.lower()} "
    role_types = profile.get("role_types", {})
    for name, cfg in role_types.items():
        if not cfg.get("enabled"):
            continue
        for kw in cfg.get("keywords", []):
            if kw.lower() in search:
                return name
    # Fallback: map the source category.
    cat = listing.category.lower()
    for cat_key, rt in CATEGORY_MAP.items():
        if cat_key in cat and role_types.get(rt, {}).get("enabled"):
            return rt
    return None


# All 50 US state abbreviations + DC (locations in these repos are usually
# "City, ST", so matching the state code is the most reliable US signal).
US_STATES = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id",
    "il", "in", "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms",
    "mo", "mt", "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok",
    "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv",
    "wi", "wy", "dc",
}

# Common US locations written without a state code.
US_BARE_CITIES = {
    "nyc", "sf", "sfo", "la", "dc", "bay area", "silicon valley", "manhattan",
    "brooklyn", "d.c.", "washington dc", "the bay",
}

_WORD_RE = re.compile(r"[a-z]+\.?")


def _is_us_location(loc: str) -> bool:
    ll = loc.lower().strip()
    if not ll:
        return False
    if "remote" in ll:
        return True
    if any(x in ll for x in ("united states", "u.s.a", "u.s.", " usa", "(usa", "usa)")) or ll in ("us", "usa"):
        return True
    if any(city in ll for city in US_BARE_CITIES):
        return True
    # Whole-word state code, e.g. "Seattle, WA" or "WA".
    words = re.findall(r"\b([a-z]{2})\b", ll)
    if any(w in US_STATES for w in words):
        return True
    return False


def _loc_has(loc: str, token: str) -> bool:
    if len(token) <= 3 and token.isalpha():
        return re.search(rf"\b{re.escape(token)}\b", loc) is not None
    return token in loc


def location_ok(listing: Listing, profile: dict) -> bool:
    cfg = profile.get("location", {})
    if cfg.get("mode") == "any":
        return True
    if not listing.locations:
        return cfg.get("keep_when_unknown", True)
    allow = [t.lower() for t in cfg.get("allow_tokens", [])]
    for loc in listing.locations:
        ll = loc.lower()
        if _is_us_location(ll):
            return True
        if any(_loc_has(ll, t) for t in allow):
            return True
    return False


def term_ok(listing: Listing, profile: dict) -> bool:
    if listing.employment == "Event":
        return True
    cfg = profile.get("term", {})
    if not listing.term:
        return cfg.get("keep_when_unknown", True)
    tl = listing.term.lower()
    found_years = set(_YEAR_RE.findall(tl))
    if found_years and not (found_years & _accepted_years(cfg)):
        return False
    accepted = [k.lower() for k in cfg.get("accepted_keywords", [])]
    if any(k in tl for k in accepted):
        return True
    return cfg.get("keep_when_unknown", True)


def company_priority(company: str, profile: dict) -> str:
    c = company.lower()
    for group in profile.get("priority_firms", {}).values():
        for firm in group:
            if firm and firm.lower() in c:
                return "High"
    if is_s_tier(company, profile):
        return "High"
    return "Normal"


def is_s_tier(company: str, profile: dict) -> bool:
    c = company.lower()
    return any(f.lower() in c for f in profile.get("s_tier", []))


def work_auth_flag(listing: Listing, profile: dict) -> str:
    s = (listing.sponsorship or "").lower()
    flags = []
    if "citiz" in s:
        flags.append("US citizen req")
    if "does not offer sponsor" in s or "no sponsor" in s:
        flags.append("No sponsorship")
    return ", ".join(flags)


def _employment_allowed(listing: Listing, profile: dict) -> bool:
    emp = listing.employment
    cfg = profile.get("employment", {})
    if emp == "Event":
        return True
    if emp == "Full-time":
        return bool(cfg.get("fulltime_if_top_tier", True)) and is_s_tier(listing.company, profile)
    return bool(cfg.get("internships", True))


def filter_listings(listings: List[Listing], profile: dict, llm: Optional[LLM] = None) -> List[Listing]:
    kept: List[Listing] = []
    wa_cfg = profile.get("work_auth", {})
    keep_inactive = bool(profile.get("keep_inactive", False))

    for lst in listings:
        rt = role_type_for(lst, profile)
        if not rt:
            continue
        lst.role_type = rt
        if rt == "nonlinear":
            lst.employment = "Event"

        if not _employment_allowed(lst, profile):
            continue
        if not lst.active and not keep_inactive:
            continue
        if not location_ok(lst, profile):
            continue
        if not term_ok(lst, profile):
            continue

        wa = work_auth_flag(lst, profile)
        lst.work_auth = wa
        if wa_cfg.get("exclude_us_citizen_required") and "US citizen req" in wa:
            continue
        if wa_cfg.get("exclude_no_sponsorship") and "No sponsorship" in wa:
            continue

        lst.priority = company_priority(lst.company, profile)
        lst.relevance = "Match" if lst.priority == "High" else "Maybe"
        kept.append(lst)

    # Optional LLM refinement of "Maybe" rows.
    rel_cfg = profile.get("llm_relevance", {})
    if rel_cfg.get("enabled") and llm and llm.available():
        kept = _llm_refine(kept, profile, llm)

    return kept


def _llm_refine(listings: List[Listing], profile: dict, llm: LLM) -> List[Listing]:
    summary = profile.get("llm_relevance", {}).get("profile_summary", "")
    system = (
        "You judge whether a job/opportunity is relevant to a candidate. "
        "Return JSON {\"verdict\": one of [\"Match\", \"Maybe\", \"Skip\"]}."
    )
    out = []
    for lst in listings:
        if lst.relevance != "Maybe":
            out.append(lst)
            continue
        data = llm.complete_json(
            system,
            f"Candidate: {summary}\n\nOpportunity: {lst.company} - {lst.role} "
            f"({lst.role_type}, {lst.employment}, {lst.location_str})",
            max_tokens=50,
        )
        verdict = (data or {}).get("verdict", "Maybe")
        if verdict == "Skip":
            continue
        lst.relevance = verdict if verdict in ("Match", "Maybe") else "Maybe"
        out.append(lst)
    return out
