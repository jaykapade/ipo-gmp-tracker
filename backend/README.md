# IPO Checker — backend

Python service: scrapers → SQLite → rule-based screen and score → PDF/email,
plus optional AI research. Everything that decides (filters, numbers, scores)
is deterministic; AI only reads, explains and researches.

## Setup

Python 3.12+ and [uv](https://docs.astral.sh/uv/). Run everything from
`backend/`.

```bash
uv venv && uv pip install -r requirements-dev.txt
cp .env.example .env.local   # optional; every key has a safe default
```

Env load order: real environment, then `.env.local`, then `.env`. The schema
is created and migrated automatically. (uv's "No `requires-python` value"
warning is harmless.)

## Commands

```bash
uv run python -m src.main scrape [--source ipowatch]
uv run python -m src.main analyze [--json]        # screen + score
uv run python -m src.main report [--email --dry-run]
uv run python -m src.main run --research --email  # scrape → analyse → research → PDF → email
uv run python -m src.main research <id> | --all-open
uv run python -m src.main notify [--dry-run]      # daily digest to subscribers
uv run python -m src.main serve                   # http://127.0.0.1:8000 (docs at /docs)
```

Useful flags: `--min-gmp` (default 20), `--include-upcoming`, `--no-persist`,
`--research-max-age HOURS` (reuse fresher research; `0` always re-runs),
`--db-path`. Only IPOs whose **latest** GMP meets the screen get a rule-based
score.

Tests: `uv run pytest -q` (offline; HTTP and the `claude` CLI are faked) and
`uv run ruff check src tests`.

## Configuration

Every key is documented in `.env.example`. Main groups: `IPO_DB_PATH`,
`MIN_GMP_PERCENT`, `RESEARCH_MAX_AGE_HOURS`, `INVESTORGAIN_*`/`IPOWATCH_*`,
`SMTP_*`/`EMAIL_*`, `SITE_URL`, `DIGEST_RESEARCH`, `API_*`, `LLM_*`.

`API_TOKEN` guards every endpoint that changes data or spends AI quota. Only
the frontend server sends it (after checking Google sign-in), so set the same
non-default value in `frontend/.env.local` and keep the backend port private.

## AI

Off by default (`LLM_ENABLED=false`); the pipeline works without it.
Switching provider is config only.

- **Providers:** local `ollama`, `lmstudio`, `llamacpp`, `vllm`,
  `openai-compatible`; cloud `openai`, `openrouter`, `groq`, `anthropic`,
  `gemini` (need `LLM_API_KEY` and `LLM_ALLOW_CLOUD=true`); `claude-code` for a
  Claude Pro/Max subscription via the `claude` CLI.
- **Roles:** analyst, verifier, extractor, challenger (optional), researcher
  (web search, `claude-code` only), embedder. Override any with
  `LLM_ROLE_<ROLE>_{PROVIDER,MODEL,BASE_URL,API_KEY,FALLBACKS}`.
- **Profiles** (full blocks in `.env.example`): *local* (Ollama), *personal*
  (`claude-code` after `claude auth login`), *commercial* (`anthropic` API,
  same model ids).

`claude-code` strips `ANTHROPIC_API_KEY` so calls bill the subscription,
caps parallel calls at `LLM_MAX_CONCURRENCY` (2) and is for personal use only.
`GET /api/health` shows each role's provider, model and availability. Model
choices are in the [framework §P](../docs/ipo-research-framework.md#p-ai-stack).

### Research pipeline (`src/research/`)

1. **Gather** — the researcher searches the web (official and exchange sources
   first) and returns facts with URLs (`W1…`); app data is added as `D1…`.
2. **H1–H4** — business, financials, valuation, risks, each in a fresh context.
3. **Citation gate** — evidence citing unknown fact ids is dropped.
4. **Verify** — the verifier marks each finding agree/disagree/unsupported;
   the rest form the dispute log.
5. **Challenge** — optional ruling on disputes.
6. **H5** — verdict, top strengths/risks, what would change the view.

Each output is stored in `ai_outputs` with provider, model, prompt version and
input hash. A run takes ~2–5 min and ~7 model calls.

## Scheduling and email

`run --research --email` is the daily job. It researches only screened IPOs,
reuses research newer than `RESEARCH_MAX_AGE_HOURS`, never starts a duplicate
run, and still sends the report if AI is off or fails. The PDF has an
overview page plus one page per IPO (both verdicts, numbers, sources); the
email is HTML with a text alternative and the PDF attached.

**SMTP:** Gmail needs an app password; Mailjet uses the API key as
`SMTP_USER` and the secret as `SMTP_PASSWORD`, with a verified `EMAIL_FROM`.
A free-mail `EMAIL_FROM` through Mailjet fails DMARC and lands in spam — use
an own domain with SPF/DKIM/DMARC.

**Subscribers:** signed-in users toggle the daily email in the frontend
footer (sent to their verified Google address). `notify` emails open IPOs and
latest GMP; `notify --research` (or `DIGEST_RESEARCH=true`) sends the full
research report instead. Every email has an unsubscribe link to `SITE_URL`.

**Task Scheduler:** `scripts/scheduled-run.ps1` runs report + digest and logs
to `logs/`. Flags: `-DryRun`, `-NoResearch`, `-NoNotify`.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\scheduled-run.ps1 -DryRun

$script = (Resolve-Path scripts\scheduled-run.ps1).Path
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At 18:30
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName 'IPO Checker daily' -Action $action -Trigger $trigger -Settings $settings
```

Register it as your own user (not SYSTEM) so `claude-code` finds your login.

## HTTP API

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/health` | DB, AI provider, per-role status |
| GET | `/api/ipos` | `q`, `status`, `min_gmp`, `category`, `has_research`, `sort`, `order`, `limit`, `offset` |
| GET | `/api/ipos/facets` | Filter values with counts |
| GET | `/api/ipos/{id}` | Detail, GMP history, sources, analysis |
| GET / POST* | `/api/ipos/{id}/research` | Latest run / queue a run (`202`) |
| GET | `/api/research/runs/{run_id}` | Run status |
| GET | `/api/candidates` | Screened, analysed IPOs |
| POST* | `/api/analyze` | Run the analysis |
| GET / POST* | `/api/reports` | List / generate PDFs |
| GET | `/api/reports/{filename}` | Download a PDF |
| GET | `/api/quality/duplicates` | Possible cross-source duplicates |
| POST* | `/api/chat` | Streaming (SSE) grounded chat |
| GET* / PUT* | `/api/subscribers` | Daily-email state for an address |
| POST* | `/api/subscribers/unsubscribe` | Unsubscribe by email-link token |

\* needs `API_TOKEN`.

## Data

Sources: InvestorGain and IPO Watch JSON APIs (open IPOs only), plus the web
for AI research. Tables (migrations in `src/database/migrations.py`): `ipos`,
`gmp_history` (one row per IPO/source/day), `ipo_sources`, `scrape_runs`,
`analysis_reports`, `research_runs`, `ai_outputs`, `subscribers`,
`schema_migrations`.

## Known issues

- InvestorGain's report id (`INVESTORGAIN_*`, default `331`) changes per season.
- Cross-source matching relies on name normalisation; check
  `/api/quality/duplicates`.
- Upserts cannot clear values; dates and issue size are stored as text.
- No RHP document store yet; research facts come from the web and are
  unverified.
- Web research works only on `claude-code`, not the `anthropic` API provider.
- No email delivery log or retry; two runs in a day send twice.
- Any Google account can sign in and spend AI quota.
