# IPO Checker

A Python toolkit for collecting Indian IPO data (GMP, pricing, dates, status) from
public sources, storing it in SQLite, screening for high-GMP opportunities, producing
an analysed PDF report that is emailed automatically, and eventually exposing a
**Next.js dashboard with an LLM chat assistant** that can run on local or cloud
models, for asking questions about current IPOs.

> **Status: working prototype.**
> Scraping, SQLite persistence with numbered migrations and source provenance,
> the 20% GMP filter, deterministic analysis, PDF reporting, optional SMTP email,
> the read-only FastAPI service, the CLI, and the test suite work. A read-only
> **Next.js 16 frontend** (dashboard, IPO detail, reports) now lives in
> `frontend/`; its chat page is a placeholder and the AI layer is not implemented
> yet. The research specification for the overview/in-depth analysis, PDF deep
> links and provider-agnostic AI layer lives in
> [`docs/ipo-research-framework.md`](docs/ipo-research-framework.md). See
> [Roadmap / TODO](#roadmap--todo) for the agreed next steps.
>
> **Disclaimer:** This project is for personal research and automation. It is **not**
> investment advice. Grey-market premium is unofficial, speculative, and can vanish
> before listing. Always verify with the official RHP / NSE / BSE filings.

---

## Table of contents

- [What it does today](#what-it-does-today)
- [Repository layout](#repository-layout)
- [Data sources](#data-sources)
- [Data model](#data-model)
- [Setup](#setup)
- [Usage](#usage)
- [Configuration](#configuration)
- [Known issues](#known-issues)
- [Where AI is needed](#where-ai-is-needed)
- [Planned architecture](#planned-architecture)
- [Roadmap / TODO](#roadmap--todo)
  - [1. Improve the web scrapers](#1-improve-the-web-scrapers)
  - [2. Keep proper database information](#2-keep-proper-database-information)
  - [3. Minimum GMP of 20% or more](#3-minimum-gmp-of-20-or-more)
  - [4. Complete the IPO analysis](#4-complete-the-ipo-analysis)
  - [5. Generate a PDF and email it](#5-generate-a-pdf-and-email-it)
  - [6. Add AI enrichment (local or cloud)](#6-add-ai-enrichment-local-or-cloud)
  - [7. Build the Next.js frontend and IPO chat](#7-build-the-nextjs-frontend-and-ipo-chat)
  - [8. Research-grade overview, financial analysis and PDF deep links](#8-research-grade-overview-financial-analysis-and-pdf-deep-links)
  - [Cross-cutting engineering tasks](#cross-cutting-engineering-tasks)
- [IPO analysis checklist](#ipo-analysis-checklist)
- [Research framework](docs/ipo-research-framework.md)
- [Definition of done](#definition-of-done)

---

## What it does today

| Area | State |
| --- | --- |
| **InvestorGain scraper** | Fetches a JSON report from an undocumented InvestorGain endpoint and maps rows into the `IPO` model. Feeds `ipos` and `gmp_history`. Only rows whose status is `open` — or, since InvestorGain supplies no status, whose open/close dates bracket today — are saved. |
| **IPO Watch scraper** | Consumes the JSON API behind the GMP page (`/server/api/ipo/GetIpoListingByStatus`) and maps the price band, sector, lot size, subscription, and dates into the `IPO` model. No HTML parsing. Only rows whose status is `open` (or derived as `open` from dates) are saved. |
| **Status filtering** | `src/utils/parsing.py` provides `is_open_status()` (exact match on `"open"`) and `derive_status_from_dates()` (infers `open`/`upcoming`/`closed` from `open_date`/`close_date`). The pipeline skips any IPO that is not currently open, so stale/closed/listed IPOs never enter `ipos` or `gmp_history`. |
| **Normalisation** | `normalize_name()` lowercases, strips `Ltd`/`Limited`, and converts to a `snake_case`-style key used as the cross-source identity. |
| **SQLite persistence** | Creates and upgrades `ipos`, `gmp_history`, `analysis_reports`, `scrape_runs`, `ipo_sources` and `schema_migrations` through numbered migrations. Upserts IPOs on `normalized_name`, keeps one GMP row per source per UTC day, and records which source each IPO came from. |
| **Analysis** | `src/analysis/` selects active IPOs whose **latest** GMP is at or above the configured threshold (default **20%**), derives `gmp_percent` when a source omits it, computes transparent weighted factors (GMP, valuation, fundamentals, subscription, risk), and produces a `Strong / Watch / Avoid` verdict with a checklist, strengths, risks and explicit data gaps. Results are persisted to `analysis_reports`. |
| **Reporting** | `src/reporting/pdf.py` renders a ReportLab PDF with a summary table, per-IPO score breakdown, checklist, strengths/risks and data gaps. Reports are written to `reports/`. |
| **Email** | `src/reporting/emailer.py` sends the PDF over SMTP (TLS by default) to comma-separated `EMAIL_TO` recipients. `--dry-run` validates the message without connecting. |
| **CLI** | `python -m src.main` (run from `backend/`) exposes `scrape`, `analyze`, `report`, `run` and `serve`, with `--source`, `--min-gmp`, `--include-upcoming`, `--no-persist`, `--json`, `--email` and `--dry-run`. |
| **Tests** | `pytest` suite covering name normalisation, number/date parsing, active-status logic, the IPO Watch mapping, DB upserts/query helpers, analysis scoring/checklists, PDF generation, email dry-runs and the CLI. |
| **AI (local or cloud)** | Not implemented. Planned as an **optional, provider-agnostic** layer for RHP extraction, analysis narratives, entity matching and chat. One common interface selects Ollama / LM Studio / llama.cpp locally, or OpenAI / Anthropic / Gemini / any OpenAI-compatible endpoint in the cloud. Switching is config-only. Local is the default; cloud requires explicit opt-in. Must never replace deterministic filters or calculations. |
| **Web frontend** | Implemented in `frontend/` with Next.js 16 (App Router, Cache Components), React 19, TypeScript and Tailwind 4. Read-only dashboard with a default 20% GMP filter and status filter, IPO detail with GMP sparkline/history and stored analysis, and a reports page. Chat is an explicit placeholder; the Overview/In-depth split, search/sort, shadcn/ui, TanStack Table and Recharts are still planned. |
| **API** | Implemented read-only FastAPI service (`python -m src.main serve`): IPOs, GMP history, analysis, reports, duplicate detection and source provenance. `POST /api/analyze` and `POST /api/reports` require `X-API-Token`. Chat streaming and admin scrape are still planned. |

---

## Repository layout

```
IPO Checker/
├── README.md
├── .gitignore
├── docs/
│   └── ipo-research-framework.md  # research specification (checklist, schema, scoring)
├── backend/
│   ├── .env.example               # documented settings (copy to .env)
│   ├── .gitignore                 # repo-level ignores
│   ├── pyproject.toml             # pytest configuration
│   ├── requirements.txt           # runtime dependencies
│   ├── requirements-dev.txt       # runtime + pytest
│   ├── data/
│   │   └── ipo_intelligence.db    # local SQLite DB (gitignored)
│   ├── debug_responses/           # captured HTML/JSON responses (gitignored)
│   ├── reports/                   # generated PDFs (gitignored)
│   ├── src/                       # Python package (all application source)
│   │   ├── __init__.py
│   │   ├── config.py              # env-backed settings + repo-rooted paths
│   │   ├── main.py                # argparse CLI (scrape / analyze / report / run / serve)
│   │   ├── pipeline.py            # scrape + analyse orchestration
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── main.py            # FastAPI app factory
│   │   │   ├── routes.py
│   │   │   └── schemas.py
│   │   ├── analysis/
│   │   │   ├── __init__.py
│   │   │   ├── filters.py         # active-IPO + min-GMP candidate filter
│   │   │   ├── metrics.py         # derived numeric metrics
│   │   │   ├── scoring.py         # transparent weighted score + verdict
│   │   │   ├── checklist.py       # pass / warn / fail / manual checks
│   │   │   └── analyzer.py        # builds the IPOAnalysis object
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── migrations.py      # numbered, idempotent schema migrations
│   │   │   └── db.py              # connection, upsert, GMP history, provenance + queries
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── ipo.py             # pydantic IPO model
│   │   │   └── analysis.py        # pydantic analysis output model
│   │   ├── reporting/
│   │   │   ├── __init__.py
│   │   │   ├── pdf.py             # ReportLab PDF report
│   │   │   ├── emailer.py         # SMTP delivery + dry-run
│   │   │   └── summary.py         # plain-text summary
│   │   ├── scrapers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # BaseScraper blueprint + payload helper
│   │   │   ├── errors.py          # ScraperError / FetchError / ParseError
│   │   │   ├── investorgain.py    # JSON API scraper
│   │   │   └── ipowatch.py        # JSON API scraper
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── dedupe.py          # cross-source duplicate detection
│   │       ├── http.py            # shared session with retries + backoff
│   │       ├── normalization.py   # name normalisation only
│   │       └── parsing.py         # numbers, dates, date ranges, status logic
│   └── tests/                     # pytest suite (inside backend/)
├── frontend/                      # Next.js 16 + TypeScript + Tailwind 4 app
│   ├── .env.example               # NEXT_PUBLIC_API_BASE_URL
│   ├── app/                       # App Router routes (dashboard, detail, reports, chat)
│   ├── components/                # shell, dashboard, ipo, reports, ui primitives
│   ├── lib/                       # API client, types, formatters
│   └── README.md                  # frontend setup and limitations
├── docker-compose.yml             # planned: api + web + optional local model runtime
└── backend/.venv/                 # local virtualenv (gitignored)
```

Only the files marked "planned" above do not exist yet. Everything else is present
in the current prototype.

---

## Data sources

| Source | Type | Endpoint / page | Notes |
| --- | --- | --- | --- |
| **InvestorGain** | JSON API | `https://webnodejs.investorgain.com/cloud/v2/report/data-read/331/1/9/2026/2026-27/0/all?search=&v=19-49` | Undocumented endpoint. URL, report ID, and fiscal year are configurable (`INVESTORGAIN_*`); the report ID still defaults to `331` and changes per season. |
| **IPO Watch** | JSON API | `https://ipowatch.in/server/api/ipo/GetIpoListingByStatus` | JSON feed used by the public GMP page. Returns name, price band, GMP, status, sector, lot size, issue size, subscription, and dates. Endpoint configurable via `IPOWATCH_API_URL`. |
| **RHP / DRHP** | PDF (official) | NSE / BSE / SEBI filings | Planned source for AI document analysis (objects of issue, risk factors, financials). Store the document URL and page-level citations. |

Both scraped sources are public, but they may be rate-limited, CAPTCHA-protected, or
change their markup. `debug_responses/` contains captured responses (including a reCAPTCHA
page) that are useful when fixing scrapers. **Do not** attempt to bypass anti-bot
protections; prefer polite request rates and a documented user agent.

---

## Data model

### `ipos`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PK | Internal canonical ID. |
| `normalized_name` | TEXT UNIQUE NOT NULL | Cross-source identity (`normalize_name(name)`). |
| `name` | TEXT NOT NULL | Display name. |
| `category` | TEXT | `Mainboard`, `SME`, or a source-specific category. |
| `issue_price` | REAL | Upper/issue price currently. |
| `issue_price_lower` | REAL | Lower end of the price band (IPO Watch). |
| `issue_price_upper` | REAL | Upper end of the price band (IPO Watch). |
| `estimated_listing_price` | REAL | From IPO Watch. |
| `ipo_size_cr` | TEXT | Issue size in ₹ crore (still text). |
| `pe` | REAL | Post-issue P/E where available. |
| `sector` | TEXT | From IPO Watch. |
| `exchange` | TEXT | e.g. `NSE`, `BSE`, `NSE/BSE`, `NSE Emerge`. |
| `lot_size` | TEXT | e.g. `1,200 shares`. |
| `subscription` | REAL | Overall subscription multiple. |
| `open_date` | TEXT | ISO date string. |
| `close_date` | TEXT | ISO date string. |
| `listing_date` | TEXT | ISO date string. |
| `status` | TEXT | e.g. `Upcoming`, `Open`, `Closed`, `Listed`. |
| `gmp_indicator` | TEXT | Emoji/indicator from source. |
| `source_url` | TEXT | IPO detail page on the source site. |
| `rhp_url` | TEXT | Reserved for the official RHP/DRHP link. |

### `gmp_history`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PK | |
| `ipo_id` | INTEGER FK → `ipos.id` | `ON DELETE CASCADE`. |
| `source` | TEXT NOT NULL | `InvestorGain`, `IPO Watch`. |
| `gmp` | REAL | Absolute premium (₹). |
| `gmp_percent` | REAL | Percentage premium. |
| `recorded_at` | TEXT NOT NULL | UTC ISO timestamp. |
| `snapshot_date` | TEXT | UTC day (`YYYY-MM-DD`) used for dedupe. |
| `scrape_run_id` | INTEGER | The `scrape_runs` row that produced this value. |

`gmp_history` keeps one row per `(ipo_id, source, snapshot_date)`, enforced by a
unique index. Repeated scrapes on the same UTC day update that day's row instead
of appending duplicates; `scrape_run_id` records which run last touched it.

### `scrape_runs`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Internal run ID. |
| `source` | TEXT NOT NULL | Scraper that ran (`IPO Watch`, `InvestorGain`). |
| `status` | TEXT NOT NULL | `running`, `completed`, or `failed`. |
| `started_at` | TEXT NOT NULL | UTC ISO timestamp when the run began. |
| `completed_at` | TEXT | UTC ISO timestamp when the run finished. |
| `rows_scraped` | INTEGER | Total rows fetched from the source. |
| `rows_saved` | INTEGER | Rows persisted to `ipos` / `gmp_history`. |
| `rows_failed` | INTEGER | Rows that errored during conversion or save. |
| `error_message` | TEXT | Fetch error, if the run failed entirely. |

One row is created per source per scrape command (`scrape` or `run`).

---

## Setup

Requires **Python 3.12+** for the backend and **Node.js 20+** for the frontend.

```bash
git clone <repo-url>
cd "IPO Checker"

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r backend/requirements.txt
```

For development (adds pytest):

```bash
pip install -r backend/requirements-dev.txt
```

Copy `backend/.env.example` to `backend/.env` only if you need to override a default.
The database schema is created/upgraded automatically on first use, and can also be
initialised explicitly (idempotent):

```bash
cd backend
python -m src.database.db
```

### Frontend

Start the API (see [Usage](#usage)), then install and run the app:

```bash
cd frontend
cp .env.example .env.local   # optional; defaults to http://localhost:8000
npm install
npm run dev                  # http://localhost:3000
```

`NEXT_PUBLIC_API_BASE_URL` points the frontend at the API. Other scripts:
`npm run build`, `npm run start`, `npm run lint` (Next 16 no longer lints during
build), and `npx next typegen` after adding routes. See
[`frontend/README.md`](frontend/README.md) for structure and current limitations.

---

## Usage

Run from the `backend/` directory so `src.` imports resolve.

```bash
cd backend

# Scrape every source and persist the results
python -m src.main scrape

# One source at a time
python -m src.main scrape --source ipowatch
python -m src.main scrape --source investorgain

# Screen + analyse candidates, persist analysis_reports, print a summary
python -m src.main analyze

# Machine-readable output
python -m src.main analyze --json

# Generate a PDF (written to reports/ by default)
python -m src.main report
python -m src.main report --output reports/today.pdf

# Validate the email without sending it
python -m src.main report --email --dry-run

# Full pipeline: scrape -> analyse -> PDF -> email
python -m src.main run
python -m src.main run --email
```

Useful flags:

| Flag | Applies to | Meaning |
| --- | --- | --- |
| `--min-gmp` | `analyze`, `report`, `run` | Override `MIN_GMP_PERCENT` (default `20`). |
| `--include-upcoming` | `analyze`, `report`, `run` | Include IPOs with an `Upcoming` status. |
| `--no-persist` | `analyze`, `report`, `run` | Do not write rows to `analysis_reports`. |
| `--json` | `analyze` | Print the full analysis payload as JSON. |
| `--output` | `report`, `run` | PDF output path. |
| `--email` | `report`, `run` | Email the PDF using the SMTP settings. |
| `--dry-run` | `report`, `run` | Validate the email without connecting. |
| `--db-path` | all | Override the SQLite database for one command. |

The low-level scrapers still run on their own:

```bash
python -m src.scrapers.investorgain
python -m src.scrapers.ipowatch
```

Inspecting the data:

```bash
python - <<'PY'
import sqlite3
c = sqlite3.connect("data/ipo_intelligence.db")
for row in c.execute("""
    SELECT i.name, g.gmp, g.gmp_percent, g.source, g.recorded_at
    FROM ipos i
    JOIN gmp_history g ON g.ipo_id = i.id
    ORDER BY g.recorded_at DESC
    LIMIT 10
"""):
    print(row)
PY
```

---

## Configuration

Settings live in `backend/src/config.py`, are read from environment variables (or a local
`.env`), and all have safe defaults. `.env.example` documents the full contract:

```ini
# Database
IPO_DB_PATH=data/ipo_intelligence.db

# Logging
LOG_LEVEL=INFO

# Screening
MIN_GMP_PERCENT=20
INCLUDE_UPCOMING=false

# HTTP
REQUEST_TIMEOUT=30
REQUEST_DELAY_SECONDS=1.0
USER_AGENT=IPO-Checker/0.1 (personal research; polite scraper)

# Sources
INVESTORGAIN_REPORT_ID=331
INVESTORGAIN_YEAR=2026
INVESTORGAIN_FISCAL_YEAR=2026-27
# IPOWATCH_API_URL=https://ipowatch.in/server/api/ipo/GetIpoListingByStatus

# Reporting
REPORT_OUTPUT_DIR=reports/

# Email (SMTP)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USER=you@example.com
SMTP_PASSWORD=app-password
EMAIL_FROM=you@example.com
EMAIL_TO=you@example.com
EMAIL_SUBJECT_PREFIX=[IPO Checker]

# AI (optional; local or cloud through one provider interface)
LLM_ENABLED=false
LLM_PROVIDER=ollama            # ollama | lmstudio | llamacpp | openai | anthropic | gemini | openai-compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=                   # required only for cloud providers
LLM_MODEL=qwen2.5:7b-instruct
LLM_EMBED_PROVIDER=ollama      # may differ from the chat provider
LLM_EMBED_MODEL=nomic-embed-text
LLM_FALLBACK_PROVIDERS=        # optional chain, e.g. ollama,openai
LLM_ALLOW_CLOUD=false          # explicit opt-in before documents leave the machine
LLM_TEMPERATURE=0
LLM_TIMEOUT_SECONDS=120
LLM_MAX_CONTEXT=8192
LLM_CACHE=true

# API / frontend
API_HOST=127.0.0.1
API_PORT=8000
API_TOKEN=change-me
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Add `.env.example` to the repo and keep real `.env` files gitignored (already
covered by `.gitignore`). AI must remain **off by default** so the scrape → analyse →
report → email pipeline works on a machine with no GPU, model runtime, or API key.

Switching AI providers is a **config change, not a code change**. The same prompts,
JSON schemas, citation checks and cache keys are used everywhere. Local providers are
the default; cloud providers are opt-in and should only receive data you are
comfortable sending to that vendor. The `LLM_*` keys are documented ahead of the AI
layer; the core pipeline ignores them until it lands.

---

## Known issues

These are the gaps that remain after the backend P1 hardening pass. Resolved items
(GMP dedupe, HTTP hardening, logging, ruff, provenance) have been removed.

1. **InvestorGain report ID still defaults to `331`.** The URL, year, and fiscal year
   are configurable (`INVESTORGAIN_*`) and the fiscal year is derived, but the report
   ID must be updated per season.
2. **No dedupe across sources.** Identity relies entirely on `normalize_name`; minor
   spelling differences (`&` vs `and`, abbreviations) create duplicate IPOs.
3. **Connection churn.** `save_ipo_with_gmp()` still opens separate connections for
   the IPO upsert, the GMP upsert and the provenance upsert; no transaction batching.
4. **`COALESCE` upserts cannot clear values.** Stale fields can never be set back to
   `NULL`, and there are no `created_at`/`updated_at` row timestamps.
5. **Weak typing.** Dates and `ipo_size_cr` are stored as text; no DB-level validation.
6. **No research-grade financial data model.** Financial statements, ratios, peers,
   subscription snapshots and per-fact source citations are not stored yet; the flat
   `ipos` row is the only source. See the
   [research framework](docs/ipo-research-framework.md).
7. **Email has no delivery log, retry policy, or idempotency.** Each `--email`
   run sends immediately; transient SMTP failures abort the send, and nothing
   records previous sends. The body is plain text, not HTML.
8. **The PDF has no GMP trend chart or app deep links.** The history is stored and
   used for the textual trend, but the report only contains tables and cannot route
   the reader into the app for in-depth analysis.
9. **Frontend and auth gap.** The API exists, but there is no web UI and no
   authentication beyond the optional `X-API-Token` on mutating endpoints.
10. **No document store.** RHP/DRHP PDFs are not fetched, parsed, chunked, or
    indexed, so there is nothing for an AI layer to cite.
11. **No AI provider abstraction, guardrails or evaluation.** There is no common
    local/cloud provider interface, prompt versioning, schema validation, caching,
    citation tracking, or golden-set tests yet.

---

## Where AI is needed

AI should be used for **reading, explaining, and retrieving** information — not for
the business rules. The minimum-GMP filter, calculations, scoring, persistence, and
delivery must stay deterministic and testable.

| Need | AI's job | Deterministic code's job |
| --- | --- | --- |
| **RHP / DRHP understanding** | Extract objects of issue, risk factors, financial highlights, red flags; summarise with page citations. | PDF fetch/parse, chunking, embedding storage, citation verification. |
| **Analysis narrative** | Turn computed metrics into "top strengths / top risks / why this verdict". | Compute every metric, score, threshold, and pass/fail result. |
| **Cross-source entity resolution** | Suggest matches using embeddings/similarity between company names. | Alias table, thresholds, `normalize_name`, and a manual review queue. |
| **Chat over current IPOs** | Understand the question, choose a whitelisted data tool, synthesise an answer with citations. | SQL queries, filters, GMP math, access control, and data freshness. |
| **Scraper repair fallback** | Convert an unfamiliar HTML/PDF layout into schema-constrained JSON when the parser fails. | Validate with pydantic, diff against previous output, and require human approval before writing. |
| **Report / email prose** | Optional: draft a readable summary paragraph. | Template layout, numbers, recipients, attachments, and sending. |
| **News / commentary (optional)** | Classify sentiment and extract events (e.g. "GMP cut", "issue postponed"). | Store source URL, timestamp, and confidence; never overwrite official fields. |

**Do not use AI for:** the 20% GMP filter, GMP % arithmetic, date parsing, candidate
selection, scoring math, DB upserts, email delivery, authentication, or anything that
must be reproducible and auditable.

### Model choices: local and cloud

| Deployment | Examples | Best for | Trade-offs |
| --- | --- | --- | --- |
| **Local** | Ollama, LM Studio, llama.cpp, vLLM; Qwen2.5 7B/14B, Llama 3.1 8B, Gemma 3 12B, or newer equivalents | Privacy, offline use, no per-token cost, full control over documents | Needs RAM/VRAM and time; smaller models reason less well |
| **Cloud** | OpenAI, Anthropic, Google Gemini, Azure OpenAI, AWS Bedrock, OpenRouter, Groq | Stronger reasoning, long context, no local GPU | Per-token cost, data leaves the machine, rate limits, vendor terms |
| **Embeddings** | Local: `nomic-embed-text`, `bge-m3`, `e5`. Cloud: OpenAI, Gemini, Voyage | Local is cheap and private; cloud is convenient at scale | Keep the embedding model stable when switching chat models |
| **Optional reranker** | Local `bge-reranker`; cloud Cohere Rerank or similar | Better retrieval over long RHP documents | Extra latency and cost |

**Seamless switching design**

- **One internal contract.** Every provider implements
  `generate(messages, response_schema) -> validated object`, `embed(texts) -> vectors`,
  `health()` and `capabilities()`. Callers import the interface, never a vendor SDK.
- **OpenAI-compatible adapter first.** It covers Ollama, LM Studio, llama.cpp server,
  vLLM, OpenAI, OpenRouter, Groq and compatible gateways. Native adapters exist only
  where the API differs materially (for example Anthropic or Gemini).
- **Config-only selection.** `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`,
  `LLM_API_KEY` and `LLM_FALLBACK_PROVIDERS` choose the provider. No caller changes.
- **Same behaviour everywhere.** Prompt versions, JSON schemas, citation validation,
  caching and evaluation are shared, so a cloud answer is checked exactly like a
  local one.
- **Capability flags.** `json_mode`, `tools`, `embeddings`, `vision`, `context_window`
  and `cost` let features degrade gracefully when a provider lacks something.
- **Optional fallback chain.** If the preferred provider is down, the next one in
  `LLM_FALLBACK_PROVIDERS` can run — but a fallback to cloud is logged and never
  silent.
- **Mix and match.** Chat can run on a cloud model while embeddings stay local (or
  the reverse), which is often the best privacy/cost balance.
- **Provenance per call.** Every output stores provider, model, prompt version,
  token counts and cost, so switching never mixes up which model produced what.
- **Local-first default.** Cloud is disabled unless `LLM_ALLOW_CLOUD=true`.

Switching from a local model to a cloud provider is just an env change — no
application code changes:

```ini
# Local (default)
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5:7b-instruct
LLM_API_KEY=
LLM_ALLOW_CLOUD=false

# Cloud (OpenAI-compatible)
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=<cloud-model-name>
LLM_API_KEY=<your-key>
LLM_ALLOW_CLOUD=true
```

Anthropic and Gemini use the same `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY`
contract through their native adapters.

### AI guardrails

- **Schema-constrained output** (JSON mode + pydantic validation); reject
  unparseable output and fall back to templates.
- **Prompt versioning and caching** keyed by content hash, provider, model, and
  prompt version.
- **Citations required** for any claim sourced from an RHP or news item.
- **Treat scraped documents as untrusted data**, never as instructions — they can
  contain prompt-injection text.
- **No raw SQL from the model.** It may only call whitelisted functions such as
  `search_ipos(filters)`, `get_ipo(id)`, `get_gmp_history(id, days)`,
  `compare_ipos(ids)`, and `get_analysis(id)`.
- **Store provenance** for every AI output: provider, model, prompt version,
  inputs, raw output, citations, token counts, cost, and creation time.
- **Local-first, cloud opt-in.** `LLM_ALLOW_CLOUD=false` blocks cloud providers
  unless explicitly enabled. Never silently fall back from local to cloud.
- **Data minimisation.** Send only the chunks needed, redact secrets/PII, and keep
  an allowlist of document types that may leave the machine.
- **Per-provider controls.** API keys stay server-side; set timeouts, retries,
  rate limits, token/cost budgets, and a data-retention/region policy.
- **Audit every call.** Record whether data left the machine, which provider saw
  it, and how much it cost.
- **Same validation everywhere.** Cloud output gets the same schema, citation and
  hallucination checks as local output.
- **Graceful degradation:** if the selected provider is missing, unconfigured or
  slow, the rest of the pipeline still works and the UI shows "AI unavailable".
- **No investment advice.** Answers must show data timestamps and the standard
  disclaimer, and must not tell the user to buy or sell.

---

## Planned architecture

```
Next.js frontend/  ──HTTP + SSE──▶  FastAPI backend/api  ──▶  SQLite data/
   dashboard                        │
   IPO detail                       ├──▶  AI providers (local or cloud)
   chat UI                          ├──▶  backend/llm (provider interface, RAG,
                                    │                   extraction, cache)
                                    └──▶  backend/reporting (PDF + email)

Scheduled job (backend/src/main.py): scrape → analyse → filter (GMP ≥ 20%) → report → email
```

### Components

| Component | Stack | Responsibility |
| --- | --- | --- |
| **Web app** | Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + Recharts | Dashboard, IPO detail, GMP charts, analysis, report downloads, streaming chat. |
| **API** | FastAPI + pydantic | Read-only data endpoints, chat streaming, protected admin actions (scrape/report). |
| **AI layer** | Provider-agnostic `backend/llm`: local (Ollama, LM Studio, llama.cpp) or cloud (OpenAI, Anthropic, Gemini, OpenAI-compatible) | One interface for embeddings, RAG, structured extraction, narrative generation, caching and provider switching. |
| **Chat layer** | `backend/chat` + AI SDK `useChat` | Intent → whitelisted tool calls → grounded answer with citations. |
| **Pipeline** | Existing Python modules + `backend/src/main.py` | Scrape, normalise, persist, filter, analyse, render, email. |

### API surface

Implemented today: `GET /api/ipos`, `GET /api/ipos/{id}` (including GMP history,
provenance and the latest analysis), `GET /api/candidates`, `GET`/`POST /api/reports`,
`GET /api/reports/{filename}`, `GET /api/quality/duplicates` and `GET /api/health`.
`POST /api/analyze` and `POST /api/reports` are token-protected. Search/sort, the
overview/in-depth financial endpoints, chat streaming, admin scrape and AI provider
health are still planned.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/ipos?status=&min_gmp=20&limit=&offset=` | Paginated, filterable IPO shortlist (search/sort still planned). |
| `GET` | `/api/ipos/{id}` | Full IPO record + latest GMP + source links. |
| `GET` | `/api/ipos/{id}/overview` | Compact overview: business snapshot, issue structure, valuation, GMP, key financial trend, strengths/risks, completeness. |
| `GET` | `/api/ipos/{id}/financials` | In-depth annual/quarterly statements, ratios, peer comparison and per-fact citations. |
| `GET` | `/api/ipos/{id}/gmp-history?days=30` | Time series for charts. |
| `GET` | `/api/ipos/{id}/analysis` | Metrics, score, strengths, risks, citations. |
| `GET` | `/api/reports` | Generated report history + download URLs. |
| `POST` | `/api/chat` | Streaming (SSE) chat grounded in current IPO data. |
| `POST` | `/api/admin/scrape` | Trigger a scrape; token-protected, disabled by default. |
| `GET` | `/api/health` | DB, scheduler, and configured AI provider availability. |

### Chat design ("talk to current IPOs")

Example questions the assistant should handle:

- "Which active IPOs have GMP above 30% and close this week?"
- "Compare the valuation and GMP trend of the top two SME IPOs."
- "What are the main risks in the RHP of the highest-GMP IPO?"
- "Why did this IPO make the shortlist, and what data is missing?"

Flow: question → tool selection against whitelisted data functions → retrieve
structured rows and document chunks → answer with inline citations
(`IPO name · source · recorded_at`, `RHP p. 123`) → show a "data as of" timestamp.
If the data does not exist, the assistant must say so rather than guess.

### Frontend pages

- **Dashboard** — active IPOs, GMP ≥ 20% filter (default), sortable table, status and
  close-date badges, last-scrape health.
- **IPO detail** — price/dates, GMP trend chart, source history, analysis score,
  strengths/risks, RHP citations, red flags.
- **Chat** — streaming conversation with suggested prompts, citations, and a clear
  "not investment advice" banner.
- **Reports** — list/download generated PDFs and re-send emails (opt-in).

### Local deployment

```bash
# 1. Start the local model runtime (optional; skip for a cloud provider)
ollama serve
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text

# 2. Backend
uvicorn src.api.main:app --host 127.0.0.1 --port 8000

# 3. Frontend
cd web && npm install && npm run dev
```

To use a cloud provider instead, set `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`
and `LLM_ALLOW_CLOUD=true`. No code changes are needed; local Ollama remains the
default. A `docker-compose.yml` (api + web + optional local model runtime + volume
for `data/`) is planned so the whole stack starts with one command. Bind services
to localhost by default; never expose the API or a local model runtime publicly
without authentication.

---

## Roadmap / TODO

Work is tracked as checkboxes. `P0` = blocks the core pipeline, `P1` = needed for
the first end-to-end product (including frontend/chat), `P2` = polish/hardening. AI
features stay **optional at runtime** even when their delivery is marked `P1`.

### 1. Improve the web scrapers

- [x] **P0 — Consolidate helpers.** Remove the duplicated scraper from
      `backend/utils/normalization.py`; keep only `normalize_name`/parsing helpers.
- [x] **P0 — Fix and finish IPO Watch parsing.**
  - [x] Consume the JSON API behind the GMP page instead of regex-scraping HTML.
  - [x] Map fields by name from the payload (no fixed column indexes).
  - [x] Normalise dates to ISO; the API provides open/close/listing separately.
  - [x] Handle missing/dash/blank values and `₹`, `%`, commas via shared helpers.
- [ ] **P1 — Make InvestorGain resilient.**
  - [x] Move report ID / fiscal year / source URL into config.
  - [x] Discover the current fiscal year dynamically (or fall back safely).
  - [x] Add row-level `try/except` so one malformed row does not abort the run.
  - [ ] Keep the raw payload in `debug_responses/` (rotating, capped) for debugging.
- [ ] **P1 — HTTP hardening (both sources).**
  - [x] Shared `requests.Session` with retry/backoff (`urllib3.Retry`).
  - [x] Explicit `User-Agent`, `Accept`, timeouts.
  - [x] Rate limiting / polite delay between requests
        (`REQUEST_DELAY_SECONDS` + `RateLimiter`).
  - [x] Clear, typed exceptions (`ScraperError`, `FetchError`, `ParseError`).
- [x] **P1 — Source abstraction.** `BaseScraper` in `src/scrapers/base.py`
      (`source_name`, `fetch()`, `rows()`, `convert_row()`, `parse()`, `scrape()`)
      with `InvestorGainScraper` and `IpoWatchScraper` implementations.
- [ ] **P2 — Add more sources** (NSE/BSE, Chittorgarh, Moneycontrol, IPO Central)
      behind the same interface, with per-source enable/disable flags.
- [x] **P2 — Scraper tests** for the IPO Watch payload mapping, offline and
      deterministic. Add fixtures for error/CAPTCHA responses when those sources are
      touched again.
- [ ] **P2 — Health check.** Detect empty/partial results and alert instead of
      overwriting good data.

### 2. Keep proper database information

- [x] **P0 — Fix the broken analysis imports** by adding the missing modules
      (`backend/src/config.py`, `backend/src/utils/parsing.py`) or removing the dead references.
- [x] **P1 — Add a migration mechanism.** `schema_migrations` table + numbered
      migrations in `src/database/migrations.py`; `initialize_database()` only
      applies pending versions.
- [ ] **P1 — Normalise the schema.**
  - [x] Store dates as ISO-8601 strings consistently.
  - [ ] Make `ipo_size_cr` numeric (`REAL`).
  - [x] Add `issue_price_lower` and `issue_price_upper`, `lot_size`.
  - [ ] Add `face_value`, `registrar`, `lead_managers`, `anchor_investors`.
  - [x] Add `sector`, `exchange`.
  - [x] Add `source_url`, `rhp_url`.
  - [ ] Add `created_at`, `updated_at` (UTC) to every table.
- [x] **P1 — Provenance table `ipo_sources`.**
      `(ipo_id, source, source_ipo_id, source_url, first_seen_at, last_seen_at)`
      with `UNIQUE(source, source_ipo_id)`. Existing history is backfilled by
      migration 6.
- [ ] **P1 — Cross-source matching.**
  - [ ] Match on `ipo_sources` first, then normalized name.
  - [ ] Add an alias table for known variants (`&`/`and`, `Ltd`, abbreviations).
  - [ ] Consider fuzzy matching with a similarity threshold + manual review queue.
- [x] **P2 — GMP snapshots without duplicates.**
  - [x] Bucket by scrape run (`scrape_run_id`) and
        `UNIQUE(ipo_id, source, snapshot_date)`.
  - [x] Index `gmp_history(ipo_id, recorded_at)`.
- [ ] **P2 — Performance & safety.**
  - [ ] One connection per job, context managers, batched `executemany`.
  - [ ] `PRAGMA journal_mode=WAL`.
  - [x] Resolve `DB_PATH` relative to the repo root, not the CWD.
  - [ ] Add retention policy for old history rows.
- [x] **P2 — Query helpers.** `get_candidates(min_gmp_percent)`,
      `get_gmp_history(ipo_id)`, and `get_ipo(id)`. SQL views are still optional.
- [ ] **P2 — Data quality checks.**
  - [x] Duplicate-name detection (`GET /api/quality/duplicates`, read-only).
  - [ ] Missing prices, GMP outliers, date inversions (close < open), stale rows.

### 3. Minimum GMP of 20% or more

- [x] **P1 — Make 20% the enforced default** (`MIN_GMP_PERCENT=20`) everywhere,
      through `src.config` and `select_candidates()`.
- [x] **P1 — Compute `gmp_percent` when missing** as
      `(gmp / issue_price) * 100` and flag it as derived.
- [x] **P1 — Filter definition.** Keep only active/upcoming IPOs whose **latest**
      GMP percentage is `>= 20.0`. Exclude listed/withdrawn/cancelled.
- [x] **P1 — Source disagreement handling.** When sources disagree, use the latest
      observation, keep both in `gmp_history`, and expose the spread through
      `source_spread_percent` in the analysis metrics, checklist and risks.
- [ ] **P2 — Guardrails.** Ignore zero/negative GMP, absurd outliers (`> 500%`),
      and rows with no `issue_price` (unless GMP% is provided directly).
- [ ] **P2 — Tests.** Boundary tests at 19.9 / 20.0 / 20.1, missing percent, and
      negative GMP.

### 4. Complete the IPO analysis

- [x] **P1 — Build `backend/analysis/` properly.**
  - [x] `__init__.py`, `filters.py`, `metrics.py`, `scoring.py`, `checklist.py`.
  - [x] Output a typed `IPOAnalysis` object (pydantic) and persist it to the
        `analysis_reports` table (JSON payload + score + `created_at`).
- [x] **P1 — Automate the standard checks** from the
      [analysis checklist](#ipo-analysis-checklist): GMP and trend, valuation, issue
      size, subscription and cross-source consistency are scored automatically;
      peer valuation, financials, objects of issue and red flags are marked
      `manual` until the RHP pipeline lands.
- [x] **P1 — Scoring.** Transparent weighted score (GMP 25%, valuation 25%,
      fundamentals 25%, subscription 15%, risk 10%) with per-factor explanations.
      No black-box model.
- [ ] **P2 — Store analysis inputs.** Subscription numbers and fundamentals need
      their own tables/snapshots, not just the free-text `ipos` row.
- [x] **P2 — Human-readable summary** per IPO: strengths, risks, verdict
      (`Strong / Watch / Avoid`) and the reasons.

### 5. Generate a PDF and email it

- [x] **P1 — PDF generation.**
  - [x] Add `backend/reporting/pdf.py`; use ReportLab.
  - [x] Cover heading: run date, threshold, upcoming flag.
  - [x] Shortlist table: name, verdict, score, GMP %, issue price, close date.
  - [x] Per-IPO sections: score breakdown, checklist, strengths, risks, data gaps.
  - [x] Footer: disclaimer and data-gap warnings.
  - [x] Write to `reports/ipo_report_YYYYMMDD_HHMMSS.pdf` (gitignored).
- [x] **P1 — Email delivery.**
  - [x] Add `backend/reporting/emailer.py` (SMTP over TLS, app password from env).
  - [x] Plain-text body summary + PDF attachment.
  - [x] Recipients from `EMAIL_TO` (comma-separated).
  - [x] `--dry-run` mode that writes the PDF and prints the email instead of sending.
  - [ ] Log every send to `email_log` (`sent_at`, recipients, status, error).
- [ ] **P2 — Reliability.**
  - [ ] Retry transient SMTP failures; never email an empty report.
  - [ ] Idempotency: one report per day/run.
  - [ ] Optional scheduling (Task Scheduler / cron / APScheduler).
  - [ ] GMP trend charts in the PDF.

### 6. Add AI enrichment (local or cloud)

All AI features are **optional and non-blocking**; `LLM_ENABLED=false` must keep the
pipeline fully functional. Local and cloud providers sit behind one interface, so
switching is config-only.

- [ ] **P1 — Provider abstraction.** `backend/llm/client.py` +
      `backend/llm/providers/` with a common `LLMProvider` contract
      (`generate`, `embed`, `health`, `capabilities`), an OpenAI-compatible adapter
      (Ollama, LM Studio, llama.cpp, vLLM, OpenAI, OpenRouter, Groq), native
      Anthropic/Gemini adapters where needed, timeouts, retries, and a
      `NullProvider` fallback.
- [ ] **P1 — Seamless provider switching.** Config-only selection
      (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`,
      `LLM_FALLBACK_PROVIDERS`), capability flags, shared prompts/schemas/cache, and
      independent chat and embedding providers.
- [ ] **P1 — Cloud safety.** `LLM_ALLOW_CLOUD=false` by default; explicit opt-in;
      data minimisation and redaction; per-provider rate limits, budgets, region and
      retention settings; audit provider/model/tokens/cost per call.
- [ ] **P1 — Structured extraction.** JSON-schema prompts + pydantic validation for
      RHP/DRHP fields (objects of issue, risk factors, financials, red flags).
- [ ] **P1 — Document ingestion + RAG.** Fetch RHP PDFs, extract text with page
      numbers, chunk (≈800–1200 tokens, overlap), embed with the configured
      embedding provider (local by default), and store `documents` /
      `document_chunks` with citations.
- [ ] **P1 — Narrative generation.** Convert computed metrics into strengths, risks,
      and a verdict explanation; persist provider/model/prompt version in
      `analysis_reports`.
- [ ] **P1 — Evaluation harness.** A golden set of RHP questions and expected facts;
      measure extraction accuracy, citation validity, and hallucination rate across
      local and cloud models, including cost and latency.
- [ ] **P2 — Entity-resolution embeddings** to suggest cross-source name matches for
      the review queue.
- [ ] **P2 — Parser-failure fallback** for changed HTML/PDF layouts, gated behind
      schema validation and human approval.
- [ ] **P2 — Optional news/commentary classification** with source URLs and
      timestamps.
- [ ] **P2 — Prompt-injection tests** using adversarial text embedded in a fake RHP.

### 7. Build the Next.js frontend and IPO chat

- [x] **P1 — FastAPI service.** Read-only endpoints for IPOs, details, GMP history,
      candidates, analysis, reports, duplicate detection and provenance, plus
      token-protected `POST /api/analyze` and `POST /api/reports`. `/api/chat`
      streaming and admin scrape are still planned.
- [x] **P1 — Next.js scaffold** in `frontend/` using Next.js 16 App Router, React 19,
      TypeScript 5 and Tailwind 4, with Cache Components. shadcn/ui, TanStack Table
      and Recharts are not installed yet; the table and GMP sparkline are local.
- [x] **P1 — Dashboard.** Active IPO table with the **20% minimum GMP** filter as
      the default, status filter, stats, empty/error/loading states and a backend
      reachability panel. Search, sort and close-date badges are still planned.
- [x] **P1 — IPO detail page.** GMP sparkline and source history, issue metrics,
      stored score/checklist/strengths/risks/data gaps, and provenance. RHP
      citations await the research data model.
- [ ] **P1 — Chat backend.** Whitelisted tools, retrieval over current IPOs +
      analysis + RHP chunks, streaming SSE, citations, and refusal when data is
      missing.
- [ ] **P1 — Chat UI.** Streaming messages, suggested prompts, citation chips,
      "data as of" timestamp, and disclaimer banner. (Placeholder page exists.)
- [x] **P2 — Reports page.** List and download generated PDFs. Re-emailing remains
      planned and stays token-protected on the backend.
- [ ] **P2 — Local deployment.** `docker-compose.yml` for api + web + optional local
      model runtime with a persistent `data/` volume and health checks;
      localhost-only by default.
- [ ] **P2 — Security.** Bearer-token or session auth for any non-localhost access,
      rate limiting on chat, and no secrets in the client bundle.
- [ ] **P2 — Quality.** API tests, Playwright end-to-end tests, loading/error/empty
      states, keyboard accessibility, and responsive dark mode.

### 8. Research-grade overview, financial analysis and PDF deep links

These are the next product goals. The full specification lives in
[`docs/ipo-research-framework.md`](docs/ipo-research-framework.md). AI runs through
a **single provider interface**: local models (Ollama / LM Studio / llama.cpp) are
the default, and cloud providers (OpenAI / Anthropic / Gemini / OpenAI-compatible)
are opt-in. Switching is a config change, not a code change.

- [ ] **P1 — Overview + in-depth split in the app.**
  - [ ] **Overview tab**: company/business snapshot, issue structure, price band,
        lot size, fresh vs OFS, valuation, GMP, subscription, top strengths/risks,
        data completeness and confidence.
  - [ ] **In-depth tab**: annual/quarterly P&L, balance sheet, cash flow, ratios,
        growth, peers, promoter/management, litigation, industry, SME module,
        post-listing performance, and source citations.
  - [ ] Add `GET /api/ipos/{id}/overview` and `GET /api/ipos/{id}/financials`
        (see [API surface](#api-surface)).
  - [ ] Persist the underlying data in the research tables
        (`financial_periods`, `financial_facts`, `financial_ratios`, `peers`,
        `subscription_snapshots`, `source_citations`) instead of extending the
        flat `ipos` row.
- [ ] **P1 — Financial analysis pipeline.**
  - [ ] Parse financial statements from the RHP/annual reports with page-level
        citations.
  - [ ] Compute the formulas in section C of the framework and persist
        `formula_version` with every derived ratio.
  - [ ] Add data-quality states (`reported` / `calculated` / `estimated` /
        `unverified` / `missing`) and a per-IPO completeness score.
  - [ ] Test every formula, including missing inputs, zero denominators and
        restated periods.
- [ ] **P1 — Summary PDF that routes into the app.**
  - [ ] Keep the shortlist summary PDF, but make it an index into the app.
  - [ ] One page per IPO: snapshot, key metrics, top 3 strengths/risks, verdict,
        confidence and data gaps.
  - [ ] Add deep links to `/ipos/{id}` and `/ipos/{id}?tab=financials`, plus a QR
        code, so the reader can jump straight into the in-depth analysis.
  - [ ] Add `APP_BASE_URL` config (default `http://localhost:3000`); never put
        secrets or API tokens in the PDF.
  - [ ] Keep the detailed per-IPO PDF as the downloadable in-depth report.
- [ ] **P1 — Provider-agnostic AI layer.**
  - [ ] Common interface for local and cloud providers (`generate`, `embed`,
        `health`, `capabilities`); OpenAI-compatible adapter plus native
        Anthropic/Gemini adapters where needed.
  - [ ] Config-only switching (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`,
        `LLM_API_KEY`, `LLM_FALLBACK_PROVIDERS`); callers never import a vendor SDK.
  - [ ] Local-first default; `LLM_ALLOW_CLOUD=false` unless explicitly enabled;
        never silently send documents to a cloud provider.
  - [ ] Same prompts, JSON schemas, citation checks, caching and evaluation across
        providers; store provider/model/prompt version with every output.
  - [ ] `LLM_ENABLED=false` falls back to deterministic templates, so the core
        pipeline still works without a model.
  - [ ] Five summaries (Business Quality, Financial Health, Valuation, Risk/Red
        Flags, Overall Assessment) with evidence, conclusion, confidence, missing
        information and citations.
  - [ ] Wait for the user to confirm local model names/VRAM and cloud
        keys/regions, then set the provider config.
  - [ ] Add prompt versioning, schema validation, caching, citation checks and a
        golden-set evaluation before trusting any generated narrative.
- [ ] **P2 — Post-listing feedback loop.**
  - [ ] Track 1-week / 1-month / 3-month / 6-month / 1-year returns.
  - [ ] Compare verdicts with outcomes and recalibrate scoring only with evidence.

### Cross-cutting engineering tasks

- [x] **P0 — Add `requirements.txt`** (runtime) and `requirements-dev.txt`
      (runtime + tests), pinned.
- [x] **P0 — Add `backend/src/main.py` CLI**: `scrape`, `analyze`, `report`, `run`
      (scrape → analyse → filter → PDF → email), with `--dry-run`, `--min-gmp`,
      `--source`, `--include-upcoming`, `--no-persist`, `--json` and `--db-path`.
- [x] **P1 — Core DB tables.** `scrape_runs`, `ipo_sources` and
      `schema_migrations` exist alongside `ipos`, `gmp_history` and
      `analysis_reports`.
- [ ] **P1 — AI/chat DB tables** for `documents`, `document_chunks`,
      `chat_sessions`, `chat_messages`, and `email_log`.
- [ ] **P1 — API contract** documented via FastAPI's OpenAPI schema and shared
      TypeScript types generated for `frontend/`.
- [ ] **P1 — Demo/seed mode** so the frontend can be developed without live scrapes
      or an AI provider.
- [x] **P1 — Logging** via `logging`; configured from `LOG_LEVEL` with a per-source
      run summary and row-level errors. `rich` formatting is optional polish.
- [x] **P1 — Tests** (`pytest`) for normalisation, parsing, status logic, IPO Watch
      mapping and DB upserts/query helpers.
- [x] **P1 — Add `.env.example`** and load config through `python-dotenv`.
- [ ] **P2 — Tooling**: `ruff` (lint + format), `mypy`, `eslint`/`prettier`,
      pre-commit hooks, and CI covering pytest, the Next.js build, and Playwright.
- [ ] **P2 — Type hints everywhere** and docstrings for public functions.
- [ ] **P2 — Make the first git commit** and add a short `CHANGELOG.md`.

---

## IPO analysis checklist

Reference list of what is normally reviewed before applying to an Indian IPO. The
automated analysis in task 4 should cover as many of these as the data allows, and
clearly mark the rest as "manual review needed".

### Market / GMP
- [ ] Grey-market premium today and its trend over the last 7–14 days.
- [ ] GMP % vs issue price (our hard filter: **≥ 20%**).
- [ ] Consistency between sources; sudden spikes/drops.
- [ ] Estimated listing price and implied listing gain.
- [ ] Kostak rate (for SME IPOs), where available.

### Valuation
- [ ] Issue P/E vs industry / listed peer P/E.
- [ ] Post-issue vs pre-issue P/E; EPS dilution.
- [ ] Price-to-book, EV/EBITDA where meaningful.
- [ ] Whether the issue is priced at a discount/premium to peers.

### Issue structure
- [ ] Fresh issue vs offer-for-sale (OFS) mix — 100% OFS = no growth capital.
- [ ] Issue size and market cap at upper band.
- [ ] Lot size and minimum retail application amount.
- [ ] Anchor investor participation and lock-in.
- [ ] Promoter holding before/after, dilution, and any pledge.

### Business & financials
- [ ] Revenue, EBITDA, PAT growth (3 years) and margins.
- [ ] Debt/equity, interest coverage, working-capital cycle.
- [ ] ROE / ROCE and cash-flow quality (CFO vs PAT).
- [ ] Customer/supplier concentration and related-party transactions.
- [ ] Auditor changes/qualifications and other governance red flags.

### Demand
- [ ] Subscription by QIB / NII / retail (overall and by day).
- [ ] Retail application count and oversubscription trend.
- [ ] Grey-market demand vs subscription demand.

### Risk & context
- [ ] Objects of the issue and whether they are credible.
- [ ] Key risk factors from the RHP (litigation, regulatory, customer loss).
- [ ] Sector outlook and recent comparable listings.
- [ ] Lead managers / registrar track record.
- [ ] Lock-in expiry and post-listing supply overhang.
- [ ] Red flags: high valuation, tiny free float, promoter selling, shell-like
      financials, unexplained auditor resignation.

### Output
- [ ] Numeric score + `Strong / Watch / Avoid` verdict.
- [ ] Top 3 strengths and top 3 risks per IPO.
- [ ] Data gaps that require manual reading of the RHP.

---

## Definition of done

The project is considered "working" when a single command (or one local stack) can:

1. Scrape all enabled sources and upsert clean, deduplicated data into SQLite.
2. Select active IPOs with **latest GMP ≥ 20%**, including computed/derived GMP %.
3. Produce a structured analysis per IPO covering the checklist above.
4. Render a dated PDF report with GMP trends and verdicts.
5. Email that PDF to the configured recipients, with a run summary and logs.
6. Run unattended on a schedule without creating duplicate rows or duplicate emails.
7. Serve a Next.js dashboard showing the same shortlist, GMP history, and analysis,
   with an **Overview** tab and an **In-depth** financial-analysis tab per IPO.
8. Generate a **summary PDF** that lists the shortlist and deep-links (URL + QR)
   into the app for the full analysis.
9. Answer free-text questions about current IPOs through the configured LLM
   provider (local or cloud), with citations, data timestamps, and no raw-SQL access.
10. Switch between local and cloud AI providers through **config only**, with
    local-first defaults, explicit cloud opt-in, and the core pipeline working even
    when no provider is available.
11. Start the whole stack locally with one command.
