# Diagnostics Report — Streamlit Dashboard

Read-only Streamlit dashboard that reproduces the per-student diagnostic report
(Overall readiness + Screening / Behavioural / Tech Thinking / Career Readiness rounds)
directly from the diagnostics Postgres DB, with filters by round and round-completion.

The app **only issues `SELECT` queries** — it never writes to the database.

## What it shows

For every student with a diagnostic:

- **Identity** — name, email, phone, institution / degree / stream, English level, target band
  (selected job title + salary range + companies).
- **Overall Diagnostic** — readiness score + label (No Hire / Hold / Hire / Strong Hire),
  salary band, language / thinking / confidence averages, overall report link. For students who
  haven't finished all 4 rounds, a *provisional* overall is computed from completed rounds.
- **Per round** (Screening, Behavioural, Tech Thinking, Career Readiness) — total score + label,
  language / thinking / confidence scores + labels, salary band, **report URL, video URL, audio
  URL, recording link**.

## Filters

- Name / email search
- Diagnostic status (In-progress / Completed)
- **Number of rounds completed** (0–4) — e.g. pick `4` for "completed all rounds", `3` for three
- **Completed specific rounds** — student must have a ready report for *all* selected rounds
- **Round sections to display** — show/hide Overall + each round
- Readiness label, target band, overall-score range

## Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/).

```bash
cd diagnostics-report-streamlit
uv sync                 # creates .venv and installs from pyproject.toml / uv.lock

cp .env.example .env    # then set DATABASE_URL (reuse the diagnostics app value) + REPORT_BASE_URL

uv run streamlit run app.py
```

## Data source notes

- Per-round scores come pre-computed from `report.metadata -> 'hydratedReport' ->
  'assessment_result'` (no scoring is recomputed here).
- Overall readiness comes from `diagnostic.finalReport` when present.
- Report links: `{REPORT_BASE_URL}/d/{shareToken}`; recordings:
  `{REPORT_BASE_URL}/session/{sessionId}/recording`; audio/video are direct S3 URLs.
