"""Config loading helpers."""

from __future__ import annotations

from pathlib import Path

import yaml


def load_yaml(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with p.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
