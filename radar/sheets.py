"""Output backends.

Two interchangeable stores implement the same interface:
  - read_existing_keys() -> set[str]   (dedupe keys derived from the Link column)
  - append(listings)                   (append new rows; never touch Status)

CSV backend needs nothing external (great for dry runs). Google backend uses a
service-account credential and a spreadsheet id.
"""

from __future__ import annotations

import csv
import json
import os
import random
import time
from pathlib import Path
from typing import List, Set

from .models import HEADERS, Listing, dedupe_key_for

# Transient HTTP statuses worth retrying: rate limiting + Google 5xx blips.
_RETRY_STATUS = {429, 500, 502, 503, 504}


def _with_retry(fn, *args, _attempts: int = 5, _base: float = 1.5, **kwargs):
    """Call a gspread network op, retrying transient API errors with backoff.

    Google Sheets returns sporadic 500 "Internal error" and 429 rate-limit
    responses that succeed on retry. Non-transient errors (bad auth, 404,
    permission) are re-raised immediately so real bugs still surface.
    """
    import gspread

    last_exc: Exception | None = None
    for attempt in range(_attempts):
        try:
            return fn(*args, **kwargs)
        except gspread.exceptions.APIError as exc:
            status = None
            try:
                status = exc.response.status_code
            except Exception:
                pass
            if status not in _RETRY_STATUS:
                raise
            last_exc = exc
            if attempt == _attempts - 1:
                break
            sleep_s = _base * (2 ** attempt) + random.uniform(0, 0.75)
            print(
                f"  [retry] Sheets API {status}; attempt {attempt + 1}/{_attempts}, "
                f"backing off {sleep_s:.1f}s"
            )
            time.sleep(sleep_s)
    assert last_exc is not None
    raise last_exc


class CSVBackend:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _link_col(self) -> int:
        return HEADERS.index("Link")

    def read_existing_keys(self) -> Set[str]:
        keys: Set[str] = set()
        if not self.path.exists():
            return keys
        with self.path.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if not header:
                return keys
            link_idx = header.index("Link") if "Link" in header else self._link_col()
            comp_idx = header.index("Company") if "Company" in header else 2
            role_idx = header.index("Role") if "Role" in header else 3
            for row in reader:
                if not row:
                    continue
                url = row[link_idx] if link_idx < len(row) else ""
                comp = row[comp_idx] if comp_idx < len(row) else ""
                role = row[role_idx] if role_idx < len(row) else ""
                keys.add(dedupe_key_for(url, comp, role))
        return keys

    def append(self, listings: List[Listing]) -> int:
        exists = self.path.exists()
        with self.path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if not exists:
                writer.writerow(HEADERS)
            for lst in listings:
                writer.writerow(lst.to_row())
        return len(listings)


class GoogleSheetBackend:
    def __init__(self, sheet_id: str, worksheet: str = "Jobs"):
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        sa_json = os.environ.get("GCP_SA_JSON")
        sa_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if sa_json:
            info = json.loads(sa_json)
            creds = Credentials.from_service_account_info(info, scopes=scopes)
        elif sa_file:
            creds = Credentials.from_service_account_file(sa_file, scopes=scopes)
        else:
            raise RuntimeError("Set GCP_SA_JSON or GOOGLE_APPLICATION_CREDENTIALS for the Google backend")

        gc = gspread.authorize(creds)
        sh = _with_retry(gc.open_by_key, sheet_id)
        try:
            self.ws = _with_retry(sh.worksheet, worksheet)
        except gspread.WorksheetNotFound:
            self.ws = _with_retry(
                sh.add_worksheet, title=worksheet, rows=1000, cols=len(HEADERS)
            )
        self._ensure_header()

    def _ensure_header(self):
        first_row = _with_retry(self.ws.row_values, 1)
        if first_row != HEADERS:
            if not first_row:
                _with_retry(self.ws.update, [HEADERS], "A1")
            # If a header exists but differs, leave user data alone; we only
            # rely on the Link column position by name below.

    def read_existing_keys(self) -> Set[str]:
        keys: Set[str] = set()
        rows = _with_retry(self.ws.get_all_values)
        if not rows:
            return keys
        header = rows[0]
        link_idx = header.index("Link") if "Link" in header else HEADERS.index("Link")
        comp_idx = header.index("Company") if "Company" in header else HEADERS.index("Company")
        role_idx = header.index("Role") if "Role" in header else HEADERS.index("Role")
        for row in rows[1:]:
            url = row[link_idx] if link_idx < len(row) else ""
            comp = row[comp_idx] if comp_idx < len(row) else ""
            role = row[role_idx] if role_idx < len(row) else ""
            if url or comp or role:
                keys.add(dedupe_key_for(url, comp, role))
        return keys

    def append(self, listings: List[Listing]) -> int:
        if not listings:
            return 0
        rows = [lst.to_row() for lst in listings]
        _with_retry(self.ws.append_rows, rows, value_input_option="USER_ENTERED")
        return len(rows)


def make_backend(backend: str):
    backend = (backend or "").lower()
    if backend == "google":
        sheet_id = os.environ.get("SHEET_ID")
        if not sheet_id:
            raise RuntimeError("SHEET_ID env var required for the Google backend")
        return GoogleSheetBackend(sheet_id, os.environ.get("RADAR_WORKSHEET", "Jobs"))
    csv_path = os.environ.get("RADAR_CSV", "data/jobs.csv")
    return CSVBackend(csv_path)


def resolve_backend_name(explicit: str = "") -> str:
    """csv unless explicitly google or Google creds are present."""
    if explicit:
        return explicit
    env = os.environ.get("RADAR_BACKEND")
    if env:
        return env
    if os.environ.get("GCP_SA_JSON") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return "google"
    return "csv"
