# IPO Checker

Personal research tool for Indian IPOs. It scrapes grey-market premium (GMP)
and issue data into SQLite, screens and scores IPOs with transparent rules,
emails PDF reports and serves a Next.js dashboard. Optional **AI research**
gathers cited facts from the web, reviews them from four isolated
perspectives plus an independent verifier, and shows the result beside
(never instead of) the rule-based score.

> **Not investment advice.** GMP is unofficial and speculative. Verify
> everything against the RHP and NSE/BSE filings.

## Quick start

Needs Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 20+ and pnpm.

```bash
make install   # backend venv + frontend packages
make dev       # API on :8000 and app on :3000
make help      # every other shortcut
```

Without `make` (Windows: `winget install ezwinports.make`):

```bash
cd backend && uv venv && uv pip install -r requirements-dev.txt
cp .env.example .env.local
uv run python -m src.main scrape && uv run python -m src.main serve

cd frontend && cp .env.example .env.local && pnpm install && pnpm dev
```

Set the same `API_TOKEN` in both `.env.local` files. For AI on a Claude
subscription, run `claude auth login` once and enable the Claude profile in
`backend/.env.local`.

## Before deploying

Local use needs none of this.

- Set `SITE_URL` in `backend/.env` to the public frontend address (email
  unsubscribe links use it).
- Add the deployed callback `https://<domain>/api/auth/callback/google` to
  the Google OAuth client and set `AUTH_URL` in the frontend env.
- Send from an own domain: set `EMAIL_FROM` on it and add Mailjet's
  SPF/DKIM plus a DMARC record. A free-mail sender lands in spam and can't
  mail other people reliably.
- Keep the backend port private; only the frontend server should reach it.

## Docs

| File | Covers |
| --- | --- |
| [backend/README.md](backend/README.md) | CLI, config, AI providers, research pipeline, scheduling, email, API, data model |
| [frontend/README.md](frontend/README.md) | Env vars, pages, sign-in, structure |
| [docs/ipo-research-framework.md](docs/ipo-research-framework.md) | Research spec: checklist, formulas, scoring, AI roles, roadmap |

## Layout

```text
backend/    Python: scrapers, SQLite, analysis, reports, AI layer, FastAPI
frontend/   Next.js 16 dashboard, IPO pages, AI research, chat
docs/       research spec and roadmap
```
