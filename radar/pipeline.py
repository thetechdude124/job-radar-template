"""Pipeline orchestrator - the stream of agents.

Ingest (multiple sources) -> normalize -> filter -> dedupe vs sheet -> append.

Usage:
    python -m radar.pipeline                 # auto backend (google if creds else csv)
    python -m radar.pipeline --backend csv   # force local CSV
    python -m radar.pipeline --dry-run       # filter + print, write nothing
"""

from __future__ import annotations

import argparse
import sys
from typing import List

from .config import load_yaml
from .dedupe import split_new
from .filter import filter_listings
from .llm import LLM
from .models import Listing
from .normalize import normalize
from .sheets import make_backend, resolve_backend_name
from .sources import FETCHERS


def ingest(sources_cfg: dict) -> List[Listing]:
    raw: List[Listing] = []
    for src in sources_cfg.get("sources", []):
        if not src.get("enabled"):
            continue
        fetcher = FETCHERS.get(src.get("type"))
        if not fetcher:
            print(f"  [warn] unknown source type: {src.get('type')}")
            continue
        try:
            raw.extend(fetcher(src))
        except Exception as exc:
            print(f"  [warn] source {src.get('name')} crashed: {exc}")
    return raw


def run(profile_path: str, sources_path: str, backend_name: str, dry_run: bool) -> int:
    profile = load_yaml(profile_path)
    sources_cfg = load_yaml(sources_path)

    print("== Ingest ==")
    raw = ingest(sources_cfg)
    listings = normalize(raw)
    print(f"Normalized to {len(listings)} unique raw listings")

    print("== Filter ==")
    llm = LLM(model=profile.get("llm_relevance", {}).get("model"))
    kept = filter_listings(listings, profile, llm=llm)
    kept.sort(key=lambda l: (l.priority != "High", l.relevance != "Match", l.company.lower()))
    print(f"Kept {len(kept)} relevant listings ({sum(1 for l in kept if l.priority == 'High')} high-priority)")

    if dry_run:
        print("== Dry run (no write). Top matches: ==")
        for l in kept[:40]:
            flag = " [!]" if l.work_auth else ""
            print(f"  [{l.priority:>6}] {l.role_type:<18} {l.company} - {l.role} ({l.employment}){flag}")
        if len(kept) > 40:
            print(f"  ... and {len(kept) - 40} more")
        return 0

    print(f"== Write ({backend_name}) ==")
    backend = make_backend(backend_name)
    existing = backend.read_existing_keys()
    new = split_new(kept, existing)
    written = backend.append(new)
    print(f"Existing rows: {len(existing)} | New appended: {written}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Job Radar pipeline")
    ap.add_argument("--profile", default="config/profile.yaml")
    ap.add_argument("--sources", default="config/sources.yaml")
    ap.add_argument("--backend", default="", choices=["", "csv", "google"],
                    help="Override output backend (default: auto)")
    ap.add_argument("--dry-run", action="store_true", help="Filter and print, write nothing")
    args = ap.parse_args(argv)

    backend_name = resolve_backend_name(args.backend)
    return run(args.profile, args.sources, backend_name, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
