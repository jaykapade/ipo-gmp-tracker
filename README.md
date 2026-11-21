# IPO Checker

Personal research toolkit for Indian IPOs. It scrapes grey-market premium (GMP)
and issue data, stores it in SQLite, screens and scores IPOs with transparent
rules, emails PDF reports, and serves a Next.js dashboard. It can also run
**AI research**: Claude (or a local model) gathers cited facts from the web,
reviews them from four isolated perspectives, an independent verifier
challenges the findings, and a synthesis is shown **beside** — never instead
of — the rule-based score.

> **Not investment advice.** GMP is unofficial and speculative and can vanish
> before listing. Verify everything against the official RHP and NSE/BSE filings.

## Documentation

| Read this | For |
| --- | --- |
| [`backend/README.md`](backend/README.md) | Setup, CLI, configuration, AI providers/roles/profiles, the research pipeline, HTTP API, data model, known issues |
| [`frontend/README.md`](frontend/README.md) | Running the app, pages, dashboard filters, the AI research tab, structure |
| [`docs/ipo-research-framework.md`](docs/ipo-research-framework.md) | The research specification: checklist, schema, formulas, AI roles, orchestration, roadmap |

## What works today

| Area | State |
| --- | --- |
| Scraping | InvestorGain and IPO Watch JSON APIs; only currently open IPOs are kept; one GMP row per source per day; source provenance. |
| Storage | SQLite with numbered, idempotent migrations. |
| Screening & scoring | Latest-GMP screen (default **≥ 20%**), weighted transparent score, `Strong / Watch / Avoid`, checklist, strengths, risks, data gaps. |
| Reports | ReportLab PDF and SMTP email (with dry-run); `run --research` adds each screened IPO's AI verdict; a Task Scheduler script runs it daily ([scheduling](backend/README.md#scheduling-and-email)). |
| API | FastAPI: IPOs with filters and facets, detail, GMP history, analysis, reports, AI research runs, streaming chat, health. |
| AI layer | Provider-agnostic: Ollama/LM Studio/llama.cpp/vLLM locally; OpenAI, Anthropic, Gemini, OpenRouter, Groq in the cloud; **`claude-code`** for a Claude Pro/Max subscription. Per-role models (analyst, verifier, extractor, challenger, researcher, embedder), fallback chains, cloud opt-in, off by default. |
| AI research | Web fact gathering with source URLs, H1–H4 isolated perspectives, citation gate, verifier + dispute log, optional challenger, H5 synthesis; every output stored with provider/model/prompt provenance. |
| Frontend | Dashboard (board, GMP, status, research filters; mobile cards), IPO detail with Overview and AI research tabs, reports, chat, AI status in the header. |
| Tests | Offline pytest suite (HTTP and the `claude` CLI are faked), ruff, ESLint, tsc. |

## Quick start

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 20+ and pnpm.

```bash
# 1. Backend
cd backend
uv venv && uv pip install -r requirements-dev.txt
cp .env.example .env.local          # optional; edit AI + API_TOKEN settings
uv run python -m src.main scrape
uv run python -m src.main analyze
uv run python -m src.main serve     # http://localhost:8000

# 2. Frontend (second terminal)
cd frontend
cp .env.example .env.local          # set API_TOKEN to the backend's value
pnpm install
pnpm dev                            # http://localhost:3000
```

To use your Claude subscription for AI: run `claude auth login` once, then
enable the "Claude subscription" profile in `backend/.env.local` (see
[backend AI profiles](backend/README.md#ai-providers-roles-and-profiles)).
Open an IPO and use its **AI research** tab, or run
`uv run python -m src.main research <id>`.

## Repository layout

```text
IPO Checker/
├── backend/     # Python: scrapers, SQLite, analysis, reports, AI layer, research, FastAPI
├── frontend/    # Next.js 16 dashboard, IPO pages, AI research UI, chat
└── docs/        # research framework (specification + roadmap)
```

## Roadmap

The detailed, phase-by-phase plan is in
[framework §O](docs/ipo-research-framework.md#o-implementation-roadmap).
Main open items:

- **Documents:** download and parse the RHP/DRHP (Docling, OCR fallback),
  chunk and embed locally, and check web facts against page-cited official
  text.
- **Financial engine:** periodised financial statements, ratios and peers
  stored as data, feeding an in-depth tab and research-grade scoring.
- **Reports:** summary PDF with GMP charts and deep links/QR codes into the
  app; email delivery log and retries.
- **Data quality:** cross-source matching beyond name normalisation, typed
  dates/sizes, outlier guards, scraper health alerts, more sources.
- **AI quality:** golden-set evaluation, prompt-injection tests, web research
  on the `anthropic` API provider for commercial use.
- **Ops:** one-command local stack (docker-compose), scheduled runs, real auth
  before any non-localhost exposure, generated TypeScript types from OpenAPI.

## Definition of done

The project is "working" when one local stack can:

1. Scrape all enabled sources into clean, de-duplicated SQLite data.
2. Select active IPOs with **latest GMP ≥ 20%**, including derived GMP %.
3. Produce a structured analysis per IPO covering the
   [research checklist](docs/ipo-research-framework.md#a-complete-research-checklist).
4. Render a dated PDF with GMP trends and verdicts, and email it.
5. Run unattended on a schedule without duplicate rows or emails.
6. Serve a dashboard with the shortlist, GMP history, analysis, and an
   overview plus in-depth view per IPO.
7. Produce a summary PDF that deep-links into the app.
8. Answer questions and run cited research through the configured AI
   provider, with timestamps and no raw-SQL access.
9. Switch between local, subscription and API providers through config only,
   with the core pipeline working when no provider is available.
10. Start the whole stack with one command.
