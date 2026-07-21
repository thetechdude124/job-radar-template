# Get your own Job Radar (5-10 min)

Job Radar watches public internship/job sources every hour and drops the ones
that match *your* goals into a Google Sheet you apply from. This guide sets up
your own copy. Everything here is **free** - no credit card, no servers.

> **Not technical?** Don't follow this by hand - open
> [claude/START_HERE.md](claude/START_HERE.md) and let Claude walk you through
> the entire thing conversationally. This written guide is the manual fallback.

## 1. Make your own copy

Click **"Use this template" → Create a new repository** at the top of the repo
page (or fork it). Then clone your copy:

```bash
git clone https://github.com/<you>/job-radar.git
cd job-radar
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Tailor what it finds

Run the guided setup - it asks a few questions and writes your `config/profile.yaml`:

```bash
python -m radar.setup
```

You choose which tracks to follow (SWE, quant, AI research, fellowships,
career-fair/"nonlinear" events), internships vs. full-time, locations, and your
target term. You can re-run it anytime, or hand-edit `config/profile.yaml`
directly (it's fully commented). Add your dream companies under `priority_firms`
to float them to the top.

Preview what it would surface, no accounts needed:

```bash
python -m radar.pipeline --dry-run
```

## 3. Create a Google Sheet + service account (free)

The hourly job runs unattended, so it needs a "robot" credential to write to
your Sheet. If prompted to enable billing anywhere, **ignore it** - not needed.

1. Create a Sheet at [sheets.new](https://sheets.new). Copy its **ID** from the
   URL (`.../spreadsheets/d/`**`THIS`**`/edit`).
2. In [console.cloud.google.com](https://console.cloud.google.com): create a
   project → search **"Google Sheets API"** → **Enable**.
3. Search **"Service Accounts"** → **Create service account** → name it → Done.
4. Open it → **Keys → Add Key → Create new key → JSON** → download it.
5. Open the JSON, copy the `client_email`, and **Share** your Sheet with that
   email as **Editor**.

Test it writes locally:

```bash
export SHEET_ID="your_sheet_id"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
python -m radar.pipeline --backend google
```

## 4. Turn on the hourly cloud cron

1. Push your repo to GitHub (if you cloned a template copy, it's already there).
2. Add secrets - either run `python -m radar.setup` again and say **yes** to
   "Set GitHub Actions secrets" (uses the `gh` CLI), or do it manually:
   Repo → **Settings → Secrets and variables → Actions**:
   - `SHEET_ID` = your Sheet ID
   - `GCP_SA_JSON` = the entire contents of the JSON key
   - `OPENAI_API_KEY` = optional (only for AI relevance / screenshots)
3. Repo → **Actions** tab → enable workflows if prompted → **Job Radar → Run
   workflow** to test. After that it runs every hour on its own.

That's it. Open your Sheet whenever - new matches appear hourly with
`Status = New`, and your edits to the `Status` column are never overwritten.

## No-cloud alternative

Don't want any Google/GitHub setup? Just run it locally to a CSV whenever you
like:

```bash
python -m radar.pipeline --backend csv   # writes data/jobs.csv
```

## Optional: AI features

Set `OPENAI_API_KEY` and enable them to get smarter relevance scoring, AI-lab
career-page extraction, and screenshot ingestion (drop story screenshots into
`inbox/`, run `python -m radar.ingest_screenshots`). All off by default; the
core pipeline is free and deterministic.
