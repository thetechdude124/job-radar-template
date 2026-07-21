# Job Radar

An automated "stream of agents" that finds relevant opportunities and drops
them into a Google Sheet you apply from - so you never have to babysit
Instagram stories or scroll job boards again.

It targets, all configurable in [`config/profile.yaml`](config/profile.yaml):

- **Quant** - QR / QT / quant-dev / quant-SWE (Citadel, HRT, Jane Street, Two Sigma, DRW, SIG, Jump, Optiver, ...)
- **Big-tech SWE** - Google, Meta, Amazon, Microsoft, Apple, Netflix, Nvidia, ...
- **AI research** - research scientist/engineer + ML roles at top AI labs
- **Research fellowships / residencies** - e.g. OpenAI Residency, Anthropic Fellows
- **Nonlinear opportunities** - career fairs, hackathons, insight/early-career programs (mainly via the Zero2Sudo screenshot ingester)

Internships first; full-time roles only surface for S-tier companies (a config flag).

## Want your own? (for anyone)

This is a template - anyone can run their own tailored copy in ~5-15 minutes.
Works for software, quant, AI research, **product management**, and
**mechanical/hardware engineering** too.

**Non-technical? Let Claude set it up with you.** Open **[claude/START_HERE.md](claude/START_HERE.md)** -
you paste one file into Claude and it walks you through everything, step by step,
no coding. (Uses your Claude subscription.)

**Comfortable with a terminal?**
1. Click **"Use this template"** at the top of the repo to create your own copy.
2. `pip install -r requirements.txt`, then run the guided setup:

```bash
python -m radar.setup
```

It asks which tracks you want, internships vs. full-time, locations, and target
term, and writes your `config/profile.yaml` for you. Full written walkthrough in
**[SETUP.md](SETUP.md)**.

## How it works

```
ingest (GitHub repos + AI-lab pages + IG screenshots)
  -> normalize -> filter (role type / location / term / priority / relevance)
  -> dedupe vs sheet -> append new rows
```

Primary data comes from fast, public, structured sources (no Instagram login,
no ban risk):

- `SimplifyJobs/Summer20xx-Internships` - JSON, updated hourly
- `vanshb03/Summer2027-Internships` - JSON
- `northwesternfintech/2027QuantInternships` - quant-specific (SWE/QR/QT)
- Optional: AI-lab career pages (LLM-extracted, off by default)
- Optional: Zero2Sudo story screenshots you drop into `inbox/`

> **Why not scrape Instagram automatically?** Zero2Sudo only posts jobs in
> ephemeral stories, and login-based scraping gets accounts banned by Meta. The
> repos above cover the same firms, update faster, and carry zero risk. So IG is
> an optional manual fallback via the screenshot ingester.

## Quick start (local, zero setup)

```bash
cd job-radar
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# See what it would surface, without writing anywhere:
python -m radar.pipeline --dry-run

# Write to a local CSV (data/jobs.csv):
python -m radar.pipeline --backend csv
open data/jobs.csv
```

## Google Sheets setup

1. Create a Google Sheet. Copy its ID from the URL
   (`https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit`).
2. In [Google Cloud Console](https://console.cloud.google.com/): create a
   project, enable the **Google Sheets API**, create a **Service Account**, and
   download its JSON key.
3. **Share the Sheet** with the service account's email
   (`...@...iam.gserviceaccount.com`) as an Editor.
4. Run locally:

```bash
export SHEET_ID="your_sheet_id"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
python -m radar.pipeline --backend google
```

The sheet gets these columns; **`Status` is yours** - the pipeline seeds new
rows with `New` and never overwrites your edits:

`Date Added | Source | Company | Role | Role Type | Employment | Location | Work Auth | Priority | Posted | Link | Relevance | Status | Notes`

## Run it on a schedule (GitHub Actions, free)

1. Push this folder to a GitHub repo.
2. Repo -> Settings -> Secrets and variables -> Actions -> add:
   - `SHEET_ID`
   - `GCP_SA_JSON` - paste the **entire** service-account JSON as the value
   - `OPENAI_API_KEY` - optional (only for LLM relevance / AI-lab pages / screenshots)
3. The workflow in [`.github/workflows/radar.yml`](.github/workflows/radar.yml)
   runs hourly. Trigger it manually first: Actions -> Job Radar -> Run workflow.

## Zero2Sudo screenshots (optional)

```bash
export OPENAI_API_KEY=sk-...
# save a story screenshot into inbox/, then:
python -m radar.ingest_screenshots            # writes to your backend
python -m radar.ingest_screenshots --dry-run  # preview only
```

## Configuration

- [`config/profile.yaml`](config/profile.yaml) - role types (toggle each),
  priority firms, S-tier list, locations, target term, work-auth flags, optional
  LLM relevance.
- [`config/sources.yaml`](config/sources.yaml) - which repos/pages to pull,
  their URLs, and enable flags. When `SimplifyJobs/Summer2027-Internships` goes
  live, swap `2026` -> `2027` in the Simplify URL.

## Roadmap: Phase 2 - apply assistant

A follow-up agent that takes a `New` row, opens the link, detects the ATS
(Greenhouse / Lever / Workday), pre-fills from your profile + resume, and pauses
for your review before submitting. Human-in-the-loop because Workday auth walls
and captchas make full auto-submit brittle.
