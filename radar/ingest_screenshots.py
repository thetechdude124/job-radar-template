"""Optional, on-demand Zero2Sudo screenshot ingester.

Drop story screenshots into ./inbox, then run:

    python -m radar.ingest_screenshots

Each image is sent to a vision model to extract company / role / link /
opportunity type (including career fairs and other nonlinear events), run
through the same filter, deduped, and appended to the same backend.
Processed images are moved to ./inbox/processed. Requires OPENAI_API_KEY.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import List

from .config import load_yaml
from .dedupe import split_new
from .filter import filter_listings
from .llm import LLM
from .models import Listing, clean_text
from .normalize import normalize
from .sheets import make_backend, resolve_backend_name

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".webp": "image/webp", ".gif": "image/gif"}

_PROMPT = (
    "This is a screenshot from a tech-careers Instagram/TikTok story (creator "
    "@zero2sudo). Extract every opportunity mentioned. Return strict JSON: "
    "{\"items\": [{\"company\": str, \"role\": str, \"url\": str, "
    "\"employment\": one of [\"Internship\", \"Full-time\", \"Event\"], "
    "\"location\": str, \"notes\": str}]}. Use 'Event' for career fairs, "
    "hackathons, insight programs, deadlines, or info sessions. Capture any "
    "visible link/URL exactly; if none is visible, leave url empty. If nothing "
    "relevant, return an empty list."
)


def _extract(image_path: Path, llm: LLM) -> List[Listing]:
    data = llm.vision_json(
        _PROMPT,
        image_path.read_bytes(),
        mime=_MIME.get(image_path.suffix.lower(), "image/png"),
    )
    items = (data or {}).get("items", []) if isinstance(data, dict) else []
    out: List[Listing] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        loc = clean_text(it.get("location", ""))
        emp = clean_text(it.get("employment", "")) or "Internship"
        emp = {"event": "Event", "full-time": "Full-time", "internship": "Internship"}.get(emp.lower(), emp)
        out.append(
            Listing(
                source="zero2sudo",
                company=clean_text(it.get("company", "")),
                role=clean_text(it.get("role", "")),
                url=(it.get("url") or "").strip(),
                locations=[loc] if loc else [],
                category="zero2sudo",
                employment=emp,
                notes=clean_text(it.get("notes", "")),
                active=True,
            )
        )
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ingest Zero2Sudo story screenshots")
    ap.add_argument("--profile", default="config/profile.yaml")
    ap.add_argument("--inbox", default="inbox")
    ap.add_argument("--backend", default="", choices=["", "csv", "google"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep", action="store_true", help="Do not move processed images")
    args = ap.parse_args(argv)

    llm = LLM()
    if not llm.available():
        print(f"[error] vision LLM unavailable: {llm.init_error}")
        return 1

    inbox = Path(args.inbox)
    images = [p for p in sorted(inbox.glob("*")) if p.suffix.lower() in IMAGE_EXTS]
    if not images:
        print(f"No images in {inbox}/ - nothing to do.")
        return 0

    profile = load_yaml(args.profile)
    raw: List[Listing] = []
    for img in images:
        print(f"  reading {img.name} ...")
        raw.extend(_extract(img, llm))

    listings = normalize(raw)
    kept = filter_listings(listings, profile, llm=llm)
    print(f"Extracted {len(raw)} -> {len(listings)} unique -> {len(kept)} relevant")

    if args.dry_run:
        for l in kept:
            print(f"  [{l.priority}] {l.role_type} | {l.company} - {l.role} ({l.employment}) {l.url}")
        return 0

    backend = make_backend(resolve_backend_name(args.backend))
    new = split_new(kept, backend.read_existing_keys())
    written = backend.append(new)
    print(f"Appended {written} new rows")

    if not args.keep:
        processed = inbox / "processed"
        processed.mkdir(exist_ok=True)
        for img in images:
            shutil.move(str(img), str(processed / img.name))
        print(f"Moved {len(images)} image(s) to {processed}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
