"""Ingest agents. Each module exposes ``fetch(source_cfg) -> list[Listing]``."""

from . import github_json, quant_repo, extra_pages, speedyapply

FETCHERS = {
    "github_json": github_json.fetch,
    "quant_repo": quant_repo.fetch,
    "extra_pages": extra_pages.fetch,
    "speedyapply": speedyapply.fetch,
}
