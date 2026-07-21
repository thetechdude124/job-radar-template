"""Interactive onboarding: `python -m radar.setup`.

Walks a new user through tailoring their `config/profile.yaml` (which roles to
track, internships vs full-time, locations, target term) using safe, in-place
edits that preserve all the comments and keyword lists. Optionally wires up the
GitHub Actions secrets via the `gh` CLI so the hourly cron can write to their
Google Sheet.

No third-party deps required.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

PROFILE = Path("config/profile.yaml")

ROLE_TYPES = [
    ("big_tech_swe", "Big-tech / general software engineering internships"),
    ("quant", "Quant (research / trading / dev) internships"),
    ("ai_research", "AI research / ML roles at top labs"),
    ("research_fellowship", "Research fellowships & residencies (OpenAI, Anthropic, ...)"),
    ("product_management", "Product management (PM / APM) roles"),
    ("hardware_mecheng", "Mechanical / hardware / general engineering roles"),
    ("nonlinear", "Nonlinear opportunities (career fairs, hackathons, insight programs)"),
]

PRESETS = {
    "1": ("Software / quant / AI (recommended for CS)", {"big_tech_swe", "quant", "ai_research", "research_fellowship", "nonlinear"}),
    "2": ("Software engineering only", {"big_tech_swe"}),
    "3": ("Quant only", {"quant"}),
    "4": ("AI research + fellowships", {"ai_research", "research_fellowship"}),
    "5": ("Product management (PM)", {"product_management", "nonlinear"}),
    "6": ("Mechanical / hardware engineering", {"hardware_mecheng", "nonlinear"}),
    "7": ("PM + engineering (mech/hardware)", {"product_management", "hardware_mecheng", "nonlinear"}),
    "8": ("Everything", {rt for rt, _ in ROLE_TYPES}),
    "9": ("Custom (pick individually)", None),
}


def _input(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        print("")
        return ""


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    return _input(f"{prompt}{suffix}: ") or default


def _yn(prompt: str, default: bool = True) -> bool:
    d = "Y/n" if default else "y/N"
    resp = _input(f"{prompt} ({d}): ").lower()
    if not resp:
        return default
    return resp.startswith("y")


def _set_role_enabled(text: str, role: str, value: bool) -> str:
    pattern = re.compile(rf"(^  {re.escape(role)}:\n    enabled: )(?:true|false)", re.M)
    return pattern.sub(rf"\g<1>{'true' if value else 'false'}", text)


def _set_scalar(text: str, key: str, value: str, indent: str = "  ") -> str:
    pattern = re.compile(rf"(^{indent}{re.escape(key)}: ).*$", re.M)
    return pattern.sub(rf"\g<1>{value}", text, count=1)


def choose_roles() -> set:
    print("\nWhich opportunities do you want tracked?")
    for k, (label, _) in PRESETS.items():
        print(f"  {k}) {label}")
    choice = _ask("Pick a preset", "1")
    label, roles = PRESETS.get(choice, PRESETS["1"])
    if roles is not None:
        print(f"  -> {label}")
        return roles
    selected = set()
    print("\nEnable each track:")
    for rt, desc in ROLE_TYPES:
        if _yn(f"  Track '{rt}' - {desc}?", True):
            selected.add(rt)
    return selected or {rt for rt, _ in ROLE_TYPES}


def wire_secrets():
    if not shutil.which("gh"):
        print("\n(Skipping secret setup: GitHub CLI `gh` not found. See SETUP.md.)")
        return
    if not _yn("\nSet GitHub Actions secrets now via gh?", False):
        return
    sheet_id = _ask("  Google Sheet ID")
    sa_path = _ask("  Path to service-account JSON")
    if not sheet_id or not Path(sa_path).expanduser().is_file():
        print("  Missing Sheet ID or JSON not found - skipping. Run again when ready.")
        return
    subprocess.run(["gh", "secret", "set", "SHEET_ID", "--body", sheet_id], check=False)
    with open(Path(sa_path).expanduser(), "rb") as fh:
        subprocess.run(["gh", "secret", "set", "GCP_SA_JSON"], stdin=fh, check=False)
    print("  Secrets set. The hourly workflow will now write to your Sheet.")


def main() -> int:
    if not PROFILE.is_file():
        print("config/profile.yaml not found. Run this from the repo root.")
        return 1

    print("=== Job Radar setup ===")
    text = PROFILE.read_text(encoding="utf-8")

    roles = choose_roles()
    for rt, _ in ROLE_TYPES:
        text = _set_role_enabled(text, rt, rt in roles)

    internships = _yn("\nInclude internships?", True)
    fulltime = _yn("Also include full-time roles at S-tier companies?", True)
    text = _set_scalar(text, "internships", "true" if internships else "false")
    text = _set_scalar(text, "fulltime_if_top_tier", "true" if fulltime else "false")

    us_only = _yn("\nRestrict to US + Remote (answer no to allow anywhere)?", True)
    text = _set_scalar(text, "mode", "us_and_remote" if us_only else "any")

    term = _ask("\nTarget recruiting term keyword", "summer 2027")
    year = re.search(r"20\d{2}", term)
    kws = f'["{term.lower()}"' + (f', "{year.group(0)}"' if year else "") + ', "summer"]'
    text = _set_scalar(text, "accepted_keywords", kws, indent="  ")

    PROFILE.write_text(text, encoding="utf-8")
    print(f"\nWrote {PROFILE}. Enabled tracks: {', '.join(sorted(roles))}")

    wire_secrets()

    print("\nDone. Next: `python -m radar.pipeline --dry-run` to preview, or see SETUP.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
