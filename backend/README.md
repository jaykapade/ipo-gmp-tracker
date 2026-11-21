# IPO Checker — backend

Python service that scrapes Indian IPO data, stores it in SQLite, screens and
scores it with transparent rules, writes PDF reports, and — optionally — runs
**AI research** that gathers cited facts from the web and reviews them from
four isolated perspectives with an independent verifier.

Everything that decides (filters, calculations, scores) is deterministic. AI
only reads, explains and researches, and its output is always shown beside the
rule-based score, never instead of it.

> Not investment advice. Grey-market premium is unofficial and speculative.
> Verify everything against the official RHP and NSE/BSE filings.

## Contents

- [Setup](#setup)
- [Everyday commands](#everyday-commands)
- [Configuration](#configuration)
- [AI: providers, roles and profiles](#ai-providers-roles-and-profiles)
- [AI research pipeline](#ai-research-pipeline)
- [Scheduling and email](#scheduling-and-email)
- [HTTP API](#http-api)
- [Data sources](#data-sources)
- [Data model](#data-model)
- [Project layout](#project-layout)
- [Tests and linting](#tests-and-linting)
- [Known issues](#known-issues)

---

## Setup

Requires **Python 3.12+** and **[uv](https://docs.astral.sh/uv/)**. Run every
command from `backend/` so `src.` imports resolve.

```bash
cd backend
uv venv                                  # creates backend/.venv
uv pip install -r requirements-dev.txt   # runtime + pytest + ruff
```

The SQLite schema is created and upgraded automatically through numbered
migrations on first use (or explicitly with `uv run python -m src.database.db`).

Settings are optional — every value has a safe default. To override, copy
`.env.example` to **`.env`** or **`.env.local`** (both gitignored). Load order:
real environment variables win, then `.env.local`, then `.env`.

> `uv` may print "No `requires-python` value found". It is harmless: the
> project is installed with `uv pip`, not as a uv project.

## Everyday commands

```bash
uv run python -m src.main scrape                 # fetch every source
uv run python -m src.main scrape --source ipowatch
uv run python -m src.main analyze                # screen + score, store results
uv run python -m src.main analyze --json
uv run python -m src.main report                 # analyse + PDF in reports/
uv run python -m src.main report --email --dry-run
uv run python -m src.main run --email            # scrape → analyse → PDF → email
uv run python -m src.main run --research --email # … plus AI research in the PDF/email
uv run python -m src.main research 1             # AI research for IPO #1
uv run python -m src.main research --all-open    # AI research for every open IPO
uv run python -m src.main serve                  # API on http://127.0.0.1:8000
```

| Flag | Applies to | Meaning |
| --- | --- | --- |
| `--min-gmp` | `analyze`, `report`, `run` | Override `MIN_GMP_PERCENT` (default `20`). |
| `--include-upcoming` | `analyze`, `report`, `run` | Include IPOs with an `Upcoming` status. |
| `--no-persist` | `analyze`, `report`, `run` | Do not write `analysis_reports` rows. |
| `--json` | `analyze` | Print the full analysis payload as JSON. |
| `--output` | `report`, `run` | PDF output path. |
| `--email` / `--dry-run` | `report`, `run` | Email the PDF / validate without sending. |
| `--research` | `report`, `run` | Research each **screened** IPO (reusing recent results) and add the AI verdict to the PDF and email. |
| `--research-max-age HOURS` | `report`, `run` | Reuse completed research newer than this (default `RESEARCH_MAX_AGE_HOURS`, 24; `0` always re-runs). |
| `--all-open` | `research` | Research every open IPO, one after another. |
| `--host`, `--port`, `--reload` | `serve` | Bind address and dev auto-reload. |
| `--db-path` | all | Use a different SQLite file for one command. |

`analyze` only scores IPOs whose **latest** GMP meets the screen (default
20%). IPOs below it get no rule-based score, so their AI research shows
"Rule-based score: not computed".

## Configuration

`src/config.py` reads these from the environment. `.env.example` documents
every key; the important groups are:

| Group | Keys |
| --- | --- |
| Database | `IPO_DB_PATH` (default `data/ipo_intelligence.db`) |
| Screening | `MIN_GMP_PERCENT` (20), `INCLUDE_UPCOMING` |
| Scheduled research | `RESEARCH_MAX_AGE_HOURS` (24) |
| HTTP / sources | `REQUEST_TIMEOUT`, `REQUEST_DELAY_SECONDS`, `USER_AGENT`, `INVESTORGAIN_*`, `IPOWATCH_*` |
| Reports / email | `REPORT_OUTPUT_DIR`, `SMTP_*`, `EMAIL_*` |
| API | `API_HOST`, `API_PORT`, `API_TOKEN`, `CORS_ORIGINS` |
| AI | `LLM_*`, `LLM_ROLE_<ROLE>_*`, `RERANK_PROVIDER`, `RESEARCH_*` — see below |

`API_TOKEN` protects the endpoints that change data or spend AI quota
(`POST /api/analyze`, `/api/reports`, `/api/ipos/{id}/research`, `/api/chat`,
`/api/subscribers*`). Only the frontend's server sends it, after checking the
visitor's Google sign-in, so the backend knows the request came through that
check. Change it from `change-me` and set the same value as `API_TOKEN` in
`frontend/.env.local`.

## AI: providers, roles and profiles

AI is **off by default** (`LLM_ENABLED=false`); the whole pipeline works
without it. Switching provider is a config change — callers depend only on the
`LLMProvider` contract in `src/llm/base.py`.

**Providers:** `ollama`, `lmstudio`, `llamacpp`, `vllm`, `openai-compatible`
(local) · `openai`, `openrouter`, `groq`, `anthropic`, `gemini` (cloud, need
`LLM_API_KEY`) · `claude-code` (Claude Pro/Max subscription through the
headless `claude` CLI). Every cloud provider also needs `LLM_ALLOW_CLOUD=true`.

**Roles** (framework §P). Each role can use its own provider/model via
`LLM_ROLE_<ROLE>_{PROVIDER,MODEL,BASE_URL,API_KEY,FALLBACKS}`; unset fields
inherit the global `LLM_*` values.

| Role | Job | Local model | Claude |
| --- | --- | --- | --- |
| analyst | H1–H4 perspectives, H5 synthesis, chat answers | `qwen3.5:9b-q4_K_M` | `claude-sonnet-5-5` |
| verifier | challenges every finding | `gemma4:12b` | `claude-opus-5-5` |
| extractor | schema-bound JSON, reranking | `qwen3.5:4b-q4_K_M` | `claude-haiku-5-5` |
| challenger | rules on disputes (optional; off until its model is set) | `gpt-oss:20b` | `claude-opus-5-5` |
| researcher | web research (inherits the extractor's settings) | — | Haiku or Sonnet via `claude-code` |
| embedder | vectors (`LLM_EMBED_*`) | `qwen3-embedding:0.6b` | stays local (no Claude embeddings) |

**Profiles** — full blocks are in `.env.example`:

| Mode | Use when | Settings |
| --- | --- | --- |
| Local | free and private | `LLM_PROVIDER=ollama` + local role models |
| Personal (subscription) | just you, on a Claude Pro/Max plan | `LLM_PROVIDER=claude-code`, `LLM_ALLOW_CLOUD=true`, run `claude auth login` once |
| Commercial | other people use the app | `LLM_PROVIDER=anthropic` + `LLM_API_KEY` — same model ids |

`claude-code` runs one `claude -p` process per call with tools, MCP servers,
project settings and session persistence disabled (the researcher role alone
gets `WebSearch`/`WebFetch`). It strips `ANTHROPIC_API_KEY` from the child
environment so usage is billed to the subscription, caps parallel calls with
`LLM_MAX_CONCURRENCY` (default 2), and logs that it is for personal use only.
Web research is not yet available on the `anthropic` API provider.

Fallbacks may pin their own model, e.g.
`LLM_FALLBACK_PROVIDERS=ollama=qwen3.5:9b-q4_K_M`. `GET /api/health` reports
the login state and each role's provider, model and availability.

## AI research pipeline

`src/research/` implements framework §H for one IPO at a time:

1. **Gather** — the researcher role searches the web (RHP/SEBI/company and
   NSE/BSE first, then reputable media) and returns schema-validated facts,
   each with a source URL and a source type (`official`, `exchange`,
   `secondary`). The pipeline assigns ids (`W1…`) and adds facts from this
   app's own data (`D1…`: price band, GMP trend, subscription, rule-based
   score).
2. **Perspectives H1–H4** — business quality, financial health, valuation,
   risks. Each runs in a fresh context and sees only the fact pack.
3. **Citation gate** — evidence citing unknown fact ids is removed and counted.
4. **Verify** — the verifier gets the findings and the evidence (not the
   analyst's reasoning) and marks each `agree`/`disagree`/`unsupported`;
   non-agreements form the dispute log.
5. **Challenge** — if configured, the challenger rules on each dispute.
6. **Synthesis H5** — verdict (`Strong`/`Watch`/`Avoid`), three strengths,
   three risks and what would change the view, written beside the
   deterministic score.

Every output is stored in `ai_outputs` with provider, model, prompt version
(`research-v1`), input hash, tokens and whether data left the machine. A run
takes ~2–5 minutes and about 7 model calls (more with a challenger).

Start a run from the CLI (`research <id>`), the API, or the **AI research**
tab on an IPO's page. API runs execute one at a time on a background worker;
a run interrupted by a restart is marked failed on the next start.

Tunables: `RESEARCH_TIMEOUT_SECONDS` (600), `RESEARCH_MAX_TURNS` (30).

## Scheduling and email

### What each command does

| Step | Command | AI? |
| --- | --- | --- |
| 1. Scrape | `scrape` — open IPOs + one GMP row per source per day | No |
| 2. Analyse | `analyze` — screen latest GMP ≥ `MIN_GMP_PERCENT`, score, store | No |
| 3. Research | `research <id>` / `--all-open`, the UI button, or `run --research` | Yes |
| 4. Report | `report` — analyse + PDF (+ `--email`) | Only with `--research` |
| All | `run` — 1 → 2 → (3) → 4 | Only with `--research` |
| Digest | `notify` — open IPOs + latest GMP to confirmed subscribers | No |

`run --research --email` is the scheduled job. After the analysis it
researches only the IPOs that passed the screen, one at a time:

- completed research newer than `RESEARCH_MAX_AGE_HOURS` is **reused**, so a
  daily schedule researches each IPO about once a day;
- an IPO already being researched (e.g. from the UI) is not started twice;
- if AI is off, or a run fails, the report still goes out with a note, and the
  previous completed result (if any) is shown, labelled as such.

The PDF opens with an overview page (verdict counts and a summary table) and
gives each IPO its own page: verdict tiles (rule-based score beside the AI
view), key numbers, rule-based strengths/risks/gaps, the AI research block
(conclusion, top strengths and risks, when it was researched), the score
breakdown, the checklist and the sources. The email is HTML (one card per IPO
with both verdicts, key numbers, the top strength/risk and the opening of the
AI view) with a plain-text alternative, and the PDF attached. The rule-based
score is unchanged by any of it.

Every report also ends each IPO with a **Sources** block of clickable links:
the market-data pages the numbers were scraped from (the IPO Watch detail
page, the InvestorGain GMP board at `INVESTORGAIN_PAGE_URL`, and the RHP when
known), then the web pages the AI research cited, official and exchange
sources first (up to 30; the rest are in the app's AI research tab). The
email body lists the market-data links and a count of the research sources.

Time and cost: ~2–5 minutes and ~7 model calls per IPO that needs fresh
research; with the default 20% screen that is usually 0–3 IPOs a day.

### Email setup

Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM` and
`EMAIL_TO` in `.env.local`, then check it without sending.

For Gmail: `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USE_TLS=true`,
`SMTP_USER` = the Gmail address. `SMTP_PASSWORD` must be a 16-character **app
password** (Google Account → Security → 2-Step Verification → App passwords),
not the normal account password; Gmail rejects that over SMTP.

For Mailjet (free plan, ~200 emails/day): `SMTP_HOST=in-v3.mailjet.com`,
`SMTP_PORT=587`, `SMTP_USE_TLS=true`, `SMTP_USER` = the API key,
`SMTP_PASSWORD` = the secret key (Account settings → API keys).
`EMAIL_FROM` must be a sender address verified in Mailjet (Account settings →
Senders & domains).

**Landing in spam?** A `@gmail.com` (or other free-mail) `EMAIL_FROM` sent
through Mailjet fails DMARC alignment, because Gmail's domain does not
authorise Mailjet's servers, so receivers treat it as spoofed. Use an address on
a domain you own and add Mailjet's SPF and DKIM DNS records for it (Senders &
domains → the domain → "Setup SPF/DKIM"), then add a DMARC record. Marking the
first mails "Not spam" also trains your own inbox.

```bash
uv run python -m src.main run --research --email --dry-run
```

### Subscribers (daily digest)

Signed-in visitors turn the daily email on or off in the frontend footer. It
goes to their Google account's address, which Google has already verified, so
there is no confirmation email. Every email has an unsubscribe link to
`SITE_URL/subscription?action=unsubscribe&token=…` that works without signing
in.

`notify` emails every confirmed subscriber the open IPOs with their latest GMP
(highest GMP first, up to 50), one email per subscriber with their own
unsubscribe link (also as a `List-Unsubscribe` header). Nothing is sent on days
without open IPOs. The scheduled script runs it after the report.

`notify --research` sends subscribers the same email as `run --research
--email` instead (the screened IPOs, AI research and the PDF), plus their
unsubscribe link. It uses stored research and never starts a run, so run it
after `run --research`; nothing is sent when no IPO passes the screen. Set
`DIGEST_RESEARCH=true` in `.env.local` to make that the default, which also
turns it on for the scheduled job; `--no-research` sends the digest once.

```bash
uv run python -m src.main notify --dry-run
```

Before inviting other people: the sender must be allowed to mail any address
(a Mailjet account with a verified own domain, see "Landing in spam?"), and the
free Mailjet plan caps sending at about 200 emails a day.

### Windows Task Scheduler

`scripts/scheduled-run.ps1` runs the job from `backend/` and appends output
to `logs/scheduled-YYYY-MM-DD.log`. Try it once by hand (`-DryRun` skips
sending; `-NoResearch` skips AI; `-NoNotify` skips the subscriber digest):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\scheduled-run.ps1 -DryRun
```

Register a daily task (example: 18:30 every day, as your own user — the
`claude-code` provider uses your Claude login, so not as SYSTEM):

```powershell
$script = (Resolve-Path scripts\scheduled-run.ps1).Path
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At 18:30
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName 'IPO Checker daily' -Action $action -Trigger $trigger -Settings $settings
```

`-StartWhenAvailable` runs a missed time once the PC is back on. Run it now
with `Start-ScheduledTask 'IPO Checker daily'`, remove it with
`Unregister-ScheduledTask 'IPO Checker daily'`. GMP moves during the day, so
an evening run (after grey-market updates, before the next day's closes)
works well; add a second trigger for a morning run if you want one.

## HTTP API

Start with `uv run python -m src.main serve`; interactive docs at
`http://127.0.0.1:8000/docs`.

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/health` | DB path, AI provider, per-role status |
| GET | `/api/ipos` | `q`, `status`, `min_gmp`, `category` (`mainboard`/`sme`), `has_research`, `sort`, `order`, `limit`, `offset` |
| GET | `/api/ipos/facets` | Filter values that exist, with counts, plus the screen floor |
| GET | `/api/ipos/{id}` | Detail, GMP history, sources, latest analysis, research status |
| GET | `/api/ipos/{id}/research` | Latest run with all outputs (`null` if never run) |
| POST | `/api/ipos/{id}/research` | **Token.** Queue a run → `202`; returns the active run if one exists |
| GET | `/api/research/runs/{run_id}` | Run status for polling |
| GET | `/api/candidates` | IPOs passing the screen, analysed |
| POST | `/api/analyze` | **Token.** Run the analysis |
| GET / POST | `/api/reports` | List PDFs / **token** generate one |
| GET | `/api/reports/{filename}` | Download a PDF |
| GET | `/api/quality/duplicates` | Possible cross-source duplicates |
| POST | `/api/chat` | **Token.** Streaming (SSE) grounded chat (the frontend proxies it) |
| GET / PUT | `/api/subscribers` | **Token.** `?email=` → `{subscribed}` / `{email, subscribed}` turns the daily email on or off |
| POST | `/api/subscribers/unsubscribe` | **Token.** `{token}` from the email link; `404` if unknown |

## Data sources

| Source | Type | Notes |
| --- | --- | --- |
| InvestorGain | JSON API (undocumented) | Report id/year/fiscal year configurable via `INVESTORGAIN_*`; the id changes per season. |
| IPO Watch | JSON API | Price band, sector, lot size, subscription, dates. |
| The web (AI research) | via the researcher role | Facts carry URLs and a source type; secondary sources are flagged. |

Scrapers only save IPOs that are currently **open** (or derived as open from
their dates). Be polite — never bypass anti-bot protection.

## Data model

Created by numbered migrations in `src/database/migrations.py`.

| Table | Purpose |
| --- | --- |
| `ipos` | One canonical row per IPO (`normalized_name` is the cross-source key). |
| `gmp_history` | One GMP row per IPO, source and UTC day. |
| `ipo_sources` | Which source reported each IPO, first/last seen. |
| `scrape_runs` | One row per source per scrape, with counts and errors. |
| `analysis_reports` | Deterministic analysis payloads (score, verdict, checklist). |
| `research_runs` | AI research runs: status, stage, error, timestamps (migration 7). |
| `ai_outputs` | Every AI output with provenance: kind (`facts`, `h1`–`h5`, `verification`, `challenge`, `disputes`), provider, model, prompt version, input hash, tokens, `data_left_machine`. |
| `schema_migrations` | Applied migration versions. |

## Project layout

```text
backend/
├── src/
│   ├── main.py            # CLI: scrape / analyze / report / run / research / serve
│   ├── config.py          # env settings, LLM roles, .env/.env.local loading
│   ├── pipeline.py        # scrape + analyse orchestration
│   ├── api/               # FastAPI app, routes, schemas, streaming chat
│   ├── analysis/          # filters, metrics, scoring, checklist
│   ├── database/          # migrations + query helpers
│   ├── llm/               # provider contract, providers, client, reranker
│   ├── research/          # schemas, prompts, gather, orchestrator, jobs
│   ├── reporting/         # PDF, email, text summary, subscriber digest
│   ├── scrapers/          # InvestorGain, IPO Watch
│   └── utils/             # HTTP, parsing, normalisation, dedupe
└── tests/                 # pytest suite (offline; fakes for HTTP and the CLI)
```

## Tests and linting

```bash
uv run pytest -q          # offline: HTTP and the claude CLI are faked
uv run ruff check src tests
```

## Known issues

1. **InvestorGain report id** defaults to `331` and must be updated per season.
2. **Cross-source identity** relies on `normalize_name`; spelling differences
   can create duplicates (see `/api/quality/duplicates`).
3. **Upserts cannot clear values** (`COALESCE`), and dates/issue size are text.
4. **No document store yet.** AI research reads the web; the Phase 2 RHP
   pipeline (download, Docling parse, chunk, embed) will let facts be checked
   against official documents with page citations.
5. **Web research needs `claude-code`.** The `anthropic` API provider does not
   yet wire up server-side web search.
6. **Email** has no delivery log or retry, so a schedule that runs twice in a
   day sends twice; the PDF has no charts or deep links.
7. **Auth**: the backend trusts one shared `API_TOKEN` from the frontend's
   server, which checks Google sign-in. Keep the backend's port private (only
   the frontend should reach it). Any Google account can sign in, so anyone
   who signs in can spend AI quota on chat and research.
